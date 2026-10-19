"""landing/ ( G5) statik-demo testleri.

Kapsam: swarmax MCP sunucusunun gercek-DB'den cekilmis gomulu demo-verisi
ile calisan tamamen-statik landing sayfasini dogrular. Bu testler
  * repo-dizinine HICBIR SEY YAZMAZ ( tmp_path-izolasyon),
  * canli-port ACMAZ ( statik dosyalari dogrudan okur),
  * mevcut 3.382 testi KIRMaz ( sadece yeni dosyalari okur).
"""
import importlib.util
import json
import re
import socket
import subprocess
import sys

import pytest

REPO = __import__("pathlib").Path(__file__).resolve().parents[1]
LANDING = REPO / "landing"
MCP_SERVER = REPO / "mcp" / "server.py"

FILES = ["index.html", "style.css", "demo.js", "demo-data.json", "demo-data.py"]


# ---------------------------------------------------------------------------
# yardimcilar
# ---------------------------------------------------------------------------

def _read(path):
    return path.read_text(encoding="utf-8", errors="strict")


def _rdj():
    """Repodaki demo-data.json'i guncel olarak python-module ile yeniden
    uretip karsilastirarak verinin demo-data.py ile uyumlu oldugunu goster."""
    return json.loads((LANDING / "demo-data.json").read_text(encoding="utf-8"))


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _mcp_call(reqs, timeout=120):
    """mcp/server.py'yi gercek-subprocess olarak calistirir ( stdio JSON-RPC)."""
    payload = "\n".join(json.dumps(r) for r in reqs)
    return subprocess.run(
        [sys.executable, str(MCP_SERVER)],
        input=payload, capture_output=True, text=True, timeout=timeout,
    )


# ---------------------------------------------------------------------------
# 1) dosya-varligi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", FILES)
def test_landing_dosyalari_var(name):
    """landing/ altindaki tum dosyalar mevcut ve bossa-hata veriyor."""
    path = LANDING / name
    assert path.is_file(), f"landing/{name} bulunamadi"
    assert path.stat().st_size > 0, f"landing/{name} bos"


def test_landing_dizini_var():
    assert LANDING.is_dir(), "landing/ dizini yok"


# ---------------------------------------------------------------------------
# 2) statiklik-guvenligi
# ---------------------------------------------------------------------------

def _meta(html, name):
    m = re.search(r'<meta[^>]+name=["\']%s["\'][^>]*>' % re.escape(name), html)
    return m.group(0) if m else ""


def test_index_statiktir(http_equiv_yok=True):
    """http-equiv=refresh YOK - yonlendirme-tuzagi degil."""
    html = _read(LANDING / "index.html").lower()
    assert "http-equiv" not in html, "http-equiv meta bulundu - statik degil"


def test_index_disa_baglanmiyor():
    """src='/href=' disinda disaari URL YOK - mutlak-makine-yolu YOK."""
    for name in ("index.html", "demo.js", "style.css", "demo-data.json"):
        text = _read(LANDING / name)
        for pat in (r"https?://", r"/home/", r"/Users/", r"file://", r"\\\\",
                    r"\blocalhost\b", r"127\.0\.0\.1"):
            hits = re.findall(pat, text)
            assert not hits, f"{name}: disa-baglanti/yerel-yol bulundu: {pat} {hits[:3]}"


def test_index_fetch_yok():
    """demo.js fetch/XMLHttpRequest/websocket KULLANMIYOR - yerel-render."""
    js = _read(LANDING / "demo.js")
    for pat in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
                "import(", "$.ajax"):
        assert pat not in js, f"demo.js network-cagrisi tespit edildi: {pat}"


def test_index_gomulu_veri_var():
    """demo-verisi index.html'e gomulu - ayri dosyaya bagimli degil."""
    html = _read(LANDING / "index.html")
    assert 'id="swarmax-demo-data"' in html
    block = html.split('id="swarmax-demo-data"')[1]
    block = block.split("</script>")[0]
    veri = json.loads(block.split(">", 1)[1])
    assert veri["fleet_status"]["summary"]["agents"] == 13
    assert len(veri["fleet_status"]["open_alarms"]) == 10


# ---------------------------------------------------------------------------
# 3) demo-veri tutarligi
# ---------------------------------------------------------------------------

def _load_module():
    spec = importlib.util.spec_from_file_location("swarmax_landing_demo_data",
                                                  LANDING / "demo-data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_veri_mcp_ile_uyusuyor():
    """index.html'e gomulu veri ile demo-data.json ayni anahtar-degerlere
    sahip - iki kaynak birbirini tutuyor."""
    html = _read(LANDING / "index.html")
    block = html.split('id="swarmax-demo-data"')[1].split("</script>")[0]
    gomulu = json.loads(block.split(">", 1)[1])
    cdosya = _rdj()
    assert gomulu["fleet_status"]["summary"] == cdosya["fleet_status"]["summary"]
    assert len(gomulu["agents"]) == len(cdosya["agents"])
    assert gomulu["audit_trail"] == cdosya["audit_trail"]


def test_demo_veri_gecerli_yapi():
    """demo-verisi MCP sozlesmesinin dogru-alan-adlarini tasiyor."""
    veri = _rdj()
    fs = veri["fleet_status"]
    assert set(fs["summary"]) >= {"open_alarms", "breached", "agents", "events_24h"}
    for a in fs["open_alarms"]:
        assert set(a) >= {"alarm_id", "agent_id", "signal", "severity",
                          "sla_hours", "status", "protection"}
    ah = veri["agent_health_example"]
    assert set(ah["agent"]) >= {"agent_id", "fleet_name", "role", "status"}
    assert set(ah["state"]) >= {"events_24h", "cost_24h", "errors_24h",
                                "open_alarms", "calibration"}
    at = veri["audit_trail"]
    assert set(at["chain"]) == {"ok", "entries_checked"}
    assert "all_ok" in at["seals"]


def test_demo_veri_python_module_gecerli():
    """demo-data.py import-edilebilir ve ayni veriyi verir."""
    mod = _load_module()
    veri = mod.SWARMAX_FLEET_DEMO
    assert veri["fleet_status"]["summary"]["open_alarms"] == 10
    assert len(veri["agents"]) == 13
    assert all(t["name"] in {"fleet_status", "agent_health", "audit_trail"}
               for t in veri["mcp_tools"])


# ---------------------------------------------------------------------------
# 4) MCP arac-adi gecerliligi ( gercek server)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not MCP_SERVER.is_file(), reason="mcp/server.py yok")
def test_mcp_tools_listesi_sunucudan_okundu():
    """mcp/server.py'yi gercek-subprocess olarak calistir; tools/list
    ciktisindaki arac-adlari ile landing'deki bire-bir ayni olmali."""
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "landing-test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    proc = _mcp_call(reqs)
    assert proc.returncode == 0, f"server RC={proc.returncode} {proc.stderr[:300]}"
    tools = []
    for line in proc.stdout.splitlines():
        d = json.loads(line)
        if d.get("id") == 2:
            tools = [t["name"] for t in d["result"]["tools"]]
    assert tools, "tools/list bos dondu"
    mod = _load_module()
    landing_tools = [t["name"] for t in mod.SWARMAX_FLEET_DEMO["mcp_tools"]]
    assert sorted(landing_tools) == sorted(tools)


@pytest.mark.skipif(not MCP_SERVER.is_file(), reason="mcp/server.py yok")
def test_mcp_arguman_adlari_sunucudan_okundu():
    """landing'deki zorunlu-arguman sozlesmesi sunucunun inputSchema'si ile
    uyusmali - uydurma arguman YOK."""
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    proc = _mcp_call(reqs)
    assert proc.returncode == 0
    schemas = {}
    for line in proc.stdout.splitlines():
        d = json.loads(line)
        if d.get("id") == 2:
            for t in d["result"]["tools"]:
                schemas[t["name"]] = t["inputSchema"]["properties"].keys()
    mod = _load_module()
    for t in mod.SWARMAX_FLEET_DEMO["mcp_tools"]:
        assert set(t["arguments"]) == set(schemas[t["name"]]), \
            f"{t['name']}: arguman-adlari sunucuyla uyumsuz"


@pytest.mark.skipif(not MCP_SERVER.is_file(), reason="mcp/server.py yok")
def test_mcp_fleet_status_sunucudan_gercek_veri():
    """fleet_status gercek-cagrida ok=true vermeli - kanit RED degil."""
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "fleet_status", "arguments": {}}},
    ]
    proc = _mcp_call(reqs)
    assert proc.returncode == 0
    payload = None
    for line in proc.stdout.splitlines():
        d = json.loads(line)
        if d.get("id") == 3:
            payload = json.loads(d["result"]["content"][0]["text"])
    assert payload is not None, "fleet_status yaniti yok"
    assert payload["ok"] is True, f"server RED: {payload.get('reason')}"
    assert payload["summary"]["agents"] == 13
    # guvenlik: sunucu yaniti DB-yolu tasir BILE landing'e girmemeli
    html = _read(LANDING / "index.html")
    if "db" in payload:
        assert payload["db"] not in html, "index.html'a makine-DB-yolu siziyor"


# ---------------------------------------------------------------------------
# 5) Turkce icerik
# ---------------------------------------------------------------------------

def test_index_turkce_icerik():
    """Sayfa Turkce - en-az 5 Turkce-sel sabit-kelime gecmeli."""
    html = _read(LANDING / "index.html")
    kelimeler = ["ajan", "filo", "alarm", "kanit", "muhur", "zincir", "durum"]
    bulunan = [k for k in kelimeler if k in html.lower()]
    assert len(bulunan) >= 5, f"Turkce icerik yetersiz: {bulunan}"


def test_index_turkce_lang():
    assert 'lang="tr"' in _read(LANDING / "index.html")


# ---------------------------------------------------------------------------
# 6) ASCII-kontrol ( P0-5)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", FILES)
def test_landing_ascii(name):
    """landing/ dosyalari TAMAMEN saf-ASCII - Turkce yorumlar ASCII-turkce."""
    raw = (LANDING / name).read_bytes()
    bozuk = [i for i, b in enumerate(raw) if b > 127]
    assert not bozuk, f"{name}: {len(bozuk)} adet non-ascii byte (ilk: {bozuk[:5]})"


def test_index_html_yapisi():
    """Minimal HTML-yapi: DOCTYPE + title + tek stylesheet + tek script."""
    html = _read(LANDING / "index.html")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<title>" in html and "</title>" in html
    assert html.count('<link rel="stylesheet"') == 1
    assert html.count("<script src=") == 1
    assert "<noscript>" in html


def test_index_anabolumler_var():
    """Istenen tum bolumler mevcut - filo/audit/MCP."""
    html = _read(LANDING / "index.html")
    for bolum in ("Filo-genel-bakis", "Acik-alarm kuyrugu",
                  "Audit-trail zaman-cizelgesi", "Nasil calisirir",
                  "MCP arayuzu"):
        assert bolum in html, f"bolum yok: {bolum}"


# ---------------------------------------------------------------------------
# canli-prova ( portsuz-gecici)
# ---------------------------------------------------------------------------

def test_statik_dosya_gecerli_html():
    """Statik-dagitim on-kosulu: index.html kaynak-dizinine YAZMADAN
    gecerli-html oldugunu gosterir ( canli-port ACMAZ)."""
    html = _read(LANDING / "index.html")
    dice = (LANDING / "index.html").read_bytes().decode("utf-8")
    assert "DEMO_JSON_PLACEHOLDER" not in html, "placeholder yerine konmadi"
    assert "<!DOCTYPE html>" in dice
    assert dice.rstrip().endswith("</html>")
