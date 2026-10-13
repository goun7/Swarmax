"""Fleet status reporting tests — the "is my fleet working?" answer path.

Covers the operator-facing status surface (FleetConsole summary / open alarms /
per-agent / hourly rollup + the WeeklyReport digest) with every expected value
derived from the store or from the APD signal map, never hard-coded.
"""
import random
from datetime import datetime, timedelta, timezone

from swarmax.console import FleetConsole
from swarmax.report import WeeklyReport
from swarmax.db import connect, init_db_with_migrations
from swarmax.fleet import emitter
from swarmax.metrics.apd import SEVERITY_ORDER, SIGNAL_MAP
from swarmax.pipeline import Pipeline
from swarmax.sealing import generate_seed, seal_ledger, verify_seals

AGENTS = ("agent-alpha", "agent-beta")
DRIFT_BASE = datetime(2026, 9, 1)     # six baseline days, then a drifted day


def first_open_alarm(conn):
    return conn.execute(
        "SELECT * FROM alarms WHERE status='open' ORDER BY created_at LIMIT 1").fetchone()


def fleet_with_real_alarm():
    """A fleet with a genuine pipeline-raised, evidence-anchored drift alarm,
    plus recent spend so the weekly report's 7-day windows are populated."""
    conn = make_conn()
    pipe = Pipeline(conn)
    rng = random.Random(11)
    for d in range(6):
        events, guards = emitter.emit_baseline_day(
            "agent-alpha", DRIFT_BASE + timedelta(days=d), rng)
        pipe.ingest(events, guards)
    events, guards = emitter.emit_s2_tool_drift(
        "agent-alpha", DRIFT_BASE + timedelta(days=7), random.Random(3))
    pipe.ingest(events, guards)
    fired = pipe.evaluate_agent("agent-alpha")
    assert fired, "the drift scenario must raise at least one alarm"
    for agent in AGENTS:
        events, guards = emitter.emit_baseline_day(agent, now_utc(), random.Random(5))
        pipe.ingest(events, guards)
    return conn, pipe


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def make_conn():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


def fleet_with_history() -> "tuple[sqlite3.Connection, Pipeline]":
    """Two agents with one day inside the 24h window and one day outside it."""
    conn = make_conn()
    pipe = Pipeline(conn)
    today = now_utc()
    rng = random.Random(7)
    for day in (today - timedelta(days=2), today):
        for agent in AGENTS:
            events, guards = emitter.emit_baseline_day(agent, day, rng)
            pipe.ingest(events, guards)
    return conn, pipe


def inject_alarm(conn, signal, *, deadline, status="open", agent="agent-alpha"):
    """One alarm row whose severity/SLA come from the APD map."""
    rule = SIGNAL_MAP[signal]
    alarm_id = f"alm-test-{signal}-{stamp(deadline).replace(' ', '-').replace(':', '')}"
    conn.execute(
        "INSERT INTO alarms (alarm_id, agent_id, task_id, signal, event_type,"
        " reason, severity, sla_hours, sla_deadline, trigger_value, protection,"
        " status, created_at) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)",
        (alarm_id, agent, signal, rule.event_type, rule.reason, rule.severity,
         rule.sla_hours, stamp(deadline), rule.protection, status, stamp(now_utc())))
    conn.commit()
    return alarm_id


def parse_ts(v) -> datetime:
    return datetime.fromisoformat(str(v))


# ------------------------------------------------------------------ summary

def test_empty_store_reports_zero_status():
    conn = make_conn()
    s = FleetConsole(conn).summary()
    assert set(s) == {"open_alarms", "breached", "agents", "events_24h"}
    assert s["open_alarms"] == conn.execute(
        "SELECT COUNT(*) AS c FROM alarms WHERE status='open'").fetchone()["c"]
    assert s["agents"] == conn.execute(
        "SELECT COUNT(*) AS c FROM fleet_agents").fetchone()["c"]
    assert s["events_24h"] == 0


def test_summary_matches_independent_recomputation():
    conn, pipe = fleet_with_history()
    horizon = SIGNAL_MAP["error.rate>0.20"].sla_hours
    inject_alarm(conn, "error.rate>0.20",
                 deadline=now_utc() + timedelta(hours=horizon))       # open, future
    inject_alarm(conn, "latency.retry>=3",
                 deadline=now_utc() - timedelta(hours=1))             # open, breached
    inject_alarm(conn, "error.new_class_seen",
                 deadline=now_utc() - timedelta(hours=2), status="resolved")

    s = FleetConsole(conn).summary()

    rows = conn.execute("SELECT status, sla_deadline FROM alarms").fetchall()
    assert s["open_alarms"] == sum(1 for r in rows if r["status"] == "open")
    assert s["breached"] == sum(
        1 for r in rows if r["status"] == "open"
        and parse_ts(r["sla_deadline"]) < now_utc())
    assert s["agents"] == conn.execute(
        "SELECT COUNT(*) AS c FROM fleet_agents").fetchone()["c"]
    day_ago = (now_utc() - timedelta(hours=24)).isoformat(sep=" ")
    assert s["events_24h"] == conn.execute(
        "SELECT COUNT(*) AS c FROM agent_task_events WHERE ts >= ?",
        (day_ago,)).fetchone()["c"]
    assert s["breached"] >= 1 and s["open_alarms"] >= 2


def test_events_24h_window_excludes_older_events():
    conn, pipe = fleet_with_history()
    s = FleetConsole(conn).summary()

    all_rows = conn.execute("SELECT ts FROM agent_task_events").fetchall()
    horizon = now_utc() - timedelta(hours=24)
    expected = sum(1 for r in all_rows if parse_ts(r["ts"]) >= horizon)
    assert s["events_24h"] == expected
    assert s["events_24h"] < len(all_rows)          # the 2-day-old events are out
    assert s["events_24h"] > 0


# ------------------------------------------------------------------ alarm queue

def test_open_alarms_sorted_by_severity_then_deadline():
    conn, pipe = fleet_with_history()
    soon = now_utc() + timedelta(minutes=30)
    later = now_utc() + timedelta(hours=6)
    for signal, deadline in (
            ("latency.retry>=3", later),        # High
            ("error.new_class_seen", soon),     # Critical
            ("error.rate>0.20", later),         # Critical
            ("loop>=2", later)):                # Emergency
        inject_alarm(conn, signal, deadline=deadline)

    rows = FleetConsole(conn).open_alarms()
    # console order = most severe first, then earliest deadline
    expected = sorted(rows, key=lambda r: (-SEVERITY_ORDER[r["severity"]],
                                           parse_ts(r["sla_deadline"])))
    assert [r["alarm_id"] for r in rows] == [r["alarm_id"] for r in expected]
    assert rows[0]["severity"] == "Emergency"
    assert parse_ts(rows[1]["sla_deadline"]) <= parse_ts(rows[2]["sla_deadline"])
    assert all(r["status"] == "open" for r in rows)


def test_open_alarms_hides_resolved_ones():
    conn, pipe = fleet_with_history()
    open_id = inject_alarm(conn, "latency.retry>=3",
                           deadline=now_utc() + timedelta(hours=1))
    inject_alarm(conn, "error.rate>0.20",
                 deadline=now_utc() + timedelta(hours=1), status="resolved")
    ids = [r["alarm_id"] for r in FleetConsole(conn).open_alarms()]
    assert open_id in ids
    assert all(not i.startswith("alm-test-error.rate>0.20") for i in ids)


# ------------------------------------------------------------------ per-agent

def test_per_agent_covers_idle_agents_and_orders_by_lifetime_cost():
    conn, pipe = fleet_with_history()
    conn.execute(
        "INSERT INTO fleet_agents (agent_id, fleet_name, role)"
        " VALUES ('agent-idle', 'fleet', 'worker')")
    conn.commit()

    rows = FleetConsole(conn).per_agent()
    known = {r["agent_id"] for r in conn.execute(
        "SELECT agent_id FROM fleet_agents").fetchall()}
    assert {r["agent_id"] for r in rows} == known       # nobody dropped
    assert "agent-idle" in known

    idle = next(r for r in rows if r["agent_id"] == "agent-idle")
    assert (idle["events"], idle["errors"], idle["cost"]) == (0, 0, 0.0)

    totals = [r["cost_total"] for r in rows]
    assert totals == sorted(totals, reverse=True)       # most expensive first
    assert any(r["cost_total"] > 0 for r in rows)


def test_per_agent_aggregates_match_the_raw_event_table():
    conn, pipe = fleet_with_history()
    day_ago = (now_utc() - timedelta(hours=24)).isoformat(sep=" ")
    month_ago = (now_utc() - timedelta(days=30)).isoformat(sep=" ")

    for r in FleetConsole(conn).per_agent():
        agg = conn.execute(
            "SELECT COUNT(*) AS n, ROUND(SUM(cost_usd), 4) AS cost,"
            " SUM(status='error') AS errs FROM agent_task_events"
            " WHERE agent_id=? AND ts >= ?", (r["agent_id"], day_ago)).fetchone()
        life = conn.execute(
            "SELECT ROUND(SUM(cost_usd), 4) AS c FROM agent_task_events"
            " WHERE agent_id=? AND ts >= ?", (r["agent_id"], month_ago)).fetchone()
        assert r["events"] == agg["n"]
        assert r["errors"] == (agg["errs"] or 0)
        assert r["cost"] == (agg["cost"] if agg["cost"] is not None else 0.0)
        assert r["cost_total"] == (life["c"] if life["c"] is not None else 0.0)


# ------------------------------------------------------------------ hourly

def test_hourly_rollup_matches_event_timestamps():
    conn, pipe = fleet_with_history()
    day_ago = (now_utc() - timedelta(hours=24)).isoformat(sep=" ")
    rows = FleetConsole(conn).hourly()

    expected: dict[int, list[int]] = {}
    for r in conn.execute(
            "SELECT ts, status FROM agent_task_events WHERE ts >= ?", (day_ago,)):
        h = parse_ts(r["ts"]).hour
        bucket = expected.setdefault(h, [0, 0])
        bucket[0] += 1
        bucket[1] += (r["status"] == "error")
    assert rows == sorted((h, v[0], v[1]) for h, v in expected.items())
    assert sum(tasks for _, tasks, _ in rows) == FleetConsole(conn).summary()["events_24h"]


# ------------------------------------------------------------------ weekly report

def test_weekly_report_digest_reports_status_cost_and_evidence():
    conn, pipe = fleet_with_real_alarm()
    alarm_id = first_open_alarm(conn)["alarm_id"]
    pipe.resolve_alarm(alarm_id, "on-call")                      # writes evidence
    seal_ledger(conn, generate_seed())

    text = WeeklyReport(conn).render()
    assert "# Swarmax Weekly Fleet Report" in text
    assert "## 1. Behavioral drift" in text
    assert "## 2. Escalations & SLA" in text
    assert "Medium" in text                                      # the drift report_item
    assert "## 5. Evidence integrity" in text

    # cost ranking appears in descending order by the reported figure
    cost_lines = [ln for ln in text.splitlines() if ln.startswith("- agent-")]
    figures = [float(ln.split("$")[1].split(" ")[0]) for ln in cost_lines]
    assert figures == sorted(figures, reverse=True)
    assert len(cost_lines) == len(AGENTS)

    # the evidence-integrity section cites the seal we just made
    seal = conn.execute(
        "SELECT seal_id, covers_through_seq FROM evidence_seals"
        " ORDER BY covers_through_seq DESC LIMIT 1").fetchone()
    assert seal["seal_id"] in text
    assert f"covers seq ≤ {seal['covers_through_seq']}" in text

    # raise -> resolve anchors link the report back to the ledger (B4)
    assert f"raise ledger#" in text
    assert f"resolve ledger#" in text


def test_report_sla_summary_recounts_alarms_independently():
    conn, pipe = fleet_with_history()
    for signal in ("latency.retry>=3", "error.rate>0.20"):
        inject_alarm(conn, signal, deadline=now_utc() + timedelta(hours=1))
    inject_alarm(conn, "error.new_class_seen",
                 deadline=now_utc() - timedelta(hours=3))              # breached

    sla = WeeklyReport(conn).sla_summary()
    for sev, counts in sla.items():
        rows = conn.execute(
            "SELECT status, sla_deadline FROM alarms WHERE severity=?", (sev,)).fetchall()
        assert counts["count"] == len(rows)
        assert counts["open"] == sum(1 for r in rows if r["status"] == "open")
        assert counts["breached"] == sum(
            1 for r in rows if r["status"] == "open"
            and parse_ts(r["sla_deadline"]) < now_utc())
    assert sla["Critical"]["breached"] == 1


def test_report_first_seen_classes_track_distinct_signatures():
    conn, pipe = fleet_with_history()
    pipe.conn.execute(
        "UPDATE agent_task_events SET error_class='rate_limit'"
        " WHERE agent_id='agent-alpha' AND ts >= ?",
        ((now_utc() - timedelta(days=7)).isoformat(sep=" "),))
    pipe.conn.execute(
        "UPDATE agent_task_events SET error_class='schema_drift'"
        " WHERE agent_id='agent-beta' AND ts >= ?",
        ((now_utc() - timedelta(days=7)).isoformat(sep=" "),))
    pipe.conn.commit()

    rows = WeeklyReport(conn).first_seen_classes()
    classes = {r["error_class"] for r in rows}
    assert classes == {"rate_limit", "schema_drift"}
    text = WeeklyReport(conn).render()
    assert "rate_limit" in text and "schema_drift" in text


# ------------------------------------------------------------------ answer path

def test_fleet_status_answer_path_verifies_under_seal():
    """The portfolio question, end to end: is the fleet working, what did it
    cost, and can the evidence be proved — all from one store."""
    conn, pipe = fleet_with_history()
    inject_alarm(conn, "error.rate>0.20",
                 deadline=now_utc() - timedelta(hours=1))             # breached, open
    triaged = inject_alarm(conn, "latency.retry>=3",
                           deadline=now_utc() + timedelta(hours=1))   # triaged live
    pipe.resolve_alarm(triaged, "on-call")
    seal_ledger(conn, generate_seed())

    console = FleetConsole(conn)
    s = console.summary()
    # 1. is it working? agents are live, the SLA queue is triageable
    assert s["agents"] == len(AGENTS)
    assert s["events_24h"] > 0
    assert s["open_alarms"] == len(console.open_alarms())
    assert s["breached"] >= 1
    # 2. what did it cost? the report ranks agents by spend
    report = WeeklyReport(conn).render()
    assert any(ln.startswith(f"- {a}: $") for a in AGENTS for ln in report.splitlines())
    # 3. can you prove it? chain + seals verify after the triage
    assert verify_seals(conn)["all_ok"]
