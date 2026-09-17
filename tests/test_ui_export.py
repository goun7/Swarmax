"""UI export tests — chart PNG downloads + weekly report delivery (§5 UX).

The PNG path is pinned to spec, not just round-trip: RFC 2083 structure
(signature, IHDR, IDAT) and a zlib *reference* recompression check —
decompressed IDAT must be exactly ``height * (width*4 + 1)`` bytes (one
filter byte per RGBA scanline).  Email path is pinned to RFC 5322/MIME via
email.message_from_bytes with attachment count and re-decode checks.
"""
import email
import struct
import threading
import time
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone

import pytest

from swarmax.auth import bootstrap_admin, add_user
from swarmax.console import FleetConsole, _chart_name_ok, weekly_report_email
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline
from swarmax.raster import decode_png


def _ev(i: int, ts: str, cost: float = 0.01) -> dict:
    return {"event_id": f"ev{i}", "agent_id": "web-bot", "task_id": f"t{i}",
            "session_id": "s", "model_name": "m", "input_tokens": 10,
            "output_tokens": 10, "cost_usd": cost, "latency_ms": 100,
            "error_class": None, "status": "ok", "synthetic": 1, "ts": ts,
            "retry_count": 0, "ttft_s": 0.2, "task_template": None,
            "end_state_json": None}


@pytest.fixture()
def server(tmp_path):
    conn = connect(str(tmp_path / "ui.db"))
    init_db_with_migrations(conn)
    bootstrap_admin(conn, "root", "correct horse battery staple")
    add_user(conn, "view", "viewer-passphrase-9", "viewer", actor="root")
    pipe = Pipeline(conn)
    now = datetime.now(timezone.utc)
    pipe.ingest(
        [_ev(i, f"2026-09-15 10:{i:02d}:00") for i in range(8)]
        + [_ev(100 + i, (now - timedelta(hours=2, minutes=i))
               .strftime("%Y-%m-%d %H:%M:%S")) for i in range(4)])
    # 7 days of events with varying cost (EWMA Z warm-up needs ≥3 observations)
    # + per-day tool_call guards with a shifting mix (JSD chart source)
    tools = ["search", "code", "browse"]
    events, guards = [], []
    for d in range(7):
        day = (now - timedelta(days=6 - d)).strftime("%Y-%m-%d")
        for j in range(3):
            events.append(_ev(
                d * 10 + j, f"{day} 10:0{j}:00", cost=0.01 * (d + 1)))
        for j in range(4):
            guards.append({
                "event_id": f"g{d}_{j}", "agent_id": "web-bot",
                "task_id": f"t{d}_{j}", "event_type": "tool_call",
                "decision": "allow",
                "tool_name": tools[j % 3 if d % 2 else (j + 1) % 3],
                "arguments_json": "{\"q\": 1}", "synthetic": 1,
                "ts": f"{day} 10:05:0{j}"})
    pipe.ingest(events, guards)
    srv = FleetConsole(conn, db_label="ui.db").serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.2)
    base = f"http://127.0.0.1:{port}"

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def login(user, pw):
        # stop at the 303 so Set-Cookie can be read (as in test_console_v2);
        # retry: scrypt is deliberately slow and CI machines are loaded
        last: Exception | None = None
        for _ in range(3):
            req = urllib.request.Request(
                base + "/login", method="POST",
                data=urllib.parse.urlencode({"username": user, "password": pw}).encode())
            try:
                with urllib.request.build_opener(_NoRedirect).open(req,
                                                                   timeout=20) as r:
                    return r.headers["Set-Cookie"].split(";")[0]
            except urllib.error.HTTPError as exc:
                return exc.headers["Set-Cookie"].split(";")[0]
            except (urllib.error.URLError, OSError) as exc:
                last = exc
                time.sleep(1.0)
        raise last

    admin = login("root", "correct horse battery staple")
    viewer = login("view", "viewer-passphrase-9")

    def get(path, cookie=None):
        req = urllib.request.Request(base + path)
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as exc:  # 403/404 come back as data
            return exc.code, dict(exc.headers), exc.read()

    yield base, get, admin, viewer, conn
    srv.shutdown()


def _png_spec_checks(png: bytes) -> tuple[int, int]:
    """RFC 2083 structure + zlib reference recompression; returns (w, h)."""
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    pos, idat = 8, b""
    w = h = None
    while pos < len(png):
        (ln,), tag = struct.unpack(">I", png[pos:pos + 4]), png[pos + 4:pos + 8]
        payload = png[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h = struct.unpack(">II", payload[:8])
        elif tag == b"IDAT":
            idat += payload
        pos += 12 + ln
    assert w and h and idat
    raw = zlib.decompress(idat)
    assert len(raw) == h * (w * 4 + 1), "IDAT must decompress to scanlines+filter bytes"
    for y in range(h):  # filter type 0 everywhere (this encoder's contract)
        assert raw[y * (w * 4 + 1)] == 0
    return w, h


def test_chart_name_gate():
    assert _chart_name_ok("ewma") and _chart_name_ok("activity")
    assert not _chart_name_ok("ledger") and not _chart_name_ok("../../etc")


def test_png_download_is_spec_compliant(server):
    base, get, admin, _, _ = server
    st, hdrs, body = get("/chart/ewma.png", admin)
    assert st == 200 and hdrs["Content-Type"] == "image/png"
    assert "attachment" in hdrs.get("Content-Disposition", "")
    w, h = _png_spec_checks(body)
    assert (w, h) == (520, 88)  # geometry-identical twin of the on-page SVG
    px, w2, h2 = decode_png(body)
    assert (w2, h2) == (w, h) and len(px) == w * h * 4


def test_all_charts_export(server):
    base, get, admin, _, _ = server
    for name in ("sparkline", "ewma", "jsd", "cost", "errors", "activity"):
        st, hdrs, body = get(f"/chart/{name}.png", admin)
        assert st == 200 and hdrs["Content-Type"] == "image/png"
        _png_spec_checks(body)


def test_activity_png_paints_bars(server):
    base, get, admin, _, _ = server
    st, _, body = get("/chart/activity.png", admin)
    px, w, h = decode_png(body)
    colors = {(px[i], px[i + 1], px[i + 2]) for i in range(0, len(px), 4)}
    assert (88, 166, 255) in colors or (248, 81, 73) in colors


def test_chart_auth_gates(server):
    base, get, admin, viewer, _ = server
    st, hdrs, body = get("/chart/ewma.png")            # unauthenticated → login
    assert st == 200 and hdrs["Content-Type"] == "text/html"
    assert b"sign in" in body.lower()
    st, _, body = get("/chart/ewma.png", viewer)        # viewer → 403
    assert st == 403 and b"admin role required" in body
    st, _, body = get("/chart/nope.png", admin)
    assert st == 404


def test_chart_png_no_data_is_honest(tmp_path):
    """Empty window must NOT download an empty picture (honesty gate)."""
    conn = connect(str(tmp_path / "empty.db"))
    init_db_with_migrations(conn)
    c = FleetConsole(conn, db_label="empty.db")
    assert c.chart_png("sparkline") is None
    assert c.chart_png("jsd") is None


def test_report_page_and_markdown_download(server):
    base, get, admin, _, _ = server
    st, hdrs, body = get("/report/weekly", admin)
    assert st == 200 and b"# Swarmax Weekly" in body
    st, hdrs, body = get("/report/weekly?format=md", admin)
    assert st == 200 and hdrs["Content-Type"] == "text/markdown"
    assert body.startswith(b"# Swarmax Weekly")
    assert "attachment" in hdrs.get("Content-Disposition", "")


def test_weekly_email_rfc5322_with_png_attachments(server):
    base, get, admin, _, conn = server
    st, hdrs, raw = get("/report/weekly.eml", admin)
    assert st == 200 and hdrs["Content-Type"] == "message/rfc822"
    msg = email.message_from_bytes(raw)
    assert msg["Subject"].startswith("Swarmax weekly fleet report")
    assert msg["From"] and msg["To"]
    parts = list(msg.walk())
    pngs = [p for p in parts if p.get_content_type() == "image/png"]
    assert len(pngs) == 6  # sparkline, ewma, jsd, cost, errors, activity
    for p in pngs:
        w, h = _png_spec_checks(p.get_payload(decode=True))
        assert w > 0 and h > 0
    texts = [p for p in parts if p.get_content_type().startswith("text/")]
    assert {p.get_content_type() for p in texts} == {"text/plain", "text/html"}
    assert b"Swarmax Weekly" in texts[0].get_payload(decode=True)


def test_email_module_standalone_empty_store(tmp_path):
    """No events at all: message still valid, activity chart still attached."""
    conn = connect(str(tmp_path / "empty.db"))
    init_db_with_migrations(conn)
    raw = weekly_report_email(conn)
    msg = email.message_from_bytes(raw)
    pngs = [p for p in msg.walk() if p.get_content_type() == "image/png"]
    assert len(pngs) == 1 and pngs[0].get_filename() == "activity.png"
