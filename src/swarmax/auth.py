"""Console authentication — §8 L2 two-person ops model.

Design (per OWASP ASVS 4.0.3 §2.4 / §3.5 and NIST SP 800-63B):
  - scrypt (N=2^14, r=8, p=1) password hashing with per-user random salt
  - 256-bit session tokens; only SHA-256(token) is stored server-side
  - constant-time comparisons everywhere (hmac.compare_digest)
  - per-session CSRF token; all state-changing POSTs require it
  - 12h session expiry; failed attempts lock the account for 15 minutes
  - roles: 'admin' (resolve/seal/user management) vs 'viewer' (read-only)
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from .evidence import append_evidence

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
SESSION_HOURS = 12
LOCKOUT_MINUTES = 15
MAX_FAILED_ATTEMPTS = 5

# In-process lockout state. A store is identified by `_swarmax_sid`, a
# process-unique id attached to the connection by swarmax.db.connect that
# dies with the object. id(conn) is deliberately NOT used: after a connection
# is garbage-collected Python may hand its address to a brand-new connection,
# letting one store inherit another store's lockout — the store-scoping this
# state exists to guarantee (reset by admin action or expiry).
_failed: dict[tuple[str, str], tuple[int, datetime]] = {}


def _lock_key(conn: sqlite3.Connection, username: str) -> tuple[str, str]:
    """Store-scoped lockout key, stable for the connection's lifetime."""
    sid = getattr(conn, "_swarmax_sid", None)
    if sid is None:
        sid = f"conn:{id(conn)}"  # foreign connection: still stable while alive
    return (sid, username)


def _lock_key(conn: sqlite3.Connection, username: str) -> tuple[int, str]:
    return (id(conn), username)


def reset_lockout(conn: sqlite3.Connection, username: str) -> None:
    """Admin utility: clear failed-attempt state for one user."""
    _failed.pop(_lock_key(conn, username), None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(),
                            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32).hex()
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(password.encode(), salt=salt.encode(),
                                   n=int(n), r=int(r), p=int(p), dklen=32).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def bootstrap_admin(conn: sqlite3.Connection, username: str, password: str) -> str:
    """Create the first admin if no user exists; returns the user_id."""
    row = conn.execute("SELECT COUNT(*) c FROM console_users").fetchone()
    if row["c"]:
        existing = conn.execute(
            "SELECT user_id FROM console_users WHERE username=?", (username,)).fetchone()
        if existing:
            return existing["user_id"]
        raise RuntimeError("admin already exists; use add_user")
    uid = f"usr_{secrets.token_hex(8)}"
    conn.execute(
        "INSERT INTO console_users (user_id, username, pw_hash, role)"
        " VALUES (?, ?, ?, 'admin')", (uid, username, hash_password(password)))
    conn.commit()
    return uid


def add_user(conn: sqlite3.Connection, username: str, password: str, role: str,
             actor: str) -> str:
    """Admin-only user creation; the action is sealed into the evidence ledger."""
    if role not in ("admin", "viewer"):
        raise ValueError("role must be admin|viewer")
    if len(password) < 12:
        raise ValueError("password must be >= 12 chars (NIST 800-63B)")
    uid = f"usr_{secrets.token_hex(8)}"
    conn.execute(
        "INSERT INTO console_users (user_id, username, pw_hash, role)"
        " VALUES (?, ?, ?, ?)", (uid, username, hash_password(password), role))
    from .evidence import append_evidence
    append_evidence(conn, "user_created", {
        "username": username, "role": role, "created_by": actor,
        "ts": _utcnow().isoformat(sep=" ")})
    conn.commit()
    return uid


def login(conn: sqlite3.Connection, username: str, password: str) -> dict | None:
    """Verify credentials and create a session. Returns
    {token, csrf_token, role, username} or None on failure."""
    key = _lock_key(conn, username)
    state = _failed.get(key, (0, _utcnow()))
    if state[0] >= MAX_FAILED_ATTEMPTS and _utcnow() < state[1]:
        return None  # locked
    row = conn.execute(
        "SELECT user_id, pw_hash, role FROM console_users WHERE username=?",
        (username,)).fetchone()
    if row is None or not verify_password(password, row["pw_hash"]):
        n = state[0] + 1 if _utcnow() < state[1] else 1
        _failed[key] = (n, _utcnow() + timedelta(minutes=LOCKOUT_MINUTES))
        return None
    _failed.pop(key, None)
    return create_session(conn, username, row["role"])


def create_session(conn: sqlite3.Connection, username: str, role: str) -> dict:
    """Mint a session for an already-authenticated identity (local password
    login or a verified SSO id_token — callers choose the trust root).

    SSO identities get a console_users row on first sight (empty pw_hash: no
    password login possible) so the sessions FK stays meaningful."""
    row = conn.execute("SELECT user_id FROM console_users WHERE username=?",
                       (username,)).fetchone()
    if row is None:
        user_id = "sso-" + hashlib.sha256(username.encode()).hexdigest()[:12]
        conn.execute(
            "INSERT INTO console_users (user_id, username, pw_hash, role)"
            " VALUES (?, ?, '', ?)", (user_id, username, role))
        conn.commit()
    else:
        user_id = row["user_id"]
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = _utcnow()
    conn.execute(
        "INSERT INTO console_sessions (token_hash, user_id, csrf_token,"
        " created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf,
         now.isoformat(sep=" "),
         (now + timedelta(hours=SESSION_HOURS)).isoformat(sep=" ")))
    conn.commit()
    return {"token": token, "csrf_token": csrf, "role": role,
            "username": username}


# ------------------------------------------------------------------- SSO
SSO_AUTOJOIN_ENV = "SWARMAX_SSO_AUTOJOIN"


def sso_login(conn: sqlite3.Connection, issuer: str, subject: str,
              email: str | None, *, autojoin: bool | None = None) -> dict | None:
    """Session for a verified SSO identity (issuer+subject already validated).

    Resolution order: existing link (its role+tenant win) → auto-provision
    'viewer' into the tenant mapped from the email domain (§8 multi-team;
    unknown domain → 'default') when SWARMAX_SSO_AUTOJOIN=1 → reject
    (fail closed). The login event is sealed into the evidence ledger either way.
    """
    if autojoin is None:
        import os
        autojoin = os.environ.get(SSO_AUTOJOIN_ENV) == "1"
    row = conn.execute(
        "SELECT username, role, tenant_id FROM sso_links WHERE issuer=? AND subject=?",
        (issuer, subject)).fetchone()
    if row is not None:
        username, role, tenant = row["username"], row["role"], row["tenant_id"]
    elif autojoin:
        username = (email or f"sso-{subject[:12]}").split("@")[0][:64]
        base, suffix = username, 1
        while conn.execute("SELECT 1 FROM sso_links WHERE username=?",
                           (username,)).fetchone():
            suffix += 1
            username = f"{base}-{suffix}"
        tenant = _tenant_for_email(conn, email)
        conn.execute(
            "INSERT INTO sso_links (issuer, subject, username, role, email, tenant_id)"
            " VALUES (?, ?, ?, 'viewer', ?, ?)",
            (issuer, subject, username, email, tenant))
        role = "viewer"
    else:
        append_evidence(conn, "sso_login_rejected", {
            "issuer": issuer, "subject": subject, "ts": _utcnow().isoformat(sep=" ")})
        conn.commit()
        return None
    append_evidence(conn, "sso_login", {
        "issuer": issuer, "subject": subject, "username": username,
        "role": role, "tenant": tenant, "ts": _utcnow().isoformat(sep=" ")})
    conn.commit()
    session = create_session(conn, username, role)
    session["tenant_id"] = tenant
    return session


def _tenant_for_email(conn: sqlite3.Connection, email: str | None) -> str:
    """Email-domain → tenant mapping (§8); falls back to 'default'."""
    if email and "@" in email:
        domain = email.rsplit("@", 1)[1].lower()
        row = conn.execute("SELECT tenant_id FROM tenants WHERE sso_domain=?",
                           (domain,)).fetchone()
        if row:
            return row["tenant_id"]
    return "default"


def link_sso(conn: sqlite3.Connection, issuer: str, subject: str, username: str,
             role: str, actor: str) -> None:
    """Admin action: map an (issuer, subject) pair onto a console identity."""
    if role not in ("admin", "viewer"):
        raise ValueError(f"bad role: {role}")
    conn.execute(
        "INSERT INTO sso_links (issuer, subject, username, role)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT(issuer, subject) DO UPDATE SET username=excluded.username,"
        " role=excluded.role", (issuer, subject, username, role))
    append_evidence(conn, "sso_link_created", {
        "issuer": issuer, "subject": subject, "username": username,
        "role": role, "actor": actor, "ts": _utcnow().isoformat(sep=" ")})
    conn.commit()


def authenticate(conn: sqlite3.Connection, token: str | None) -> dict | None:
    """Resolve a bearer token to an active session. Expired sessions are purged."""
    if not token:
        return None
    conn.execute("DELETE FROM console_sessions WHERE expires_at < ?",
                 (_utcnow().isoformat(sep=" "),))
    row = conn.execute(
        "SELECT s.csrf_token, s.user_id, s.expires_at, u.username, u.role"
        " FROM console_sessions s JOIN console_users u USING (user_id)"
        " WHERE s.token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if row is None:
        return None
    return {"csrf_token": row["csrf_token"], "user_id": row["user_id"],
            "username": row["username"], "role": row["role"]}


def logout(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM console_sessions WHERE token_hash=?",
                     (hashlib.sha256(token.encode()).hexdigest(),))
        conn.commit()


def check_csrf(session: dict | None, supplied: str | None) -> bool:
    return bool(session) and bool(supplied) and hmac.compare_digest(
        session["csrf_token"], supplied)  # type: ignore[index]
