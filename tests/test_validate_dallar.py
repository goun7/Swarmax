"""test_validate_dallar.py — swarmax/semconv/validate.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/semconv/validate.py, 89 satir) — public API:
  SemconvReport(ok, checked, unknown, type_mismatches) — dataclass (L20)
    summary() -> "ok=.. checked=.. unknown=N type_mismatches=N" (L27)
  validate_attributes(attributes) -> SemconvReport (L56):
    gen_ai.* -> _expected_type: yoksa unknown, varsa tip-denetim (L61)
    swx.*    -> _expected_type: yoksa unknown, varsa tip-denetim (L71)
    error./otel./service./deployment./k8s./host./telemetry. -> continue (L79)
    digeri   -> unknown (L81)
    alias: int-beklenen-double-gelen => gecersiz sayILMAZ (L69, L77)

DAL HARITASI:
  validate_attributes (basari): pinli her gen_ai*/swx* key correct-tip ->
    ok=True; int-key-float-deger alias'i; str[]-bos-liste (vacuous);
    allowed-prefix'ler tip-denetimsiz gecer; bos-dict -> (True, 0).
  validate_attributes (basarisiz): yanlis-tip -> (expected, actual) tuple;
  bilinmeyen gen_ai./swx. key -> unknown; "gen_ai." tam- stringi -> unknown;
    gen_ai+swx+unknown+aIlanmis karisik girdi; tuple "json" olur; bool<int
    sayilir; None "json" olur.
  SemconvReport: default unknown=[]/type_mismatches={} list-dict
    (her ornekte TAZE); ozdeslik; mutable (frozen degil); summary()
    birebir format.

BULGU-1 (production'a DOKUNULMADI — DAL-KESEN KESIF): "error.type" key'i
  GENAI_ATTRIBUTES kayit defterinde "str" olarak PINLI olmasina ragmen,
  validate_attributes onu "error." onek sinirlamasindan dolayi continue
  ile ATLAR ve HIC tip-denetim yapmaz. Test kaniti:
    validate_attributes({"error.type": 123}) -> ok=True (tip yanlis!).
  Yani pinli kayitla validator DALGASI: registry pinli, validator pasif.
  Onem: error.* attribute'leri her zaman bilincli oIk gecer — production
  DOKUNULMADAN belgelendi.

BULGU-2 (production'a DOKUNULMADI): int-as-double alias'i ASIMETRIK:
    expected="int" & actual="double"  -> gecersiz sayILMAZ (toleransli)
    expected="double" & actual="int"  -> MISMATCH (katiliyor)
  Yani 5.0 max_tokens gecer, 40 temperature degil. Tolerans yalnizca
  yukari-yonde (int -> double yukseltme), asagi-yonde degil. [Testlerde
  her iki yonde de olculdu.]

BULGU-3 (production'a DOKUNULMADI): _actual_type bool'i ONCE kontrol
  ettiginden, bool degeri int-beklenen key'e "bool" verir ve MIS-match
  olur (True bir int degildir validator gozunde). Kullanici True'yu 1
  olarak gecemez. bool<->int ozdesligi bilincli reddedilir.

BULGU-4 (production'a DOKUNULMADI): bos-liste [] -> "str[]" (vacuous
  truth: all(...) bos listede True). Kullanici [] gecerli str[] sayar;
  boş liste ile None farkli (None -> "json"). Ayrica tuple ("a","b")
  -> "json" — str[] beklense bile tuple KABUL edilmez (sadece list).

BULGU-5 (production'a DOKUNULMADI): SemconvReport plain (frozen-olmayan)
  dataclass — ok/checked/unknown/type_mismatches sonra degistirilebilir.
  validate_attributes tarafindan uretilen raporlar her zaman YENI dict/
  list ile gelir (her cagrida taze, paylasim yok).

BULGU-6 (production'a DOKUNULMADI — DAL-KESEN KESIF): validate_attributes
  her key'in str oldugunu VARSAYAR — L61'de key.startswith("gen_ai.")
  non-str key icin AttributeError firlatir: validate_attributes({5: "x"})
  CRASH eder (unknown'a dusMEZ). Yani fail-closed zihniyeti burada
  exception'lardir: cagri sahibi dict-key'lerini sanitize etmeyen bir
  cagri beklenmeyen exception alir. Onem: JSON attribute kaynagi gibi
  bazi ortamlar int-key dict'leri mumkundur. Production DOKUNULMADI.

Kural-1: SADECE yeni test dosyasi (tests/test_validate_dallar.py);
  production/conftest/mevcut-testlere DOKUNMA.
Kural-4: saf-bellek — ag/RPC/subprocess/socket YOK; monkeypatch+tmp_path.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.semconv.registry import GENAI_ATTRIBUTES  # noqa: E402
from swarmax.semconv.swx import SWX_ATTRIBUTES  # noqa: E402
from swarmax.semconv.validate import (  # noqa: E402
    SemconvReport,
    validate_attributes,
)

# Tip -> gecerli ornek deger katalogu (BULGU-4: [] gecerli str[])
TIPLI_ORNEK: dict[str, object] = {
    "str": "openai",
    "str[]": ["stop1", "stop2"],
    "int": 42,
    "double": 0.7,
    "bool": True,
}

# validate.py L17 — tip-denetimsiz gecen onek listesi
_ALLOWED = ("error.", "otel.", "service.", "deployment.", "k8s.", "host.", "telemetry.")

_GENAI_INT_KEYS = ["gen_ai.request.max_tokens", "gen_ai.request.seed",
                   "gen_ai.request.choice_count", "gen_ai.usage.input_tokens",
                   "gen_ai.usage.output_tokens"]
_GENAI_DOUBLE_KEYS = ["gen_ai.request.temperature", "gen_ai.request.top_p",
                      "gen_ai.request.frequency_penalty",
                      "gen_ai.request.presence_penalty", "gen_ai.usage.cost"]
_GENAI_STR_KEYS = ["gen_ai.system", "gen_ai.operation.name", "gen_ai.request.model",
                   "gen_ai.conversation.id", "gen_ai.tool.name"]
_GENAI_STRARR_KEYS = ["gen_ai.request.stop_sequences", "gen_ai.response.finish_reasons"]


# ================================================== validate_attributes ====
class TestValidateGenaiBasari:
    """validate_attributes — pinli gen_ai.* basari dallari."""

    @pytest.mark.parametrize("key", sorted(GENAI_ATTRIBUTES))
    def test_genai_pinli_key_gecerli_tip(self, key):
        """Basari dal: pinli HER gen_ai key correct-tip degerle gecer —
        ok=True, checked=1, unknown/type_mismatches bos (parametrik)."""
        tip = GENAI_ATTRIBUTES[key]
        rapor = validate_attributes({key: TIPLI_ORNEK[tip]})
        assert rapor.ok is True
        assert rapor.checked == 1
        assert rapor.unknown == []
        assert rapor.type_mismatches == {}

    def test_genai_tum_kayit_gecerli(self):
        """Basari dal: tum pinli gen_ai kaydi bir arada gecer (entegrasyon)."""
        attrs = {k: TIPLI_ORNEK[v] for k, v in GENAI_ATTRIBUTES.items()}
        rapor = validate_attributes(attrs)
        assert rapor.ok is True
        assert rapor.checked == len(attrs)

    @pytest.mark.parametrize("key", _GENAI_INT_KEYS)
    def test_int_key_double_deger_alias_gecerli(self, key):
        """BULGU-2 basari dal: int-beklenen key'e double deger geyerse
        alias'i nedeniyle gecerli sayilir (tolerans)."""
        rapor = validate_attributes({key: 5.0})
        assert rapor.ok is True
        assert rapor.type_mismatches == {}

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_bos_liste_gecerli(self, key):
        """BULGU-4 basari dal: bos-liste "str[]" sayilir —
        all(...) vacuous-truth (None -> "json" ile zitti)."""
        rapor = validate_attributes({key: []})
        assert rapor.ok is True
        assert rapor.type_mismatches == {}

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_str_listesi_gecerli(self, key):
        """Basari dal: str-listesi str[] beklentisini karsilar."""
        rapor = validate_attributes({key: ["a", "b"]})
        assert rapor.ok is True

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_tek_eleman_gecerli(self, key):
        """Sinir dal: tek-elemanli str-listesi gecerli (alt sinir)."""
        rapor = validate_attributes({key: ["a"]})
        assert rapor.ok is True

    @pytest.mark.parametrize("key", _GENAI_INT_KEYS)
    def test_int_key_negatif_deger_gecerli(self, key):
        """Sinir dal: negatif int deger tip-denetiminden gecer
        (validator semantic degeril tipi denetler)."""
        rapor = validate_attributes({key: -5})
        assert rapor.ok is True

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_unicode_gecerli(self, key):
        """Sinir dal: unicode str degeri gecerli (tip-temelli denetim)."""
        rapor = validate_attributes({key: "bälkεs-Δ"})
        assert rapor.ok is True

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_bos_string_gecerli(self, key):
        """Sinir dal: bos string "" gecerli str (uzunluk denetimi YOK)."""
        rapor = validate_attributes({key: ""})
        assert rapor.ok is True


class TestValidateGenaiBasarisiz:
    """validate_attributes — gen_ai.* basarisiz (yanlis-tip) dallari."""

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_int_deger_uyumsuz(self, key):
        """Basarisiz dal: int deger str-beklenen key'de (expected, actual)."""
        rapor = validate_attributes({key: 5})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str", "int")

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_bool_deger_uyumsuz(self, key):
        """Basarisiz dal: bool deger str-beklenen key'de — bool once
        kontrol edildiginden "bool" sayilir (BULGU-3)."""
        rapor = validate_attributes({key: True})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str", "bool")

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_none_deger_uyumsuz(self, key):
        """Basarisiz dal: None degeri "json" tipine duser (str degil)."""
        rapor = validate_attributes({key: None})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str", "json")

    @pytest.mark.parametrize("key", _GENAI_STR_KEYS)
    def test_str_key_liste_deger_uyumsuz(self, key):
        """Basarisiz dal: str-listesi str-beklenen key'de uyumsuzdur."""
        rapor = validate_attributes({key: ["a", "b"]})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str", "str[]")

    @pytest.mark.parametrize("key", _GENAI_INT_KEYS)
    def test_int_key_str_deger_uyumsuz(self, key):
        """Basarisiz dal: str deger int-beklenen key'de uyumsuzdur."""
        rapor = validate_attributes({key: "42"})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("int", "str")

    @pytest.mark.parametrize("key", _GENAI_INT_KEYS)
    def test_int_key_bool_deger_uyumsuz(self, key):
        """BULGU-3 basarisiz dal: bool deger int-beklenen key'inde "bool"
        olarak uyumsuzdur — True int'e zorlanmaz."""
        rapor = validate_attributes({key: True})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("int", "bool")

    @pytest.mark.parametrize("key", _GENAI_DOUBLE_KEYS)
    def test_double_key_int_deger_uyumsuz(self, key):
        """BULGU-2 basarisiz dal: double-beklenen key'e int deger MIS-match
        — alias asimetrik (int<-double gecer, double<-int degil)."""
        rapor = validate_attributes({key: 1})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("double", "int")

    @pytest.mark.parametrize("key", _GENAI_DOUBLE_KEYS)
    def test_double_key_str_deger_uyumsuz(self, key):
        """Basarisiz dal: str deger double-beklenen key'de uyumsuzdur."""
        rapor = validate_attributes({key: "0.7"})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("double", "str")

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_karisik_liste_uyumsuz(self, key):
        """Basarisiz dal: str-olmayan eleman iceren liste "list" tipine
        duser — str[] beklentisi karsilanmaz."""
        rapor = validate_attributes({key: ["a", 1]})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str[]", "list")

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_tuple_deger_uyumsuz(self, key):
        """BULGU-4 basarisiz dal: tuple "json" sayilir — yalnizca list
        str[] kabul edilir (tuple degil)."""
        rapor = validate_attributes({key: ("a", "b")})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str[]", "json")

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_none_deger_uyumsuz(self, key):
        """Basarisiz dal: None "json" tipine duser (bos liste ile zitti)."""
        rapor = validate_attributes({key: None})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str[]", "json")

    @pytest.mark.parametrize("key", _GENAI_STRARR_KEYS)
    def test_strarr_bool_liste_uyumsuz(self, key):
        """Basarisiz dal: bool-listesi "list" tipine duser."""
        rapor = validate_attributes({key: [True, False]})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("str[]", "list")

    @pytest.mark.parametrize("bilinmeyen", [
        "gen_ai.olmayan.key",
        "gen_ai.request.fake",
        "gen_ai.",
        "gen_ai.system.fake.deep",
        "GEN_AI.SYSTEM",
    ])
    def test_bilinmeyen_genai_key_unknown(self, bilinmeyen):
        """Basarisiz dal: registry'de OLMAYAN gen_ai.* key'i unknown'a
        gider — pinli-olmayan attribute kabul edilmez (paper §3.1)."""
        rapor = validate_attributes({bilinmeyen: "deger"})
        assert rapor.ok is False
        assert rapor.unknown == [bilinmeyen]


class TestValidateSwxDallari:
    """validate_attributes — swx.* basari+basarisiz+sinir dallari."""

    @pytest.mark.parametrize("key", sorted(SWX_ATTRIBUTES))
    def test_swx_pinli_key_gecerli_tip(self, key):
        """Basari dal: pinli HER swx key correct-tip degerle gecer
        (parametrik tam tarama — BULGU-4 bool dahil)."""
        tip = SWX_ATTRIBUTES[key]
        rapor = validate_attributes({key: TIPLI_ORNEK[tip]})
        assert rapor.ok is True
        assert rapor.checked == 1
        assert rapor.unknown == []

    @pytest.mark.parametrize("key", sorted(SWX_ATTRIBUTES))
    def test_swx_key_tip_kayit_eslesmesi(self, key):
        """Basari dal: validator swx key icin SWX_ATTRIBUTES tipini
        kullanir — registry ile birebir tip eslesmesi (parametrik)."""
        rapor = validate_attributes({key: TIPLI_ORNEK[SWX_ATTRIBUTES[key]]})
        assert key not in GENAI_ATTRIBUTES  # namespace'ler cakismiyor
        assert rapor.ok is True

    def test_swx_bilinmeyen_key_unknown(self):
        """Basarisiz dal: swx.* ama kayitta yok -> unknown."""
        rapor = validate_attributes({"swx.olmayan.key": 1})
        assert rapor.ok is False
        assert rapor.unknown == ["swx.olmayan.key"]

    def test_swx_str_key_int_uyumsuz(self):
        """Basarisiz dal: swx agent.role int ile uyumsuzdur."""
        rapor = validate_attributes({"swx.agent.role": 7})
        assert rapor.ok is False
        assert rapor.type_mismatches["swx.agent.role"] == ("str", "int")

    @pytest.mark.parametrize("key", ["swx.retry.count", "swx.mask.count",
                                     "swx.evidence.seq"])
    def test_swx_int_key_double_alias_gecerli(self, key):
        """BULGU-2 dal: swx int-key'leri icin de int-as-double alias'i
        gecerlidir (gen_ai ile ayni kural)."""
        rapor = validate_attributes({key: 2.0})
        assert rapor.ok is True

    def test_swx_bool_key_true_gecerli(self):
        """Basari dal: swx.slo.adopted=True bool olarak gecerli."""
        rapor = validate_attributes({"swx.slo.adopted": True})
        assert rapor.ok is True

    @pytest.mark.parametrize("key", ["swx.slo.adopted", "swx.synthetic"])
    @pytest.mark.parametrize("deger, beklenen_actual", [
        (1, "int"), ("true", "str"), ([], "str[]"), (None, "json"),
    ])
    def test_swx_bool_key_tip_uyumsuz(self, key, deger, beklenen_actual):
        """Basarisiz dal: bool-beklenen swx key'inde bool-disi deger
        (BULGU-4: [] str[] sayilir, None json)."""
        rapor = validate_attributes({key: deger})
        assert rapor.ok is False
        assert rapor.type_mismatches[key] == ("bool", beklenen_actual)

    def test_genai_swx_karisik_gecerli(self):
        """Basari dal: gen_ai ve swx key'leri ayni dict'te beraber gecer."""
        rapor = validate_attributes({
            "gen_ai.system": "openai", "swx.fleet.name": "fleet-1",
        })
        assert rapor.ok is True
        assert rapor.checked == 2


class TestValidateAllowedPrefixDallari:
    """validate_attributes — izinli onek (error./otel./...) dallari."""

    @pytest.mark.parametrize("key", [
        "error.type", "otel.library.name", "service.name",
        "deployment.environment", "k8s.namespace.name", "host.name",
        "telemetry.sdk.name",
    ])
    def test_izinli_onek_tip_denetimsiz_gecerli(self, key):
        """Basari dal: izinli her onek herhangi bir DEGERLE gecer —
        tip denetimi YAPILMAZ (continue)."""
        rapor = validate_attributes({key: 999})
        assert rapor.ok is True
        assert rapor.checked == 1
        assert rapor.unknown == []
        assert rapor.type_mismatches == {}

    @pytest.mark.parametrize("onek", _ALLOWED)
    def test_izinli_onek_sayim(self, onek):
        """Basari dal: izinli onekler checed-listede sayilir (continue).
        """
        rapor = validate_attributes({f"{onek}key": "deger"})
        assert rapor.ok is True
        assert rapor.checked == 1

    def test_error_type_pinli_ama_denetimsiz(self):
        """BULGU-1 DAL-KESEN KESIF: "error.type" GENAI_ATTRIBUTES'te "str"
        olarak PINLI fakat validator "error." onekinden continue ile gecer
        — 123 (int) bile gecer. Registry-virtual dalga (DOKUNULMADI)."""
        assert GENAI_ATTRIBUTES["error.type"] == "str"
        rapor = validate_attributes({"error.type": 123})
        assert rapor.ok is True
        assert rapor.type_mismatches == {}

    @pytest.mark.parametrize("key, deger", [
        ("error.type", None), ("error.type", ["x"]),
    ])
    def test_error_type_hic_tip_denetimine_girmez(self, key, deger):
        """BULGU-1 peklestirme: None/list degerler bile gecer — error.*
        attribute'leri tamamen tip-disidir."""
        rapor = validate_attributes({key: deger})
        assert rapor.ok is True

    @pytest.mark.parametrize("noktasiz", [
        "service", "error", "otel", "telemetry", "k8s", "host", "deployment",
    ])
    def test_noktasiz_onek_unknown(self, noktasiz):
        """Sinir dal: "service" (noktasiz) izinli DEGIL — unknown'a gider.
        onek ayrimi tam-string startswith ile (nokta dahil)."""
        rapor = validate_attributes({noktasiz: 1})
        assert rapor.ok is False
        assert rapor.unknown == [noktasiz]

    @pytest.mark.parametrize("yakin", ["servicex.name", "errors.type",
                                        "otelx.name", "hosts.name"])
    def test_yakin_ama_farkli_onek_unknown(self, yakin):
        """Sinir dal: "servicex"/"errors" onekleri izinli degildir —
        startswith tam oneki bekler."""
        rapor = validate_attributes({yakin: 1})
        assert rapor.ok is False
        assert rapor.unknown == [yakin]


class TestValidateBilinmeyenVeBirlesik:
    """validate_attributes — unknown ve birlesik (combined) dallari."""

    def test_bos_dict_bos_rapor(self):
        """Sinir dal: bos attributes -> (ok=True, checked=0)."""
        rapor = validate_attributes({})
        assert rapor.ok is True
        assert rapor.checked == 0
        assert rapor.unknown == []
        assert rapor.type_mismatches == {}

    @pytest.mark.parametrize("bilinmeyen", ["foo.bar", "custom.attr",
                                            "llm.model", "x", ""])
    def test_bilinmeyen_oneksiz_key_unknown(self, bilinmeyen):
        """Basarisiz dal: oneksiz/degisik key bilinmeyen olarak flag'lenir."""
        rapor = validate_attributes({bilinmeyen: 1})
        assert rapor.ok is False
        assert rapor.unknown == [bilinmeyen]

    def test_int_dict_key_attribute_error(self):
        """BULGU-6 DAL-KESEN KESIF: int (non-str) dict-key validate_attributes'i
        AttributeError ile CRASH eder — key.startswith("") str-varsayar; fail-
        closed Degil, EXCEPTION. Unions: {"x":"y"} normal; {5:"deger"} hata.
        Onem: validator dogal-bakim dis key'leri unknown saymak yerine
        kivirir; cagridan beklenmeyen exception. Production DOKUNULMADI."""
        with pytest.raises(AttributeError):
            validate_attributes({5: "deger"})

    def test_unknown_sirasi_korunur(self):
        """Dal: bilinmeyen key'ler dict sirasinda unknown listesine eklenir
        (karsilastirma ongone siralamasi)."""
        rapor = validate_attributes({"b_attr": 1, "a_attr": 2, "c_attr": 3})
        assert rapor.unknown == ["b_attr", "a_attr", "c_attr"]

    def test_unknown_arti_tip_uyumsuz_birlesik(self):
        """Dal: unknown VE tip-uyumsuz ayni anda -> ikisi de raporlanir,
        ok=False (iki ayri basarisizlik turu)."""
        rapor = validate_attributes({
            "foo.bar": 1,
            "gen_ai.request.model": 99,
        })
        assert rapor.ok is False
        assert rapor.unknown == ["foo.bar"]
        assert rapor.type_mismatches == {
            "gen_ai.request.model": ("str", "int")}

    def test_sade_unknown_ok_false(self):
        """Dal: yalnizca unknown varsa ok=True degil (fail-closed)."""
        rapor = validate_attributes({"foo.bar": 1})
        assert rapor.ok is False
        assert rapor.type_mismatches == {}

    def test_sade_tip_uyumsuz_ok_false(self):
        """Dal: yalnizca tip-uyumsuz varsa ok=False (fail-closed)."""
        rapor = validate_attributes({"gen_ai.system": 42})
        assert rapor.ok is False
        assert rapor.unknown == []

    def test_coklu_tip_uyumsuzlari_hepsi_raporlanir(self):
        """Dal: birden fazla uyumsuz key ayri ayri raporlanir."""
        rapor = validate_attributes({
            "gen_ai.system": 5,
            "gen_ai.request.max_tokens": "cok",
            "gen_ai.request.temperature": 1,
        })
        assert len(rapor.type_mismatches) == 3
        assert rapor.type_mismatches["gen_ai.system"] == ("str", "int")
        assert rapor.type_mismatches["gen_ai.request.max_tokens"] == ("int", "str")
        assert rapor.type_mismatches["gen_ai.request.temperature"] == ("double", "int")

    def test_uyumlu_uzun_dict_hepsi_sayilir(self):
        """Sinir dal: tum pinli Kayitlar + izinli onekler bir arada —
        checked toplam anahtar sayisini verir."""
        attrs = {k: TIPLI_ORNEK[v] for k, v in GENAI_ATTRIBUTES.items()}
        attrs.update({k: TIPLI_ORNEK[v] for k, v in SWX_ATTRIBUTES.items()})
        attrs["service.name"] = "swarmax"
        rapor = validate_attributes(attrs)
        assert rapor.ok is True
        assert rapor.checked == len(attrs)

    def test_genai_arti_service_birlesik_gecerli(self):
        """Basari dal: gen_ai key + allowed prefix key birlikte gecer."""
        rapor = validate_attributes({
            "gen_ai.system": "openai", "service.name": "swarmax"})
        assert rapor.ok is True
        assert rapor.checked == 2

    def test_checked_unknown_dahil_sayar(self):
        """Dal: checked bilinmeyen + uyumsuz dahil TUM key'leri sayar
        (checked len(attributes) ile birebir)."""
        attrs = {"foo.bar": 1, "gen_ai.system": 5, "host.name": "h1"}
        rapor = validate_attributes(attrs)
        assert rapor.checked == len(attrs) == 3

    def test_ozet_birebir_birlesik_rapor(self):
        """Dal: birlesik raporun summary() ciktisi birebir beklenen formata
        uyar (ok=False checked=2 unknown=1 type_mismatches=1)."""
        rapor = validate_attributes({
            "foo.bar": 1, "gen_ai.system": 5})
        assert rapor.summary() == "ok=False checked=2 unknown=1 type_mismatches=1"

    def test_genai_swx_arti_unknown_karisik_tam(self):
        """Dal: gen_ai (gecerli+uyumsuz) + swx (gecerli) + unknown karisik —
        dallarin hepsi tek raporda olculur."""
        rapor = validate_attributes({
            "gen_ai.system": "openai",
            "gen_ai.usage.cost": 1,        # double<-int -> mismatch
            "swx.fleet.name": "fleet-1",
            "swx.ttft.s": 0.5,
            "bilinmeyen.key": 3,
            "error.type": "timeout",
        })
        assert rapor.ok is False
        assert rapor.checked == 6
        assert rapor.unknown == ["bilinmeyen.key"]
        assert rapor.type_mismatches == {"gen_ai.usage.cost": ("double", "int")}


# ====================================================== SemconvReport ======
class TestSemconvReportYapi:
    """SemconvReport — dataclass default/ozdeslik/mutability dallari."""

    def test_default_deger_zerolastirma(self):
        """Basari dal: default unknown=[] ve type_mismatches={} ile
        SemconvReport(ok=..., checked=...) kurulur."""
        rapor = SemconvReport(ok=True, checked=3)
        assert rapor.ok is True
        assert rapor.checked == 3
        assert rapor.unknown == []
        assert rapor.type_mismatches == {}

    def test_default_listeleri_taze_ornek_basina(self):
        """BULGU-5 dal: default_factory list/dict HER ornekte tazedir —
        bir ornege append digerini etkilemez (paylasim YOK)."""
        r1 = SemconvReport(ok=True, checked=1)
        r2 = SemconvReport(ok=True, checked=1)
        r1.unknown.append("x")
        r1.type_mismatches["k"] = ("str", "int")
        assert r2.unknown == []
        assert r2.type_mismatches == {}

    def test_ozdeslik_ayni_deger_esit(self):
        """Basari dal: ayni alan degerlerine sahip raporlar esittir
        (dataclass __eq__ list/dict deger karsilastirir)."""
        r1 = SemconvReport(ok=False, checked=2, unknown=["a"],
                           type_mismatches={"k": ("str", "int")})
        r2 = SemconvReport(ok=False, checked=2, unknown=["a"],
                           type_mismatches={"k": ("str", "int")})
        assert r1 == r2

    def test_farkli_deger_esit_degil(self):
        """Basarisiz dal: farkli degerler esitsizdir (ozdeslik anlamli)."""
        r1 = SemconvReport(ok=True, checked=1)
        r2 = SemconvReport(ok=False, checked=1)
        assert r1 != r2

    def test_default_farkli_checked_esit_degil(self):
        """Basarisiz dal: sadece checked farkliysa esit degildir."""
        assert SemconvReport(ok=True, checked=1) != SemconvReport(ok=True, checked=2)

    def test_rapor_mutable_frozen_degil(self):
        """BULGU-5 basarisiz dal: plain dataclass — ok/checked/unknown
        sonradan degistirilebilir (frozen DEGIL)."""
        rapor = SemconvReport(ok=True, checked=1)
        rapor.ok = False
        rapor.checked = 5
        rapor.unknown.append("b")
        assert rapor.ok is False
        assert rapor.checked == 5
        assert rapor.unknown == ["b"]

    @pytest.mark.parametrize("rapor, beklenen", [
        (SemconvReport(ok=True, checked=0), "ok=True checked=0 unknown=0 type_mismatches=0"),
        (SemconvReport(ok=False, checked=0), "ok=False checked=0 unknown=0 type_mismatches=0"),
        (SemconvReport(ok=False, checked=9, unknown=["a", "b"]),
         "ok=False checked=9 unknown=2 type_mismatches=0"),
        (SemconvReport(ok=False, checked=2, type_mismatches={"k": ("int", "str")}),
         "ok=False checked=2 unknown=0 type_mismatches=1"),
        (SemconvReport(ok=False, checked=5, unknown=["a", "b", "c"],
                       type_mismatches={"k1": (), "k2": ()}),
         "ok=False checked=5 unknown=3 type_mismatches=2"),
    ])
    def test_summary_birebilir_format(self, rapor, beklenen):
        """Basari dal: summary() "ok=.. checked=.. unknown=N
        type_mismatches=N" birebir formatinda (parametrik)."""
        assert rapor.summary() == beklenen

    def test_summary_str_turu(self):
        """Basari dal: summary() str doner (baska tip degil)."""
        assert isinstance(SemconvReport(ok=True, checked=0).summary(), str)

    def test_summary_mutasyona_yansir(self):
        """BULGU-5 dal: mutasyon sonrasi summary guncel degeri verir
        (rapor canli-goruntu, dinamik sayim)."""
        rapor = SemconvReport(ok=True, checked=1)
        once = rapor.summary()
        rapor.unknown.extend(["x", "y"])
        rapor.ok = False
        assert once == "ok=True checked=1 unknown=0 type_mismatches=0"
        assert rapor.summary() == "ok=False checked=1 unknown=2 type_mismatches=0"


class TestValidateEnstrumansal:
    """validate_attributes — determinizm/tekrar (saf-fonksiyon) dallari."""

    def test_deterministik_ayni_girdi_ayni_rapor(self):
        """Dal: ayni girdi iki cagri AYNI raporu verir (saf-fonksiyon)."""
        attrs = {"gen_ai.system": "x", "foo": 1}
        r1 = validate_attributes(attrs)
        r2 = validate_attributes(attrs)
        assert r1.ok == r2.ok
        assert r1.checked == r2.checked
        assert r1.unknown == r2.unknown
        assert r1.type_mismatches == r2.type_mismatches

    def test_sayma_algoritmasi_uzun_dict(self):
        """Sinir dal: uzun (100 karisik) dict'te checked birebir len —
        agirlik/dogruluk olcumu."""
        attrs = {f"gen_ai.request.model_{i}": "m" for i in range(50)}
        attrs.update({f"service.name_{i}": "s" for i in range(50)})
        rapor = validate_attributes(attrs)
        assert rapor.checked == 100
        assert len(rapors_unknown(rapor)) == 50

    def test_nested_olmayan_deger_ipuclari(self):
        """Sinir dal: dict degeri "json" tipine duser — validator nested
        objeleri str ile karistirmaz."""
        rapor = validate_attributes({"gen_ai.system": {"nested": 1}})
        assert rapor.type_mismatches["gen_ai.system"] == ("str", "json")


def rapors_unknown(rapor: SemconvReport) -> list[str]:
    """Test-yardimcisi: rapor.unknown listesini dondurur (sayma testi)."""
    return list(rapor.unknown)
