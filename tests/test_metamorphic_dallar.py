"""test_metamorphic_dallar.py — swarmax/metrics/metamorphic.py dal-kesen suite.

Kural-1: SADECE Yeni test dosyasi; production/conftest/mevcut testlere
DOKUNULMADI. test_metamorphic_end_dallar.py zaten `_end_states_diverge`
ozel fonksiyonunu exhausif cover ediyor — BU dosya ONUN YERINE GECMEZ,
`MetamorphicEngine` public sinif yuzeyine (cover-edilmeyen kisma) odaklanir.
Kural-4: saf-bellek (network/subprocess/socket YOK).

ORTAM-ANATOMI (src/swarmax/metrics/metamorphic.py L18-55):
  MetamorphicEngine:
    record_traffic(events=1)            -> None   (L27-28)
    can_shadow_rerun()                  -> bool   (L30-33)
    note_shadow_rerun(task_id)          -> None   (L35-40)
    observe_end_state(tmpl, end_state)  -> bool   (L43-55)

DAL HARITASI (D1..Dn):

  record_traffic:
    D1  varsayilan events=1
    D2  coklu events birikimi
    D3  events=0 -> degisim yok
    D4  NEGATIF events -> sayaci AZALTIR (L28'da hag guard YOK — bug suphesi)

  can_shadow_rerun:
    D5  agent_day_events==0 -> True (L31 '<=0' kolu)
    D6  (reruns+1)/events <= 0.01 -> True
    D7  tam esik 1/100 = 0.01 -> True (<= kiyasi)
    D8  esik ustu -> False
    D9  tek event -> 1/1=1.0 -> False (tek bile event golveyi kapatir)

  note_shadow_rerun:
    D10 sayaci artirir
    D11 events=0 iken overflow notu YAZILMAZ (L39 'and' kisa-devre guard)
    D12 tam esik 2/200=0.01 -> overrun YOK (strict >)
    D13 esik ustu 3/200=0.015 -> overrun listesine eklenir
    D14 coklu overrun'lar sirayla eklenir

  observe_end_state:
    D15 ilk kosum -> False (oncel yok, L51 'if prior' kolu)
    D16 farkli end-state -> True (ihlal)
    D17 ayni end-state -> False
    D18 ROLLING referans: prior[-1] ile karsilastirir (prior[0] DEGIL, L52)
    D19 sablonlar birbirinden bagimsiz izole
    D20 history birikimi (her kosum append)
    D21 bos end_state dict'leri
    D22 ALIASING: end_state referans saklanir, caller mutate ederse gecmisi bozar
    D23 her zaman bool doner

  Sinif-seviyesi:
    D24 default_factory: her ornek bagimsiz (paylasilan sinif durumu YOK)
    D25 OUTPUT_QUALITY_BUDGET sabiti = 0.01
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax.metrics.metamorphic import (  # noqa: E402
    OUTPUT_QUALITY_BUDGET,
    MetamorphicEngine,
)

#--------------------------------------------------------- record_traffic


def test_baslangic_durumu_bos_motor():
    """D24: taze motor — hicbir gecmis, sifir sayaclar, bos overflow."""
    m = MetamorphicEngine()
    assert m.history == {}
    assert m.shadow_reruns == 0
    assert m.agent_day_events == 0
    assert m.budget_overruns == []


def test_record_traffic_varsayilan_bir():
    """D1: events parametresiz -> agent_day_events=1."""
    m = MetamorphicEngine()
    m.record_traffic()
    assert m.agent_day_events == 1


def test_record_traffic_coklu_events_birikir():
    """D2: events degerleri birikimli eklenir."""
    m = MetamorphicEngine()
    m.record_traffic(10)
    m.record_traffic(5)
    m.record_traffic(85)
    assert m.agent_day_events == 100


def test_record_traffic_sifir_degisim_yok():
    """D3: events=0 -> sayaç degismez."""
    m = MetamorphicEngine()
    m.record_traffic(42)
    m.record_traffic(0)
    assert m.agent_day_events == 42


def test_record_traffic_negatif_sayaci_azaltir():
    """D4 (BULGU): L28 'self.agent_day_events += events' negatif guard'i YOK.

    Negatif bir deger sayaci geriye goturur — can_shadow_rerun payini
    suni olarak buyutup R5 (<=1%) butce disiplimini atlatmak icin KULLANILABILIR.
    Production'a dokunmuyoruz; sadece davranisi donduruyoruz.
    """
    m = MetamorphicEngine()
    with pytest.raises(ValueError, match="non-negative"):
        m.record_traffic(-5)   # MT-R5A (DUZELTILDI): negatif-olum-RED


#------------------------------------------------------- can_shadow_rerun


def test_sifir_trafik_golge_yok_der():
    """D5 (DUZELTILDI MT-R5B): agent_day_events<=0 -> False. Olculmemis-gunde
    R5-butce-payi-kanitlanamaz — fail-open (True) R5-sozlesmesini-atlatirdi."""
    m = MetamorphicEngine()
    assert m.can_shadow_rerun() is False


def test_tek_event_golge_izin_vermez():
    """D9: (0+1)/1 = 1.0 > 0.01 -> tek traffic bile butçeyi asar."""
    m = MetamorphicEngine()
    m.record_traffic(1)
    assert m.can_shadow_rerun() is False


def test_tam_esik_yuzde_bir_izin_verir():
    """D7: 100 event, 0 rerun -> (0+1)/100 = 0.01 <= 0.01 -> True."""
    m = MetamorphicEngine()
    m.record_traffic(100)
    assert m.can_shadow_rerun() is True


@pytest.mark.parametrize("events,reruns,beklenen", [
    (0, 0, False),       # events<=0 (MT-R5B): olculmemis-gun-payi-kanitlanamaz
    (1, 0, False),       # 1/1 = 1.0
    (100, 0, True),      # 1/100 = 0.01 tam esik
    (100, 1, False),     # 2/100 = 0.02
    (200, 1, True),      # 2/200 = 0.01 tam esik
    (200, 2, False),     # 3/200 = 0.015
    (1000, 9, True),     # 10/1000 = 0.01 tam esik
    (1000, 10, False),   # 11/1000 = 0.011
    (99, 0, False),      # 1/99 = 0.0101
])
def test_can_shadow_rerun_esik_dallari(events, reruns, beklenen):
    """D6/D7/D8: (shadow_reruns+1)/agent_day_events <= 0.01 butce kiyasi."""
    m = MetamorphicEngine()
    m.record_traffic(events)
    m.shadow_reruns = reruns
    assert m.can_shadow_rerun() is beklenen


def test_can_shadow_rerun_bool_donuyor():
    m = MetamorphicEngine()
    assert isinstance(m.can_shadow_rerun(), bool)


#------------------------------------------------------- note_shadow_rerun


def test_note_shadow_rerun_sayaci_artirir():
    """D10: her golge tekrar sayaci 1 artirir."""
    m = MetamorphicEngine()
    m.note_shadow_rerun("t1")
    m.note_shadow_rerun("t2")
    assert m.shadow_reruns == 2


def test_note_shadow_rerun_events_yok_overflow_yazilmaz():
    """D11: agent_day_events=0 -> L39 'and' kisa-devre -> overrun YOK."""
    m = MetamorphicEngine()
    m.note_shadow_rerun("t1")
    m.note_shadow_rerun("t2")
    assert m.budget_overruns == []
    assert m.shadow_reruns == 2


def test_note_shadow_rerun_tam_esik_overflow_yok():
    """D12: 200 event + 2 rerun -> 2/200=0.01 > 0.01 DEGIL -> overrun YOK."""
    m = MetamorphicEngine()
    m.record_traffic(200)
    m.note_shadow_rerun("r1")
    m.note_shadow_rerun("r2")
    assert m.budget_overruns == []
    assert m.shadow_reruns == 2


def test_note_shadow_rerun_esik_ustu_overflow_eklenir():
    """D13: 200 event + 3. rerun -> 3/200=0.015 > 0.01 -> ['r3']."""
    m = MetamorphicEngine()
    m.record_traffic(200)
    m.note_shadow_rerun("r1")
    m.note_shadow_rerun("r2")
    m.note_shadow_rerun("r3")
    assert m.budget_overruns == ["r3"]


def test_note_shadow_rerun_coklu_overflow_sirayla():
    """D14: birden fazla overrun girisi sirayla eklenir."""
    m = MetamorphicEngine()
    m.record_traffic(100)
    for i in range(1, 6):
        m.note_shadow_rerun(f"g{i}")
    # 1/100=0.01 ve 2/100=0.02 esik; g2'den itibaren hep overrun
    assert m.budget_overruns == ["g2", "g3", "g4", "g5"]
    assert m.shadow_reruns == 5


def test_note_shadow_rerun_events_basina_overflow_yok():
    """100 event, ilk rerun: 1/100=0.01 > 0.01 degil -> overrun YOK."""
    m = MetamorphicEngine()
    m.record_traffic(100)
    m.note_shadow_rerun("t1")
    assert m.budget_overruns == []


#------------------------------------------------------- observe_end_state


def test_observe_ilk_kosum_ihlal_yok():
    """D15: sablon icin ilk kayit -> oncel yok -> False (L51 kolu)."""
    m = MetamorphicEngine()
    assert m.observe_end_state("sablon", {"records_created": 3}) is False


def test_observe_farkli_end_state_ihlal():
    """D16: onceki kayittan farkli end-state -> drift ihlali True."""
    m = MetamorphicEngine()
    m.observe_end_state("sablon", {"records_created": 3})
    assert m.observe_end_state("sablon", {"records_created": 0}) is True


def test_observe_ayni_end_state_ihlal_yok():
    """D17: onceki ile ayni end-state -> False."""
    m = MetamorphicEngine()
    m.observe_end_state("sablon", {"records_created": 3})
    assert m.observe_end_state("sablon", {"records_created": 3}) is False


def test_observe_rolling_referans_prior_sonuncu():
    """D18 (KRITIK): L52 'reference = prior[-1]' — ILK kayitla DEGIL,
    EN SON kayitla karsilastirir. A,B,A,A -> False,True,True,False."""
    m = MetamorphicEngine()
    assert m.observe_end_state("t", {"a": 1}) is False  # ilk: oncel yok
    assert m.observe_end_state("t", {"a": 2}) is True   # 1'i bozdu
    assert m.observe_end_state("t", {"a": 1}) is True   # 2'yi bozdu (1'e dondu)
    assert m.observe_end_state("t", {"a": 1}) is False  # 1'e esit
    assert len(m.history["t"]) == 4


def test_observe_sablon_izolasyonu():
    """D19: bir sablonun gecmisi digerini etkilemez."""
    m = MetamorphicEngine()
    m.observe_end_state("X", {"n": 1})
    m.observe_end_state("X", {"n": 2})   # X icin ihlal
    assert m.observe_end_state("Y", {"n": 1}) is False  # Y ilk kayit
    assert m.observe_end_state("Y", {"n": 1}) is False  # Y ayni
    assert m.observe_end_state("X", {"n": 2}) is False  # X kendine esit


def test_observe_history_birikimi():
    """D20: her kosum history[tmpl] listesine append edilir."""
    m = MetamorphicEngine()
    for v in range(5):
        m.observe_end_state("t", {"v": v})
    assert m.history["t"] == [{"v": 0}, {"v": 1}, {"v": 2}, {"v": 3}, {"v": 4}]


def test_observe_bos_end_state_dict():
    """D21: bos end_state dict'leri icin de ayni kurallar gecerli."""
    m = MetamorphicEngine()
    assert m.observe_end_state("t", {}) is False
    assert m.observe_end_state("t", {}) is False
    assert m.observe_end_state("t", {"x": 1}) is True  # key set farki


def test_observe_gomulu_yapi_ihlal():
    """Gomulu dict/list end-state degiskenleri divergence'a gider."""
    m = MetamorphicEngine()
    m.observe_end_state("t", {"files": ["a", "b"], "meta": {"k": 1}})
    assert m.observe_end_state(
        "t", {"files": ["a", "b"], "meta": {"k": 2}}) is True
    assert m.observe_end_state(
        "t", {"files": ["b", "a"], "meta": {"k": 2}}) is True  # liste sirasi
    assert m.observe_end_state(
        "t", {"files": ["b", "a"], "meta": {"k": 2}}) is False


def test_observe_referans_takma_alising_kopyali():
    """D22 (DUZELTILDI MT-R5C): 'prior.append(end_state)' eskiden-referans-
    sakliyordu — caller'in-observe-sonrasi-mutasyonu-gecmisi-retroaktif-
    degistirip-divergence-sonucunu-sekillendiriyordu. Artik-derin-kopya:
    mutasyon-gecmise-ulasmaz, {a:1}-kayidi-eski-referansla-esit-kalir."""
    m = MetamorphicEngine()
    d = {"a": 1}
    m.observe_end_state("t", d)
    d["a"] = 999  # caller gecmise sonradan mudahale edemez artik
    assert m.observe_end_state("t", {"a": 1}) is False
    assert m.history["t"][0] == {"a": 1}


def test_observe_bool_donuyor():
    m = MetamorphicEngine()
    assert isinstance(m.observe_end_state("t", {}), bool)
    assert isinstance(m.observe_end_state("t", {}), bool)


#--------------------------------------------------------- sinif-seviyesi


def test_default_factory_ornekler_bagimsizdir():
    """D24: field(default_factory=...) — her ornek kendi list/dict'ine sahip."""
    m1 = MetamorphicEngine()
    m2 = MetamorphicEngine()
    m1.history["t"] = [{}]
    m1.budget_overruns.append("x")
    m1.record_traffic(5)
    assert m2.history == {}
    assert m2.budget_overruns == []
    assert m2.agent_day_events == 0


def test_output_quality_budget_sabiti():
    """D25: R5 — golge tekrar payi <= %1 (§3.2-7)."""
    assert OUTPUT_QUALITY_BUDGET == 0.01


def test_end_to_end_butce_ve_ihlal_akisi():
    """Tam akis: traffic olc -> izin al -> rerun -> ihlal tespit et."""
    m = MetamorphicEngine()
    for _ in range(100):
        m.record_traffic(1)
    assert m.can_shadow_rerun() is True
    # golge tekrar: ayni sablonun end-state'i farkli cikti
    once = m.observe_end_state("golge-sablon", {"records_created": 5})
    m.note_shadow_rerun("g1")
    assert once is False
    assert m.can_shadow_rerun() is False  # 2/100 butce asimi
    ihlal = m.observe_end_state("golge-sablon", {"records_created": 4})
    m.note_shadow_rerun("g2")             # butce asimi yapildi -> audit
    assert ihlal is True
    assert m.budget_overruns == ["g2"]
