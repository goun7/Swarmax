"""Schema tests: §12.1 DDL, append-only enforcement, migration 002, WAL."""
import sqlite3

from swarmax.db import connect, current_version, init_db, init_db_with_migrations, migrate


def make_db(path: str = ":memory:") -> sqlite3.Connection:
    conn = connect(path)
    init_db_with_migrations(conn)
    return conn


def test_wal_enabled_on_file_db(tmp_path):
    conn = connect(str(tmp_path / "swx.db"))
    init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_schema_version_after_migration():
    conn = make_db()
    assert current_version(conn) == 10  # ... + 008 privacy/B4 + 009 F5 scale indexes + 010 T3.1 TSA countersign


def test_migration_adds_guard_events_and_columns():
    conn = make_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(agent_task_events)")}
    assert {"task_template", "end_state_json", "retry_count", "ttft_s"} <= cols
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(hitl_escalations)")}
    assert "created_at" in cols
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "guard_events" in tables
    assert "alarms" in tables and "evidence_seals" in tables


def test_evidence_ledger_is_append_only():
    conn = make_db()
    conn.execute(
        "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash, ed25519_sig)"
        " VALUES ('test', 'aa', 'GENESIS', x'00')")
    conn.commit()
    with conn:
        try:
            conn.execute("UPDATE evidence_ledger SET event_type='tampered'")
            assert False, "UPDATE on evidence_ledger must abort"
        except sqlite3.IntegrityError as e:
            assert "append-only" in str(e)
    try:
        conn.execute("DELETE FROM evidence_ledger")
        assert False, "DELETE on evidence_ledger must abort"
    except sqlite3.IntegrityError:
        pass


def test_migrations_are_idempotent():
    conn = make_db()
    assert migrate(conn) == 0  # already applied
    assert current_version(conn) == 10  # ... + 008 privacy/B4 + 009 F5 scale indexes + 010 T3.1 TSA countersign
