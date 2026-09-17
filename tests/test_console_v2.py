"""Console v2 integration tests: login flow, CSRF enforcement, roles,
agent drill-down, attribution UI — all over real HTTP against a live server."""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from swarmax import auth
from swarmax.console import FleetConsole
from swarmax.db import connect, init_db_with_migrations
from swarmax.pipeline import Pipeline


@pytest.fixture()
def server(tmp_path):
    conn = connect(str(tmp_path / "c.db"))
    init_db_with_migrations(conn)
    auth.bootstrap_admin(conn, "root", "correct horse battery staple")
    auth.add_user(conn, "viewer1", "viewer-passphrase-123", "viewer", actor="root")
    pipe = Pipeline(conn)
    base = time.time()
    pipe.ingest([{
        "event_id": f"ev{i}", "agent_id": "web-bot", "task_id": f"t{i}",
        "session_id": "s", "model_name": "m", "input_tokens": 10,
        "output_tokens": 10, "cost_usd": 0.01, "latency_ms": 100,
        "error_class": None, "status": "ok", "synthetic": 1,
        "ts": f"2026-09-15 10:{i:02d}:00", "retry_count": 0, "ttft_s": 0.2,
        "task_template": None, "end_state_json": None} for i in range(5)])
    srv = FleetConsole(conn, db_label="test.db").serve("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}", conn, pipe
    srv.shutdown()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop at 3xx so Set-Cookie/Location can be inspected directly."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener():
    return urllib.request.build_opener(_NoRedirect)


def _raw(req):
    try:
        with _opener().open(req) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def _get(url, cookie=None):
    req = urllib.request.Request(url, headers={"Cookie": cookie} if cookie else {})
    return _raw(req)


def _post(url, data, cookie=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Cookie": cookie} if cookie else {})
    return _raw(req)


def test_anonymous_is_redirected_to_login(server):
    base, _, _ = server
    code, _, headers = _get(base + "/")
    assert code == 303 and headers["Location"].endswith("/login")
    code, page, _ = _get(base + "/login")
    assert code == 200 and "sign in" in page.lower()


def test_login_sets_cookie_and_renders_console(server):
    base, conn, _ = server
    code, _, headers = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    assert code == 303
    cookie = headers["Set-Cookie"].split(";")[0]
    assert cookie.startswith("swarmax_session=")
    code, page, _ = _get(base + "/", cookie)
    assert "Swarmax Fleet Console" in page
    assert "logout (root)" in page


def test_csrf_is_enforced(server):
    base, _, _ = server
    _, _, headers = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    cookie = headers["Set-Cookie"].split(";")[0]
    # resolve without the CSRF token must 403
    code, body, _ = _post(base + "/resolve", {"alarm_id": "alm_x"}, cookie=cookie)
    assert code == 403 and "csrf" in body


def test_viewer_cannot_resolve_admin_can(server):
    base, conn, pipe = server
    # create one open alarm directly (the seeded events are healthy)
    conn.execute(
        "INSERT INTO alarms (alarm_id, agent_id, task_id, signal, event_type,"
        " reason, severity, sla_hours, sla_deadline, trigger_value, protection,"
        " status, created_at) VALUES ('alm_t1', 'web-bot', NULL, 'error.rate>0.20',"
        " 'escalation', 'test', 'Critical', 4, '2026-09-16 00:00:00', NULL,"
        " NULL, 'open', '2026-09-15 10:00:00')")
    conn.commit()
    # viewer session
    _, _, h1 = _post(base + "/login", {
        "username": "viewer1", "password": "viewer-passphrase-123"})
    vcookie = h1["Set-Cookie"].split(";")[0]
    _, vpage, _ = _get(base + "/", vcookie)
    csrf_v = vpage.split("name='csrf' value='")[1].split("'")[0]
    code, body, _ = _post(base + "/resolve", {
        "alarm_id": "alm_t1", "csrf": csrf_v}, cookie=vcookie)
    assert code == 403 and "admin" in body
    # admin session
    _, _, h2 = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    acookie = h2["Set-Cookie"].split(";")[0]
    _, apage, _ = _get(base + "/", acookie)
    csrf_a = apage.split("name='csrf' value='")[1].split("'")[0]
    code, _, _ = _post(base + "/resolve", {
        "alarm_id": "alm_t1", "csrf": csrf_a}, cookie=acookie)
    assert code == 303
    assert conn.execute(
        "SELECT status FROM alarms WHERE alarm_id='alm_t1'"
    ).fetchone()["status"] == "resolved"


def test_resolve_unknown_or_closed_alarm_fails_closed(server):
    """D2: a stale/unknown alarm id must 404 and never fabricate evidence."""
    base, conn, _ = server
    _, _, h = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    cookie = h["Set-Cookie"].split(";")[0]
    _, page, _ = _get(base + "/", cookie)
    csrf = page.split("name='csrf' value='")[1].split("'")[0]
    code, body, _ = _post(base + "/resolve", {
        "alarm_id": "alm_ghost", "csrf": csrf}, cookie=cookie)
    assert code == 404 and "not open" in body
    # payload lives in its own table; the honest assertion: no new
    # alarm_resolved evidence row appeared during the 404 attempt
    n = conn.execute(
        "SELECT COUNT(*) FROM evidence_ledger"
        " WHERE event_type='alarm_resolved'").fetchone()[0]
    assert n == 0


def test_agent_metric_charts_accessible(server):
    """WS-1: EWMA-Z + JSD charts render as accessible SVG with table alternates."""
    base, conn, pipe = server
    import random as _r
    from datetime import datetime, timedelta, timezone as _tz
    now = datetime.now(_tz.utc).replace(tzinfo=None, microsecond=0)
    rng = _r.Random(7)
    agent = "chart-bot"
    tools = ["search", "write", "calc"]
    for d in range(7):
        day = now - timedelta(days=6 - d)
        evs, guards = [], []
        cost = 8.0 + rng.uniform(-1.0, 1.0) + (14.0 if d == 6 else 0.0)
        for i in range(6):
            evs.append({
                "event_id": f"c{d}-{i}", "agent_id": agent, "task_id": f"ct{d}-{i}",
                "session_id": "s", "model_name": "m", "input_tokens": 10,
                "output_tokens": 10, "cost_usd": cost / 6, "latency_ms": 100,
                "error_class": None, "status": "ok", "synthetic": 1,
                "ts": day.isoformat(sep=" "), "retry_count": 0, "ttft_s": 0.2,
                "task_template": None, "end_state_json": None})
        for i in range(8):
            guards.append({"event_id": f"g{d}-{i}", "agent_id": agent,
                           "task_id": f"ct{d}-{i % 6}", "ts": day.isoformat(sep=" "),
                           "event_type": "tool_call", "tool_name": tools[i % 3],
                           "decision": "allow", "arguments_json": "{}",
                           "synthetic": 1})
        pipe.ingest(evs, guards)
    _, _, h = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    cookie = h["Set-Cookie"].split(";")[0]
    code, page, _ = _get(base + f"/agent/{agent}", cookie)
    assert code == 200
    # accessible SVG: aria-label + <title>/<desc> on both §3.2 charts
    assert "aria-label='EWMA Z by day" in page
    assert "aria-label='Tool-mix JSD by day" in page
    assert "<desc>" in page and "<title>" in page
    # per-point tooltips and data-table alternatives
    assert "<circle" in page and "data table" in page
    # Z axis unit and JSD thresholds surfaced
    assert "σ" in page and "0.40" in page


def test_agent_page_and_404(server):
    base, _, _ = server
    _, _, headers = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    cookie = headers["Set-Cookie"].split(";")[0]
    code, page, _ = _get(base + "/agent/web-bot", cookie)
    assert code == 200 and "agent web-bot" in page and "Daily series" in page
    code, body, _ = _get(base + "/agent/ghost-bot", cookie)
    assert code == 404 and body == "unknown agent"


def test_api_summary_requires_session(server):
    base, _, _ = server
    code, _, headers = _get(base + "/api/summary")
    assert code == 303  # redirected: no data without a session
    _, _, headers = _post(base + "/login", {
        "username": "root", "password": "correct horse battery staple"})
    cookie = headers["Set-Cookie"].split(";")[0]
    code, body, _ = _get(base + "/api/summary", cookie)
    assert code == 200 and json.loads(body)["agents"] >= 1
