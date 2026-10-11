"""swarmax.console._sparkline + _sparkline_canvas + _activity_canvas dal-kesen testleri (LEED).

Kural-1: mevcut dosyalara DOKUNULMADI, SADECE bu yeni dosya eklendi.
Kural-4: saf in-memory (Canvas yazilim-rasterizer — dis cagri YOK).
SVG sparkline + RGBA canvas sparkline + 24h aktivite canvas.
"""
import sys

import pytest

sys.path.insert(0, "src")
from swarmax.console import _sparkline, _sparkline_canvas  # noqa: E402
from swarmax.console import _activity_canvas  # noqa: E402
from swarmax.metrics.charts import Canvas  # noqa: E402


# == _sparkline: temel ============================================================================

def test_bos_values():
    """ORTAM: bos -> 'no data' span."""
    assert _sparkline([]) == "<span class='muted'>no data</span>"


def test_hepsi_sifir():
    """ORTAM: max <= 0 -> 'no data'."""
    assert _sparkline([0, 0, 0]) == _sparkline([])


def test_negatif_values():
    """ORTAM: max <= 0 -> 'no data' (negatif)."""
    assert _sparkline([-1, -2]) == "<span class='muted'>no data</span>"


def test_tek_deger():
    r = _sparkline([5])
    assert "<svg" in r


def test_svg_etiketi():
    assert _sparkline([1, 2]).startswith("<svg ")


def test_svg_kapanis():
    assert _sparkline([1, 2]).endswith("</svg>")


def test_svg_width():
    assert "width='260'" in _sparkline([1, 2])


def test_svg_height():
    assert "height='40'" in _sparkline([1, 2])


def test_custom_width():
    assert "width='100'" in _sparkline([1, 2], w=100)


def test_custom_height():
    assert "height='50'" in _sparkline([1, 2], h=50)


def test_polyline_var():
    assert "<polyline" in _sparkline([1, 2, 3])


def test_fill_none():
    assert "fill='none'" in _sparkline([1, 2])


def test_stroke_color():
    assert "stroke='#58a6ff'" in _sparkline([1, 2])


def test_custom_color():
    assert "stroke='#ff0000'" in _sparkline([1, 2], color="#ff0000")


def test_returns_str():
    assert isinstance(_sparkline([1, 2]), str)


# == _sparkline: noktalar =========================================================================

def test_iki_deger_noktalar():
    """ORTAM: x = i*w // (len-1)."""
    r = _sparkline([0, 10], w=260)
    assert "points='0," in r and "260," in r


def test_uc_deger_noktalar():
    r = _sparkline([0, 5, 10], w=300)
    assert "points='0," in r


def test_tek_deger_nokta():
    """ORTAM: len-1 = 0 -> max(1,0) = 1 -> x=0."""
    r = _sparkline([5], w=100)
    assert "points='0," in r


def test_y_degerleri():
    """ORTAM: y = h - int(v/vmax * (h-4)) - 2."""
    r = _sparkline([0, 10], h=40)
    # v=0 -> y = 40-0-2 = 38; v=10 -> y = 40-36-2 = 2
    assert "38" in r and "2" in r


def test_y_max_deger():
    r = _sparkline([10, 10], h=40)
    assert "points='0,2 260,2" in r or "points='0,2" in r


def test_artan_values():
    r1 = _sparkline([1, 2, 3, 4, 5])
    r2 = _sparkline([5, 4, 3, 2, 1])
    assert r1 != r2


def test_repeatable():
    assert _sparkline([1, 2, 3]) == _sparkline([1, 2, 3])


def test_ondalik_values():
    assert "<svg" in _sparkline([0.5, 1.5, 2.5])


def test_buyuk_values():
    assert "<svg" in _sparkline([1e6, 2e6])


# == _sparkline_canvas ==============================================================================

def test_canvas_bos_none():
    """ORTAM: bos -> None."""
    assert _sparkline_canvas([]) is None


def test_canvas_hepsi_sifir_none():
    assert _sparkline_canvas([0, 0]) is None


def test_canvas_tek_deger():
    r = _sparkline_canvas([5])
    assert r is not None


def test_canvas_return_tuple():
    """ORTAM: (bytes, w, h)."""
    r = _sparkline_canvas([1, 2], w=100, h=50)
    assert isinstance(r, tuple) and len(r) == 3


def test_canvas_boyut():
    data, w, h = _sparkline_canvas([1, 2], w=100, h=50)
    assert w == 100 and h == 50


def test_canvas_bytes():
    data, w, h = _sparkline_canvas([1, 2], w=10, h=10)
    assert isinstance(data, (bytes, bytearray))
    assert len(data) == w * h * 4  # RGBA


def test_canvas_custom_color():
    d1, _, _ = _sparkline_canvas([1, 2], color="#ff0000")
    d2, _, _ = _sparkline_canvas([1, 2], color="#00ff00")
    assert d1 != d2


def test_canvas_default_color():
    d1, _, _ = _sparkline_canvas([1, 2])
    d2, _, _ = _sparkline_canvas([1, 2], color="#58a6ff")
    assert d1 == d2


def test_canvas_bg_renk():
    """ORTAM: bg=(13,17,23) — ilk-piksol bg."""
    data, w, h = _sparkline_canvas([0, 10], w=4, h=4)
    assert tuple(data[:3]) == (13, 17, 23)


def test_canvas_rgba_alpha():
    data, w, h = _sparkline_canvas([0, 10], w=2, h=2)
    assert data[3] == 255


def test_canvas_repeatable():
    assert _sparkline_canvas([1, 2, 3]) == _sparkline_canvas([1, 2, 3])


def test_canvas_ayni_geometri():
    """ORTAM: canvas SVG ile ayni x-geometri."""
    svg = _sparkline([0, 10], w=100, h=50)
    canv = _sparkline_canvas([0, 10], w=100, h=50)
    assert canv is not None


# == _activity_canvas ================================================================================

def test_activity_bos():
    """ORTAM: bos-list -> maxv=1, hepsi 0-yukseklik."""
    r = _activity_canvas([])
    assert isinstance(r, (bytes, bytearray))


def test_activity_bytes():
    assert isinstance(_activity_canvas([(0, 5, 0)]), (bytes, bytearray))


def test_activity_boyut():
    w, h = 300, 120
    r = _activity_canvas([(0, 5, 0)], w=w, h=h)
    assert len(r) == w * h * 4


def test_activity_bg():
    r = _activity_canvas([], w=4, h=4)
    assert tuple(r[:3]) == (13, 17, 23)


def test_activity_tek_saat():
    r1 = _activity_canvas([(0, 5, 0)], w=100, h=120)
    r2 = _activity_canvas([], w=100, h=120)
    assert r1 != r2


def test_activity_24_saat():
    hourly = [(h, h, 0) for h in range(24)]
    assert isinstance(_activity_canvas(hourly), (bytes, bytearray))


def test_activity_error_bar():
    """ORTAM: hata-cubugu farkli-renk cizilir."""
    r1 = _activity_canvas([(0, 5, 0)])
    r2 = _activity_canvas([(0, 5, 3)])
    assert r1 != r2


def test_activity_sifir_tasks():
    """ORTAM: tasks=0 -> hicbirsey cizilmez (hb=0)."""
    r1 = _activity_canvas([(0, 0, 0)])
    r2 = _activity_canvas([])
    assert r1 == r2


def test_activity_maxv_buyuk():
    """ORTAM: bar-yuksekligi ORANSAL (60*tasks/maxv) — mutlak DEGIL."""
    r1 = _activity_canvas([(0, 100, 0), (1, 50, 0)])
    r2 = _activity_canvas([(0, 100, 0)])
    assert r1 != r2


def test_activity_oransal_ayni():
    """ORTAM: ayni-oran -> ayni canvas (100/100 = 1/1 = 60)."""
    assert _activity_canvas([(0, 100, 0)]) == _activity_canvas([(0, 1, 0)])


def test_activity_default_h():
    """ORTAM: default h=120."""
    r = _activity_canvas([(0, 5, 0)])
    assert len(r) % (120 * 4) == 0


def test_activity_repeatable():
    assert _activity_canvas([(0, 5, 1)]) == _activity_canvas([(0, 5, 1)])


def test_activity_out_of_range_hour():
    """ORTAM: hours dict sadece verilen saatler; range(24) bosluk 0."""
    r = _activity_canvas([(23, 5, 0)])
    assert isinstance(r, (bytes, bytearray))


@pytest.mark.parametrize("n", [0, 1, 12, 24])
def test_activity_matrix(n):
    hourly = [(i % 24, i + 1, i % 3) for i in range(n)]
    assert isinstance(_activity_canvas(hourly), (bytes, bytearray))
