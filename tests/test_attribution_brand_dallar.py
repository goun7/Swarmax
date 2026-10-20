"""69-Swarmax attribution._utcnow/_parse/_fallback + gen_brand._lerp/_pt + build_pdf_package._inline/_table dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (saf fonksiyonlar; network/DB YASAK).

ORTAM-ANATOMI:
- _utcnow(): datetime.now(timezone.utc).replace(tzinfo=None) — NAIVE!
- _parse(v): datetime.fromisoformat(str(v))
- _fallback(agent_id, note): {suggested_agent_id, suggested_step:
  'insufficient trace', confidence: 0.30, method: METHOD, note}
- _lerp(c0, c1, t): tuple(int(round(a+(b-a)*t)) for a,b in zip(c0,c1))
- _pt(angle_deg, radius): (CX + radius*cos(rad), CY + radius*sin(rad))
- _inline(s): html.escape(quote=False) + code-stash + **bold** + *italic*
  + [text](url)
- _table(lines, out): markdown table -> HTML (|cells|, ayirici satir
  zorunlu); <2 satir veya ayirici yoksa <p> fallback
"""
import datetime as _dt
import math
import sys

import pytest

sys.path.insert(0, ".")
sys.path.insert(0, "src")
sys.path.insert(0, "scripts")
from build_pdf_package import _inline, _table  # noqa: E402
from gen_brand import CX, CY, INNER_R, N, OUTER_R, _lerp, _pt  # noqa: E402
from swarmax.attribution import METHOD, _fallback, _parse, _utcnow  # noqa: E402


# == _utcnow ==========================================================================================

def test_utcnow_naive():
    """ORTAM-OGRENDI (KRITIK-FARK): replace(tzinfo=None) — NAIVE datetime!
    Kredent/Ostrakon/Veridrome/AnswRank'in aksine tz-aware DEGIL (DB
    tarihi naive tutulur — SQLite adaptasyonu)."""
    assert _utcnow().tzinfo is None


def test_utcnow_donut_tipi():
    assert isinstance(_utcnow(), _dt.datetime)


def test_utcnow_yakin():
    """ORTAM: UTC'ye yakin (<5 sn) — yerel saate DEGIL."""
    now = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    assert abs((now - _utcnow()).total_seconds()) < 5


def test_utcnow_artar():
    a = _utcnow()
    import time as _t
    _t.sleep(0.002)
    assert _utcnow() >= a


def test_utcnow_utc_degeri():
    """ORTAM: deger UTC (yerel +3 DEGIL) — tz-aware karsilastirma."""
    aware = _utcnow().replace(tzinfo=_dt.timezone.utc)
    assert abs((_dt.datetime.now(_dt.timezone.utc) - aware).total_seconds()) < 5


# == _parse ============================================================================================

def test_parse_basit():
    """ORTAM: fromisoformat."""
    assert _parse("2026-01-01T12:00:00") == _dt.datetime(2026, 1, 1, 12, 0, 0)


def test_parse_z_aware():
    """ORTAM: 'Z'/offset KABUL — fromisoformat."""
    assert _parse("2026-01-01T12:00:00Z") == _dt.datetime(
        2026, 1, 1, 12, tzinfo=_dt.timezone.utc)


def test_parse_offset():
    v = _parse("2026-01-01T12:00:00+02:00")
    assert v.utcoffset() == _dt.timedelta(hours=2)


def test_parse_mikro():
    assert _parse("2026-01-01T12:00:00.123456") == _dt.datetime(
        2026, 1, 1, 12, 0, 0, 123456)


def test_parse_tarih():
    """ORTAM: sadece tarih."""
    assert _parse("2026-01-01") == _dt.datetime(2026, 1, 1)


def test_parse_py310_normalize_sw_iso10():
    """SW-ISO10 pin: py3.10-fromisoformat 'Z'-ve-basic-format-RED-ederdi.

    Uretim-hatasi: _parse-3.10-target'inda-gercek-OTLP-UTC-zaman-damgalarini
    ( '...Z')-ve-basic-formatlari-ADMIN-edemezdi ( 3.11+-genisletildi).
    Normalize-sonrasi-uc-modul-de-ayni-sonucu-vermeli ( attribution,
    console, pipeline)."""
    from swarmax import attribution as _attr
    from swarmax import console as _cons
    from swarmax import pipeline as _pipe
    for f in (_attr._parse, _cons._parse, _pipe._parse_ts):
        assert f("2026-01-01T12:00:00Z") == _dt.datetime(
            2026, 1, 1, 12, tzinfo=_dt.timezone.utc)
        assert f("20260101") == _dt.datetime(2026, 1, 1)
        assert f("20260101T120000") == _dt.datetime(2026, 1, 1, 12, 0, 0)


def test_parse_str_cast():
    """ORTAM: str(v) — int/None KABUL edilip stringlesir."""
    assert _parse(20260101) == _dt.datetime(2026, 1, 1)


def test_parse_none_hata():
    """ORTAM: str(None)='None' -> ValueError."""
    with pytest.raises(ValueError):
        _parse(None)


def test_parse_gecersiz_hata():
    with pytest.raises(ValueError):
        _parse("gecersiz")


def test_parse_uzun_form():
    """ORTAM: ISO-8601 'T' ayirici."""
    assert _parse("20260101T120000") == _dt.datetime(2026, 1, 1, 12, 0, 0)


@pytest.mark.parametrize("v,b", [
    ("2026-01-01", _dt.datetime(2026, 1, 1)),
    ("2026-01-01T12:00:00", _dt.datetime(2026, 1, 1, 12)),
    ("2026-01-01T12:00:00Z", _dt.datetime(2026, 1, 1, 12, tzinfo=_dt.timezone.utc)),
])
def test_parse_matrix(v, b):
    assert _parse(v) == b


# == _fallback =========================================================================================

def test_fallback_yapi():
    """ORTAM: {suggested_agent_id, suggested_step, confidence, method, note}."""
    d = _fallback("a1", "iz yetersiz")
    assert set(d) == {"suggested_agent_id", "suggested_step", "confidence",
                      "method", "note"}


def test_fallback_agent_id():
    assert _fallback("a1", "n")["suggested_agent_id"] == "a1"


def test_fallback_step():
    """ORTAM-OGRENDI: 'insufficient trace' — sabit fallback mesaji."""
    assert _fallback("a1", "n")["suggested_step"] == "insufficient trace"


def test_fallback_confidence():
    """ORTAM: confidence 0.30 (düsük-güven sabit)."""
    assert _fallback("a1", "n")["confidence"] == 0.30


def test_fallback_method():
    """ORTAM: method=METHOD ('swarmax.heuristic.v1 ...')."""
    assert _fallback("a1", "n")["method"] == METHOD
    assert "swarmax.heuristic.v1" in METHOD


def test_fallback_note():
    assert _fallback("a1", "aciklama")["note"] == "aciklama"


def test_fallback_bos_note():
    assert _fallback("a1", "")["note"] == ""


def test_fallback_deterministik():
    assert _fallback("a1", "n") == _fallback("a1", "n")


def test_fallback_agent_degisir():
    assert _fallback("a1", "n")["suggested_agent_id"] != \
        _fallback("a2", "n")["suggested_agent_id"]


def test_fallback_donut_dict():
    assert isinstance(_fallback("a1", "n"), dict)


def test_fallback_stabil():
    d = _fallback("x", "y")
    assert d == _fallback("x", "y")


@pytest.mark.parametrize("aid,note", [("a1", "n1"), ("a2", ""), ("", "n3")])
def test_fallback_matrix(aid, note):
    d = _fallback(aid, note)
    assert d["suggested_agent_id"] == aid and d["note"] == note


# == _lerp =============================================================================================

def test_lerp_orta():
    """ORTAM: tuple(int(round(a+(b-a)*t)) ...)."""
    assert _lerp((0, 0, 0), (100, 200, 255), 0.5) == (50, 100, 128)


def test_lerp_t0():
    """ORTAM: t=0 -> c0."""
    assert _lerp((10, 20), (30, 40), 0.0) == (10, 20)


def test_lerp_t1():
    """ORTAM: t=1 -> c1."""
    assert _lerp((10, 20), (30, 40), 1.0) == (30, 40)


def test_lerp_donut_tuple():
    assert isinstance(_lerp((1,), (2,), 0.5), tuple)


def test_lerp_int_donut():
    """ORTAM: hep INT (round)."""
    v = _lerp((0.7,), (1.7,), 0.5)
    assert all(isinstance(x, int) for x in v)


def test_lerp_yari_karisik():
    """ORTAM: round(127.5) -> 128 (banker's rounding: cift sayiya)."""
    assert _lerp((0,), (255,), 0.5) == (128,)


def test_lerp_uzunluk_farkli():
    """ORTAM-OGRENDI: zip — kisa tuple uzunlugunu belirler (fazla atlanir)."""
    assert _lerp((0, 0, 0, 0), (10, 20), 1.0) == (10, 20)


def test_lerp_bos():
    """ORTAM: iki bos tuple -> ()."""
    assert _lerp((), (), 0.5) == ()


def test_lerp_negatif():
    assert _lerp((-10,), (10,), 0.5) == (0,)


def test_lerp_t_disinda():
    """ORTAM: t>1 EXTRAPOLASYON (clamp YOK)."""
    assert _lerp((0,), (10,), 2.0) == (20,)
    assert _lerp((0,), (10,), -1.0) == (-10,)


def test_lerp_stabil():
    assert _lerp((1, 2), (3, 4), 0.3) == _lerp((1, 2), (3, 4), 0.3)


@pytest.mark.parametrize("c0,c1,t,b", [
    ((10, 20), (30, 40), 0.0, (10, 20)),
    ((10, 20), (30, 40), 1.0, (30, 40)),
    ((0, 0, 0), (100, 200, 255), 0.5, (50, 100, 128)),
])
def test_lerp_matrix(c0, c1, t, b):
    assert _lerp(c0, c1, t) == b


# == _pt ===============================================================================================

def test_pt_yukari():
    """ORTAM: -90 derece = YUKARI (cos(-90°)=0, sin=-1)."""
    x, y = _pt(-90, 100)
    assert x == pytest.approx(CX)
    assert y == pytest.approx(CY - 100)


def test_pt_sag():
    """ORTAM: 0 derece = SAG."""
    x, y = _pt(0, 100)
    assert x == pytest.approx(CX + 100)
    assert y == pytest.approx(CY)


def test_pt_asagi():
    x, y = _pt(90, 100)
    assert x == pytest.approx(CX)
    assert y == pytest.approx(CY + 100)


def test_pt_sol():
    x, y = _pt(180, 100)
    assert x == pytest.approx(CX - 100)
    assert y == pytest.approx(CY)


def test_pt_sifir_radius():
    """ORTAM: radius 0 -> merkez."""
    assert _pt(45, 0) == (CX, CY)


def test_pt_donut_tuple():
    assert isinstance(_pt(0, 1), tuple)


def test_pt_uzunluk():
    assert len(_pt(30, 50)) == 2


def test_pt_float():
    """ORTAM: float donut (round YOK — aksine _lerp)."""
    v = _pt(45, 100)
    assert isinstance(v[0], float)


def test_pt_cember_uzerinde():
    """ORTAM: tum acilar ayni radius'ta merkezle ayni uzaklikta."""
    for aci in range(0, 360, 30):
        x, y = _pt(aci, 75.0)
        assert math.hypot(x - CX, y - CY) == pytest.approx(75.0)


def test_pt_derece_radyan():
    """ORTAM: math.radians — 360 = 0 (tam tur)."""
    assert _pt(360, 10) == pytest.approx(_pt(0, 10))


def test_pt_negatif_aci():
    """ORTAM: -90 = 270 (yukari)."""
    assert _pt(-90, 10) == pytest.approx(_pt(270, 10))


def test_pt_stabil():
    assert _pt(45, 100) == _pt(45, 100)


@pytest.mark.parametrize("aci,r,bx,by", [
    (0, 100, CX + 100, CY), (90, 100, CX, CY + 100),
    (180, 100, CX - 100, CY), (270, 100, CX, CY - 100),
])
def test_pt_matrix(aci, r, bx, by):
    x, y = _pt(aci, r)
    assert x == pytest.approx(bx)
    assert y == pytest.approx(by)


# == _inline ===========================================================================================

def test_inline_duz_metin():
    """ORTAM: duz metin OLDUGU GIBI."""
    assert _inline("merhaba") == "merhaba"


def test_inline_bos():
    assert _inline("") == ""


def test_inline_bold():
    """ORTAM: **x** -> <strong>x</strong>."""
    assert _inline("**kalin**") == "<strong>kalin</strong>"


def test_inline_bold_ic_metin():
    assert _inline("a **b** c") == "a <strong>b</strong> c"


def test_inline_italic():
    """ORTAM: *x* -> <em>x</em> (kelime-siniri lookaround ile)."""
    assert _inline("italic *x*") == "italic <em>x</em>"


def test_inline_italic_kelime_icinde_degil():
    """ORTAM-OGRENDI: (?<![\w*])\*(?![\w*]) — kelime icinde * ESLEMEZ."""
    assert _inline("a*b*c") == "a*b*c"


def test_inline_italic_bold_once():
    """ORTAM-OGRENDI: ** once calisir -> *italic* SONRA; ama bold icindeki
    *b* kelime-siniri lookaround'u yuzunden ESLEMEZ (solunda 'a' word var)
    -> <strong>a*b* c</strong> (icte italic OLMAZ)."""
    assert _inline("**a*b* c**") == "<strong>a*b* c</strong>"


def test_inline_bold_icine_italic():
    """ORTAM: ** lazy icte * esler."""
    v = _inline("**x *y* z**")
    assert "<strong>" in v and "<em>" in v


def test_inline_link():
    """ORTAM: [text](url) -> <a href="url">text</a>."""
    assert _inline("[link](http://a)") == '<a href="http://a">link</a>'


def test_inline_link_metin():
    assert _inline("[merhaba](/x)") == '<a href="/x">merhaba</a>'


def test_inline_link_bosluklu_url():
    """ORTAM-OGRENDI: [^)\s]+ — url'de BOSLUK OLAMAZ."""
    assert _inline("[a](http://b c)") == '[a](http://b c)'


def test_inline_kod_korunur():
    """ORTAM-OGRENDI: `x` -> <code>x</code> STASH — icindeki */_ EMPHASIS
    regex'lerine YEM OLMAZ (once stash, son yerine koy)."""
    assert _inline("kod `a*b`") == "kod <code>a*b</code>"


def test_inline_kod_italic_korunur():
    assert _inline("`*x*`") == "<code>*x*</code>"


def test_inline_kod_bold_korunur():
    assert _inline("`**x**`") == "<code>**x**</code>"


def test_inline_coklu_kod():
    """ORTAM: birden fazla kod span'i sirayla stash."""
    v = _inline("`a` ve `b`")
    assert v == "<code>a</code> ve <code>b</code>"


def test_inline_escape_html():
    """ORTAM: html.escape(quote=False) — < > & escape, TIRNAK DEGIL."""
    assert _inline("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"


def test_inline_tirnak_escape_yok():
    """ORTAM-OGRENDI: quote=False — " escape EDILMEZ (attribute disi)."""
    assert _inline('"x"') == '"x"'


def test_inline_ampersand():
    assert _inline("a & b") == "a &amp; b"


def test_inline_kod_icinde_html_escape():
    """ORTAM: escape KOD-DAN ONCE — kod icindeki < de escape."""
    assert _inline("`a<b`") == "<code>a&lt;b</code>"


def test_inline_karisik():
    """ORTAM: tum kurallar birlikte."""
    v = _inline("**a** ve *b* ve [c](d) ve `e*f`")
    assert v == "<strong>a</strong> ve <em>b</em> ve " \
               '<a href="d">c</a> ve <code>e*f</code>'


def test_inline_donut_tipi():
    assert isinstance(_inline("x"), str)


def test_inline_stabil():
    assert _inline("**a** *b* `c`") == _inline("**a** *b* `c`")


@pytest.mark.parametrize("s,b", [
    ("", ""), ("düz", "düz"), ("**k**", "<strong>k</strong>"),
    ("*i*", "<em>i</em>"), ("a *i*", "a <em>i</em>"),
    ("[t](u)", '<a href="u">t</a>'), ("`c`", "<code>c</code>"),
    ("a & b", "a &amp; b"),
])
def test_inline_matrix(s, b):
    assert _inline(s) == b


# == _table ============================================================================================

def test_table_gecerli():
    """ORTAM: |h1|h2| + ayirici + satir -> HTML table."""
    out = []
    _table(["|a|b|", "|---|---|", "|1|2|"], out)
    v = "".join(out)
    assert "<table>" in v and "<th>a</th>" in v and "<td>1</td>" in v


def test_table_header():
    out = []
    _table(["|a|b|", "|---|---|"], out)
    assert "<thead>" in "".join(out)


def test_table_body_satir():
    out = []
    _table(["|a|", "|---|", "|1|"], out)
    assert "<tbody>" in "".join(out) and "<td>1</td>" in "".join(out)


def test_table_eksik_hucre_doldur():
    """ORTAM-OGRENDI: cells += [''] * (len(header)-len(cells)) — eksik
    hucreler BOS string ile doldurulur."""
    out = []
    _table(["|a|b|c|", "|---|---|---|", "|1|"], out)
    v = "".join(out)
    assert "<td>1</td><td></td><td></td>" in v


def test_table_fazla_hucre_kesilmez():
    """ORTAM: fazla hucreler KORUNUR (header'dan fazla olabilir)."""
    out = []
    _table(["|a|", "|---|", "|1|2|3|"], out)
    assert "<td>1</td><td>2</td><td>3</td>" in "".join(out)


def test_table_inline_uygulanir():
    """ORTAM: hucrelerde _inline — **bold** calisir."""
    out = []
    _table(["|a|", "|---|", "|**x**|"], out)
    assert "<td><strong>x</strong></td>" in "".join(out)


def test_table_baslik_inline():
    out = []
    _table(["|**h**|", "|---|"], out)
    assert "<th><strong>h</strong></th>" in "".join(out)


def test_table_boslukKirpma():
    """ORTAM: c.strip() — hucre bosluklari kirpilir."""
    out = []
    _table(["| a |", "|---|", "| 1 |"], out)
    v = "".join(out)
    assert "<th>a</th>" in v and "<td>1</td>" in v


def test_table_tek_satir_fallback():
    """ORTAM-OGRENDI: <2 satir -> <p> fallback (tablo DEGIL)."""
    out = []
    _table(["|a|b|"], out)
    v = "".join(out)
    assert "<table>" not in v
    assert "<p>" in v


def test_table_ayirici_yok_fallback():
    """ORTAM-OGRENDI: 2. satir ayirici DEGIL -> <p> fallback."""
    out = []
    _table(["|a|b|", "|1|2|"], out)
    assert "<table>" not in "".join(out)


def test_table_fallback_inline():
    """ORTAM: fallback <p> icinde _inline + | kirpilir."""
    out = []
    _table(["|**a**|"], out)
    assert "<p><strong>a</strong></p>" in "".join(out)


def test_table_fallback_pipe_kirpma():
    """ORTAM: l.strip().strip('|') — bas/son | kirpilir."""
    out = []
    _table(["|a|"], out)
    assert "<p>a</p>" in "".join(out)


def test_table_bos():
    """ORTAM: bos liste -> hicbir sey."""
    out = []
    _table([], out)
    assert out == []


def test_table_ayirici_noktali():
    """ORTAM: ':---:' merkez-hizali ayirici KABUL."""
    out = []
    _table(["|a|", "|:---:|", "|1|"], out)
    assert "<table>" in "".join(out)


def test_table_ayirici_sag():
    out = []
    _table(["|a|", "|---:|", "|1|"], out)
    assert "<table>" in "".join(out)


def test_table_yan_etki_none():
    """ORTAM: out listesini degistirir, None doner."""
    out = []
    assert _table(["|a|", "|---|"], out) is None
    assert len(out) > 0


def test_table_satir_filtresi():
    """ORTAM: sadece | ile baslayanlar satir sayilir."""
    out = []
    _table(["|a|", "|---|", "düz metin", "|1|"], out)
    v = "".join(out)
    assert "<table>" in v
    assert "düz metin" not in v


def test_table_girdi_korunur():
    """ORTAM: girdiyi DEGISTIRMEZ."""
    lines = ["|a|", "|---|", "|1|"]
    once = list(lines)
    _table(lines, [])
    assert lines == once


# == karakterizasyon ===================================================================================

def test_utcnow_amaci():
    """ORTAM-OGRENDI (DOCSTACK): UTC zamanini NAIVE olarak dondurur
    (replace(tzinfo=None)) — SQLite TIMESTAMP kolonlari tz-aware
    KABUL ETMEZ; sistem-geneli tutarli UTC depolama karari. TZ-AWARE
   reposlardan (Kredent/Veridrome/AnswRank) bilincli FARK."""
    assert _utcnow().tzinfo is None


def test_fallback_amaci():
    """ORTAM-OGRENDI: deterministik dusuk-guven fallback — LLM yargici
    YOK, kara-kutu YOK ('The ladder is deterministic and auditable').
    confidence 0.30 sabit; suggested_step 'insufficient trace'; method
    METHOD (swarmax.heuristic.v1 Who&When-aligned E14/E15)."""
    d = _fallback("a1", "iz yetersiz")
    assert d["confidence"] == 0.30
    assert d["suggested_step"] == "insufficient trace"


def test_inline_amaci():
    """ORTAM-OGRENDI (DOCSTACK): markdown-inline -> HTML — html.escape
    ONCE (XSS korumasi; quote=False cunku attribute disinda), kod-span
    STASH (backtick icindeki */_ emphasis regex'lerine yem olmasin),
    **bold** lazy (nested tag'ler), *italic* kelime-siniri lookaround
    (kelime-ici yildiz ESLEMEZ), [text](url) link (url'de bosluk YASAK)."""
    assert _inline("`*x*`") == "<code>*x*</code>"
    assert _inline("a*b*c") == "a*b*c"


def test_table_amaci():
    """ORTAM-OGRENDI: markdown table -> HTML; ayirici satir (2.) ZORUNLU
    (|---| veya :---:); <2 satir veya ayirici yoksa <p> fallback;
    eksik hucreler '' ile DOLDURULUR (header uzunluguna); fazla hucreler
    KORUNUR; hucrelerde _inline uygulanir."""
    out = []
    _table(["|a|b|", "|---|---|", "|1|"], out)
    assert "<td>1</td><td></td>" in "".join(out)


def test_lerp_amaci():
    """ORTAM-OGRENDI: renk interpolasyonu — int(round(...)) ile bayt
    araligina (0-255) yuvarlama; zip ile KISA tuple uzunlugu belirler;
    t>1 extrapolasyon (clamp YOK); banker's-rounding (127.5->128)."""
    assert _lerp((0, 0, 0), (100, 200, 255), 0.5) == (50, 100, 128)
