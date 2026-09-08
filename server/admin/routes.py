"""Admin portal routes. Mounted always; every route 404s while the portal is
unconfigured (see `auth.is_configured`)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..clips import is_allowed_clip_name, media_type_for
from ..config import settings
from ..game import GameRegistry
from ..storage import Storage
from . import auth, games, render, status
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
                f'<td><a href="/admin/games/{esc(g["code"])}">{esc(g["code"])}</a></td>'
                f'<td>{esc(g["mode"])}</td><td>{esc(g["phase"])}</td>'
                f'<td>{g["round_no"]}</td>'
                f'<td>{g["connected"]}/{g["players"]}</td>'
                f'<td>{esc(human_duration(g["age_seconds"]))}</td>'
                "</tr>"
                for g in s["active_games"]
            )
            games_html = (
                "<h2>Active games</h2><table><tr><th>Code</th><th>Mode</th>"
                "<th>Phase</th><th>Round</th><th>Connected</th><th>Age</th></tr>"
                f"{rows}</table>"
            )
        else:
            games_html = '<h2>Active games</h2><p class="muted">None in memory.</p>'

        return render.page(
            "Status", f"<h1>Status</h1><div class=grid>{grid}</div>{games_html}",
            user=user, csrf=csrf,
        )

    # --- recordings browser (protected) ------------------------------

    @router.get("/games", response_class=HTMLResponse)
    def games_list(request: Request, user: str = Depends(auth.admin_required)):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        rows = games.list_games(storage, settings.game_ttl_seconds)
        if not rows:
            body = '<h1>Recordings</h1><p class="muted">No stored games.</p>'
            return render.page("Recordings", body, user=user, csrf=csrf)
        trs = "".join(
            "<tr>"
            f'<td><a href="/admin/games/{esc(r["code"])}">{esc(r["code"])}</a></td>'
            f'<td>{esc(r["mode"])}</td><td>{esc(r["phase"])}</td>'
            f'<td>{r["players"]}</td><td>{r["attempts"]}</td>'
            f'<td>{esc(human_duration(r["age_seconds"]))} ago</td>'
            f'<td>{esc(human_duration(r["expires_in_seconds"]))}</td>'
            "<td>"
            + render.post_button(
                f"/admin/games/{r['code']}/delete", "delete", csrf,
                danger=True, confirm=f"Delete game {r['code']} and every clip?",
            )
            + "</td></tr>"
            for r in rows
        )
        body = (
            f"<h1>Recordings <span class=muted>({len(rows)})</span></h1>"
            "<table><tr><th>Code</th><th>Mode</th><th>Phase</th><th>Players</th>"
            "<th>Takes</th><th>Age</th><th>Expires in</th><th></th></tr>"
            f"{trs}</table>"
        )
        return render.page("Recordings", body, user=user, csrf=csrf)

    @router.get("/games/{code}", response_class=HTMLResponse)
    def game_detail(code: str, request: Request, user: str = Depends(auth.admin_required)):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        detail = games.load_game(storage, code)
        if detail is None:
            raise HTTPException(404, "no stored game with that code")
        code = detail["code"]
        meta = detail["meta"]

        def clip(label: str, name: str | None) -> str:
            if not name:
                return f'<p class="muted">{esc(label)}: —</p>'
            url = f"/admin/games/{esc(code)}/audio/{esc(name)}"
            drop = render.post_button(
                f"/admin/games/{code}/clips/{name}/delete", "delete", csrf,
                danger=True, confirm=f"Delete {name}?",
            )
            return (
                f"<p>{esc(label)} · <span class=muted>{esc(name)}</span> · {drop}</p>"
                f'<audio controls preload="none" src="{url}"></audio>'
            )

        head = (
            f"<h1>Game {esc(code)}</h1>"
            f'<p class="muted">{esc(meta.get("mode", "?"))} · '
            f'{esc(meta.get("phase", "?"))} · '
            f'{esc(", ".join(p.get("name", "") for p in meta.get("players", [])) or "no players")}'
            "</p>"
        )
        orig = detail["original"]
        orig_html = (
            "<h2>Original</h2><div class=card>"
            + clip("Reversed (what players mimic)", orig["reversed"])
            + clip("Forward (as sung)", orig["forward"])
            + clip("Source upload", orig["source"])
            + "</div>"
        )

        atts = detail["attempts"]
        if atts:
            blocks = "".join(
                "<div class=card>"
                f'<p><b>{esc(a["name"] or "?")}</b> '
                f'<span class=muted>{esc(human_duration((a["duration_ms"] or 0) / 1000))}</span></p>'
                + clip("Reversed", a["reversed"])
                + clip("Source", a["source"])
                + "</div>"
                for a in atts
            )
            atts_html = f"<h2>Attempts ({len(atts)})</h2>{blocks}"
        else:
            atts_html = '<h2>Attempts</h2><p class="muted">None.</p>'

        orphan_html = ""
        if detail["orphans"]:
            items = "".join(clip("Orphan clip", n) for n in detail["orphans"])
            orphan_html = f"<h2>Unlinked clips</h2><div class=card>{items}</div>"

        delete_all = render.post_button(
            f"/admin/games/{code}/delete", "Delete whole game", csrf,
            danger=True, confirm=f"Delete game {code} and every clip?",
        )
        body = (
            head + f'<p style="margin:8px 0 4px">{delete_all}</p>'
            + orig_html + atts_html + orphan_html
            + '<p style="margin-top:20px"><a href="/admin/games">← all recordings</a></p>'
        )
        return render.page(f"Game {code}", body, user=user, csrf=csrf)

    # --- manual deletes (protected, CSRF-guarded) -------------------

    @router.post("/games/{code}/delete")
    def delete_game(
        code: str,
        request: Request,
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        storage.delete(f"games/{code}")
        registry.drop(code)
        return RedirectResponse("/admin/games", status_code=303)

    @router.post("/games/{code}/clips/{name}/delete")
    def delete_clip(
        code: str,
        name: str,
        request: Request,
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        if not is_allowed_clip_name(name):
            raise HTTPException(404, "unknown clip")
        storage.delete(f"games/{code}/{name}")
        return RedirectResponse(f"/admin/games/{code}", status_code=303)

    @router.get("/games/{code}/audio/{name}")
    def game_audio(code: str, name: str, _user: str = Depends(auth.admin_required)):
        if not is_allowed_clip_name(name):
            raise HTTPException(404, "unknown clip")
        path = storage.local_path(f"games/{code}/{name}")
        if path is None or not path.is_file():
            raise HTTPException(404, "clip not found")
        return FileResponse(
            path, media_type=media_type_for(name), headers={"Cache-Control": "no-store"}
        )

    return router
