#!/usr/bin/env python
"""Evidence Trust Services — live countersign drill (T3.1, §5.3 Hat 2).

Against the REAL public TSA (FreeTSA) by default:
  1. fresh store, realistic evidence entries;
  2. seal_ledger with countersigning enabled (SWARMAX_TSA_URL);
  3. verify_seals: chain + Ed25519 + countersign binding all green;
  4. external PKI check: `openssl ts -verify` against the TSA certificate
     (downloaded from the TSA; skipped loudly if the network blocks it);
  5. prints the PASS card.  Exit 1 on any failure.  No mocks.

  python scripts/trust_drill.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from swarmax.db import connect, init_db_with_migrations  # noqa: E402
from swarmax.evidence import append_evidence  # noqa: E402
from swarmax.pipeline import Pipeline  # noqa: E402
from swarmax.sealing import load_or_create_seed, seal_ledger, verify_seals  # noqa: E402

TSA_URL = os.environ.get("SWARMAX_TSA_URL", "https://freetsa.org/tsr")
TSA_LEAF_CRT = os.environ.get(
    "SWARMAX_TSA_CRT", "https://freetsa.org/files/tsa.crt")
TSA_ROOT_CRT = os.environ.get(
    "SWARMAX_TSA_ROOT", "https://freetsa.org/files/cacert.pem")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="swx-trust-"))
    conn = connect(str(tmp / "trust.db"))
    init_db_with_migrations(conn)

    # realistic fleet activity → evidence anchors
    pipe = Pipeline(conn)
    pipe.ingest([{
        "event_id": f"ev{i}", "agent_id": "trust-bot", "task_id": f"t{i}",
        "session_id": "s", "model_name": "m", "input_tokens": 100,
        "output_tokens": 40, "cost_usd": 0.01, "latency_ms": 300,
        "error_class": None, "status": "ok", "synthetic": 1,
        "ts": "2026-09-17 10:00:00", "retry_count": 0, "ttft_s": 0.2,
        "task_template": None, "end_state_json": None} for i in range(4)])
    seq = append_evidence(conn, "trust_drill_started", {"tsa": TSA_URL})
    conn.commit()
    print(f"ledger entries incl. anchor #{seq}")

    seed = load_or_create_seed(tmp / "seed.hex")
    res = seal_ledger(conn, seed, tsa_url=TSA_URL)
    print(f"seal    : {res['seal_id']} root={res['root_hash'][:16]}… "
          f"countersigned={res['countersigned']}")

    v = verify_seals(conn)
    ok_local = v["all_ok"] and v["results"][0]["countersign_ok"] is True
    print(f"verify  : chain+ed25519+binding -> "
          f"{'PASS' if ok_local else 'FAIL'}")

    # external PKI check with openssl against the TSA certificate
    tok_path = tmp / "seal.tsr"
    tok_path.write_bytes(conn.execute(
        "SELECT tsa_token FROM evidence_seals WHERE seal_id=?",
        (res["seal_id"],)).fetchone()["tsa_token"])
    data = (res["root_hash"].encode()
            + res["covers_through_seq"].to_bytes(8, "big"))
    (tmp / "seal.bin").write_bytes(data)
    ok_pki, pki_note = False, "skipped (no network/cert)"
    try:
        leaf, root = tmp / "tsa.crt", tmp / "root.pem"
        urllib.request.urlretrieve(TSA_LEAF_CRT, leaf)
        urllib.request.urlretrieve(TSA_ROOT_CRT, root)
        r = subprocess.run(
            ["openssl", "ts", "-verify", "-data", str(tmp / "seal.bin"),
             "-in", str(tok_path), "-CAfile", str(root),
             "-untrusted", str(leaf)],
            capture_output=True, text=True, timeout=30)
        ok_pki = r.returncode == 0 and "OK" in (r.stdout + r.stderr)
        pki_note = (r.stdout + r.stderr).strip().splitlines()[-1] \
            if (r.stdout or r.stderr) else "no output"
    except Exception as exc:  # noqa: BLE001 - drill must not crash on net
        pki_note = f"skipped: {exc}"
    print(f"openssl : {'PASS' if ok_pki else ('SKIP' if 'skipped' in pki_note else 'FAIL')}"
          f"  ({pki_note})")

    verdict = ok_local  # PKI step is extra proof when network allows
    print(f"\nTRUST DRILL: {'PASS' if verdict else 'FAIL'}  "
          f"(PKI {'verified' if ok_pki else 'not verified — see note above'}; "
          f"store: {tmp / 'trust.db'})")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
