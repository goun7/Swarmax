"""Fleet console v2 — auth'd, multi-user, agent drill-down (§5, §8).

Stdlib-only single process, server-rendered pages:
  GET  /login                    login form (scrypt + lockout)
  POST /login                    create session (HttpOnly+SameSite=Lax cookie)
  POST /logout                   kill session (CSRF-protected)
  GET  /                         main console (session required)  GET  /agent/<id>               per-agent drill-down: metric series, alarms,
                                 ticket history, calibration state
  POST /resolve                  alarm triage (admin, CSRF)
  POST /confirm                  attribution verdict (admin, CSRF) → evidence
  POST /seal                    seal ledger (admin, CSRF)
  GET  /api/summary              JSON summary (session required)
  POST /resolve                  alarm triage (admin, CSRF)
  POST /confirm                  attribution verdict (admin, CSRF) → evidence
  GET  /chart/<name>.png         PNG export of any chart (sparkline, ewma, jsd,
                                 cost, errors, activity); admin-only; geometry
                                 identical to the on-page SVGs (§5 monitor UX)
  GET  /report/weekly            weekly report (admin; ?format=md|html|txt)
  GET  /report/weekly.eml        RFC 5322 email with the report + PNG charts
                                 attached, for SMTP pickup (§5 monitor UX)
  GET  /healthz                  liveness (no auth)
  GET  /?refresh=off|on          pause/resume auto-refresh

Security: scrypt hashes (ASVS 2.4), server-side sessions with only sha256
stored, per-session CSRF on every mutating POST, HttpOnly+SameSite cookies,
admin/viewer roles, 15-minute lockout after 5 failed logins, constant-time
compares. HTML is escaped via html.escape at every interpolation point.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sqlite3
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie

import time

from . import auth, attribution, sso
from .metrics.charts import Canvas
from .raster import encode_png
from .db import connect, init_db_with_migrations
from .evidence import append_evidence
from .metrics.apd import FleetApd
from .pipeline import Pipeline
from .privacy.store import SubjectKeyStore, master_key_from_env, seal_subject_erasure
from .report import WeeklyReport
from .sealing import load_or_create_seed, seal_ledger, verify_seals

SESSION_COOKIE = "swarmax_session"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(str(value))


STYLE = """<style>
 body { font-family: ui-sans-serif, system-ui, sans-serif; margin: 24px;
       background:#0e1116; color:#e6e6e6 }
 h1 { font-size: 20px } .cards { display:flex; flex-wrap:wrap; gap:16px; margin: 16px 0 }
 .card { background:#161b22; border:1px solid #30363d; border-radius:8px;
        padding:12px 18px; min-width:140px }
 .card b { display:block; font-size:26px } .muted { color:#8b949e }
 body { overflow-x: hidden }
 .tablewrap { overflow-x: auto }
 table { border-collapse: collapse; width: 100%; margin: 12px 0 }
 th, td { text-align:left; padding:6px 10px; border-bottom:1px solid #21262d;
         font-size:14px } th { color:#8b949e; font-weight:500 }
 tr:hover td { background:#161b22 }
 .Emergency { color:#f85149; font-weight:600 } .Critical { color:#ff7b54 }
 .High { color:#d29922 } .Medium { color:#58a6ff } .ok { color:#3fb950 }
 button { background:#238636; color:white; border:0; border-radius:6px;
         padding:4px 10px; cursor:pointer }
 button.danger { background:#b62324 } input { background:#0e1116; color:#e6e6e6;
 border:1px solid #30363d; border-radius:6px; padding:6px 10px }
 a { color:#58a6ff; text-decoration:none } a:hover { text-decoration:underline }
 svg text { fill:#8b949e; font-size:10px }
 .grid2 { display:grid; grid-template-columns: 1fr 1fr; gap: 24px }
 .grid2 > div { min-width: 0 }
 svg.chart { width:100%; max-width:720px; height:auto }
 @media (max-width: 900px) { .grid2 { grid-template-columns: 1fr } }
</style>"""


def esc(v) -> str:
    return html.escape(str(v))


def metric_series(conn: sqlite3.Connection, agent_id: str) -> list[sqlite3.Row]:
    """7-day daily series powering the agent page: cost, tokens, errors, tasks."""
    return conn.execute(
        "SELECT date(ts) d, ROUND(SUM(cost_usd),4) cost, SUM(input_tokens) tin,"
        " SUM(output_tokens) tout, SUM(status='error') errors, COUNT(*) tasks"
        " FROM agent_task_events WHERE agent_id=? AND ts >="
        " date('now','-6 day') GROUP BY d ORDER BY d", (agent_id,)).fetchall()


def tool_mix_series(conn: sqlite3.Connection, agent_id: str) -> dict[str, dict[str, int]]:
    """Per-day tool-call counts for the 7d window -> JSD chart source (§3.2-2)."""
    rows = conn.execute(
        "SELECT date(ts) d, tool_name, COUNT(*) c FROM guard_events"
        " WHERE agent_id=? AND event_type='tool_call' AND ts >= date('now','-6 day')"
        " GROUP BY d, tool_name", (agent_id,)).fetchall()
    mix: dict[str, dict[str, int]] = {}
    for r in rows:
        mix.setdefault(r["d"], {})[r["tool_name"]] = r["c"]
    return mix


def jsd_series(tool_mix: dict[str, dict[str, int]]) -> list[tuple[str, float | None]]:
    """Per-day JSD(P7d || Qday) over the tool mix — the drift chart (§3.2-2, R4).

    Reference window: the trailing 7 days excluding the day itself, mirroring
    `fact_tool_drift`. Empty either side -> None (warming_up, chart shows a gap).
    """
    from .metrics.statistics import jsd_divergence  # local: render-time only
    days = sorted(tool_mix)
    out: list[tuple[str, float | None]] = []
    for i, day in enumerate(days):
        ref: dict[str, int] = {}
        for j in range(max(0, i - 6), i):
            for k, v in tool_mix[days[j]].items():
                ref[k] = ref.get(k, 0) + v
        res = jsd_divergence(ref, tool_mix[day])
        out.append((day, res.value))
    return out


def ewma_z_series(costs: list[float]) -> list[float | None]:
    """EWMA control-card Z per day (§3.2-1) for *display*: the state is marked
    calibrated because R3's 30-observation warm-up guards the alarm path, not
    charts; a 3-observation warm-up fits the 7-day daily cadence."""
    from .metrics.statistics import EwmaState, ewma_update
    state = EwmaState(calibrated=True)
    return [ewma_update(state, c, min_obs=3).z for c in costs]


def agent_state(conn: sqlite3.Connection, agent_id: str) -> dict:
    """Everything the agent page renders, in one round of queries."""
    day_ago = (_utcnow() - timedelta(hours=24)).isoformat(sep=" ")
    month_ago = (_utcnow() - timedelta(days=30)).isoformat(sep=" ")
    def one(sql: str, args: tuple = ()) -> object:
        r = conn.execute(sql, args).fetchone()
        return r[0] if r else None
    calib = conn.execute(
        "SELECT calibration_until, closed FROM agent_calibration WHERE agent_id=?",
        (agent_id,)).fetchone()
    return {
        "events_24h": one("SELECT COUNT(*) FROM agent_task_events"
                          " WHERE agent_id=? AND ts >= ?", (agent_id, day_ago)) or 0,
        "cost_24h": one("SELECT ROUND(SUM(cost_usd),4) FROM agent_task_events"
                        " WHERE agent_id=? AND ts >= ?", (agent_id, day_ago)) or 0.0,
        # lifetime cost is bounded to the 30d warm tier (§10.1) so the agent
        # page stays inside the 200 ms gate at 1M+ events
        "cost_total": one("SELECT ROUND(SUM(cost_usd),4) FROM agent_task_events"
                          " WHERE agent_id=? AND ts >= ?",
                          (agent_id, month_ago)) or 0.0,
        "errors_24h": one("SELECT COUNT(*) FROM agent_task_events"
                          " WHERE agent_id=? AND status='error' AND ts >= ?",
                          (agent_id, day_ago)) or 0,
        "open_alarms": one("SELECT COUNT(*) FROM alarms WHERE agent_id=?"
                           " AND status='open'", (agent_id,)) or 0,
        "open_tickets": one("SELECT COUNT(*) FROM hitl_escalations WHERE agent_id=?"
                            " AND status='open'", (agent_id,)) or 0,
        "calibration": ("calibrated" if (calib and calib["closed"])
                        else f"calibrating until {str(calib['calibration_until'])[:16]}"
                        if calib else "unknown"),
        "tools_7d": conn.execute(
            "SELECT tool_name, COUNT(*) c FROM guard_events WHERE agent_id=?"
            " AND event_type='tool_call' GROUP BY tool_name ORDER BY c DESC LIMIT 8",
            (agent_id,)).fetchall(),
        "recent_alarms": conn.execute(
            "SELECT signal, severity, status, created_at, resolved_at FROM alarms"
            " WHERE agent_id=? ORDER BY created_at DESC LIMIT 10",
            (agent_id,)).fetchall(),
        "recent_tickets": conn.execute(
            "SELECT trigger_metric, trigger_value, reason, status, created_at"
            " FROM hitl_escalations WHERE agent_id=?"
            " ORDER BY created_at DESC LIMIT 10", (agent_id,)).fetchall(),
    }


def _sparkline(values: list[float], w: int = 260, h: int = 40,
               color: str = "#58a6ff") -> str:
    if not values or max(values) <= 0:
        return "<span class='muted'>no data</span>"
    vmax = max(values)
    pts = " ".join(
        f"{i * w // max(1, len(values) - 1)},{h - int(v / vmax * (h - 4)) - 2}"
        for i, v in enumerate(values))
    return (f"<svg class='chart' width='{w}' height='{h}' role='img'"
            f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2'/>"
            f"</svg>")


def _sparkline_canvas(values: list[float], w: int = 260, h: int = 40,
                      color: str = "#58a6ff") -> tuple[bytes, int, int] | None:
    """RGBA canvas of the sparkline; None when there is no data.
    Geometry is identical to _sparkline, so the PNG export and the on-page
    SVG show the same picture by construction."""
    if not values or max(values) <= 0:
        return None
    vmax = max(values)
    pts = [(i * w // max(1, len(values) - 1),
            h - int(v / vmax * (h - 4)) - 2)
           for i, v in enumerate(values)]
    rgb = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    canv = Canvas(w, h, bg=(13, 17, 23))
    canv.line_pts(pts, tuple(rgb))
    return canv.bytes(), w, h


def _activity_canvas(hourly: list[tuple[int, int, int]], *, w: int = 720,
                     h: int = 120) -> bytes:
    """RGBA canvas of the 24h activity chart (blue tasks, red errors) —
    same bar geometry as the on-page SVG."""
    canv = Canvas(w, h, bg=(13, 17, 23))
    hours = {hr: (t, e) for hr, t, e in hourly}
    maxv = max([t for _, t, _ in hourly] + [1])
    for hr in range(24):
        tasks, errors = hours.get(hr, (0, 0))
        hb = int(60 * tasks / maxv)
        eb = int(60 * errors / maxv)
        x = 30 + hr * 29
        if hb:
            canv.rect(x, 90 - hb, 12, hb, (88, 166, 255))
        if eb:
            canv.rect(x, 90 - eb, 12, eb, (248, 81, 73))
    return canv.bytes()


def _chart_name_ok(name: str) -> bool:
    return name in {"sparkline", "ewma", "jsd", "cost", "errors", "activity"}


def weekly_report_email(conn: sqlite3.Connection) -> bytes:
    """RFC 5322 / MIME-multipart weekly report email (§4.2 weekly path,
    §5 monitor UX).

    The WeeklyReport markdown digest ships as text/plain + a pre-wrap HTML
    alternative, and every console chart rides along as a PNG attachment
    (sparkline, EWMA Z, JSD, cost, errors, 24h activity) so an operator can
    read the digest without console access.  Stdlib-only; delivery is the
    operator's SMTP contract (SWARMAX_REPORT_FROM/TO) — this module only
    produces the message, honestly without magic.
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).replace(tzinfo=None)
    hc = FleetConsole(conn)

    charts: list[tuple[str, tuple[bytes, int, int] | None]] = []
    top = conn.execute(
        "SELECT agent_id FROM agent_task_events WHERE ts >= ? LIMIT 1",
        (since.strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()
    if top is not None:
        aid = top["agent_id"]
        series = metric_series(conn, aid)
        costs = [float(r["cost"]) for r in series]
        days = [str(r["d"]) for r in series]
        charts.append(("sparkline", _sparkline_canvas(costs)))
        charts.append(("ewma", _labeled_canvas(
            list(zip(days, ewma_z_series(costs))), color="#d29922",
            zero_based=False, threshold=2.5)))
        charts.append(("jsd", _labeled_canvas(
            jsd_series(tool_mix_series(conn, aid)), color="#58a6ff")))
        charts.append(("cost", _labeled_canvas(
            list(zip(days, costs)), color="#3fb950")))
        charts.append(("errors", _labeled_canvas(
            list(zip(days, [float(r["errors"]) for r in series])),
            color="#f85149")))
    hourly = [(r[0], r[1], r[2]) for r in hc.hourly()]
    charts.append(("activity", (_activity_canvas(hourly), 720, 120)))

    md = WeeklyReport(conn).render()
    msg = EmailMessage()
    msg["Subject"] = f"Swarmax weekly fleet report — {now:%Y-%m-%d}"
    msg["From"] = os.environ.get("SWARMAX_REPORT_FROM", "swarmax@localhost")
    msg["To"] = os.environ.get("SWARMAX_REPORT_TO", "dpo@localhost")
    msg.set_content(md)
    msg.add_alternative(
        "<html><body><pre style=\"font-family:monospace;white-space:pre-wrap\">"
        + html.escape(md) + "</pre></body></html>", subtype="html")
    for name, png in charts:
        if png:
            data, w, h = png
            msg.add_attachment(encode_png(data, w, h), maintype="image",
                               subtype="png", filename=f"{name}.png")
    return bytes(msg)


def _labeled_svg(points: list[tuple[str, float | None]], *, title: str,
                 desc: str, color: str, unit: str = "", w: int = 520,
                 h: int = 88, zero_based: bool = True) -> str:
    """Accessible time-series SVG (WCAG 1.1.1): role=img + <title>/<desc>,
    per-point <title> tooltips, None values rendered as gaps, and callers pair
    it with a data-table alternative inside <details>."""
    vals = [v for _, v in points if v is not None]
    if not vals:
        return "<span class='muted'>no data yet (warming up)</span>"
    lo = 0.0 if zero_based else min(vals)
    hi = max(vals + [lo])
    if hi <= lo:
        hi = lo + 1.0
    n = len(points)

    def X(i: int) -> float:
        return 6.0 if n == 1 else 6.0 + i * (w - 12.0) / (n - 1)

    def Y(v: float) -> float:
        return h - 6.0 - (v - lo) / (hi - lo) * (h - 12.0)

    path_parts: list[str] = []
    dots: list[str] = []
    prev = False
    for i, (label, v) in enumerate(points):
        if v is None:
            prev = False
            continue
        path_parts.append(f"{'M' if not prev else 'L'}{X(i):.1f},{Y(v):.1f}")
        prev = True
        dots.append(f"<circle cx='{X(i):.1f}' cy='{Y(v):.1f}' r='3' fill='{color}'>"
                    f"<title>{esc(label)}: {v:.3f}{unit}</title></circle>")
    zero_line = ""
    if not zero_based and lo < 0 < hi:
        zero_line = (f"<line x1='6' y1='{Y(0):.1f}' x2='{w - 6}' y2='{Y(0):.1f}'"
                     f" stroke='#30363d' stroke-dasharray='4 4'/>")
    return (f"<svg class='chart' width='{w}' height='{h}' role='img' aria-label='{esc(title)}'>"
            f"<title>{esc(title)}</title><desc>{esc(desc)}</desc>"
            f"{zero_line}"
            f"<path d='{' '.join(path_parts)}' fill='none' stroke='{color}'"
            f" stroke-width='2'/>" + "".join(dots) + "</svg>")


def _labeled_canvas(points: list[tuple[str, float | None]], *, color: str,
                    w: int = 520, h: int = 88, zero_based: bool = True,
                    threshold: float | None = None) -> tuple[bytes, int, int] | None:
    """RGBA canvas twin of _labeled_svg: identical X()/Y() mapping, gap
    handling for None points and (optionally) the dashed threshold line.
    None when every point is empty."""
    vals = [v for _, v in points if v is not None]
    if not vals:
        return None
    lo = 0.0 if zero_based else min(vals)
    hi = max(vals + [lo])
    if hi <= lo:
        hi = lo + 1.0
    n = len(points)

    def X(i: int) -> float:
        return 6.0 if n == 1 else 6.0 + i * (w - 12.0) / (n - 1)

    def Y(v: float) -> float:
        return h - 6.0 - (v - lo) / (hi - lo) * (h - 12.0)

    canv = Canvas(w, h, bg=(13, 17, 23))
    if threshold is not None and lo < threshold < hi:
        y = int(round(Y(threshold)))
        for x in range(6, w - 6, 8):
            canv.hline(x, min(x + 3, w - 6), y, (48, 54, 61))
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    prev = False
    for i, (_, v) in enumerate(points):
        if v is None:
            prev = False
            continue
        x, y = X(i), Y(v)
        canv.disc(int(round(x)), int(round(y)), 2, (r, g, b))
        if prev:
            canv.line(int(round(px)), int(round(py)), int(round(x)), int(round(y)),
                      (r, g, b))
        px, py, prev = x, y, True
    return canv.bytes(), w, h


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Swarmax Fleet Console</title>
{refresh_meta}{style}</head><body>
<h1>Swarmax Fleet Console <span class="muted">— {now} UTC{refresh_note}</span>
<form method="post" action="/logout" style="display:inline">
<input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="token" value="{token}"><button class="danger" type="submit">logout ({username})</button></form></h1>
<div class="cards">{cards}</div>
<h2>Open alarm queue (SLA countdown)</h2>
<div class="tablewrap"><form method="post" action="/resolve">{csrf_field}{token_field}{alarm_table}</form></div>
<h2>24h activity</h2>{svg}{png_link}
<div class="grid2">
<div><h2>Per-agent (24h)</h2><div class="tablewrap">{agent_table}</div></div>
<div><h2>Attribution (v1.1 — human-confirm gate §9.2)</h2>
<div class="tablewrap"><form method="post" action="/confirm">{csrf_field}{token_field}{attribution_block}</form></div></div>
</div>
<h2>Calibration (§3.3 — suppression visible)</h2><div class="tablewrap">{calibration_table}</div>
<div class="grid2">
<div><h2>Privacy (§10.3 — Art. 17 crypto-shred)</h2>
<table><tr><th>Subject</th><th>Key state</th><th>Erased at</th></tr>{privacy_rows}</table>
<form method="post" action="/forget">{csrf_field}{token_field}
<p><input name="subject_id" placeholder="subject-id" style="min-width:16ch">&nbsp;
<button class="danger" type="submit">erase (crypto-shred)</button></p></form></div>
<div><h2>Key custody (append-only)</h2><div class="tablewrap"><table><tr><th>Subject</th><th>v</th><th>Note</th><th>Created</th><th>Revoked</th></tr>{custody_rows}</table></div></div>
</div>
<p class="muted">{evidence}
<form method="post" action="/seal" style="display:inline">{csrf_field}{token_field}
<button type="submit">seal now (Ed25519 + Merkle)</button></form></p>
<p class="muted">first run? seed a demo fleet: <code>python scripts/seed_fleet.py</code>
&nbsp;·&nbsp; quarterly exit drill: <code>python scripts/exit_drill.py --db {db_label}</code></p>
</body></html>"""


LOGIN_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Swarmax — sign in</title>{style}</head>
<body><h1>Swarmax Fleet Console</h1>
<p class="muted">§8 operations model — sign in to triage the fleet.</p>
<form method="post" action="/login">
<p><input name="username" placeholder="username" autofocus></p>
<p><input name="password" type="password" placeholder="password"></p>
{error}<p><button type="submit">sign in</button></p>
</form>{sso_link}</body></html>"""


class FleetConsole:
    def __init__(self, conn: sqlite3.Connection, db_label: str = "data/swarmax.db",
                 auto_refresh_s: int = 5, *, sso_config: dict | None = None,
                 redirect_uri: str = "http://127.0.0.1:8080/sso/callback") -> None:
        self.conn = conn
        self.db_label = esc(db_label)
        self.auto_refresh_s = max(0, int(auto_refresh_s))
        self.sso_config = sso_config  # OIDC RP config; None = password login only
        self.redirect_uri = redirect_uri
        # pending OIDC flows: state -> {verifier, nonce, created}
        self._sso_state: dict[str, dict] = {}
        self.refresh_meta = (f'<meta http-equiv="refresh" content="{self.auto_refresh_s}">'
                            if self.auto_refresh_s else "")
        self.refresh_note = (f" (auto-refresh {self.auto_refresh_s}s)"
                            if self.auto_refresh_s else " (paused)")

    # ------------------------------------------------------------------ data
    def summary(self) -> dict:
        now = _utcnow().isoformat(sep=" ")
        day_ago = (_utcnow() - timedelta(hours=24)).isoformat(sep=" ")
        q = lambda sql, args=(): self.conn.execute(sql, args).fetchone()["c"]  # noqa: E731
        return {
            "open_alarms": q("SELECT COUNT(*) c FROM alarms WHERE status='open'"),
            "breached": q("SELECT COUNT(*) c FROM alarms"
                          " WHERE status='open' AND sla_deadline < ?", (now,)),
            "agents": q("SELECT COUNT(*) c FROM fleet_agents"),
            "events_24h": q("SELECT COUNT(*) c FROM agent_task_events WHERE ts >= ?",
                            (day_ago,)),
        }

    def open_alarms(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM alarms WHERE status='open' ORDER BY"
            " CASE severity WHEN 'Emergency' THEN 0 WHEN 'Critical' THEN 1"
            " WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 ELSE 5 END,"
            " sla_deadline").fetchall()

    def hourly(self) -> list[tuple[int, int, int]]:
        day_ago = (_utcnow() - timedelta(hours=24)).isoformat(sep=" ")
        rows = self.conn.execute(
            "SELECT CAST(strftime('%H', ts) AS INT) h, COUNT(*) tasks,"
            " SUM(status='error') errors FROM agent_task_events"
            " WHERE ts >= ? GROUP BY h", (day_ago,)).fetchall()
        return [(r["h"], r["tasks"], r["errors"] or 0) for r in rows]

    def per_agent(self) -> list[sqlite3.Row]:
        # F5 scale probe: the LEFT-JOIN form triggered per-agent random I/O at
        # 1M rows (>1 s). Two grouped scans stay inside the covering index
        # (SEARCH ... ANY(agent_id) AND ts>) and return in single-digit ms.
        day_ago = (_utcnow() - timedelta(hours=24)).isoformat(sep=" ")
        month_ago = (_utcnow() - timedelta(days=30)).isoformat(sep=" ")
        day = {r["agent_id"]: r for r in self.conn.execute(
            "SELECT agent_id, COUNT(*) events, ROUND(SUM(cost_usd),4) cost,"
            " SUM(status='error') errors FROM agent_task_events"
            " WHERE ts >= ? GROUP BY agent_id", (day_ago,)).fetchall()}
        life = {r["agent_id"]: r["cost_total"] for r in self.conn.execute(
            "SELECT agent_id, ROUND(SUM(cost_usd),4) cost_total"
            " FROM agent_task_events WHERE ts >= ? GROUP BY agent_id",
            (month_ago,)).fetchall()}
        agents = [r["agent_id"] for r in
                  self.conn.execute("SELECT agent_id FROM fleet_agents").fetchall()]
        rows = []
        for a in agents:
            d = day.get(a)
            rows.append({"agent_id": a,
                         "events": d["events"] if d else 0,
                         "cost": d["cost"] if d else 0.0,
                         "errors": d["errors"] if d else 0,
                         "cost_total": life.get(a, 0.0)})
        rows.sort(key=lambda r: r["cost_total"], reverse=True)
        return rows

    def attribution_rows(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT s.alarm_id, a.agent_id, a.signal, a.severity, a.status,"
            " s.suggested_agent_id, s.suggested_step, s.confidence, s.note,"
            " s.confirmed FROM attribution_suggestions s"
            " JOIN alarms a USING (alarm_id)"
            " WHERE s.confirmed IS NULL ORDER BY s.confidence DESC LIMIT 12"
        ).fetchall()

    def approval_stats(self) -> dict:
        return attribution.approval_rate(self.conn)

    # ------------------------------------------------------------------ png twin
    def chart_png(self, key: str) -> tuple[bytes, int, int] | None:
        """RGBA canvas of chart ``key`` — the PNG twin of the on-page SVG.
        None when the chart has no data (cold-start / empty window)."""
        if key == "activity":
            return _activity_canvas(self.hourly()), 720, 120
        top = self.conn.execute(
            "SELECT agent_id FROM agent_task_events WHERE ts >= ? LIMIT 1",
            ((datetime.now(timezone.utc) - timedelta(days=7))
             .replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),)).fetchone()
        if top is None:
            return None
        series = metric_series(self.conn, top["agent_id"])
        days = [str(r["d"]) for r in series]
        if key == "sparkline":
            return _sparkline_canvas([float(r["cost"]) for r in series])
        if key == "ewma":
            zp = list(zip(days, ewma_z_series([float(r["cost"]) for r in series])))
            return _labeled_canvas(zp, color="#d29922", zero_based=False,
                                   threshold=2.5)
        if key == "jsd":
            jp = jsd_series(tool_mix_series(self.conn, top["agent_id"]))
            return _labeled_canvas(jp, color="#58a6ff")
        if key == "cost":
            return _labeled_canvas(
                list(zip(days, [float(r["cost"]) for r in series])),
                color="#3fb950")
        if key == "errors":
            return _labeled_canvas(
                list(zip(days, [float(r["errors"]) for r in series])),
                color="#f85149")
        return None

    # ------------------------------------------------------------------ render
    def render(self, session: dict) -> str:
        s = self.summary()
        now = _utcnow()
        csrf, token = session["csrf_token"], session["token"]
        csrf_field = (f"<input type='hidden' name='csrf' value='{esc(csrf)}'>")
        token_field = (f"<input type='hidden' name='token' value='{esc(token)}'>")
        cards = "".join(
            f'<div class="card"><b>{esc(v)}</b>'
            f'<span class="muted">{esc(k)}</span></div>'
            for k, v in s.items())

        rows = []
        for a in self.open_alarms():
            deadline = _parse(a["sla_deadline"])
            left_s = int((deadline - now).total_seconds())
            if left_s < 0:
                countdown = f"BREACHED {-left_s // 3600}h {-left_s % 3600 // 60:02d}m ago"
                cls = "Emergency"
            elif left_s >= 48 * 3600:
                countdown = f"{left_s // 86400}d {(left_s % 86400) // 3600}h left"
                cls = a["severity"]
            else:
                countdown = f"{left_s // 3600}h {left_s % 3600 // 60:02d}m left"
                cls = a["severity"]
            rows.append(
                f"<tr><td class='{cls}'>{esc(a['severity'])}</td>"
                f"<td><a href='/agent/{esc(a['agent_id'])}'>{esc(a['agent_id'])}</a></td>"
                f"<td><code>{esc(a['signal'])}</code></td>"
                f"<td>{esc(a['reason'])}</td>"
                f"<td class='{cls}'>{countdown}</td>"
                f"<td><button name='alarm_id' value='{esc(a['alarm_id'])}'"
                f">resolve</button></td></tr>")
        alarm_table = ("<table><tr><th>Sev</th><th>Agent</th><th>Signal</th>"
                       "<th>Reason</th><th>SLA</th><th></th></tr>"
                       + ("".join(rows) or
                          "<tr><td colspan='6' class='ok'>queue empty</td></tr>")
                       + "</table>")

        hours = {h: (t, e) for h, t, e in self.hourly()}
        bars = []
        width, height, maxv = 720, 120, max([t for _, t, _ in self.hourly()] + [1])
        if not hours:
            bars.append("<text x='30' y='60'>no activity in the last 24h</text>")
        for hr in range(24):
            tasks, errors = hours.get(hr, (0, 0))
            h_bar = int(60 * tasks / maxv)
            e_bar = int(60 * errors / maxv)
            x = 30 + hr * 29
            bars.append(f"<rect x='{x}' y='{90 - h_bar}' width='12' height='{h_bar}'"
                        f" fill='#58a6ff'></rect>")
            if errors:
                bars.append(f"<rect x='{x}' y='{90 - e_bar}' width='12'"
                            f" height='{e_bar}' fill='#f85149'></rect>")
            bars.append(f"<text x='{x}' y='104'>{hr:02d}</text>")
        svg = (f"<svg class='chart' width='{width}' height='{height}' role='img'"
               f" aria-label='24h tasks (blue) and errors (red)'>"
               + "".join(bars) + "</svg>")
        png_link = "<p><a class='muted' href='/chart/activity.png'>⬇ PNG</a></p>"

        arows = "".join(
            f"<tr><td><a href='/agent/{esc(r['agent_id'])}'>{esc(r['agent_id'])}</a></td>"
            f"<td>{r['events']}</td>"
            f"<td>${r['cost']:.4f}</td><td>${r['cost_total']:.4f}</td>"
            f"<td>{r['errors'] or 0}</td></tr>"
            for r in self.per_agent())
        agent_table = ("<table><tr><th>Agent</th><th>Events 24h</th><th>Cost 24h</th>"
                       f"<th>Cost (lifetime)</th><th>Errors</th></tr>{arows}</table>")

        # v1.1 attribution queue — suggestions awaiting the operator verdict
        sug_rows = []
        for r in self.attribution_rows():
            verdict = ("<button name='alarm_id' value='" + esc(r["alarm_id"]) +
                       "' title='accept suggestion'>accept</button> "
                       "<button class='danger' name='alarm_id' value='" +
                       esc(r["alarm_id"]) + "' formaction='/confirm?reject=1'"
                       ">reject</button>")
            sug_rows.append(
                f"<tr><td class='{esc(r['severity'])}'>{esc(r['severity'])}</td>"
                f"<td><a href='/agent/{esc(r['suggested_agent_id'])}'>"
                f"{esc(r['suggested_agent_id'])}</a></td>"
                f"<td><code>{esc(r['signal'])}</code></td>"
                f"<td>{esc(r['suggested_step'])}</td>"
                f"<td>{r['confidence']:.2f}</td>"
                f"<td class='muted'>{esc(r['note'])}</td>"
                f"<td>{verdict}</td></tr>")
        stats = self.approval_stats()
        rate = (f"{stats['rate']:.0%}" if stats["rate"] is not None else "—")
        attribution_block = ("<table><tr><th>Sev</th><th>Suggested</th><th>Signal</th>"
                             "<th>Critical step</th><th>Conf</th><th>Why</th><th></th>"
                             "</tr>"
                             + ("".join(sug_rows) or
                                "<tr><td colspan='7' class='muted'>no pending suggestions</td></tr>")
                             + "</table>"
                             f"<p class='muted'>§9.2 acceptance: {rate} approval"
                             f" ({stats['accepted']}/{stats['decided']} decided)"
                             " — gate: ≥ 70% operator approval</p>")

        calib_rows = []
        try:
            calib = self.conn.execute(
                "SELECT agent_id, calibration_until, closed FROM agent_calibration"
                " ORDER BY closed, agent_id").fetchall()
        except sqlite3.OperationalError:  # pre-migration store
            calib = []
        for c in calib:
            if c["closed"]:
                state, cls = "calibrated", "ok"
                until = "—"
            else:
                left = _parse(c["calibration_until"]) - now
                state = f"calibrating ({max(0, left.days)}d left) — High/Critical suppressed"
                cls = "High"
                until = str(c["calibration_until"])[:16]
            calib_rows.append(
                f"<tr><td><a href='/agent/{esc(c['agent_id'])}'>{esc(c['agent_id'])}</a></td>"
                f"<td class='{cls}'>{esc(state)}</td>"
                f"<td class='muted'>{esc(until)}</td></tr>")
        calibration_table = ("<table><tr><th>Agent</th><th>State</th><th>Until</th></tr>"
                             + ("".join(calib_rows) or
                                "<tr><td colspan='3' class='muted'>no agents registered</td></tr>")
                             + "</table>")

        n_ledger = self.conn.execute(
            "SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        vseals = verify_seals(self.conn)
        seal_state = (f"{vseals['seals']} seals (verified={vseals['all_ok']})"
                      if vseals["seals"] else "no seal yet")
        evidence = (f"evidence: {n_ledger} ledger entries, {seal_state}, "
                    f"append-only enforced")

        return PAGE.format(
            now=now.strftime("%Y-%m-%d %H:%M:%S"), cards=cards,
            csrf=esc(csrf), token=esc(token), csrf_field=csrf_field,
            token_field=token_field, alarm_table=alarm_table, svg=svg,
            png_link=png_link,
            agent_table=agent_table, attribution_block=attribution_block,
            calibration_table=calibration_table, db_label=self.db_label,
            evidence=evidence, style=STYLE, username=esc(session["username"]),
            privacy_rows=self._privacy_rows(), custody_rows=self._custody_rows(),
            refresh_meta=self.refresh_meta, refresh_note=self.refresh_note)

    def _privacy_rows(self) -> str:
        rows = []
        try:
            subjects = self.conn.execute(
                "SELECT subject_id, display_name, erased_at FROM data_subjects"
                " ORDER BY registered_at DESC LIMIT 12").fetchall()
        except sqlite3.OperationalError:
            return "<tr><td colspan='3' class='muted'>no subjects registered</td></tr>"
        for r in subjects:
            key_state = "destroyed" if r["erased_at"] else "active (wrapped)"
            cls = "High" if r["erased_at"] else "ok"
            name = "[ERASED]" if r["erased_at"] else r["display_name"]
            rows.append(
                f"<tr><td><code>{esc(r['subject_id'])}</code> — {esc(name)}</td>"
                f"<td class='{cls}'>{key_state}</td>"
                f"<td class='muted'>{esc(str(r['erased_at'] or '—')[:16])}</td></tr>")
        return "".join(rows) or "<tr><td colspan='3' class='muted'>no subjects registered</td></tr>"

    def _custody_rows(self) -> str:
        try:
            rows = self.conn.execute(
                "SELECT subject_id, key_version, note, created_at, revoked_at"
                " FROM subject_keys ORDER BY custody_id DESC LIMIT 12").fetchall()
        except sqlite3.OperationalError:
            return "<tr><td colspan='5' class='muted'>no custody entries</td></tr>"
        out = []
        for r in rows:
            out.append(
                f"<tr><td><code>{esc(r['subject_id'])}</code></td>"
                f"<td>{r['key_version']}</td><td class='muted'>{esc(r['note'])}</td>"
                f"<td class='muted'>{esc(str(r['created_at'])[:16])}</td>"
                f"<td class='muted'>{esc(str(r['revoked_at'] or '—')[:16])}</td></tr>")
        return "".join(out) or "<tr><td colspan='5' class='muted'>no custody entries</td></tr>"

    def render_agent(self, agent_id: str, session: dict) -> str | None:
        """/agent/<id> drill-down page; None if the agent is unknown."""
        st = agent_state(self.conn, agent_id)
        if st["events_24h"] == 0 and st["open_alarms"] == 0 and \
                st["open_tickets"] == 0 and st["cost_total"] == 0:
            # unknown agent: no events, alarms, tickets, or cost anywhere
            exists = self.conn.execute(
                "SELECT 1 FROM fleet_agents WHERE agent_id=?", (agent_id,)).fetchone()
            if not exists:
                return None
        series = metric_series(self.conn, agent_id)
        csrf = esc(session["csrf_token"])
        token = esc(session["token"])
        csrf_field = f"<input type='hidden' name='csrf' value='{csrf}'>"
        token_field = f"<input type='hidden' name='token' value='{token}'>"

        # §3.2 metric charts: EWMA Z control-card + JSD drift over the tool mix
        jser = jsd_series(tool_mix_series(self.conn, agent_id))
        zser = ewma_z_series([float(r["cost"]) for r in series])
        day_labels = [str(r["d"]) for r in series]
        z_points = list(zip(day_labels, zser))
        j_points = [(d, v) for d, v in jser]
        cost_pts = list(zip(day_labels, [float(r["cost"]) for r in series]))
        err_pts = list(zip(day_labels, [float(r["errors"]) for r in series]))
        z_svg = _labeled_svg(
            z_points, title="EWMA Z by day (7d cost, §3.2-1)",
            desc="Daily cost expressed as EWMA Z-score; values above 2.5 cross the "
                 "alarm threshold. Missing points are cold-start days where the "
                 "control card is disarmed (R3).",
            color="#d29922", unit="σ", zero_based=False)
        z_png = "<p><a class='muted' href='/chart/ewma.png'>⬇ PNG</a></p>"
        j_svg = _labeled_svg(
            j_points, title="Tool-mix JSD by day (§3.2-2)",
            desc="Jensen-Shannon divergence between each day's tool mix and the "
                 "trailing 7-day reference; 0.20 watch, 0.40 alarm.",
            color="#58a6ff", zero_based=True)
        j_canvas = _labeled_canvas(j_points, color="#58a6ff")
        j_png = "<p><a class='muted' href='/chart/jsd.png'>⬇ PNG</a></p>"
        cost_chart = _labeled_svg(
            cost_pts, title="Cost per day (USD, 7d)",
            desc="Daily total task cost in US dollars over the trailing 7 days.",
            color="#3fb950", unit=" USD", zero_based=True)
        cost_png = "<p><a class='muted' href='/chart/cost.png'>⬇ PNG</a></p>"
        err_chart = _labeled_svg(
            err_pts, title="Errors per day (7d)",
            desc="Daily failed task count over the trailing 7 days.",
            color="#f85149", zero_based=True)
        err_png = "<p><a class='muted' href='/chart/errors.png'>⬇ PNG</a></p>"

        def _alt_table(pts: list[tuple[str, float | None]], col: str) -> str:
            rows = "".join(f"<tr><td>{esc(d)}</td><td>{'—' if v is None else f'{v:.4f}'}</td></tr>"
                           for d, v in pts)
            return ("<details><summary class='muted'>data table</summary>"
                    f"<table><tr><th>Day</th><th>{col}</th></tr>{rows}</table></details>")

        series_rows = "".join(
            f"<tr><td>{esc(r['d'])}</td><td>${r['cost']:.4f}</td>"
            f"<td>{r['tin'] or 0}</td><td>{r['tout'] or 0}</td>"
            f"<td class='{'Critical' if r['errors'] else ''}'>{r['errors']}</td>"
            f"<td>{r['tasks']}</td></tr>"
            for r in series) or "<tr><td colspan='6' class='muted'>no data</td></tr>"
        tool_rows = "".join(
            f"<tr><td>{esc(r['tool_name'])}</td><td>{r['c']}</td></tr>"
            for r in st["tools_7d"]) or ("<tr><td colspan='2' class='muted'>no tool calls</td></tr>")
        alarm_rows = "".join(
            f"<tr><td class='{esc({'Emergency': 'Emergency', 'Critical': 'Critical', 'High': 'High', 'Medium': 'Medium'}.get(r['severity'], ''))}'>{esc(r['signal'])}</td>"
            f"<td>{esc(r['status'])}</td><td class='muted'>{esc(str(r['created_at'])[:19])}</td>"
            f"<td class='muted'>{esc(str(r['resolved_at'] or '—')[:19])}</td></tr>"
            for r in st["recent_alarms"])
        ticket_rows = "".join(
            f"<tr><td>{esc(r['trigger_metric'])}</td><td>{esc(r['status'])}</td>"
            f"<td class='muted'>{esc(r['reason'])}</td>"
            f"<td class='muted'>{esc(str(r['created_at'])[:19])}</td></tr>"
            for r in st["recent_tickets"]) or ("<tr><td colspan='4' class='muted'>no tickets</td></tr>")

        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Swarmax — {esc(agent_id)}</title>{STYLE}</head><body>
<h1><a href="/">← fleet</a> · agent {esc(agent_id)}
<span class="muted">— {now_stamp()} UTC</span></h1>
<div class="cards">
<div class="card"><b>{st['events_24h']}</b><span class="muted">events 24h</span></div>
<div class="card"><b>${st['cost_24h']:.4f}</b><span class="muted">cost 24h</span></div>
<div class="card"><b>${st['cost_total']:.4f}</b><span class="muted">cost lifetime</span></div>
<div class="card"><b>{st['errors_24h']}</b><span class="muted">errors 24h</span></div>
<div class="card"><b>{st['open_alarms']}</b><span class="muted">open alarms</span></div>
<div class="card"><b>{st['open_tickets']}</b><span class="muted">open tickets</span></div>
<div class="card"><b class='{"ok" if st["calibration"] == "calibrated" else "High"}'>{esc(st['calibration'])}</b><span class="muted">calibration §3.3</span></div>
</div>
<div class="grid2">
<div><h2>7-day cost</h2>{cost_chart}{cost_png}{_alt_table(cost_pts, 'USD')}
<h2>7-day errors</h2>{err_chart}{err_png}{_alt_table(err_pts, 'errors')}
<h2>EWMA Z — cost control card (§3.2-1)</h2>{z_svg}{z_png}{_alt_table(z_points, 'Z')}
<h2>Tool-mix JSD — drift (§3.2-2)</h2>{j_svg}{j_png}{_alt_table(j_points, 'JSD')}
<h2>Daily series</h2>
<table><tr><th>Day</th><th>Cost</th><th>tok in</th><th>tok out</th><th>errors</th><th>tasks</th></tr>{series_rows}</table></div>
<div><h2>Tool mix (7d)</h2><table><tr><th>Tool</th><th>Calls</th></tr>{tool_rows}</table>
<h2>Recent alarms</h2><table><tr><th>Signal</th><th>Status</th><th>Opened</th><th>Resolved</th></tr>{alarm_rows}</table>
<h2>Tickets</h2><table><tr><th>Trigger</th><th>Status</th><th>Reason</th><th>Opened</th></tr>{ticket_rows}</table></div>
</div>
<p class="muted">row links: alarm queue triage stays on the fleet page;
metric formulas: SWARMAX.md §3.2</p>
</body></html>"""

    # ------------------------------------------------------------------ http
    def make_handler(self):  # noqa: ANN201
        console = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            # ---------- helpers
            def _send(self, code: int, body: bytes, ctype: str = "text/html",
                      extra: dict | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                # F5 hardening: OWASP Secure Headers baseline (§8 L2)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; style-src 'unsafe-inline';"
                                 " img-src 'self'; base-uri 'none'")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _redirect(self, loc: str) -> None:
                self.send_response(303)
                self.send_header("Location", loc)
                self.end_headers()

            def _token(self) -> str | None:
                c = SimpleCookie(self.headers.get("Cookie", ""))
                return c[SESSION_COOKIE].value if SESSION_COOKIE in c else None

            def _form(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                return {k: v[0] for k, v in
                        parse_qs(self.rfile.read(length).decode()).items()}

            def _session(self):
                return auth.authenticate(console.conn, self._token())

            # ---------- routes
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path
                if path == "/healthz":
                    self._send(200, b"ok", "text/plain")
                    return
                if path == "/login":
                    sess = self._session()
                    if sess:
                        self._redirect("/")
                        return
                    sso_link = ""
                    if console.sso_config:
                        url, state, verifier = sso.build_authorize_url(
                            console.sso_config, redirect_uri=console.redirect_uri)
                        console._sso_state[state] = {
                            "verifier": verifier, "created": time.time()}
                        sso_link = (f"<p><a href='{url}'>sign in with SSO</a></p>")
                    self._send(200, LOGIN_PAGE.format(style=STYLE, error="",
                                                      sso_link=sso_link).encode())
                    return
                if path == "/sso/callback":
                    self._sso_callback(parse_qs(parsed.query))
                    return
                sess = self._session()
                if sess is None:
                    self._redirect("/login")
                    return
                sess = {**sess, "token": self._token()}
                refresh = parse_qs(parsed.query).get("refresh", [None])[0]
                if refresh == "off":
                    self._send(200, FleetConsole(
                        console.conn, auto_refresh_s=0).render(sess).encode())
                elif refresh == "on":
                    self._send(200, FleetConsole(console.conn).render(sess).encode())
                elif path == "/" or path == "/index.html":
                    self._send(200, console.render(sess).encode())
                elif path.startswith("/agent/"):
                    agent_id = path[len("/agent/"):].strip("/")
                    page = console.render_agent(agent_id, sess)
                    if page is None:
                        self._send(404, b"unknown agent", "text/plain")
                    else:
                        self._send(200, page.encode())
                elif path.startswith("/chart/"):
                    self._chart_png(path, sess)
                elif path == "/report/weekly.eml":
                    self._report_email(sess)
                elif path == "/report/weekly":
                    self._report_page(sess, parse_qs(parsed.query))
                elif path == "/api/summary":
                    self._send(200, json.dumps(console.summary()).encode(),
                               "application/json")
                else:
                    self._send(404, b"not found")

            # ---------- chart export & report delivery (§5 monitor UX)
            def _chart_png(self, path: str, sess: dict) -> None:
                base = path[len("/chart/"):]
                if base.endswith(".png"):
                    base = base[:-4]
                if not _chart_name_ok(base):
                    self._send(404, b"unknown chart", "text/plain")
                    return
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                canv = console.chart_png(base)
                if canv is None:
                    self._send(200, b"no data yet (warming up)", "text/plain")
                    return
                data, w, h = canv
                self._send(200, encode_png(data, w, h), "image/png",
                           {"Content-Disposition":
                            f'attachment; filename="{base}.png"'})

            def _report_page(self, sess: dict, qs: dict) -> None:
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                fmt = (qs.get("format") or ["html"])[0]
                md = WeeklyReport(console.conn).render()
                if fmt in ("md", "txt"):
                    ctype = "text/markdown" if fmt == "md" else "text/plain"
                    self._send(200, md.encode(), ctype,
                               {"Content-Disposition":
                                'attachment; filename="weekly-report.md"'})
                    return
                page = ("<!doctype html><html><head><meta charset='utf-8'>"
                        "<title>Swarmax weekly report</title>" + STYLE +
                        "</head><body><h1>Weekly report "
                        "<a class='muted' href='/report/weekly?format=md'>⬇ .md</a>"
                        " · <a class='muted' href='/report/weekly.eml'>⬇ email"
                        " (.eml)</a></h1><pre>" + html.escape(md)
                        + "</pre></body></html>")
                self._send(200, page.encode())

            def _report_email(self, sess: dict) -> None:
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                self._send(200, weekly_report_email(console.conn),
                           "message/rfc822",
                           {"Content-Disposition":
                            'attachment; filename="weekly-report.eml"'})

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path == "/sso/callback":
                    self._sso_callback(self._form())
                    return
                if path == "/login":
                    self._handle_login()
                    return
                sess = self._session()
                if sess is None:
                    self._redirect("/login")
                    return
                form = self._form()
                if not auth.check_csrf(sess, form.get("csrf")):
                    self._send(403, b"csrf mismatch", "text/plain")
                    return
                if path == "/logout":
                    auth.logout(console.conn, self._token())
                    self._redirect("/login")
                elif path == "/resolve":
                    self._resolve(form, sess)
                elif path == "/confirm":
                    self._confirm(form, sess)
                elif path == "/seal":
                    self._seal(sess)
                elif path == "/forget":
                    self._forget(form, sess)
                else:
                    self._send(404, b"not found")

            # ---------- handlers
            def _sso_callback(self, params: dict) -> None:
                """OIDC redirect handler: validate state → exchange code →
                verify id_token → sso_login session. Any failure is fail-closed
                (no session, honest error)."""
                if not console.sso_config:
                    self._send(404, b"sso disabled", "text/plain")
                    return

                def _first(v):
                    """GET query params arrive as lists, POST form as scalars."""
                    return v[0] if isinstance(v, list) else v

                state = _first(params.get("state"))
                code = _first(params.get("code"))
                pending = console._sso_state.pop(state, None) if state else None
                if pending is None or time.time() - pending["created"] > 600:
                    self._send(400, b"sso: unknown or expired state", "text/plain")
                    return
                try:
                    tokens = sso.exchange_code(
                        console.sso_config, code=code or "",
                        redirect_uri=console.redirect_uri,
                        code_verifier=pending["verifier"])
                    claims = sso.verify_id_token(
                        tokens["id_token"],
                        expect_iss=console.sso_config.get(
                            "issuer", "").rstrip("/"),
                        expect_aud=console.sso_config["client_id"],
                        client_secret=console.sso_config.get("client_secret"),
                        jwk=console.sso_config.get("jwk"))
                except (sso.SsoError, KeyError, ValueError) as exc:
                    self._send(401, f"sso failed: {exc}".encode(), "text/plain")
                    return
                result = auth.sso_login(
                    console.conn, claims["iss"], claims["sub"],
                    claims.get("email"))
                if result is None:
                    self._send(403, b"sso identity not linked", "text/plain")
                    return
                cookie = (f"{SESSION_COOKIE}={result['token']}; HttpOnly;"
                          f" SameSite=Lax; Path=/; Max-Age=43200")
                self._redirect_with_cookie("/", cookie)

            def _handle_login(self) -> None:
                form = self._form()
                result = auth.login(console.conn, form.get("username", ""),
                                    form.get("password", ""))
                if result is None:
                    page = LOGIN_PAGE.format(
                        style=STYLE,
                        error="<p class='Emergency'>invalid credentials"
                              " (or account locked)</p>", sso_link="")
                    self._send(200, page.encode())  # 200: no user enumeration
                    return
                cookie = (f"{SESSION_COOKIE}={result['token']}; HttpOnly;"
                          f" SameSite=Lax; Path=/; Max-Age=43200")
                self._redirect_with_cookie("/", cookie)

            def _redirect_with_cookie(self, loc: str, cookie: str) -> None:
                self.send_response(303)
                self.send_header("Location", loc)
                self.send_header("Set-Cookie", cookie)
                self.end_headers()

            def _resolve(self, form: dict, sess: dict) -> None:
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                alarm_id = form.get("alarm_id", "")
                if alarm_id:
                    pipe = Pipeline(console.conn)
                    n = pipe.resolve_alarm(alarm_id, f"console:{sess['username']}")
                    if n == 0:
                        # fail-closed: an unknown/stale id must never silently
                        # 303 and fabricate an evidence entry (deep-scan D2);
                        # resolve_alarm itself writes the B4 anchor only on success
                        self._send(404, f"alarm not open: {alarm_id}".encode(),
                                   "text/plain")
                        return
                    console.conn.commit()
                self._redirect("/")

            def _confirm(self, form: dict, sess: dict) -> None:
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                alarm_id = form.get("alarm_id", "")
                reject = "reject=1" in (urlparse(self.path).query or "")
                if alarm_id:
                    attribution.confirm_attribution(
                        console.conn, alarm_id,
                        accepted=not reject, operator=sess["username"])
                self._redirect("/")

            def _seal(self, sess: dict) -> None:
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                try:
                    seal = seal_ledger(console.conn, load_or_create_seed())
                    append_evidence(console.conn, "seal_created", {
                        "seal_id": seal["seal_id"],
                        "covers": seal["covers_through_seq"]})
                    console.conn.commit()
                    self._send(200, f"sealed: {seal['seal_id']}".encode(),
                               "text/plain")
                except Exception as exc:  # never drop the connection on faults
                    self._send(500, f"seal failed: {exc}".encode(), "text/plain")

            def _forget(self, form: dict, sess: dict) -> None:
                """GDPR/AI-Act Art. 17 erasure: per-subject crypto-shred (B2)."""
                if sess["role"] != "admin":
                    self._send(403, b"admin role required", "text/plain")
                    return
                subject_id = form.get("subject_id", "").strip()
                if not subject_id:
                    self._send(400, b"subject_id required", "text/plain")
                    return
                try:
                    store = SubjectKeyStore(console.conn, master_key_from_env())
                    result = store.crypto_shred(subject_id,
                                                actor=f"console:{sess['username']}")
                except KeyError:
                    # fail-closed: unknown subject must not fabricate evidence
                    self._send(404, f"unknown subject: {subject_id}".encode(),
                               "text/plain")
                    return
                if result["erased"]:
                    seal_subject_erasure(console.conn, subject_id)
                    console.conn.commit()
                    self._send(200, f"erased: {subject_id}".encode(), "text/plain")
                else:
                    self._send(200, f"no-op: {result.get('reason', '?')}".encode(),
                               "text/plain")

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        return ThreadingHTTPServer((host, port), self.make_handler())


def now_stamp() -> str:
    return _utcnow().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    ap = argparse.ArgumentParser(description="Swarmax fleet console")
    ap.add_argument("--db", default="data/swarmax.db")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--admin-user", default=None,
                    help="bootstrap the first admin (defaults to env SWARMAX_ADMIN)")
    ap.add_argument("--admin-password", default=None,
                    help="bootstrap password (env SWARMAX_ADMIN_PASSWORD; "
                         "min 12 chars)")
    args = ap.parse_args()
    conn = connect(args.db)
    init_db_with_migrations(conn)
    user = args.admin_user or os.environ.get("SWARMAX_ADMIN")
    pwd = args.admin_password or os.environ.get("SWARMAX_ADMIN_PASSWORD")
    if user and pwd:
        auth.bootstrap_admin(conn, user, pwd)
    console = FleetConsole(conn, db_label=args.db)
    server = console.serve(args.host, args.port)
    print(f"Swarmax console on http://{args.host}:{args.port} (db={args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
