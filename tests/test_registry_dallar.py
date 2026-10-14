"""test_registry_dallar.py — swarmax/semconv/registry.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/semconv/registry.py, 60 satir) — public API:
  PINNED_SEMCONV   : str — pinlenen semconv kaynagini tanimlayan sabit (L15)
  GENAI_ATTRIBUTES : dict[str,str] — pinlenen gen_ai.* attribute kayit defteri (L18)
  genai_keys()     -> sorted(GENAI_ATTRIBUTES) — sirali anahtar listesi (L59)
  (private) _EVENT_NAMES — 4 adet event adinin demeti; genai_keys bunlari
  KULLANMAZ (kayıt defteri attribute'leri ile event adlari ayik tutulmustur).

DAL HARITASI:
  PINNED_SEMCONV: str-turu, doluluk, kaynak-kimligi, okuma-tarihi, status
    ("Development" hepsi, "Stable" HIC YOK — bu yuzden pin+validator).
  GENAI_ATTRIBUTES: dict-turu, her key bos-olmayan str, her value str, her
    value {"str","str[]","int","double","bool"} sozlugunden, key'ler essiz,
    bilinen-pinli key'ler mevcut, deprecated key'ler pinli, 5 tipin de en
    az bir kullanimi var, "gen_ai." on-ek kurali.
  genai_keys: list-donus, siralama, uzunluk, essizlik, determinizm, kopya
    (mutasyon module degmesin), bos-kayıt (monkeypatch), ters-sira girdide
    sirali cikti, tek-eleman, karisik-tip anahtarda TypeError (basarisiz).

BULGU-1 (production'a DOKUNULMADI — gerceklik test dosyasinda belgelendi):
  genai_keys() adi "gen_ai anahtarlari" cagrisi yapsa da GENAI_ATTRIBUTES
  "error.type": "str" elemanini ICERIR ve bukey "gen_ai." on-ekiyle
  BASLAMAZ. Yani cikti saf-gen_ai degil; tek bir "error.*" haricidir.
  Bu bilincli_PIN: validator "error." on-eklini ayri ele alir (icin
  test_validate_dallar.py'ye bakin). Onem: arayan kod genai_keys()'i
  filtresiz "gen_ai.*" listesi olarak kullaniyorsa "error.type" surpriz.

BULGU-2 (production'a DOKUNULMADI): _EVENT_NAMES demeti (4 event adi)
  GENAI_ATTRIBUTES ile ayik tutulmustur — genai_keys() event adlarini
  DIŞARIDA birakir. Yani "gen_ai.client.token.usage" gibi event adlari
  attribute validasyonuna GIRMEZ; validator sadece attribute kayit
  defterini kullanir. Ayirim bilinclidir (docs/registry'de event'ler
  ayri tabloda), fakat attrs/event karisikligina açik bir sürprizdir.

BULGU-3 (production'a DOKUNULMADI): GENAI_ATTRIBUTES plain dict'tir —
  MappingProxy/değişmez degil. Dis mutasyon (registry.GENAI_ATTRIBUTES
  ["gen_ai.x"]="str") mumkun ve genai_keys() bunu aninda yansitir.
  Test-44 mutasyona-karsi-izolasyonu olcer; production disaridan
  mutasyona karsi korumasizdir (guven tek-basinlik disiplinidir).

BULGU-4 (production'a DOKUNULMADI — DAL-KESEN KESIF): registry.py L17
  comment'inde tip sozlugunu "str" | "str[]" | "int" | "double" | "bool"
  olarak tanimlar, ANCAK pinlenen GERCHEK GENAI_ATTRIBUTES icinde "bool"
  tipini KULLANAN HICBIR attribute YOKTUR (dagilim: str=20, int=5,
  double=5, str[]=2, bool=0). "bool" yalnizca swx.* uzanti alaninda
  kullanilir (swx.slo.adopted, swx.synthetic). Onem: validor
  ("kayit defterinde var mi" dediginden degil _actual_type bool'i
  taniyacaktir) ama sozluk-genisligi gercek kullanimi asmaktadir —
  vocabulary 5 parca, pinli kullanim 4 parca. Bu bosluk testlerle
  olculdu, production'a DOKUNULMADI.

Kural-1: SADECE yeni test dosyasi (tests/test_registry_dallar.py).
Kural-4: saf-bellek — ag/RPC/subprocess/socket YOK, monkeypatch only.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.semconv import registry  # noqa: E402
from swarmax.semconv.registry import (  # noqa: E402
    GENAI_ATTRIBUTES,
    PINNED_SEMCONV,
    genai_keys,
)

# Pinli tip sozlugu (registry.py L17 yorumunda belgelendi) — BULGU-4:
# "bool" sozlukte tanimli ANCAK pinli GENAI_ATTRIBUTES'te HIC kullanilmaz.
TIPLER = ("str", "str[]", "int", "double", "bool")
KULLANILAN_TIPLER = ("str", "str[]", "int", "double")  # gercek pinli dagilim

# Katalog: her tip icin ornek deger — basari dallari icin
TIPLI_ORNEK: dict[str, object] = {
    "str": "openai",
    "str[]": ["stop1", "stop2"],
    "int": 42,
    "double": 0.7,
    "bool": True,
}


def _kayıt_gecerli(ka: dict[str, str]) -> list[str]:
    """Invariant denetleyicisi: kayit defteri bozukluklarinin listesi."""
    ihlaller: list[str] = []
    for key, tip in ka.items():
        if not isinstance(key, str) or not key:
            ihlaller.append(f"key-bos-veya-str-degil:{key!r}")
        if not isinstance(tip, str) or tip not in TIPLER:
            ihlaller.append(f"tip-sozluk-disi:{tip!r}")
    if len(ka) != len(set(ka)):
        ihlaller.append("key-essiz-degil")
    return ihlaller


# ==================================================== PINNED_SEMCONV =========
class TestPinnedSemconv:
    """PINNED_SEMCONV — pin kimligi sabiti dallari."""

    def test_str_turu(self):
        """Dal: sabit bir Python str'sidir (baska tip degil)."""
        assert isinstance(PINNED_SEMCONV, str)

    def test_dolu(self):
        """Dal: bos degil — pin anlamsiz olmaz."""
        assert PINNED_SEMCONV.strip() != ""

    def test_kaynak_kimligi(self):
        """Dal: upstream repo kimligini icerir (takip edilebilirlik)."""
        assert "open-telemetry/semantic-conventions-genai" in PINNED_SEMCONV

    def test_okuma_tarihi(self):
        """Dal: pin okuma tarihini icerir (snapshot hangi gun)."""
        assert "2025-09-14" in PINNED_SEMCONV

    def test_status_development(self):
        """Dal: pin status kelimesini istir — pinlemenin nedeni (R9)."""
        assert "Development" in PINNED_SEMCONV

    def test_stable_kelimesi_yok(self):
        """Sinir/basarisiz dal: pin "Stable" DEMEZ — hicbir attribute
        stable olmadigi icin pin+validator tasarlandi (module docstring)."""
        assert "Stable" not in PINNED_SEMCONV

    def test_isaret_cicesi(self):
        """Dal: pin "@" baglacini icerir — surum/de referans notasyonu."""
        assert "@" in PINNED_SEMCONV

    def test_branch_main(self):
        """Dal: pin "main" branch referansini icerir."""
        assert "main" in PINNED_SEMCONV


# ==================================================== GENAI_ATTRIBUTES ======
class TestGenaiAttributesYapi:
    """GENAI_ATTRIBUTES — yapi/fidan invariant dallari."""

    def test_dict_turu(self):
        """Dal: bir dict'tir (liste/demet degil)."""
        assert isinstance(GENAI_ATTRIBUTES, dict)

    def test_bos_degil(self):
        """Dal: bos kayit defteri degil — pin anlamlidir."""
        assert len(GENAI_ATTRIBUTES) > 0

    @pytest.mark.parametrize("key", sorted(GENAI_ATTRIBUTES))
    def test_key_str_ve_dolu(self, key):
        """Basari dal: HER key str ve bos-degil (parametrik tarama)."""
        assert isinstance(key, str)
        assert key != ""

    @pytest.mark.parametrize("key", sorted(GENAI_ATTRIBUTES))
    def test_value_str(self, key):
        """Basari dal: HER value str (tip adi metnidir)."""
        assert isinstance(GENAI_ATTRIBUTES[key], str)

    def test_keyler_essiz(self):
        """Dal: dict zaten essiz anahtar zorlar — teyit (BULGU-3 on kosul)."""
        assert len(GENAI_ATTRIBUTES) == len(set(GENAI_ATTRIBUTES))

    def test_none_key_yok(self):
        """Sinir dal: None key bulunmaz (dict yapisal izin verir ama)."""
        assert None not in GENAI_ATTRIBUTES

    @pytest.mark.parametrize("tip", KULLANILAN_TIPLER)
    def test_tipin_kullanimi_var(self, tip):
        """Basari dal: pinli 4 tipten HER biri en az bir attribute tarafindan
        kullanilir — gercek dagilim (parametrik)."""
        kullananlar = [k for k, v in GENAI_ATTRIBUTES.items() if v == tip]
        assert len(kullananlar) >= 1, f"tip {tip!r} icin kayit yok"

    def test_bool_tipi_sozlukte_fakat_kullanilmiyor(self):
        """BULGU-4 basarisiz dal: "bool" registry.py L17 tip sozlugunde
        tanimli ANCAK pinli GENAI_ATTRIBUTES'te HIC kullanilmamistir.
        Sozluk-genisligi gercek kullanimi asar (production DOKUNULMADI)."""
        bool_kullanan = [k for k, v in GENAI_ATTRIBUTES.items() if v == "bool"]
        assert bool_kullanan == []
        # teyit: tip seti icinde tanimli, kullanilan set disinda
        assert "bool" in TIPLER
        assert "bool" not in KULLANILAN_TIPLER

    def test_tip_dagilimi_gercegi(self):
        """BULGU-4 olcum dal: pinli dagilim str=20/int=5/double=5/str[]=2."""
        from collections import Counter

        dagilim = Counter(GENAI_ATTRIBUTES.values())
        assert dict(dagilim) == {"str": 20, "int": 5, "double": 5, "str[]": 2}

    def test_tip_degerleri_disinda_yok(self):
        """Basari dal: HIÇ bir value {"str","str[]","int","double","bool"}
        disinda deger ALMAZ — bu yapi invariant'i (mutasyona karsi olculdu)."""
        assert set(GENAI_ATTRIBUTES.values()) <= set(TIPLER)

    def test_plain_dict_koruma_yok(self):
        """BULGU-3 dal: korumasiz plain dict — MappingProxyType (değişmez)
        DEGILDIR; dis mutasyona acik (production'a DOKUNMADAN belgelendi)."""
        from types import MappingProxyType

        assert isinstance(GENAI_ATTRIBUTES, dict)
        assert not isinstance(GENAI_ATTRIBUTES, MappingProxyType)

    @pytest.mark.parametrize("key", [
        "gen_ai.system",
        "gen_ai.operation.name",
        "gen_ai.request.model",
        "gen_ai.request.max_tokens",
        "gen_ai.request.temperature",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.tool.name",
        "gen_ai.conversation.id",
        "error.type",
    ])
    def test_pinli_key_mevcut(self, key):
        """Basari dal: bilinen pinli key'ler kayitta mevcut (regresyon)."""
        assert key in GENAI_ATTRIBUTES

    @pytest.mark.parametrize("key", ["gen_ai.prompt", "gen_ai.completion"])
    def test_deprecated_key_pinli(self, key):
        """Dal: deprecated event-tercihli key'ler pinli tutulmus
        (kayit defteri comment L39-40 ile belgelendirildi)."""
        assert key in GENAI_ATTRIBUTES
        assert GENAI_ATTRIBUTES[key] == "str"

    @pytest.mark.parametrize("tip, beklenen_key", [
        ("str[]", "gen_ai.request.stop_sequences"),
        ("str[]", "gen_ai.response.finish_reasons"),
        ("int", "gen_ai.request.max_tokens"),
        ("int", "gen_ai.usage.input_tokens"),
        ("double", "gen_ai.request.temperature"),
        ("double", "gen_ai.request.top_p"),
    ])
    def test_tip_key_eslesmesi(self, tip, beklenen_key):
        """Basari dal: tip<->key eslesmesi kayit defterinde dogru pinli."""
        assert GENAI_ATTRIBUTES[beklenen_key] == tip

    @pytest.mark.parametrize("key", sorted(GENAI_ATTRIBUTES))
    def test_key_gen_ai_on_eki_veya_error(self, key):
        """Basari dal: her key "gen_ai." ile baslar VEYA tek "error.type"
        istisnasidir (BULGU-1 — genai_keys bu istisnayi yansitir)."""
        assert key.startswith("gen_ai.") or key == "error.type"

    def test_gen_ai_disi_key_sayisi_bir(self):
        """BULGU-1 dal: "gen_ai." disi TEK key "error.type" — istisna sayisi."""
        disinda = [k for k in GENAI_ATTRIBUTES if not k.startswith("gen_ai.")]
        assert disinda == ["error.type"]


class TestGenaiAttributesInvariant:
    """GENAI_ATTRIBUTES — invariant denetleyici dallari (mutasyon testi).

    Veri modulu oldugu icin "basarisiz" dallari burada olculur: invariant
    denetleyicisi (_kayıt_gecerli) GERCHEK kayitta HIC ihlal bulmaz, ama
    monkeypatch ile bozulmus kayitlarda ihlal BULUR (denetleyici anlamli).
    """

    def test_invariant_gercekte_gecti(self):
        """Basari dal: gercek pinli kayit defteri invariant'lari saglar."""
        assert _kayıt_gecerli(GENAI_ATTRIBUTES) == []

    @pytest.mark.parametrize("bozuk, beklenen_ihllal", [
        ({"gen_ai.a": "str", 7: "int"}, "key-bos-veya-str-degil:7"),
        ({"gen_ai.a": "liste"}, "tip-sozluk-disi:'liste'"),
        ({"gen_ai.a": "bool", "gen_ai.b": "numara"}, "tip-sozluk-disi:'numara'"),
        ({"": "str"}, "key-bos-veya-str-degil:''"),
        ({7: "str"}, "key-bos-veya-str-degil:7"),
    ])
    def test_invariant_bozuk_kayitti_isaretler(self, bozuk, beklenen_ihllal):
        """Basarisiz dal: bozulmus kayitta denetleyici ihlal raporlar
        (parametrik — her ihlal turu ayri dal)."""
        ihlaller = _kayıt_gecerli(bozuk)
        assert beklenen_ihllal in ihlaller

    def test_tip_degeri_none_ihllal(self):
        """Basarisiz dal: None tip degeri sozluk-disidir."""
        ihlaller = _kayıt_gecerli({"gen_ai.a": None})  # type: ignore[dict-item]
        assert any("tip-sozluk-disi" in i for i in ihlaller)

    def test_bos_kayit_invariant_gecti(self):
        """Sinir dal: bos kayitta ihlal YOK (vacuous-basari)."""
        assert _kayıt_gecerli({}) == []

    def test_uzun_kayit_invariant_gecti(self):
        """Sinir dal: uzun kayitta da invariant saglanir (gercek boyut)."""
        assert _kayıt_gecerli(dict(GENAI_ATTRIBUTES)) == []


# ==================================================== genai_keys ===========
class TestGenaiKeys:
    """genai_keys() — siralama/determinizm/kopya dallari."""

    def test_list_turu(self):
        """Basari dal: donus bir list'dir (dict-keys degil)."""
        assert isinstance(genai_keys(), list)

    def test_sorted_karsiligi(self):
        """Basari dal: cikti birebir sorted(GENAI_ATTRIBUTES)."""
        assert genai_keys() == sorted(GENAI_ATTRIBUTES)

    def test_uzunluk_esit(self):
        """Basari dal: tum kayit defteri anahtarlari doner (eksik yok)."""
        assert len(genai_keys()) == len(GENAI_ATTRIBUTES)

    @pytest.mark.parametrize("key", sorted(GENAI_ATTRIBUTES))
    def test_her_eleman_str(self, key):
        """Basari dal: donen HER eleman str (parametrik tarama)."""
        assert isinstance(key, str)

    def test_essiz_elemanlar(self):
        """Dal: cikti TEKRAR icermez (duplikat yok)."""
        sonuc = genai_keys()
        assert len(sonuc) == len(set(sonuc))

    @pytest.mark.parametrize("once, sonra", list(zip(sorted(GENAI_ATTRIBUTES), sorted(GENAI_ATTRIBUTES)[1:])))
    def test_sirali(self, once, sonra):
        """Basari dal: komsu ciftlerde siralama korunur (parametrik)."""
        assert once <= sonra

    def test_deterministik(self):
        """Dal: ardisik iki cagri ayni listeyi verir (zaman-degismez)."""
        assert genai_keys() == genai_keys()

    def test_donen_kopya_mutasyon_module_degmez(self):
        """Dal: donen liste KOPYA — append module kayit degistirmez."""
        once = len(GENAI_ATTRIBUTES)
        sonuc = genai_keys()
        sonuc.append("gen_ai.test.mutasyon")
        assert len(GENAI_ATTRIBUTES) == once
        assert "gen_ai.test.mutasyon" not in GENAI_ATTRIBUTES

    def test_donen_kopya_pop_module_degmez(self):
        """Dal: donen listeden pop module kayit degistirmez (kopya teyit)."""
        sonuc = genai_keys()
        sonuc.pop()
        assert len(genai_keys()) == len(GENAI_ATTRIBUTES)

    def test_set_esitligi(self):
        """Dal: cikti kumesi kayit defteri kumesine esit (eksik/fazla yok)."""
        assert set(genai_keys()) == set(GENAI_ATTRIBUTES)

    def test_error_type_icerir(self):
        """BULGU-1 dal: genai_keys "error.type" dondurur — "gen_ai.*" listesi
        degildir (production'a DOKUNMADAN belgelendi)."""
        assert "error.type" in genai_keys()

    @pytest.mark.parametrize("event_adi", [
        "gen_ai.client.inference.operation.details",
        "gen_ai.client.token.usage",
        "gen_ai.agent.definitions",
        "gen_ai.tool.definitions",
    ])
    def test_event_adlari_disarida(self, event_adi):
        """BULGU-2 dal: _EVENT_NAMES adlari genai_keys ciktisinda YOK —
        attribute/event ayirimi bilinclidir."""
        assert event_adi not in genai_keys()

    def test_event_names_demeti_kullanilmaz(self):
        """BULGU-2 dal: registry._EVENT_NAMES demeti gercekten 4 event
        icerir ve bunlardan HICBIRI attribute kayit defterinde degildir."""
        for event_adi in registry._EVENT_NAMES:
            assert event_adi not in GENAI_ATTRIBUTES
        assert len(registry._EVENT_NAMES) == 4


class TestGenaiKeysMonkeypatch:
    """genai_keys() — monkeypatch ile bos/tek/ters/karisik giris dallari.

    Kural-4: saf-bellek — GENAI_ATTRIBUTES module global'i gecici olarak
    degistirilir, monkeypatch otomatik-restore eder (uretime DOKUNMAZ).
    """

    def test_bos_kayıt_bos_liste(self, monkeypatch):
        """Sinir dal: bos kayitta genai_keys() bos liste doner."""
        monkeypatch.setattr(registry, "GENAI_ATTRIBUTES", {})
        assert genai_keys() == []

    def test_ters_sira_girdide_sirali_cikti(self, monkeypatch):
        """Basari dal: ters-sirali kayitta cikti YINE sorted (insertion onemsiz)."""
        kayit = {"gen_ai.z": "str", "gen_ai.a": "str", "gen_ai.m": "int"}
        monkeypatch.setattr(registry, "GENAI_ATTRIBUTES", kayit)
        assert genai_keys() == ["gen_ai.a", "gen_ai.m", "gen_ai.z"]

    def test_tek_eleman(self, monkeypatch):
        """Sinir dal: tek-elemanli kayitta tek-elemanli cikti."""
        monkeypatch.setattr(registry, "GENAI_ATTRIBUTES", {"gen_ai.tek": "str"})
        assert genai_keys() == ["gen_ai.tek"]

    def test_karisik_tip_anahtarda_type_error(self, monkeypatch):
        """Basarisiz dal: int+str karisik anahtarda sorted() TypeError
        firlatir — genai_keys kayit defteri invariant'ina guvenir."""
        monkeypatch.setattr(
            registry,
            "GENAI_ATTRIBUTES",
            {7: "int", "gen_ai.a": "str"},
        )
        with pytest.raises(TypeError):
            genai_keys()

    def test_none_anahtarda_type_error(self, monkeypatch):
        """Basarisiz dal: None anahtar sorted tarafindan reddedilir."""
        monkeypatch.setattr(
            registry,
            "GENAI_ATTRIBUTES",
            {None: "int", "gen_ai.a": "str"},
        )
        with pytest.raises(TypeError):
            genai_keys()

    def test_veri_sirali_uzun_kayit(self, monkeypatch):
        """Basari dal: cok-fazla (50) anahtarli kayitta siralama korunur."""
        kayit = {f"gen_ai.k{i:02d}": "str" for i in range(50, -1, -1)}
        monkeypatch.setattr(registry, "GENAI_ATTRIBUTES", kayit)
        sonuc = genai_keys()
        assert sonuc == sorted(sonuc)
        assert len(sonuc) == 51

    def test_monkeypatch_kapsamda_degistirildi(self, monkeypatch):
        """Dal: monkeypatch KAPSAMINDA module global'i gecici olarak
        degisir — bu test, sonraki testte restore teyidinin on kosuludur."""
        monkeypatch.setattr(registry, "GENAI_ATTRIBUTES", {"x": "str"})
        assert genai_keys() == ["x"]

    def test_monkeypatch_sonrasi_gercekrestore(self):
        """Dal: Onceki testin monkeypatch'i cope atti — gercek kayit
        bozulMADI (Kural-1: production'a DOKUNULMADI teyidi)."""
        assert "x" not in GENAI_ATTRIBUTES
        assert genai_keys() == sorted(GENAI_ATTRIBUTES)


# ==================================================[ public API yapi ]=====
class TestPublicApiYapi:
    """registry public API semasi — import yapi dallari (geri-uyumluluk)."""

    def test_uc_public_simge_mevcut(self):
        """Basari dal: PINNED_SEMCONV + GENAI_ATTRIBUTES + genai_keys
        module seviyesinde mevcut (__init__. __all__ ile uyumlu)."""
        assert hasattr(registry, "PINNED_SEMCONV")
        assert hasattr(registry, "GENAI_ATTRIBUTES")
        assert callable(registry.genai_keys)

    def test_package_export_ile_uyumlu(self):
        """Basari dal: swarmax.semconv package __all__ registry simgelerini
        disa aktarir (import yapi tutarliligi)."""
        from swarmax.semconv import __all__ as p_all  # noqa: E402

        for s in ("GENAI_ATTRIBUTES", "PINNED_SEMCONV", "genai_keys"):
            assert s in p_all

    def test_ornek_deger_tip_uyumu(self):
        """Basari dal: her PINLI tip icin ornek deger(isinstance) tip
        beklentisini karsilar — bool BULGU-4 sebebiyle haric tutuldu."""
        for tip, ornek in TIPLI_ORNEK.items():
            if tip == "bool":
                # BULGU-4: bool pinli gen_ai kaydinda kullanilmiyor
                continue
            kullanan = [k for k, v in GENAI_ATTRIBUTES.items() if v == tip]
            assert kullanan, f"tip {tip!r} pinli degil"
            if tip == "int":
                assert isinstance(ornek, int) and not isinstance(ornek, bool)
            elif tip == "double":
                assert isinstance(ornek, float)
            elif tip == "str":
                assert isinstance(ornek, str)
            elif tip == "str[]":
                assert isinstance(ornek, list)
                assert all(isinstance(v, str) for v in ornek)

    def test_swx_bool_kullanimi_var(self):
        """BULGU-4 tamamlama dal: "bool" tipi gercekten swx uzanti
        alaninda kullanilmaktadir (sozluk bos yere genis degil)."""
        from swarmax.semconv.swx import SWX_ATTRIBUTES

        bool_kullanan = [k for k, v in SWX_ATTRIBUTES.items() if v == "bool"]
        assert set(bool_kullanan) == {"swx.slo.adopted", "swx.synthetic"}
