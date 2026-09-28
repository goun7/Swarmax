"""SQLite store: PRAGMA discipline, schema init, migration runner.

Paper refs: §12.1 (DDL), §14 R12–R14 (migration 002), §7.1 (schema-change test).
"""
from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime

# explicit adapter: no reliance on the deprecated default datetime adapter (py3.12+)
sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))

_PKG_ROOT = pathlib.Path(__file__).resolve().parent
SCHEMA_FILE = _PKG_ROOT / "schema" / "sqlite_v1.sql"
MIGRATIONS_DIR = _PKG_ROOT / "schema" / "migrations"


class Connection(sqlite3.Connection):
    """sqlite3.Connection with one extra attribute.

    A plain sqlite3.Connection refuses arbitrary attributes, so in-process
    state scoped to a store (console login lockout) cannot be attached to it.
    This subclass carries `_swarmax_sid`: a process-unique store id that dies
    with the object. Using id(conn) instead is unsafe — Python may hand a
    recycled address to a brand-new connection after the old one is
    garbage-collected, letting one store inherit another's lockout.
    """

    _swarmax_sid: str


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open a connection with the PRAGMA discipline the paper mandates (§12.1).

    check_same_thread=False: services (OTLP ingest, console) are thread-per-request;
    callers serialize writes with their own lock (see OtlpIngest/FleetConsole).
    """
    conn = sqlite3.connect(path, check_same_thread=False, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # §8 R2: single-node crash durability
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Apply the base §12.1 DDL (idempotent)."""
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return int(row["v"] or 0)


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations in filename order; returns count applied.

    Migration files are named ``NNN_description.sql``; NNN is the target version.
    """
    version = current_version(conn)
    applied = 0
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        file_version = int(path.name.split("_", 1)[0])
        if file_version <= version:
            continue
        with conn:
            conn.executescript(path.read_text(encoding="utf-8"))
        applied += 1
        version = current_version(conn)
    return applied


def init_db_with_migrations(conn: sqlite3.Connection) -> None:
    """Convenience: base DDL + pending migrations (the F0 production path)."""
    init_db(conn)
    migrate(conn)


def init_main(argv: list[str] | None = None) -> int:
    """`swarmax-init` — create a Swarmax store at PATH (default data/swarmax.db)."""
    import argparse

    ap = argparse.ArgumentParser(
        prog="swarmax-init",
        description="Create or upgrade a Swarmax store (base schema + migrations).")
    ap.add_argument("path", nargs="?", default="data/swarmax.db",
                    help="store path (default: data/swarmax.db)")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.path)
    if root.parent and str(root.parent) not in (".", ""):
        root.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(str(root))
    try:
        init_db_with_migrations(conn)
        version = current_version(conn)
    finally:
        conn.close()
    print(f"swarmax store ready: {root} (schema v{version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(init_main())
