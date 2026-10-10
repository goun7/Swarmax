"""Otonom dal-kesen testler — hedef: ``swarmax.ed25519._point_add``

Kapsam: extended (X, Y, Z, T) twisted-Edwards koordinatlarinda nokta toplama.
Üretim koduna ASLA DOKUNULMADI; bu dosya yalnizca tests/ altinda olusturuldu.

Bilinen referans degerleri (RFC 8032 / Ed25519 standart curve parametreleri):
  P  = 2**255 - 19
  D  = -121665/121666  (mod P)
  G  = (Gx, Gy, 1, Gx*Gy)  — base point, Gy = 4/5 (mod P)
  G  compressed = "5866...6666"
  2G compressed = c9a3f86aae465f0e56513864510f3997561fa2c9e85ea21dc2292309f3cd6022
  3G compressed = d4b4f5784868c3020403246717ec169ff79e26608ea126a1ab69ee77d1b16712

Bagimsiz oracle: testin icinde, uretim kodunun extended formülünden tamamen
farkli, affine koordinatli klasik twisted-Edwards toplama formülü uygulanir.
Iki formül ayni noktayi vermeli (bagimsizlik kaniti).
"""
from __future__ import annotations

import hashlib

import pytest

import swarmax.ed25519 as ed

# ---------------------------------------------------------------------------
# Sabit referans degerleri (uretim modülünden bagimsiz sabitlenmis)
# ---------------------------------------------------------------------------

P = 57896044618658097711785492504343953926634992332820282019728792003956564819949
Q = 7237005577332262213973186563042994240857116359379907606001950938285454250989
D = 37095705934669439343138083508754565189542113879843219016388785533085940283555

ID = (0, 1, 1, 0)  # birim eleman (identity)

# Base point'un sabitlenmis koordinatlari (Ed25519 standarti)
GX = 15112221349535400772501151409588531511454012693041857206046113283949847762202
GY = 46316835694926478169428394003475163141307993866256225615783033603165251855960

# k*G compressed (little-endian 32 bayt hex) — RFC 8032 vektörleri ve
# `cryptography` kutuphanesi ile dogrulanmis sabitler
KG_COMPRESSED = {
    0: "0100000000000000000000000000000000000000000000000000000000000000",
    1: "5866666666666666666666666666666666666666666666666666666666666666",
    2: "c9a3f86aae465f0e56513864510f3997561fa2c9e85ea21dc2292309f3cd6022",
    3: "d4b4f5784868c3020403246717ec169ff79e26608ea126a1ab69ee77d1b16712",
    4: "2f1132ca61ab38dff00f2fea3228f24c6c71d58085b80e47e19515cb27e8d047",
    5: "edc876d6831fd2105d0b4389ca2e283166469289146e2ce06faefe98b22548df",
    7: "b862409fb5c4c4123df2abf7462b88f041ad36dd6864ce872fd5472be363c5b1",
}

# Turkce/unicode metinlerden deterministik nokta uretmek icin metinler
TR_SEEDS = ["İstanbul-ajan-2026", "çağlaÜmitŞiir"]


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------


def _kg(k: int):
    """k*G noktasi (uretim _point_mul'i — oracle olarak kullanilir)."""
    return ed._point_mul(k % Q, ed.G)


def _neg(pt):
    """Extended koordinatlarda negatif: -P = (P-X, Y, Z, P-T)."""
    return ((P - pt[0]) % P, pt[1], pt[2], (P - pt[3]) % P)


def _affine(pt):
    """Extended -> affine (x, y) donusumu."""
    zinv = pow(pt[2], P - 2, P)
    return ((pt[0] * zinv) % P, (pt[1] * zinv) % P)


def _affine_add(p1, p2):
    """BAGIMSIZ ORACLE: klasik affine twisted-Edwards toplama (a = -1).

    Uretim kodunun extended formülünden tamamen farkli bir yol; ortak hata
    payi olmamali.
    """
    x1, y1 = _affine(p1)
    x2, y2 = _affine(p2)
    denom_x = (1 + D * x1 * x2 * y1 * y2) % P
    denom_y = (1 - D * x1 * x2 * y1 * y2) % P
    x3 = ((x1 * y2 + y1 * x2) * pow(denom_x, P - 2, P)) % P
    y3 = ((y1 * y2 + x1 * x2) * pow(denom_y, P - 2, P)) % P
    return (x3, y3)


def _tr_point(text: str):
    """Turkce metinden deterministik skaler nokta: P = (a mod Q) * G."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    a, _prefix = ed._secret_expand(seed)
    return ed._point_mul(a, ed.G)


# ---------------------------------------------------------------------------
# A. Birim eleman (identity) dallari
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_identity_sag_birim(k):
    """_point_add(kG, ID) == kG (sifir sagdan etkisiz eleman)."""
    assert ed._point_equal(ed._point_add(_kg(k), ID), _kg(k))


@pytest.mark.parametrize("k", [1, 2, 3])
def test_identity_sol_birim(k):
    """_point_add(ID, kG) == kG (sifir soldan etkisiz eleman)."""
    assert ed._point_equal(ed._point_add(ID, _kg(k)), _kg(k))


def test_identity_arti_identity_birim_ve_exact_tuple():
    """ID + ID yine birim eleman; exact (0,4,4,0) doner (kanonik olmayan
    gosterim — _point_add Z=1 normalizasyonu yapmaz)."""
    res = ed._point_add(ID, ID)
    assert ed._point_equal(res, ID)
    assert res == (0, 4, 4, 0)
    assert ed._point_equal((0, 4, 4, 0), ID) is True


@pytest.mark.parametrize("k", [1, 2])
def test_kanonik_olmayan_birimle_toplama(k):
    """(0,4,4,0) birim eleman gibi davranmali: (0,4,4,0) + kG == kG."""
    assert ed._point_equal(ed._point_add((0, 4, 4, 0), _kg(k)), _kg(k))


@pytest.mark.parametrize("lam", [2, 3])
def test_olceklenmis_birimlerle_toplama(lam):
    """Iki olceklenmis birim elemanin toplami yine birim: (0,λ,λ,0)+(0,λ+1,...)."""
    a = (0, lam, lam, 0)
    b = (0, lam + 1, lam + 1, 0)
    assert ed._point_equal(ed._point_add(a, b), ID)


# ---------------------------------------------------------------------------
# B. Sabitlenmis bilinen degerler (known vectors)
# ---------------------------------------------------------------------------


def test_base_point_sabit_deger():
    """Uretim G'su sabitlenen standart Ed25519 base point ile ayni."""
    assert ed.G == (GX, GY, 1, (GX * GY) % P)


def test_iki_base_point_bilinen_2g():
    """G + G compressed hali bilinen 2G degeri."""
    assert ed.point_compress(ed._point_add(ed.G, ed.G)).hex() == KG_COMPRESSED[2]


def test_base_point_arti_2g_bilinen_3g():
    """G + 2G compressed hali bilinen 3G degeri."""
    assert ed.point_compress(ed._point_add(ed.G, _kg(2))).hex() == KG_COMPRESSED[3]


def test_g_arti_g_point_mul_2_ile_ayni_nokta():
    """G+G ile _point_mul(2, G) ayni nokta. Extended koordinatlar projektif
    oldugu icin tuple birebir ayni olmak ZORUNDA DEGIL; _point_equal yeterli."""
    lhs = ed._point_add(ed.G, ed.G)
    rhs = ed._point_mul(2, ed.G)
    assert ed._point_equal(lhs, rhs)
    assert ed.point_compress(lhs) == ed.point_compress(rhs)


@pytest.mark.parametrize(
    "a,b", [(1, 1), (1, 2), (2, 3), (7, 11)]
)
def test_bilinen_toplama_tablosu(a, b):
    """aG + bG compressed hali (a+b)G bilinen degeri ile eslesmeli."""
    lhs = ed.point_compress(ed._point_add(_kg(a), _kg(b))).hex()
    rhs = KG_COMPRESSED.get(a + b)
    if rhs is None:
        rhs = ed.point_compress(_kg(a + b)).hex()
    assert lhs == rhs


# ---------------------------------------------------------------------------
# C. Cebirsel kurallar (group laws)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a,b", [(1, 2), (3, 4)])
def test_toplama_skaler_carpimla_tutarli(a, b):
    """aG + bG, (a+b)G noktasina esit olmali (grup kanunu)."""
    assert ed._point_equal(ed._point_add(_kg(a), _kg(b)), _kg(a + b))


@pytest.mark.parametrize("delta", [1, 2])
def test_toplama_mod_q_dusmesi(delta):
    """(Q-delta)G + delta*G == ID — mod Q indirgenmesi (grup duzeni Q)."""
    assert ed._point_equal(ed._point_add(_kg(Q - delta), _kg(delta)), ID)


def test_q_kati_birim_eleman():
    """Q*G birim elemandir (G'nin derecesi Q) — oracle tutarlilik kontrolu."""
    assert ed._point_equal(ed._point_mul(Q, ed.G), ID)


@pytest.mark.parametrize("a,b", [(1, 2), (3, 4)])
def test_degisme_ozelligi(a, b):
    """P + Q == Q + P (toplama degisken) — tuple ve compress duzeyinde."""
    pa, pb = _kg(a), _kg(b)
    lhs, rhs = ed._point_add(pa, pb), ed._point_add(pb, pa)
    assert ed._point_equal(lhs, rhs)
    assert ed.point_compress(lhs) == ed.point_compress(rhs)


@pytest.mark.parametrize("triple", [(1, 2, 3), (2, 3, 5)])
def test_birlesme_ozelligi(triple):
    """(P+Q)+R == P+(Q+R) (toplama birlesken)."""
    a, b, c = triple
    pa, pb, pc = _kg(a), _kg(b), _kg(c)
    lhs = ed._point_add(ed._point_add(pa, pb), pc)
    rhs = ed._point_add(pa, ed._point_add(pb, pc))
    assert ed._point_equal(lhs, rhs)


@pytest.mark.parametrize("k", [1, 2, 3])
def test_katlama_ve_negatif_toplami(k):
    """P + P == 2P (katlama) ve P + (-P) == ID (ters eleman)."""
    pk = _kg(k)
    assert ed._point_equal(ed._point_add(pk, pk), _kg(2 * k))
    assert ed._point_equal(ed._point_add(pk, _neg(pk)), ID)


@pytest.mark.parametrize("a,b", [(3, 1), (5, 2)])
def test_cikarma_ve_negatiflerin_toplami(a, b):
    """aG + (-bG) == (a-b)G ve (-aG) + (-bG) == -(a+b)G."""
    lhs = ed._point_add(_kg(a), _neg(_kg(b)))
    assert ed._point_equal(lhs, _kg(a - b))
    lhs2 = ed._point_add(_neg(_kg(a)), _neg(_kg(b)))
    assert ed._point_equal(lhs2, _neg(_kg(a + b)))


# ---------------------------------------------------------------------------
# D. Çikti yapisi, invariantlar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a,b", [(1, 2), (3, 4)])
def test_cikti_yapisi_ve_aralik(a, b):
    """Sonuc 4 int'ten olusan bir tuple, tum koordinatlar [0, P) araliginda,
    ve extended invarianti T*Z == X*Y (mod P) saglanmali."""
    res = ed._point_add(_kg(a), _kg(b))
    assert isinstance(res, tuple) and len(res) == 4
    assert all(isinstance(c, int) for c in res)
    assert all(0 <= c < P for c in res)
    x, y, z, t = res
    assert (t * z - x * y) % P == 0


@pytest.mark.parametrize("a,b", [(1, 2), (3, 4), (5, 7)])
def test_sonuc_egri_uzerinde(a, b):
    """Sonuc normalize edilince Edwards egrisi uzerinde: -x²+y² = 1+D x²y²."""
    x, y = _affine(ed._point_add(_kg(a), _kg(b)))
    assert (-x * x + y * y) % P == (1 + D * x * x * y * y) % P


@pytest.mark.parametrize("combo", [(2, 1, 3), (3, 2, 5)])
def test_projektif_invarians_z_olcegi(combo):
    """Girdi Z ile olceklenince ayni nokta: (λP)+Q == P+Q.

    Extended koordinatlar projektif oldugu icin Z olceklemesi temsil edilen
    noktayi degistirmez; _point_add bunu korumali.
    """
    lam, a, b = combo
    pa, pb = _kg(a), _kg(b)
    scaled = ((pa[0] * lam) % P, (pa[1] * lam) % P, (pa[2] * lam) % P, (pa[3] * lam) % P)
    assert ed._point_equal(ed._point_add(scaled, pb), ed._point_add(pa, pb))


def test_her_bagi_bagimsiz_etkili_ve_deterministik():
    """Her iki arguman da sonucu etkiler (P+Q != P) ve toplama deterministik."""
    pa, pb = _kg(3), _kg(5)
    assert not ed._point_equal(ed._point_add(pa, pb), pa)
    assert ed._point_add(pa, pb) == ed._point_add(pa, pb)


@pytest.mark.parametrize("combo", [(2, 1, 3), (3, 2, 4)])
def test_skaler_dagilma(combo):
    """n*(P+Q) == nP + nQ (skaler carpma toplama uzerinde dagilir)."""
    n, a, b = combo
    lhs = ed._point_mul(n, ed._point_add(_kg(a), _kg(b)))
    rhs = ed._point_add(_kg(n * a), _kg(n * b))
    assert ed._point_equal(lhs, rhs)


def test_cifte_negatif_etkisiz():
    """-(-P) + Q == P + Q."""
    pa, pb = _kg(3), _kg(5)
    assert ed._point_equal(ed._point_add(_neg(_neg(pa)), pb), ed._point_add(pa, pb))


# ---------------------------------------------------------------------------
# E. Bagimsiz affine oracle ile capraz dogrulama
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("a,b", [(1, 2), (3, 4), (5, 8)])
def test_affine_oracle_eslesme(a, b):
    """Uretim extended toplami, bagimsiz affine formulle ayni nokta."""
    assert _affine(ed._point_add(_kg(a), _kg(b))) == _affine_add(_kg(a), _kg(b))


@pytest.mark.parametrize("k", [1, 2])
def test_affine_oracle_katlama(k):
    """P+P doubling'i de affine oracle ile tutarli."""
    pk = _kg(k)
    assert _affine(ed._point_add(pk, pk)) == _affine_add(pk, pk)


def test_affine_oracle_birim_eleman():
    """Affine oracle ile birim elemanli toplama da ayni nokta."""
    assert _affine(ed._point_add(ID, _kg(2))) == _affine_add(ID, _kg(2))


# ---------------------------------------------------------------------------
# F. Unicode / Turkce seed'lerden uretilen noktalarla grup kanunu
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", TR_SEEDS)
def test_turkce_seed_nokta_birim_ve_negatif(text):
    """Turkce metinden uretilen P: P + ID == P ve P + (-P) == ID."""
    pt = _tr_point(text)
    assert ed._point_equal(ed._point_add(pt, ID), pt)
    assert ed._point_equal(ed._point_add(pt, _neg(pt)), ID)


@pytest.mark.parametrize("text", TR_SEEDS)
def test_turkce_seed_birim_arti_g_ve_degisme(text):
    """P + G == (a+1)G ve P + 2P == 2P + P (Turkce skaler noktada grup kanunu)."""
    pt = _tr_point(text)
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    a, _ = ed._secret_expand(seed)
    assert ed._point_equal(ed._point_add(pt, ed.G), ed._point_mul(a + 1, ed.G))
    pt2 = ed._point_mul(2 * a, ed.G)
    assert ed._point_equal(ed._point_add(pt, pt2), ed._point_add(pt2, pt))


@pytest.mark.parametrize("text", TR_SEEDS)
def test_turkce_seed_affine_oracle(text):
    """Turkce skaler noktalari da bagimsiz affine oracle ile eslesir."""
    pt = _tr_point(text)
    pt3 = ed._point_mul(3, ed.G)
    assert _affine(ed._point_add(pt, pt3)) == _affine_add(pt, pt3)


# ---------------------------------------------------------------------------
# G. Sinir degerler / buyuk skalerler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("big", [2**200])
def test_buyuk_skaler_noktalarla_toplama(big):
    """Cok buyuk skalerlerden gelen noktalar da kurallari bozmamali."""
    pa = ed._point_mul(big, ed.G)
    pb = ed._point_mul(big + 1, ed.G)
    assert ed._point_equal(ed._point_add(pa, ed.G), pb)


def test_alana_yakin_koordinatlarla_toplama():
    """P'ye cok yakin koordinat iceren noktayla toplama reduksiyonu."""
    pt = _kg(7)
    near = ((P - 1) * pow(2, 200, P) % P, (P - 2) % P, 1, ((P - 1) * (P - 2)) % P)
    res = ed._point_add(pt, near)
    assert all(0 <= c < P for c in res)


def test_sifir_skaler_birimle_toplama():
    """0*G == ID: ID + 0*G yine ID."""
    assert ed._point_equal(ed._point_add(_kg(0), _kg(0)), ID)
