"""swarmax MCP sunucu testleri — Model Context Protocol 2025-06-18 over stdio.

JSON-RPC el sıkışması + 3 aracı ( fleet_status/agent_health/audit_trail)
uçtan-uca SUBPROCESS üzerinden çalıştırır. Tamga/sester MCP testlerinin
aynı deseni ( stdio'yu besle, stdout JSON satırlarını çöz).

Sözleşmeler-tespit-edilenler:
  - initialize → protocolVersion + capabilities + serverInfo
  - tools/list → 3 aracın-da listesi
  - araç çağrısı → {"content":[{"type":"text","text":JSON}]}, asla exception
  - bozuk-zincir → ok=false RED ( fail-closed, traceback yok)
  - bilinmeyen-arac → JSON-RPC -32601 hatası
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp" / "server.py"
PROTOCOL_VERSION = "2025-06-18"


def _rpc(lines, env_extra=None, timeout=60):
    """Server'ı stdio üzerinden besle; yanıt satırlarını dict listesi dön."""
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    reqs = list(lines or [])
    proc = subprocess.run(
        [sys.executable, str(SERVER)], input="\n".join(reqs) + "\n",
        capture_output=True, text=True, env=env, timeout=timeout,
        cwd=str(ROOT), check=False)
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return proc, out


def _init_line():
    return ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
            '{"protocolVersion":"2025-06-18","capabilities":{},'
            '"clientInfo":{"name":"swarmax-mcp-test","version":"0.1"}}}')


def _tools_list():
    return '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'


def _call(req_id, name, arguments):
    return (f'{{"jsonrpc":"2.0","id":{req_id},"method":"tools/call",'
            f'"params":{{"name":"{name}",'
            f'"arguments":{json.dumps(arguments, ensure_ascii=False)}}}}}')


def _tools(out, req_id):
    for d in out:
        if d.get("id") == req_id and "result" in d:
            return d["result"]
    return None


def _call_result(out, req_id):
    """tools/call yanıtını çek → {"content":[{"type":"text","text":JSON}]}."""
    for d in out:
        if d.get("id") == req_id and "result" in d:
            content = d["result"].get("content") or []
            if content:
                try:
                    return json.loads(content[0].get("text", ""))
                except json.JSONDecodeError:
                    return None
    return None


# ------------------------------------------------------------------ fixtures

@pytest.fixture()
def fleet_db(tmp_path):
    """Bilinen-iyi bir filo: 2 ajan, 1 event, 1 alarm, evidence-ledger + mühür.

    pipeline._register_agent çağırmadan elle yazıyoruz çünkü MCP'nin
    sözleşmesi DB-durumudur, pipeline-değil.
    """
    db = tmp_path / "swarmax.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    schema = (ROOT / "src" / "swarmax" / "schema" / "sqlite_v1.sql")
    conn.executescript(schema.read_text(encoding="utf-8"))
    for mig in sorted((ROOT / "src" / "swarmax" / "schema" /
                       "migrations").glob("*.sql")):
        conn.executescript(mig.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO fleet_agents (agent_id, fleet_name, role)"
        " VALUES ('agent-a', 'fleet', 'worker')")
    conn.execute(
        "INSERT INTO fleet_agents (agent_id, fleet_name, role)"
        " VALUES ('agent-b', 'fleet', 'reviewer')")
    conn.execute(
        "INSERT INTO agent_calibration (agent_id, calibration_until, closed)"
        " VALUES ('agent-a', '2099-01-01 00:00:00', 1)")
    conn.execute(
        "INSERT INTO agent_calibration (agent_id, calibration_until, closed)"
        " VALUES ('agent-b', '2099-01-01 00:00:00', 1)")
    conn.execute(
        "INSERT INTO agent_task_events (event_id, agent_id, task_id, model_name,"
        " input_tokens, output_tokens, cost_usd, latency_ms, status)"
        " VALUES ('e1', 'agent-a', 't1', 'm', 10, 20, 0.5, 100, 'ok')")
    conn.execute(
        "INSERT INTO alarms (alarm_id, agent_id, signal, event_type, reason,"
        " severity, sla_hours, sla_deadline, status, created_at)"
        " VALUES ('alm-1', 'agent-a', 'cost>budget', 'escalation', 'cost',"
        " 'High', 8, '2026-10-18 18:00:00', 'open', '2026-10-18 10:00:00')")
    conn.commit()

    from swarmax.evidence import append_evidence
    from swarmax.sealing import seal_ledger
    # sânî evidence-ledger + gerçek mühür ( verify_seals'ın okuyabileceği)
    append_evidence(conn, "test_event", {"k": "v"})
    conn.commit()
    seed = bytes.fromhex("11" * 32)
    seal_ledger(conn, seed)
    conn.commit()
    conn.close()
    return str(db)


# ------------------------------------------------------------------ protocol

def test_initialize_handshake():
    proc, out = _rpc([_init_line()])
    assert proc.returncode == 0
    r = _tools(out, 1)
    assert r is not None
    assert r["protocolVersion"] == PROTOCOL_VERSION
    assert r["capabilities"] == {"tools": {"listChanged": False}}
    assert r["serverInfo"]["name"] == "swarmax"


def test_tools_list_three_tools():
    _, out = _rpc([_init_line(), _tools_list()])
    r = _tools(out, 2)
    names = {t["name"] for t in r["tools"]}
    assert names == {"fleet_status", "agent_health", "audit_trail"}
    # her aracın bir şeması ve açıklaması olmalı
    for t in r["tools"]:
        assert t["description"]
        assert isinstance(t["inputSchema"], dict)


def test_notifications_initialized_no_reply():
    """notifications/initialized bir BİLDİRİM — yanıt üretmemeli."""
    _, out = _rpc([
        _init_line(),
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
        '{"jsonrpc":"2.0","id":7,"method":"ping","params":{}}'])
    # sadece init+ping Yanıtlanmalı — 2 yanıt, 3 değil
    ids = [d["id"] for d in out if "result" in d or "error" in d]
    assert 7 in ids
    assert len(ids) == 2


# ------------------------------------------------------------------ fleet_status

def test_fleet_status_reads_known_good_fleet(fleet_db):
    _, out = _rpc([_init_line(),
                      _call(3, "fleet_status", {"db_path": fleet_db})])
    res = _call_result(out, 3)
    assert res["ok"] is True
    assert res["summary"]["agents"] == 2
    assert res["summary"]["open_alarms"] == 1
    assert res["summary"]["events_24h"] >= 1
    assert len(res["open_alarms"]) == 1
    assert res["open_alarms"][0]["alarm_id"] == "alm-1"


def test_fleet_status_missing_db_is_red_not_crash():
    _, out = _rpc([_init_line(),
                      _call(3, "fleet_status",
                            {"db_path": "/yok/böyle/bir/dizin/swarmax.db"})])
    res = _call_result(out, 3)
    assert res["ok"] is False
    assert "db-acilamadi" in res["reason"]
    # asla traceback — JSON kanıtı geldi
    assert "Traceback" not in json.dumps(res)


# ------------------------------------------------------------------ agent_health

def test_agent_health_known_agent(fleet_db):
    _, out = _rpc([_init_line(),
                      _call(4, "agent_health",
                            {"agent_id": "agent-a", "db_path": fleet_db})])
    res = _call_result(out, 4)
    assert res["ok"] is True
    assert res["agent"]["role"] == "worker"
    assert res["state"]["open_alarms"] == 1
    assert res["state"]["events_24h"] >= 1


def test_agent_health_unknown_agent_is_red(fleet_db):
    _, out = _rpc([_init_line(),
                      _call(4, "agent_health",
                            {"agent_id": "yok-boyle-agent",
                             "db_path": fleet_db})])
    res = _call_result(out, 4)
    assert res["ok"] is False
    assert "bilinmeyen-agent" in res["reason"]


def test_agent_health_missing_agent_id_is_red(fleet_db):
    _, out = _rpc([_init_line(),
                      _call(4, "agent_health", {"db_path": fleet_db})])
    res = _call_result(out, 4)
    assert res["ok"] is False
    assert "agent_id-zorunlu" in res["reason"]


# ------------------------------------------------------------------ audit_trail

def test_audit_trail_verifies_chained_ledger(fleet_db):
    _, out = _rpc([_init_line(),
                      _call(5, "audit_trail", {"db_path": fleet_db})])
    res = _call_result(out, 5)
    assert res["ok"] is True
    assert res["chain"]["ok"] is True
    assert res["chain"]["entries_checked"] >= 1
    assert res["seals"]["count"] >= 1
    assert res["seals"]["all_ok"] is True


def test_audit_trail_broken_chain_is_red(fleet_db):
    """Zinciri-sonradan-boz: audit_trail fail-closed RED dönmeli.

    evidence_ledger'i UPDATE/DELETE tetikleyiciler korur ( §12.1 append-only),
    yani bozma-yolu INSERT'tir: araya prev_hash'i-köpük bir satır sıkıştır.
    Bu, gerçek bir saldırı-yolu değildir ( tetikleyiciler plancı-satırını
    engellemez), ama verify_chain'ın RED'ye-düşüşünü ölçer — bozuk bir
    satıra-reddetme, ave-ları sayma.
    """
    conn = sqlite3.connect(fleet_db)
    prev = conn.execute(
        "SELECT payload_hash FROM evidence_ledger ORDER BY seq DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO evidence_ledger (event_type, payload_hash, prev_hash,"
        " ed25519_sig) VALUES ('forged', "
        "'0000000000000000000000000000000000000000000000000000000000000000',"
        " ?, X'00')",
        (prev,))
    conn.commit()
    conn.close()
    _, out = _rpc([_init_line(),
                      _call(5, "audit_trail", {"db_path": fleet_db})])
    res = _call_result(out, 5)
    assert res["ok"] is False
    assert res["chain"]["ok"] is False


def test_audit_trail_broken_seal_is_red(fleet_db):
    """Mührü-boz: seals.all_ok=false → toplam ok=false.

    evidence_seals tablosu append-only-tetikleyicisizdir ( §12.1 kapsamı
    evidence_ledger'dır), yani root_hash'i UPDATE ile bozmak mümkündür.
    Bu, operatörün-yanlış-mührü veya üçüncü-bir-yazıcının-bozuk-mührünü
    modeller: verify_seals RED dönmeli, toplam ok=false olmalı."""
    conn = sqlite3.connect(fleet_db)
    conn.execute(
        "UPDATE evidence_seals SET root_hash='dead' WHERE seal_id="
        " (SELECT seal_id FROM evidence_seals ORDER BY covers_through_seq"
        " DESC LIMIT 1)")
    conn.commit()
    conn.close()
    _, out = _rpc([_init_line(),
                      _call(5, "audit_trail", {"db_path": fleet_db})])
    res = _call_result(out, 5)
    assert res["ok"] is False
    assert res["seals"]["all_ok"] is False


# ------------------------------------------------------------------ hata-yolları

def test_unknown_tool_jsonrpc_error():
    _, out = _rpc([_init_line(),
                      _call(6, "yok-boyle-arac", {})])
    errs = [d for d in out if d.get("id") == 6 and "error" in d]
    assert errs
    assert errs[0]["error"]["code"] == -32601
    assert "bilinmeyen-arac" in errs[0]["error"]["message"]


def test_invalid_json_does_not_crash():
    _, out = _rpc(["bu-bir-json-degil",
                      _init_line(),
                      '{"jsonrpc":"2.0","id":9,"method":"ping","params":{}}'])
    # ping hâlâ yanıtlanmalı — sunucu ayakta
    ids = [d["id"] for d in out if "result" in d or "error" in d]
    assert 9 in ids


def test_env_db_path_used_when_arg_absent(fleet_db, monkeypatch):
    """SWARMAX_MCP_DB env'i db_path argümanı yoksa kullanılmalı."""
    _, out = _rpc([_init_line(),
                      _call(3, "fleet_status", {})],
                     env_extra={"SWARMAX_MCP_DB": fleet_db})
    res = _call_result(out, 3)
    assert res["ok"] is True
    assert res["summary"]["agents"] == 2


# ------------------------------------------------------- G20-varsayilan-DB

def test_default_db_used_when_env_and_arg_absent(monkeypatch, tmp_path):
    """G20-pini: ne env ne argüman verilmemişse repo-altı data/swarmax.db
    varsayılanına düşülür — eski docstring "fail-closed RED" iddiası YANLIŞTI.

    Bu test varsayılanın VAROLDUĞUNU kanıtlar: KYK-dizini ( env'i ve
    argümanı temizlenmiş) ile çağrılınca db-acilamadi RED'i DEĞİL, mevcut
    repo-DB'sinden gelen bir okuma döner ( summaryagents>0 veya alarms).
    Isolasyon: SWARMAX_MCP_DB'i /yol/yok olarak set-etmesek bile sunucu
    kendisi DEFAULT_DB'ye düşmeli; bu gercek-proje-DB'sine MUDAHALE ETMEZ
    ( salt-oku mode=ro)."""
    monkeypatch.delenv("SWARMAX_MCP_DB", raising=False)
    monkeypatch.chdir(tmp_path)  # cwd bagimsiz: DEFAULT_DB mutlak-rootlu
    proc, out = _rpc([_init_line(),
                      _call(3, "fleet_status", {})],
                     env_extra={"SWARMAX_MCP_DB": ""})
    res = _call_result(out, 3)
    # env-bos-string -> falsy -> DEFAULT_DB yoluna dusmus olmali
    assert res is not None, "cevap-yok (beklenmeyen-kaynak)"
    assert res.get("ok") is True, "varsayilan-DB okunamadi: %r" % (res,)
    # geri-donen db yolu DEFAULT_DB olmali (mutlak, repo-alti)
    assert res["db"].endswith("swarmax.db"), res["db"]
    import pathlib
    assert pathlib.Path(res["db"]).is_absolute(), res["db"]
    # P0: salt-oku baglanti — yazma-denemesi RED vermemeli degil, ama sunucu
    # hicbir yazma yapmadigini kanitlamak uzere summary okundu:
    assert res["summary"]["agents"] > 0, res["summary"]


# ------------------------------------------------------- G21-dagitim-grayhole

def test_sdist_manifest_includes_mcp_server():
    """G21-pini: mcp/server.py sdist'in DISINDA birakilirsa pip-ile-gelen
    kullanicida README'nin sozunu verdigi MCP sunucusu olmaz ( dagitim-
    grayhole). MANIFEST.in'de acik bir kural olmali — packages.find
    ( where=["src"]) mcp/'yi zaten goremeyecegi icin bu kural tek sigortadır.
    """
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "mcp" in manifest, "MANIFEST.in mcp/ kurali yok: %r" % manifest
    assert any(
        part.strip().startswith(("recursive-include mcp", "include mcp"))
        for part in manifest.splitlines()), manifest
    # modulun kendisi de repo-altinda mevcut olmali (VCS-sapmasi yok)
    assert SERVER.is_file(), SERVER


def test_readme_documents_mcp_distribution_limit():
    """G21-pini: README MCP sunucusunu tanitiyorsa, dagitim-sinirini da
    soylemelidir — aksi halde wheel'de olmayan bir giris-noktasi oldugu
    izlenimi olur ( over-imply)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "mcp/server.py" in readme, "README MCP sunucu-yolunu vermiyor"
    assert "Packaging note (G21)" in readme, (
        "README G21 dagitim-sinirini belirtmiyor ( over-imply-riski)")
