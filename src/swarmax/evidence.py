"""Append-only evidence ledger — paper §12.1.

SHA-256 payload hash chained to the previous entry (prev_hash), stored in the
append-only table (UPDATE/DELETE forbidden by triggers). Ed25519 signatures land in
F2 (§7.1); F0 rows carry an explicit unsigned marker, never a fake signature.

SW-EVID-1 (fail-closed):
  (a) canonical-JSON tip-zorlamasi kabul edilmez — str-olmayan anahtar, tuple ve
      NaN/Inf gibi tip-ayrimini/kimligi kaybettiren payload'lar digest'e ALINMAZ;
  (b) verify_chain imza kolonunu da denetler — F0'un acik isareti ya da 64-bayt
      Ed25519 imzasi disindaki deger 'sessiz imzasizlik'tir, zincir kirmizi olur.
Denetimlerin hicbiri COKMEZ: belirsiz payload TypeError/ValueError ile
reddedilir (ledger'a HIC satir yazilmaz), bozuk satir ise verify_chain'i
(False, k) ile kirmizi yapar — istisna firlatmaz.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3

UNSIGNED_F0 = b"F0-UNSIGNED-F2-PENDING"
GENESIS = "GENESIS"

# SW-EVID-2: payload'lar tabloda saklanmadigi icin icerik-dogrulama imkansizdir,
# ama her payload_hash gercek bir SHA-256 ozeti (64-kucuk-hex) OLMALIDIR —
# manual/buggy bir INSERT 'sabit-olmayan' gibi bir deger koyup zinciri
# gecersizlestirebilir; eski verify_chain yalnizca prev baglarini sayiyordu.
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

# SW-EVID-1b: F2 imzalari her zaman 64 bayttir; F0'un ACIK isareti tek mesru
# 'imzasiz' degerdir. Bos/kisa/rastgele/metin-lekesi blob = sessiz-imzasizlik
# -> kirmizi. Kolon BLOB NOT NULL; yine de TEXT yazilmis bir satir verify_chain'i
# patlatmamali, KIRMIZI olmalı (fail-closed cokme yerine reddeder).
_SIG_LEN = 64


def _validate_canonical(obj: object, path: str = "$",
                        _stack: frozenset[int] = frozenset()) -> None:
    """SW-EVID-1a: kanonik-JSON'un tip-ayrimini kaybettirdigi payload'lari reddet.

    json.dumps canonical uyumu: str-olmayan anahtarlar string'e zorlanir
    ({1: 'a'} -> '{"1": "a"}') ve tuple JSON dizisi olarak serilesir
    ((1, 2) -> [1, 2]) — iki FARKLI Python nesnesi AYNI digest'e gotururdu.
    Kanoniklestirme bu sinirlari KORUYAMADIGI icin tip-uyusmazligi fail-closed
    reddedilir. NaN/Inf gecerli JSON sayi DEGILDIR (RFC 8785) ve farkli NaN
    nesneleri ayni 'NaN' dizisine serilirdi — o da reddedilir.
    """
    if isinstance(obj, dict):
        if id(obj) in _stack:
            raise ValueError(f"canonical payload: circular reference at {path}")
        nxt = _stack | {id(obj)}
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"canonical payload: non-str key {k!r} at {path} "
                    "(SW-EVID-1: JSON would coerce it to a string)")
            _validate_canonical(v, f"{path}.{k}", nxt)
    elif isinstance(obj, tuple):
        raise TypeError(
            f"canonical payload: tuple at {path} "
            "(SW-EVID-1: JSON would serialize it as an array)")
    elif isinstance(obj, list):
        if id(obj) in _stack:
            raise ValueError(f"canonical payload: circular reference at {path}")
        nxt = _stack | {id(obj)}
        for i, v in enumerate(obj):
            _validate_canonical(v, f"{path}[{i}]", nxt)
    elif isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError(
            f"canonical payload: non-finite float {obj!r} at {path} "
            "(SW-EVID-1: not valid canonical JSON)")


def payload_digest(payload: dict) -> str:
    """sha256(canonical-json(payload)) — tip-zorlayan payload'lar reddedilir
    (SW-EVID-1a: TypeError/ValueError, digest uretilmez)."""
    _validate_canonical(payload)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def append_evidence(conn: sqlite3.Connection, event_type: str, payload: dict) -> int:
    """Append one hash-chained entry; returns its seq. Must run inside a transaction
    to keep the chain linear under concurrency."""
    cur = conn.execute(
        "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["payload_hash"] if row else GENESIS
    payload_hash = payload_digest(payload)
    cur = conn.execute(
        "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash, ed25519_sig) "
        "VALUES (?, ?, ?, ?)",
        (event_type, payload_hash, prev_hash, UNSIGNED_F0),
    )
    return int(cur.lastrowid)


def _as_blob(sig: object) -> bytes | None:
    """Imza kolonunu byte'a cevir; cevrilemeyen (str/int/...) deger None doner —
    None 'sozlesme-disi' demektir -> kirmizi (fail-closed: cokme DEGIL, ret var)."""
    if isinstance(sig, (bytes, bytearray, memoryview)):
        return bytes(sig)
    return None


def _sig_wellformed(sig: object) -> bool:
    """SW-EVID-1b: imza kolonu sozlesmesi — F0'un ACIK isareti (UNSIGNED_F0)
    ya da 64-bayt Ed25519 imzasi. NULL/bos/kisa/rastgele/metin-lekesi deger
    'sessiz imzasizlik'tir; fail-closed reddedilir (cokme yok, kirmizi var)."""
    raw = _as_blob(sig)
    if raw is None:
        return False
    return raw == UNSIGNED_F0 or len(raw) == _SIG_LEN


def _hash_wellformed(value: object) -> bool:
    """SW-EVID-2: payload_hash 64-kucuk-hex bir METIN olmali. BLOB/yazilmis bir
    deger (elle INSERT) regex'i patlatir — o da kirmizidir, hata degil."""
    return isinstance(value, str) and bool(_DIGEST_RE.match(value))


def verify_chain(conn: sqlite3.Connection) -> tuple[bool, int]:
    """Recompute the chain; returns (ok, entries_checked).

    Her satir fail-closed denetlenir:
      - payload_hash gecerli bir SHA-256 ozeti (64-kucuk-hex metin) olmali
        (SW-EVID-2),
      - ed25519_sig F0-acik-isareti ya da 64-bayt imza olmali (SW-EVID-1b:
        sessiz-imzasizlik kabul edilmez),
      - prev_hash onceki satirin payload_hash'ine (ilk satirda GENESIS) bagli olmali.
    Kirmizida (False, k) — k, kirilma noktasina kadar dogrulanan satir sayisi.
    Denetimlerin hicbiri istisna FIRLATMAZ: bozuk satir = kirmizi (fail-closed).
    """
    prev = GENESIS
    checked = 0
    for row in conn.execute(
            "SELECT seq, payload_hash, prev_hash, ed25519_sig"
            " FROM evidence_ledger ORDER BY seq"):
        h = row["payload_hash"]
        if not _hash_wellformed(h):         # SW-EVID-2: gercek-ozet-zorunlu
            return False, checked
        if not _sig_wellformed(row["ed25519_sig"]):   # SW-EVID-1b
            return False, checked
        if row["prev_hash"] != prev:
            return False, checked
        prev = h
        checked += 1
    return True, checked
