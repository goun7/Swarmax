#!/usr/bin/env python3
"""swarmax MCP sunucusu — Model Context Protocol 2025-06-18 over stdio.

Swarmax filo-sorgu çekirdeğini AI ajanlarına MCP araçları olarak sunar.

Tasarım-ilkesi ( tamga/sester MCP sunucuları ile aynı sözleşme):
  • SAF STDLIB — hiçbir pip bağımliliği; sunucu tek-başına çalışır.
  • HİÇBİR ZAMAN exception — her araç JSON kanıtı döndürür; traceback
    DEĞİL "ok:false, reason:…" ( tamga AT-192 message-RED disiplini).
  • DB-yolu: db_path argümanı -> SWARMAX_MCP_DB env'i -> repo-altı
    data/swarmax.db varsayılanı ( sirayla; sonuncusu mevcut degilse
    db-acilamadi RED'i). Varsayilan GERCEK-DB oldugu icin MCP-istemcisi
    open-alarm sayilarini degil, yalnizca salt-oku amaclariyla erisir.
  • SALT-OKUMA — bu sunucu hiçbir şey YAZMAZ. fleet_status/agent_health
    sadece SELECT'ler okur; audit_trail mevcut mühürleri DOĞRULAR, yeni
    mühür ÜRETLMEZ. otel_relay ( stateless-forwarder) ve seal_ledger
    ( yazma-yolu) bilinçli olarak burada YOK.

Araçlar:
  fleet_status  açık-alarmlar + ajan-sayısı + 24s-etkinlikler ( FleetConsole.summary)
  agent_health  tek-ajan durum sayfası ( console.agent_state)
  audit_trail   evidence-ledger zincir + mühür doğrulaması ( verify_chain+verify_seals)

Çalıştırma:
  python3 mcp/server.py                   # stdio JSON-RPC
  SWARMAX_MCP_DB=/yol/swarmax.db python3 mcp/server.py
  ( istemci tarafı: "command": "python",
    "args": ["<repo>/mcp/server.py"],
    "env": {"SWARMAX_MCP_DB": "/yol/swarmax.db"})
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "swarmax"
SERVER_VERSION = "0.1.0"

ROOT = Path(__file__).resolve().parents[1]
# src/swarmax paketini içe-aktarmak için ( subprocess-izolasyon YOK — araçlar
# Python-API'yı doğrudan çağırır, çünkü fleet konsolu zaten projenin kendi
# okuma-yoludur; tamga'nın subprocess-deseninden farklı, swarmax'ta
# CLI-yüzü yoktur).
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# SW-G42C: varsayilan-DB-test-ortamlarinda-yonlendirilebilsin diye env
# uzerinden-gecersiz-kilinabilir ( CI-de data/swarmax.db-gitignore'li-oldugu
# icin-YOK; testler-kendi-filo-DB'lerini-buraya-yonlendirir). Bos-string
# falsy-oldugundan-yoksayilir — gercek-depolyonunda-davranis-aynidir.
DEFAULT_DB = Path(os.environ.get("SWARMAX_MCP_DEFAULT_DB", "")
                  ) if os.environ.get("SWARMAX_MCP_DEFAULT_DB") \
    else ROOT / "data" / "swarmax.db"


def _result(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id, code: int, msg: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": msg}}


def _text(payload: dict) -> dict:
    """Asla-exception sözleşmesinin-son-kapısı: serileştirme-başarısızlığı
    bile JSON kanıtı döndürür ( tamga AT-192 message-RED disiplini)."""
    try:
        text = json.dumps(_jsonable(payload), ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — son-kapı, traceback-YASAK
        text = json.dumps({"ok": False,
                           "reason": f"serilestirme-hatasi: {type(e).__name__}: {e}"})
    return {"content": [{"type": "text", "text": text}]}


def _jsonable(obj):
    """sqlite3.Row → dict, özyineli. agent_state() agent_health içinde Row
    listeleri döndürür ( tools_7d/recent_alarms/recent_tickets) ve bunlar
    json.dumps'a-verilemez — sunucu traceback'i çökertir. Bu dönüşüm OLMAZSA
    sözleşme ( asla-exception) delinir; bu yüzden burada, serileştirme
    yerinde yapılır."""
    if isinstance(obj, sqlite3.Row):
        #Row.keys() liste-döndürür — `k in obj` Row'da değer-araması yapar
        #( SIM118 burada yanlış-uyarır), keys() gereklidir.
        return {k: _jsonable(obj[k]) for k in obj.keys()}  # noqa: SIM118
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _connect(db_path: str) -> sqlite3.Connection | None:
    """swarmax.db'yi READ-ONLY aç. Hata → exception DEĞİL None.

    read_only=True: sunucu ASLA yazmaz (PRAGMA journal_mode=WAL okumayı
    bozmaz; fakat bağlantıyı uri=True+ro modunda açarak çifte-yazma
    riskini ortadan kaldırır).
    """
    if not db_path:
        return None
    try:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _resolve_db(args: dict) -> str:
    return (args.get("db_path") or os.environ.get("SWARMAX_MCP_DB")
            or str(DEFAULT_DB))


def _rowify(rows) -> list:
    """sqlite3.Row listesini JSON'a çevir."""
    return [dict(r) for r in rows] if rows else []


# --- araç implementasyonları ----------------------------------------------------

def _tool_fleet_status(args: dict) -> dict:
    db = _resolve_db(args)
    conn = _connect(db)
    if conn is None:
        return {"ok": False, "reason": f"db-acilamadi: {db}"}
    try:
        from swarmax.console import FleetConsole
        summary = FleetConsole(conn).summary()
        open_alarms = FleetConsole(conn).open_alarms()
        return {"ok": True, "db": db, "summary": summary,
                "open_alarms": _rowify(open_alarms)}
    except Exception as e:  # noqa: BLE001 — cephedeki her hata JSON kanıtı
        return {"ok": False, "reason": f"fleet-status-hatasi: {type(e).__name__}: {e}"}
    finally:
        conn.close()


def _tool_agent_health(args: dict) -> dict:
    agent_id = args.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        return {"ok": False, "reason": "agent_id-zorunlu (string)"}
    db = _resolve_db(args)
    conn = _connect(db)
    if conn is None:
        return {"ok": False, "reason": f"db-acilamadi: {db}"}
    try:
        from swarmax.console import agent_state
        row = conn.execute(
            "SELECT agent_id, fleet_name, role, status FROM fleet_agents"
            " WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            return {"ok": False, "reason": f"bilinmeyen-agent: {agent_id}",
                    "db": db}
        state = agent_state(conn, agent_id)
        return {"ok": True, "db": db, "agent": dict(row), "state": state}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"agent-health-hatasi: {type(e).__name__}: {e}"}
    finally:
        conn.close()


def _tool_audit_trail(args: dict) -> dict:
    db = _resolve_db(args)
    conn = _connect(db)
    if conn is None:
        return {"ok": False, "reason": f"db-acilamadi: {db}"}
    try:
        from swarmax.evidence import verify_chain
        from swarmax.sealing import verify_seals
        chain_ok, entries = verify_chain(conn)
        seals = verify_seals(conn)
        return {"ok": bool(chain_ok and seals.get("all_ok")),
                "db": db,
                "chain": {"ok": chain_ok, "entries_checked": entries},
                "seals": {"count": seals.get("seals", 0),
                          "all_ok": seals.get("all_ok"),
                          "results": seals.get("results", [])}}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"audit-trail-hatasi: {type(e).__name__}: {e}"}
    finally:
        conn.close()


TOOLS = {
    "fleet_status": {
        "handler": _tool_fleet_status,
        "description": (
            "Swarmax filosunun anlık-durumunu verir: açık-alarm sayısı, "
            "SLA'sı-geçmiş ( breached) alarm sayısı, kayıtlı ajan sayısı, "
            "son-24-saatten-etkinlik sayısı ve açık-alarmların listesi "
            "( şiddete-göre-sıralı). Salt-okuma. "
            "Dönüş: {ok, db, summary, open_alarms} — ok=false RED."),
        "schema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": ("swarmax.db yolu ( opsiyonel — verilmezse "
                                    "SWARMAX_MCP_DB env'i veya repo-altındaki "
                                    "data/swarmax.db kullanılır)"),
                }},
            "required": [],
        }},
    "agent_health": {
        "handler": _tool_agent_health,
        "description": (
            "Tek-ajanın durum-sayfasını verir: 24s-etkinlik/maliyet/hata "
            "sayıları, açık-alarm ve ticket'lar, kalibrasyon-durumu, 7-günün "
            "araç-kullanımı, son-alarm/ticket'lar. Salt-okuma. "
            "Dönüş: {ok, db, agent, state} — bilinmeyen-agent RED."),
        "schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "ajan tanımlayıcısı ( zorunlu)",
                },
                "db_path": {
                    "type": "string",
                    "description": "swarmax.db yolu ( opsiyonel)",
                }},
            "required": ["agent_id"],
        }},
    "audit_trail": {
        "handler": _tool_audit_trail,
        "description": (
            "Filonun evidence-ledger'ını bağımsız-doğrular: hash-zinciri "
            "( prev-link + SHA-256 + imza-sözleşmesi) VE Ed25519/Merkle "
            "mühürlerinin tamamını. Salt-okuma — yeni mühür ÜRETMEZ. "
            "Dönüş: {ok, db, chain{ok, entries_checked}, seals{...}} "
            "— zincir ya da mühür bozuksa ok=false RED."),
        "schema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "swarmax.db yolu ( opsiyonel)",
                }},
            "required": [],
        }},
}


def _tools_list_result() -> dict:
    return {"tools": [
        {"name": name,
         "description": spec["description"],
         "inputSchema": spec["schema"]}
        for name, spec in TOOLS.items()]}


def _handle_call(req_id, params: dict) -> dict | None:
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    spec = TOOLS.get(name)
    if spec is None:
        return _err(req_id, -32601, f"bilinmeyen-arac: {name}")
    try:
        payload = spec["handler"](args)
    except Exception as e:  # noqa: BLE001 — hiçbir yol exception'a düşmez
        payload = {"ok": False,
                   "reason": f"arac-ic-hata: {type(e).__name__}: {e}"}
    return _result(req_id, _text(payload))


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError:
            sys.stdout.write(
                json.dumps(_err(None, -32600, "gecersiz-json")) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(req, dict):
            sys.stdout.write(
                json.dumps(_err(None, -32600, "istek-bir-nesne-degil")) + "\n")
            sys.stdout.flush()
            continue
        method = req.get("method")
        req_id = req.get("id")
        if method == "initialize":
            sys.stdout.write(json.dumps(_result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                    "instructions": (
                        "Swarmax filo-sorgu sunucusu (salt-okuma). "
                        "fleet_status → filo-özeti+açık-alarm; "
                        "agent_health → tek-ajan-durumu; "
                        "audit_trail → evidence-ledger-zincir+mühür. "
                        "Her araç JSON kanıtı döner, asla exception fırlatmaz. "
                        "DB yolu SWARMAX_MCP_DB env'inde veya db_path "
                        "argümanında verilir."),
                }})) + "\n")
        elif method == "notifications/initialized":
            continue  # bildirim — yanıt yok
        elif method == "tools/list":
            sys.stdout.write(
                json.dumps(_result(req_id, _tools_list_result())) + "\n")
        elif method == "tools/call":
            resp = _handle_call(req_id, req.get("params") or {})
            if resp is not None:
                sys.stdout.write(
                    json.dumps(resp, ensure_ascii=False) + "\n")
        elif method == "ping":
            sys.stdout.write(json.dumps(_result(req_id, {})) + "\n")
        elif req_id is not None:
            sys.stdout.write(json.dumps(_err(
                req_id, -32601, f"bilinmeyen-method: {method}")) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
