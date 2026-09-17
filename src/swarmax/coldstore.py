"""B1 cold tier (§10.3, AI_ACT_COMPLIANCE.md) — signed archive of the evidence
ledger to any S3-compatible object store (AWS S3, R2, MinIO), zero-dependency.

Closes compliance gap B1: "the 2-year cold tier is design, not code". What this
module delivers:

  - ``S3CompatStore``   minimal AWS SigV4 signer + PUT/GET/HEAD client
                        (path-style), no vendor SDK — the project stays
                        stdlib-only (§7 F0).
  - ``archive_ledger``  batches the append-only ledger into deterministic gzip
                        chunks (rows + re-computed chain digests) and writes a
                        ``manifest.json`` pointing at every chunk. Idempotent:
                        chunks already present (HEAD probe) are skipped.
  - ``verify_archive``  offline verifier: downloads manifest + chunks and
                        recomputes the whole chain. Needs **no database and no
                        private key** — the hash chain is self-authenticating.

Design bounds (honest): the archive stores *ledger rows* (payload hashes,
signatures), not raw payload bodies — payloads live in the operational store
per §10. Row order is append-only (PK ``seq``), so chunking is deterministic.
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .evidence import GENESIS  # chain anchor

CHUNK_ROWS = 10_000

__all__ = ["S3CompatStore", "archive_ledger", "verify_archive",
           "verify_manifest_bytes"]


# ------------------------------------------------------------------ SigV4
def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


class S3CompatStore:
    """Minimal S3-compatible client with AWS SigV4 (path-style, stdlib only).

    Works with AWS S3, Cloudflare R2 and MinIO. Credentials come from
    constructor args (wire them from environment variables in the operator
    wrapper, never hard-code them).
    """

    def __init__(self, endpoint: str, bucket: str, access_key: str,
                 secret_key: str, *, region: str = "us-east-1",
                 prefix: str = "evidence") -> None:
        u = urllib.parse.urlparse(endpoint)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"bad endpoint: {endpoint!r}")
        self.scheme, self.host = u.scheme, u.hostname
        self.port = u.port or (443 if u.scheme == "https" else 80)
        # the Host header on the wire must be byte-identical to the one signed:
        # urllib appends the port only when it is non-default
        default_port = (80, 443)
        self.host_header = (self.host if self.port in default_port
                            else f"{self.host}:{self.port}")
        self.bucket, self.region = bucket, region
        self.access_key, self.secret_key = access_key, secret_key
        self.prefix = prefix.strip("/")

    # -- SigV4 internals ----------------------------------------------------
    def _sigv4(self, method: str, key: str, payload_hash: str,
               amz_date: str) -> dict[str, str]:
        datestamp = amz_date[:8]
        canonical = (f"{method}\n/{self.bucket}/{key}\n\n"
                     f"host:{self.host_header}\n"
                     f"x-amz-content-sha256:{payload_hash}\n"
                     f"x-amz-date:{amz_date}\n\nhost;x-amz-content-sha256;x-amz-date\n"
                     f"{payload_hash}")
        scope = f"{datestamp}/{self.region}/s3/aws4_request"
        string_to_sign = (f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
                          f"{hashlib.sha256(canonical.encode()).hexdigest()}")
        k = _sign(_sign(_sign(_sign(f"AWS4{self.secret_key}".encode(), datestamp),
                              self.region), "s3"), "aws4_request")
        sig = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return {
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": (f"AWS4-HMAC-SHA256 Credential="
                              f"{self.access_key}/{scope}, SignedHeaders="
                              f"host;x-amz-content-sha256;x-amz-date, Signature={sig}"),
        }

    def _request(self, method: str, key: str, body: bytes | None) -> tuple[int, bytes]:
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = hashlib.sha256(body or b"").hexdigest()
        headers = self._sigv4(method, key, payload_hash, amz_date)
        if body is not None:
            headers["Content-Length"] = str(len(body))
        url = f"{self.scheme}://{self.host}:{self.port}/{self.bucket}/{key}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def _key(self, name: str) -> str:
        return f"{self.prefix}/{name}"

    # -- public ---------------------------------------------------------
    def put(self, name: str, data: bytes) -> str:
        status, _ = self._request("PUT", self._key(name), data)
        if status not in (200, 201):
            raise RuntimeError(f"S3 PUT failed: HTTP {status}")
        return f"{self.bucket}/{self._key(name)}"

    def head(self, name: str) -> bool:
        status, _ = self._request("HEAD", self._key(name), None)
        return status == 200

    def get(self, name: str) -> bytes:
        status, data = self._request("GET", self._key(name), None)
        if status != 200:
            raise RuntimeError(f"S3 GET failed: HTTP {status}")
        return data


# ------------------------------------------------------------------ archive
def archive_ledger(conn: sqlite3.Connection, store: S3CompatStore,
                   *, upto_seq: int | None = None) -> dict:
    """Archive the ledger in deterministic gzip chunks + manifest.

    Idempotent: a chunk already present in the store (HEAD probe) is skipped,
    so the archive can run on a schedule. The manifest is rewritten each run
    (objects are immutable chunks; the manifest is the single pointer).
    """
    rows = conn.execute(
        "SELECT seq, event_type, payload_hash, prev_hash, ed25519_sig, created_at"
        f" FROM evidence_ledger{'' if upto_seq is None else ' WHERE seq <= ?'}"
        " ORDER BY seq",
        () if upto_seq is None else (upto_seq,)).fetchall()
    if not rows:
        raise ValueError("nothing to archive: ledger is empty")

    stored, skipped = 0, 0
    chunk_meta = []
    for i in range(0, len(rows), CHUNK_ROWS):
        part = rows[i:i + CHUNK_ROWS]
        first_seq, last_seq = int(part[0]["seq"]), int(part[-1]["seq"])
        name = f"chunk_{first_seq:012d}_{last_seq:012d}.json.gz"
        payload = json.dumps([{**r, "ed25519_sig": bytes(r["ed25519_sig"]).hex()}
                              for r in part]).encode()
        blob = gzip.compress(payload, mtime=0)
        if store.head(name):
            skipped += 1
        else:
            store.put(name, blob)
            stored += 1
        chunk_meta.append({
            "key": name, "first_seq": first_seq, "last_seq": last_seq,
            "rows": len(part), "sha256": hashlib.sha256(blob).hexdigest(),
            "chain_digest": hashlib.sha256(
                "".join(r["payload_hash"] for r in part).encode()).hexdigest(),
        })

    manifest = {
        "version": 1,
        "first_seq": int(rows[0]["seq"]),
        "last_seq": int(rows[-1]["seq"]),
        "rows": len(rows),
        "chunks": chunk_meta,
        "genesis_prev": GENESIS,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    store.put("manifest.json", json.dumps(manifest, sort_keys=True).encode())
    return {"chunks_stored": stored, "chunks_skipped": skipped,
            "rows": len(rows), "last_seq": manifest["last_seq"]}


def verify_manifest_bytes(manifest_bytes: bytes, fetch_chunk) -> dict:
    """Chain-verify an archive given a ``fetch_chunk(name) -> bytes`` callable.
    Recomputes: chunk sha256, chunk boundaries, per-chunk chain digest and the
    full prev_hash chain from GENESIS."""
    manifest = json.loads(manifest_bytes)
    prev = manifest["genesis_prev"]
    rows_seen = 0
    for c in manifest["chunks"]:
        blob = fetch_chunk(c["key"])
        if hashlib.sha256(blob).hexdigest() != c["sha256"]:
            return {"ok": False, "reason": f"chunk hash mismatch: {c['key']}"}
        rows = json.loads(gzip.decompress(blob))
        if int(rows[0]["seq"]) != c["first_seq"] or \
                int(rows[-1]["seq"]) != c["last_seq"]:
            return {"ok": False, "reason": f"chunk boundary mismatch: {c['key']}"}
        digest = hashlib.sha256(
            "".join(r["payload_hash"] for r in rows).encode()).hexdigest()
        if digest != c["chain_digest"]:
            return {"ok": False, "reason": f"chain digest mismatch: {c['key']}"}
        for r in rows:
            if r["prev_hash"] != prev:
                return {"ok": False, "reason": f"chain break at seq {r['seq']}"}
            prev = r["payload_hash"]
        rows_seen += len(rows)
    ok = rows_seen == manifest["rows"]
    return {"ok": ok, "rows": rows_seen, "last_seq": manifest["last_seq"],
            "reason": None if ok else "row count mismatch"}


def verify_archive(store: S3CompatStore) -> dict:
    """Download manifest + chunks and recompute the chain — offline: no DB, no
    private key. This is the property auditors care about: the archive is
    self-authenticating evidence."""
    manifest = store.get("manifest.json")
    return verify_manifest_bytes(manifest, store.get)
