"""test_apd_dallar.py — swarmax/metrics/apd.py dal-kesen test suite.

ORTAM-ANATOMI (src/swarmax/metrics/apd.py, 180 satir) — public API:
  EWMA_MULTIPLIER (L19)      -> 2.0  (§4.2: gunluk maliyet > 2.0×EWMA-µ)
  SEVERITY_ORDER  (L23)      -> {"Info":0 ... "Emergency":5}
  Rule            (L26)      -> frozen dataclass (signal/sekildeki alanlar)
  SIGNAL_MAP      (L37)      -> 9 kuralin signal→Rule haritasi (§4.2)
  Alarm           (L60)      -> dataclass; suppressed varsayilan False
  FpBudget        (L71)      -> record_cycle / ratio / within_budget (R10)
  CalibrationWindow (L91)    -> closed_by() = opened_at + days
  FleetApd        (L102)     -> durum sahibi; fact_* degerlendiricileri + evaluate

DAL HARITASI (D1..D56): her public dal icin basari/basarisiz/sinir testi:
  FpBudget (L76-87):
    D1  record_cycle her halukarda cycles'i artirir
    D2  record_cycle(true) false_positives'i artirir
    D3  record_cycle(false) false_positives'i degistirmez
    D4  cycles=0 iken ratio -> 0.0 (sifirla-bolme korumasi)
    D5  ratio = false_positives / cycles
    D6  within_budget siniri: ratio == 0.05 tam esitte True (<=)
    D7  within_budget: ratio > 0.05 -> False
    D8  sifir devirli budget -> True (0.0 <= 0.05)
  CalibrationWindow (L93-98):
    D9  varsayilan days=14, closed=False; closed_by() opened_at+14 gun
    D10 days parametresi closed_by()'yi souncular (1/30/90)
    D11 sentetik agent penceresi onceden kapali (R10)
  FleetApd state erisimleri (L114-123):
    D12 window_for ayni agent icin ayni nesne (kimlik kararliligi)
    D13 window_for(synthetic=True) kapali pencere olusturur
    D14 classifier_for ayni agent icin ayni nesne; farkli agent farkli
    D15 loop_breaker_for ayni gorev icin ayni nesne; farkti gorev farkli
  fact_cost_spike (L126-131):
    D16 kalibrasyon disi (calibrated=False) -> isitsa patlamasi bile False
    D17 R3 isitma disiplini: n<30 iken spike False (29. guncellemede)
    D18 tam spike: alarm + mu>0 + daily>2.0×EWMA -> True
    D19 alarm ama mu <= 0 (negatif maliyet) -> False (mu-koruma)
    D20 alarm ama daily <= 2.0×mu (yuksek mu, kucuk spike) -> False
    D21 ewma durumu agent basina cagrilar arasi paylasilir (kumulatif n)
  fact_error_class (L133-140):
    D22 loop_detected=True -> ("loop", False) passthrough
    D23 loop passthrough classifier'i gormez (seen set bos kalir)
    D24 ham hatadan siniflandirma (timeout/auth/parse/.../unknown)
    D25 ilk gozlem -> (sinif, True); ayni sinif tekrar -> (sinif, False)
  fact_tool_drift (L142-144):
    D26 jsd band "alarm" -> True
    D27 "watch"/"healthy"/"warming_up" -> False
  fact_loop (L146-148):
    D28 3 ayni cagri -> True (esik tam olarak 3)
    D29 1-2 cagri -> False; farkli arac run'u kirar
    D30 A-A-B-A-A-A -> 6. cagri True (pencere konumsal, kumulatif sayim YOK)
    D31 acik kirici kisa-devre: True doner, hash eklenmez
  fact_new_class (L149-150): D32 ilk -> True, ikinci -> False
  fact_output_quality (L152-156):
    D33 ilk kosum (oncesiz) -> False
    D34 farkli end-state -> True; ayni -> False
    D35 eksik/ekstra key -> True
    D36 ihlal audit_notes'a "drift.output_quality:{template}" notu düser
    D37 kiyas her zaman son onceki run ile (prior[-1]) yapilir
  evaluate (L159-175):
    D38 bos facts -> []
    D39 fired=False olan sinyal atlanir
    D40 SIGNAL_MAP disi sinyal atlanir (bilinmeyene sessiz gec)
    D41 acik pencere + fires_during_calibration=False -> suppressed=True
    D42 acik pencere + fires_during_calibration=True -> suppressed=False
    D43 kapali pencere -> HIC baskilama yok
    D44 Alarm alanlari SIGNAL_MAP kuraliyla birebir esler (9 kural)
    D45 baskilama audit_notes'a "calibration_suppressed:{agent}:{sig}"
    D46 alarm sirasi facts sirasini korur (dict insertion order)
    D47 sentetik agent (onceden kapali pencere) -> baskilanmaz
    D48 evaluate pencereyi talep-uzerine olusturur (closed=False)
  fact_ticket_aging (L179-180):
    D49 24 saatten fazla -> True
    D50 tam 24 saat (esit) -> False (katı >)
    D51 24 saatten az / gelecek tarih -> False
    D52 ozel limit_h siniri tam esit -> False, asim -> True
  Sabitler/harita butunlugu:
    D53 EWMA_MULTIPLIER == 2.0; SIGNAL_MAP 9 kayit; signal == key
    D54 SEVERITY_ORDER Info..Emergency 0..5; kurallarin severities gecerli
    D55 Rule frozen -> mutating FrozenInstanceError
    D56 Alarm varsayilan suppressed=False

Kural-1: SADECE yeni test dosyasi — production/conftest DOKUNULMADI.
Kural-4: saf-bellek — network/DNS/subprocess/socket YOK; hepsi in-memory.
Deterministik: hic RNG yok; tum EWMA/JSD verileri onceden hesaplandi.
"""
from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, "src")

from swarmax.metrics.apd import (  # noqa: E402
    EWMA_MULTIPLIER,
    SEVERITY_ORDER,
    SIGNAL_MAP,
    Alarm,
    CalibrationWindow,
    FleetApd,
    FpBudget,
    Rule,
)

# Deterministik EWMA tabanlari (onceden dogrulandi, Kural: RNG'siz)
baseline_miagr = [10.0 + (i % 5) for i in range(30)]      # mu>0, sigma kucuk
baseline_neg   = [-10.0 - (i % 5) for i in range(30)]     # mu<0 patlamasi
baseline_high  = [100.0 + (i % 3) * 0.5 for i in range(60)]  # mu~100


# ============================================================ FpBudget

class TestFpBudget:
    """R10 FP budget: saatlik degerlendirme donguleri basina <= %5 FP."""

    def test_record_cycle_sayaci_her_halukarda_artar(self):
        b = FpBudget()
        b.record_cycle()
        b.record_cycle(True)
        assert b.cycles == 2
        assert b.false_positives == 1

    @pytest.mark.parametrize("fp_flags,beklenen_fp", [
        ([], 0),
        ([False, False, False], 0),
        ([True], 1),
        ([False, True, False, True], 2),
    ])
    def test_record_cycle_fp_sayimi_dogrudur(self, fp_flags, beklenen_fp):
        b = FpBudget()
        for fp in fp_flags:
            b.record_cycle(fp)
        assert b.cycles == len(fp_flags)
        assert b.false_positives == beklenen_fp

    @pytest.mark.parametrize("cycles,fp,beklenen_ratio,beklenen_ici", [
        (0, 0, 0.0, True),            # D4+D8: sifir devir -> 0.0, True
        (20, 0, 0.0, True),
        (20, 1, 0.05, True),          # D6: tam sinirda True (<=)
        (100, 5, 0.05, True),         # D6: 5/100 tam esik
        (1000, 51, 0.051, False),     # D7: esigi asar
        (20, 2, 0.1, False),
        (19, 1, 1 / 19, False),       # 5.26% -> disarida
        (100, 100, 1.0, False),
    ])
    def test_ratio_ve_within_budget_sinirlari(self, cycles, fp,
                                              beklenen_ratio, beklenen_ici):
        b = FpBudget(cycles=cycles, false_positives=fp)
        assert b.ratio == pytest.approx(beklenen_ratio)
        assert b.within_budget is beklenen_ici


# ============================================================ CalibrationWindow

class TestKalibrasyonPenceresi:
    """§3.3: agent basina 14 gun kalibrasyon; sentetik onceden kapali."""

    def test_varsayilan_14_gun_ve_acik(self):
        w = CalibrationWindow()
        assert w.days == 14
        assert w.closed is False
        assert w.closed_by() == w.opened_at + timedelta(days=14)

    @pytest.mark.parametrize("gun", [1, 7, 14, 30, 90])
    def test_days_parametresi_closed_by_sonucunu_belirler(self, gun):
        acilis = datetime(2026, 1, 1, 12, 0, 0)
        w = CalibrationWindow(days=gun, opened_at=acilis)
        assert w.closed_by() == acilis + timedelta(days=gun)

    def test_sentetik_agent_penceresi_onceden_kapali(self):
        w = CalibrationWindow(closed=True)
        assert w.closed is True


# ============================================================ FleetApd state erisimleri

class TestDurumErisimcileri:
    """window_for / classifier_for / loop_breaker_for kimlik kararliligi."""

    def test_window_for_ayni_agent_icin_ayni_nesne(self):
        apd = FleetApd()
        assert apd.window_for("a1") is apd.window_for("a1")

    def test_window_for_farkli_agent_farkli_pencere(self):
        apd = FleetApd()
        assert apd.window_for("a1") is not apd.window_for("a2")

    def test_window_for_sentetik_acilista_kapali(self):
        apd = FleetApd()
        assert apd.window_for("s1", synthetic=True).closed is True
        assert apd.window_for("r1").closed is False

    def test_classifier_for_kimlik_kararliligi(self):
        apd = FleetApd()
        assert apd.classifier_for("a1") is apd.classifier_for("a1")
        assert apd.classifier_for("a1") is not apd.classifier_for("a2")

    def test_loop_breaker_for_gorev_basina(self):
        apd = FleetApd()
        assert apd.loop_breaker_for("t1") is apd.loop_breaker_for("t1")
        assert apd.loop_breaker_for("t1") is not apd.loop_breaker_for("t2")

    def test_metamorphic_motor_paylasilir(self):
        apd = FleetApd()
        assert apd.metamorphic is apd.metamorphic

    def test_baslangicta_diziler_bos_ve_denetim_notu_bos(self):
        apd = FleetApd()
        assert apd.ewma == {}
        assert apd.classifiers == {}
        assert apd.loop_breakers == {}
        assert apd.windows == {}
        assert apd.audit_notes == []
        assert apd.fp_budget.cycles == 0


# ============================================================ fact_cost_spike

class TestFactCostSpike:
    """§4.2 kosul: Z > 2.5 AND daily > 2.0×EWMA-µ (R3 isitma + kalibrasyon)."""

    @staticmethod
    def _besle(apd, agent, seri, kalibre):
        for c in seri:
            sonuc = apd.fact_cost_spike(agent, c, calibrated=kalibre)
        return sonuc

    def test_kalibrasyon_disi_spike_patlamaz(self):
        apd = FleetApd()
        sonuc = self._besle(apd, "a1", baseline_miagr + [60.0], kalibre=False)
        # D16: 41 gozlem + buyuk spike ama calibrated=False -> False
        assert sonuc is False
        assert apd.ewma["a1"].n == 31

    def test_isitma_disiplini_n29_spike_false(self):
        apd = FleetApd()
        # D17: 28 taban + 60.0 (29. guncelleme) -> n=29 < 30 -> False
        sonuc = self._besle(apd, "a1", baseline_miagr[:28] + [60.0], kalibre=True)
        assert apd.ewma["a1"].n == 29
        assert sonuc is False

    def test_n30_isinca_silahlanir_ve_tam_spikey_atesler(self):
        apd = FleetApd()
        # D18: 30 taban + 60.0 -> armed, mu=19.46, z=3.15, 60 > 2×mu
        sonuc = self._besle(apd, "a1", baseline_miagr + [60.0], kalibre=True)
        assert sonuc is True
        assert apd.ewma["a1"].n == 31

    def test_mu_sifirdan_kucukse_alarm_duser(self):
        apd = FleetApd()
        # D19: negatif maliyetler -> z=2.94 alarm Ama mu=-10.6 <= 0 -> False
        sonuc = self._besle(apd, "a1", baseline_neg + [-1.0], kalibre=True)
        assert sonuc is False

    def test_iki_kat_ewma_esigi_asilmazsa_false(self):
        apd = FleetApd()
        # D20: mu~100.9, z=2.78 alarm Ama 103 <= 2×100.9 -> False
        sonuc = self._besle(apd, "a1", baseline_high + [103.0], kalibre=True)
        assert sonuc is False

    @pytest.mark.parametrize("deger", [11.0, 9.0, 12.0])
    def test_normal_degerler_spike_degildir(self, deger):
        apd = FleetApd()
        sonuc = self._besle(apd, "a1", baseline_miagr + [deger], kalibre=True)
        assert sonuc is False

    def test_ewma_durumu_cagrilar_arasi_paylasilir(self):
        apd = FleetApd()
        for c in baseline_miagr:
            apd.fact_cost_spike("a1", c, calibrated=True)
        assert apd.ewma["a1"].n == 30
        # D21: ayni agentin 31. guncellemesi state uzerinden devam eder
        assert apd.fact_cost_spike("a1", 60.0, calibrated=True) is True
        assert apd.ewma["a1"].n == 31

    def test_ewma_durumu_agent_basina_izole(self):
        apd = FleetApd()
        for c in baseline_miagr:
            apd.fact_cost_spike("a1", c, calibrated=True)
        apd.fact_cost_spike("a2", 60.0, calibrated=True)
        assert apd.ewma["a1"].n == 30
        assert apd.ewma["a2"].n == 1


# ============================================================ fact_error_class

class TestFactErrorClass:
    """MAST siniflandirmasi + loop passthrough + first-seen."""

    def test_loop_passthrough_loop_ve_yeni_degildir(self):
        apd = FleetApd()
        # D22: loop_detected -> ("loop", False)
        assert apd.fact_error_class("a1", "Timeout", loop_detected=True) == ("loop", False)

    def test_loop_passthrough_classifier_gormez(self):
        apd = FleetApd()
        apd.fact_error_class("a1", "Timeout", loop_detected=True)
        # D23: seen set hala bos
        assert apd.classifier_for("a1").seen == set()

    @pytest.mark.parametrize("ham_hatA,beklenen_sinif", [
        ("Connection timed out", "timeout"),
        ("request timed out after 30s", "timeout"),
        ("401 Unauthorized", "auth"),
        ("permission denied for scope", "auth"),
        ("invalid json: parse error", "parse"),
        ("schema validation failed", "parse"),
        ("tool runner crashed with 500", "tool_fail"),
        ("api rate limit 429", "tool_fail"),
        ("verify step failed", "verification_fail"),
        ("handoff mismatch between agents", "interagent_mismatch"),
        ("ambiguous requirement spec", "spec_ambiguity"),
        ("totally weird failure", "unknown"),
        ("schema drift detected", "schema_drift"),
        ("truncated partial response", "partial_response"),
    ])
    def test_ham_hatadan_siniflandirma(self, ham_hatA, beklenen_sinif):
        apd = FleetApd()
        # D24: classify + observe
        sinif, yeni = apd.fact_error_class("a1", ham_hatA)
        assert sinif == beklenen_sinif
        assert yeni is True

    def test_ilk_gozlem_yeni_ikincisi_degil(self):
        apd = FleetApd()
        # D25: ayni sinifin ikinci gozlemi yeni sayilmaz
        assert apd.fact_error_class("a1", "Timeout")[1] is True
        assert apd.fact_error_class("a1", "Timeout")[1] is False

    def test_farkli_siniflar_ayri_ayri_yeni(self):
        apd = FleetApd()
        apd.fact_error_class("a1", "Timeout")
        assert apd.fact_error_class("a1", "401 Unauthorized")[1] is True
        assert apd.classifier_for("a1").seen == {"timeout", "auth"}

    def test_loop_passthrough_sonrasi_normal_siniflandirma(self):
        apd = FleetApd()
        apd.fact_error_class("a1", "Timeout", loop_detected=True)
        # loop passthrough classify'i etkilemez
        assert apd.fact_error_class("a1", "Timeout") == ("timeout", True)


# ============================================================ fact_tool_drift

class TestFactToolDrift:
    """JSD band takibi: yalnizca "alarm" bandi drift sinyali üretir."""

    @pytest.mark.parametrize("p7d,q24h,beklenen", [
        # D26: alarm bandi
        ({"a": 3, "b": 0, "c": 0}, {"a": 1, "b": 2, "c": 0}, True),
        ({"git": 10, "ls": 0}, {"git": 0, "ls": 10}, True),
        # D27: watch bandi (0.20..0.40)
        ({"a": 95, "b": 5}, {"a": 50, "b": 50}, False),
        ({"git": 90, "ls": 10}, {"git": 40, "ls": 60}, False),
        ({"a": 4, "b": 1}, {"a": 1, "b": 4}, False),
        # D27: healthy bandi
        ({"git": 5, "ls": 3}, {"git": 5, "ls": 3}, False),
        ({"a": 8, "b": 2}, {"a": 6, "b": 4}, False),
        # D27: warming_up (bos pencere)
        ({}, {"a": 1}, False),
        ({}, {}, False),
        ({"a": 0}, {"a": 1}, False),
    ])
    def test_band_sinyali_alarm_midir(self, p7d, q24h, beklenen):
        apd = FleetApd()
        assert apd.fact_tool_drift(p7d, q24h) is beklenen

    def test_band_metodu_durum_degismez(self):
        # D26: statik metot — FleetApd durumuna (ewma/windows) dokunmaz
        apd = FleetApd()
        apd.fact_tool_drift({"a": 3, "b": 0, "c": 0}, {"a": 1, "b": 2, "c": 0})
        assert apd.audit_notes == []
        assert apd.windows == {}


# ============================================================ fact_loop

class TestFactLoop:
    """LoopBreaker sarmalayicisi: 3 ayni-hash cagri -> True (§3.2-3)."""

    def test_uc_ayni_cagri_acar(self):
        apd = FleetApd()
        args = {"cmd": "ls", "path": "/tmp"}
        assert apd.fact_loop("t1", "shell", args) is False
        assert apd.fact_loop("t1", "shell", args) is False
        # D28: esik tam olarak 3
        assert apd.fact_loop("t1", "shell", args) is True

    def test_iki_cagri_acmaz(self):
        apd = FleetApd()
        for _ in range(2):
            assert apd.fact_loop("t1", "shell", {"cmd": "ls"}) is False

    def test_farkli_arac_runu_kirar(self):
        apd = FleetApd()
        apd.fact_loop("t1", "shell", {"cmd": "ls"})
        apd.fact_loop("t1", "shell", {"cmd": "ls"})
        # D29: ucuncu cagri farkli arac -> run kirilir
        assert apd.fact_loop("t1", "python", {"cmd": "ls"}) is False

    def test_farkli_arguman_runu_kirar(self):
        apd = FleetApd()
        apd.fact_loop("t1", "shell", {"cmd": "ls"})
        apd.fact_loop("t1", "shell", {"cmd": "ls"})
        assert apd.fact_loop("t1", "shell", {"cmd": "rm", "path": "/"}) is False

    def test_anahtar_sirasi_farkli_ayni_hash_run_devam(self):
        apd = FleetApd()
        apd.fact_loop("t1", "shell", {"cmd": "ls", "path": "/tmp"})
        apd.fact_loop("t1", "shell", {"path": "/tmp", "cmd": "ls"})
        # normalize_arguments sort_keys ile ayni hash -> 3. ayni cagri acar
        assert apd.fact_loop("t1", "shell", {"path": "/tmp", "cmd": "ls"}) is True

    def test_pencere_konumsal_AABA_AA_altinci_acar(self):
        apd = FleetApd()
        a = {"cmd": "ls"}
        b = {"cmd": "ps"}
        apd.fact_loop("t1", "shell", a)
        apd.fact_loop("t1", "shell", a)
        apd.fact_loop("t1", "shell", b)
        apd.fact_loop("t1", "shell", a)
        apd.fact_loop("t1", "shell", a)
        # D30: 5. cagrida son-3 = A-A-A degil (A,B,A); 6. da A
        assert apd.fact_loop("t1", "shell", a) is True
        assert len(apd.loop_breakers["t1"].hashes) == 6

    def test_kumulatif_sayim_yok_ABA_A(self):
        apd = FleetApd()
        apd.fact_loop("t1", "shell", {"cmd": "ls"})
        apd.fact_loop("t1", "python", {"cmd": "ls"})
        # D30: toplam 3 ayni-hash var ama konumsal degil -> False
        assert apd.fact_loop("t1", "shell", {"cmd": "ls"}) is False

    def test_acik_kirici_kisadevre_hash_eklenmez(self):
        apd = FleetApd()
        a = {"cmd": "ls"}
        for _ in range(3):
            apd.fact_loop("t1", "shell", a)
        assert apd.loop_breakers["t1"].opened is True
        # D31: acikken her cagri True ama hash eklenmez
        assert apd.fact_loop("t1", "shell", {"cmd": "ps"}) is True
        assert apd.fact_loop("t1", "shell", a) is True
        assert len(apd.loop_breakers["t1"].hashes) == 3

    def test_gorev_izolasyonu(self):
        apd = FleetApd()
        for _ in range(3):
            apd.fact_loop("t1", "shell", {"cmd": "ls"})
        # baska gorev ayni kalipta acmaz
        assert apd.fact_loop("t2", "shell", {"cmd": "ls"}) is False
        assert apd.loop_breakers["t2"].opened is False
        assert apd.loop_breakers["t1"].opened is True


# ============================================================ fact_new_class

class TestFactNewClass:
    """Classifier.observe sarmalayicisi: ilk-seen disiplini."""

    @pytest.mark.parametrize("sinif", [
        "timeout", "auth", "parse", "tool_fail", "verification_fail",
        "interagent_mismatch", "spec_ambiguity", "unknown",
    ])
    def test_ilk_seen_true_ikincisi_false(self, sinif):
        apd = FleetApd()
        assert apd.fact_new_class("a1", sinif) is True
        assert apd.fact_new_class("a1", sinif) is False

    def test_preseen_siniflarda_agent_icin_ilk_seen_true(self):
        # classifier.observe PRESEEN_CLASSES'i gormez; agent iki ilk-seen
        apd = FleetApd()
        assert apd.fact_new_class("a1", "tool_fail") is True
        assert apd.fact_new_class("a1", "tool_fail") is False
        assert apd.classifier_for("a1").seen == {"tool_fail"}


# ============================================================ fact_output_quality

class TestFactOutputQuality:
    """Metamorfik end-state denkleme oracvu (§3.2-7)."""

    @staticmethod
    def _sonuc(apd, sablon, end):
        return apd.fact_output_quality(sablon, end)

    @pytest.mark.parametrize("end_state", [
        {"records_created": 1, "notifications_sent": 2},
        {},
        {"files": {"hash": "abc"}, "uptime": 99.0},
    ])
    def test_ilk_kosum_ihlal_degildir(self, end_state):
        apd = FleetApd()
        # D33: oncesi yok -> her zaman False
        assert self._sonuc(apd, "tpl", end_state) is False

    def test_ayni_end_state_ihlal_degildir(self):
        apd = FleetApd()
        end = {"records_created": 1, "notifications_sent": 2}
        apd.fact_output_quality("tpl", end)
        # D34: ayni end-state -> False
        assert apd.fact_output_quality("tpl", dict(end)) is False

    @pytest.mark.parametrize("ref,cand", [
        ({"a": 1}, {"a": 2}),                              # D34: deger farki
        ({"a": 1}, {"a": 1, "b": 2}),                      # D35: ekstra key
        ({"a": 1, "b": 2}, {"a": 1}),                      # D35: eksik key
        ({"files": {"hash": "abc"}}, {"files": {"hash": "def"}}),  # ic ice
        ({"files": {"hash": "abc"}}, {"files": {"hash": "abc", "x": 1}}),
        ({"lst": [1, 2]}, {"lst": [2, 1]}),                # liste sirasi onemli
    ])
    def test_farkli_end_state_ihlal_verir(self, ref, cand):
        apd = FleetApd()
        apd.fact_output_quality("tpl", ref)
        assert apd.fact_output_quality("tpl", cand) is True

    @pytest.mark.parametrize("ref,cand", [
        ({"files": {"hash": "abc"}}, {"files": {"hash": "abc"}}),   # esit ic ice
        ({"lst": [1, 2]}, {"lst": [1, 2]}),                          # esit liste
        ({"files": {"b": 1, "a": 2}}, {"files": {"a": 2, "b": 1}}),  # key sirasi onemsiz
    ])
    def test_esdeger_end_state_ihlal_degildir(self, ref, cand):
        apd = FleetApd()
        apd.fact_output_quality("tpl", ref)
        assert apd.fact_output_quality("tpl", cand) is False

    def test_ihhal_denetim_notu_duser(self):
        apd = FleetApd()
        apd.fact_output_quality("tpl", {"a": 1})
        apd.fact_output_quality("tpl", {"a": 2})
        # D36: once audit notu düser, once hata notu degil
        assert apd.audit_notes == ["drift.output_quality:tpl"]

    def test_ihhal_yoksa_denetim_notu_yazilmaz(self):
        apd = FleetApd()
        apd.fact_output_quality("tpl", {"a": 1})
        apd.fact_output_quality("tpl", {"a": 1})
        assert apd.audit_notes == []

    def test_kiyas_her_zaman_son_onceki_run_ile(self):
        apd = FleetApd()
        first = {"a": 1}
        second = {"a": 2}
        apd.fact_output_quality("tpl", first)
        assert apd.fact_output_quality("tpl", second) is True   # 2. run vs 1.
        # D37: 3. run SON run ile (2.) karsilastirilir -> esit -> False
        assert apd.fact_output_quality("tpl", dict(second)) is False

    def test_sablon_izolasyonu(self):
        apd = FleetApd()
        apd.fact_output_quality("tpl1", {"a": 1})
        # baska sablon once run'u yok -> ihlal degil
        assert apd.fact_output_quality("tpl2", {"a": 2}) is False
        assert apd.audit_notes == []


# ============================================================ evaluate

class TestEvaluate:
    """§4.2 signal→escalation haritasi + §3.3 kalibrasyon disiplini."""

    def test_bos_facts_bos_alarm(self):
        apd = FleetApd()
        assert apd.evaluate({}, "a1") == []

    @pytest.mark.parametrize("facts", [
        {"loop>=2": False},
        {"cost.daily>2x_ewma": False, "loop>=2": False},
    ])
    def test_fired_false_atlanir(self, facts):
        apd = FleetApd()
        # D39: fired False -> alarm üretilmez
        assert apd.evaluate(facts, "a1") == []
        assert apd.audit_notes == []

    @pytest.mark.parametrize("facts,beklenen_uretilen", [
        ({"bogus": True}, set()),
        ({"loop>=2": True, "hatali_sinyal": True}, {"loop>=2"}),
        ({"new_class_seen": True}, set()),   # classifier.CLASS_TRIGGERS ile uyumsuz key
        ({"error.rate>0.20": False}, set()),
    ])
    def test_bilinmeyen_sinyal_not_duser(self, facts, beklenen_uretilen):
        """D40 (DUZELTILDI F4): SIGNAL_MAP disi-sinyaller-hala-alarm-uretmez
        (KeyError-YOK, severity-bilinmeden-uydurulamaz) ama artik
        'unknown_signal:<agent>:<signal>'-notu-ile-iz-birakir — eski
        sessiz-atma-fail-silent-degildi."""
        apd = FleetApd()
        alarms = apd.evaluate(facts, "a1")
        assert {a.signal for a in alarms} == beklenen_uretilen
        bilinmeyen = {s for s, v in facts.items() if v and s not in SIGNAL_MAP}
        for s in bilinmeyen:
            assert any(f"unknown_signal:a1:{s}" in n for n in apd.audit_notes)
        if not bilinmeyen:
            assert apd.audit_notes == []

    @pytest.mark.parametrize("signal,beklenen_baskili", [
        # D42: acik pencerede yangin-genel sinyaller (Info/Emergency) ATESLER
        ("loop>=2", False),                    # Emergency, fires True
        ("error.new_class_seen", False),       # Critical ama fires True
        ("escalation.age_max>24", False),      # Emergency, fires True
        # D41: bunlar kalibrasyonda susmustur (fires_during_calibration=False)
        ("permission.deny>0.20", True),
        ("cost.daily>2x_ewma", True),
        ("error.rate>0.20", True),
        ("latency.retry>=3", True),
        ("drift.tool_distribution>0.40", True),
        ("drift.output_quality", True),
    ])
    def test_acik_pencere_baskilama_haritasi(self, signal, beklenen_baskili):
        apd = FleetApd()
        alarms = apd.evaluate({signal: True}, "a1")
        assert len(alarms) == 1
        alarm = alarms[0]
        assert alarm.suppressed is beklenen_baskili
        if beklenen_baskili:
            # D45: baskilama notu
            assert f"calibration_suppressed:a1:{signal}" in apd.audit_notes
        else:
            assert all("calibration_suppressed" not in n for n in apd.audit_notes)

    @pytest.mark.parametrize("signal", list(SIGNAL_MAP))
    def test_kapali_pencere_hic_baskilama_yok(self, signal):
        apd = FleetApd()
        apd.window_for("a1").closed = True
        # D43: kapali pencerede tum sinyaller baskilanmaz
        alarms = apd.evaluate({signal: True}, "a1")
        assert len(alarms) == 1
        assert alarms[0].suppressed is False

    @pytest.mark.parametrize("signal", list(SIGNAL_MAP))
    def test_alarm_alanlari_kuralla_birebir_eslesir(self, signal):
        apd = FleetApd()
        kural = SIGNAL_MAP[signal]
        apd.window_for("a1").closed = True
        alarm = apd.evaluate({signal: True}, "a1")[0]
        # D44: tum alanlar kuraldan gelir
        assert alarm.signal == kural.signal
        assert alarm.event_type == kural.event_type
        assert alarm.reason == kural.reason
        assert alarm.severity == kural.severity
        assert alarm.sla_hours == kural.sla_hours
        assert alarm.protection == kural.protection
        assert alarm.suppressed is False

    def test_baskilanmis_sinyal_yine_de_alarm_kaydi_olusturur(self):
        apd = FleetApd()
        # D41: suppressed=True olsa da Alarm kaydi yine de olusturulur
        # (kayit tutulur, eskalasyon yapilmaz)
        alarms = apd.evaluate({"cost.daily>2x_ewma": True}, "a1")
        assert len(alarms) == 1
        assert alarms[0].signal == "cost.daily>2x_ewma"
        assert alarms[0].severity == "Critical"

    def test_coklu_facts_siralama_korunur(self):
        apd = FleetApd()
        apd.window_for("a1").closed = True
        facts = {
            "error.rate>0.20": True,
            "loop>=2": True,
            "permission.deny>0.20": True,
        }
        alarms = apd.evaluate(facts, "a1")
        # D46: alarm sirasi facts dict sirasiyla ayni
        assert [a.signal for a in alarms] == [
            "error.rate>0.20", "loop>=2", "permission.deny>0.20",
        ]

    def test_sentetik_agent_baskilanmaz(self):
        apd = FleetApd()
        # D47: onceden kapali pencere (R10) -> cost sinyali bile baskilanmaz
        apd.window_for("s1", synthetic=True)
        alarms = apd.evaluate({"cost.daily>2x_ewma": True}, "s1")
        assert len(alarms) == 1
        assert alarms[0].suppressed is False

    def test_evaluate_pencere_talep_uzerine_olusturur(self):
        apd = FleetApd()
        # D48: ilk evaluate cagrisi pencere olusturur (closed=False)
        apd.evaluate({"loop>=2": True}, "yeni1")
        assert "yeni1" in apd.windows
        assert apd.windows["yeni1"].closed is False

    def test_tum_sinyal_kumesi_acik_pencerede_karisik(self):
        apd = FleetApd()  # acik pencere
        facts = {s: True for s in SIGNAL_MAP}
        alarms = apd.evaluate(facts, "a1")
        assert len(alarms) == 9
        baskili = [a.signal for a in alarms if a.suppressed]
        # D41+D42: tam olarak 6 sinyal (fires=False olanlar) baskilanir
        assert len(baskili) == 6
        assert set(baskili) == {
            "permission.deny>0.20", "cost.daily>2x_ewma", "error.rate>0.20",
            "latency.retry>=3", "drift.tool_distribution>0.40",
            "drift.output_quality",
        }
        assert len(apd.audit_notes) == 6
        # Yangin-genel 3 sinyal baskilanmadi
        assert {a.signal for a in alarms if not a.suppressed} == {
            "loop>=2", "error.new_class_seen", "escalation.age_max>24",
        }


# ============================================================ fact_ticket_aging

class TestFactTicketAging:
    """R14: 24 saatten eski bilet -> self-escalation (Emergency)."""

    simdi = datetime(2026, 10, 15, 12, 0, 0)

    @pytest.mark.parametrize("olustur_saat_once,beklenen", [
        (25.0, True),
        (48.5, True),
        (24.0, False),   # D50: tam esit -> False (katı >)
        (23.999, False),
        (1.0, False),
        (0.0, False),
        (-5.0, False),   # D51: gelecek tarihli bilet
    ])
    def test_yirmi_dort_saat_siniri(self, olustur_saat_once, beklenen):
        created = self.simdi - timedelta(hours=olustur_saat_once)
        sonuc = FleetApd.fact_ticket_aging(created, self.simdi)
        assert sonuc is beklenen

    @pytest.mark.parametrize("limit_h,olustur_saat_once,beklenen", [
        (2.0, 2.5, True),
        (2.0, 2.0, False),    # D52: tam esit -> False
        (2.0, 1.9, False),
        (0.5, 0.6, True),
        (168.0, 169.0, True),
        (168.0, 167.5, False),
    ])
    def test_ozel_limit_siniri(self, limit_h, olustur_saat_once, beklenen):
        created = self.simdi - timedelta(hours=olustur_saat_once)
        sonuc = FleetApd.fact_ticket_aging(created, self.simdi, limit_h=limit_h)
        assert sonuc is beklenen

    def test_statik_metot_instance_gerekmez(self):
        # R14 statik metot — FleetApd instance'i olmadan cagrilabilir
        created = datetime(2026, 10, 1)
        now = datetime(2026, 10, 16)
        assert FleetApd.fact_ticket_aging(created, now) is True

    def test_negatif_limit_da_kati_karsilastirma(self):
        created = self.simdi - timedelta(hours=1)
        # limit 0 -> > 1s. katı >
        assert FleetApd.fact_ticket_aging(created, self.simdi, limit_h=0.0) is True
        assert FleetApd.fact_ticket_aging(self.simdi, self.simdi, limit_h=0.0) is False


# ============================================================ Sabitler ve harita butunlugu

class TestSabitlerVeHarita:
    """SIGNAL_MAP/SEVERITY_ORDER/Rule/Alarm yapysal butunlugu."""

    def test_ewma_carpani_iki_nokta_sifir(self):
        # D53: §4.2 conjunctive kuralinin ikinci kosulu
        assert EWMA_MULTIPLIER == 2.0

    def test_signal_map_dokuz_kayit_ve_key_eslesmesi(self):
        # D53: 9 kural; her key kuralin signal alanyla ayni
        assert len(SIGNAL_MAP) == 9
        for key, kural in SIGNAL_MAP.items():
            assert key == kural.signal
            assert isinstance(key, str)

    @pytest.mark.parametrize("signal,beklenen_sira", [
        ("Info", 0), ("Low", 1), ("Medium", 2),
        ("High", 3), ("Critical", 4), ("Emergency", 5),
    ])
    def test_severity_order_siralama(self, signal, beklenen_sira):
        # D54: Info..Emergency 0..5
        assert SEVERITY_ORDER[signal] == beklenen_sira
        assert len(SEVERITY_ORDER) == 6

    @pytest.mark.parametrize("signal", list(SIGNAL_MAP))
    def test_kurallarin_severities_gecerli(self, signal):
        # D54: her kural severity SEVERITY_ORDER icinde
        assert SIGNAL_MAP[signal].severity in SEVERITY_ORDER

    @pytest.mark.parametrize("signal", list(SIGNAL_MAP))
    def test_kural_alanlari_kisitlari(self, signal):
        kural = SIGNAL_MAP[signal]
        # D55: yapisal kisitlar
        assert kural.event_type in ("escalation", "report_item")
        assert isinstance(kural.sla_hours, float) and kural.sla_hours > 0
        assert isinstance(kural.fires_during_calibration, bool)

    def test_rule_frozen_mutasyon_hatasi(self):
        # D55: frozen dataclass -> FrozenInstanceError
        kural = SIGNAL_MAP["loop>=2"]
        with pytest.raises(FrozenInstanceError):
            kural.severity = "Low"

    def test_rule_esitlik_ve_yapisi(self):
        r1 = Rule(signal="x", event_type="escalation", reason="budget",
                  sla_hours=1.0, protection="p", severity="Low",
                  fires_during_calibration=True)
        r2 = Rule(signal="x", event_type="escalation", reason="budget",
                  sla_hours=1.0, protection="p", severity="Low",
                  fires_during_calibration=True)
        assert r1 == r2

    def test_alarm_varsayilan_suppressed_false(self):
        # D56: Alarm varsayilani
        a = Alarm(signal="x", event_type="escalation", reason="budget",
                  severity="Low", sla_hours=1.0, protection="p")
        assert a.suppressed is False

    def test_alarm_suppressed_true_olabilir(self):
        a = Alarm(signal="x", event_type="escalation", reason="budget",
                  severity="Low", sla_hours=1.0, protection="p", suppressed=True)
        assert a.suppressed is True

    def test_bilinen_sinyal_isimleri(self):
        # §4.2 haritasindaki sinyal anahtarlari tam listesi
        assert set(SIGNAL_MAP) == {
            "loop>=2", "permission.deny>0.20", "cost.daily>2x_ewma",
            "error.new_class_seen", "error.rate>0.20", "latency.retry>=3",
            "drift.tool_distribution>0.40", "drift.output_quality",
            "escalation.age_max>24",
        }
