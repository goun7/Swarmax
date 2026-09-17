"""Console auth (§8): scrypt hashes, sessions, CSRF, lockout, roles."""
import hashlib

import pytest

from swarmax import auth
from swarmax.db import connect, init_db_with_migrations


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    auth.bootstrap_admin(conn, "root", "correct horse battery staple")
    auth.add_user(conn, "viewer1", "viewer-passphrase-123", "viewer", actor="root")
    return conn


def test_password_hash_shape_and_verify(db):
    row = db.execute(
        "SELECT pw_hash FROM console_users WHERE username='root'").fetchone()
    parts = row["pw_hash"].split("$")
    assert parts[0] == "scrypt" and parts[1] == str(auth.SCRYPT_N)
    assert auth.verify_password("correct horse battery staple", row["pw_hash"])
    assert not auth.verify_password("wrong", row["pw_hash"])
    # every hash has a unique salt
    row2 = db.execute(
        "SELECT pw_hash FROM console_users WHERE username='viewer1'").fetchone()
    assert row["pw_hash"] != row2["pw_hash"]


def test_login_session_and_logout(db):
    sess = auth.login(db, "root", "correct horse battery staple")
    assert sess and sess["role"] == "admin"
    resolved = auth.authenticate(db, sess["token"])
    assert resolved and resolved["username"] == "root"
    # token never stored raw
    h = hashlib.sha256(sess["token"].encode()).hexdigest()
    assert db.execute(
        "SELECT 1 FROM console_sessions WHERE token_hash=?", (h,)).fetchone()
    auth.logout(db, sess["token"])
    assert auth.authenticate(db, sess["token"]) is None


def test_bad_password_and_lockout(db):
    assert auth.login(db, "root", "nope") is None
    for _ in range(auth.MAX_FAILED_ATTEMPTS - 1):
        assert auth.login(db, "root", "nope") is None
    assert auth.login(db, "root", "correct horse battery staple") is None  # locked
    # a different user is unaffected
    assert auth.login(db, "viewer1", "viewer-passphrase-123") is not None


def test_csrf_check(db):
    sess = auth.login(db, "root", "correct horse battery staple")
    assert auth.check_csrf(sess, sess["csrf_token"])
    assert not auth.check_csrf(sess, "forged")
    assert not auth.check_csrf(None, sess["csrf_token"])
    assert not auth.check_csrf(sess, None)


def test_session_expiry(db):
    sess = auth.login(db, "root", "correct horse battery staple")
    db.execute("UPDATE console_sessions SET expires_at='2000-01-01 00:00:00'")
    db.commit()
    assert auth.authenticate(db, sess["token"]) is None


def test_password_minimum_length(db):
    with pytest.raises(ValueError):
        auth.add_user(db, "shorty", "short", "viewer", actor="root")
