#!/usr/bin/env python
"""Combined compliance drill (AI_ACT_COMPLIANCE.md §5 — the auditor walkthrough,
executable): erasure → evidence → cold archive → offline verify, in one pass.

  python scripts/compliance_drill.py                       # fresh in-memory run
  python scripts/compliance_drill.py --db data/swarmax.db  # against a store
  make compliance-drill
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.pipeline import Pipeline  # noqa: E402
from swarmax.privacy.store import (  # noqa: E402
    SubjectKeyStore, master_key_from_env, seal_subject_erasure,
)
from swarmax.dpo import DpoReport  # noqa: E402
from swarmax.coldstore import (  # noqa: E402
    S3CompatStore, archive_ledger, verify_archive,
)
import swarmax.auth as auth  # noqa: E402
import swarmax.console as console_mod  # noqa: E402


def _http_post(op, base, path, **data):
    req = urllib.request.Request(base + path, urllib.parse.urlencode(data).encode())
    try:
        return op.open(req, timeout=30)
    except urllib.error.HTTPError as e:
        return e


def run(conn) -> list[str]:
    checks: list[str] = []
    master = master_key_from_env()

    # 1. register a subject with lawful basis, bind a real event
    store = SubjectKeyStore(conn, master)
    # the drill registers then erases its own synthetic subject; /forget
    # crypto-shreds in place and keeps the row, so purge leftovers from an
    # earlier run first — otherwise the drill is not re-runnable. The real
    # erasure path never does this; the evidence ledger keeps its history.
    for _table in ("subject_keys", "data_subjects"):
        conn.execute(f"DELETE FROM {_table} WHERE subject_id='drill-subject'")
    conn.commit()
    store.register("drill-subject", "Compliance Drill",
                   {"email": "drill@example.com"}, actor="drill",
                   lawful_basis="consent")
    ev = conn.execute(
        "SELECT event_id FROM agent_task_events ORDER BY ts LIMIT 1").fetchone()
    assert ev, "store has no task events; seed first"
    from swarmax.privacy.store import bind_subject_event
    bind_subject_event(conn, "drill-subject", ev["event_id"])
    conn.commit()
    pii = store.decrypt_pii("drill-subject")
    checks.append(f"register+decrypt: {pii['email'] == 'drill@example.com'}")

    # 2. erase over the REAL console HTTP path (auth + CSRF + role gate)
    if not conn.execute(
            "SELECT 1 FROM console_users WHERE username='root'").fetchone():
        auth.bootstrap_admin(conn, "root", "swarmax-demo-admin")
    console = console_mod.FleetConsole(conn)
    srv = console.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    op = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.open(base + "/login", data=urllib.parse.urlencode(
        {"username": "root", "password": "swarmax-demo-admin"}).encode(), timeout=30)
    home = op.open(base + "/", timeout=30).read().decode()
    csrf = re.search(r"name='csrf' value='([^']+)'", home).group(1)
    token = re.search(r"name='token' value='([^']+)'", home).group(1)
    r = _http_post(op, base, "/forget", csrf=csrf, token=token,
                   subject_id="drill-subject")
    body = r.read().decode()
    checks.append(f"console /forget: {r.status} ({body[:30]})")
    kinds = conn.execute("SELECT group_concat(event_type) g"
                         " FROM evidence_ledger").fetchone()["g"]
    checks.append(f"erasure anchored: {'subject_erased' in kinds}")

    # 3. crypto state: undecryptable now, including for the master-key holder
    try:
        store.decrypt_pii("drill-subject")
        checks.append("crypto-shred: FAILED (still decryptable)")
    except ValueError as exc:
        checks.append(f"crypto-shred: {exc}")

    # 4. DPO report sanity
    dpo = DpoReport(conn)
    checks.append(f"dpo sla breaches: {len(dpo.erasure_sla_breaches())}")
    anchors = dpo.ledger_anchors()
    checks.append(f"ledger anchors: {anchors['subject_erased']} erased,"
                  f" {anchors['subject_event_bound']} bound")

    # 5. cold archive + offline verify (in-process S3-compatible endpoint;
    #    full SigV4 server-side verification lives in tests/test_coldstore.py)
    class _DrillS3(BaseHTTPRequestHandler):
        # class attribute shared by all handler instances (per-run object store)
        objects: dict[str, bytes] = {}

        @classmethod
        def reset(cls):
            cls.objects = {}

        def log_message(self, *a):
            pass

        def do_PUT(self):
            n = int(self.headers.get("Content-Length", 0))
            self.objects[self.path] = self.rfile.read(n)
            self.send_response(200); self.end_headers()

        def do_HEAD(self):
            self.send_response(200 if self.path in self.objects else 404)
            self.send_header("Content-Length", "0"); self.end_headers()

        def do_GET(self):
            obj = self.objects.get(self.path)
            if obj is None:
                self.send_response(404); self.end_headers(); return
            self.send_response(200)
            self.send_header("Content-Length", str(len(obj))); self.end_headers()
            self.wfile.write(obj)

    from http.server import ThreadingHTTPServer
    _DrillS3.reset()
    srv3 = ThreadingHTTPServer(("127.0.0.1", 0), _DrillS3)
    threading.Thread(target=srv3.serve_forever, daemon=True).start()
    cold = S3CompatStore(f"http://127.0.0.1:{srv3.server_address[1]}",
                         "drill-bucket", "drill-ak", "drill-secret")
    arch = archive_ledger(conn, cold)
    ver = verify_archive(cold)
    checks.append(f"cold archive: {arch['chunks_stored']} chunks,"
                  f" {arch['rows']} rows")
    checks.append(f"offline verify: ok={ver['ok']}")

    # 6. tamper rejection: attacker rewrites one archived chunk; the manifest
    #    sha256 + chain digest must expose the forgery (self-authenticating
    #    evidence — the auditable property of the cold tier)
    keys = [k for k in list(_DrillS3.objects) if "chunk_" in k]
    assert keys, "no chunk objects stored"
    _DrillS3.objects[keys[0]] = b"forged"
    ver_bad = verify_archive(cold)
    checks.append(f"tamper rejected: {ver_bad['ok'] is False}")
    return checks


def main() -> int:
    ap = argparse.ArgumentParser(description="Swarmax compliance drill")
    ap.add_argument("--db", default=None,
                    help="existing store; default: fresh in-memory")
    args = ap.parse_args()
    if args.db:
        conn = connect(args.db)
        init_db_with_migrations(conn)
    else:
        conn = connect(":memory:")
        init_db_with_migrations(conn)
        pipe = Pipeline(conn)
        rng = __import__("random").Random(7)
        from swarmax.fleet import emitter
        base = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2)
        for d in range(2):
            events, guards = emitter.emit_baseline_day("drill-agent",
                                                       base + timedelta(days=d), rng)
            pipe.ingest(events, guards)
        conn.commit()
    results = run(conn)
    print("COMPLIANCE DRILL")
    for line in results:
        print(f"  - {line}")
    ok = all(("False" not in line and "FAILED" not in line) for line in results)
    print(f"{'COMPLIANCE PASS' if ok else 'COMPLIANCE FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
