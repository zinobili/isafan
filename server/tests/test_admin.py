"""Admin portal: password hashing, login, session cookie, throttle, logout."""

import re

from server.admin import auth
from server.admin.passwords import hash_password, verify_password


def test_hashpw_cli_prints_quoted_env_line(capsys):
    from server.admin import hashpw

    assert hashpw.main(["hashpw", "correct horse battery"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("ISAFAN_ADMIN_PASSWORD_HASH='scrypt$") and out.endswith("'")
    value = out.split("=", 1)[1].strip().strip("'")
    assert verify_password("correct horse battery", value)


def test_password_hash_roundtrip():
    h = hash_password("hunter2")
    assert h.startswith("scrypt$")
    assert verify_password("hunter2", h)
    assert not verify_password("Hunter2", h)
    assert not verify_password("hunter2", h[:-2] + "xx")   # tampered digest
    assert not verify_password("hunter2", "garbage")
    assert hash_password("hunter2") != h                   # random salt


def test_admin_404_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(auth, "is_configured", lambda: False)
    assert client.get("/admin/login", follow_redirects=False).status_code == 404
    assert client.get("/admin", follow_redirects=False).status_code == 404


def test_status_redirects_anonymous_to_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"


def test_login_page_renders(client):
    r = client.get("/admin/login")
    assert r.status_code == 200 and "Admin sign in" in r.text


def test_login_success_then_status(client, admin_creds):
    r = client.post("/admin/login", data=admin_creds, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    assert auth.COOKIE_NAME in r.cookies

    s = client.get("/admin")
    assert s.status_code == 200
    assert "Uptime" in s.text and admin_creds["username"] in s.text


def test_login_wrong_password_leaves_no_session(client, admin_creds):
    r = client.post(
        "/admin/login", data={**admin_creds, "password": "nope"}, follow_redirects=False
    )
    assert r.status_code == 303 and r.headers["location"] == "/admin/login?error=1"
    assert auth.COOKIE_NAME not in r.cookies
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_login_throttled_after_the_attempt_budget(client, admin_creds):
    bad = {**admin_creds, "password": "nope"}
    for _ in range(5):  # ISAFAN_ADMIN_LOGIN_RATE default
        client.post("/admin/login", data=bad, follow_redirects=False)
    blocked = client.post("/admin/login", data=bad, follow_redirects=False)
    assert blocked.status_code == 200 and "Too many attempts" in blocked.text
    # correct credentials are refused too while the bucket is empty
    still = client.post("/admin/login", data=admin_creds, follow_redirects=False)
    assert "Too many attempts" in still.text


def test_logout_clears_session(client, admin_creds):
    client.post("/admin/login", data=admin_creds)
    csrf = re.search(r'name="csrf" value="([0-9a-f]{32})"', client.get("/admin").text)
    assert csrf
    r = client.post(
        "/admin/logout", data={"csrf": csrf.group(1)}, follow_redirects=False
    )
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_logout_rejects_bad_csrf(client, admin_creds):
    client.post("/admin/login", data=admin_creds)
    r = client.post("/admin/logout", data={"csrf": "0" * 32}, follow_redirects=False)
    assert r.status_code == 403
    assert client.get("/admin").status_code == 200  # session intact


def test_session_cookie_rejected_when_signing_key_changes(client, admin_creds, monkeypatch):
    client.post("/admin/login", data=admin_creds)
    assert client.get("/admin", follow_redirects=False).status_code == 200
    # a password rotation re-derives _secret(); existing cookies stop verifying
    monkeypatch.setattr(auth, "_secret", lambda: b"\x11" * 32)
    assert client.get("/admin", follow_redirects=False).status_code == 303
