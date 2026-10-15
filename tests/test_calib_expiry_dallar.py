"""F2 (aa23e082-bulgu): §3.3 kalibrasyon-penceresi-kapanisi — pin dosyasi.

S鲁能gensiz: closed=True-yalnizca-synthetic-kayit-veya-restart-restore-ile
geliyordu; 14-gunluk-pencere-süresi-doldugunda-HICBIR-kanal-kapamiyordu —
calibration_until-geçmiş-pencere-açik-kaldi ve ( evaluate icindeki
'not window.closed'-kis平方-olarak) alarmlar-sürekli-baskilandi.

DUZELTILDI: evaluate_agent-oncesi-_close_expired_calibration-kanali;
süresi-dolmus-pencere-ilk-evaluasyonda-kapatilir-ve-persist-edilir.
"""
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline


def _event(agent_id: str, event_id: str) -> dict:
    return {
        "event_id": event_id, "agent_id": agent_id, "task_id": f"t-{event_id}",
        "session_id": "s", "model_name": "m", "input_tokens": 1,
        "output_tokens": 1, "cost_usd": 0.01, "latency_ms": 100,
        "error_class": None, "status": "ok", "synthetic": 0,
        "ts": "2026-09-12 10:00:00", "retry_count": 0, "ttft_s": 0.1,
        "task_template": None, "end_state_json": None,
    }


def _hazirlik():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    pipe = Pipeline(conn)
    pipe.ingest([_event("prod-agent", "e1")])
    return conn, pipe


def test_suresi_dolmus_pencere_evaluasyonda_kapanir():
    conn, pipe = _hazirlik()
    conn.execute(
        "UPDATE agent_calibration SET calibration_until='2020-01-01 00:00:00'"
        " WHERE agent_id='prod-agent'")
    conn.commit()
    alarms = pipe.evaluate_agent("prod-agent")
    row = conn.execute(
        "SELECT closed FROM agent_calibration"
        " WHERE agent_id='prod-agent'").fetchone()
    assert row["closed"] == 1
    assert pipe.apd.window_for("prod-agent").closed is True
    # kapali-pencerede-hicbir-alarm-baskilanmaz (D43-aynisi)
    assert all(not a.suppressed for a in alarms)


def test_kapanis_idempotan_ve_restart_tutarli():
    conn, pipe = _hazirlik()
    conn.execute(
        "UPDATE agent_calibration SET calibration_until='2020-01-01 00:00:00'"
        " WHERE agent_id='prod-agent'")
    conn.commit()
    pipe.evaluate_agent("prod-agent")
    pipe.evaluate_agent("prod-agent")          # ikinci-evaluasyon-bosu-bosuna
    row = conn.execute(
        "SELECT closed FROM agent_calibration"
        " WHERE agent_id='prod-agent'").fetchone()
    assert row["closed"] == 1
    # restart-restore (D1) kapali-durumu-korur
    pipe2 = Pipeline(conn)
    assert pipe2.apd.window_for("prod-agent").closed is True


def test_henuz_suresi_dolmamis_pencere_acik_kalir():
    conn, pipe = _hazirlik()
    conn.execute(
        "UPDATE agent_calibration SET calibration_until='2099-01-01 00:00:00'"
        " WHERE agent_id='prod-agent'")
    conn.commit()
    pipe.evaluate_agent("prod-agent")
    row = conn.execute(
        "SELECT closed FROM agent_calibration"
        " WHERE agent_id='prod-agent'").fetchone()
    assert row["closed"] == 0
    assert pipe.apd.window_for("prod-agent").closed is False


def test_f3_calibrated_propagasyonu():
    """F3: ewma 'armed = n>=warmup AND state.calibrated' — state.calibrated
    her-cagrada-pencere-kapanma-durumuyla-tazelenir. Pencere-acikken-cost
    alarmlari-baskili (R3-warmup-ve-§3.3), pencere-kapandiginda-ilk-
    cagrada-silahlanir ( F2-kapatisi-olmadan-sonsuza-kadar-baskili-kalirdi)."""
    from swarmax.metrics.apd import FleetApd
    apd = FleetApd()
    for _ in range(35):                      # warmup asar (EWMA_MIN_OBS=30)
        assert apd.fact_cost_spike("a1", 100.0, calibrated=False) is False
    assert apd.ewma["a1"].calibrated is False
    # pencere-kapanir -> calibrated=True: sabit-100-tabaninda-5000'luk-
    # gunluk-maliyet z>2.5-ve-2x-EWMA-sartlarini-gecer (spike-silahlanir)
    assert apd.fact_cost_spike("a1", 5000.0, calibrated=True) is True
    assert apd.ewma["a1"].calibrated is True
