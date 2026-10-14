"""test_loop_breaker_dallar.py — swarmax/metrics/loop_breaker.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/metrics/loop_breaker.py, 45 satir) — public API:
  KILL_CIRCUIT_OPEN       -> "KILL_CIRCUIT_OPEN" (§3.2-3 karantina durumu)  (L16)
  LOOP_RUN_THRESHOLD      -> 3 (ardisik ayni-hash esigi)                    (L17)
  normalize_arguments(a)  -> kanonik JSON: sort_keys + kompakt separators   (L20)
  call_hash(tool, args)   -> sha256(tool_name || normalize_arguments)) hex  (L25)
  LoopBreaker             -> dataclass: hashes list, opened bool            (L29)
  LoopBreaker.feed(tool, args) -> bool — tam acildiginda True              (L35)

DAL HARITASI:
  normalize_arguments (L20-22):
    D1  dict -> sort_keys ile sirali + separators=(",",":") kompakt cikti
    D2  anahtar sirasi bagimsizligi (icice dict'lerde sort recursive)
    D3  dict-disi tipler: None/True/sayi/str/list JSON skaleri olarak
    D4  ensure_ascii default -> latin-disi karakterler \\uXXXX kacisi
    D5  tuple ile list ayni JSON dizisine serilesir (tip kaybi)
    D6  int anahtar str'ye zorlanir ({1:'a'} == {'1':'a'})
    D7  bool anahtar str'ye zorlanir ({True:'a'} == {'true':'a'})
    D8  int vs float ayrimi korunur (1 != 1.0 serilesimi)
    D9  karisik anahtar turleri + sort_keys -> TypeError (kirilganlik)
    D10 determinizm: ayni girdi ayni cikti
  call_hash (L25-26):
    D11 sha256 hex (64 karakter), encode("utf-8")
    D12 determinizm (D10 + hashing)
    D13 tool_name degisince hash degisir
    D14 arguments degisince hash degisir
    D15 tool_name || normalize(arguments) — AYRAC (delimiter) YOK
    D16 tip carpismasi (tuple/list, int/bool anahtar) hash'a tasinir
  LoopBreaker.feed (L35-45):
    D17 opened=True ise kisa-devre: hemen True, hash EKLENMEZ
    D18 acilista feed sonucu == opened (her cagrida senkron)
    D19 1 veya 2 cagri: len < LOOP_RUN_THRESHOLD -> False
    D20 3. ayni cagri: son-3 pencere tamami ayni -> True (esik tam 3)
    D21 farkli cagri run'i kirar (son-3 pencerede farkli hash)
    D22 A-A-B-A-A-A: 6. cagri son-3 penceresi ayni -> True (pencere konumsal)
    D23 kumulatif sayim YOK: A-B-A-A toplam 3A ama peaked degil -> False
    D24 anahtar sirasi farkli args ayni hash -> run devam eder (D2+D20)
    D25 tool_name farkliysa run kirilir (D13)

BULGU-1 (production'a DOKUNULMADI — gerceklik test dosyasinda belgelendi):
  AYRACSIZ BIRLESTIRME Carpismasi (D15): call_hash tool_name ile
  normalize(arguments) arasinda HIC ayraç koymaz — cikti f"{tool}{json}":
    call_hash("x", 12)  == call_hash("x1", 2)  == call_hash("x12", ...)
    hepsi sha256("x12") — cok-basamakli sayisal argumanlar araç adi
  sinirini belirsizlestirir. Önem: ayyni fingerprint farkli (tool,args)
  ciftlerini isaret edebilir; kanit dosyasi (hash) tek-tarafli cozulemez.

BULGU-2 (KOMULSATIF-PENCERE, sayim YOK — D23): feed "son 3 hash ayni mi"
  pencere testi yapar (hashes[-1]==hashes[-2]==hashes[-3]), ardisik-ayni
  SAYISINI takip ETMEZ: A,B,A,A cagri dizisinde toplam 3 ayni-A cagri
  olmasina ragmen breaker ACILMAZ (False). Ya A,B,A,A,A? — 4. A'da
  pencere [B,A,A] esit degil; 5. A'da [A,A,A] -> Acilir. Yani 'run'un
  kirilmasi bütünüyle unutulmaz; son-3 penceresinde kalmali.

BULGU-3 (KANIT KAYBI acildiktan sonra — D17): opened=True olduktan sonra
  feed cagrisi kisa-devreye girer ve gelen cagridaki hash'i hashes
  listesine EKLEMEZ. Acilma anindan sonraki çağrilarin (yani döngünün
  devamı) fingerprintsi kanit zincirinde YOK — post-open patoloji
  geri-izlenemez.

BULGU-4 (tip carpismasi D5-D7): SHA-256 oncesinde Python tipi
  korunmaz: {"a": (1,2)} ile {"a": [1,2]}, {1:"a"} ile {"1":"a"},
  {True:"a"} ile {"true":"a"} AYNI normalize cikti -> ayni hash.
  Buna karsilik 1 ile 1.0 FARKLI serilesim (D8) — ayrim korunur.

BULGU-5 (unicode kacisi D4): json.dumps ensure_ascii=True varsayilan —
  Türkçe 'ğ' → "\\u011f". Deterministik ve hash-stabil olmakla birlikte
  insan-okunabilir degil; metinsel argumanlarinAlfabe bilgisi kaybolur.

BULGU-6 (KARISIK ANAHTAR TypeError — D9): normalize_arguments karisik
  türde dict anahtarlariyla (int + str) sort_keys yaparken TypeError
  firlatir: '<' not supported between 'str' and 'int'. feed() bunu
  yakaLAMAZ — guard plane bool yerine istisna alir (Python 3.14).

Kural-1: SADECE yeni test dosyasi (bu dosya). Kural-4: SAF-BELLEK —
ag/RPC/subprocess/socket YOK; tüm durumlar saf nesne graflariyla kurulur.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.metrics import loop_breaker as lb  # noqa: E402

# ==================================================== normalize_arguments
class TestNormalizeArguments:
    """normalize_arguments kanonik-JSON dallari (D1-D10)."""

    def test_dict_sirali_ve_kompakt(self):
        """Dal D1: dict sort_keys ile sirali, separators kompakt."""
        assert lb.normalize_arguments({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    @pytest.mark.parametrize("once, sonda", [
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
        ({"z": 0, "a": {"y": 1, "x": 2}}, {"a": {"x": 2, "y": 1}, "z": 0}),
        ({}, {}),
    ])
    def test_anahtar_sira_bagimsizligi(self, once, sonda):
        """Dal D2: anahtar sirasi ciktiyi degistirmez (icice dict'lerde recursive)."""
        assert lb.normalize_arguments(once) == lb.normalize_arguments(sonda)

    def test_icice_dict_recursive_sirali(self):
        """Dal D2: sort_keys icice dict'lere de uygulanir."""
        sonuc = lb.normalize_arguments({"z": {"y": 1, "x": 2}, "a": 1})
        assert sonuc == '{"a":1,"z":{"x":2,"y":1}}'

    @pytest.mark.parametrize("args, beklenen", [
        (None, "null"),                    # D3 None -> JSON null
        (True, "true"),                    # D3 bool true
        (False, "false"),                  # D3 bool false
        (5, "5"),                          # D3 int
        ("metin", '"metin"'),              # D3 str
        ([1, 2, 3], "[1,2,3]"),            # D3 liste
        ({}, "{}"),                        # D3 bos dict
        ([], "[]"),                        # D3 bos liste
    ])
    def test_dict_disi_tipler_json_skaleri(self, args, beklenen):
        """Dal D3: dict-disi tipler dogrudan JSON skaleri olarak serilesir."""
        assert lb.normalize_arguments(args) == beklenen

    def test_separators_kompakt_bosluk_yok(self):
        """Dal D1: cikti ':' ve ',' sonrasi bosluk icermez (separators=(",",":"))."""
        sonuc = lb.normalize_arguments({"a": 1, "b": 2})
        assert sonuc == '{"a":1,"b":2}'
        assert " " not in sonuc

    def test_unicode_turkce_karakter_kacisi(self):
        """Dal D4 + BULGU-5: ensure_ascii default 'ğ' harfini \\u011f kacisina donusturur."""
        assert lb.normalize_arguments({"k": "ğ"}) == '{"k":"\\u011f"}'
        assert lb.normalize_arguments({"k": "ğ"}) == lb.normalize_arguments({"k": "ğ"})

    def test_tuple_list_carpismasi(self):
        """Dal D5 + BULGU-4: tuple ve list ayni JSON dizisi — tip kaybi."""
        assert lb.normalize_arguments({"a": (1, 2)}) == lb.normalize_arguments({"a": [1, 2]})

    def test_int_anahtar_str_yasinda_carpismasi(self):
        """Dal D6 + BULGU-4: {1:'a'} ile {'1':'a'} AYNI cikti (int anahtar str'ye zorlanir)."""
        assert lb.normalize_arguments({1: "a"}) == lb.normalize_arguments({"1": "a"})

    def test_bool_anahtar_str_yasinda_carpismasi(self):
        """Dal D7 + BULGU-4: {True:'a'} ile {'true':'a'} AYNI cikti."""
        assert lb.normalize_arguments({True: "a"}) == lb.normalize_arguments({"true": "a"})

    def test_int_float_ayrimi_korunur(self):
        """Dal D8: 1 ile 1.0 FARKLI serilesir — tip carpismasi gerceklesmez."""
        assert lb.normalize_arguments(1) != lb.normalize_arguments(1.0)
        assert lb.normalize_arguments({"v": 1}) != lb.normalize_arguments({"v": 1.0})

    def test_karisik_anahtar_turu_typeerror(self):
        """Dal D9 + BULGU-6: int+str karisik anahtar sort_keys ile TypeError firlatir."""
        with pytest.raises(TypeError):
            lb.normalize_arguments({1: "a", "b": 2})

    @pytest.mark.parametrize("args", [
        {"a": 1}, None, True, "x", [1, 2], {"z": {"x": 2, "y": 1}}, 3.14, {},
    ])
    def test_deterministik(self, args):
        """Dal D10: ayni girdi her cagrida ayni cikti."""
        assert lb.normalize_arguments(args) == lb.normalize_arguments(args)


# ==================================================== call_hash
class TestCallHash:
    """call_hash sha256+fingerprint dallari (D11-D16) + BULGU-1."""

    def test_cikti_sha256_hex_64(self):
        """Dal D11: cikti SHA-256 hex — 64 karakter, hex alfebasisi."""
        h = lb.call_hash("tool", {"a": 1})
        assert len(h) == 64
        int(h, 16)

    @pytest.mark.parametrize("tool, args", [
        ("sql_query", {"table": "users"}),
        ("http", None),
        ("notify", "metin"),
        ("sum", [1, 2]),
        ("noop", {}),
    ])
    def test_deterministik(self, tool, args):
        """Dal D12: ayni (tool, args) cifti ayni hash."""
        assert lb.call_hash(tool, args) == lb.call_hash(tool, args)

    def test_tool_name_degisince_hash_degisir(self):
        """Dal D13: tool_name fingerprint'in parçasidir."""
        assert lb.call_hash("t1", {"a": 1}) != lb.call_hash("t2", {"a": 1})

    def test_arguments_degisince_hash_degisir(self):
        """Dal D14: arguments fingerprint'in parçasidir."""
        assert lb.call_hash("t", {"a": 1}) != lb.call_hash("t", {"a": 2})

    @pytest.mark.parametrize("once, sonda", [
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}),
        ({"z": 1, "a": {"y": 2, "x": 3}}, {"a": {"x": 3, "y": 2}, "z": 1}),
    ])
    def test_anahtar_sira_fingerprint_degismez(self, once, sonda):
        """Dal D2+D12: anahtar sirasi farkli args ayni hash (D24 icin temel)."""
        assert lb.call_hash("t", once) == lb.call_hash("t", sonda)

    @pytest.mark.parametrize("ilk, ikinci", [
        (("x", 12), ("x1", 2)),        # BULGU-1: "x"+"12" == "x1"+"2" == "x12"
        (("y", 123), ("y1", 23)),      # "y123" — 3 komponent
        (("y", 123), ("y12", 3)),      # "y123" — baska bolme
        (("z", 45), ("z4", 5)),        # "z45"
    ])
    def test_ayrac_yok_carpismasi(self, ilk, ikinci):
        """Dal D15 + BULGU-1: || birlestirmesinde ayraç yok — farkli ciftler
        ayni fingerprint üretebilir (cok-basamakli sayisal arguman)."""
        assert lb.call_hash(*ilk) == lb.call_hash(*ikinci)

    @pytest.mark.parametrize("args_a, args_b", [
        ({"a": (1, 2)}, {"a": [1, 2]}),  # D5 tuple/list
        ({1: "a"}, {"1": "a"}),          # D6 int anahtar
        ({True: "a"}, {"true": "a"}),    # D7 bool anahtar
    ])
    def test_tip_carpismasi_hash_a_tasinir(self, args_a, args_b):
        """Dal D16 + BULGU-4: tip carpismasi normalize seviyesinden hash'e tasinir."""
        assert lb.call_hash("t", args_a) == lb.call_hash("t", args_b)

    def test_int_float_hash_ayrimi(self):
        """Dal D8+D14: 1 vs 1.0 farkli hash — tip korunmuyor olsa da deger ayrimi var."""
        assert lb.call_hash("t", 1) != lb.call_hash("t", 1.0)

    def test_bos_argument_dict_ve_bos_tool(self):
        """Dal D1+D11: bos dict ve bos tool adi gecerli fingerprint üretir."""
        h = lb.call_hash("", {})
        assert len(h) == 64
        assert lb.call_hash("", {}) == lb.call_hash("", {})


# ==================================================== sabitler
class TestSabitler:
    """KILL_CIRCUIT_OPEN / LOOP_RUN_THRESHOLD sabit dallari (L16-17)."""

    def test_kill_circuit_open_degeri(self):
        """Dal: karantina durum sabiti "KILL_CIRCUIT_OPEN" (§3.2-3)."""
        assert lb.KILL_CIRCUIT_OPEN == "KILL_CIRCUIT_OPEN"

    def test_loop_run_threshold_degeri(self):
        """Dal: ardisik-ayni esigi 3 (§3.2-3)."""
        assert lb.LOOP_RUN_THRESHOLD == 3


# ==================================================== LoopBreaker.feed
class TestFeed:
    """feed() esik/pencere/acilma dallari (D17-D25) + BULGU-2/3."""

    def test_baslangic_durumu_kapali_ve_bos(self):
        """Dal: yeni breaker kapali, hashes bos (L32-33)."""
        b = lb.LoopBreaker()
        assert b.opened is False
        assert b.hashes == []

    @pytest.mark.parametrize("adim", [1, 2])
    def test_esik_alti_cagri_false(self, adim):
        """Dal D19: 1 veya 2 ayni cagri len<THRESHOLD -> False (acilmaz)."""
        b = lb.LoopBreaker()
        for _ in range(adim):
            assert b.feed("t", {"a": 1}) is False
        assert b.opened is False
        assert len(b.hashes) == adim

    def test_ucuncu_ayni_cagri_acar(self):
        """Dal D20: tam 3. ayni cagri breaker'i acar (esik tam 3, sinir degeri)."""
        b = lb.LoopBreaker()
        assert b.feed("t", {"a": 1}) is False
        assert b.feed("t", {"a": 1}) is False
        assert b.feed("t", {"a": 1}) is True
        assert b.opened is True
        assert len(b.hashes) == 3

    def test_esik_tam_3_pencere(self):
        """Dal D20: son-3 pencerenin tamami ayni-oldugunda tam esikte acilir."""
        for kirici in (lb.LoopBreaker(), lb.LoopBreaker()):
            kirici.feed("t", 1); kirici.feed("t", 1)
            assert len(kirici.hashes) == 2
            assert kirici.feed("t", 1) is True
            assert len(kirici.hashes) == lb.LOOP_RUN_THRESHOLD

    def test_farkli_cagri_zinciri_kirar(self):
        """Dal D21: A,A,B,A — 4. cagrida son-3 pencere [A,B,A] esit degil -> False."""
        b = lb.LoopBreaker()
        b.feed("t", {"a": 1}); b.feed("t", {"a": 1})
        assert b.feed("t", {"a": 2}) is False       # run kirildi
        assert b.feed("t", {"a": 1}) is False       # [A,B,A?] — esit degil
        assert b.opened is False

    def test_aabaa_pencere_konumsal(self):
        """Dal D22: A,A,B,A,A 5 cagrida False; 6. A'da son-3 [A,A,A] -> True."""
        b = lb.LoopBreaker()
        assert b.feed("t", 1) is False
        assert b.feed("t", 1) is False
        assert b.feed("t", 2) is False               # B run'i kirar
        assert b.feed("t", 1) is False               # pencere [A,B,A]
        assert b.feed("t", 1) is False               # pencere [B,A,A]
        assert b.feed("t", 1) is True                # pencere [A,A,A]
        assert b.opened is True

    def test_kumulatif_sayim_yok(self):
        """Dal D23 + BULGU-2: A,B,A,A — toplam 3 A ama pekte degil -> False."""
        b = lb.LoopBreaker()
        assert b.feed("t", 1) is False
        assert b.feed("u", 1) is False
        assert b.feed("t", 1) is False
        assert b.feed("t", 1) is False               # son-3 [A,B,A] -> False
        assert b.opened is False

    def test_kumulatif_ayni_run_acilir(self):
        """Dal D20: ayni-run'da 3 ardisik cagri (kumulatif==pencere) -> True."""
        b = lb.LoopBreaker()
        for _ in range(3):
            b.feed("t", 1)
        assert b.opened is True

    @pytest.mark.parametrize("sira", [
        [{"a": 1, "b": 2}, {"b": 2, "a": 1}, {"a": 1, "b": 2}],   # D24: karisik sira
        [{"x": 1}, {"x": 1}, {"x": 1}],                            # ayni sira
    ])
    def test_anahtar_sira_farkli_run_acilir(self, sira):
        """Dal D24: anahtar sirasi farkli args AYNI hash üretir — run devam eder."""
        b = lb.LoopBreaker()
        son = None
        for args in sira:
            son = b.feed("t", args)
        assert son is True
        assert b.opened is True
        assert len(set(b.hashes)) == 1                # uc cagrinin hash'i tek

    def test_farkli_tool_run_kirilir(self):
        """Dal D25: ayni args farkli tool_name — hash farkli -> run kirilir."""
        b = lb.LoopBreaker()
        assert b.feed("t1", {"a": 1}) is False
        assert b.feed("t2", {"a": 1}) is False
        assert b.feed("t1", {"a": 1}) is False        # [t1,t2,t1] esit degil
        assert b.opened is False

    def test_farkli_argumanla_run_kirilir_ve_yeniden_acilir(self):
        """Dal D21+D20: run kirilir, sonra 3 yeni ayni cagri yeniden acar."""
        b = lb.LoopBreaker()
        b.feed("t", 1); b.feed("t", 1)
        assert b.feed("t", 2) is False
        assert b.feed("t", 1) is False
        assert b.feed("t", 1) is False
        assert b.feed("t", 1) is True                 # [A,A,A]

    def test_bos_arguman_dict_run_acilir(self):
        """Dal D3+D20: bos dict argumanla 3 cagri breaker'i acar."""
        b = lb.LoopBreaker()
        b.feed("t", {}); b.feed("t", {})
        assert b.feed("t", {}) is True

    def test_acilan_kirici_acik_kalir_hash_eklemez(self):
        """Dal D17 + BULGU-3: opened=True sonraki feed hemen True doner ve
        gelen cagridaki hash kanit listesine EKLENMEZ."""
        b = lb.LoopBreaker()
        b.feed("t", 1); b.feed("t", 1); b.feed("t", 1)
        kanit_sayisi = len(b.hashes)
        assert b.feed("t", 999) is True               # yeni arguma ragmen
        assert len(b.hashes) == kanit_sayisi          # hash eklenmedi

    def test_acilan_kirici_degisik_tool_da_true(self):
        """Dal D17: opened sonrasi farkli tool_name bile True doner (kisa-devre)."""
        b = lb.LoopBreaker()
        b.feed("t", 1); b.feed("t", 1); b.feed("t", 1)
        assert b.feed("baska_tool", {"baska": 1}) is True
        assert b.opened is True

    def test_feed_sonucu_opened_ile_her_zaman_tutali(self):
        """Dal D18: her feed cagrisinda donus degeri opened bayragiyla senkron."""
        b = lb.LoopBreaker()
        for i in range(5):
            donus = b.feed("t", 1)
            assert donus is b.opened

    def test_uc_kirici_bagimsiz(self):
        """Dal: her LoopBreaker ornegi ayakta kalmali (datafield default_paylasimi yok)."""
        a, b, c = lb.LoopBreaker(), lb.LoopBreaker(), lb.LoopBreaker()
        a.feed("t", 1); a.feed("t", 1); a.feed("t", 1)
        assert a.opened is True
        assert b.opened is False and c.opened is False
        assert b.hashes == [] and c.hashes == []
