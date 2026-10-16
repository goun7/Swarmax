"""test_evidence_dallar.py — swarmax/evidence.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/evidence.py) — public API:
  payload_digest(payload)        -> sha256(canonical-json(payload)) hex;
                                    tip-zorlayan payload REDDEDILIR (SW-EVID-1a)
  append_evidence(conn,tip,payload) -> bos tablo -> prev=GENESIS; degilse
                                     prev = son satirin payload_hash; seq doner;
                                     reddedilen payload SATIR YAZMAZ
  verify_chain(conn)             -> (ok, sayi); kirik zincirde (False, k);
                                    payload_hash formati (SW-EVID-2) + imza
                                    kolonu (SW-EVID-1b) fail-closed denetlenir;
                                    bozuk satir istisna COPERTMEZ (kirmizi doner)
  sabitler: GENESIS='GENESIS', UNSIGNED_F0=b'F0-UNSIGNED-F2-PENDING'

DAL HARITASI:
  payload_digest: anahtar-sira-bagimsizligi (sort_keys), ayristirici
    kompaktligi (separators), farkli-payload-farkli-hash, determinizm,
    unicode-guvenli, 64-hex, tip-zorlamasi-fail-closed (str-olmayan anahtar
    tum tipleri, tuple (derin dahil), NaN/Inf, dongusel basvuru, DAG yanlis-
    pozitif kontrolu, sonlu-deger kabul kontrolu).
  append_evidence: bos-tablo GENESIS bagi, zincir-baglantisi (prev onceki
    payload_hash), seq=lastrowid, ed25519_sig=UNSIGNED_F0 isareti, event_type
    ayni olsa payload farkliysa hash farkli, belirsiz-payload-reddi (ledger'a
    satir yazilmaz) + red sonrasi gecerli payload yazilabilirligi.
  verify_chain: bos tablo (True,0); gecerli (True,N); kirik bagda
    (False, k) — k kirilma noktasina kadar dogrulanan satir sayisi;
    payload_hash formati (64-kucuk-hex; buyuk-harf ve BLOB deger kirmizi).
  imza kolonu sozlesmesi (SW-EVID-1b): F0-acik-isareti (True) / 64-bayt imza
    (True) / bos-kisa-uzun-metin-lekesi imza (False, konum korunur).
  append-only tetikleyicileri (sqlite_v1.sql): UPDATE/DELETE -> RAISE(ABORT).

BULGU-1 — DUZELTILDI (SW-EVID-1a, fail-closed): kanonik-JSON normalizasyonu iki
  Python tipini CARPISTIRIYORDU:
    (a) {1: 'a'} ile {'1': 'a'} AYNI digest'ti — json.dumps int anahtari str'ye
        zorlar ('{"1": "a"}').
    (b) {'a': (1,2)} ile {'a': [1,2]} AYNI digest'ti — tuple JSON dizisi olarak
        serilesir; Python tipi kaybolur.
  Cozum: kanoniklestirme tip-ayrimini KORUYAMADIGI icin bu sinif payload'lar
  digest uretmeden reddedilir — TypeError (str-olmayan anahtar, tuple),
  ValueError (NaN/Inf: RFC 8785 gecerli JSON'da sonlu sayi ister; ayrica farkli
  NaN nesneleri ayni 'NaN' dizisine serilirdi; dongusel basvuru). Reddetmek
  dogru fail-closed davranistir: belirsiz digest ledger'a hic girmez.
  Ek: {'k': 1} ile {'k': 1.0} FARKLIdir (json 1.0'i korur) — bu carpisma
  gerceklesmez; kanit testlerle olculdu.
  Ek-2 — DUZELTILDI (SW-EVID-2 + SW-EVID-1b): verify_chain uc satir-duzeyi
  denetimi yapar — payload_hash 64-kucuk-hex formati, imza kolonunun F0-acik-
  isareti ya da 64-bayt Ed25519 imzasi olmasi, prev_hash baglantisi. Icerik
  dogrulamasi payload'lar tabloda saklanmadigi icin hala imkansizdir (iddia
  edilmez). F0 zinciri (imzasiz ama ACIK isaretli) yesil kalmaya devam eder:
  test_uc_satir_gecerli / test_f0_acik_isareti_yesil.

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
        ({1: "a"}, {"1": "a"}),           # BULGU-1: int anahtar str'ye zorlanirdi
        ({"a": (1, 2)}, {"a": [1, 2]}),   # BULGU-1: tuple JSON dizisi olurdu
    ])
    def test_tip_zorlamasi_carpismasi(self, a, b):
        """BULGU-1 -> SW-EVID-1a DUZELTILDI: kanonik-JSON iki ayri Python tipini
        (int-anahtar/str-anahtar; tuple/list) AYNI digest'e goturuyordu.
        Kanoniklestirme tip-ayrimini KORUYAMADIGI icin belirsiz taraf (a) artik
        digest URETEMIYOR (TypeError, fail-closed); yalnizca kanonik taraf (b)
        hash'lanir — dolayisiyla (a)-(b) arasinda paylasilan bir digest artik
        iddia edilemez. Eski kirmizi assertion 'ayni digest' idi."""
        assert a != b  # Python duzeyinde farkli turler
        with pytest.raises(TypeError, match="SW-EVID-1"):
            evidence.payload_digest(a)
        with pytest.raises(TypeError, match="SW-EVID-1"):
            evidence.payload_digest(a)   # red deterministik: 2. cagri da ayni
        assert len(evidence.payload_digest(b)) == 64   # (b) gecerlidir: zorlama yok

    def test_int_anahtar_str_anahtardan_ayrisabilir(self):
        """SW-EVID-1a: int anahtarlarin 'birbirinden ayrisabilmesi' tip-
        zorlamasina yaslaniyordu ({1:'a'} vs {2:'a'} -> '1'/'2'); zorlama
        kaldirildigi icin str-olmayan anahtar HIC digestlenmez. Ayrisabilirlik
        artik str-anahtar sozlesmesinde: '1' ile '2' farkli digest (eski dalin
        kanonik karsiligi — kapsama korunur, zorlama daline donulmez)."""
        with pytest.raises(TypeError, match="non-str key"):
            evidence.payload_digest({1: "a"})
        with pytest.raises(TypeError, match="non-str key"):
            evidence.payload_digest({2: "a"})
        assert evidence.payload_digest({"1": "a"}) != evidence.payload_digest({"2": "a"})

    @pytest.mark.parametrize("deger", [float("nan"), float("inf"), float("-inf")])
    def test_nan_infinity_reddedilir(self, deger):
        """SW-EVID-1a: NaN/Inf gecerli JSON DEGILDIR (RFC 8785) ve TUM NaN
        nesneleri ayni 'NaN' dizisine serilir -> kimlik kaybi. ValueError."""
        with pytest.raises(ValueError, match="non-finite"):
            evidence.payload_digest({"k": deger})

    @pytest.mark.parametrize("deger", [0.0, -0.5, 1e308, 1, "NaN", None, True])
    def test_sonlu_ve_gecerli_degerler_kabul(self, deger):
        """Dal (olumlu kontrol): sonlu sayilar ve diger JSON-degerleri
        kabul edilir — red sinifi asiri genisletilmedi, gecerli payload'lar
        hash'lanmaya devam eder."""
        assert len(evidence.payload_digest({"k": deger})) == 64

    @pytest.mark.parametrize("anahtar", [1, 2.5, True, None, (1,)])
    def test_str_olmayan_her_anahtar_tipi_reddedilir(self, anahtar):
        """SW-EVID-1a: int/float/bool/None/tuple anahtarlarin hepsi JSON'da
        str'ye dusurulurdu -> tek kapi TypeError, her anahtar tipi dali kapali."""
        with pytest.raises(TypeError, match="non-str key"):
            evidence.payload_digest({anahtar: "a"})

    def test_tuple_nested_yapida_da_reddedilir(self):
        """Dal: dogrulama REKURSIFTIR — tuple derin list/dict icinde de
        yakalanir (yuzeyel kontrol yalnizca top-level'i gorurdu)."""
        with pytest.raises(TypeError, match="tuple"):
            evidence.payload_digest({"k": [{"i": [1, (2, 3)]}]})
        with pytest.raises(TypeError, match="tuple"):
            evidence.payload_digest([(1, 2)])   # top-level dizi de denetlenir

    def test_dongusel_basvuru_reddedilir(self):
        """Dal: kendi kendine isaret eden payload -> ValueError (json.dumps'un
        'Circular reference detected' hatasindan once, konum bilgisiyle)."""
        p: dict = {"a": 1}
        p["kendisi"] = p
        with pytest.raises(ValueError, match="circular"):
            evidence.payload_digest(p)

    def test_derin_dongu_reddedilir(self):
        """Dal: dongu dict -> list -> dict uzerinden kurulsa da yakalanir."""
        ic: dict = {}
        dis: dict = {"ic": [ic]}
        ic["dis"] = dis
        with pytest.raises(ValueError, match="circular"):
            evidence.payload_digest(dis)

    def test_kardes_ayni_nesne_dongu_degildir(self):
        """Dal (yanlis-pozitif kontrolu): iki kardes dalin AYNI nesneyi
        gosteresi (DAG) dongu DEGILDIR — kabul edilmeli, yoksa gecerli
        payload'lar yanlisla reddedilir ve ledger yazilamaz."""
        ortak = {"x": 1}
        assert len(evidence.payload_digest({"sol": ortak, "sag": ortak})) == 64


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

    @pytest.mark.parametrize("payload", [
        {1: "a"},                # str-olmayan anahtar (tip-zorlamasi)
        {"a": (1, 2)},           # tuple (JSON dizisine donerdi)
        {"a": float("nan")},     # gecersiz JSON sayisi
        {"k": {"i": [1, (2, 3)]}},   # derin tuple
    ])
    def test_belirsiz_payload_reddi_ledgere_yazmaz(self, db, payload):
        """SW-EVID-1a (DAL HARITASI: belirsiz-payload-reddi): reddedilen payload
        ledger'a HIC satir yazmaz — digest uretilmedigi icin INSERT'e de
        gelinmez; zincir yesil ve sayac ayni kalir (fail-closed, yan-yazim yok)."""
        once = db.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        with pytest.raises((TypeError, ValueError)):
            evidence.append_evidence(db, "olay", payload)
        sonra = db.execute("SELECT COUNT(*) c FROM evidence_ledger").fetchone()["c"]
        assert (once, sonra) == (0, 0)
        assert evidence.verify_chain(db) == (True, 0)

    def test_red_sonrasi_gecerli_payload_yazilabilir(self, db):
        """Dal: red durumu bulaatici degildir — ayni baglantida gecerli payload
        sonrasinda normal sekilde zincirlenir (ledger kilitlenmez)."""
        with pytest.raises(TypeError):
            evidence.append_evidence(db, "olay", {1: "a"})
        seq = evidence.append_evidence(db, "olay", {"1": "a"})
        assert seq == 1
        assert evidence.verify_chain(db) == (True, 1)


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

    def test_sabit_olmayan_payload_hash_kirmizi(self, db):
        """SW-EVID-2 (DUZELTILDI): 2. satirin payload_hash'i 'sabit-olmayan' —
        gecerli SHA-256 ozeti DEGIL. Eski verify_chain yalnizca prev baglarini
        saydigi icin (True, 3) donerdi; artik format denetimi var -> (False, 1).
        Icerik dogrulamasi (hash == sha256(payload)) payload'lar tabloda
        saklanmadigi icin HALA imkansizdir — bu dal bunu iddia etmez."""
        evidence.append_evidence(db, "a", {"i": 1})
        dogru = db.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()["payload_hash"]
        # 2. satirin prev_hash'i dogru ama payload_hash'i gercek digest DEGIL
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('b', ? , ?, ?)",
            ("sabit-olmayan", dogru, evidence.UNSIGNED_F0))
        # 3. satir append_evidence ile 2. satirin (sahte) hash'ine baglanir;
        # zincir baglantisi dogal gorse de 2. satirin formati kirmizi
        evidence.append_evidence(db, "c", {"i": 3})
        ok, n = evidence.verify_chain(db)
        assert (ok, n) == (False, 1)

    def test_buyuk_harfli_hex_payload_hash_kirmizi(self, db):
        """Dal (format siniri): 64-hex ama BUYUK harfli -> kanonik digest
        kucuk-hex uretir; fail-closed, kirmizi (sessiz gecis yok)."""
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('x', ?, 'GENESIS', ?)",
            ("A" * 64, evidence.UNSIGNED_F0))
        assert evidence.verify_chain(db) == (False, 0)

    def test_blob_payload_hash_cokmez_kirmizi(self, db):
        """SW-EVID-2 hardening: payload_hash'e BLOB yazilmis bir satir regex'i
        PATLATMAZ — verify_chain (False, k) doner (fail-closed = cokmek degil)."""
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES ('x', ?, 'GENESIS', ?)",
            (b"\x01" * 64, evidence.UNSIGNED_F0))
        assert evidence.verify_chain(db) == (False, 0)


# ================================== verify_chain: imza kolonu sozlesmesi =====
class TestImzaSozlesmesi:
    """SW-EVID-1b: ed25519_sig F0-acik-isareti ya da 64-bayt imza olmali.

    F0'da her satir imzasizdir ama bu ACIK isaretlenir (UNSIGNED_F0). Kolon
    NULL/bos/kisa/metin-lekesi ise 'sessiz imzasizlik'tir: zincir kirmizi olur
    ve (True, N) ile 'saglam gorunmesi' mumkun degildir (fail-closed).
    """

    def _ekle(self, db, sig, event_type="x", h=None, prev="GENESIS"):
        db.execute(
            "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
            " ed25519_sig) VALUES (?, ?, ?, ?)",
            (event_type, h or ("a" * 64), prev, sig))

    def test_f0_acik_isareti_yesil(self, db):
        """Dal (mevcut uretken yol): append_evidence UNSIGNED_F0 koyar ->
        (True, 3); imza-denetimi F0 zincirini KIRMIZIYA CEVIRMEZ."""
        for i in range(3):
            evidence.append_evidence(db, "olay", {"i": i})
        assert evidence.verify_chain(db) == (True, 3)

    def test_gercek_64bayt_imza_yesil(self, db):
        """Dal: F2'de kolon 64-bayt Ed25519 imzasi ile dolar -> kabul."""
        evidence.append_evidence(db, "a", {"i": 1})
        h = db.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()["payload_hash"]
        self._ekle(db, b"\x7f" * 64, "b", "b" * 64, prev=h)
        assert evidence.verify_chain(db) == (True, 2)

    def test_bos_imza_blob_kirmizi(self, db):
        """Dal: bos BLOB = imzasizlik aciklanmadi -> (False, 0)."""
        self._ekle(db, b"")
        assert evidence.verify_chain(db) == (False, 0)

    def test_kisa_imza_blob_kirmizi(self, db):
        """Dal: 32-bayt (yarim) imza Ed25519 sozlesmesine uymaz -> kirmizi."""
        self._ekle(db, b"\x01" * 32)
        assert evidence.verify_chain(db) == (False, 0)

    def test_uzun_imza_blob_kirmizi(self, db):
        """Dal: 65-bayt blob da sozlesme disi (tam 64 bayt sart)."""
        self._ekle(db, b"\x01" * 65)
        assert evidence.verify_chain(db) == (False, 0)

    def test_metin_lekesi_imza_kirmizi_cokmez(self, db):
        """Dal hardening: kolona TEXT yazilmis 'F0-UNSIGNED-F2-PENDING' LEKESi
        bytes() ile cozulamaz -> verify_chain PATLAMAZ, kirmizi doner."""
        self._ekle(db, "F0-UNSIGNED-F2-PENDING")
        assert evidence.verify_chain(db) == (False, 0)

    def test_sessiz_imzasiz_satir_ikinci_satirda_yakalanir(self, db):
        """Dal: kirilma konumu korunur — 1. satir gecerli, 2. satirin imzasi
        bozuk -> (False, 1) (dogrulanan satir sayisi)."""
        evidence.append_evidence(db, "a", {"i": 1})
        h = db.execute(
            "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()["payload_hash"]
        self._ekle(db, b"eksik", "b", "b" * 64, prev=h)
        assert evidence.verify_chain(db) == (False, 1)

    def test_imza_kontrolu_prev_kontrolunden_once_gelir(self, db):
        """Dal: hem imzasi hem bagi bozuk olan satir yine (False, k) — hangi
        denetimin one gectigi sonuc acisindan ayni (kirmizi), konum ayni."""
        evidence.append_evidence(db, "a", {"i": 1})
        self._ekle(db, b"bozuk", "b", "b" * 64, prev="YANLIS-BAG")
        assert evidence.verify_chain(db) == (False, 1)


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
