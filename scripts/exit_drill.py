#!/usr/bin/env python
"""Quarterly exit drill CLI (paper §3 çıkış tatbikatı).

  python scripts/exit_drill.py --db data/swarmax.db
  python scripts/exit_drill.py --seed-if-missing   # fresh clone: seed a demo fleet first

Exports every user table to a portable JSON bundle, rebuilds a fresh store from
it, and verifies the hash chain + Ed25519 seals + row counts. Exit code 0 = PASS.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.exit_drill import format_drill_report, run_exit_drill  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Swarmax quarterly exit drill")
    ap.add_argument("--db", default="data/swarmax.db")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--seed-if-missing", action="store_true",
                    help="seed a demo fleet when the store does not exist yet")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        if args.seed_if_missing:
            print(f"store not found — seeding a demo fleet at {db} first")
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from seed_fleet import main as seed_main
            sys.argv = ["seed_fleet.py", "--db", args.db, "--reset"]
            return seed_main()
        print(f"error: db not found: {args.db} "
              f"(use --seed-if-missing to create one)", file=sys.stderr)
        return 2
    conn = connect(str(db))
    init_db_with_migrations(conn)
    report = run_exit_drill(conn)
    print(format_drill_report(report) if not args.json
          else __import__("json").dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
