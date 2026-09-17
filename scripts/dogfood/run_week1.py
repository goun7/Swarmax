#!/usr/bin/env python
"""Dogfood week 1, day 1 runnable (DOGFOOD_PLAN.md §1).

Boots a real ingest service + console over a fresh store, feeds the pilot
fleet (dog-doc / dog-test / dog-refactor) through FleetSdk over real HTTP —
the production path — then prints the MT-6/MT-7 cards from committed state.

  python scripts/dogfood/run_week1.py          # demo run
  make dogfood-demo                            # same via make
"""
from __future__ import annotations

import random
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from swarmax.console import FleetConsole  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.dogfood import (FleetSdk, measure_mt6, measure_mt7,  # noqa: E402
                             mt6_text, mt7_text)
from swarmax.otlp import OtlpIngest  # noqa: E402
from swarmax.pipeline import Pipeline  # noqa: E402

SECRET = b"dogfood-week1-secret"
PILOT = ("dog-doc", "dog-test", "dog-refactor")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Dogfood week 1, day 1 runnable")
    ap.add_argument("--db", default=str(ROOT / "data" / "dogfood.db"))
    ap.add_argument("--reset", action="store_true",
                    help="start from a fresh store (honest day-1 semantics; "
                         "re-running on an existing store would double-count "
                         "stale alarms in the MT-6 card)")
    args = ap.parse_args()
    if args.reset:
        Path(args.db).unlink(missing_ok=True)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(str(db_path))
    init_db_with_migrations(conn)

    ingest = OtlpIngest(conn, {"dogfood": SECRET})
    srv = ingest.serve("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    endpoint = f"http://127.0.0.1:{srv.server_address[1]}"

    console = FleetConsole(conn, db_label=str(db_path)).serve("127.0.0.1", 0)
    threading.Thread(target=console.serve_forever, daemon=True).start()

    # console users for the pilot (§8): root admin + viewer — idempotent so the
    # day-1 script can be re-run against an existing store without failing
    from swarmax import auth
    if not conn.execute(
            "SELECT 1 FROM console_users WHERE username='root'").fetchone():
        auth.bootstrap_admin(conn, "root", "swarmax-demo-admin")
    if not conn.execute(
            "SELECT 1 FROM console_users WHERE username='viewer'").fetchone():
        auth.add_user(conn, "viewer", "swarmax-demo-viewer", "viewer",
                      actor="root")

    sdk = FleetSdk(endpoint, "dogfood", SECRET)
    rng = random.Random(2026)
    models = {"dog-doc": "gpt-4o-mini", "dog-test": "gpt-4o-mini",
              "dog-refactor": "claude-sonnet"}

    print(f"ingest  : {endpoint}")
    print(f"console : http://127.0.0.1:{console.server_address[1]}  "
          f"(login: root / swarmax-demo-admin)")

    n_spans = 0
    for i in range(24):  # a realistic morning: 8 tasks per pilot agent
        agent = PILOT[i % 3]
        error = "timeout" if rng.random() < 0.08 else None
        sdk.task(agent, f"w1d1-{i:03d}", model=models[agent],
                 cost_usd=round(rng.uniform(0.006, 0.020), 6),
                 tokens_in=rng.randrange(500, 1600),
                 tokens_out=rng.randrange(200, 900),
                 latency_ms=rng.randrange(700, 2200), error=error)
        if len(sdk._batch) >= 4:
            n_spans += sdk.flush()
    n_spans += sdk.flush()
    print(f"shipped : {n_spans} spans via OTLP/HTTP (HMAC anti-replay), "
          f"{sdk.rejected} rejected")

    # Day-1 measurable MT-6 scenario, shipped over the SAME production path:
    # a first-seen error signature ('loop') on dog-refactor.  The E7 sentinel
    # (error.new_class_seen) is designed to fire during calibration (§3.3),
    # so it is exactly the day-1 measurable latency property MT-6 needs.
    # The triggering task is intentionally SHORT (50 ms): the store keeps the
    # span-START timestamp, so a short task keeps 'event ts ≈ span close' and
    # the card measures pipeline latency, not task duration.
    sdk.task("dog-refactor", "w1d1-loop-001", model=models["dog-refactor"],
             cost_usd=0.011, tokens_in=40, tokens_out=0, latency_ms=50,
             error="loop")
    n_spans += sdk.flush()
    t0 = time.perf_counter()
    alarms = ingest.pipe.evaluate_agent("dog-refactor")
    mt6_ms = (time.perf_counter() - t0) * 1000.0
    live = [a for a in alarms if a.signal == "error.new_class_seen"]
    print(f"scenario: first-seen 'loop' signature -> "
          f"{len(live)} new_class alarm(s), evaluate path {mt6_ms:.0f} ms")

    # day-1 MT cards from committed store state
    m7 = measure_mt7(conn)
    print("\n## MT-7 (day 1)")
    print(mt7_text(m7))
    m6 = measure_mt6(conn)
    print("## MT-6 (day 1)")
    print(mt6_text(m6))

    print("\nMT-1/2/3 full measurement unlocks at day 11 (§3.3 calibration) — "
          "per DOGFOOD_PLAN.md this is honest scope, not a gap.")
    print(f"store   : {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
