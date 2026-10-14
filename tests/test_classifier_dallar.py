"""test_classifier_dallar.py — swarmax/metrics/classifier.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/metrics/classifier.py, 78 satir) — public API:
  MAST_FAMILIES        -> dict[sinif -> MAST ailesi] (11 anahtar)      (L15)
  KNOWN_CLASSES        -> frozenset(MAST_FAMILIES) - {"unknown"} (10) (L28)
  CLASS_TRIGGERS       -> {"loop": "loop>=2", "unknown": "new_class_seen"} (L31)
  PRESEEN_CLASSES      -> {"tool_fail","parse","timeout","auth"}      (L36)
  Classifier(seen)     -> dataclass; seen: set[str]                    (L39)
  Classifier.classify(raw_error, *, loop_detected=False) -> str       (L44)
  Classifier.observe(error_class) -> bool                              (L71)

DAL HARITASI:
  classify (L44-69):
    D1  loop_detected=True kisa-devresi -> "loop" (ham hatayi incelemeden)
    D2  loop_detected=True + raw_error=None -> yine "loop" (loop > None)
    D3  raw_error=None -> "" (basari: hata sinifi yok)
    D4  metin kucultme (str(...).lower()) — buyuk/kucuk duyarsizlik
    D5  "schema drift"/"schema_drift" -> "schema_drift"
    D6  "partial response"/"truncated" -> "partial_response"
    D7  "timeout"/"timed out" -> "timeout"
    D8  "auth"/"401"/"403"/"permission" -> "auth"
    D9  "parse"/"json"/"schema" -> "parse"
    D10 "tool"/"api"/"500"/"429" -> "tool_fail"
    D11 "verify"/"validation"/"expected" -> "verification_fail"
    D12 "mismatch"/"protocol"/"handoff" -> "interagent_mismatch"
    D13 "ambiguous"/"spec"/"unclear" -> "spec_ambiguity"
    D14 tutar (fallback) -> "unknown"
    D15 oncelik siralamasi: ilk eslesen dal kazanir (D5..D13 sira)
    D16 istisna/nesne -> str() donusumu (string olmayan raw_error)
  observe (L71-77):
    D17 ilk-gorus -> True + seen'e ekle
    D18 tekrar -> False + seen degismez
    D19 "" (classify(None) basari cikisi) observe edilebilir
    D20 "unknown" sentinel ilk-gorus olarak True doner

BULGU-1 (production'a DOKUNULMADI — gerceklik test dosyasinda belgelendi):
  DAL-ONCELIgi CARKISMASI: classify dallari sabit sirada calisir; bir metinde
  birden fazla sinyal varsa SADECE ilk eslesen doner, geri kalan kaybolur:
    "timed out api tool 500" -> "timeout"  (api/tool/500 sinyalleri kaybolur)
    "verify tool output"     -> "tool_fail" (verification sinyali kaybolur)
    "403 permission json"    -> "auth"      (json sinyali kaybolur)
  Sonuc: zengin hata metinleri tek-boyutlu sinifa indirgenir; eszamanli
  (örn. timeout + tool hatasi) patolojiler ayristirilamaz (D15).

BULGU-2 (tokenizasyon YOK — alt-dize yanlis-pozitifleri):
  eslesme ham alt-dize uzerinden yapilir (D5..D13), kelime sinirlari yok:
    "author"      -> "auth"          ("auth" ⊂ "author")
    "sparse"      -> "parse"         ("parse" ⊂ "sparse")
    "rapid"       -> "tool_fail"     ("api" ⊂ "rapid")
    "specific"    -> "spec_ambiguity" ("spec" ⊂ "specific")
    "speculative" -> "spec_ambiguity"
  Önem: "author"-gibi masum metinler auth sinifina yanlis yonlendirilir;
  siniflandirma dilbilimsel degil leksikiktir.

BULGU-3 (sentinel izolasyonu):
  "unknown" KNOWN_CLASSES'in DISINDA (frozenset - {"unknown"}); degeri
  MAST_FAMILIES["unknown"] == "(sentinel)". Bilinen sinif tam kumesi 10;
  new_class_seen tetikleyicisi (CLASS_TRIGGERS) unknown + bilinmeyen-imza
  icin ayristirilmistir. MAST families siralamasi: bilinen 10 sinifin 7'si
  gercek MAST ailesine, 4'u "(mechanical-operational)" etiketine gider.

BULGU-4 (observe dogrulamasi YOK):
  observe() gelen sinif adinin taxonomy'de olup olmadigini DENETLEMEZ —
  observe("bogus_sinif") -> True ve seen setine habis eklenir. Ayrica
  classify(None) basari cikisi "" (D19) observe ile first-seen olarak True
  doner; basarili cagrimlar new_class_seen tetikleyicisini bulandirabilir.

BULGU-5 (loop_detected mutlak oncelik):
  loop_detected=True, ham hatayi hic incelemeden "loop" doner (D1/D2) —
 classify("timeout") ile classify(None) ayirdedilemez. Kasitli kisa-devre
  (§3.2-3) ama ayni cagrida hem loop hem baska bir patoloji varsa bilgi
  kaybolur.

Kural-1: SADECE yeni test dosyasi (bu dosya). Kural-4: SAF-BELLEK —
ag/RPC/subprocess/socket YOK; tum durumlar saf nesne graflariyla kurulur.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.metrics import classifier as clf  # noqa: E402

# ============================================================ MODUL SABITLERI
class TestModulSabitleri:
    """MAST_FAMILIES / KNOWN_CLASSES / CLASS_TRIGGERS / PRESEEN_CLASSES sabit dallari."""

    def test_bilinen_sinif_tam_kumesi_10_ve_unknown_dislanmis(self):
        """Dal: KNOWN_CLASSES = frozenset(MAST_FAMILIES) - {"unknown"} (L28)."""
        assert len(clf.KNOWN_CLASSES) == 10
        assert "unknown" not in clf.KNOWN_CLASSES
        assert clf.KNOWN_CLASSES | {"unknown"} == set(clf.MAST_FAMILIES)

    @pytest.mark.parametrize("sinif, aile", sorted(clf.MAST_FAMILIES.items()))
    def test_mast_families_degerleri_bos_degil(self, sinif, aile):
        """Dal: her sinif (unknown dahil) bos-olmayan bir aile etiketine haritali (L15-27)."""
        assert isinstance(aile, str) and aile
        assert sinif in clf.MAST_FAMILIES

    @pytest.mark.parametrize("sinif", sorted(clf.KNOWN_CLASSES))
    def test_bilinen_siniflar_gosterim_degeri(self, sinif):
        """Dal: bilinen her sinif MAST_FAMILIES'te haritali (KNOWN ⊆ MAST keys, L28)."""
        assert sinif in clf.MAST_FAMILIES

    def test_karisik_isletim_siniflari_etiketi(self):
        """Dal: 4 mekanik-isletim sinifi ortak etikete gider (L19-22)."""
        mekanik = {"tool_fail", "parse", "timeout", "auth"}
        for sinif in mekanik:
            assert clf.MAST_FAMILIES[sinif].startswith("(mechanical-operational)")

    def test_chaos_siniflari_reliabilitybench_etiketi(self):
        """Dal: ReliabilityBench chaos siniflari ayri etikete gider (L23-24)."""
        assert "ReliabilityBench" in clf.MAST_FAMILIES["schema_drift"]
        assert "ReliabilityBench" in clf.MAST_FAMILIES["partial_response"]

    def test_sentinel_ve_circulation_etiketleri(self):
        """Dal: unknown sentinel + loop circulation etiketleri (L25-26)."""
        assert clf.MAST_FAMILIES["unknown"] == "(sentinel)"
        assert "circulation" in clf.MAST_FAMILIES["loop"]

    def test_class_triggers_anahtar_ve_degerleri(self):
        """Dal: CLASS_TRIGGERS yalnizca loop+unknown tetikleyiclerini tasiyor (L31)."""
        assert set(clf.CLASS_TRIGGERS) == {"loop", "unknown"}
        assert clf.CLASS_TRIGGERS == {"loop": "loop>=2", "unknown": "new_class_seen"}
        for anahtar in clf.CLASS_TRIGGERS:
            assert anahtar in clf.MAST_FAMILIES

    def test_preseen_classes_mekanik_taban(self):
        """Dal: PRESEEN_CLASSES bilinen mekanik siniflarin tam kumesi (L36)."""
        assert clf.PRESEEN_CLASSES == {"tool_fail", "parse", "timeout", "auth"}
        assert clf.PRESEEN_CLASSES <= clf.KNOWN_CLASSES

    def test_preseen_chaos_siniflarini_icermiyor(self):
        """Dal: chaos/MAST-aile siniflari onboarding oncesi gorulmus sayilmaz (L34-36)."""
        for sinif in ("schema_drift", "partial_response", "loop",
                      "verification_fail", "interagent_mismatch", "spec_ambiguity"):
            assert sinif not in clf.PRESEEN_CLASSES

    @pytest.mark.parametrize("sinif", sorted(clf.KNOWN_CLASSES))
    def test_bilinen_siniflar_preseen_degilse_gorus_sayilir(self, sinif):
        """Dal: PRESEEN disindaki bilinen sinif new_class_seen icin aday (L31/L36)."""
        if sinif in clf.PRESEEN_CLASSES:
            assert clf.Classifier().observe(sinif) is True  # yine de ilk-gorus (preseen dis seeding caller'da)
        else:
            assert clf.Classifier().observe(sinif) is True


# ============================================================ classify eslemesi
class TestClassifyEslemesi:
    """classify ham-hata -> sinif esleme dallari (D3-D14)."""

    @pytest.mark.parametrize("ham, beklenen", [
        ("schema drift: unexpected field", "schema_drift"),       # D5 "schema drift"
        ("schema_drift in envelope", "schema_drift"),             # D5 "schema_drift"
        ("partial response: body cut", "partial_response"),       # D6 "partial response"
        ("response truncated at 4KB", "partial_response"),        # D6 "truncated"
        ("request timeout after 30s", "timeout"),                 # D7 "timeout"
        ("call timed out waiting peer", "timeout"),               # D7 "timed out"
        ("auth header missing", "auth"),                          # D8 "auth"
        ("HTTP 401 unauthorized", "auth"),                        # D8 "401"
        ("HTTP 403 forbidden", "auth"),                           # D8 "403"
        ("permission denied by policy", "auth"),                  # D8 "permission"
        ("json parse error at line 3", "parse"),                  # D9 "parse"/"json"
        ("invalid schema for payload", "parse"),                  # D9 "schema"
        ("tool execution failed", "tool_fail"),                   # D10 "tool"
        ("api gateway error", "tool_fail"),                       # D10 "api"
        ("HTTP 500 internal error", "tool_fail"),                 # D10 "500"
        ("HTTP 429 too many requests", "tool_fail"),              # D10 "429"
        ("could not verify checkpoint", "verification_fail"),     # D11 "verify"
        ("validation rejected rows", "verification_fail"),        # D11 "validation"
        ("result differs from expected", "verification_fail"),    # D11 "expected"
        ("handoff mismatch between agents", "interagent_mismatch"),  # D12 "mismatch"
        ("protocol violation in envelope", "interagent_mismatch"),   # D12 "protocol"
        ("handoff to next stage failed", "interagent_mismatch"),     # D12 "handoff"
        ("ambiguous requirement wording", "spec_ambiguity"),      # D13 "ambiguous"
        ("spec missing deadline", "spec_ambiguity"),              # D13 "spec"
        ("unclear acceptance criteria", "spec_ambiguity"),        # D13 "unclear"
        ("???", "unknown"),                                       # D14 fallback
        ("", "unknown"),                                          # D14 bos metin
    ])
    def test_bilinen_imzalar_sinif_donuyor(self, ham, beklenen):
        """Dal: bilinen her imza karsilik gelen sinifa doner (D5-D14)."""
        assert clf.Classifier().classify(ham) == beklenen

    @pytest.mark.parametrize("ham, beklenen", [
        ("SCHEMA DRIFT detected", "schema_drift"),       # D4 buyuk harf
        ("Request TIMEOUT after 30s", "timeout"),        # D4
        ("HTTP 401 UNAUTHORIZED", "auth"),               # D4 + D8 sayi
        ("TIMED OUT waiting peer", "timeout"),           # D4 + D7
        ("VERIFY checkpoint FAILED", "verification_fail"),  # D4
        ("MixedCase Schema Drift", "schema_drift"),      # D4 yarim-buyuk
        ("  TiMeD oUt  ", "timeout"),                    # D4 karisik + bosluk
    ])
    def test_buyuk_kucuk_harf_duyarsiz(self, ham, beklenen):
        """Dal: str(...).lower() ile ASCII buyuk/kucuk duyarsiz esleme (L50)."""
        assert clf.Classifier().classify(ham) == beklenen

    @pytest.mark.parametrize("istisna, beklenen", [
        (ValueError("connection timeout"), "timeout"),          # D16 istisna -> str
        (RuntimeError("403 forbidden gate"), "auth"),           # D16
        (KeyError("schema_drift"), "schema_drift"),             # D16 KeyError "schemadrift"?
        (ValueError("handoff mismatch on stage 2"), "interagent_mismatch"),
        (Exception("???"), "unknown"),                          # D16 + D14
    ])
    def test_istisna_nesnesi_str_donusumu(self, istisna, beklenen):
        """Dal: string olmayan raw_error str() ile metne donusturulur (L50, D16)."""
        assert clf.Classifier().classify(istisna) == beklenen

    @pytest.mark.parametrize("nesne, beklenen", [
        (42, "unknown"),                    # D16 sayi -> bilinmeyen
        (3.14, "unknown"),                  # D16-ondalik
        (True, "unknown"),                  # D16 bool ("true" eslesmiyor)
        (None, ""),                         # D3 None -> basarisi
        (["parse error at line"], "parse"), # D16 liste str() -> "['parse error...']"
        (("timed out",), "timeout"),        # D16 demet
        ({"mesaj": "json hata"}, "parse"),     # D16 dict str() -> "json" kelimesi parse dalini yakalar
    ])
    def test_str_olmayan_tipler(self, nesne, beklenen):
        """Dal: herhangi Python nesnesi str() cevrilip siniflandirilir (L50, D16)."""
        assert clf.Classifier().classify(nesne) == beklenen

    @pytest.mark.parametrize("imza", [
        "request timeout after 30s", "HTTP 401 unauthorized", "json parse error",
        "schema drift field", "truncated body", "tool failed", "verify result",
        "mismatch agents", "unclear spec", "random chatter",
    ])
    def test_cikti_sozlesmesi_gecerli_sinif(self, imza):
        """Dal: classify cikti daima MAST_FAMILIES anahtari veya "" (sozlesme)."""
        sonuc = clf.Classifier().classify(imza)
        assert sonuc == "" or sonuc in clf.MAST_FAMILIES


# ============================================================ oncelik siralamasi
class TestOncelikSiralamasi:
    """classify dal-oncelik siralamasi: ilk eslesen kazanir (D15) + BULGU-1."""

    def test_schema_drift_parse_oncesinde(self):
        """Dal D15: "schema drift" metni "json"/"schema" kelimelerini icerir ama schema_drift kazanir."""
        assert clf.Classifier().classify("schema drift in json schema") == "schema_drift"

    def test_partial_response_parse_oncesinde(self):
        """Dal D15: "partial response ... json" partial_response kazanir (D6 > D9)."""
        assert clf.Classifier().classify("partial response: json body truncated") == "partial_response"

    def test_timeout_tool_fail_oncesinde(self):
        """Dal D15 + BULGU-1: "timed out" api/tool/500 sinyallerini ezer (D7 > D10)."""
        assert clf.Classifier().classify("timed out calling api tool 500") == "timeout"

    def test_auth_tool_fail_oncesinde(self):
        """Dal D15 + BULGU-1: auth "tool"/"api" sinyallerini ezer (D8 > D10)."""
        assert clf.Classifier().classify("403 permission denied on tool api call") == "auth"

    def test_auth_parse_oncesinde(self):
        """Dal D15 + BULGU-1: auth json/parse sinyalini ezer (D8 > D9)."""
        assert clf.Classifier().classify("auth rejected json payload parse") == "auth"

    def test_timeout_auth_oncesinde(self):
        """Dal D15: timeout auth'tan once (D7 > D8)."""
        assert clf.Classifier().classify("request timed out: re-auth needed") == "timeout"

    def test_parse_tool_fail_oncesinde(self):
        """Dal D15: parse "tool"/"api" sinyallerini ezer (D9 > D10)."""
        assert clf.Classifier().classify("json parse error in tool api layer") == "parse"

    def test_tool_fail_verification_oncesinde(self):
        """Dal D15 + BULGU-1: "verify ... tool" -> tool_fail kazanir (D10 > D11)."""
        assert clf.Classifier().classify("verify tool output failed") == "tool_fail"

    def test_verification_spec_ambiguity_oncesinde(self):
        """Dal D15: verification "spec"/"unclear" sinyallerini ezer (D11 > D13)."""
        assert clf.Classifier().classify("validation rejected unclear spec") == "verification_fail"

    def test_mismatch_spec_ambiguity_oncesinde(self):
        """Dal D15: interagent_mismatch "spec"/"unclear" sinyallerini ezer (D12 > D13)."""
        assert clf.Classifier().classify("protocol mismatch on unclear spec") == "interagent_mismatch"

    def test_verification_mismatch_oncesinde(self):
        """Dal D15: verification mismatch'tan once (D11 > D12)."""
        assert clf.Classifier().classify("validation mismatch on handoff") == "verification_fail"


# ============================================================ alt-dize yanlis-pozitif
class TestAltDizeYanlisPozitif:
    """Tokenizasyon yok — alt-dize yanlis-pozitifleri (BULGU-2)."""

    @pytest.mark.parametrize("masum, yanlis_sinif", [
        ("author of the module", "auth"),        # "auth" ⊂ "author"
        ("sparse data layout", "parse"),         # "parse" ⊂ "sparse"
        ("rapid response cycle", "tool_fail"),   # "api" ⊂ "rapid"
        ("specific guidance needed", "spec_ambiguity"),  # "spec" ⊂ "specific"
        ("speculative design", "spec_ambiguity"),        # "spec" ⊂ "speculative"
    ])
    def test_masum_metinler_yanlis_sinifa_yonelendirilir(self, masum, yanlis_sinif):
        """Dal + BULGU-2: kelime siniri yok; alt-dize eslesmesi masum metinleri
        hata sinifina yonlendirir (ham substring dal D5..D13)."""
        assert clf.Classifier().classify(masum) == yanlis_sinif

    @pytest.mark.parametrize("masum", [
        "author", "sparse", "rapid", "specific", "speculative",
    ])
    def test_masum_tek_kelime_hata_sinifi_uretir(self, masum):
        """Dal + BULGU-2: hata icermeyen tek kelime bile hata sinifi doner (D14 dis)."""
        sonuc = clf.Classifier().classify(masum)
        assert sonuc != "unknown"  # erken dal yakaladi; "unknown" fallback'e hic ulasmadi


# ============================================================ None + loop kisa-devre
class TestNoneVeLoopKisaDevre:
    """loop_detected kisa-devresi + None basari dali (D1-D3) + BULGU-5."""

    def test_none_basari_bos_sinif(self):
        """Dal D3: raw_error=None -> "" (basari: hata sinifi yok)."""
        assert clf.Classifier().classify(None) == ""

    def test_loop_detected_none_uzerinde_kazanir(self):
        """Dal D2: loop_detected=True + raw_error=None -> yine "loop" (loop > None)."""
        assert clf.Classifier().classify(None, loop_detected=True) == "loop"

    def test_loop_detected_gercek_hatayi_gecersiz_kilar(self):
        """Dal D1 + BULGU-5: loop_detected=True "timeout" ham hatasini ezer."""
        assert clf.Classifier().classify("request timeout after 30s", loop_detected=True) == "loop"

    def test_loop_detected_bilinmeyen_hatayi_gecersiz_kilar(self):
        """Dal D1: loop_detected=True bilinmeyen imzayi da ezer ("loop" > "unknown")."""
        assert clf.Classifier().classify("???", loop_detected=True) == "loop"

    def test_loop_detected_false_normal_yolu_izler(self):
        """Dal D1 inkari: loop_detected=False (varsayilan) normal eslemeyi yapar."""
        assert clf.Classifier().classify("request timeout", loop_detected=False) == "timeout"

    def test_classify_seen_setine_dokunmaz(self):
        """Dal: classify() yan etkisizdir — seen setini asla degistirmez."""
        c = clf.Classifier()
        c.classify("timeout"), c.classify(None), c.classify("???", loop_detected=True)
        assert c.seen == set()


# ============================================================ observe
class TestObserve:
    """observe() ilk-gorus/tekrar dallari (D17-D20) + BULGU-4."""

    def test_ilk_gorus_true_ve_seen_ekler(self):
        """Dal D17: ilk-gorus True doner, sinifi seen setine ekler."""
        c = clf.Classifier()
        assert c.observe("loop") is True
        assert c.seen == {"loop"}

    @pytest.mark.parametrize("sinif", [
        "loop", "unknown", "schema_drift", "partial_response", "timeout",
        "auth", "parse", "tool_fail", "verification_fail",
        "interagent_mismatch", "spec_ambiguity",
    ])
    def test_her_sinif_ilk_gorus_true(self, sinif):
        """Dal D17: bilinen/tum siniflar ilk-gorus olarak True doner."""
        assert clf.Classifier().observe(sinif) is True

    def test_tekrar_false(self):
        """Dal D18: ayni sinifin ikinci gozlemi False doner."""
        c = clf.Classifier()
        c.observe("timeout")
        assert c.observe("timeout") is False

    def test_tekrar_false_seen_degismez(self):
        """Dal D18: False donusunde seen setine ekleme yapilmaz (idempotent)."""
        c = clf.Classifier()
        c.observe("timeout")
        once = set(c.seen)
        assert c.observe("timeout") is False
        assert c.seen == once

    def test_unknown_sentinel_ilk_gorus_true(self):
        """Dal D20: "unknown" sentinel ilk-gorus olarak True doner (§3.1)."""
        c = clf.Classifier()
        assert c.observe("unknown") is True
        assert c.observe("unknown") is False

    def test_bos_string_basari_sinifi_observe_edilebilir(self):
        """Dal D19: classify(None) cikisi "" observe ile first-seen True doner (BULGU-4)."""
        c = clf.Classifier()
        assert c.observe("") is True
        assert c.observe("") is False

    def test_taxonomy_disinda_sinif_habis_eklenir(self):
        """BULGU-4: observe() sinif adini dogrulamaz — "bogus" seen'e habis eklenir."""
        c = clf.Classifier()
        assert c.observe("bogus_sinif") is True
        assert "bogus_sinif" in c.seen
        assert c.observe("bogus_sinif") is False

    def test_farkli_siniflar_birikiyor(self):
        """Dal D17: her yeni sinif first-seen True; seen birikir."""
        c = clf.Classifier()
        assert c.observe("timeout") is True
        assert c.observe("auth") is True
        assert c.observe("timeout") is False
        assert c.seen == {"timeout", "auth"}

    def test_preseen_seeding_sonu_novel_sinif_tetikler(self):
        """Dal D17 + §3.1: PRESEEN seeding sonrasi preseen sinif False,
        novel chaos sinifi True (new_class_seen disiplini)."""
        c = clf.Classifier()
        c.seen |= clf.PRESEEN_CLASSES
        assert c.observe("timeout") is False          # preseen mekanik sinif
        assert c.observe("schema_drift") is True      # novel chaos sinifi
        assert c.observe("schema_drift") is False     # artik goruldu

    def test_default_seen_bos_settir(self):
        """Dal: dataclass default_factory bos seen (L42)."""
        assert clf.Classifier().seen == set()
        # iki ayri ornek ayakta kalmali (default_factory paylasilmiyor)
        a, b = clf.Classifier(), clf.Classifier()
        a.observe("loop")
        assert b.seen == set()

    def test_observe_seen_uzerinde_true_dondukten_sonra_degismez(self):
        """Dal D18: False donusu seen'i genisletmez (zaten iceriyordu)."""
        c = clf.Classifier()
        c.observe("loop")
        assert c.observe("loop") is False
        assert c.seen == {"loop"}


# ============================================================ siniflandirma + tetikler
class TestTetikSozlesmesi:
    """CLASS_TRIGGERS ile classify/observe isbirligi (§3.1 + §4.2)."""

    def test_loop_sinifi_tetikleyici_anahtari(self):
        """Dal: "loop" sinifi CLASS_TRIGGERS icinde ve loop>=2 tetikleyicisi tasiyor."""
        assert "loop" in clf.CLASS_TRIGGERS
        assert clf.CLASS_TRIGGERS["loop"] == "loop>=2"

    def test_loop_tetikleyici_loop_sinifi_ile_tutali(self):
        """Dal: loop_detected True -> "loop" doner, tetikleyici anahtar MAST icinde."""
        assert clf.Classifier().classify("her sey", loop_detected=True) == "loop"
        assert clf.Classifier().observe("loop") is True

    def test_unknown_tetikleyici_sentinel_ile_tutali(self):
        """Dal: new_class_seen tetikleyicisi unknown sentinel uzerinden calisir."""
        c = clf.Classifier()
        novel = c.classify("???")
        assert novel == "unknown"
        assert c.observe(novel) is True      # new_class_seen ilk keza
        assert c.observe(novel) is False

    def test_yeni_bilinen_sinif_new_class_seen_tetikler(self):
        """Dal: bilinen ama bu-agent-icin-yeni sinif observe ile True doner (§3.1)."""
        c = clf.Classifier()
        seen_once = c.observe("partial_response")
        assert seen_once is True
        assert c.observe("loop") is True
