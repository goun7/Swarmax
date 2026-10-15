"""test_statistics_dallar.py — swarmax/metrics/statistics.py dal-kesen suite.

Kural-1: SADECE Yeni test dosyasi; production/conftest/test_metrics.py
DOKUNULMADI. Kural-4: saf-bellek (network/subprocess/socket YOK).

ORTAM-ANATOMI (src/swarmax/metrics/statistics.py):
  ewma_update(state, cost, *, min_obs=None) -> EwmaResult   (L48-71)
  jsd_divergence(p_counts, q_counts) -> JsdResult           (L89-115)
  mad_robust_z(values, x=None) -> MadResult                 (L128-151)
  cusum_update(state, x, mu0) -> CusumResult                (L169-172)
  psi(expected_counts, actual_counts) -> PsiResult          (L183-198)

DAL HARITASI (D1..Dn) — her public fonksiyon: basari+basarisiz+sinir:

  ewma_update:
    D1  n==0 ilk adim: mu=cost, sigma2=0 -> z=None
    D2  calibrated=False -> asla armed (R3)
    D3  warmup=30 siniri: 29. adim silahsiz, 30. adim silahli
    D4  min_obs baskisi: daha kisa isinma suresi
    D5  min_obs=0: n>=0 her zaman dogru -> ilk adimda armed sarti
    D6  sigma==0 (sabit maliyetler) -> armed olsa bile z=None
    D7  z > 2.5 -> alarm=True
    D8  negatif z (cost < mu) -> alarm YOK (tek yonlu kiyas, quirks)
    D9  durum mutasyonu: mu/sigma2/n yerinde guncellenir

  jsd_divergence:
    D10 bos pencere (total<=0) -> warming_up, value=None
    D11 negatif sayim total<=0 -> warming_up
    D12 ayni dagilim -> value=0.0, healthy
    D13 bantlar: healthy (0.1887 < 0.20), watch (0.278), alarm (0.713)
    D14 ayrik anahtar kumeleri -> ~1.0 alarm
    D15 sayimi 0 olan anahtar: EPS 때문에 absent ile ayni (0.0 healthy)
    D16 deger max(0, jsd) -> asla negatif

  mad_robust_z:
    D17 len<3 -> robust_z=None, median/mad=NaN
    D18 sabit degerler -> mad=0 -> robust_z=None, alarm=False
    D19 aykiri deger -> alarm=True
    D20 x varsayilan: values[-1]
    D21 cift sayida eleman: medyan iki ortanca ortalamasi
    D22 |robust_z| tam esik 3.0 -> alarm YOK (strict >)
    D23 |robust_z| 3.0001 -> alarm var
    D24 negatif yon buyuk |z| -> alarm=True (abs)

  cusum_update:
    D25 negatif akisu -> g=max(0,...)=0 (Page-Hinkley hafizasiz)
    D26 g > threshold(5.0) -> alarm
    D27 g tam esik 5.0 (drift=0) -> alarm YOK (strict >)
    D28 float quirk: 15.05-10-0.05=5.000000000000001 -> alarm=True
    D29 ozel drift/threshold degerleri

  psi:
    D30 bos pencere -> value=None, large_shift=False
    D31 ayni dagilim -> value=0.0
    D32 buyuk kayma (0.25 ustu) -> large_shift=True
    D33 kucuk kayma -> large_shift=False
    D34 ayrik anahtarlar -> dogal log tabaniyla devasa deger
"""
from __future__ import annotations

import math
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.metrics.statistics import (  # noqa: E402
    CusumResult,
    CusumState,
    EPS,
    EWMA_MIN_OBS,
    EWMA_Z_THRESHOLD,
    JSD_ALARM,
    JSD_WATCH,
    MadResult,
    MAD_SCALE,
    MAD_Z_THRESHOLD,
    PSI_LARGE_SHIFT,
    PsiResult,
    EwmaResult,
    EwmaState,
    cusum_update,
    ewma_update,
    jsd_divergence,
    mad_robust_z,
    psi,
)

# ------------------------------------------------------------------ ewma_update


def test_ilk_gozlem_mu_cost_sigma_sifir_z_none():
    """D1: n==0 adimi mu=cost, sigma2=0 -> z=None, armed=False."""
    st = EwmaState(calibrated=True)
    r = ewma_update(st, 42.0)
    assert st.mu == 42.0
    assert st.sigma2 == 0.0
    assert st.n == 1
    assert r.z is None
    assert r.armed is False
    assert r.alarm is False
    assert r.mu == 42.0
    assert r.sigma == 0.0


def test_kalibrasyonsuz_asla_silahlanmaz():
    """D2: calibrated=False -> 100 adim sonra bile armed=False (R3)."""
    st = EwmaState(calibrated=False)
    for i in range(100):
        r = ewma_update(st, float(i))
        assert r.armed is False
        assert r.alarm is False
        assert r.z is None
    assert st.n == 100


def test_isinma_suresi_29_ve_30_siniri():
    """D3: warmup=30 -> 29. adim silahsiz, 30. adim silahli (calibrated)."""
    st = EwmaState(calibrated=True)
    for i in range(29):
        r = ewma_update(st, 10.0 + (i % 3))
        assert r.armed is False
    assert st.n == 29
    r30 = ewma_update(st, 10.0)
    assert st.n == 30
    assert r30.armed is True  # n >= 30 ve calibrated


def test_isinma_suresi_30_sabit_modul_sabiti():
    st = EwmaState()
    ewma_update(st, 1.0)
    assert EWMA_MIN_OBS == 30
    assert st.n == 1


def test_min_obs_baskisi_daha_erken_silahlanir():
    """D4: min_obs=5 -> 4. adim silahsiz, 5. adim silahli."""
    st = EwmaState(calibrated=True)
    for i in range(4):
        r = ewma_update(st, float(i + 1), min_obs=5)
        assert r.armed is False, f"{i + 1}. adim silahsiz olmali"
    r5 = ewma_update(st, 5.0, min_obs=5)
    assert r5.armed is True


def test_min_obs_sifir_ikinci_adimda_silahli():
    """D5: min_obs=0 -> n>=0 her zaman dogru; sigma>0 olunca z hesaplanir."""
    st = EwmaState(calibrated=True)
    r1 = ewma_update(st, 5.0, min_obs=0)
    assert r1.z is None  # sigma hala 0
    r2 = ewma_update(st, 6.0, min_obs=0)
    assert r2.armed is True
    assert r2.z == pytest.approx(3.1622776601683795)


def test_sabit_maliyetlerde_sigma_sifir_z_none():
    """D6: 31 sabit maliyet + calibrated + n>=30 -> armed degil (sigma=0)."""
    st = EwmaState(calibrated=True)
    for _ in range(31):
        r = ewma_update(st, 10.0)
    assert st.n == 31
    assert st.sigma2 == 0.0
    assert r.armed is False
    assert r.z is None
    assert r.alarm is False


def test_stabil_seride_spike_alarm_verir():
    """D7: 40 stabil gozlem sonra buyuk spike -> z>2.5 alarm."""
    st = EwmaState(calibrated=True)
    for i in range(40):
        ewma_update(st, 10.0 + (i % 2))
    r = ewma_update(st, 100.0)
    assert r.armed is True
    assert r.z > EWMA_Z_THRESHOLD
    assert r.alarm is True


def test_negatif_spike_alarm_vermez_tek_yonlu():
    """D8: cost mu'nun altinda -> z<0 -> alarm=False (tek yonlu kiyas)."""
    st = EwmaState(calibrated=True)
    for i in range(40):
        ewma_update(st, 10.0 + (i % 2))
    r = ewma_update(st, -1000.0)
    assert r.z < 0.0
    assert r.alarm is False  # z > esigi tek yonlu; negatif z alarm vermez


def test_z_esik_altinda_alarm_yok():
    st = EwmaState(calibrated=True)
    for i in range(40):
        ewma_update(st, 10.0 + (i % 2))
    r = ewma_update(st, 12.0)
    assert r.armed is True
    assert r.alarm is False
    assert r.z < EWMA_Z_THRESHOLD


def test_durum_mutasyonu_ve_ait_degerler():
    """D9: mu/sigma2/n yerinde guncellenir; sonuc state ile uyumlu."""
    st = EwmaState(calibrated=True)
    ewma_update(st, 10.0)
    once = (st.mu, st.sigma2, st.n)
    r = ewma_update(st, 20.0)
    assert (st.mu, st.sigma2, st.n) != once
    assert st.n == 2
    assert r.mu == st.mu
    assert r.sigma == math.sqrt(st.sigma2)
    # mu = a*C + (1-a)*mu_prev (L62)
    assert st.mu == pytest.approx(0.15 * 20.0 + 0.85 * 10.0)


def test_negatif_maliyet_degeri_kabul_edilir():
    st = EwmaState(calibrated=True)
    for i in range(31):
        ewma_update(st, -5.0 - (i % 2))
    r = ewma_update(st, -5.5)
    assert r.mu < 0.0
    assert isinstance(r.z, float) or r.z is None


#--------------------------------------------------------------- jsd_divergence


@pytest.mark.parametrize("p,q", [
    ({}, {"a": 1}),          # p penceresi bos
    ({"a": 1}, {}),          # q penceresi bos
    ({}, {}),                # her ikisi bos
    ({"a": 0}, {"a": 1}),    # p totali 0
])
def test_bos_pencere_warming_up(p, q):
    """D10: total<=0 -> value=None, band='warming_up' (R4)."""
    r = jsd_divergence(p, q)
    assert r.value is None
    assert r.band == "warming_up"


def test_negatif_sayim_warming_up():
    """D11: negatif sayimlar total<=0 -> warming_up."""
    assert jsd_divergence({"a": -1.0}, {"a": 1.0}).band == "warming_up"
    assert jsd_divergence({"a": -5.0, "b": 1.0}, {"a": 1.0}).band == "warming_up"


def test_ayni_dagilim_saglikli_deger_sifir():
    """D12: ayni sayim dagilimi -> value=0.0, healthy."""
    r = jsd_divergence({"a": 5, "b": 3}, {"a": 5, "b": 3})
    assert r.value == 0.0
    assert r.band == "healthy"


def test_anahtar_sirasi_onemsiz():
    assert jsd_divergence({"a": 1, "b": 2}, {"b": 2, "a": 1}).value == 0.0


@pytest.mark.parametrize("p,q,deger,bant", [
    ({"a": 3, "b": 1}, {"a": 1, "b": 3}, 0.188721, "healthy"),
    ({"a": 1, "b": 1}, {"a": 1, "b": 3}, 0.048795, "healthy"),
    ({"a": 4, "b": 1}, {"a": 1, "b": 4}, 0.278071, "watch"),
    ({"a": 10, "b": 10, "c": 1}, {"a": 1, "b": 10, "c": 10}, 0.293595, "watch"),
    ({"a": 19, "b": 1}, {"a": 1, "b": 19}, 0.713601, "alarm"),
])
def test_bantlar_healthy_watch_alarm(p, q, deger, bant):
    """D13: JSD_WATCH=0.20 / JSD_ALARM=0.40 bant sinirlari."""
    r = jsd_divergence(p, q)
    assert r.value == pytest.approx(deger, abs=1e-5)
    assert r.band == bant


def test_ayrik_anahtar_kumeleri_alarm():
    """D14: hic ortak anahtar yok -> ~1.0 (base-2 tavan) alarm."""
    r = jsd_divergence({"a": 1}, {"b": 1})
    assert r.value > JSD_ALARM
    assert r.band == "alarm"
    assert r.value < 1.0  # eps nedeniyle tam 1.0 degil


def test_sayim_sifir_anahtar_absent_ile_ayni():
    """D15 QUIRK: {'a':0} anahtari absent anahtarla ayni sekilde EPS'e oturur.

    p={'a':0,'b':2} normalize -> {a:0,b:1}; q='b' -> her iki tarafta da
    a icin 0+EPS=EPS → katki 0 → value=0.0 healthy.
    """
    r = jsd_divergence({"a": 0, "b": 2}, {"b": 2})
    assert r.value == 0.0
    assert r.band == "healthy"


def test_deger_asla_negatif_degil():
    """D16: value = max(0.0, jsd) -> >= 0 garantili."""
    for p, q in [
        ({"a": 1}, {"a": 1}),
        ({"a": 2, "b": 1}, {"b": 2, "a": 1}),
        ({"a": 1, "b": 1, "c": 1}, {"c": 2, "b": 1, "a": 0}),
    ]:
        assert jsd_divergence(p, q).value >= 0.0


def test_tek_anahtarli_sozlukler_hic_dallanamaz():
    """QUIRK: tek anahtarli pencereler normalize'de her zaman {a:1.0} ->
    ayni kategoride olduklari icin JSD=0.0, hicbir zaman dallanamaz."""
    assert jsd_divergence({"a": 1}, {"a": 1}).value == 0.0
    assert jsd_divergence({"a": 10}, {"a": 1}).value == 0.0
    assert jsd_divergence({"a": 999}, {"a": 3}).band == "healthy"


def test_buyuk_sayim_degerleri_olceginden_bagimsiz():
    r1 = jsd_divergence({"a": 1000, "b": 1000}, {"a": 1, "b": 1})
    assert r1.value == 0.0
    r2 = jsd_divergence({"a": 1000000, "b": 1}, {"a": 1, "b": 1000000})
    assert r2.band == "alarm"


def test_jsd_base2_log_kullaniyor():
    """JSD base-2: tam ayrik tek-anahtar ~1.0 (dogal log olsaydi ~0.693)."""
    r = jsd_divergence({"a": 1}, {"b": 1})
    assert r.value == pytest.approx(0.9999806257342256, abs=1e-9)


#-------------------------------------------------------------- mad_robust_z


@pytest.mark.parametrize("vals", [
    [],
    [1.0],
    [1.0, 2.0],
])
def test_ucdan_az_gozlem_none_nan(vals):
    """D17: len<3 -> robust_z=None, alarm=False, median/mad=NaN."""
    r = mad_robust_z(vals)
    assert r.robust_z is None
    assert r.alarm is False
    assert math.isnan(r.median)
    assert math.isnan(r.mad)


def test_tekrarli_degerler_mad_sifir_none():
    """D18: butun degerler ayni -> mad=0 -> robust_z=None, alarm=False."""
    r = mad_robust_z([10.0] * 5)
    assert r.mad == 0.0
    assert r.robust_z is None
    assert r.alarm is False


def test_aykiri_deger_alarm_verir():
    """D19: [10,10,10,12,14,40] -> |z|>>3 alarm (medyan=11, mad=1)."""
    r = mad_robust_z([10.0, 10.0, 10.0, 12.0, 14.0, 40.0])
    assert r.median == 11.0
    assert r.mad == 1.0
    assert r.robust_z == pytest.approx(MAD_SCALE * 29.0)
    assert abs(r.robust_z) > MAD_Z_THRESHOLD
    assert r.alarm is True


def test_kararli_seri_alarm_yok():
    r = mad_robust_z([10.0, 10.1, 9.9, 10.2, 9.8, 10.0])
    assert r.alarm is False
    assert r.robust_z is not None


def test_x_varsayilan_son_eleman():
    """D20: x verilmezse values[-1] ( already-included convention)."""
    r = mad_robust_z([10.0, 10.0, 10.0, 12.0, 14.0, 40.0])
    r_explicit = mad_robust_z([10.0, 10.0, 10.0, 12.0, 14.0, 40.0], x=40.0)
    assert r.robust_z == r_explicit.robust_z
    assert r.robust_z is not None


def test_x_acik_override_farkli_deger():
    r = mad_robust_z([10.0, 10.0, 10.0, 12.0, 14.0, 40.0], x=10.0)
    assert r.robust_z == pytest.approx(MAD_SCALE * (10.0 - 11.0))
    assert r.alarm is False


def test_cift_sayida_eleman_medyan_ortanca_ortalamasi():
    """D21: n=4 -> medyan = (s[1]+s[2])/2; mad de ayni kural."""
    r = mad_robust_z([1.0, 2.0, 3.0, 4.0])
    assert r.median == 2.5
    assert r.mad == 1.0
    assert r.robust_z == pytest.approx(MAD_SCALE * 1.5)  # x=4


def test_tek_sayida_eleman_medyan_ortadaki():
    """D21: n=3 -> medyan s[1]; mad=sapmalarin medyani; x=values[-1]."""
    r = mad_robust_z([1.0, 5.0, 9.0])
    assert r.median == 5.0
    assert r.mad == 4.0
    # x varsayilanda values[-1] = 9.0 (medyan DEGIL) -> 0.6745*(9-5)/4
    assert r.robust_z == pytest.approx(0.6745)


@pytest.mark.parametrize("x,beklenen_alarm", [
    (3.0, False),        # |z| tam 3.0 -> strict > kiyasi alarm YOK
    (3.0001, True),      # |z| 3.0001 -> alarm var
    (-3.0, False),       # negatif yon tam esik -> alarm YOK
])
def test_robust_z_esik_siniri_strict_buyuktur(x, beklenen_alarm):
    """D22/D23/D24: alarm = |robust_z| > 3.0 (strict, abs)."""
    vals = [-0.6745, 0.0, 0.0, 0.6745, 2.0]  # medyan=0.0, mad=0.6745
    r = mad_robust_z(vals, x=x)
    assert r.median == 0.0
    assert r.mad == pytest.approx(0.6745)
    assert r.alarm is beklenen_alarm


def test_negatif_yonde_buyuk_robust_z_alarm_verir():
    """D24: x medyanin cok altinda -> |z|>3 -> alarm=True (abs)."""
    vals = [-0.6745, 0.0, 0.0, 0.6745, 2.0]
    r = mad_robust_z(vals, x=-10.0)
    assert r.robust_z < -MAD_Z_THRESHOLD
    assert r.alarm is True


def test_mad_sabitleri():
    assert MAD_SCALE == 0.6745
    assert MAD_Z_THRESHOLD == 3.0


#--------------------------------------------------------------- cusum_update


def test_negatif_akista_g_sifira_reset():
    """D25: g + (x-mu0-drift) < 0 -> g=0 (Page-Hinkley hafizasiz)."""
    st = CusumState()
    r1 = cusum_update(st, 12.0, 10.0)
    assert r1.g == pytest.approx(1.95)  # 12-10-0.05
    r2 = cusum_update(st, 0.0, 10.0)  # 1.95 + (0-10-0.05) < 0
    assert r2.g == 0.0
    assert r2.alarm is False


def test_devamli_kaymada_alarm_verir():
    """D26: 8 x 14 (mu0=10, drift=0.05) -> her adim +3.95 birikir, 2. adimda alarm."""
    st = CusumState()
    alarmlar = [cusum_update(st, 14.0, 10.0).alarm for _ in range(8)]
    # g: 3.95 (<5), 7.90 (>5), 11.85, ... -> 1. adimdan sonra hep alarm
    assert alarmlar == [False] + [True] * 7
    assert st.g == pytest.approx(3.95 * 8)


def test_sabit_seride_sessiz():
    st = CusumState()
    for _ in range(50):
        assert cusum_update(st, 10.0, 10.0).alarm is False


def test_g_esit_esik_alarm_yok():
    """D27: drift=0, x-mu0 tam 5.0 -> g=5.0 -> strict > alarm YOK."""
    st = CusumState(drift=0.0, threshold=5.0)
    r = cusum_update(st, 15.0, 10.0)
    assert r.g == 5.0
    assert r.alarm is False


def test_g_esik_ustu_alarm_var():
    """D28 float quirk: 15.05-10-0.05 = 5.000000000000001 -> alarm."""
    st = CusumState()  # drift=0.05
    r = cusum_update(st, 15.05, 10.0)
    assert r.g > 5.0
    assert r.alarm is True
    # drift=0 ile ayni adim tam esikte kalarak alarm vermez
    st2 = CusumState(drift=0.0, threshold=5.0)
    assert cusum_update(st2, 15.001, 10.0).alarm is True


def test_ozel_drift_ve_threshold():
    """D29: drift/threshold state uzerinden ozellestirilebilir."""
    st = CusumState(drift=0.5, threshold=2.0)
    r = cusum_update(st, 10.0, 0.0)  # 0 + (10-0-0.5) = 9.5 > 2
    assert r.g == pytest.approx(9.5)
    assert r.alarm is True


def test_negatif_x_ve_mu0_sifir():
    st = CusumState(drift=0.0, threshold=1.0)
    r = cusum_update(st, -3.0, 0.0)
    assert r.g == 0.0  # max(0, -3)
    assert r.alarm is False


def test_g_birikimi_ve_durum_mutasyonu():
    st = CusumState()
    assert cusum_update(st, 11.0, 10.0).g == pytest.approx(0.95)
    assert cusum_update(st, 11.0, 10.0).g == pytest.approx(1.90)
    assert st.g == pytest.approx(1.90)


def test_cusum_sonuc_dataclass_alanlari():
    r = cusum_update(CusumState(), 10.0, 10.0)
    assert isinstance(r, CusumResult)
    assert r.g == 0.0
    assert r.alarm is False
    assert isinstance(r.alarm, bool)


#---------------------------------------------------------------------- psi


@pytest.mark.parametrize("e,a", [
    ({}, {"a": 1}),
    ({"a": 1}, {}),
    ({}, {}),
    ({"a": 0}, {"a": 1}),
])
def test_bos_pencere_none_large_shift_false(e, a):
    """D30: normalize edilemeyen pencere -> value=None, large_shift=False."""
    r = psi(e, a)
    assert r.value is None
    assert r.large_shift is False


def test_ayni_dagilim_deger_sifir():
    """D31: ayni oranlar -> her terim 0 -> value=0.0."""
    r = psi({"ok": 90, "fail": 10}, {"ok": 90, "fail": 10})
    assert r.value == 0.0
    assert r.large_shift is False


def test_buyuk_kayma_large_shift_true():
    """D32: 90/10 -> 40/60 PSI=1.3013 > 0.25 -> large_shift."""
    r = psi({"ok": 90, "fail": 10}, {"ok": 40, "fail": 60})
    assert r.value == pytest.approx(1.30133998163664, abs=1e-9)
    assert r.large_shift is True


def test_kucuk_kayma_large_shift_false():
    """D33: 90/10 -> 88/12 PSI=0.004 -> False."""
    r = psi({"ok": 90, "fail": 10}, {"ok": 88, "fail": 12})
    assert r.value < PSI_LARGE_SHIFT
    assert r.large_shift is False


def test_ayrik_anahtarlar_deger_devasa():
    """D34: ayrik kategoriler -> (ak-ek)*ln(ak/ek) terimleri devasa."""
    r = psi({"a": 1}, {"b": 1})
    assert r.value == pytest.approx(27.631023115927544, abs=1e-9)
    assert r.large_shift is True


def test_psi_dogal_log_tabani():
    """PSI math.log (dogal) kullanir — JSD log2 degil (L196)."""
    e = {"ok": 90, "fail": 10}
    a = {"ok": 40, "fail": 60}
    beklenen = (0.4 - 0.9) * math.log(0.4 / 0.9) + (0.6 - 0.1) * math.log(0.6 / 0.1)
    assert psi(e, a).value == pytest.approx(beklenen, abs=1e-3)


def test_psi_sonuc_dataclass_alanlari():
    r = psi({"a": 1}, {"a": 2})
    assert isinstance(r, PsiResult)
    assert isinstance(r.value, float)
    assert r.large_shift is False


def test_eps_sabit_ve_modul_sabiti():
    assert EPS == 1e-6
    assert PSI_LARGE_SHIFT == 0.25
    assert JSD_WATCH == 0.20
    assert JSD_ALARM == 0.40
    assert EWMA_Z_THRESHOLD == 2.5
