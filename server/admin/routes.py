"""Admin portal routes. Mounted always; every route 404s while the portal is
unconfigured (see `auth.is_configured`)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings
from ..game import GameRegistry
from ..storage import Storage
from . import auth, render, status
from .render import esc, human_bytes, human_duration

# Close enough to process start: this module is imported once during app setup.
_STARTED_AT = time.time()


def build_admin_router(registry: GameRegistry, storage: Storage) -> APIRouter:
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
            "autofocus></p>"
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

    # --- status (protected) -------------------------------------------

    @router.get("", response_class=HTMLResponse)
    def status_page(request: Request, user: str = Depends(auth.admin_required)):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        s = status.collect(registry, storage, settings, start_time=_STARTED_AT)

        if s["purge_enabled"]:
            when = s["next_sweep_at"]
            purge = (
                f"in {human_duration(when - time.time())}"
                if when
                else f"within {human_duration(s['purge_interval_seconds'])}"
            )
            purge += f" · TTL {human_duration(s['ttl_seconds'])}"
        else:
            purge = "disabled"

        disk = "—"
        if s["disk_total_bytes"]:
            disk = (
                f"{human_bytes(s['disk_free_bytes'])} free / "
                f"{human_bytes(s['disk_total_bytes'])}"
            )

        stats = [
            ("Uptime", human_duration(s["uptime_seconds"])),
            ("Active games", str(len(s["active_games"]))),
            ("Stored game folders", str(s["stored_game_count"])),
            ("Stored clips", f"{s['clip_count']} · {human_bytes(s['clip_bytes'])}"),
            ("data/ on disk", human_bytes(s["data_bytes"])),
            ("Disk", disk),
            ("Next purge", purge),
            (
                "Oldest / newest game",
                f"{human_duration(s['oldest_game_age_seconds'])} / "
                f"{human_duration(s['newest_game_age_seconds'])}",
            ),
        ]
        grid = "".join(
            f'<div class="stat"><span class="muted">{esc(label)}</span>'
            f"<b>{esc(val)}</b></div>"
            for label, val in stats
        )

        if s["active_games"]:
            rows = "".join(
                "<tr>"
                f'<td>{esc(g["code"])}</td>'
                f'<td>{esc(g["mode"])}</td><td>{esc(g["phase"])}</td>'
                f'<td>{g["round_no"]}</td>'
                f'<td>{g["connected"]}/{g["players"]}</td>'
                f'<td>{esc(human_duration(g["age_seconds"]))}</td>'
                "</tr>"
                for g in s["active_games"]
            )
            games = (
                "<h2>Active games</h2><table><tr><th>Code</th><th>Mode</th>"
                "<th>Phase</th><th>Round</th><th>Connected</th><th>Age</th></tr>"
                f"{rows}</table>"
            )
        else:
            games = '<h2>Active games</h2><p class="muted">None in memory.</p>'

        return render.page(
            "Status", f"<h1>Status</h1><div class=grid>{grid}</div>{games}",
            user=user, csrf=csrf,
        )

    return router
