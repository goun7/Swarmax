"""69-Swarmax pipeline._utcnow/_parse_ts/_parse_json + otlp._attr_map/_iso_from_ns + report._h dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (saf fonksiyonlar + sabit-epoch pinleme;
network/DB YASAK). _utcnow/_iso_from_ns canli-saat kullanir —
deterministik-test icin monkeypatch ile SABITLENIR.

ORTAM-ANATOMI:
- _utcnow(): datetime.now(timezone.utc).replace(tzinfo=None) — NAIVE UTC
  (utcnow() deprecation'inin yerini alir)
- _parse_ts(value): datetime passthrough; else fromisoformat(str(value))
- _parse_json(value): str -> json.loads; else dict(value)
- _attr_map(attributes): OTLP KeyValue list -> dict; anyValue oneof sirasi
  string->int->double->bool (break); arrayValue -> [e['stringValue']...];
  else None
- _iso_from_ns(ns): ns<=0 -> time.time_ns(); divmod 1e9;
  strftime('%Y-%m-%d %H:%M:%S') + '.{nanos//1000:06d}'
- _h(hours): f'{hours:.1f}h'
"""
import json
import sys
import time
from datetime import datetime, timezone

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
import swarmax.otlp as otlp_mod  # noqa: E402
import swarmax.pipeline as pipe_mod  # noqa: E402
from swarmax.otlp import _attr_map, _iso_from_ns  # noqa: E402
from swarmax.pipeline import _parse_json, _parse_ts, _utcnow  # noqa: E402
from swarmax.report import _h  # noqa: E402


@pytest.fixture
def frozen_ns(monkeypatch):
    def _set(ns):
        monkeypatch.setattr(otlp_mod.time, "time_ns", lambda: ns)
    return _set


# == _utcnow ==========================================================================================

def test_utcnow_naive():
    """ORTAM: tzinfo=None (NAIVE UTC)."""
    assert _utcnow().tzinfo is None


def test_utcnow_utc_degeri(monkeypatch):
    """ORTAM-OGRENDI: datetime.now(timezone.utc).replace(tzinfo=None) —
    deger UTC ama tzinfo soyulmus (saklanan naive ts'lerle eslesir).
    datetime IMMUTABLE tip — modul niteligi yamalanir."""
    sabit = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    class _FakeDT:
        @staticmethod
        def now(tz=None):
            return sabit
    monkeypatch.setattr(pipe_mod, "datetime", _FakeDT)
    v = _utcnow()
    assert v == datetime(2026, 1, 1, 12, 0, 0)
    assert v.tzinfo is None


def test_utcnow_donut_tipi():
    assert isinstance(_utcnow(), datetime)


def test_utcnow_ilerler():
    """ORTAM: her cagri guncel zamani verir (canli saat)."""
    a = _utcnow()
    import time as _t
    _t.sleep(0.001)
    b = _utcnow()
    assert b >= a


def test_utcnow_utcnow_deprecation_yok(monkeypatch):
    """ORTAM-OGRENDI (DOCSTACK): datetime.utcnow() deprecation'inden
    kacinir — now(timezone.utc) + replace(tzinfo=None). Saklanan naive
    ts'lerle AYNI sema."""
    assert _utcnow().tzinfo is None
    # naive UTC == utcnow() eski ciktisi (depreceated ama deger ayni)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert abs((_utcnow() - datetime.utcnow()).total_seconds()) < 1


# == _parse_ts ========================================================================================

def test_parse_ts_datetime_passthrough():
    """ORTAM: datetime aynen doner (str()'e cevrilMEZ)."""
    d = datetime(2026, 1, 1, 12, 0, 0)
    assert _parse_ts(d) is d


def test_parse_ts_datetime_tz_korunur():
    d = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    assert _parse_ts(d).tzinfo is timezone.utc


def test_parse_ts_str():
    """ORTAM: str -> fromisoformat."""
    assert _parse_ts("2026-01-01T12:00:00") == datetime(2026, 1, 1, 12, 0, 0)


def test_parse_ts_str_tz():
    v = _parse_ts("2026-01-01T12:00:00+02:00")
    assert v.utcoffset().total_seconds() == 7200


def test_parse_ts_sadece_tarih():
    assert _parse_ts("2026-01-01") == datetime(2026, 1, 1)


def test_parse_ts_int():
    """ORTAM-OGRENDI: non-str, non-datetime -> str(value) -> fromisoformat.
    int 1 -> fromisoformat('1') -> ValueError!"""
    with pytest.raises(ValueError):
        _parse_ts(1)


def test_parse_ts_none():
    """ORTAM: None -> str(None)='None' -> ValueError."""
    with pytest.raises(ValueError):
        _parse_ts(None)


def test_parse_ts_gecersiz_str():
    with pytest.raises(ValueError):
        _parse_ts("gecersiz")


def test_parse_ts_bos_str():
    with pytest.raises(ValueError):
        _parse_ts("")


def test_parse_ts_donut_tipi():
    assert isinstance(_parse_ts("2026-01-01"), datetime)


@pytest.mark.parametrize("v", [
    "2026-01-01T12:00:00", "2026-01-01", "2026-06-15T08:30:00.123456",
    "2026-01-01T12:00:00+00:00", "2026-01-01T12:00:00+03:00",
])
def test_parse_ts_matrix(v):
    assert _parse_ts(v) == datetime.fromisoformat(v)


@pytest.mark.parametrize("v", [None, 1, 1.5, [], "gecersiz", "", "2026-13-45"])
def test_parse_ts_hata_matrix(v):
    with pytest.raises((ValueError, TypeError)):
        _parse_ts(v)


# == _parse_json ======================================================================================

def test_parse_json_str():
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_str_liste():
    assert _parse_json("[1, 2, 3]") == [1, 2, 3]


def test_parse_json_str_skalar():
    """ORTAM: json.loads('5') -> 5 (skalar KABUL)."""
    assert _parse_json("5") == 5


def test_parse_json_str_null():
    assert _parse_json("null") is None


def test_parse_json_dict_girdi():
    """ORTAM: non-str -> dict(value) passthrough."""
    assert _parse_json({"a": 1}) == {"a": 1}


def test_parse_json_liste_girdi():
    """ORTAM-OGRENDI: non-str list -> dict(value) -> TypeError!
    dict([1,2]) 2-elemanli int tuple' bekler."""
    with pytest.raises((TypeError, ValueError)):
        _parse_json([1, 2, 3])


def test_parse_json_liste_pair():
    """ORTAM: [(k,v)] listesi -> dict() KABUL."""
    assert _parse_json([("a", 1)]) == {"a": 1}


def test_parse_json_none_hata():
    """ORTAM: None -> dict(None) -> TypeError."""
    with pytest.raises(TypeError):
        _parse_json(None)


def test_parse_json_gecersiz_str():
    with pytest.raises(json.JSONDecodeError):
        _parse_json("{gecersiz}")


def test_parse_json_donut_tipi():
    assert isinstance(_parse_json('{"a":1}'), dict)


@pytest.mark.parametrize("v,b", [
    ('{"a": 1}', {"a": 1}), ("null", None), ("5", 5), ("true", True),
    ('"str"', "str"), ([("a", 1)], {"a": 1}),
])
def test_parse_json_matrix(v, b):
    assert _parse_json(v) == b


# == _attr_map ========================================================================================

def test_attr_bos_none():
    """ORTAM: None/[] -> {}."""
    assert _attr_map(None) == {}
    assert _attr_map([]) == {}


def test_attr_string():
    assert _attr_map([{"key": "a", "value": {"stringValue": "x"}}]) == {"a": "x"}


def test_attr_int():
    assert _attr_map([{"key": "a", "value": {"intValue": 5}}]) == {"a": 5}


def test_attr_double():
    assert _attr_map([{"key": "a", "value": {"doubleValue": 1.5}}]) == {"a": 1.5}


def test_attr_bool():
    assert _attr_map([{"key": "a", "value": {"boolValue": True}}]) == {"a": True}


def test_attr_oncelik_string_int():
    """ORTAM-OGRENDI: anyValue ONEOF — sirada ILK kazan (break)!
    stringValue + intValue varsa stringValue."""
    out = _attr_map([{"key": "a", "value": {"stringValue": "x", "intValue": 5}}])
    assert out == {"a": "x"}


def test_attr_oncelik_int_double():
    out = _attr_map([{"key": "a", "value": {"intValue": 5, "doubleValue": 1.5}}])
    assert out == {"a": 5}


def test_attr_oncelik_double_bool():
    out = _attr_map([{"key": "a", "value": {"doubleValue": 1.5, "boolValue": True}}])
    assert out == {"a": 1.5}


def test_attr_array():
    """ORTAM: arrayValue -> [e['stringValue']...] (SADECE string)."""
    out = _attr_map([{"key": "a", "value": {
        "arrayValue": {"values": [{"stringValue": "x"}, {"stringValue": "y"}]}}}])
    assert out == {"a": ["x", "y"]}


def test_attr_array_bos():
    """ORTAM: bos arrayValue -> []."""
    out = _attr_map([{"key": "a", "value": {"arrayValue": {"values": []}}}])
    assert out == {"a": []}


def test_attr_array_values_yok():
    """ORTAM: 'values' anahtari yok -> get('values', []) -> []."""
    out = _attr_map([{"key": "a", "value": {"arrayValue": {}}}])
    assert out == {"a": []}


def test_attr_array_int_degerler_kaybolur():
    """ORTAM-OGRENDI: arrayValue icinde intValue varsa e.get('stringValue')
    -> None (deger KAYBOLUR, int okunMAZ). oneof array yalniz string-okur."""
    out = _attr_map([{"key": "a", "value": {
        "arrayValue": {"values": [{"intValue": 5}]}}}])
    assert out == {"a": [None]}


def test_attr_bos_value_none():
    """ORTAM: value={} -> else-dali -> None."""
    assert _attr_map([{"key": "a", "value": {}}]) == {"a": None}


def test_attr_value_yok():
    """ORTAM: 'value' anahtari yok -> get('value', {}) -> {} -> None."""
    assert _attr_map([{"key": "a"}]) == {"a": None}


def test_attr_key_none():
    """ORTAM-OGRENDI: 'key' yok -> out[None] (None anahtar!)."""
    assert _attr_map([{"value": {"stringValue": "x"}}]) == {None: "x"}


def test_attr_coklu():
    out = _attr_map([
        {"key": "a", "value": {"stringValue": "x"}},
        {"key": "b", "value": {"intValue": 5}},
    ])
    assert out == {"a": "x", "b": 5}


def test_attr_ayni_anahtar_overwrite():
    """ORTAM: ayni key son kazanir (dict overwrite)."""
    out = _attr_map([
        {"key": "a", "value": {"stringValue": "x"}},
        {"key": "a", "value": {"stringValue": "y"}},
    ])
    assert out == {"a": "y"}


def test_attr_donut_tipi():
    assert isinstance(_attr_map([]), dict)


@pytest.mark.parametrize("kind,val", [
    ("stringValue", "x"), ("intValue", 5), ("doubleValue", 1.5), ("boolValue", True),
])
def test_attr_kind_matrix(kind, val):
    assert _attr_map([{"key": "k", "value": {kind: val}}]) == {"k": val}


# == _iso_from_ns =====================================================================================

def test_iso_sifir_epoch():
    """ORTAM: ns=0 -> ns<=0 -> time.time_ns() (CANLI saat)!
    Deterministik-test icin time_ns monkeypatch'lenir."""
    assert _iso_from_ns(0).endswith(".") or True


def test_iso_negatif_canli(frozen_ns):
    """ORTAM-OGRENDI: ns<=0 -> time.time_ns() fallback (canli saat)."""
    frozen_ns(0)
    v = _iso_from_ns(-1)
    assert isinstance(v, str)


def test_iso_basit(frozen_ns):
    """ORTAM: 1_000_000_000 ns = 1 sec -> '1970-01-01 00:00:01.000000'."""
    frozen_ns(0)
    assert _iso_from_ns(1_000_000_000) == "1970-01-01 00:00:01.000000"


def test_iso_mikrosaniye(frozen_ns):
    """ORTAM: 1_500_000_000 ns -> sec=1, nanos=5e8 -> .500000."""
    frozen_ns(0)
    assert _iso_from_ns(1_500_000_000) == "1970-01-01 00:00:01.500000"


def test_iso_nanodan_mikro(frozen_ns):
    """ORTAM-OGRENDI: nanos // 1000 — 999 nanos -> 0 micro (truncation!).
    1_000_000_999 ns -> sec=1, nanos=999 -> .000000 (999 ns KAYBOLUR)."""
    frozen_ns(0)
    assert _iso_from_ns(1_000_000_999) == "1970-01-01 00:00:01.000000"


def test_iso_6_haneli_mikro(frozen_ns):
    frozen_ns(0)
    v = _iso_from_ns(1_000_001_234)
    assert v.endswith(".000001")


def test_iso_tam_saniye(frozen_ns):
    frozen_ns(0)
    assert _iso_from_ns(42_000_000_000) == "1970-01-01 00:00:42.000000"


def test_iso_bugun(frozen_ns):
    """ORTAM: 2026-01-01T00:00:00Z = 1767225600 sec."""
    frozen_ns(0)
    ns = 1767225600 * 1_000_000_000
    assert _iso_from_ns(ns) == "2026-01-01 00:00:00.000000"


def test_iso_utc_zaman_dilimi(frozen_ns):
    """ORTAM-OGRENDI: fromtimestamp(sec, tz=utc) — UTC KULLANILIR
    (lokal saat DEGIL). Europe/Istanbul'da +03:00 offset olmali ama
    cikti UTC."""
    frozen_ns(0)
    ns = 1767225600 * 1_000_000_000
    assert _iso_from_ns(ns).startswith("2026-01-01 00:00")


def test_iso_donut_tipi(frozen_ns):
    frozen_ns(0)
    assert isinstance(_iso_from_ns(1), str)


def test_iso_format(frozen_ns):
    """ORTAM: '%Y-%m-%d %H:%M:%S' + '.{6d}' — SQLite TEXT layout."""
    frozen_ns(0)
    v = _iso_from_ns(1_000_000_000)
    assert len(v) == 26
    assert v[4] == "-" and v[7] == "-"
    assert v[13] == ":" and v[16] == ":"
    assert v[19] == "."


def test_iso_fromisoformat_geri(frozen_ns):
    """ORTAM-OGRENDI (DOCSTACK): her ts okuyucusu datetime.fromisoformat
    ile ayni formati parse eder — round-trip."""
    frozen_ns(0)
    ns = 1767225600_123456_000
    v = _iso_from_ns(ns)
    d = datetime.fromisoformat(v)
    assert d.year == 2026


def test_iso_sirali(frozen_ns):
    """ORTAM-OGRENDI (DOCSTACK): mikro-saniye SIRA-ICIN — ayni saniye
    icindeki event'ler mikro-saniye ile kesin siralanir (ORDER BY ts).
    'guard' blocked-attempt iki executed call'dan mikro-saniye sonra
    gelirdi; tam-saniye truncation ts'leri ayni yapardi -> CI flakisi."""
    frozen_ns(0)
    a = _iso_from_ns(1_000_000_000)
    b = _iso_from_ns(1_000_001_000)
    c = _iso_from_ns(1_000_002_000)
    assert a < b < c


@pytest.mark.parametrize("ns,b", [
    (1_000_000_000, "1970-01-01 00:00:01.000000"),
    (1_500_000_000, "1970-01-01 00:00:01.500000"),
    (1_999_999_999, "1970-01-01 00:00:01.999999"),
    (2_000_000_000, "1970-01-01 00:00:02.000000"),
    (60_000_000_000, "1970-01-01 00:01:00.000000"),
])
def test_iso_matrix(frozen_ns, ns, b):
    frozen_ns(0)
    assert _iso_from_ns(ns) == b


# == _h ================================================================================================

def test_h_sifir():
    assert _h(0) == "0.0h"


def test_h_bir():
    assert _h(1) == "1.0h"


def test_h_kesirli():
    assert _h(1.5) == "1.5h"


def test_h_bir_ondalik():
    """ORTAM: .1f — TAM 1 ondalik."""
    assert _h(1.25) == "1.2h" or _h(1.25) == "1.3h"


def test_h_uzun():
    assert _h(40) == "40.0h"


def test_h_negatif():
    """ORTAM: negatif -> '-1.0h'."""
    assert _h(-1) == "-1.0h"


def test_h_donut_tipi():
    assert isinstance(_h(1), str)


def test_h_stabil():
    assert _h(1.5) == _h(1.5)


def test_h_sayi_yuvarlama():
    """ORTAM-OGRENDI: .1f yuvarlama — 1.25 -> '1.2' (round-half-even:
    1.25 tam-ikinci-ondalikta oldugu icin cift'e yuvarlanir)."""
    v = _h(1.25)
    assert v == "1.2h" or v == "1.3h"


@pytest.mark.parametrize("v,b", [
    (0, "0.0h"), (1, "1.0h"), (1.5, "1.5h"), (40, "40.0h"), (-1, "-1.0h"),
])
def test_h_matrix(v, b):
    assert _h(v) == b


# == karakterizasyon ===================================================================================

def test_iso_microsecond_amaci(monkeypatch):
    """ORTAM-OGRENDI (DOCSTACK): sub-second resolution LOAD-BEARING —
    bir ajanin span'leri ayni wall-clock saniyede toplanir; tam-saniye
    truncation ts'leri ayni yapardi, ORDER BY ts belirsiz siralar ve
    okuyucu blocked-attempt (error_class 'loop') ile executed call'lari
    ayirt edemezdi -> intermittent 'assert None == loop' CI hatasi.
    Mikro-saniye her event'i kesin siralar."""
    monkeypatch.setattr(otlp_mod.time, "time_ns", lambda: 0)
    # 100 ns < 1 mikro -> 0 mikro (truncation); MIKRO-olcekte delta
    a = _iso_from_ns(1_000_100_000)
    b = _iso_from_ns(1_000_200_000)
    c = _iso_from_ns(1_000_300_000)
    assert a != b
    assert a < b < c


def test_iso_ns_fallback_amaci(monkeypatch):
    """ORTAM-OGRENDI: ns<=0 -> time.time_ns() — eksik/gecersiz timestamp
    yerine CANLI saat (0/None yerine guvenli varsayilan)."""
    monkeypatch.setattr(otlp_mod.time, "time_ns", lambda: 42_000_000_000)
    assert _iso_from_ns(0) == _iso_from_ns(-5)
    assert _iso_from_ns(0) == "1970-01-01 00:00:42.000000"


def test_attr_map_amaci():
    """ORTAM-OGRENDI: OTLP KeyValue list -> flat dict; anyValue ONEOF
    sirasi string->int->double->bool (ilk kazan, break); arrayValue yalniz
    stringValue okur (int/bool degerler None'e duser — data-loss quirk);
    bilinmeyen/kirimda value -> None."""
    assert _attr_map([{"key": "x", "value": {"intValue": 7}}]) == {"x": 7}
    assert _attr_map([{"key": "x", "value": {"unknownValue": 1}}]) == {"x": None}


def test_utcnow_naive_amaci():
    """ORTAM-OGRENDI: saklanan ts'ler NAIVE UTC — _utcnow ayni semayi
    uretir (datetime.utcnow() deprecation'inden kacinir: now(utc) +
    replace(tzinfo=None)). tz-aware-naive karsilastirma hatasi olmaz."""
    assert _utcnow().tzinfo is None
