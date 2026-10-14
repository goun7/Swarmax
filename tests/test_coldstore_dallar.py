"""test_coldstore_dallar.py — swarmax/coldstore.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/coldstore.py, 216 satir) — public API (__all__):
  S3CompatStore(endpoint, bucket, access, secret, *, region, prefix)
      __init__ : scheme http|https + hostname dogrulamasi; port cikarimi;
                 host_header imzada wire ile birebir olmali (L55)
      put(name, data)  -> status 200|201 -> "bucket/prefix/name"; yoksa RuntimeError (L113)
      head(name)       -> status==200 (L119)
      get(name)        -> status 200 -> bytes; yoksa RuntimeError (L123)
      _sigv4/_request/_key — SigV4 imzasi + urllib tasiyicisi (private, test edildi)
  archive_ledger(conn, store, *, upto_seq=None)
      bos ledger -> ValueError; CHUNK_ROWS'lik parcalar; zaten varsa (HEAD)
      atla (idempotent); manifest.json her seferinde yeniden yazilir (L131)
  verify_manifest_bytes(manifest_bytes, fetch_chunk)
      chunk sha256 / boundary / chain_digest / prev_hash zinciri / row-count
      dogrulamasi; her biri ozneden doner (L182)
  verify_archive(store) -> manifest + chunk indir, zinciri SIFIRDAN kur (L211)
      (DB ya da ozel anahtar GEREKMEZ — self-authenticating)

AG STUB'LAMA (Kural-4): urllib.request.urlopen, in-memory FakeS3 ile
monkeypatch edilir. Gercek SigV4 imzalama + _request + put/head/get
KODU calisir; yalnizca tasiyici sahtedir. Gercek ag/RPC/subprocess YOK.

Kural-1: SADECE yeni test dosyasi; production/conftest'e DOKUNULMADI.
filterwarnings=error::UserWarning => ureten yol YOK.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.error

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import coldstore, evidence  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402


# ============================================ fake S3 backend ==============
class FakeResponse:
    """urlopen donus taklidi: status + read() + context-manager."""

    def __init__(self, status: int, data: bytes = b""):
        self.status = status
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeS3:
    """In-memory S3 backend; monkeypatch hedefi (urllib.request.urlopen)."""

    def __init__(self, *, put_status: int = 200, missing_code: int = 404):
        self.objects: dict[str, bytes] = {}
        self.requests: list[tuple[str, str, bytes | None, dict]] = []
        self.put_status = put_status
        self.missing_code = missing_code

    def __call__(self, req, timeout=None):
        method = req.get_method()
        key = "/".join(req.full_url.split("/")[4:])  # scheme://host:port/bucket/KEY
        body = req.data
        self.requests.append((method, key, body, dict(req.header_items())))
        if method == "PUT":
            self.objects[key] = body or b""
            return FakeResponse(self.put_status)
        if method == "HEAD":
            if key in self.objects:
                return FakeResponse(200)
            raise self._hata(req.full_url)
        if method == "GET":
            if key in self.objects:
                return FakeResponse(200, self.objects[key])
            raise self._hata(req.full_url)
        raise AssertionError(f"beklenmeyen metod: {method}")

    def _hata(self, url: str) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(url, self.missing_code, "No Such Key", {}, None)

    def manifest(self) -> bytes:
        return next(v for k, v in self.objects.items() if k.endswith("manifest.json"))

    def fetch(self):
        """verify_manifest_bytes icin fetch_chunk(name) -> bytes."""
        def _f(name):
            return next(v for k, v in self.objects.items() if k.endswith("/" + name))
        return _f


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


@pytest.fixture()
def fake(monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(coldstore.urllib.request, "urlopen", s3)
    return s3


@pytest.fixture()
def store(fake):
    return coldstore.S3CompatStore("https://s3.example.com", "testbucket",
                                   "AKID", "SECRET")


@pytest.fixture()
def dolu_ledger(db):
    for i in range(1, 6):
        evidence.append_evidence(db, "olay", {"i": i})
    return db


# ============================================ __init__ dogrulama ===========
class TestUcNoktaDogrulama:
    """S3CompatStore.__init__ scheme/port/host_header/prefix dallari."""

    def test_https_default_port_443(self, fake):
        s = coldstore.S3CompatStore("https://s3.example.com", "b", "a", "s")
        assert (s.scheme, s.host, s.port, s.host_header) == (
            "https", "s3.example.com", 443, "s3.example.com")

    def test_http_default_port_80(self, fake):
        s = coldstore.S3CompatStore("http://s3.example.com", "b", "a", "s")
        assert (s.port, s.host_header) == (80, "s3.example.com")

    @pytest.mark.parametrize("endpoint,beklenen_port", [
        ("http://localhost:9000", 9000),
        ("https://localhost:8443", 8443),
    ])
    def test_standart_disi_port_host_headerde(self, fake, endpoint, beklenen_port):
        """Dal: port (80,443) disinda ise host_header 'host:port' — imzadaki
        Host basligi wire ile birebir olmali (urllib yalnizca standart disi
        portta ekler)."""
        s = coldstore.S3CompatStore(endpoint, "b", "a", "s")
        assert s.port == beklenen_port
        assert s.host_header == f"localhost:{beklenen_port}"

    @pytest.mark.parametrize("kotu", [
        "ftp://s3.example.com",      # izin disi scheme
        "http://",                   # hostname YOK
        "s3.example.com",            # scheme YOK
        "",                          # bos
        "http:///bucket",            # bos hostname
    ])
    def test_gecersiz_uc_nokta_valueerror(self, fake, kotu):
        """Dal: scheme http|https DEGIL veya hostname yok -> ValueError."""
        with pytest.raises(ValueError, match="bad endpoint"):
            coldstore.S3CompatStore(kotu, "b", "a", "s")

    @pytest.mark.parametrize("prefix,beklenen", [
        ("evidence", "evidence"),
        ("evidence/", "evidence"),
        ("/evidence", "evidence"),
        ("/a/b/c/", "a/b/c"),
        ("", ""),
    ])
    def test_prefix_strip(self, fake, prefix, beklenen):
        """Dal: prefix.strip('/') -> bas/son slash kaldirilir."""
        s = coldstore.S3CompatStore("https://s3", "b", "a", "s", prefix=prefix)
        assert s.prefix == beklenen

    def test_anahtar_yapisi(self, fake):
        """Dal: _key(name) = '{prefix}/{name}'."""
        s = coldstore.S3CompatStore("https://s3", "b", "a", "s", prefix="ev")
        assert s._key("manifest.json") == "ev/manifest.json"

    def test_bolge_ve_kimlik_saklanir(self, fake):
        s = coldstore.S3CompatStore("https://s3", "b", "a", "s", region="eu-west-1")
        assert (s.region, s.access_key, s.secret_key) == ("eu-west-1", "a", "s")


# ============================================ SigV4 imzalama ===============
class TestSigV4Imzalama:
    """_sigv4 determinizm + yapi + girdi-duyarliligi dallari."""

    def test_ayni_girdi_ayni_imza(self, store):
        """Dal: Sabit (method, key, payload_hash, amz_date) -> deterministik."""
        a = store._sigv4("PUT", "k/x", hashlib.sha256(b"").hexdigest(), "20260101T000000Z")
        b = store._sigv4("PUT", "k/x", hashlib.sha256(b"").hexdigest(), "20260101T000000Z")
        assert a == b

    @pytest.mark.parametrize("alan,yeni", [
        ("method", "GET"),
        ("key", "k/y"),
        ("payload_hash", hashlib.sha256(b"baska").hexdigest()),
        ("amz_date", "20260102T000000Z"),
    ])
    def test_girdi_degisince_imza_degisir(self, store, alan, yeni):
        """Dal: her girdi imzayi degistirir (method/key/payload/zaman)."""
        taban = dict(method="PUT", key="k/x",
                     payload_hash=hashlib.sha256(b"").hexdigest(),
                     amz_date="20260101T000000Z")
        a = store._sigv4(taban["method"], taban["key"], taban["payload_hash"], taban["amz_date"])
        taban[alan] = yeni
        b = store._sigv4(taban["method"], taban["key"], taban["payload_hash"], taban["amz_date"])
        assert a != b
        assert a["Authorization"].rsplit("Signature=", 1)[1] != \
            b["Authorization"].rsplit("Signature=", 1)[1]

    def test_baslik_yapisi(self, store):
        """Dal: Authorization 'AWS4-HMAC-SHA256 Credential=.../scope, SignedHeaders=..., Signature=hex'."""
        h = store._sigv4("PUT", "k", hashlib.sha256(b"").hexdigest(), "20260101T000000Z")
        assert h["x-amz-date"] == "20260101T000000Z"
        assert h["x-amz-content-sha256"] == hashlib.sha256(b"").hexdigest()
        auth = h["Authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKID/20260101/us-east-1/s3/aws4_request")
        assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
        sig = auth.rsplit("Signature=", 1)[1]
        int(sig, 16) and len(sig) == 64

    def test_bolge_kapsami(self, store):
        """Dal: scope '{datestamp}/{region}/s3/aws4_request' imzada gomulu."""
        s = coldstore.S3CompatStore("https://s3", "b", "a", "z", region="eu-central-1")
        h = s._sigv4("GET", "k", "p".encode().hex() * 8, "20260615T120000Z")
        assert "20260615/eu-central-1/s3/aws4_request" in h["Authorization"]


# ============================================ put/head/get =================
class TestMagazaIslemleri:
    """put/head/get basari + basarisiz HTTP dallari (FakeS3 tasiyici)."""

    def test_put_donus_yolu(self, store, fake):
        """Dal: 200 -> 'bucket/prefix/name'."""
        assert store.put("f.txt", b"merhaba") == "testbucket/evidence/f.txt"

    def test_put_201_kabul(self, fake):
        """Dal: 201 de basarili sayilir (R2/MinIO davranisi)."""
        fake.put_status = 201
        s = coldstore.S3CompatStore("https://s3", "b", "a", "z")
        assert s.put("f.txt", b"x") == "b/evidence/f.txt"

    def test_put_500_runtimeerror(self, fake):
        """Dal: status 200|201 disi -> RuntimeError 'S3 PUT failed'."""
        fake.put_status = 500
        s = coldstore.S3CompatStore("https://s3", "b", "a", "z")
        with pytest.raises(RuntimeError, match="S3 PUT failed: HTTP 500"):
            s.put("f.txt", b"x")

    def test_head_var_yok(self, store, fake):
        """Dal: var -> True; yok -> HTTPError yutulur, False."""
        store.put("f.txt", b"data")
        assert store.head("f.txt") is True
        assert store.head("yok.txt") is False

    def test_get_roundtrip(self, store, fake):
        """Dal: put -> get bytes birebir."""
        blob = b"\x00\x01\x02gzip" * 10
        store.put("arsiv.gz", blob)
        assert store.get("arsiv.gz") == blob

    def test_get_yoksa_runtimeerror(self, store, fake):
        """Dal: GET 404 -> RuntimeError 'S3 GET failed: HTTP 404'."""
        with pytest.raises(RuntimeError, match="S3 GET failed: HTTP 404"):
            store.get("yok.gz")

    def test_get_500_runtimeerror(self, fake):
        """Dal: GET 500 -> RuntimeError (404 disi kod da ayni yolu izler)."""
        fake.missing_code = 500
        s = coldstore.S3CompatStore("https://s3", "b", "a", "z")
        with pytest.raises(RuntimeError, match="S3 GET failed: HTTP 500"):
            s.get("yok.gz")

    def test_islem_yollari_prefix_icerir(self, store, fake):
        """Dal: her istek '{prefix}/{name}' anahtarina gider."""
        store.put("f.txt", b"x")
        store.head("f.txt")
        store.get("f.txt")
        anahtarlar = [r[1] for r in fake.requests]
        assert anahtarlar == ["evidence/f.txt"] * 3
        yontemler = [r[0] for r in fake.requests]
        assert yontemler == ["PUT", "HEAD", "GET"]


# ============================================ _request detaylari ===========
class TestIstekDetaylari:
    """_request Content-Length + URL + body-hash dallari."""

    def test_body_varsa_content_length(self, store, fake):
        """Dal: body is not None -> 'Content-Length' basligi eklenir."""
        store.put("f", b"12345")
        _, _, body, basliklar = fake.requests[-1]
        assert body == b"12345"
        assert basliklar["Content-length"] == "5"

    def test_body_yoksa_content_length_yok(self, store, fake):
        """Dal: body None (HEAD/GET) -> Content-Length basligi YOK."""
        store.head("f")
        _, _, body, basliklar = fake.requests[-1]
        assert body is None
        assert "Content-length" not in basliklar

    def test_bos_govde_bos_hash(self, store, fake):
        """Dal: body None -> x-amz-content-sha256 = sha256(b'') (S3 kurali)."""
        store.head("f")
        _, _, _, basliklar = fake.requests[-1]
        assert basliklar["X-amz-content-sha256"] == hashlib.sha256(b"").hexdigest()

    def test_govde_hashi_govdeden(self, store, fake):
        """Dal: PUT icin payload hash dogrudan sha256(body)."""
        store.put("f", b"abcdef")
        _, _, _, basliklar = fake.requests[-1]
        assert basliklar["X-amz-content-sha256"] == hashlib.sha256(b"abcdef").hexdigest()

    def test_url_path_style(self, store, fake):
        """Dal: URL path-style scheme://host:port/bucket/key."""
        store.head("f")
        # fake, full URL'den '/bucket/' sonrasini anahtar olarak cikardi
        assert fake.requests[-1][1] == "evidence/f"

    def test_imzali_basliklar_her_istekte(self, store, fake):
        """Dal: her istek Authorization + x-amz-date tasiyor."""
        store.head("f")
        _, _, _, basliklar = fake.requests[-1]
        assert basliklar["Authorization"].startswith("AWS4-HMAC-SHA256")
        assert len(basliklar["X-amz-date"]) == 16  # YYYYmmddTHHMMSSZ


# ============================================ archive_ledger ===============
class TestArsivleme:
    """archive_ledger bos/idempotent/upto_seq/cok-parca dallari."""

    def test_bos_ledger_valueerror(self, db, store):
        """Dal: satir yok -> ValueError 'nothing to archive'."""
        with pytest.raises(ValueError, match="nothing to archive"):
            coldstore.archive_ledger(db, store)

    def test_tek_parca_ve_manifest(self, dolu_ledger, store, fake):
        """Dal: 5 satir < CHUNK_ROWS -> 1 parca + manifest.json."""
        r = coldstore.archive_ledger(dolu_ledger, store)
        assert (r["chunks_stored"], r["chunks_skipped"], r["rows"], r["last_seq"]) == (
            1, 0, 5, 5)
        assert "evidence/chunk_000000000001_000000000005.json.gz" in fake.objects
        assert "evidence/manifest.json" in fake.objects

    def test_manifest_icerigi(self, dolu_ledger, store, fake):
        """Dal: manifest version/first/last/rows/genesis_prev/chunks meta."""
        coldstore.archive_ledger(dolu_ledger, store)
        m = json.loads(fake.manifest())
        assert (m["version"], m["first_seq"], m["last_seq"], m["rows"]) == (1, 1, 5, 5)
        assert m["genesis_prev"] == evidence.GENESIS
        assert len(m["chunks"]) == 1
        c = m["chunks"][0]
        assert (c["first_seq"], c["last_seq"], c["rows"]) == (1, 5, 5)
        blob = fake.objects["evidence/" + c["key"]]
        assert c["sha256"] == hashlib.sha256(blob).hexdigest()

    def test_chain_digest_govde_hashlerinden(self, dolu_ledger, store, fake):
        """Dal: chain_digest = sha256(payload_hash'lerin birlesimi)."""
        coldstore.archive_ledger(dolu_ledger, store)
        m = json.loads(fake.manifest())
        satirlar = dolu_ledger.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq").fetchall()
        beklenen = hashlib.sha256(
            "".join(s["payload_hash"] for s in satirlar).encode()).hexdigest()
        assert m["chunks"][0]["chain_digest"] == beklenen

    def test_parca_govdesi_gzip_json(self, dolu_ledger, store, fake):
        """Dal: parca gzip + JSON; ed25519_sig HEX olarak yazilir."""
        coldstore.archive_ledger(dolu_ledger, store)
        blob = fake.objects["evidence/chunk_000000000001_000000000005.json.gz"]
        satirlar = json.loads(gzip.decompress(blob))
        assert len(satirlar) == 5
        assert set(satirlar[0]) == {"seq", "event_type", "payload_hash",
                                    "prev_hash", "ed25519_sig", "created_at"}
        # BLOB -> hex (text-safe arsivleme)
        assert satirlar[0]["ed25519_sig"] == evidence.UNSIGNED_F0.hex()
        assert all(isinstance(r["ed25519_sig"], str) for r in satirlar)

    def test_idempotent_ikinci_kosusta_atla(self, dolu_ledger, store, fake):
        """Dal: parca zaten varsa (HEAD 200) atla; manifest yine yazilir."""
        bir = coldstore.archive_ledger(dolu_ledger, store)
        assert bir["chunks_stored"] == 1
        iki = coldstore.archive_ledger(dolu_ledger, store)
        assert (iki["chunks_stored"], iki["chunks_skipped"]) == (0, 1)
        # manifest her seferinde yeniden yazilir (tek isaretci)
        assert "evidence/manifest.json" in fake.objects

    def test_upto_seq_filtresi(self, dolu_ledger, store, fake):
        """Dal: upto_seq -> yalnizca seq <= upto satirlari."""
        r = coldstore.archive_ledger(dolu_ledger, store, upto_seq=3)
        assert (r["rows"], r["last_seq"]) == (3, 3)
        m = json.loads(fake.manifest())
        assert m["chunks"][0]["last_seq"] == 3

    def test_upto_seq_sifir_hic_veri_yok(self, dolu_ledger, store):
        """Dal: upto_seq=0 -> bos sonuc -> ValueError (dallar: 0 satir)."""
        with pytest.raises(ValueError, match="nothing to archive"):
            coldstore.archive_ledger(dolu_ledger, store, upto_seq=0)

    def test_cok_parca_limiti(self, db, store, fake, monkeypatch):
        """Dal: len(rows) > CHUNK_ROWS -> birden fazla parca (sinir 2'ye dusuldu)."""
        monkeypatch.setattr(coldstore, "CHUNK_ROWS", 2)
        for i in range(1, 6):
            evidence.append_evidence(db, "olay", {"i": i})
        r = coldstore.archive_ledger(db, store)
        assert r["chunks_stored"] == 3  # 5 satir / 2 = 3 parca
        m = json.loads(fake.manifest())
        assert [c["last_seq"] for c in m["chunks"]] == [2, 4, 5]
        assert [c["rows"] for c in m["chunks"]] == [2, 2, 1]

    def test_gzip_deterministik(self, dolu_ledger, store, fake):
        """Dal: gzip.compress(mtime=0) -> ayni parca her zaman BIREBIR bytes."""
        coldstore.archive_ledger(dolu_ledger, store)
        once = fake.objects["evidence/chunk_000000000001_000000000005.json.gz"]
        fake.objects.clear()
        coldstore.archive_ledger(dolu_ledger, store)
        sonra = fake.objects["evidence/chunk_000000000001_000000000005.json.gz"]
        assert once == sonra


# ======================================== verify_manifest_bytes ============
class TestManifestDogrulama:
    """verify_manifest_bytes sha256/boundary/chain/row-count dallari."""

    @pytest.fixture()
    def arsiv(self, dolu_ledger, store, fake):
        """Gecerli arsiv + manifest byte'lari + fetch_chunk."""
        coldstore.archive_ledger(dolu_ledger, store)
        return fake

    def test_gecerli_manifest_ok(self, arsiv):
        """Dal: tertemiz arsiv -> ok=True, rows=5, last_seq=5."""
        sonuc = coldstore.verify_manifest_bytes(arsiv.manifest(), arsiv.fetch())
        assert sonuc["ok"] is True
        assert (sonuc["rows"], sonuc["last_seq"]) == (5, 5)
        assert sonuc["reason"] is None

    def test_parca_sha256_uyusmaz(self, arsiv):
        """Dal: blob degismisse -> ok=False 'chunk hash mismatch'."""
        anahtar = next(k for k in arsiv.objects if k.endswith(".json.gz"))
        arsiv.objects[anahtar] = b"bozulmus"
        sonuc = coldstore.verify_manifest_bytes(arsiv.manifest(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert "chunk hash mismatch" in sonuc["reason"]

    def test_sinir_uyusmaz(self, arsiv):
        """Dal: manifest first_seq/last_seq yanlissa -> 'boundary mismatch'."""
        m = json.loads(arsiv.manifest())
        m["chunks"][0]["first_seq"] = 999
        sonuc = coldstore.verify_manifest_bytes(
            json.dumps(m).encode(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert "chunk boundary mismatch" in sonuc["reason"]

    def test_chain_digest_uyusmaz(self, arsiv):
        """Dal: manifest chain_digest yanlissa -> 'chain digest mismatch'."""
        m = json.loads(arsiv.manifest())
        m["chunks"][0]["chain_digest"] = "f" * 64
        sonuc = coldstore.verify_manifest_bytes(
            json.dumps(m).encode(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert "chain digest mismatch" in sonuc["reason"]

    def test_zincir_kirigi_genesis(self, arsiv):
        """Dal: genesis_prev yanlissa ilk satirda kirilir -> 'chain break at seq 1'."""
        m = json.loads(arsiv.manifest())
        m["genesis_prev"] = "YANLIS-GENESIS"
        sonuc = coldstore.verify_manifest_bytes(
            json.dumps(m).encode(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert "chain break at seq 1" in sonuc["reason"]

    def test_zincir_kirigi_ortada(self, arsiv, monkeypatch):
        """Dal: ortadaki bir satirin prev_hash'i degisse -> o seq'de kirilma.
        Blob degistigi icin manifest sha256 de guncellenmeli (gercek tahrif)."""
        m = json.loads(arsiv.manifest())
        anahtar = next(k for k in arsiv.objects if k.endswith(".json.gz"))
        satirlar = json.loads(gzip.decompress(arsiv.objects[anahtar]))
        satirlar[2]["prev_hash"] = "TAMPER"   # 3. satirin bagi kirilir
        blob = gzip.compress(json.dumps(satirlar).encode(), mtime=0)
        arsiv.objects[anahtar] = blob
        m["chunks"][0]["sha256"] = hashlib.sha256(blob).hexdigest()
        sonuc = coldstore.verify_manifest_bytes(
            json.dumps(m).encode(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert "chain break at seq 3" in sonuc["reason"]

    def test_satir_sayisi_uyusmaz(self, arsiv):
        """Dal: manifest rows != gorulen satir -> ok=False 'row count mismatch'."""
        m = json.loads(arsiv.manifest())
        m["rows"] = 999
        sonuc = coldstore.verify_manifest_bytes(
            json.dumps(m).encode(), arsiv.fetch())
        assert sonuc["ok"] is False
        assert sonuc["reason"] == "row count mismatch"

    def test_fetch_chunk_anahtarla_cagrilir(self, arsiv):
        """Dal: fetch_chunk'a manifest'teki 'key' gecer."""
        m = json.loads(arsiv.manifest())
        cagrildi = []

        def fetch(name):
            cagrildi.append(name)
            return arsiv.fetch()(name)

        coldstore.verify_manifest_bytes(json.dumps(m).encode(), fetch)
        assert cagrildi == [c["key"] for c in m["chunks"]]

    def test_cok_parcali_manifest(self, db, store, fake, monkeypatch):
        """Dal: 2 parca > sirayla dogrulanir, prev zinciri parca disinda DEVAM."""
        monkeypatch.setattr(coldstore, "CHUNK_ROWS", 2)
        for i in range(1, 6):
            evidence.append_evidence(db, "olay", {"i": i})
        coldstore.archive_ledger(db, store)
        sonuc = coldstore.verify_manifest_bytes(fake.manifest(), fake.fetch())
        assert sonuc["ok"] is True
        assert sonuc["rows"] == 5
        # 3 parca da islendi
        m = json.loads(fake.manifest())
        assert len(m["chunks"]) == 3


# ============================================ verify_archive ===============
class TestArsivDogrulama:
    """verify_archive store.get uzerinden tam round-trip (DB/anahtar GEREKMEZ)."""

    def test_roundtrip_ok(self, dolu_ledger, store, fake):
        """Dal: arsivlenmis magaza offline dogrulanir."""
        coldstore.archive_ledger(dolu_ledger, store)
        sonuc = coldstore.verify_archive(store)
        assert sonuc["ok"] is True
        assert (sonuc["rows"], sonuc["last_seq"]) == (5, 5)

    def test_tahrif_edilmis_parca(self, dolu_ledger, store, fake):
        """Dal: tahrif edilmis parca -> ok=False, nedeni belirtilmis."""
        coldstore.archive_ledger(dolu_ledger, store)
        anahtar = next(k for k in fake.objects if k.endswith(".json.gz"))
        fake.objects[anahtar] = b"bozuk"
        sonuc = coldstore.verify_archive(store)
        assert sonuc["ok"] is False
        assert "chunk hash mismatch" in sonuc["reason"]

    def test_manifest_yoksa_runtimeerror(self, store, fake):
        """Dal: manifest yoksa store.get RuntimeError firlatir (404)."""
        with pytest.raises(RuntimeError, match="S3 GET failed"):
            coldstore.verify_archive(store)

    def test_db_ve_anahtar_gerekmez(self, dolu_ledger, store, fake):
        """§10.3 ozelligi: dogrulama yalnizca magazaya bakar — DB baglantisi
        veya Ed25519 ozel anahtari hic kullanilmaz. Kanit: ledger baglantisi
        KAPANSA bile verify_archive calismaya devam eder."""
        coldstore.archive_ledger(dolu_ledger, store)
        dolu_ledger.close()
        sonuc = coldstore.verify_archive(store)
        assert sonuc["ok"] is True
        assert (sonuc["rows"], sonuc["last_seq"]) == (5, 5)
