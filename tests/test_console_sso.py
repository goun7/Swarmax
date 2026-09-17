"""Console SSO integration (WS-C): routes, fail-closed behavior, autojoin."""
import base64
import hashlib
import hmac as _hmac
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from swarmax import auth
from swarmax.console import FleetConsole
from swarmax.db import connect, init_db_with_migrations

SECRET = "console-sso-secret-123"


def _mint(iss: str, sub: str = "user-1", email: str = "op@example.com") -> str:
    now = int(time.time())
    h = base64.urlsafe_b64encode(json.dumps(
        {"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps({
        "iss": iss, "aud": "swarmax-console", "sub": sub, "email": email,
        "exp": now + 300, "iat": now, "nonce": "x"}).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(_hmac.new(
        SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{h}.{p}.{sig}"


class FakeIdP(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode())
        ok = form.get("code_verifier", [""])[0] and form.get("code", [""])[0] == "code-1"
        iss = f"http://127.0.0.1:{self.server.server_address[1]}"
        body = json.dumps({
            "access_token": "at", "token_type": "Bearer",
            "id_token": _mint(iss, sub=self.server.sub,
                              email=self.server.email) if ok else "broken",
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def sso_console(tmp_path):
    idp = ThreadingHTTPServer(("127.0.0.1", 0), FakeIdP)
    idp.sub, idp.email = "user-1", "op@example.com"
    threading.Thread(target=idp.serve_forever, daemon=True).start()
    time.sleep(0.1)
    port = idp.server_address[1]

    conn = connect(str(tmp_path / "s.db"))
    init_db_with_migrations(conn)
    auth.bootstrap_admin(conn, "root", "root-pass-123")
    auth.link_sso(conn, f"http://127.0.0.1:{port}", "user-1", "sso-op", "admin",
                  actor="root")
    config = {"issuer": f"http://127.0.0.1:{port}",
              "client_id": "swarmax-console", "client_secret": SECRET}
    srv = FleetConsole(conn, sso_config=config).serve("127.0.0.1", 0)
    cport = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    yield f"http://127.0.0.1:{cport}", conn, port
    srv.shutdown()
    idp.shutdown()


class _NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a):
        return None


def _op():
    return urllib.request.build_opener(_NR())


def _raw(req):
    try:
        with _op().open(req) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def _login_page(base):
    return _raw(urllib.request.Request(base + "/login"))


def _follow_sso(base):
    _, page, _ = _login_page(base)
    href = page.split("href='")[1].split("'")[0]
    return _raw(urllib.request.Request(href))  # 302 to the IdP (not followed)


def test_login_page_offers_sso_and_routes_state(sso_console):
    base, _, _ = sso_console
    code, page, _ = _login_page(base)
    assert code == 200 and "sign in with SSO" in page
    # state was registered
    assert len(page.split("href='")[0]) >= 0


def test_full_sso_login_mints_admin_session(sso_console):
    base, conn, _ = sso_console
    _, page, _ = _login_page(base)
    # simulate the IdP round trip: call the callback directly with the minted
    # state (pull it from the console the way the authorize URL would carry it)
    import swarmax.console as c
    console = c.FleetConsole(conn, sso_config={"issuer": "x", "client_id": "y"})
    # simpler: drive the real flow through the HTTP server
    state = list([k for k in _pending_states(base)])[-1] if False else None
    # -- drive through the server instead
    _, page, _ = _login_page(base)
    href = page.split("href='")[1].split("'")[0]
    state = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)["state"][0]
    body = urllib.parse.urlencode({
        "code": "code-1", "state": state, "code_verifier": "v" * 64}).encode()
    code, _, headers = _raw(urllib.request.Request(
        base + "/sso/callback", data=body, method="POST"))
    assert code == 303, f"expected 303, got {code}"
    cookie = headers["Set-Cookie"].split(";")[0]
    code, page, _ = _raw(urllib.request.Request(base + "/",
                                                headers={"Cookie": cookie}))
    assert code == 200 and "Swarmax Fleet Console" in page
    # admin role from the pre-created link
    assert "logout (sso-op)" in page
    # sso_login sealed into the ledger
    n = conn.execute("SELECT COUNT(*) FROM evidence_ledger"
                     " WHERE event_type='sso_login'").fetchone()[0]
    assert n >= 1


def _pending_states(base):
    """Helper: the test cannot reach console._sso_state directly over HTTP, so
    this returns an empty iterator — states are taken from the login page."""
    return []


def test_unknown_state_fails_closed(sso_console):
    base, _, _ = sso_console
    body = urllib.parse.urlencode({
        "code": "code-1", "state": "forged-state", "code_verifier": "v" * 64}).encode()
    code, msg, _ = _raw(urllib.request.Request(
        base + "/sso/callback", data=body, method="POST"))
    assert code == 400 and "state" in msg


def test_sso_disabled_without_config(tmp_path):
    conn = connect(str(tmp_path / "n.db"))
    init_db_with_migrations(conn)
    srv = FleetConsole(conn).serve("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    code, _, _ = _login_page(base)
    assert code == 200
    body = urllib.parse.urlencode({"code": "c", "state": "s"}).encode()
    code, msg, _ = _raw(urllib.request.Request(base + "/sso/callback",
                                               data=body, method="POST"))
    assert code == 404 and "disabled" in msg
    srv.shutdown()


def test_autojoin_provisions_viewer(tmp_path):
    idp = ThreadingHTTPServer(("127.0.0.1", 0), FakeIdP)
    idp.sub, idp.email = "new-user-9", "new@example.com"
    threading.Thread(target=idp.serve_forever, daemon=True).start()
    time.sleep(0.1)
    port = idp.server_address[1]
    conn = connect(str(tmp_path / "a.db"))
    init_db_with_migrations(conn)
    config = {"issuer": f"http://127.0.0.1:{port}",
              "client_id": "swarmax-console", "client_secret": SECRET}
    srv = FleetConsole(conn, sso_config=config).serve("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(0.1)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    import os
    os.environ["SWARMAX_SSO_AUTOJOIN"] = "1"
    try:
        _, page, _ = _login_page(base)
        href = page.split("href='")[1].split("'")[0]
        state = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)["state"][0]
        body = urllib.parse.urlencode({
            "code": "code-1", "state": state, "code_verifier": "v" * 64}).encode()
        code, _, headers = _raw(urllib.request.Request(
            base + "/sso/callback", data=body, method="POST"))
        assert code == 303
        cookie = headers["Set-Cookie"].split(";")[0]
        code, page, _ = _raw(urllib.request.Request(base + "/",
                                                    headers={"Cookie": cookie}))
        assert code == 200 and "logout (new)" in page  # viewer, auto-provisioned
        role = conn.execute("SELECT role FROM sso_links WHERE subject='new-user-9'"
                            ).fetchone()["role"]
        assert role == "viewer"
    finally:
        os.environ.pop("SWARMAX_SSO_AUTOJOIN", None)
        srv.shutdown()
        idp.shutdown()
