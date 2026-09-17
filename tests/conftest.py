"""Shared test fixtures."""
import os
import sys

# make `import swarmax` work from a source checkout (src/ layout)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "src"))

import pytest

import swarmax.console as console_mod


@pytest.fixture()
def serve_http():
    """Factory: serve_http(conn) -> FleetConsole with a live HTTP server."""
    def _serve(conn):
        console = console_mod.FleetConsole(conn)
        srv = console.serve(port=0)
        import threading
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return console
    return _serve
