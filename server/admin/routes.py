"""Admin portal routes. Mounted always; every route 404s while the portal is
unconfigured (see `auth.is_configured`)."""

from __future__ import annotations

import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from ..clips import is_allowed_clip_name, media_type_for
from ..config import settings
from ..game import GameRegistry
from ..songs import SongLibrary
from ..storage import Storage
from . import auth, games, render, status
from .render import esc, human_bytes, human_duration

# Close enough to process start: this module is imported once during app setup.
_STARTED_AT = time.time()


def build_admin_router(
    registry: GameRegistry, storage: Storage, songs: SongLibrary
) -> APIRouter:
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
            (
                "Library songs",
                f"{s['song_count']} · {s['song_enabled_count']} enabled",
            ),
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

        as_of = time.strftime("%H:%M:%S")
        refresh = (
            '<button class="link refresh" type="button" title="Refresh this page" '
            'aria-label="Refresh this page" onclick="location.reload()">↻</button>'
        )
        return render.page(
            "Status",
            f'<h1>Status{refresh}'
            f'<span class="muted" style="font-size:.8rem;font-weight:400">as of {as_of}</span>'
            f"</h1><div class=grid>{grid}</div>{games_html}",
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

    # --- song library (protected) ----------------------------------

    def _song_audio_block(slug: str) -> str:
        rows = "".join(
            f'<p>{esc(label)} · <span class=muted>{esc(kind)}</span></p>'
            f'<audio controls preload="none" '
            f'src="/admin/songs/{esc(slug)}/audio/{kind}"></audio>'
            for kind, label in (
                ("reversed", "Reversed (what players mimic)"),
                ("forward", "Forward (as recorded)"),
                ("source", "Source upload"),
            )
        )
        return f"<div class=card>{rows}</div>"

    def _relay_lines_form(slug: str, song: dict, csrf: str) -> str:
        def row(ln: dict) -> str:
            label = esc(str(ln.get("label", "")))
            start = ln.get("startMs", "")
            end = ln.get("endMs", "")
            if start != "" and end != "":
                seg = (
                    f'<audio controls preload="none" src="/admin/songs/{esc(slug)}'
                    f'/audio/forward#t={int(start) / 1000:.2f},{int(end) / 1000:.2f}">'
                    "</audio>"
                )
            else:
                seg = '<span class="muted">—</span>'
            return (
                "<tr>"
                f'<td><input name="label" value="{label}" size="14"></td>'
                f'<td><input name="startMs" value="{start}" size="7" inputmode="numeric"></td>'
                f'<td><input name="endMs" value="{end}" size="7" inputmode="numeric"></td>'
                f"<td>{seg}</td></tr>"
            )

        existing = song.get("lines") or []
        rows = "".join(row(ln) for ln in [*existing, {}, {}])
        return (
            "<h2>Relay lines</h2>"
            '<p class="muted">Split the song into lines for relay mode — each '
            "player sings one reversed line. Times are milliseconds into the clip; "
            "clear both times to drop a line. Preview jumps to the line start.</p>"
            f'<form method="post" action="/admin/songs/{esc(slug)}/lines">'
            f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
            "<table><tr><th>Label</th><th>Start&nbsp;ms</th><th>End&nbsp;ms</th>"
            f"<th>Preview</th></tr>{rows}</table>"
            '<p><button type="submit">Save lines</button></p></form>'
        )

    @router.get("/songs", response_class=HTMLResponse)
    def songs_list(
        request: Request, error: str = "", user: str = Depends(auth.admin_required)
    ):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        rows = songs.list()

        add_form = (
            '<h2>Add a song</h2>'
            '<form class="card" method="post" action="/admin/songs" '
            'enctype="multipart/form-data">'
            f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
            '<p><input name="name" placeholder="song name (optional)"></p>'
            '<p><input type="file" name="file" accept="audio/*" required></p>'
            "<button type=submit>Add song</button></form>"
        )
        err = f'<p class="err">{esc(error)}</p>' if error else ""

        if not rows:
            return render.page(
                "Songs",
                f'<h1>Songs</h1>{err}<p class="muted">No songs yet.</p>{add_form}',
                user=user, csrf=csrf,
            )

        trs = ""
        for s in rows:
            slug = s["slug"]
            toggle = (
                f'<form class="inline" method="post" '
                f'action="/admin/songs/{esc(slug)}/enabled">'
                f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
                f'<input type="hidden" name="on" value="{0 if s.get("enabled") else 1}">'
                f'<button class="link" type="submit">'
                f'{"disable" if s.get("enabled") else "enable"}</button></form>'
            )
            trs += (
                "<tr>"
                f'<td><a href="/admin/songs/{esc(slug)}">{esc(s["name"])}</a></td>'
                f'<td>{"yes" if s.get("enabled") else "<span class=muted>no</span>"}</td>'
                f'<td>{esc(human_duration((s.get("durationMs") or 0) / 1000))}</td>'
                f'<td>{len(s.get("lines") or [])}</td>'
                f"<td>{toggle}</td>"
                "<td>"
                + render.post_button(
                    f"/admin/songs/{slug}/delete", "delete", csrf,
                    danger=True, confirm=f"Delete song \"{s['name']}\"?",
                )
                + "</td></tr>"
            )
        table = (
            "<table><tr><th>Name</th><th>Enabled</th><th>Length</th><th>Lines</th>"
            f"<th></th><th></th></tr>{trs}</table>"
        )
        return render.page(
            "Songs", f"<h1>Songs <span class=muted>({len(rows)})</span></h1>"
            f"{err}{table}{add_form}",
            user=user, csrf=csrf,
        )

    @router.post("/songs")
    async def add_song(
        request: Request,
        file: UploadFile,
        csrf: str = Form(""),
        name: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        try:
            await songs.add(name, file, max_seconds=settings.max_song_seconds)
        except HTTPException as exc:
            return RedirectResponse(
                f"/admin/songs?error={quote(str(exc.detail))}", status_code=303
            )
        return RedirectResponse("/admin/songs", status_code=303)

    @router.get("/songs/{slug}", response_class=HTMLResponse)
    def song_detail(
        slug: str, request: Request, user: str = Depends(auth.admin_required)
    ):
        csrf = auth.csrf_token(request.cookies.get(auth.COOKIE_NAME))
        song = songs.get(slug)
        if song is None:
            raise HTTPException(404, "no song with that slug")

        rename = (
            f'<form class="inline" method="post" '
            f'action="/admin/songs/{esc(slug)}/rename">'
            f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
            f'<input name="name" value="{esc(song["name"])}" size="28">'
            "<button type=submit>rename</button></form>"
        )
        toggle = (
            f'<form class="inline" method="post" '
            f'action="/admin/songs/{esc(slug)}/enabled">'
            f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
            f'<input type="hidden" name="on" value="{0 if song.get("enabled") else 1}">'
            f'<button class="link" type="submit">'
            f'{"disable" if song.get("enabled") else "enable"}</button></form>'
        )
        delete = render.post_button(
            f"/admin/songs/{slug}/delete", "Delete song", csrf,
            danger=True, confirm=f"Delete song \"{song['name']}\"?",
        )
        head = (
            f"<h1>{esc(song['name'])}</h1>"
            f'<p class="muted">{esc(slug)} · '
            f'{esc(human_duration((song.get("durationMs") or 0) / 1000))} · '
            f'{"enabled" if song.get("enabled") else "disabled"}</p>'
            f'<p>{rename} &nbsp; {toggle} &nbsp; {delete}</p>'
        )
        body = (
            head + _song_audio_block(slug) + _relay_lines_form(slug, song, csrf)
            + '<p style="margin-top:20px"><a href="/admin/songs">← all songs</a></p>'
        )
        return render.page(f"Song {song['name']}", body, user=user, csrf=csrf)

    @router.post("/songs/{slug}/rename")
    def rename_song(
        slug: str,
        request: Request,
        name: str = Form(""),
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        songs.rename(slug, name)
        return RedirectResponse(f"/admin/songs/{slug}", status_code=303)

    @router.post("/songs/{slug}/enabled")
    def set_song_enabled(
        slug: str,
        request: Request,
        on: str = Form("1"),
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        songs.set_enabled(slug, on == "1")
        return RedirectResponse("/admin/songs", status_code=303)

    @router.post("/songs/{slug}/delete")
    def delete_song(
        slug: str,
        request: Request,
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        songs.delete(slug)
        return RedirectResponse("/admin/songs", status_code=303)

    @router.post("/songs/{slug}/lines")
    async def save_song_lines(
        slug: str,
        request: Request,
        csrf: str = Form(""),
        _user: str = Depends(auth.admin_required),
    ):
        if not auth.check_csrf(request, csrf):
            raise HTTPException(403, "bad CSRF token")
        form = await request.form()  # FastAPI cached this; getlist() for repeats
        lines = []
        for label, start, end in zip(
            form.getlist("label"), form.getlist("startMs"), form.getlist("endMs")
        ):
            start, end = start.strip(), end.strip()
            if not start and not end:
                continue  # a fully-blank row means "no line here"
            try:
                lines.append(
                    {"startMs": int(start or 0), "endMs": int(end or 0), "label": label}
                )
            except ValueError:
                continue
        if songs.set_lines(slug, lines) is None:
            raise HTTPException(404, "no song with that slug")
        return RedirectResponse(f"/admin/songs/{slug}", status_code=303)

    @router.get("/songs/{slug}/audio/{kind}")
    def song_audio(
        slug: str, kind: str, _user: str = Depends(auth.admin_required)
    ):
        key = songs.clip_key(slug, kind)
        if key is None:
            raise HTTPException(404, "unknown song clip")
        path = storage.local_path(key)
        if path is None or not path.is_file():
            raise HTTPException(404, "clip not found")
        return FileResponse(
            path, media_type=media_type_for(key), headers={"Cache-Control": "no-store"}
        )

    return router
