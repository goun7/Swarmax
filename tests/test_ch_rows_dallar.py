"""test_ch_rows_dallar.py — _rows dal-kesen test suite.

ORTAM-ANATOMI (swarmax/ch.py L112):
  _rows(conn, since_ts, limit, *, inclusive=False) -> list[dict]
    SELECT event_id, agent_id, task_id, session_id, model_name, input_tokens,
           output_tokens, cost_usd, latency_ms, error_class, status,
           retry_count, ttft_s, ts FROM agent_task_events
    since_ts varsa: ts >= ? (inclusive) veya ts > ? (exclusive)
    ORDER BY ts LIMIT ?

ORTAM-OGRENDILER:
  (1) 14 kolon her satirda dict olarak doner (sqlite3.Row -> dict()).
  (2) since_ts=None -> filtre YOK; limit uygulanir (LIMIT 0 -> bos liste).
  (3) inclusive=False (default): esit-degerli ts DISLANIR; inclusive=True
      esit-degerli ts DAHIL edilir (ReplacingTreeTree idempotent dual-write).
  (4) ORDER BY ts:_insert sirasindan bagimsiz artan ts sirasi.
  (5) agent_task_events, fleet_agents'a FK — once fleet_agents insert sart.

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory sqlite. --noconftest ZORUNLU.
"""
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.ch import _rows  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402

COLUMNS = ["event_id", "agent_id", "task_id", "session_id", "model_name",
           "input_tokens", "output_tokens", "cost_usd", "latency_ms",
           "error_class", "status", "retry_count", "ttft_s", "ts"]


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    conn.execute("INSERT OR IGNORE INTO fleet_agents(agent_id, fleet_name, role)"
                 " VALUES('a1','fleet','planner')")
    conn.commit()
    return conn


def _insert(conn, event_id, ts, *, agent="a1", task="t1", session="s1",
            model="gpt-4o", inp=100, out=50, cost=0.01, latency=120,
            error=None, status="ok", retry=0, ttft=0.5):
    conn.execute(
        """INSERT INTO agent_task_events(event_id, agent_id, task_id, session_id,
           model_name, input_tokens, output_tokens, cost_usd, latency_ms,
           error_class, status, retry_count, ttft_s, ts)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (event_id, agent, task, session, model, inp, out, cost, latency,
         error, status, retry, ttft, ts))
    conn.commit()


@pytest.fixture()
def db_3(db):
    _insert(db, "e1", "2026-01-01 10:00:00")
    _insert(db, "e2", "2026-01-01 11:00:00")
    _insert(db, "e3", "2026-01-01 12:00:00")
    return db


def test_rows_empty_table_returns_empty_list(db):
    result = _rows(db, None, 100)
    assert result == []
    assert isinstance(result, list)


def test_rows_returns_list_of_dicts(db_3):
    result = _rows(db_3, None, 100)
    assert len(result) == 3
    assert all(isinstance(r, dict) for r in result)


def test_rows_dict_keys_are_exactly_14_columns(db_3):
    for r in _rows(db_3, None, 100):
        assert set(r.keys()) == set(COLUMNS)
        assert len(r) == 14


@pytest.mark.parametrize("limit,expected", [(0, 0), (1, 1), (2, 2), (3, 3),
                                            (5, 3), (100, 3), (1000000, 3)])
def test_rows_limit_respected(db_3, limit, expected):
    assert len(_rows(db_3, None, limit)) == expected


@pytest.mark.parametrize("since,expected", [
    ("2026-01-01 09:00:00", ["e1", "e2", "e3"]),
    ("2026-01-01 10:00:00", ["e2", "e3"]),   # exclusive default
    ("2026-01-01 11:00:00", ["e3"]),
    ("2026-01-01 12:00:00", []),
    ("2099-01-01 00:00:00", []),
])
def test_rows_since_exclusive(db_3, since, expected):
    got = [r["event_id"] for r in _rows(db_3, since, 100)]
    assert got == expected


@pytest.mark.parametrize("since,expected", [
    ("2026-01-01 09:00:00", ["e1", "e2", "e3"]),
    ("2026-01-01 10:00:00", ["e1", "e2", "e3"]),  # inclusive
    ("2026-01-01 11:00:00", ["e2", "e3"]),
    ("2026-01-01 12:00:00", ["e3"]),
    ("2026-01-02 00:00:00", []),
])
def test_rows_since_inclusive(db_3, since, expected):
    got = [r["event_id"] for r in _rows(db_3, since, 100, inclusive=True)]
    assert got == expected


def test_rows_inclusive_and_exclusive_differ_at_boundary(db_3):
    exc = [r["event_id"] for r in _rows(db_3, "2026-01-01 11:00:00", 100)]
    inc = [r["event_id"] for r in _rows(db_3, "2026-01-01 11:00:00", 100, inclusive=True)]
    assert exc == ["e3"]
    assert inc == ["e2", "e3"]
    assert exc != inc


def test_rows_ordered_by_ts_ascending(db):
    # ters sirada insert et, artan sirada gelmeli
    _insert(db, "c", "2026-03-01 00:00:00")
    _insert(db, "a", "2026-01-01 00:00:00")
    _insert(db, "b", "2026-02-01 00:00:00")
    assert [r["event_id"] for r in _rows(db, None, 100)] == ["a", "b", "c"]


def test_rows_since_plus_limit_interaction(db_3):
    # once filtre, sonra limit
    assert [r["event_id"] for r in _rows(db_3, "2026-01-01 10:00:00", 1)] == ["e2"]
    assert [r["event_id"] for r in _rows(db_3, "2026-01-01 10:00:00", 1, inclusive=True)] == ["e1"]


def test_rows_field_values_roundtrip(db):
    db.execute("INSERT OR IGNORE INTO fleet_agents(agent_id, fleet_name, role)"
               " VALUES('agent-7','fleet','planner')")
    db.commit()
    _insert(db, "vx", "2026-05-01 08:30:00", agent="agent-7", task="task-9",
            session="sess-3", model="claude-3.5", inp=1234, out=567,
            cost=12.345678, latency=98765, error="RateLimitError",
            status="error", retry=3, ttft=1.25)
    r = _rows(db, None, 100)[0]
    assert r["event_id"] == "vx"
    assert r["agent_id"] == "agent-7"
    assert r["task_id"] == "task-9"
    assert r["session_id"] == "sess-3"
    assert r["model_name"] == "claude-3.5"
    assert r["input_tokens"] == 1234
    assert r["output_tokens"] == 567
    assert r["cost_usd"] == 12.345678
    assert r["latency_ms"] == 98765
    assert r["error_class"] == "RateLimitError"
    assert r["status"] == "error"
    assert r["retry_count"] == 3
    assert r["ttft_s"] == 1.25
    assert r["ts"] == "2026-05-01 08:30:00"


@pytest.mark.parametrize("field", COLUMNS)
def test_rows_every_column_present(db_3, field):
    assert all(field in r for r in _rows(db_3, None, 100))


def test_rows_null_error_class(db):
    _insert(db, "n1", "2026-01-01 00:00:00", error=None)
    assert _rows(db, None, 100)[0]["error_class"] is None


def test_rows_empty_string_error_class(db):
    _insert(db, "n2", "2026-01-01 00:00:00", error="")
    assert _rows(db, None, 100)[0]["error_class"] == ""


def test_rows_token_columns_are_int(db_3):
    for r in _rows(db_3, None, 100):
        assert isinstance(r["input_tokens"], int)
        assert isinstance(r["output_tokens"], int)
        assert isinstance(r["latency_ms"], int)


def test_rows_ts_is_str(db_3):
    for r in _rows(db_3, None, 100):
        assert isinstance(r["ts"], str)


def test_rows_no_extra_columns(db_3):
    r = _rows(db_3, None, 100)[0]
    assert set(r.keys()) == set(COLUMNS)


def test_rows_isolates_connections(db):
    c2 = connect(":memory:")
    init_db_with_migrations(c2)
    try:
        _insert(db, "e1", "2026-01-01 00:00:00")
        assert len(_rows(db, None, 100)) == 1
        assert _rows(c2, None, 100) == []
    finally:
        c2.close()


def test_rows_since_boundary_exact_equality(db):
    _insert(db, "e1", "2026-01-01 00:00:00")
    _insert(db, "e2", "2026-01-01 00:00:00")  # ayni ts
    assert len(_rows(db, "2026-01-01 00:00:00", 100)) == 0
    assert len(_rows(db, "2026-01-01 00:00:00", 100, inclusive=True)) == 2


def test_rows_limit_between_filters(db_3):
    assert len(_rows(db_3, "2026-01-01 09:00:00", 2)) == 2
    assert [r["event_id"] for r in _rows(db_3, "2026-01-01 09:00:00", 2)] == ["e1", "e2"]


def test_rows_large_volume(db):
    for i in range(200):
        _insert(db, f"e{i}", f"2026-01-01 00:{i // 60:02d}:{i % 60:02d}")
    assert len(_rows(db, None, 10000)) == 200
    assert len(_rows(db, None, 50)) == 50
    ids = [r["event_id"] for r in _rows(db, None, 50)]
    assert ids == sorted(ids, key=lambda x: int(x[1:]))
