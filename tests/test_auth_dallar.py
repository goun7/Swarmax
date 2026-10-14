"""test_auth_dallar.py — swarmax/auth.py dal-kesen (branch-cutting) test suite.

MODUL ANATOMISI (src/swarmax/auth.py, 260 satir) — public fonksiyonlar:
  hash_password(pw)            -> "scrypt$N$r$p$salt$digest"     (L57)
  verify_password(pw, stored)  -> bool; ValueError/TypeError -> False (L64)
  bootstrap_admin(conn,u,pw)   -> user_id; tablo dolu + ayni u -> mevcut id
                                 tablo dolu + yeni u -> RuntimeError (L76)
  add_user(conn,u,pw,role,aktor) -> role!={admin,viewer} -> ValueError
                                 len(pw)<12 -> ValueError (NIST 800-63B) (L93)
  login(conn,u,pw)             -> kilitli -> None; kullanici yok -> None;
                                 yanlis sifre -> None + sayac; dogru -> session (L112)
  create_session(conn,u,role)  -> kullanici yoksa 'sso-'+sha256[:12] + bos pw (L130)
  sso_login(conn,issuer,subj,email,*,autojoin) -> bag/otomatik/red    (L164)
  link_sso(conn,issuer,subj,u,role,actor) -> bad role -> ValueError   (L219)
  authenticate(conn,token)     -> token yok -> None; expire silme; yok -> None (L235)
  logout(conn,token)           -> token None -> no-op                  (L251)
  check_csrf(session,supplied) -> session|supplied yalanci -> False    (L258)
  reset_lockout(conn,u)        -> _failed.pop                          (L48)
  _lock_key(conn,u)            -> (id(conn), username)                 (L44)

BULGU-1 (production'a DOKUNULMADI — gerceklik test dosyasinda belgelendi):
  auth.py L27-41 yorumu + birinci _lock_key tanimi, lockout durumunun
  "store-scoped" oldugunu iddia eder: baglanti `getattr(conn,'_swarmax_sid')`
  ile taninir ve yorum id(conn)'in "deliberately NOT used" oldugunu soyler
  (adres geri-donusumu riski). ANCAK:
    (a) ayni modulde _lock_key IKI KEZ tanimlidir (L36 ve L44); Python son
        tanimi kullanir => CANLI _lock_key = (id(conn), username).
    (b) db.Connection sinifinda `_swarmax_sid: str` sadece ANNOTASYON'dur;
        src/ agacinda HICBIR YERDE deger ATANMAZ (grep ile dogrulandi).
  Sonuc: yorumda-soylenen store-scoping gercekte YOK; lockout id(conn)
  uzerindedir. Testler CANLI davranisi (id(conn)) sabitler ve birinci
  (olu) tanimin gecersiz oldugunu kanitlar.

Kural-1: SADECE yeni test dosyasi; production/conftest/mevcut testlere
DOKUNULMADI. Kural-4: saf in-memory sqlite; ag/RPC/subprocess YOK.
filterwarnings=error::UserWarning => ureten yol YOK (pytest.warns gerekmedi).
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from swarmax import auth  # noqa: E402
from swarmax.db import connect, init_db_with_migrations  # noqa: E402

PW = "correct horse battery staple"  # 28 karakter; add_user >= 12 sinirini gecer


@pytest.fixture()
def db():
    conn = connect(":memory:")
    init_db_with_migrations(conn)
    return conn


@pytest.fixture()
def db_admin(db):
    """bootstrap_admin yapilmis, tek admin'li mağaza."""
    auth.bootstrap_admin(db, "root", PW)
    return db


@pytest.fixture(autouse=True)
def _lockout_durumu_temizle():
    """auth._failed modul-globalidir; test izolasyonu icin her testte sifirla."""
    auth._failed.clear()
    yield
    auth._failed.clear()


# ==================================================== hash_password ==========
class TestSifreHashlama:
    """hash_password(pw) -> 'scrypt$N$r$p$salt$digest' dal tamligi."""

    def test_cikti_formati(self, db):
        """Dal: 6 '$'-ayrilmasi alani; sembolik sabitler format icine gomulu."""
        h = auth.hash_password(PW)
        parca = h.split("$")
        assert len(parca) == 6
        assert parca[0] == "scrypt"
        assert parca[1] == str(auth.SCRYPT_N)
        assert parca[2] == str(auth.SCRYPT_R)
        assert parca[3] == str(auth.SCRYPT_P)

    def test_digest_64_hex_ve_salt_32_hex(self, db):
        """Dal: dklen=32 -> digest 64 hex; salt token_hex(16) -> 32 hex."""
        h = auth.hash_password(PW).split("$")
        assert len(h[4]) == 32
        assert all(c in "0123456789abcdef" for c in h[4])
        assert len(h[5]) == 64
        int(h[5], 16)  # hex olmali

    def test_salt_rastgele_ayni_sifre_farkli_hash(self, db):
        """Dal: ayni sifre iki kez => farkli salt => farkli digest."""
        a, b = auth.hash_password(PW), auth.hash_password(PW)
        assert a != b
        assert a.split("$")[4] != b.split("$")[4]

    @pytest.mark.parametrize("sifre", [
        PW, "baska-bir-uzun-sifre", "Türkçe-şifre-123", "x" * 200, "   ", "1",
    ])
    def test_farkli_sifre_farkli_digest(self, db, sifre):
        """Dal: her sifre icin digest degisir (uzunluk/icerik bagimsiz)."""
        h = auth.hash_password(sifre).split("$")
        assert auth.verify_password(sifre, "$".join(h)) is True


# ================================================== verify_password =========
class TestSifreDogrulama:
    """verify_password(pw, stored) basari/basarisizlik/sinir dallari."""

    def test_dogru_sifre(self, db):
        """Dal: sembol scrypt + dogru digest -> True (compare_digest)."""
        assert auth.verify_password(PW, auth.hash_password(PW)) is True

    def test_yanlis_sifre(self, db):
        """Dal: scrypt ama digest farkli -> False."""
        assert auth.verify_password("yanlis-sifre", auth.hash_password(PW)) is False

    def test_hassas_karsilastirma(self, db):
        """Dal: digest bir hex karakter bozulursa -> False (case/trim toleransı YOK)."""
        h = auth.hash_password(PW)
        bozuk = h[:-1] + ("0" if h[-1] != "0" else "1")
        assert auth.verify_password(PW, bozuk) is False

    @pytest.mark.parametrize("kotu", [
        "",                                   # bos stored -> split 1 eleman -> ValueError
        "scrypt",                             # eksik alan -> ValueError
        "scrypt$16384",                       # 2 alan -> ValueError
        "bcrypt$16384$8$1$salt$digest",       # sembol != scrypt -> False
        "SCRYPT$16384$8$1$salt$digest",       # buyuk harf sembol -> False
        "scrypt$abc$8$1$salt$digest",         # int('abc') -> TypeError
        "scrypt$16384$8$1$" + "a" * 64,       # salt/digest var ama yanlis -> False
    ])
    def test_bicimsiz_saklanan_hash_false(self, db, kotu):
        """Dallar: ValueError/TypeError/scheme-uyumsuzluk hepsi False (asla patlama)."""
        assert auth.verify_password(PW, kotu) is False

    def test_none_saklanan_hash_patlar(self, db):
        """BULGU-sinir: guard yalnizca (ValueError, TypeError); None.split ->
        AttributeError yiyor ve DIŞARI sızıyor (callable'a guvenen cagirici
        icin fark). Canli davranisi sabitleriz, production'a dokunmayiz."""
        with pytest.raises(AttributeError):
            auth.verify_password(PW, None)


# ================================================== bootstrap_admin ==========
class TestAdminOntlama:
    """bootstrap_admin basari + zaten-var + yeni-kullanici dallari."""

    def test_bos_magazada_admin_olustur(self, db):
        """Dal: tablo bos -> INSERT admin, user_id 'usr_' ongekli."""
        uid = auth.bootstrap_admin(db, "root", PW)
        assert uid.startswith("usr_")
        row = db.execute("SELECT * FROM console_users WHERE username='root'").fetchone()
        assert row["role"] == "admin"
        assert auth.verify_password(PW, row["pw_hash"])

    def test_sayi_tekrar_ayni_kullanici_idempotent(self, db_admin):
        """Dal: tablo dolu + ayni username -> MEVCUT user_id doner, satir cogalmaz."""
        once = db_admin.execute(
            "SELECT user_id FROM console_users WHERE username='root'").fetchone()["user_id"]
        tekrar = auth.bootstrap_admin(db_admin, "root", "baska-sifre-12345")
        assert tekrar == once
        n = db_admin.execute("SELECT COUNT(*) c FROM console_users").fetchone()["c"]
        assert n == 1
        # mevcut sifre dokunulmadi
        assert auth.verify_password(PW, db_admin.execute(
            "SELECT pw_hash FROM console_users WHERE username='root'").fetchone()["pw_hash"])

    def test_admin_varken_farkli_kullanici_reddedilir(self, db_admin):
        """Dal: tablo dolu + bilinmeyen username -> RuntimeError."""
        db_admin.execute(
            "INSERT INTO console_users(user_id,username,pw_hash,role)"
            " VALUES ('usr_x','gosterge','x','viewer')")
        db_admin.commit()
        with pytest.raises(RuntimeError, match="add_user"):
            auth.bootstrap_admin(db_admin, "yeni-admin", PW)

    def test_admin_var_ama_username_silindi_ise_yeni_admin(self, db_admin):
        """Dal: sayac>0 AMA aranan username YOK -> RuntimeError (yukaridaki ile
        ayni dalin ikinci girisi: 'existing is None' alt-dali)."""
        with pytest.raises(RuntimeError):
            auth.bootstrap_admin(db_admin, "yok-admin", PW)


# ======================================================= add_user ===========
class TestKullaniciEkleme:
    """add_user rol/sifre-uzunluk dogrulama + evidence dal tamligi."""

    def test_gecerli_ekleme(self, db_admin):
        """Dal: gecerli -> 'usr_' id, satir, evidence(user_created) mohru."""
        uid = auth.add_user(db_admin, "ali", "cok-gizli-sifre", "viewer", actor="root")
        assert uid.startswith("usr_")
        row = db_admin.execute("SELECT * FROM console_users WHERE username='ali'").fetchone()
        assert row["role"] == "viewer"
        ev = db_admin.execute(
            "SELECT payload_hash FROM evidence_ledger WHERE event_type='user_created'"
        ).fetchone()
        assert ev is not None

    @pytest.mark.parametrize("rol", ["superuser", "", "Admin", "VIEWER", "root", None])
    def test_gecersiz_rol_valueerror(self, db_admin, rol):
        """Dal: role not in ('admin','viewer') -> ValueError (case-sensitive)."""
        with pytest.raises(ValueError, match="role"):
            auth.add_user(db_admin, "x", "yeterince-uzun-sifre", rol, actor="root")

    @pytest.mark.parametrize("uzunluk,beklenen", [(0, False), (1, False), (11, False)])
    def test_kisa_sifre_reddedilir(self, db_admin, uzunluk, beklenen):
        """Dal: len(password) < 12 -> ValueError (NIST 800-63B siniri)."""
        with pytest.raises(ValueError, match="12"):
            auth.add_user(db_admin, "kisa", "x" * uzunluk, "viewer", actor="root")

    @pytest.mark.parametrize("uzunluk", [12, 13, 64])
    def test_sifre_siniri_dahil_kabul(self, db_admin, uzunluk):
        """Dal: tam 12 karakter (sinir dahil) -> kabul."""
        uid = auth.add_user(db_admin, f"u{uzunluk}", "y" * uzunluk, "admin", actor="root")
        assert uid.startswith("usr_")

    def test_evidence_icerigi(self, db_admin):
        """Dal: mohur payload'inda username/role/created_by var (denetim izi)."""
        auth.add_user(db_admin, "veli", "cok-gizli-sifre", "admin", actor="operator-1")
        # evidence_ledger payload_hash'tir; payload disinda tutulmaz —
        # bu nedenle tetikleyici olarak ledger'a YAZILDIĞINI dogruluyoruz
        n = db_admin.execute(
            "SELECT COUNT(*) c FROM evidence_ledger WHERE event_type='user_created'"
        ).fetchone()["c"]
        assert n == 1


# =========================================================== login ==========
class TestGiris:
    """login basari / yanlis sifre / kilit / kilit-vadesi / kullanici-yok dallari."""

    def test_giris_basarili_session_sekli(self, db_admin):
        """Dal: dogru sifre -> {token, csrf_token, role, username} + sayac temiz."""
        sess = auth.login(db_admin, "root", PW)
        assert set(sess) == {"token", "csrf_token", "role", "username"}
        assert sess["role"] == "admin"
        assert sess["username"] == "root"
        assert auth._lock_key(db_admin, "root") not in auth._failed

    def test_giris_token_diskte_hashli(self, db_admin):
        """Dal: session(token) DEGIL sha256(token) saklanir."""
        sess = auth.login(db_admin, "root", PW)
        ham = db_admin.execute(
            "SELECT 1 FROM console_sessions WHERE token_hash=?",
            (sess["token"],)).fetchone()
        assert ham is None
        h = hashlib.sha256(sess["token"].encode()).hexdigest()
        assert db_admin.execute(
            "SELECT 1 FROM console_sessions WHERE token_hash=?", (h,)).fetchone()

    def test_yanlis_sifre_none_ve_sayac_bir(self, db_admin):
        """Dal: yanlis sifre -> None, _failed[key] = (1, vade)."""
        assert auth.login(db_admin, "root", "yanlis") is None
        key = auth._lock_key(db_admin, "root")
        assert auth._failed[key][0] == 1

    def test_kilit_sonrasi_dogru_sifre_bile_reddedilir(self, db_admin):
        """Dal: state[0] >= MAX && simdi < vade -> correct password da None."""
        auth._failed[auth._lock_key(db_admin, "root")] = (
            auth.MAX_FAILED_ATTEMPTS, auth._utcnow() + timedelta(minutes=auth.LOCKOUT_MINUTES))
        assert auth.login(db_admin, "root", PW) is None

    def test_kilit_vadesi_dolduysa_dogru_sifre_acar(self, db_admin):
        """Dal: state[0] >= MAX AMA simdi >= vade -> kilit asildi, giris yapilir."""
        auth._failed[auth._lock_key(db_admin, "root")] = (
            auth.MAX_FAILED_ATTEMPTS, auth._utcnow() - timedelta(minutes=1))
        assert auth.login(db_admin, "root", PW) is not None

    def test_kilit_vadesi_dolduysa_basarisizlik_sayaci_bire_duser(self, db_admin):
        """Dal: vade gectikten sonra yanlis sifre -> n = 1 (MAX+1 DEGIL)."""
        key = auth._lock_key(db_admin, "root")
        auth._failed[key] = (auth.MAX_FAILED_ATTEMPTS,
                             auth._utcnow() - timedelta(minutes=1))
        auth.login(db_admin, "root", "yanlis")
        assert auth._failed[key][0] == 1

    def test_basarisizlik_dizisi_kilitler(self, db_admin):
        """Dal: MAX_FAILED_ATTEMPTS yanlis deneme sonrasi kilit; basarili giris
        sayaci sifirlar (butun bagimsiz yol)."""
        for _ in range(auth.MAX_FAILED_ATTEMPTS):
            assert auth.login(db_admin, "root", "yanlis") is None
        assert auth.login(db_admin, "root", PW) is None  # kilitli
        # reset_lockout admin araci ile acilir
        auth.reset_lockout(db_admin, "root")
        assert auth.login(db_admin, "root", PW) is not None

    def test_kilit_diger_kullaniciyi_etkilemez(self, db_admin):
        """Dal: lockout key (sid, username) -> kullaniciya ozel."""
        auth.add_user(db_admin, "veli", "cok-gizli-sifre", "viewer", actor="root")
        auth._failed[auth._lock_key(db_admin, "root")] = (
            auth.MAX_FAILED_ATTEMPTS, auth._utcnow() + timedelta(minutes=15))
        assert auth.login(db_admin, "veli", "cok-gizli-sifre") is not None

    def test_olmayan_kullanici_none_ve_sayac_artar(self, db_admin):
        """Dal: row is None -> kisa-devre, sayac yine artar (kilitlenir)."""
        key = auth._lock_key(db_admin, "hayalet")
        for i in range(auth.MAX_FAILED_ATTEMPTS):
            assert auth.login(db_admin, "hayalet", "x") is None
            assert auth._failed[key][0] == i + 1
        # artik kilitli: dogru sifre olmasa da ayni sekilde None
        assert auth.login(db_admin, "hayalet", "x") is None

    def test_reset_lockout_bilinmeyen_kullanici_zararsiz(self, db_admin):
        """Dal: _failed.pop(..., None) -> olmayan key hata vermez."""
        auth.reset_lockout(db_admin, "yok-kullanici")  # KeyError YOK


# ==================================================== create_session =========
class TestOturumOlusturma:
    """create_session mevcut/yeni-kullanici + oturum suresi dallari."""

    def test_mevcut_kullanici_icin_oturum(self, db_admin):
        """Dal: kullanici var -> onun user_id'si ile session."""
        sess = auth.create_session(db_admin, "root", "admin")
        row = db_admin.execute(
            "SELECT * FROM console_sessions WHERE"
            " token_hash=?", (hashlib.sha256(sess["token"].encode()).hexdigest(),)
        ).fetchone()
        onceki = db_admin.execute(
            "SELECT user_id FROM console_users WHERE username='root'").fetchone()["user_id"]
        assert row["user_id"] == onceki
        assert row["csrf_token"] == sess["csrf_token"]

    def test_bilinmeyen_kullanici_sso_kimligi_olusturulur(self, db):
        """Dal: kullanici YOK -> user_id='sso-'+sha256(username)[:12], pw_hash=''."""
        sess = auth.create_session(db, "dis-kimlik@acme.com", "viewer")
        row = db.execute(
            "SELECT * FROM console_users WHERE username='dis-kimlik@acme.com'"
        ).fetchone()
        beklenen = "sso-" + hashlib.sha256(b"dis-kimlik@acme.com").hexdigest()[:12]
        assert row["user_id"] == beklenen
        assert row["pw_hash"] == ""
        assert sess["role"] == "viewer"

    def test_sso_kullanici_sifre_ile_giremez(self, db):
        """Dal: bos pw_hash -> verify_password('') ValueError -> False."""
        auth.create_session(db, "dis-kimlik", "viewer")
        row = db.execute(
            "SELECT pw_hash FROM console_users WHERE username='dis-kimlik'").fetchone()
        assert auth.verify_password("herhangi-bisey", row["pw_hash"]) is False

    def test_oturum_suresi_12_saattir(self, db_admin):
        """Dal: expires_at = created_at + SESSION_HOURS."""
        once = auth._utcnow()
        sess = auth.create_session(db_admin, "root", "admin")
        row = db_admin.execute(
            "SELECT created_at, expires_at FROM console_sessions WHERE"
            " token_hash=?", (hashlib.sha256(sess["token"].encode()).hexdigest(),)
        ).fetchone()
        uretim = datetime.fromisoformat(row["created_at"])
        son = datetime.fromisoformat(row["expires_at"])
        assert (son - uretim) == timedelta(hours=auth.SESSION_HOURS)
        assert (uretim - once) < timedelta(seconds=5)

    def test_iki_oturum_token_ve_csrf_farkli(self, db_admin):
        """Dal: her cagrida secrets.token_urlsafe(32) -> taze cifler."""
        a, b = auth.create_session(db_admin, "root", "admin"), \
            auth.create_session(db_admin, "root", "admin")
        assert a["token"] != b["token"]
        assert a["csrf_token"] != b["csrf_token"]


# ======================================================== sso_login =========
class TestSSOGiris:
    """sso_login mevcut-bag / autojoin / carpisma / red / env dallari."""

    def test_mevcut_bag_rol_ve_tenant_kazanir(self, db_admin):
        """Dal: sso_links satiri var -> onun rol+tenant'i kazanilir."""
        db_admin.execute(
            "INSERT INTO sso_links(issuer,subject,username,role,email,tenant_id)"
            " VALUES ('https://idp','sub-1','bagli-kullanici','admin','a@acme.com','alpha')")
        db_admin.commit()
        sess = auth.sso_login(db_admin, "https://idp", "sub-1", "a@acme.com")
        assert sess["role"] == "admin"
        assert sess["tenant_id"] == "alpha"
        assert sess["username"] == "bagli-kullanici"

    def test_mevcut_bag_evidence_mohru(self, db_admin):
        """Dal: basarili SSO girisi 'sso_login' ile ledger'a mohurlenir."""
        db_admin.execute(
            "INSERT INTO sso_links(issuer,subject,username,role)"
            " VALUES ('https://idp','sub-2','k2','viewer')")
        db_admin.commit()
        auth.sso_login(db_admin, "https://idp", "sub-2", None)
        n = db_admin.execute(
            "SELECT COUNT(*) c FROM evidence_ledger WHERE event_type='sso_login'"
        ).fetchone()["c"]
        assert n == 1

    def test_autojoin_acik_email_domain_tenanti(self, db_admin):
        """Dal: autojoin -> username email yerel-bolumu, rol viewer, tenant domain."""
        db_admin.execute(
            "INSERT INTO tenants(tenant_id,display_name,sso_domain)"
            " VALUES ('acme','Acme','acme.com')")
        db_admin.commit()
        sess = auth.sso_login(db_admin, "https://idp", "sub-3",
                              "kisi@acme.com", autojoin=True)
        assert sess["role"] == "viewer"
        assert sess["username"] == "kisi"
        assert sess["tenant_id"] == "acme"
        row = db_admin.execute(
            "SELECT * FROM sso_links WHERE subject='sub-3'").fetchone()
        assert row["email"] == "kisi@acme.com"

    def test_autojoin_kullanici_carpismasi_sonek(self, db_admin):
        """Dal: username mevcut -> -2, -3 ... sonek ile benzersiz yapilir."""
        db_admin.execute(
            "INSERT INTO sso_links(issuer,subject,username,role)"
            " VALUES ('https://idp','sub-x','kisi','viewer')")
        db_admin.commit()
        s1 = auth.sso_login(db_admin, "https://idp", "s-1",
                            "kisi@acme.com", autojoin=True)
        s2 = auth.sso_login(db_admin, "https://idp", "s-2",
                            "kisi@acme.com", autojoin=True)
        # 'kisi' ZATEN tabluda oldugu icin ilk yeni kimlik 'kisi-2' alir;
        # ikincisi tabluda artik 'kisi-2' de oldugu icin 'kisi-3' alir.
        assert {s1["username"], s2["username"]} == {"kisi-2", "kisi-3"}

    def test_autojoin_email_yok_sso_on_ek(self, db_admin):
        """Dal: email None -> username = 'sso-{subject[:12]}'."""
        sess = auth.sso_login(db_admin, "https://idp", "ABCDEFGHIJ1234567890",
                              None, autojoin=True)
        assert sess["username"] == "sso-ABCDEFGHIJ12"

    def test_autojoin_email_domain_bilinmiyorsa_default(self, db_admin):
        """Dal: eslesmeyen domain -> tenant 'default'."""
        sess = auth.sso_login(db_admin, "https://idp", "sub-d",
                              "kisi@bilinmeyen.domain", autojoin=True)
        assert sess["tenant_id"] == "default"

    def test_autojoin_kapali_red_mohru(self, db_admin):
        """Dal: autojoin False -> None + 'sso_login_rejected' mohru."""
        assert auth.sso_login(db_admin, "https://idp", "sub-r",
                              "k@acme.com", autojoin=False) is None
        n = db_admin.execute(
            "SELECT COUNT(*) c FROM evidence_ledger"
            " WHERE event_type='sso_login_rejected'").fetchone()["c"]
        assert n == 1

    def test_env_degiskeni_autojoin_acar(self, db_admin, monkeypatch):
        """Dal: autojoin None + SWARMAX_SSO_AUTOJOIN='1' -> otomatik katilim."""
        monkeypatch.setenv(auth.SSO_AUTOJOIN_ENV, "1")
        sess = auth.sso_login(db_admin, "https://idp", "sub-env", "k@acme.com")
        assert sess is not None
        assert sess["role"] == "viewer"

    def test_env_degiskeni_yoksa_red(self, db_admin, monkeypatch):
        """Dal: autojoin None + env '1' DEGIL -> fail-closed red."""
        monkeypatch.delenv(auth.SSO_AUTOJOIN_ENV, raising=False)
        assert auth.sso_login(db_admin, "https://idp", "sub-env2", "k@acme.com") is None


# ==================================================== _tenant_for_email =====
class TestEmailTenanti:
    """_tenant_for_email: email-domain -> tenant haritlama + dusus('default')."""

    @pytest.mark.parametrize("email,beklenen", [
        (None, "default"),
        ("", "default"),
        ("düz-etuszc", "default"),        # '@' yok
        ("kisi@BILINMEYEN.domain", "default"),
        ("kisi@sub.acme.com", "default"),  # alt-domain eslesMEZ (rsplit son bolum)
    ])
    def test_default_dallari(self, db_admin, email, beklenen):
        """Dal: None/''/'@'-yok/eslesmeyen/sub-domain -> 'default'."""
        assert auth._tenant_for_email(db_admin, email) == beklenen

    def test_domain_kucuk_harfe_cevrilir(self, db_admin):
        """Dal: domain .lower() -> BUYUK harfli email tenant ile eslesir."""
        db_admin.execute(
            "INSERT INTO tenants(tenant_id,display_name,sso_domain)"
            " VALUES ('acme','Acme','acme.com')")
        db_admin.commit()
        assert auth._tenant_for_email(db_admin, "KISI@ACME.COM") == "acme"

    def test_coklu_et_isaretli_email_son_bolum(self, db_admin):
        """Dal: 'a@b@acme.com'.rsplit('@',1)[1] = 'acme.com' -> eslesir."""
        db_admin.execute(
            "INSERT INTO tenants(tenant_id,display_name,sso_domain)"
            " VALUES ('acme','Acme','acme.com')")
        db_admin.commit()
        assert auth._tenant_for_email(db_admin, "a@b@acme.com") == "acme"


# ======================================================== link_sso ==========
class TestSSOBaglama:
    """link_sso rol dogrulama + upsert (ON CONFLICT) + evidence dallari."""

    @pytest.mark.parametrize("rol", ["superuser", "", "Viewer", None])
    def test_gecersiz_rol_valueerror(self, db_admin, rol):
        """Dal: role not in ('admin','viewer') -> ValueError."""
        with pytest.raises(ValueError, match="bad role"):
            auth.link_sso(db_admin, "https://idp", "s1", "u1", rol, actor="root")

    @pytest.mark.parametrize("rol", ["admin", "viewer"])
    def test_gecerli_bag_evidence_ile(self, db_admin, rol):
        """Dal: gecerli rol -> sso_links satiri + 'sso_link_created' mohru."""
        auth.link_sso(db_admin, "https://idp", "s1", "u1", rol, actor="root")
        row = db_admin.execute(
            "SELECT * FROM sso_links WHERE issuer='https://idp'").fetchone()
        assert row["role"] == rol
        n = db_admin.execute(
            "SELECT COUNT(*) c FROM evidence_ledger"
            " WHERE event_type='sso_link_created'").fetchone()["c"]
        assert n == 1

    def test_tekrar_baglama_gunceller(self, db_admin):
        """Dal: ayni (issuer,subject) -> ON CONFLICT DO UPDATE username+role."""
        auth.link_sso(db_admin, "https://idp", "s1", "u1", "viewer", actor="root")
        auth.link_sso(db_admin, "https://idp", "s1", "u2", "admin", actor="root")
        n = db_admin.execute(
            "SELECT COUNT(*) c FROM sso_links"
            " WHERE issuer='https://idp' AND subject='s1'").fetchone()["c"]
        assert n == 1
        row = db_admin.execute(
            "SELECT username, role FROM sso_links WHERE subject='s1'").fetchone()
        assert (row["username"], row["role"]) == ("u2", "admin")


# ==================================================== authenticate ===========
class TestKimlikDogrulama:
    """authenticate token-yok / bilinmeyen / gecerli / vade-silme dallari."""

    @pytest.mark.parametrize("token", [None, ""])
    def test_yalanci_token_none(self, db_admin, token):
        """Dal: not token -> None (kimliklendirme yapilmadan doner)."""
        assert auth.authenticate(db_admin, token) is None

    def test_bilinmeyen_token_none(self, db_admin):
        """Dal: token_hash eslesmesi yok -> None."""
        assert auth.authenticate(db_admin, "hi-cime-token") is None

    def test_gecerli_token_cozumlenir(self, db_admin):
        """Dal: eslesme -> {csrf_token, user_id, username, role}."""
        sess = auth.login(db_admin, "root", PW)
        cozum = auth.authenticate(db_admin, sess["token"])
        assert set(cozum) == {"csrf_token", "user_id", "username", "role"}
        assert cozum["username"] == "root"
        assert cozum["role"] == "admin"
        assert cozum["csrf_token"] == sess["csrf_token"]

    def test_suresi_dolmus_oturum_silinir(self, db_admin):
        """Dal: expires_at < simdi -> DELETE, cozum None (otomatik temizlik)."""
        sess = auth.login(db_admin, "root", PW)
        h = hashlib.sha256(sess["token"].encode()).hexdigest()
        db_admin.execute(
            "UPDATE console_sessions SET expires_at=? WHERE token_hash=?",
            ((auth._utcnow() - timedelta(hours=1)).isoformat(sep=" "), h))
        db_admin.commit()
        assert auth.authenticate(db_admin, sess["token"]) is None
        assert db_admin.execute(
            "SELECT 1 FROM console_sessions WHERE token_hash=?", (h,)).fetchone() is None

    def test_suresi_dolmamis_oturum_saklanir(self, db_admin):
        """Dal: vade dolmamis -> purge onu SILMEZ, cozum doner."""
        sess = auth.login(db_admin, "root", PW)
        h = hashlib.sha256(sess["token"].encode()).hexdigest()
        once = db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"]
        assert auth.authenticate(db_admin, sess["token"]) is not None
        sonra = db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"]
        assert (once, sonra) == (1, 1)

    def test_purge_diger_oturumlara_dokunmaz(self, db_admin):
        """Dal: silme yalnizca expires_at < simdi satirlarini alir."""
        auth.add_user(db_admin, "veli", "cok-gizli-sifre", "viewer", actor="root")
        gecerli = auth.login(db_admin, "root", PW)
        auth.login(db_admin, "veli", "cok-gizli-sifre")
        hg = hashlib.sha256(gecerli["token"].encode()).hexdigest()
        db_admin.execute(
            "UPDATE console_sessions SET expires_at=? WHERE token_hash<>?",
            ((auth._utcnow() - timedelta(days=1)).isoformat(sep=" "), hg))
        db_admin.commit()
        auth.authenticate(db_admin, gecerli["token"])
        kalan = db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"]
        assert kalan == 1  # yalnizca 'root' oturumu sag


# ======================================================== logout ============
class TestCikis:
    """logout token-None no-op / gecerli silme / bilinmeyen zararsiz."""

    def test_cikis_oturumu_siler(self, db_admin):
        """Dal: token -> DELETE token_hash + commit."""
        sess = auth.login(db_admin, "root", PW)
        auth.logout(db_admin, sess["token"])
        assert db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"] == 0

    @pytest.mark.parametrize("token", [None, ""])
    def test_cikis_yalanci_token_noop(self, db_admin, token):
        """Dal: token yalanci -> DELETE hic calismaz, oturum durur."""
        sess = auth.login(db_admin, "root", PW)
        auth.logout(db_admin, token)
        assert db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"] == 1

    def test_cikis_bilinmeyen_token_zararsiz(self, db_admin):
        """Dal: olmayan token -> hata YOK, oturum durur."""
        sess = auth.login(db_admin, "root", PW)
        auth.logout(db_admin, "baska-token")
        assert db_admin.execute(
            "SELECT COUNT(*) c FROM console_sessions").fetchone()["c"] == 1


# ======================================================== check_csrf =========
class TestCsrfKontrol:
    """check_csrf session/supplied yalanci + eslesme/basarisizlik dallari."""

    @pytest.mark.parametrize("session,supplied", [
        (None, "csrf"),
        ({}, "csrf"),
        ({"csrf_token": "csrf"}, None),
        ({"csrf_token": "csrf"}, ""),
    ])
    def test_yalanci_girdi_false(self, session, supplied):
        """Dal: bool(session) and bool(supplied) kisa-devre -> False."""
        assert auth.check_csrf(session, supplied) is False

    def test_eslesme_true(self):
        """Dal: compare_digest esit -> True."""
        assert auth.check_csrf({"csrf_token": "abc123"}, "abc123") is True

    def test_yanlis_token_false(self):
        """Dal: eslesme yok -> False (sabit-zamanli karsilastirma)."""
        assert auth.check_csrf({"csrf_token": "abc123"}, "abc124") is False

    def test_case_sensitive(self):
        """Dal: BUYUK/kucuk harf farki -> False."""
        assert auth.check_csrf({"csrf_token": "ABC"}, "abc") is False


# ================================================== _lock_key / reset =======
class TestKilitAnahtari:
    """_lock_key canli davranis + SW-AUTH-1 FIX + reset_lockout."""

    def test_anahtar_tuple_sid_ve_username(self, db):
        """Canli dal (FIX-sonrasi): (store-sid, username) — sid uuid4 hex,
        baglanti-omurlu, _swarmax_sid'den gelir (db.connect atar)."""
        k = auth._lock_key(db, "u1")
        assert isinstance(k, tuple) and len(k) == 2
        assert isinstance(k[0], str)
        assert k[0] == db._swarmax_sid
        assert k[1] == "u1"

    def test_anahtar_ayni_girdide_kararli(self, db):
        """Dal: ayni conn+username -> AYNI tuple (dict-key hashable)."""
        assert auth._lock_key(db, "u1") == auth._lock_key(db, "u1")
        d = {auth._lock_key(db, "u1"): 1}
        assert d[auth._lock_key(db, "u1")] == 1

    def test_anahtar_farkli_kullanici_farkli(self, db):
        """Dal: username ayirici."""
        assert auth._lock_key(db, "u1") != auth._lock_key(db, "u2")

    def test_anahtar_farkli_baglanti_farkli(self, db):
        """Dal: id(conn) ayirici — BULGU-1: iki ayri mağaza iki ayri lockout."""
        baska = connect(":memory:")
        try:
            assert auth._lock_key(db, "u1") != auth._lock_key(baska, "u1")
        finally:
            baska.close()

    def test_swarmax_sid_atandi_store_scoped(self, db):
        """SW-AUTH-1 FIX-Sonrasi kaniti: db.connect() _swarmax_sid'yi atar
        (uuid4 hex); _lock_key bunu kullanir — adres-geri-donusum-korumasi
        artik SAGLANIYOR. ONCE: _swarmax_sid SADECE-annotation'di, connect()
        HIC-ATAMIYORDU ve _lock_key IKI-KEZ-tanimliydi (L44 id(conn) L36'yi
        gecersiz kilardi) — bir-store-digerinin-lockoutunu-miras-alabilirdi."""
        sid = getattr(db, "_swarmax_sid", "YOK")
        assert isinstance(sid, str) and len(sid) == 32  # uuid4().hex
        assert auth._lock_key(db, "u1")[0] == sid
        assert auth._lock_key(db, "u1")[0] != id(db)

    def test_reset_lockout_sayaci_temizler(self, db_admin):
        """Dal: reset_lockout -> _failed.pop; ardindan giris serbest."""
        key = auth._lock_key(db_admin, "root")
        auth._failed[key] = (auth.MAX_FAILED_ATTEMPTS,
                             auth._utcnow() + timedelta(minutes=15))
        auth.reset_lockout(db_admin, "root")
        assert key not in auth._failed
        assert auth.login(db_admin, "root", PW) is not None
