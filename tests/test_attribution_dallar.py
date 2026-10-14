"""test_attribution_dallar.py — swarmax/attribution.py dal-kesen test suite.

MODUL ANATOMISI (src/swarmax/attribution.py, 171 satir) — public API:
  suggest_for_alarm(conn, alarm) -> {suggested_agent_id, suggested_step,
      confidence, method, note}; deterministik merdiven (L31):
      1 'loop>=2'                          -> son tool_call izi  (0.90)
      2 'error.new_class_seen'|'error.rate>0.20' -> ilk hata satiri (0.75)
      3 'permission.deny>0.20'             -> en cok reddedilen tool (0.80)
      4 'drift.tool_distribution>0.40'     -> baskin tool pivotu (0.70)
      5 'cost.daily>2x_ewma'               -> en pahali task    (0.65)
      6 'escalation.age_max>24'            -> en eski acik bilet(0.60)
      7 bilinmeyen sinyal                  -> _fallback         (0.30)
      her rung: iz varsa oneri, iz yoksa _fallback
  confirm_attribution(conn,alarm_id,accepted,operator) -> rowcount 0 -> False;
      pending guncellenince evidence mohru + True (L142)
  approval_rate(conn) -> {decided, accepted, rejected, rate}; rate None
      eger decided=0 (L162)
  sabitler: METHOD = 'swarmax.heuristic.v1 (Who&When-aligned, E14/E15)'

BULGU-1 (production'a DOKUNULMADI): 'escalation.age_max>24' rung'u FİLO geneli
  calisir — sorguda agent_id FİLTRESİ YOK ve suggested_agent_id = BILET'in
  agent_id'si (alarm'ın agent_id'si DEGIL). Alarm A icin calistirildiginda,
  en eski acik bilet B'ye aitse oneri B'yi isaret eder. Notu ("oldest open
  escalation in the fleet') bunu bilincli gosterir; bu onemli bir
  karakteristik — cagirani suprizleyebilir. Test dosyasinda belgelendi.

BULGU-2: 'loop>=2' rung'u 24h penceresini HIC kullanmaz (window_start
  hesaplanir ama bu rung'da sorguya girmez); 'escalation.age_max>24' da
  pencere disindadir. Geri kalan 4 rung ts >= window_start ile 24h ile sinirli.

Kural-1: SADECE yeni test dosyasi. Kural-4: saf in-memory sqlite; ag YOK.
filterwarnings=error::UserWarning => ureten yol YOK.
"""
from __future__ import annotations

import sys
from datetime import timedelta

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import attribution  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402

ANAHTARLAR = {"suggested_agent_id", "suggested_step", "confidence", "method", "note"}


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    conn.execute(
        "INSERT INTO fleet_agents(agent_id, fleet_name, role)"
        " VALUES ('agent-a','filo','planner'), ('agent-b','filo','worker')")
    conn.commit()
    return conn


def _alarm(db, agent_id="agent-a", signal="loop>=2", alarm_id="alm-1"):
    """alarms tablosuna satir ekleyip sqlite3.Row olarak doner."""
    db.execute(
        "INSERT INTO alarms(alarm_id, agent_id, signal, event_type, reason,"
        " severity, sla_hours, sla_deadline, created_at)"
        " VALUES (?,?,?,'escalation','test','high',24,"
        " '2030-01-01 00:00:00', '2030-01-01 00:00:00')",
        (alarm_id, agent_id, signal))
    db.commit()
    return db.execute("SELECT * FROM alarms WHERE alarm_id=?", (alarm_id,)).fetchone()


def _tool_call(db, agent_id, tool, ts=None, arguments="{}"):
    db.execute(
        "INSERT INTO guard_events(event_id, agent_id, event_type, tool_name,"
        " arguments_json, ts) VALUES (?,?, 'tool_call', ?, ?, ?)",
        (f"ge-{agent_id}-{tool}-{ts or 'x'}", agent_id, tool, arguments,
         ts or attribution._utcnow().isoformat(sep=" ")))


def _task(db, agent_id, task_id, status="error", error_class="ValueError",
          session_id="sess-1", model="gpt-x", cost=0.01, ts=None, gun_once=0):
    db.execute(
        "INSERT INTO agent_task_events(event_id, agent_id, task_id, session_id,"
        " model_name, input_tokens, output_tokens, cost_usd, latency_ms,"
        " error_class, status, ts) VALUES (?,?,?,?,?,?,?, ?, 100, ?, ?, ?)",
        (f"ev-{agent_id}-{task_id}-{gun_once}", agent_id, task_id, session_id,
         model, 10, 20, cost, error_class, status,
         ts or (attribution._utcnow() - timedelta(days=gun_once)).isoformat(sep=" ")))


def _bilet(db, agent_id, task_id, status="open", gun_once=0):
    db.execute(
        "INSERT INTO hitl_escalations(escalation_id, agent_id, task_id,"
        " trigger_metric, trigger_value, reason, evidence_ref, sla_deadline,"
        " status, created_at) VALUES (?,?,?,'age',1.0,'quality','ref',"
        " '2030-01-01 00:00:00', ?, ?)",
        (f"esc-{agent_id}-{task_id}-{gun_once}", agent_id, task_id, status,
         (attribution._utcnow() - timedelta(days=gun_once)).isoformat(sep=" ")))


# ============================================ ortak yapi ===================
class TestOneriOrtakYapisi:
    """Her rung'in donus formatinin invariantlari."""

    @pytest.mark.parametrize("signal", [
        "loop>=2", "error.new_class_seen", "error.rate>0.20",
        "permission.deny>0.20", "drift.tool_distribution>0.40",
        "cost.daily>2x_ewma", "escalation.age_max>24",
        "tamamen-bilinmeyen-sinyal",
    ])
    def test_anahtarlar_ve_method_sabit(self, db, signal):
        """Dal: her giris (fallback dahil) 5 anahtar + METHOD doner."""
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert set(oneri) == ANAHTARLAR
        assert oneri["method"] == attribution.METHOD

    @pytest.mark.parametrize("signal", [
        "loop>=2", "error.new_class_seen", "error.rate>0.20",
        "permission.deny>0.20", "drift.tool_distribution>0.40",
        "cost.daily>2x_ewma", "escalation.age_max>24", "bilinmeyen",
    ])
    def test_guven_araliginda(self, db, signal):
        """Dal: confidence her zaman [0.30, 0.90] araliginda."""
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert 0.0 <= oneri["confidence"] <= 1.0
        assert oneri["confidence"] >= 0.30

    def test_bilinmeyen_sinyal_fallback(self, db):
        """Dal 7: merdiven rung'u olmayan sinyal -> _fallback (0.30)."""
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal="nonsense.x"))
        assert oneri["confidence"] == 0.30
        assert oneri["suggested_step"] == "insufficient trace"
        assert "no dedicated ladder rung" in oneri["note"]
        assert oneri["suggested_agent_id"] == "agent-a"


# ============================================ 'loop>=2' =====================
class TestLoopSinyali:
    """signal='loop>=2': son tool_call izi -> 0.90; iz yok -> fallback."""

    def test_iz_varsa_090(self, db):
        """Dal: en son tool_call => 'repeated call <tool> (last at <ts[:19]>)'."""
        _tool_call(db, "agent-a", "shell.exec", ts="2030-01-01 10:00:00")
        _tool_call(db, "agent-a", "file.read", ts="2030-01-02 11:30:45.123")
        oneri = attribution.suggest_for_alarm(db, _alarm(db))
        assert oneri["confidence"] == 0.90
        assert oneri["suggested_agent_id"] == "agent-a"
        assert oneri["suggested_step"].startswith("repeated call file.read")
        assert "2030-01-02 11:30:45" in oneri["suggested_step"]
        assert "loop breaker" in oneri["note"]

    def test_son_tool_call_secilir(self, db):
        """Dal: ORDER BY ts DESC LIMIT 1 -> en YENISI."""
        _tool_call(db, "agent-a", "eski-tool", ts="2020-01-01 00:00:00")
        _tool_call(db, "agent-a", "yeni-tool", ts="2030-01-01 00:00:00")
        oneri = attribution.suggest_for_alarm(db, _alarm(db))
        assert "yeni-tool" in oneri["suggested_step"]

    def test_baskasinin_izi_secilmez(self, db):
        """Dal: agent_id filtresi -> baska agent'in izi kullanilmaz."""
        _tool_call(db, "agent-b", "b-tool", ts="2030-01-01 00:00:00")
        oneri = attribution.suggest_for_alarm(db, _alarm(db))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "loop breaker fired; no tool trace in window"

    def test_pencere_disi_iz_hala_kullanilir(self, db):
        """BULGU-2: 'loop>=2' rung'inda 24h penceresi YOK — eski iz de kabul."""
        _tool_call(db, "agent-a", "cok-eski-tool",
                   ts=(attribution._utcnow() - timedelta(days=365)).isoformat(sep=" "))
        oneri = attribution.suggest_for_alarm(db, _alarm(db))
        assert oneri["confidence"] == 0.90
        assert "cok-eski-tool" in oneri["suggested_step"]


# ================================== error.new_class_seen / rate>0.20 ========
class TestHataSinyalleri:
    """Iki sinyal ayni rung'u paylasir: ilk hata satiri -> 0.75."""

    @pytest.mark.parametrize("signal", ["error.new_class_seen", "error.rate>0.20"])
    def test_ilk_hata_075(self, db, signal):
        """Dal: ORDER BY ts ASC LIMIT 1 -> EN ESKI hata (Who&When 'when')."""
        _task(db, "agent-a", "t-2", error_class="ConnectionError",
              ts="2030-01-02 00:00:00")
        _task(db, "agent-a", "t-1", error_class="ValueError",
              ts="2030-01-01 00:00:00")  # daha eski -> secilir
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert oneri["confidence"] == 0.75
        assert "ValueError on t-1" in oneri["suggested_step"]
        assert "first error 'ValueError' on task t-1" in oneri["note"]

    @pytest.mark.parametrize("signal", ["error.new_class_seen", "error.rate>0.20"])
    def test_ayni_oturum_partneri_note_ekler(self, db, signal):
        """Dal: ayni session_id'li baska agent varsa note'a partner eklenir."""
        _task(db, "agent-a", "t-1", session_id="s-1",
              ts="2030-01-01 00:00:00")
        _task(db, "agent-b", "t-9", session_id="s-1", status="ok",
              error_class=None, ts="2030-01-01 00:30:00")
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert "same-session partner: agent-b" in oneri["note"]

    @pytest.mark.parametrize("signal", ["error.new_class_seen", "error.rate>0.20"])
    def test_partner_yoksa_note_sade(self, db, signal):
        """Dal: partner yoksa note yalnizca ilk hatayi soyler."""
        _task(db, "agent-a", "t-1", session_id="s-1", ts="2030-01-01 00:00:00")
        _task(db, "agent-b", "t-9", session_id="s-2", status="ok",
              error_class=None, ts="2030-01-01 00:30:00")  # baska session
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert "partner" not in oneri["note"]

    @pytest.mark.parametrize("signal", ["error.new_class_seen", "error.rate>0.20"])
    def test_pencere_disi_hata_gorulmez(self, db, signal):
        """Dal: ts < (now-24h) hatalar window disinda kalir -> fallback."""
        _task(db, "agent-a", "t-eski", gun_once=3)  # 3 gun onceki hata
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "error burst detected; no error rows in window"

    @pytest.mark.parametrize("signal", ["error.new_class_seen", "error.rate>0.20"])
    def test_basarisiz_durum_filtresi(self, db, signal):
        """Dal: status='error' DEGILSE satir sayilmaz."""
        _task(db, "agent-a", "t-ok", status="ok", error_class=None)
        oneri = attribution.suggest_for_alarm(db, _alarm(db, signal=signal))
        assert oneri["confidence"] == 0.30


# ================================== permission.deny>0.20 ===================
class TestRedSinyali:
    """signal='permission.deny>0.20': en cok reddedilen tool -> 0.80."""

    def test_baskin_red_araci(self, db):
        """Dal: GROUP BY tool_name ORDER BY c DESC -> en cok reddedilen."""
        for _ in range(2):
            self._red(db, "shell.exec")
        for _ in range(5):
            self._red(db, "file.write")
        for _ in range(3):
            self._red(db, "shell.exec")  # toplam 5, beraberlik bozulur
        # file.write 5x, shell.exec 5x -> beraberlik; belirgin kazanan ekleyelim
        self._red(db, "file.write")  # file.write 6x -> kazanir
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="permission.deny>0.20"))
        assert oneri["confidence"] == 0.80
        assert "denied tool 'file.write'" in oneri["suggested_step"]
        assert "6x in 24h" in oneri["suggested_step"]
        assert "highest deny count" in oneri["note"]

    def test_allow_kararlari_sayilmaz(self, db):
        """Dal: decision='allow' satirlari sayilmaz -> yalniz deny."""
        db.execute(
            "INSERT INTO guard_events(event_id, agent_id, event_type, decision,"
            " tool_name, ts) VALUES ('ge-ok','agent-a','permission_decision',"
            " 'allow','file.write','2030-01-01 00:00:00')")
        db.commit()
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="permission.deny>0.20"))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "deny storm detected; no deny rows in window"

    def test_pencere_disi_red_gorulmez(self, db):
        """Dal: 24h'den eski deny sayilmaz."""
        db.execute(
            "INSERT INTO guard_events(event_id, agent_id, event_type, decision,"
            " tool_name, ts) VALUES ('ge-eski','agent-a','permission_decision',"
            " 'deny','shell.exec', ?)",
            ((attribution._utcnow() - timedelta(days=2)).isoformat(sep=" "),))
        db.commit()
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="permission.deny>0.20"))
        assert oneri["confidence"] == 0.30

    @staticmethod
    def _red(db, tool):
        sid = "red-%s-%d" % (tool, db.execute(
            "SELECT COUNT(*) c FROM guard_events").fetchone()["c"])
        db.execute(
            "INSERT INTO guard_events(event_id, agent_id, event_type, decision,"
            " tool_name, ts) VALUES (?,?, 'permission_decision', 'deny', ?, ?)",
            (sid, "agent-a", tool,
             attribution._utcnow().isoformat(sep=" ")))


# ================================== drift.tool_distribution>0.40 ============
class TestDriftSinyali:
    """signal='drift.tool_distribution>0.40': baskin 24h tool pivotu -> 0.70."""

    def test_baskin_tool_pivotu(self, db):
        """Dal: 24h icinde en cok cagrilan tool pivot sayilir."""
        _tool_call(db, "agent-a", "http.get", ts="2030-01-01 00:00:00")
        for i in range(4):
            _tool_call(db, "agent-a", "shell.exec",
                       ts=f"2030-01-01 0{i}:00:00")
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="drift.tool_distribution>0.40"))
        assert oneri["confidence"] == 0.70
        assert "pivot onto 'shell.exec'" in oneri["suggested_step"]
        assert "4x in 24h" in oneri["suggested_step"]
        assert "JSD drift" in oneri["note"]

    def test_pencere_disi_cagri_sayilmaz(self, db):
        """Dal: eski tool_call sayilmaz."""
        _tool_call(db, "agent-a", "eski-tool",
                   ts=(attribution._utcnow() - timedelta(days=5)).isoformat(sep=" "))
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="drift.tool_distribution>0.40"))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "drift alarm; no tool calls in window"

    def test_baska_agent_izi_sayilmaz(self, db):
        """Dal: agent_id filtresi."""
        _tool_call(db, "agent-b", "b-tool", ts="2030-01-01 00:00:00")
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="drift.tool_distribution>0.40"))
        assert oneri["confidence"] == 0.30


# ================================== cost.daily>2x_ewma =====================
class TestMaliyetSinyali:
    """signal='cost.daily>2x_ewma': en pahali task -> 0.65."""

    def test_en_pahali_task(self, db):
        """Dal: ORDER BY cost_usd DESC LIMIT 1."""
        _task(db, "agent-a", "ucuz", cost=0.01, status="ok",
              error_class=None, ts="2030-01-01 00:00:00")
        _task(db, "agent-a", "pahali", cost=3.50, status="ok",
              error_class=None, ts="2030-01-01 01:00:00")
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="cost.daily>2x_ewma"))
        assert oneri["confidence"] == 0.65
        assert "task pahali on gpt-x ($3.50)" in oneri["suggested_step"]
        assert "largest single-task cost" in oneri["note"]

    def test_pencere_disi_maliyet_gorulmez(self, db):
        """Dal: 24h disi task sayilmaz."""
        _task(db, "agent-a", "eski-pahali", cost=99.0, gun_once=3)
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="cost.daily>2x_ewma"))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "cost spike; no task rows in window"


# ================================== escalation.age_max>24 ==================
class TestYaslanmaSinyali:
    """signal='escalation.age_max>24': en eski ACIK bilet -> 0.60."""

    def test_en_eski_acik_bilet(self, db):
        """Dal: ORDER BY created_at ASC LIMIT 1 (status='open')."""
        _bilet(db, "agent-a", "t-1", gun_once=2)   # 2 gun once
        _bilet(db, "agent-a", "t-2", gun_once=1)   # 1 gun once
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="escalation.age_max>24"))
        assert oneri["confidence"] == 0.60
        assert "open ticket t-1" in oneri["suggested_step"]
        assert "48h" in oneri["suggested_step"]
        assert "oldest open escalation" in oneri["note"]

    def test_kapali_bilet_atlanir(self, db):
        """Dal: status='open' filtresi -> kapatilmis bilet eski bile olsa atlanir."""
        _bilet(db, "agent-a", "t-eski-kapali", status="resolved", gun_once=10)
        _bilet(db, "agent-a", "t-yeni", gun_once=1)
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="escalation.age_max>24"))
        assert "open ticket t-yeni" in oneri["suggested_step"]

    def test_baskasinin_bileti_isaret_edilir(self, db):
        """BULGU-1: sorgu filo-geneldir; alarm agent-a'da olsa en eski acik
        bilet agent-b'ye aitse oneri agent-b'yi isaret eder."""
        _bilet(db, "agent-b", "t-baskasi", gun_once=5)
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, agent_id="agent-a", signal="escalation.age_max>24"))
        assert oneri["suggested_agent_id"] == "agent-b"
        assert oneri["suggested_agent_id"] != "agent-a"

    def test_acik_bilet_yoksa_fallback(self, db):
        """Dal: acik bilet yok -> fallback."""
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="escalation.age_max>24"))
        assert oneri["confidence"] == 0.30
        assert oneri["note"] == "aging alarm; no open ticket found"

    def test_bilet_pencere_disinda_da_kabul(self, db):
        """BULGU-2: bu rung'ta 24h penceresi YOK — 30 gunluk bilet de secilir."""
        _bilet(db, "agent-a", "cok-eski-bilet", gun_once=30)
        oneri = attribution.suggest_for_alarm(
            db, _alarm(db, signal="escalation.age_max>24"))
        assert oneri["confidence"] == 0.60
        assert "cok-eski-bilet" in oneri["suggested_step"]


# ================================== confirm_attribution ====================
class TestOnaylama:
    """confirm_attribution pending/tekrar/mohur dallari."""

    def _oneri(self, db, alarm_id="alm-1", confirmed=None):
        # attribution_suggestions.alarm_id -> alarms(alarm_id) FK'si vardir
        _alarm(db, alarm_id=alarm_id, signal="loop>=2")
        db.execute(
            "INSERT INTO attribution_suggestions(alarm_id, suggested_agent_id,"
            " suggested_step, confidence, method, note, confirmed)"
            " VALUES (?,?, 'insufficient trace', 0.3, ?, 'n', ?)",
            (alarm_id, "agent-a", attribution.METHOD, confirmed))

    def test_pending_kabul(self, db):
        """Dal: confirmed IS NULL + accepted=True -> confirmed=1 + True."""
        self._oneri(db)
        assert attribution.confirm_attribution(db, "alm-1", True, "op-1") is True
        row = db.execute(
            "SELECT confirmed, confirmed_by FROM attribution_suggestions"
            " WHERE alarm_id='alm-1'").fetchone()
        assert (row["confirmed"], row["confirmed_by"]) == (1, "op-1")

    def test_pending_red(self, db):
        """Dal: accepted=False -> confirmed=0 + True."""
        self._oneri(db)
        assert attribution.confirm_attribution(db, "alm-1", False, "op-1") is True
        assert db.execute(
            "SELECT confirmed FROM attribution_suggestions"
            " WHERE alarm_id='alm-1'").fetchone()["confirmed"] == 0

    def test_evidence_mohru(self, db):
        """Dal: karar 'attribution_confirmed' ile ledger'a mohurlenir."""
        self._oneri(db)
        attribution.confirm_attribution(db, "alm-1", True, "op-7")
        row = db.execute(
            "SELECT COUNT(*) c FROM evidence_ledger"
            " WHERE event_type='attribution_confirmed'").fetchone()["c"]
        assert row == 1

    def test_zaten_onayliysa_false(self, db):
        """Dal: rowcount 0 (confirmed NOT NULL) -> False, mohur YAZILMAZ."""
        self._oneri(db, confirmed=1)
        assert attribution.confirm_attribution(db, "alm-1", True, "op-1") is False
        assert db.execute(
            "SELECT COUNT(*) c FROM evidence_ledger"
            " WHERE event_type='attribution_confirmed'").fetchone()["c"] == 0

    def test_olmayan_alarm_false(self, db):
        """Dal: satir yok -> rowcount 0 -> False (patlama yok)."""
        assert attribution.confirm_attribution(db, "alm-yok", True, "op-1") is False

    def test_reddedilmis_tekrar_onaylanmaz(self, db):
        """Dal: once red, sonra ayni alarm'a tekrar deneme -> False."""
        self._oneri(db)
        assert attribution.confirm_attribution(db, "alm-1", False, "op-1") is True
        assert attribution.confirm_attribution(db, "alm-1", True, "op-1") is False


# ================================== approval_rate ==========================
class TestOnayOrani:
    """approval_rate decided/rate dallari (§9.2 kabul metrigi)."""

    def _oneri(self, db, alarm_id, confirmed):
        # attribution_suggestions.alarm_id -> alarms(alarm_id) FK'si vardir
        _alarm(db, alarm_id=alarm_id, signal="loop>=2")
        db.execute(
            "INSERT INTO attribution_suggestions(alarm_id, suggested_agent_id,"
            " suggested_step, confidence, method, confirmed)"
            " VALUES (?,?, 'step', 0.3, ?, ?)",
            (alarm_id, "agent-a", attribution.METHOD, confirmed))

    def test_bos_tablo_rate_none(self, db):
        """Dal: hic satir yok -> decided=0, rate=None."""
        r = attribution.approval_rate(db)
        assert (r["decided"], r["accepted"], r["rejected"]) == (0, 0, 0)
        assert r["rate"] is None

    def test_yalniz_pending_rate_none(self, db):
        """Dal: hepsi pending (confirmed NULL) -> kararli 0, rate None."""
        self._oneri(db, "a1", None)
        r = attribution.approval_rate(db)
        assert r["decided"] == 0
        assert r["rate"] is None

    def test_karisik_oran(self, db):
        """Dal: 3 kabul + 1 red -> decided 4, rate 0.75."""
        for i, c in enumerate([1, 1, 1, 0]):
            self._oneri(db, f"a{i}", c)
        r = attribution.approval_rate(db)
        assert (r["decided"], r["accepted"], r["rejected"]) == (4, 3, 1)
        assert r["rate"] == 0.75

    def test_hepsi_kabul_oran_1(self, db):
        """Dal: tum kararlar kabul -> rate 1.0."""
        for i in range(3):
            self._oneri(db, f"a{i}", 1)
        assert attribution.approval_rate(db)["rate"] == 1.0

    def test_pending_haric_sayilir(self, db):
        """Dal: pending satirler decided'a katilmaz."""
        self._oneri(db, "a1", 1)
        self._oneri(db, "a2", None)
        r = attribution.approval_rate(db)
        assert (r["decided"], r["rate"]) == (1, 1.0)
