"""test_auth_tenant_dallar.py — 2-fonksiyon dal-kesen test suite.

ORTAM-ANATOMI (swarmax/auth.py):
  _lock_key(conn, username)      -> (id(conn), username)            (L44)
  _tenant_for_email(conn, email) -> email-domain -> tenant_id       (L208)
      domain = email.rsplit("@",1)[1].lower()
      SELECT tenant_id FROM tenants WHERE sso_domain=domain -> row ise onu
      yoksa "default"

ORTAM-OGRENDILER:
  (1) _lock_key birinci elemani id(conn) — nesne-kimligi; ayni conn+username
      her zaman AYNI tuple (dict-key olarak kullanilabilir, hashable).
  (2) _tenant_for_email: None / "" / "@"-yok / eslesmeyen-domain -> "default";
      domain .lower() ile KUCUK-HARFE cevrilir (BUYUK-harfli email eslesir);
      SUBDOMAIN eslesMEZ (rsplit sadece SON bileşeni alir — sub.acme.com !=
      acme.com); coklu "@"-li emailde son bilesen kullanilir; bosluk-strip
      YOK ( "@ acme.com" eslesmez).
  (3) tenants tablosu (migration 006): tenant_id PK, sso_domain VARCHAR(256).

Kural-1: SADECE yeni test dosyasi; production DOKUNULMADI. Kural-4: saf
in-memory sqlite (network/subprocess YASAK). --noconftest ZORUNLU.
"""
import sqlite3
import sys

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import auth  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


@pytest.fixture()
def db_with_domains(db):
    db.execute("INSERT INTO tenants(tenant_id, display_name, sso_domain)"
               " VALUES ('acme','Acme','acme.com'),"
               " ('lower','Lower','example.org'),"
               " ('tr','Turkce','ornek.com')")
    db.commit()
    return db


# ========================================================== _lock_key =======
def test_lock_key_returns_tuple(db):
    k = auth._lock_key(db, "user1")
    assert isinstance(k, tuple)
    assert len(k) == 2


def test_lock_key_first_element_is_conn_id(db):
    # SW-AUTH-1 fix-sonrasi: sid uuid4 hex (db.connect atar), id(conn) DEGIL
    k = auth._lock_key(db, "user1")
    assert k[0] == db._swarmax_sid
    assert isinstance(k[0], str) and len(k[0]) == 32


def test_lock_key_second_element_is_username(db):
    assert auth._lock_key(db, "user1")[1] == "user1"


@pytest.mark.parametrize("username", [
    "user1", "root", "", "admin@acme.com", "Türkçe-Kullanıcı",
    "user-with-dash", "user.with.dot", "x" * 200, "UPPER", "  spaced  ",
])
def test_lock_key_username_verbatim(db, username):
    assert auth._lock_key(db, username)[1] == username


def test_lock_key_stable_for_same_inputs(db):
    assert auth._lock_key(db, "user1") == auth._lock_key(db, "user1")


def test_lock_key_hashable_and_usable_as_dict_key(db):
    k1 = auth._lock_key(db, "user1")
    k2 = auth._lock_key(db, "user1")
    d = {k1: "v"}
    assert d[k2] == "v"
    assert hash(k1) == hash(k2)


@pytest.mark.parametrize("u1,u2", [("user1", "user2"), ("a", "b"), ("root", "admin")])
def test_lock_key_differs_by_username(db, u1, u2):
    assert auth._lock_key(db, u1) != auth._lock_key(db, u2)


def test_lock_key_differs_by_connection():
    c1 = connect(":memory:")
    c2 = connect(":memory:")
    try:
        assert auth._lock_key(c1, "user1") != auth._lock_key(c2, "user1")
    finally:
        c1.close()
        c2.close()


def test_lock_key_conn_id_changes_after_close_reopen():
    c1 = connect(":memory:")
    k1 = auth._lock_key(c1, "user1")
    c1.close()
    c2 = connect(":memory:")
    k2 = auth._lock_key(c2, "user1")
    try:
        assert k1 != k2  # yeni nesne -> yeni id
        assert k1[1] == k2[1] == "user1"
    finally:
        c2.close()


def test_lock_key_matches_failed_attempts_dict_usage(db):
    # _failed ve _attempts map'leri ayni key-formatini kullanir
    # SW-AUTH-1 fix-sonrasi: key[0] store-sid (str uuid4 hex)
    k = auth._lock_key(db, "user1")
    assert isinstance(k[0], str) and isinstance(k[1], str)


def test_lock_key_with_closed_conn_keeps_sid():
    conn = connect(":memory:")
    sid = conn._swarmax_sid
    conn.close()
    k = auth._lock_key(conn, "user1")
    # close sonrasi nesne yasar; sid hala ulasilabilir (foreign-degil, bizim)
    assert k[0] == sid
    assert isinstance(k[0], str)


# ==================================================== _tenant_for_email =====
@pytest.mark.parametrize("email", [None, "", "plainuser", "notanemail",
                                   "a@", "@", "a@@acme.com"])
def test_tenant_for_email_defaults(db, email):
    assert auth._tenant_for_email(db, email) == "default"


def test_tenant_for_email_returns_str(db):
    assert isinstance(auth._tenant_for_email(db, None), str)


@pytest.mark.parametrize("email,expected", [
    ("x@acme.com", "acme"),
    ("user@acme.com", "acme"),
    ("a.b.c@acme.com", "acme"),
])
def test_tenant_for_email_matches_domain(db_with_domains, email, expected):
    assert auth._tenant_for_email(db_with_domains, email) == expected


@pytest.mark.parametrize("email", ["x@ACME.COM", "x@Acme.Com", "X@ACME.COM"])
def test_tenant_for_email_domain_case_insensitive(db_with_domains, email):
    # .lower() uygulanir
    assert auth._tenant_for_email(db_with_domains, email) == "acme"


@pytest.mark.parametrize("email", [
    "x@sub.acme.com", "x@acme.com.tr", "x@notacme.com", "x@acme", "x@acme.comx",
])
def test_tenant_for_email_subdomain_does_not_match(db_with_domains, email):
    # QUIRK: sadece TAM domain eslesir; subdomain/suffix eslesmez
    assert auth._tenant_for_email(db_with_domains, email) == "default"


@pytest.mark.parametrize("email,expected", [
    ("a@b@acme.com", "acme"),       # rsplit -> son bilesen
    ("@@acme.com", "acme"),
    ("a@b@sub.acme.com", "default"),
])
def test_tenant_for_email_multiple_at_uses_last(db_with_domains, email, expected):
    assert auth._tenant_for_email(db_with_domains, email) == expected


@pytest.mark.parametrize("email", ["x@ acme.com", "x@acme.com "])
def test_tenant_for_email_no_whitespace_strip(db_with_domains, email):
    # QUIRK: domain tarafinda strip YOK — bosluk iceren domain eslesmez
    # (local-part'taki bosluk domain'i etkilemez: ' x@acme.com' -> 'acme')
    assert auth._tenant_for_email(db_with_domains, email) == "default"


@pytest.mark.parametrize("email", [" x@acme.com", "x @acme.com"])
def test_tenant_for_email_localpart_whitespace_ignored(db_with_domains, email):
    # local-part bosluklari domain cikarimini etkilemez
    assert auth._tenant_for_email(db_with_domains, email) == "acme"


@pytest.mark.parametrize("email", ["x@ORNEK.COM", "x@ornek.com", "x@Ornek.Com"])
def test_tenant_for_email_unicode_domain(db_with_domains, email):
    assert auth._tenant_for_email(db_with_domains, email) == "tr"


def test_tenant_for_email_unmatched_existing_tenants(db):
    # seed tenants (default/alpha/beta) sso_domain=NULL -> hicbir email eslesmez
    for email in ["x@default", "x@alpha", "x@beta", "x@default.com"]:
        assert auth._tenant_for_email(db, email) == "default"


def test_tenant_for_email_domain_with_port(db_with_domains):
    # "x@acme.com:8080" -> domain "acme.com:8080" -> eslesmez
    assert auth._tenant_for_email(db_with_domains, "x@acme.com:8080") == "default"


def test_tenant_for_email_pure_localpart_only(db_with_domains):
    assert auth._tenant_for_email(db_with_domains, "localpart") == "default"


def test_tenant_for_email_empty_domain_after_at(db_with_domains):
    assert auth._tenant_for_email(db_with_domains, "user@") == "default"


def test_tenant_for_email_email_is_not_str(db_with_domains):
    # QUIRK: int email -> `"@" in 1234` TypeError (str-olmayan giriste hata)
    with pytest.raises(TypeError):
        auth._tenant_for_email(db_with_domains, 1234)


def test_tenant_for_email_matches_after_new_tenant_inserted(db):
    assert auth._tenant_for_email(db, "x@newco.com") == "default"
    db.execute("INSERT INTO tenants(tenant_id, display_name, sso_domain)"
               " VALUES ('newco','NewCo','newco.com')")
    db.commit()
    assert auth._tenant_for_email(db, "x@newco.com") == "newco"


def test_tenant_for_email_second_domain_for_existing_tenant(db_with_domains):
    # ayni tenant_id ikinci kez eklenemez (PK) — yeni tenant_id ile ikinci domain
    db_with_domains.execute(
        "INSERT INTO tenants(tenant_id, display_name, sso_domain)"
        " VALUES ('acme2','Acme Too','acme.io')")
    db_with_domains.commit()
    assert auth._tenant_for_email(db_with_domains, "x@acme.io") == "acme2"
    assert auth._tenant_for_email(db_with_domains, "x@acme.com") == "acme"


def test_tenant_for_email_sql_injection_safe(db):
    malicious = "x@acme.com' OR '1'='1"
    assert auth._tenant_for_email(db, malicious) == "default"  # parametreize sorgu
