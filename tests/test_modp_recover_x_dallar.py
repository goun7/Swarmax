"""Otonom dal-kesen testler — hedef: ``swarmax.ed25519._modp_recover_x``

Kapsam: Edwards egrisinde verilen y koordinatindan (ve isaret bitinden)
x koordinatini geri kazanma. Fonksiyonun tum dallari:

  1. y >= P                       -> None
  2. x2 == 0 & sign_bit == 0      -> 0
  3. x2 == 0 & sign_bit == 1      -> None
  4. x = x^((P+3)/8)              (birinci sqrt denemesi)
  5. x*x != x2 (mod P)            -> x = x * 2^((P-1)/4)   (I carpani dali)
  6. hala x*x != x2               -> None (kuadratik artik degil)
  7. (x & 1) != sign_bit          -> x = P - x             (isaret dali)

Üretim koduna ASLA DOKUNULMADI; bu dosya yalnizca tests/ altinda olusturuldu.

Referans degerler Ed25519 standart curve parametreleri ve RFC 8032 vektörleri
ile bagimsiz olarak sabitlenmistir.

BULGU (karakterizasyon testi ile sabitlenmistir, üretim DEGISMEMISTIR):
  ``_modp_recover_x(P-1, 1)`` == P doner — alan disi! Beklenen None.
  Kok neden: `x2 = (y*y-1) * _modp_inv(D*y*y+1)` satirinda `% P` EKSIK;
  y = P-1 icin (y²-1) sifira esit OLMASINA ragmen ham carpim sifir DEGIL,
  P'nin sifirdan farkli bir kati olur, dolayisiyla `x2 == 0` kontrolu
  baypas edilir ve isaret dali x = P - 0 = P uretir.
  (Not: bu durum yalnizca ozel olarak hazirlanmis bir y ile ulasilabilir;
  gercek anahtarlarla ortaya cikmaz.)
"""
from __future__ import annotations

import hashlib

import pytest

import swarmax.ed25519 as ed

# ---------------------------------------------------------------------------
# Sabit referans degerleri
# ---------------------------------------------------------------------------

P = 57896044618658097711785492504343953926634992332820282019728792003956564819949
D = 37095705934669439343138083508754565189542113879843219016388785533085940283555

# 2^((P-1)/4) mod P — "I" carpani (sqrt(-1) mod P)
I_VAL = 19681161376707505956807079304988542015446066515923890162744021073123829784752

# Base point (Ed25519 standarti)
GX = 15112221349535400772501151409588531511454012693041857206046113283949847762202
GY = 46316835694926478169428394003475163141307993866256225615783033603165251855960

# Bagimsiz olarak hesaplanmis beklenen degerler
EXPECT = {
    (3, 0): 47490639360184182837601875270316946735278442122217188244898328344323804759522,
    (3, 1): 10405405258473914874183617234027007191356550210603093774830463659632760060427,
    (4, 0): 26193273134124080442446118532604303931175156347221147955160486408041496074798,
    (5, 0): 39662079413846548812394406357884595898465868971068617279194812783497449546402,
    (6, 0): 44179385186637231197387423809866071544592466792969908008717492870455120005190,
    (9, 0): 20998110467665258077629620998309994886851780706327836337918840104339545710600,
    (10, 0): 24688177111351944971186944795630209763032700723300105170855113893569705867530,
}

TR_TEXTS = ["İstanbul-ajan-2026", "çağlaÜmitŞiir"]


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------


def _x2(y: int) -> int:
    """Egriden gelen x² degeri: x² = (y²-1) / (D·y²+1)  (mod P)."""
    return ((y * y - 1) % P) * pow((D * y * y + 1) % P, P - 2, P) % P


def _tr_pubkey(text: str) -> bytes:
    """Turkce metinden uretilen seed ile public key (32 bayt)."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    return ed.secret_to_public(seed)


# ---------------------------------------------------------------------------
# A. Dal 1: y >= P -> None
# ---------------------------------------------------------------------------


def test_y_esit_p_none():
    """y == P tam sinirda None donmeli (y >= P kontrolu)."""
    assert ed._modp_recover_x(P, 0) is None
    assert ed._modp_recover_x(P, 1) is None


@pytest.mark.parametrize("y", [P + 1, 2**300, P * 2])
def test_y_buyuk_p_none(y):
    """y > P degerleri None donmeli (reduksiyon YAPILMAZ)."""
    assert ed._modp_recover_x(y, 0) is None
    assert ed._modp_recover_x(y, 1) is None


def test_y_buyuk_deger_modp_alinmaz():
    """y = P + (P-1) gibi bir deger P'ye indirgenip kabul EDILMEMELI."""
    assert ed._modp_recover_x(P + (P - 1), 0) is None


# ---------------------------------------------------------------------------
# B. Dal 2 & 3: x2 == 0 (y = ±1)
# ---------------------------------------------------------------------------


def test_y_bir_isaret_sifir_sifir_doner():
    """y = 1: x2 = 0 oldugu icin sign_bit=0 ise 0 doner."""
    assert _x2(1) == 0
    assert ed._modp_recover_x(1, 0) == 0


def test_y_bir_isaret_bir_none_doner():
    """y = 1: x2 = 0 ve sign_bit=1 ise None (0 cift sayi, isaret 1 alinamaz)."""
    assert ed._modp_recover_x(1, 1) is None


def test_y_eksi_bir_isaret_sifir_sifir_doner():
    """y = P-1 (≡ -1): y²-1 ≡ 0, sign_bit=0 ise 0 doner."""
    assert _x2(P - 1) == 0
    assert ed._modp_recover_x(P - 1, 0) == 0


def test_y_eksi_bir_isaret_bir_alan_disi_deger_uretim_quirk():
    """KARAKTERIZASYON: y = P-1, sign_bit=1 icin P doner (alan disi!).

    Beklenen None olurdu; ancak x2 hesabinda `% P` eksik oldugu icin
    `x2 == 0` kontrolu baypas edilir ve x = P - 0 = P uretilir.
    Üretim koduna DOKUNULMADI; davranis bu testle sabitlenmistir.
    """
    result = ed._modp_recover_x(P - 1, 1)
    assert result == P
    assert not (0 <= result < P)  # [0, P) alan disinda


# ---------------------------------------------------------------------------
# C. Dal 4: birinci sqrt direkt calisir (I carpani GEREKMEZ)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("y,sign,want", [(9, 0, EXPECT[(9, 0)]), (10, 0, EXPECT[(10, 0)])])
def test_direkt_sqrt_dallari(y, sign, want):
    """Bu y degerlerinde x^((P+3)/8) dogrudan karekok verir (I dali girmez)."""
    x2 = _x2(y)
    x = pow(x2, (P + 3) // 8, P)
    assert (x * x - x2) % P == 0  # I'ye ihtiyac yok
    assert ed._modp_recover_x(y, sign) == want


# ---------------------------------------------------------------------------
# D. Dal 5: I carpani dali (x*x != x2 -> x = x * I)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("y,want", [(3, EXPECT[(3, 0)]), (4, EXPECT[(4, 0)]), (5, EXPECT[(5, 0)])])
def test_i_dali_gereken_degerler(y, want):
    """Bu y degerlerinde birinci sqrt basarisizdir, I carpani uygulanir."""
    x2 = _x2(y)
    x = pow(x2, (P + 3) // 8, P)
    assert (x * x - x2) % P != 0  # birinci deneme basarili degil
    fixed = x * I_VAL % P
    assert (fixed * fixed - x2) % P == 0  # I sonrasi duzgun karekok
    assert ed._modp_recover_x(y, 0) == want


def test_i_carpani_sqrt_eksi_bir():
    """I = 2^((P-1)/4) mod P aslinda -1'in karekoku: I*I ≡ -1 (mod P)."""
    assert (I_VAL * I_VAL + 1) % P == 0
    assert I_VAL == pow(2, (P - 1) // 4, P)


# ---------------------------------------------------------------------------
# E. Dal 6: kuadratik artik degil -> None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("y", [2, 7, 11])
def test_kuadratik_artik_degil_none(y):
    """y²-1 bir QR olmadiginda (I'dan sonra da olmazsa) None doner."""
    x2 = _x2(y)
    assert x2 != 0
    x = pow(x2, (P + 3) // 8, P)
    fixed = (x * I_VAL) % P
    assert (x * x - x2) % P != 0
    assert (fixed * fixed - x2) % P != 0
    assert ed._modp_recover_x(y, 0) is None
    assert ed._modp_recover_x(y, 1) is None


# ---------------------------------------------------------------------------
# F. Bilinen base point degerleri
# ---------------------------------------------------------------------------


def test_base_point_x_dogrudan():
    """recover_x(GY, 0) standart Ed25519 base point x koordinatini verir."""
    assert ed._modp_recover_x(GY, 0) == GX


def test_base_point_x_isaretli():
    """recover_x(GY, 1) = P - GX (diger kok)."""
    assert ed._modp_recover_x(GY, 1) == P - GX
    assert (ed._modp_recover_x(GY, 1) + GX) % P == 0


def test_base_point_uretim_ile_tutarli():
    """recover_x(GY, 0) uretim modülündeki G'nin x koordinatina esit."""
    assert ed._modp_recover_x(GY, 0) == ed.G[0]
    assert ed.G[1] == GY


# ---------------------------------------------------------------------------
# G. Dal 7: isaret dali ve parite invariantlari
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "y,sign", [(3, 0), (3, 1), (GY, 0), (GY, 1)]
)
def test_sonuc_paritesi_isaret_bitine_uyar(y, sign):
    """Gecerli bir sonucun paritesi sign_bit ile ayni olmali."""
    x = ed._modp_recover_x(y, sign)
    assert x is not None
    assert (x & 1) == sign


@pytest.mark.parametrize("y", [3, 4, GY])
def test_iki_kok_toplami_p(y):
    """recover(y,0) + recover(y,1) == P (kokler toplamı P'dir)."""
    x0 = ed._modp_recover_x(y, 0)
    x1 = ed._modp_recover_x(y, 1)
    assert x0 is not None and x1 is not None
    assert x0 + x1 == P


def test_sifir_y_dali():
    """y = 0: x2 = -1, karekoku I'dir; isaret 1 P-I verir."""
    assert _x2(0) == (P - 1) % P
    assert ed._modp_recover_x(0, 0) == I_VAL
    assert ed._modp_recover_x(0, 1) == P - I_VAL


# ---------------------------------------------------------------------------
# H. Bagimsiz matematiksel oracle (dogruluk kontrolu)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("y,sign", [(3, 0), (3, 1), (GY, 0)])
def test_sonuc_karekok_denklemi_saglar(y, sign):
    """Donen x, x² ≡ (y²-1)/(Dy²+1) (mod P) denklemini saglamali."""
    x = ed._modp_recover_x(y, sign)
    assert x is not None
    assert (x * x - _x2(y)) % P == 0


@pytest.mark.parametrize("y,sign", [(4, 0), (5, 1), (9, 0)])
def test_sonuc_alan_araliginda(y, sign):
    """Gecerli sonucun degeri [0, P) araliginda olmali."""
    x = ed._modp_recover_x(y, sign)
    assert x is not None
    assert 0 <= x < P


@pytest.mark.parametrize("y", [3, 123])
def test_negatif_y_ayni_kok_verir(y):
    """x2 sadece y²'ye bagli oldugu icin recover(P-y, s) == recover(y, s)."""
    assert ed._modp_recover_x(P - y, 0) == ed._modp_recover_x(y, 0)
    assert ed._modp_recover_x(P - y, 1) == ed._modp_recover_x(y, 1)


@pytest.mark.parametrize("sign", [0, 1])
def test_isaret_bit_dogrulanmamis_sinir(sign):
    """sign_bit ∈ {0,1} normal davranir; degerler uygun kokler arasindadir."""
    x0 = ed._modp_recover_x(GY, 0)
    x1 = ed._modp_recover_x(GY, 1)
    assert ed._modp_recover_x(GY, sign) in (x0, x1)


@pytest.mark.parametrize("sign", [-1, 2, 100])
def test_isaret_bit_01_disinda_her_zaman_flip_yapar(sign):
    """SINIR BULGUSU: sign_bit 0/1 disinda bir degerse her zaman flip yapar.

    (x & 1) != sign_bit her dogru oldugu icin kok her zaman 'digeri' olur;
    fonksiyon sign_bit'i [0,1] ile sinirlandirmaz.
    """
    # GY icin sqrt sonu tek sayi: sign=1 flip yapmaz, digerleri flip yapar
    assert ed._modp_recover_x(GY, sign) == ed._modp_recover_x(GY, 0)


# ---------------------------------------------------------------------------
# I. Entegrasyon: point_decompress/compress ile round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [1, 2, 3])
def test_compress_decompress_roundtrip(k):
    """kG'nin sikistirilip acilmasi ayni noktayi vermeli (recover_x uzerinden)."""
    pt = ed._point_mul(k, ed.G)
    comp = ed.point_compress(pt)
    back = ed.point_decompress(comp)
    assert back is not None
    assert ed._point_equal(back, pt)


def test_roundtrip_birim_eleman():
    """Birim elemanin compress/decompress'i recover_x(1, 0) = 0 kullanir."""
    comp = ed.point_compress((0, 1, 1, 0))
    back = ed.point_decompress(comp)
    assert back is not None
    assert ed._point_equal(back, (0, 1, 1, 0))


@pytest.mark.parametrize("y", [P, P + 1, 2**255 - 1])
def test_decompress_gecersiz_y_none(y):
    """Maskeleme sonrasi y ∈ [P, 2^255) olan kodlama None doner.

    Not: point_decompress once y'yi 255 bite maskeledigi icin bit 255
    isaret olarak ayrilir; yalnizca [P, 2^255) araligindaki degerler
    recover_x tarafindan None doner.
    """
    bad = (y | (1 << 255)).to_bytes(32, "little")
    assert ed.point_decompress(bad) is None


def test_decompress_boyut_kontrolu():
    """32 bayt olmayan kodlama None doner (point_decompress dalı)."""
    assert ed.point_decompress(b"kisa") is None


# ---------------------------------------------------------------------------
# J. Unicode / Turkce seed'lerden turetilen anahtarlarla dogrulama
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", TR_TEXTS)
def test_turkce_seed_pubkey_decompress_edilir(text):
    """Turkce metinden uretilen public key gecerli bir nokta acilmali."""
    pub = _tr_pubkey(text)
    pt = ed.point_decompress(pub)
    assert pt is not None
    assert 0 <= pt[0] < P
    # recover_x ile geri kazanilan x, noktanin x'ile ayni paritede
    y = int.from_bytes(pub, "little") & ((1 << 255) - 1)
    sign = int.from_bytes(pub, "little") >> 255
    assert ed._modp_recover_x(y, sign) == pt[0]


@pytest.mark.parametrize("text", TR_TEXTS)
def test_turkce_seed_noktasi_egri_uzerinde(text):
    """Turkce seed'den gelen nokta Edwards egrisi uzerinde olmali."""
    pt = ed.point_decompress(_tr_pubkey(text))
    assert pt is not None
    x, y = pt[0], pt[1]
    assert (-x * x + y * y) % P == (1 + D * x * x * y * y) % P
