"""Admin portal routes. Mounted always; every route 404s while the portal is
unconfigured (see `auth.is_configured`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import auth, render
from .render import esc


def build_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin")

    def _require_enabled() -> None:
        if not auth.is_configured():
            raise HTTPException(404)

    # --- login / logout --------------------------------------------------

    @router.get("/login", response_class=HTMLResponse)
    def login_form(request: Request, error: str = ""):
        _require_enabled()
        if auth.read_session(request.cookies.get(auth.COOKIE_NAME)):
            return RedirectResponse("/admin", status_code=303)
        msg = '<p class="err">Wrong username or password.</p>' if error else ""
        body = (
            "<h1>Admin sign in</h1>"
            f'<div class="card">{msg}'
            '<form method="post" action="/admin/login">'
            '<p><input name="username" placeholder="username" autocomplete="username" '
            'autofocus></p>'
            '<p><input type="password" name="password" placeholder="password" '
            'autocomplete="current-password"></p>'
            "<button type=submit>Sign in</button>"
            "</form></div>"
        )
        return render.page("Sign in", body)

    @router.post("/login")
    def login_submit(
        request: Request,
        username: str = Form(""),
        password: str = Form(""),
    ):
        _require_enabled()
        if not auth.login_limiter.allow(auth.client_ip(request)):
            return render.page(
                "Sign in",
                '<h1>Admin sign in</h1><div class="card"><p class="err">Too many '
                "attempts. Wait a few minutes and try again.</p></div>",
            )
        if not auth.authenticate(username, password):
            return RedirectResponse("/admin/login?error=1", status_code=303)
        resp = RedirectResponse("/admin", status_code=303)
        auth.set_session_cookie(resp, auth.issue_session(username))
        return resp

    @router.post("/logout")
    def logout(request: Request, csrf: str = Form("")):
        _require_enabled()
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        resp = RedirectResponse("/admin/login", status_code=303)
        auth.clear_session_cookie(resp)
        return resp

    # --- portal (protected) --------------------------------------------

    @router.get("", response_class=HTMLResponse)
    def status_page(request: Request, user: str = Depends(auth.admin_required)):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        body = (
            "<h1>Status</h1>"
            f'<div class="card"><p>Signed in as <b>{esc(user)}</b>.</p>'
            '<p class="muted">Status details, the recordings browser, and manual '
            "deletes land in the next commits.</p></div>"
        )
        return render.page("Status", body, user=user, csrf=csrf)

    return router
