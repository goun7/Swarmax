"""test_evidence_dallar.py — swarmax/evidence.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/evidence.py, 49 satir) — public API:
  payload_digest(payload)        -> sha256(canonical-json(payload)) hex  (L17)
  append_evidence(conn,tip,payload) -> bos tablo -> prev=GENESIS; degilse
                                     prev = son satirin payload_hash; seq doner (L23)
  verify_chain(conn)             -> (ok, sayi); kirik zincirde (False, k)  (L39)
  sabitler: GENESIS='GENESIS', UNSIGNED_F0=b'F0-UNSIGNED-F2-PENDING'

DAL HARITASI:
  payload_digest: anahtar-sira-bagimsizligi (sort_keys), ayristirici
    kompaktligi (separators), farkli-payload-farkli-hash, determinizm,
    unicode-guvenli, 64-hex.
  append_evidence: bos-tablo GENESIS bagi, zincir-baglantisi (prev onceki
    payload_hash), seq=lastrowid, ed25519_sig=UNSIGNED_F0 isareti, event_type
    ayni olsa payload farkliysa hash farkli.
  verify_chain: bos tablo (True,0); gecerli (True,N); kirik bagda
    (False, k) — k kirilma noktasina kadar dogrulanan satir sayisi.
  append-only tetikleyicileri (sqlite_v1.sql): UPDATE/DELETE -> RAISE(ABORT).

BULGU-1 (production'a DOKUNULMADI — gerceklik test dosyasinda belgelendi):
  kanonik-JSON normalizasyonu iki Python tipi arasinda CARPISMAYA neden olur:
    (a) {1: 'a'} ile {'1': 'a'} AYNI digest — json.dumps int anahtari str'ye
        zorlar ('{"1": "a"}'); dict Python'da farkli turlu olsa da.
    (b) {'a': (1,2)} ile {'a': [1,2]} AYNI digest — tuple JSON dizisi olarak
        serilesir; Python tipi kaybolur.
  Ek: {'k': 1} ile {'k': 1.0} FARKLIdir (json 1.0'i korur) — bu carpisma
  gerceklesmez; kanit testlerle olculdu. Onem: payload turleri SHA-256
  oncesinde tam korunmaz; ayni digest iki farkli nesneyi isaret edebilir.
  Ek-2: verify_chain YALNIZCA prev_hash baglarini sayar; payload_hash'in
  gecersiz bir deger olmasini DENETLEMEZ (payload'lar tabloda saklanmadigi
  icin bu imkansizdir — zincilg baglantisi olmasa da gecersiz hash
  kaydedilebilir).

Kural-1: SADECE yeni test dosyasi. Kural-4: saf in-memory sqlite.
"""
from __future__ import annotations

import sqlite3
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import evidence  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


@pytest.fixture()
def zincir(db):
    """Uc satirli, hash zinciri append_evidence ile kurulmus tablo."""
    evidence.append_evidence(db, "olay_a", {"sira": 1})
    evidence.append_evidence(db, "olay_a", {"sira": 2})
    evidence.append_evidence(db, "olay_b", {"sira": 3})
    return db


# =================================================== payload_digest =========
class TestPayloadDigest:
    """payload_digest kanoniklestirme + determinizm dallari."""

    def test_cikti_64_hex(self):
        """Dal: cikti SHA-256 hex (64 karakter, hex-alfebasi)."""
        d = evidence.payload_digest({"a": 1})
        assert len(d) == 64
        int(d, 16)

    @pytest.mark.parametrize("once,sonda", [
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
        ({"z": 1, "a": {"y": 1, "x": 2}}, {"a": {"x": 2, "y": 1}, "z": 1}),
    ])
    def test_anahtar_sirasi_bagimsiz(self, once, sonda):
        """Dal: sort_keys=True -> anahtar siralamasi digest'i DEGISTIRMEZ."""
        assert evidence.payload_digest(once) == evidence.payload_digest(sonda)

    def test_kanonik_string_birebir(self):
        """Dal: separators=(',',':') + sort_keys -> cikti '{"a":1}' ile ayni."""
        import hashlib
        dgst = hashlib.sha256(b'{"a":1}').hexdigest()
        assert evidence.payload_digest({"a": 1}) == dgst

    @pytest.mark.parametrize("a,b", [
        ({"a": 1}, {"a": 2}),
        ({"a": 1}, {"a": 1, "b": 2}),
        ({"a": 1}, {}),
        ({"a": 1}, {"a": "1"}),   # tip degisimi
        ({"a": [1, 2]}, {"a": [2, 1]}),
    ])
    def test_farkli_payload_farkli_digest(self, a, b):
        """Dal: her anlamli fark digest'i degistirir."""
        assert evidence.payload_digest(a) != evidence.payload_digest(b)

    def test_determinizm(self):
        """Dal: ayni payload -> her zaman ayni digest."""
        p = {"b": [1, 2], "a": "x", "n": {"i": 1}}
        assert evidence.payload_digest(p) == evidence.payload_digest(p)

    def test_unicode_deterministik(self):
        """Dal: json.dumps ensure_ascii -> Türkce karakterler kacis dizisi,
        digest kararli ve tekrarlanabilirdir."""
        p = {"kullanici": "Gökün", "sehir": "İstanbul"}
        assert evidence.payload_digest(p) == evidence.payload_digest(p)

    def test_bos_payload(self):
        """Dal: {} -> yine 64-hex, digerlerinden farkli."""
        d = evidence.payload_digest({})
        assert len(d) == 64 and d != evidence.payload_digest({"a": 1})

    @pytest.mark.parametrize("a,b", [
        ({1: "a"}, {"1": "a"}),           # BULGU-1: int anahtar str'ye zorlanir
        ({"a": (1, 2)}, {"a": [1, 2]}),   # BULGU-1: tuple JSON dizisi olarak serilesir
    ])
    def test_tip_zorlamasi_carpismasi(self, a, b):
        """BULGU-1: kanonik-JSON iki ayri Python tipini ayni digest'e goturur
        (int-anahtar->str; tuple->array). SHA-256 oncesi normalizasyon bu
        sinirlari KORUMAZ; kanit bu dosyada, production'a DOKUNULMADI."""
        assert a != b  # Python duzeyinde farkli turler
        assert evidence.payload_digest(a) == evidence.payload_digest(b)

    def test_int_anahtar_str_anahtardan_ayrisabilir(self):
        """Dal: 1 ve 2 anahtarlari str'ye zorlanir ama BIRBIRINDEN farklidir."""
        assert evidence.payload_digest({1: "a"}) != evidence.payload_digest({2: "a"})


# =================================================== append_evidence ========
class TestKanalEkleme:
    """append_evidence GENESIS bagi + zincir + seq + isaret dallari."""

    def test_bos_tabloda_genesis_bagi(self, db):
        """Dal: tablo bos -> prev_hash = GENESIS."""
        seq = evidence.append_evidence(db, "ilk", {"x": 1})
        assert seq == 1
        row = db.execute("SELECT * FROM evidence_ledger WHERE seq=1").fetchone()
        assert row["prev_hash"] == evidence.GENESIS
        assert row["payload_hash"] == evidence.payload_digest({"x": 1})

    def test_zincir_baglantisi(self, zincir):
        """Dal: her satirin prev_hash'i oncekinin payload_hash'i."""
        satirlar = zincir.execute(
            "SELECT seq, payload_hash, prev_hash FROM evidence_ledger ORDER BY seq"
        ).fetchall()
        assert len(satirlar) == 3
        assert satirlar[0]["prev_hash"] == evidence.GENESIS
        assert satirlar[1]["prev_hash"] == satirlar[0]["payload_hash"]
        assert satirlar[2]["prev_hash"] == satirlar[1]["payload_hash"]

    def test_seq_artan_ve_int(self, zincir):
        """Dal: donus degeri int lastrowid ve artandir."""
        s4 = evidence.append_evidence(zincir, "olay_c", {"sira": 4})
        assert isinstance(s4, int)
        assert s4 == 4

    def test_isaret_unsigned_f0(self, db):
        """Dal: ed25519_sig her zaman UNSIGNED_F0 isaretini tasiyor (F2 bekleme)."""
        evidence.append_evidence(db, "olay", {})
        row = db.execute("SELECT ed25519_sig FROM evidence_ledger").fetchone()
        assert bytes(row["ed25519_sig"]) == evidence.UNSIGNED_F0

    def test_event_type_ayi_payload_farkliysa_hash_farkli(self, db):
        """Dal: ayni event_type, farkli payload -> farkli payload_hash."""
        evidence.append_evidence(db, "olay", {"n": 1})
        evidence.append_evidence(db, "olay", {"n": 2})
        hashlar = [r["payload_hash"] for r in db.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq")]
        assert hashlar[0] != hashlar[1]

    def test_created_at_dolu(self, db):
        """Dal: created_at DEFAULT CURRENT_TIMESTAMP ile set edilir."""
        evidence.append_evidence(db, "olay", {})
        row = db.execute("SELECT created_at FROM evidence_ledger").fetchone()
        assert row["created_at"] is not None


# ====================================================== verify_chain ========
class TestZincirDogrulama:
    """verify_chain bos/gecerli/kirik dallari + (False, k) konumu."""

    def test_bos_tablo_true_sifir(self, db):
        """Dal: hic satir yok -> (True, 0)."""
        assert evidence.verify_chain(db) == (True, 0)

    def test_tek_satir_gecerli(self, db):
        """Dal: GENESIS bagli tek satir -> (True, 1)."""
        evidence.append_evidence(db, "tek", {})
        assert evidence.verify_chain(db) == (True, 1)

    def test_uc_satir_gecerli(self, zincir):
        """Dal: append_evidence ile kurulmus zincir -> (True, 3)."""
        assert evidence.verify_chain(zincir) == (True, 3)

    def test_kirik_ilk_satirda(self, db):
        """Dal: ilk satirin prev_hash != GENESIS -> (False, 0)."""
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('x', ? , 'ASLA-GENESIS', ?)",
            ("a" * 64, evidence.UNSIGNED_F0))
        assert evidence.verify_chain(db) == (False, 0)

    def test_kirik_ikinci_satirda_konum(self, db):
        """Dal: kirilma 2. satirda -> (False, 1) — k dogrulanan satir sayisi."""
        evidence.append_evidence(db, "a", {"i": 1})  # gecerli GENESIS bagi
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('b', ? , 'KIRIK', ?)",
            ("b" * 64, evidence.UNSIGNED_F0))
        assert evidence.verify_chain(db) == (False, 1)

    def test_kirik_ucuncu_satirda_konum(self, db):
        """Dal: kirilma 3. satirda -> (False, 2)."""
        evidence.append_evidence(db, "a", {"i": 1})
        evidence.append_evidence(db, "b", {"i": 2})
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('c', ? , 'KIRIK-3', ?)",
            ("c" * 64, evidence.UNSIGNED_F0))  # prev_hash onceki payload_hash DEGIL
        assert evidence.verify_chain(db) == (False, 2)

    def test_verify_chain_sadece_prev_baglarini_sayar(self, db):
        """Dal: 2. satirin payload_hash'i gercek digest DEGIL ama prev_hash
        baglisi — verify_chain (True, 3) verir. BULGU: verify_chain
        payload_hash'lerin payload ile eslestigini DENETLEMEZ (payload'lar
        tabloda olmadigi icin); yalnizca zincir baglarini sayar."""
        evidence.append_evidence(db, "a", {"i": 1})
        dogru = db.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()["payload_hash"]
        # 2. satirin prev_hash'i dogru ama payload_hash'i gercek digest DEGIL
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('b', ? , ?, ?)",
            ("sabit-olmayan", dogru, evidence.UNSIGNED_F0))
        # zincir baglanti acisindan: 3. satir eklersek onun prev'i 'sabit-olmayan'
        evidence.append_evidence(db, "c", {"i": 3})
        # append_evidence son satirin payload_hash'ini alir -> 3. satir bagli;
        # ama 2. satirin payload_hash'i kendi payload'una uymuyor olsa da
        # verify_chain yalnizca prev_hash baglantilarini sayar.
        ok, n = evidence.verify_chain(db)
        assert (ok, n) == (True, 3)


# ============================================ append-only tetikleyici =======
class TestAppendOnlyTetikleyici:
    """evidence_ledger UPDATE/DELETE yasaklari (sqlite_v1.sql tetikleyicileri)."""

    def test_update_yasak(self, zincir):
        """Dal: BEFORE UPDATE RAISE(ABORT) -> IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError, match="UPDATE forbidden"):
            zincir.execute("UPDATE evidence_ledger SET event_type='x' WHERE seq=1")

    def test_delete_yasak(self, zincir):
        """Dal: BEFORE DELETE RAISE(ABORT) -> IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError, match="DELETE forbidden"):
            zincir.execute("DELETE FROM evidence_ledger WHERE seq=1")

    def test_insert_serbest(self, zincir):
        """Dal: ekleme yasak DEGIL — append-only tam olarak UPDATE/DELETE."""
        once = zincir.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        evidence.append_evidence(zincir, "yeni", {})
        sonra = zincir.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        assert (once, sonra) == (3, 4)

    def test_tetikleyici_hata_sonrasi_zincir_saglam(self, zincir):
        """Dal: yasak UPDATE Transaction'i geri alir, zincir bozulmaz."""
        with pytest.raises(sqlite3.IntegrityError):
            zincir.execute("UPDATE evidence_ledger SET prev_hash='x' WHERE seq=2")
        assert evidence.verify_chain(zincir) == (True, 3)
