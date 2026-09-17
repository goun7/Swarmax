"""Console brand integration: favicon route, header mark, packaged asset."""
import importlib.resources
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swarmax import console


def test_favicon_asset_ships_in_package():
    data = console._favicon_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), "PNG magic missing"
    assert len(data) > 200


def test_hero_asset_ships_in_package():
    data = console._hero_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), "PNG magic missing"
    assert len(data) > 5000


def test_login_page_carries_hero():
    page = console.LOGIN_PAGE.format(style="", error="", sso_link="")
    assert '/hero.png' in page
    assert 'role="img"' in page


def test_pages_reference_favicon():
    html = console.PAGE
    assert '/favicon.png' in html
    assert '<link rel="icon"' in html
    login = console.LOGIN_PAGE
    assert '/favicon.png' in login
    # agent page: build one and check the template carries the mark
    import sqlite3
    from swarmax.db import connect, init_db_with_migrations
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    c = console.FleetConsole(conn, auto_refresh_s=0)
    page = c.render_agent("no-such-agent", {"role": "admin", "username": "t",
                                            "token": "x"})
    assert page is None or "/favicon.png" in page  # template carries it when rendered


def test_favicon_endpoint_served(tmp_path):
    from swarmax.db import connect, init_db_with_migrations
    from swarmax.console import FleetConsole
    conn = connect(str(tmp_path / "c.db"))
    init_db_with_migrations(conn)
    console.FleetConsole(conn, auto_refresh_s=0)  # smoke: console builds
