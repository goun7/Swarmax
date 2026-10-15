"""test_charts_dallar.py — swarmax/metrics/charts.py dal-kesen test suite.

ORTAM-ANATOMI (src/swarmax/metrics/charts.py, 84 satir) — public API:
  Canvas (L14)            -> __slots__ ("w","h","buf"); RGBA8 row-major tuval
  Canvas.__init__ (L20)   -> w<=0|h<=0 -> ValueError("empty canvas"); bg dolgu
  Canvas.start (L27)      -> canli buffer'i döndürür (dogrudan piksel erisimi)
  Canvas._px (L31)        -> OZEL: sinir disi koordinatlari sessizce kirpar
  Canvas.hline (L36)      -> yatay cizgi; x0>x1 normalize (min/max)
  Canvas.vline (L40)      -> dikey cizgi; y0>y1 normalize (min/max)
  Canvas.line (L44)       -> Bresenham dogru parcasi (tüm oktantlar)
  Canvas.line_pts (L63)   -> polyline (sparkline); zip(pts, pts[1:])
  Canvas.rect (L69)       -> dolu dikdortgen
  Canvas.disc (L75)       -> dolu disk (dx*dx+dy*dy <= r*r)
  Canvas.bytes (L82)      -> bytes(buf) anlik olmayan kopya

DAL HARITASI (D1..D45): her public dal icin basari/basarisiz/sinir testi:
  __init__:
    D1  w<=0 -> ValueError("empty canvas")
    D2  h<=0 -> ValueError("empty canvas")
    D3  1x1 minimum gecerli tuval
    D4  gecerli w,h -> w/h saklanir, len(buf) == w*h*4
    D5  bg her piksele (r,g,b) olarak yedirilir
    D6  alfa her pikselde 255 (on-composited, §5 docstring)
    D7  bg 4 elemanli -> ValueError (unpack kisir)
  start:
    D8  start() canli buffer'dir (is ile ayni), bytearray tipi
    D9  start() uzerinde degisiklik canvas'i etkiler (dogrudan cizim)
  _px_kirpma (public cizimler uzerinden):
    D10 sinir disi x/y -> IndexError DEGIL, sessizce atlanir
  hline:
    D11 soldan saga (x0<x1) inclusive -> (x1-x0+1) piksel
    D12 saga-soldan (x0>x1) normalize -> ayni piksel kumesi
    D13 y tuval disinda -> hic piksel yok
    D14 kismi sagdan tasma -> w-1'de kirpilir
    D15 negatif x0 -> 0'da kirpilir
  vline:
    D16 yukaridan asagi (y0<y1) inclusive
    D17 asagi-yukari (y0>y1) normalize -> ayni pikseller
    D18 x tuval disinda -> hic piksel yok
    D19 kismi alttan tasma -> h-1'de kirpilir
  line (Bresenham):
    D20 tek nokta (x0==x1 ve y0==y1) -> tam 1 piksel
    D21 yatay -> (x1-x0+1) piksel
    D22 dikey -> (y1-y0+1) piksel
    D23 kosegen (0,0)->(4,4) -> ana kosegede 5 piksel, uçlar dahil
    D24 ters yon (4,4)->(0,0) -> ileri yonle AYNI piksel kumesi (simetri)
    D25 dik egim (steep) -> uçlar + ara noktalar, hepsi sinir icinde
    D26 her iki uç da tuval disinda -> hata YOK, 0 piksel
    D27 tek uç tuval disinda (isvar) -> kismi yol, sadece sinir icinde
    D28 negatif koordinatli isvar -> sadece 0+ kismi cizilir
  line_pts:
    D29 2 nokta -> line() ile ayni pikseller
    D30 3+ noktal polyline -> tum parcalar cizilir
    D31 tek nokta -> HIC piksel cizilmez (zip bos)
    D32 bos liste -> hata YOK, 0 piksel
  rect:
    D33 tamamen icinde -> w*h piksel
    D34 w=0 -> 0 piksel; h=0 -> 0 piksel
    D35 negatif x,y -> sadece sinir icindeki kisim
    D36 tamamen tuval disinda -> 0 piksel
    D37 sag/alt tasma -> w-1/h-1'de kirpilir
  disc:
    D38 r=0 -> tam 1 piksel (merkez)
    D39 r=1 -> 5 piksel (artı sekiller)
    D40 r=2 -> 13 piksel; TOPLUMLA dx*dx+dy*dy<=4 (euclid) seklide
    D41 r<0 -> 0 piksel (range bos)
    D42 merkez tamamen disarida -> 0 piksel
    D43 merkez kismen disarida -> sadece sinir icindeki kisim
  bytes:
    D44 len == w*h*4, tip bytes (immutable snapshot)
    D45 once alinan bytes() kopyasi sonradan cizimden etkilenmez
    D46 cizimden sonra bile alfa 255 kalir (alpha degmez)

Kural-1: SADECE yeni test dosyasi — production/conftest DOKUNULMADI.
Kural-4: saf-bellek — network/DNS/subprocess/socket YOK; hepsi in-memory.
Deterministik: hic RNG yok; tum piksel sayilari onceden hesaplandi.
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")

from swarmax.metrics.charts import Canvas  # noqa: E402


# ============================================================ yardimcilar

def _renkliler(canvas: Canvas, bg: tuple[int, int, int] = (0, 0, 0)) -> int:
    """Arka plandan farkli (cizilmis) piksel sayisi."""
    return sum(
        1 for i in range(0, len(canvas.buf), 4)
        if tuple(canvas.buf[i:i + 3]) != bg
    )


def _piksel(canvas: Canvas, x: int, y: int) -> tuple[int, int, int, int]:
    """(x, y) pikselinin RGBA degeri."""
    i = (y * canvas.w + x) * 4
    return tuple(canvas.buf[i:i + 4])  # type: ignore[return-value]


def _noktalar(canvas: Canvas, bg: tuple[int, int, int] = (0, 0, 0)) -> set[tuple[int, int]]:
    """Cizilmis piksel koordinat kumesi."""
    return {
        (i // 4 % canvas.w, i // 4 // canvas.w)
        for i in range(0, len(canvas.buf), 4)
        if tuple(canvas.buf[i:i + 3]) != bg
    }


KIRMIZI = (255, 0, 0)
YESIL = (0, 255, 0)


# ============================================================ __init__

class TestBaslatici:
    """Canvas.__init__ — boyut dogrulama + bg dolgu + alfa."""

    @pytest.mark.parametrize("w,h", [
        (0, 5), (-1, 5), (0, 0), (-100, -100), (5, 0), (5, -1),
    ])
    def test_gecersiz_boyut_value_error(self, w, h):
        # D1+D2: w<=0 veya h<=0 -> ValueError("empty canvas")
        with pytest.raises(ValueError, match="empty canvas"):
            Canvas(w, h)

    def test_bir_bir_minimum_tuval_gecerli(self):
        # D3: 1x1 minimum gecerli
        c = Canvas(1, 1)
        assert (c.w, c.h) == (1, 1)
        assert len(c.buf) == 4

    @pytest.mark.parametrize("w,h", [
        (1, 1), (2, 3), (10, 10), (640, 480), (7, 1), (1, 7),
    ])
    def test_boyut_ve_buffer_uzunlugu(self, w, h):
        # D4: w/h saklanir; buf RGBA8 -> w*h*4 bayt
        c = Canvas(w, h)
        assert c.w == w
        assert c.h == h
        assert len(c.buf) == w * h * 4

    @pytest.mark.parametrize("bg", [
        (0, 0, 0), (255, 255, 255), (10, 20, 30), (128, 64, 200),
    ])
    def test_arka_plan_dolgu(self, bg):
        # D5: her piksel bg ile baslatildi
        c = Canvas(4, 3, bg=bg)
        for i in range(0, len(c.buf), 4):
            assert tuple(c.buf[i:i + 3]) == bg

    def test_alfa_her_yerde_255(self):
        # D6: tuval on-composited; alfa 255 kalmali
        c = Canvas(5, 5, bg=(13, 26, 39))
        assert all(c.buf[i + 3] == 255 for i in range(0, len(c.buf), 4))
        assert _piksel(c, 0, 0)[3] == 255
        assert _piksel(c, 4, 4)[3] == 255

    def test_bg_dort_elemanli_value_error(self):
        # D7: docstring 3-demet bg ister; 4 demet unpack hatasi
        with pytest.raises(ValueError):
            Canvas(3, 3, bg=(1, 2, 3, 255))


# ============================================================ start()

class TestStart:
    """start() — dogrudan piksel erisimi icin canli buffer."""

    def test_start_canli_buffer_dir(self):
        c = Canvas(3, 3)
        buf = c.start()
        # D8: ayni nesne (canli), bytearray
        assert buf is c.buf
        assert isinstance(buf, bytearray)
        assert len(buf) == 3 * 3 * 4

    def test_start_uzzerinde_cizim_tuvalu_degistirir(self):
        c = Canvas(3, 3)
        buf = c.start()
        # D9: direkt buffer yazimi canvas'a yansir
        buf[0:4] = bytes((255, 0, 0, 255))
        assert _piksel(c, 0, 0) == (255, 0, 0, 255)
        assert _renkliler(c) >= 1


# ============================================================ hline / vline

class TestHline:
    """hline — yatay cizgi; yon bagimsiz + kirma."""

    def test_sola_saga_inclusive(self):
        c = Canvas(6, 3)
        c.hline(1, 4, 1, KIRMIZI)
        # D11: x1-x0+1 piksel; y=1 satirinda
        assert _noktalar(c) == {(1, 1), (2, 1), (3, 1), (4, 1)}
        assert _renkliler(c) == 4

    def test_sola_saga_yon_normalize(self):
        # D12: x0>x1 -> min/max ile ayni cikti
        c = Canvas(6, 3)
        c.hline(4, 1, 1, KIRMIZI)
        assert _noktalar(c) == {(1, 1), (2, 1), (3, 1), (4, 1)}

    def test_tek_piksel_hline(self):
        c = Canvas(4, 4)
        c.hline(2, 2, 2, KIRMIZI)
        # sinir: x0==x1 -> 1 piksel
        assert _noktalar(c) == {(2, 2)}

    @pytest.mark.parametrize("y", [-1, 3, 100])
    def test_y_tuval_disinda_hic_piksel(self, y):
        c = Canvas(4, 3)
        c.hline(0, 3, y, KIRMIZI)
        # D13: y sinir disi -> sessizce atlanir, hata YOK
        assert _renkliler(c) == 0

    def test_sagdan_tasma_kirpilir(self):
        c = Canvas(4, 3)
        c.hline(2, 10, 1, KIRMIZI)
        # D14: sadece x=2,3 cizilir (w-1=3'te kirpilir)
        assert _noktalar(c) == {(2, 1), (3, 1)}

    def test_negatif_x_kirpilir(self):
        c = Canvas(5, 1)
        c.hline(-3, 1, 0, KIRMIZI)
        # D15: sadece x=0,1 cizilir
        assert _noktalar(c) == {(0, 0), (1, 0)}

    def test_hline_rengi_piksele_yazilir(self):
        c = Canvas(3, 3)
        c.hline(0, 2, 0, (10, 200, 30))
        assert _piksel(c, 1, 0) == (10, 200, 30, 255)


class TestVline:
    """vline — dikey cizgi; yon bagimsiz + kirma."""

    def test_yukaridan_asagi_inclusive(self):
        c = Canvas(3, 6)
        c.vline(1, 1, 4, KIRMIZI)
        # D16: y1-y0+1 piksel; x=1 sutununda
        assert _noktalar(c) == {(1, 1), (1, 2), (1, 3), (1, 4)}

    def test_asagidan_yukari_yon_normalize(self):
        # D17: y0>y1 -> min/max ile ayni cikti
        c = Canvas(3, 6)
        c.vline(1, 4, 1, KIRMIZI)
        assert _noktalar(c) == {(1, 1), (1, 2), (1, 3), (1, 4)}

    @pytest.mark.parametrize("x", [-1, 3, 100])
    def test_x_tuval_disinda_hic_piksel(self, x):
        c = Canvas(3, 4)
        c.vline(x, 0, 3, KIRMIZI)
        # D18: x sinir disi -> sessizce atlanir, hata YOK
        assert _renkliler(c) == 0

    def test_alttan_tasma_kirpilir(self):
        c = Canvas(3, 5)
        c.vline(1, 3, 7, KIRMIZI)
        # D19: sadece y=3,4 cizilir (h-1=4'te kirpilir)
        assert _noktalar(c) == {(1, 3), (1, 4)}

    def test_vline_rengi_piksele_yazilir(self):
        c = Canvas(3, 3)
        c.vline(2, 0, 2, (9, 8, 7))
        assert _piksel(c, 2, 1) == (9, 8, 7, 255)


# ============================================================ line (Bresenham)

class TestLine:
    """line — Bresenham dogru parcasi (tüm oktantlar)."""

    def test_tek_nokta_tam_bir_piksel(self):
        c = Canvas(5, 5)
        c.line(2, 2, 2, 2, KIRMIZI)
        # D20: bas==son -> 1 piksel
        assert _noktalar(c) == {(2, 2)}

    @pytest.mark.parametrize("x0,x1,beklenen_n", [
        (1, 4, 4), (0, 0, 1), (3, 3, 1), (0, 5, 6), (4, 1, 4),
    ])
    def test_yatay_dogru(self, x0, x1, beklenen_n):
        c = Canvas(6, 6)
        c.line(x0, 2, x1, 2, KIRMIZI)
        # D21: yatay -> |x1-x0|+1 piksel, hepsi y=2'de
        assert _renkliler(c) == beklenen_n
        assert all(y == 2 for (_, y) in _noktalar(c))

    @pytest.mark.parametrize("y0,y1,beklenen_n", [
        (1, 4, 4), (0, 0, 1), (0, 5, 6), (4, 1, 4),
    ])
    def test_dikey_dogru(self, y0, y1, beklenen_n):
        c = Canvas(6, 6)
        c.line(2, y0, 2, y1, KIRMIZI)
        # D22: dikey -> |y1-y0|+1 piksel, hepsi x=2'de
        assert _renkliler(c) == beklenen_n
        assert all(x == 2 for (x, _) in _noktalar(c))

    def test_kosegen_uc_noktalar_dahil(self):
        c = Canvas(5, 5)
        c.line(0, 0, 4, 4, KIRMIZI)
        # D23: ana kosege; 5 piksel; uçlar dahil
        assert _noktalar(c) == {(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)}

    def test_ters_kosegen_ayni_kume(self):
        # D24: (4,4)->(0,0) ters yon -> ayni pikseller (simetri)
        c1 = Canvas(5, 5)
        c1.line(0, 0, 4, 4, KIRMIZI)
        c2 = Canvas(5, 5)
        c2.line(4, 4, 0, 0, KIRMIZI)
        assert _noktalar(c1) == _noktalar(c2)

    def test_ters_kosegen_ust_capraz(self):
        # D24: (0,4)->(4,0) yukari capraz (sy=-1)
        c1 = Canvas(5, 5)
        c1.line(0, 4, 4, 0, KIRMIZI)
        c2 = Canvas(5, 5)
        c2.line(4, 0, 0, 4, KIRMIZI)
        assert _noktalar(c1) == _noktalar(c2)
        assert _noktalar(c1) == {(0, 4), (1, 3), (2, 2), (3, 1), (4, 0)}

    def test_dik_egim_steep(self):
        c = Canvas(5, 5)
        c.line(0, 0, 2, 4, KIRMIZI)
        # D25: |dy|>|dx| (steep); uçlar dahil, ara noktalar segir
        n = _noktalar(c)
        assert (0, 0) in n and (2, 4) in n
        assert len(n) == 5
        # tum pikseller tuval sinirlari icinde
        assert all(0 <= x < 5 and 0 <= y < 5 for x, y in n)

    def test_her_iki_uc_tuval_disinda_hata_yok(self):
        c = Canvas(5, 5)
        oncesi = bytes(c.buf)
        c.line(10, 10, 14, 14, KIRMIZI)
        # D26: tamamen disarida -> hata YOK, hic degisiklik yok
        assert bytes(c.buf) == oncesi

    def test_tek_uc_disarida_kismi_yol(self):
        # D27: isvar (-3,1)->(3,1) -> sadece 0..3 cizilir
        c = Canvas(5, 5)
        c.line(-3, 1, 3, 1, KIRMIZI)
        assert _noktalar(c) == {(0, 1), (1, 1), (2, 1), (3, 1)}

    def test_negatif_koordinat_isvari(self):
        # D28: kosege isvari (-2,-2)->(2,2) -> sadece (0,0),(1,1),(2,2)
        c = Canvas(5, 5)
        c.line(-2, -2, 2, 2, KIRMIZI)
        assert _noktalar(c) == {(0, 0), (1, 1), (2, 2)}

    def test_cizimden_sonra_alfa_degismez(self):
        # cizim sonrasi alfa 255 kalmali (D6+D46)
        c = Canvas(5, 5)
        c.line(0, 0, 4, 4, KIRMIZI)
        assert all(c.buf[i + 3] == 255 for i in range(0, len(c.buf), 4))
        assert _piksel(c, 2, 2) == (255, 0, 0, 255)


# ============================================================ line_pts

class TestLinePts:
    """line_pts — polyline (sparkline yolu)."""

    def test_iki_nokta_line_ile_ayni(self):
        # D29: 2 nokta -> tek parca; line() ile ayni sonuc
        c1 = Canvas(6, 6)
        c1.line_pts([(1, 1), (5, 1)], KIRMIZI)
        c2 = Canvas(6, 6)
        c2.line(1, 1, 5, 1, KIRMIZI)
        assert _noktalar(c1) == _noktalar(c2)

    def test_uc_nokta_polyline_tum_parcalar(self):
        # D30: 3 nokta -> 2 parca; tum kesimler cizilir
        c = Canvas(6, 6)
        c.line_pts([(0, 0), (5, 0), (5, 5)], KIRMIZI)
        ust_satir = {(x, 0) for x in range(6)}
        sag_sutun = {(5, y) for y in range(6)}
        assert _noktalar(c) == ust_satir | sag_sutun

    def test_dort_nokta_zigzag(self):
        c = Canvas(5, 5)
        c.line_pts([(0, 0), (4, 0), (4, 4), (0, 4)], KIRMIZI)
        # D30: 4 nokta -> 3 parca; cerceve tam
        n = _noktalar(c)
        assert all((x, 0) in n for x in range(5))
        assert all((4, y) in n for y in range(5))
        assert all((x, 4) in n for x in range(5))
        assert len(n) == 5 + 4 + 4   # 13 (ust 5 + sag 4 + alt 4; kose ortak)

    def test_tek_nokta_hic_piksel_cizilmez(self):
        c = Canvas(5, 5)
        c.line_pts([(2, 2)], KIRMIZI)
        # D31: zip(pts, pts[1:]) bos -> HIC cizim YOK
        assert _renkliler(c) == 0

    def test_bos_liste_hata_yok(self):
        c = Canvas(5, 5)
        c.line_pts([], KIRMIZI)
        # D32: bos liste -> zip bos
        assert _renkliler(c) == 0


# ============================================================ rect

class TestRect:
    """rect — dolu dikdortgen."""

    def test_tamamen_icinde(self):
        c = Canvas(8, 8)
        c.rect(2, 2, 4, 3, KIRMIZI)
        # D33: w*h piksel
        assert _renkliler(c) == 4 * 3
        assert _noktalar(c) == {
            (x, y) for x in (2, 3, 4, 5) for y in (2, 3, 4)
        }

    @pytest.mark.parametrize("w,h", [(0, 3), (4, 0), (0, 0)])
    def test_sifir_boyut_hic_piksel(self, w, h):
        c = Canvas(6, 6)
        c.rect(1, 1, w, h, KIRMIZI)
        # D34: w=0 veya h=0 -> bos range
        assert _renkliler(c) == 0

    def test_negatif_koordinat_kismi_dolu(self):
        c = Canvas(5, 5)
        c.rect(-2, -2, 4, 4, KIRMIZI)
        # D35: sadece (0..1, 0..1) kismi cizilir
        assert _noktalar(c) == {(0, 0), (0, 1), (1, 0), (1, 1)}

    @pytest.mark.parametrize("x,y,w,h", [
        (9, 9, 2, 2),     # tamamen sag-alt disarida
        (-8, -8, 2, 2),   # tamamen sol-ust disarida
        (10, 2, 3, 3),    # tamamen sag disarida
        (2, 10, 3, 3),    # tamamen alt disarida
    ])
    def test_tamamen_disarida_hic_piksel(self, x, y, w, h):
        c = Canvas(5, 5)
        c.rect(x, y, w, h, KIRMIZI)
        # D36: tüm alan disarida -> 0 piksel, hata YOK
        assert _renkliler(c) == 0

    def test_sag_alt_tasma_kirpilir(self):
        c = Canvas(5, 5)
        c.rect(3, 3, 4, 4, KIRMIZI)
        # D37: x 3..6 -> 3..4; y 3..6 -> 3..4
        assert _noktalar(c) == {(3, 3), (3, 4), (4, 3), (4, 4)}


# ============================================================ disc

class TestDisc:
    """disc — dolu disk (euclid uzaklik: dx*dx+dy*dy <= r*r)."""

    def test_sifir_yaricap_tek_piksel(self):
        c = Canvas(7, 7)
        c.disc(3, 3, 0, KIRMIZI)
        # D38: r=0 -> tam 1 piksel (merkez)
        assert _noktalar(c) == {(3, 3)}

    def test_bir_yaricap_bes_piksel(self):
        c = Canvas(9, 9)
        c.disc(4, 4, 1, KIRMIZI)
        # D39: arti sekli: merkez + 4 komsu
        assert _noktalar(c) == {(4, 4), (3, 4), (5, 4), (4, 3), (4, 5)}
        assert _renkliler(c) == 5

    def test_iki_yaricap_on_uc_piksel(self):
        c = Canvas(9, 9)
        c.disc(4, 4, 2, KIRMIZI)
        # D40: 13 piksel; hepsi dx*dx+dy*dy <= 4
        n = _noktalar(c)
        assert len(n) == 13
        for (x, y) in n:
            dx, dy = x - 4, y - 4
            assert dx * dx + dy * dy <= 4

    def test_iki_yaricap_uzaklik_dogrulugu(self):
        # D40: (4±2,4) dahil ama (4±2,4±2) disarida (dx²+dy²=8 > 4)
        c = Canvas(9, 9)
        c.disc(4, 4, 2, KIRMIZI)
        assert _piksel(c, 2, 4) == (255, 0, 0, 255)   # dx=-2, dy=0 -> icte
        assert _piksel(c, 6, 4) == (255, 0, 0, 255)   # dx=+2, dy=0 -> icte
        assert _piksel(c, 2, 2) == (0, 0, 0, 255)     # dx=-2,dy=-2 -> disarida

    @pytest.mark.parametrize("r", [-1, -3, -100])
    def test_negatif_yaricap_hic_piksel(self, r):
        c = Canvas(5, 5)
        c.disc(2, 2, r, KIRMIZI)
        # D41: range(-r, r+1) bos -> 0 piksel
        assert _renkliler(c) == 0

    @pytest.mark.parametrize("cx,cy", [(10, 2), (-3, 2), (2, 10), (2, -3)])
    def test_merkez_disarida_hic_piksel(self, cx, cy):
        c = Canvas(5, 5)
        c.disc(cx, cy, 2, KIRMIZI)
        # D42: merkez tamamen disarida -> cakismayan kisim YOK
        assert _renkliler(c) == 0

    def test_merkez_kismen_disarida_kirpilir(self):
        c = Canvas(5, 5)
        c.disc(0, 2, 2, KIRMIZI)
        # D43: cx=0 -> sadece dx>=0 kisim cizilir; 5+3+1 = 9 piksel
        assert _renkliler(c) == 9
        assert all(x >= 0 for (x, _) in _noktalar(c))


# ============================================================ bytes()

class TestBytes:
    """bytes() — RGBA ham cikti (raster.encode_png icin)."""

    def test_uzunluk_ve_tip(self):
        c = Canvas(4, 3)
        b = c.bytes()
        # D44: len == w*h*4; tip bytes (immutable)
        assert isinstance(b, bytes)
        assert len(b) == 4 * 3 * 4

    def test_bos_tuval_bytes_bg_ile_ayni(self):
        c = Canvas(2, 2, bg=(11, 22, 33))
        assert c.bytes() == bytes((11, 22, 33, 255)) * 4

    def test_snapshot_cizimden_sonra_degismez(self):
        c = Canvas(3, 3)
        once = c.bytes()
        # D45: once alinan kopya sonradan cizimden etkilenmez
        c.rect(0, 0, 3, 3, KIRMIZI)
        sonra = c.bytes()
        assert once != sonra
        assert once == bytes((0, 0, 0, 255)) * 9
        assert sonra == bytes((255, 0, 0, 255)) * 9

    def test_cizimden_sonra_alfa_255(self):
        # D46: _px sadece RGB yazar; alfa degmez
        c = Canvas(4, 4)
        c.hline(0, 3, 0, (1, 2, 3))
        c.vline(3, 0, 3, (4, 5, 6))
        c.line(0, 0, 3, 3, (7, 8, 9))
        c.rect(1, 1, 2, 2, (10, 11, 12))
        c.disc(0, 3, 1, (13, 14, 15))
        c.line_pts([(0, 0), (3, 3)], (16, 17, 18))
        assert all(c.buf[i + 3] == 255 for i in range(0, len(c.buf), 4))


# ============================================================ yapisal butunluk

class TestYapisalButunluk:
    """Canvas __slots__ ve genelAPI butunlugu."""

    def test_slots_yeni_alan_reddedilir(self):
        c = Canvas(2, 2)
        with pytest.raises(AttributeError):
            c.ekstra_alan = 1   # __slots__ -> yeni alan yok

    def test_slots_alanlari_erisilebilir(self):
        c = Canvas(2, 2)
        assert (c.w, c.h) == (2, 2)
        assert isinstance(c.buf, bytearray)

    @pytest.mark.parametrize("cizim", [
        lambda cv: cv.hline(0, 2, 0, (1, 1, 1)),
        lambda cv: cv.vline(0, 0, 2, (1, 1, 1)),
        lambda cv: cv.line(0, 0, 2, 2, (1, 1, 1)),
        lambda cv: cv.line_pts([(0, 0), (2, 2)], (1, 1, 1)),
        lambda cv: cv.rect(0, 0, 3, 3, (1, 1, 1)),
        lambda cv: cv.disc(1, 1, 1, (1, 1, 1)),
    ])
    def test_cizim_metotlari_none_donmez_hata_yok(self, cizim):
        c = Canvas(3, 3)
        sonuc = cizim(c)
        # tum cizim metotlari void (None); hata firlatmaz
        assert sonuc is None

    def test_kucuk_tuvarda_tam_cizim(self):
        # 1x1 tuval: tum cizimler merkez
        c = Canvas(1, 1)
        c.hline(0, 0, 0, (5, 6, 7))
        c.vline(0, 0, 0, (5, 6, 7))
        c.line(0, 0, 0, 0, (5, 6, 7))
        c.rect(0, 0, 1, 1, (5, 6, 7))
        c.disc(0, 0, 0, (5, 6, 7))
        assert _piksel(c, 0, 0) == (5, 6, 7, 255)
