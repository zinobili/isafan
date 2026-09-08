"""Admin auth: credential check, signed session cookie, CSRF token, and the
`admin_required` FastAPI dependency.

The portal is enabled only when both ISAFAN_ADMIN_USER and
ISAFAN_ADMIN_PASSWORD_HASH are set; otherwise every `/admin` route 404s.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request, Response

from ..config import settings
from ..ratelimit import RateLimiter
from .passwords import verify_password

COOKIE_NAME = "isafan_admin"
COOKIE_PATH = "/admin"

# Shared budget for failed logins, keyed by client IP.
login_limiter = RateLimiter(settings.admin_login_rate, settings.admin_login_window)


def is_configured() -> bool:
    return bool(settings.admin_user and settings.admin_password_hash)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


# --- credentials ------------------------------------------------------------

def authenticate(username: str, password: str) -> bool:
    """True only when the portal is on and both fields match. The scrypt verify
    runs regardless of the username so a wrong user and a wrong password cost
    about the same."""
    if not is_configured():
        return False
    user_ok = hmac.compare_digest(
        (username or "").encode("utf-8"), settings.admin_user.encode("utf-8")
    )
    pw_ok = verify_password(password or "", settings.admin_password_hash)
    return user_ok and pw_ok


# --- signing key ----------------------------------------------------------

def _secret() -> bytes:
    """Key for the session cookie and CSRF token. An explicit ISAFAN_ADMIN_SECRET
    wins; otherwise it's derived from the password hash, so rotating the password
    invalidates every existing session."""
    material = settings.admin_secret or ("pwhash|" + settings.admin_password_hash)
    return hashlib.sha256(b"isafan.admin.v1|" + material.encode("utf-8")).digest()


def _sign(payload: bytes) -> str:
    mac = hmac.new(_secret(), payload, hashlib.sha256).digest()
    body = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    sig = base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
    return f"{body}.{sig}"


def _unsign(token: str) -> bytes | None:
    try:
        body_b64, sig_b64 = token.split(".", 1)
        pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
        payload = base64.urlsafe_b64decode(pad(body_b64))
        sig = base64.urlsafe_b64decode(pad(sig_b64))
    except (ValueError, TypeError):
        return None
    expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return payload if hmac.compare_digest(sig, expected) else None


# --- session cookie -------------------------------------------------------

def issue_session(username: str) -> str:
    return _sign(f"{username}|{int(time.time())}".encode("utf-8"))


def read_session(token: str | None) -> str | None:
    """Return the logged-in username, or None if the cookie is missing, forged,
    expired, or for a different configured user."""
    if not token or not is_configured():
        return None
    payload = _unsign(token)
    if payload is None:
        return None
    try:
        username, issued = payload.decode("utf-8").split("|", 1)
        issued_at = int(issued)
    except ValueError:
        return None
    if time.time() - issued_at > settings.admin_session_ttl:
        return None
    if not hmac.compare_digest(username, settings.admin_user):
        return None
    return username


def cookie_secure() -> bool:
    """Send the cookie only over HTTPS. Forced on when we terminate TLS; can be
    relaxed for local plain-http testing with ISAFAN_ADMIN_INSECURE=1."""
    if settings.ssl_certfile and settings.ssl_keyfile:
        return True
    return not settings.admin_insecure


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.admin_session_ttl,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path=COOKIE_PATH,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)


# --- CSRF (double-submit, bound to the current session cookie) -----------

def csrf_token(session_cookie: str | None) -> str:
    mac = hmac.new(
        _secret(), b"csrf|" + (session_cookie or "").encode("utf-8"), hashlib.sha256
    )
    return mac.hexdigest()[:32]


def check_csrf(request: Request, submitted: str | None) -> bool:
    want = csrf_token(request.cookies.get(COOKIE_NAME))
    return bool(submitted) and hmac.compare_digest(submitted, want)


# --- dependency ----------------------------------------------------------

class _RedirectToLogin(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=303, headers={"Location": "/admin/login"})


def admin_required(request: Request) -> str:
    """FastAPI dependency: yields the username, 404s when the portal is off, and
    303-redirects anonymous visitors to the login page."""
    if not is_configured():
        raise HTTPException(404)
    user = read_session(request.cookies.get(COOKIE_NAME))
    if not user:
        raise _RedirectToLogin()
    return user
