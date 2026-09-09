---
name: isafan-dev
description: >-
  Working rules for changing this repo (isafan): which pytest files to run for a
  given change so the full suite is skipped while iterating, how much
  verification a change actually needs, and how to run the local server. Load it
  before editing anything under server/ or web/, or before running tests here.
---

# isafan dev workflow

Goal: stop re-running the whole test suite and re-doing full browser checks for
small changes. Scope the work to what actually changed; do the full pass once,
right before pushing.

## Run the app

One dev server, defined in `.claude/launch.json`. Start it with `preview_start`
(name `isafan`) and **reuse it** — never spawn ad-hoc `uvicorn`/`nohup` servers
and never kill servers by scraping PIDs from `netstat`.

- It serves the API + WebSocket + `/admin` + the built SPA on `:8000`,
  auto-reloads on `server/**.py` edits, and reads `.env` for config (admin
  creds, TTLs, rate limits, …).
- **Frontend changes** aren't served until `npm --prefix web run build` runs —
  `web/dist/` is gitignored. For fast frontend iteration use
  `npm --prefix web run dev` (Vite HMR on `:5173`) and open `/admin` on `:8000`
  directly (don't proxy it through `:5173`).

## Which tests to run

While iterating, run **only** the file(s) mapped to what changed. Run the full
`pytest` (and, if `web/` changed, `npm --prefix web run check` + `run build`)
**only right before `git push`**.

| Changed file(s) | Run |
|---|---|
| `web/**` | `npm --prefix web run check` — no pytest (add `run build` before push) |
| `*.md`, `.env.example`, `backlog.md` | nothing |
| `server/audio.py` | `pytest server/tests/test_audio.py server/tests/test_media.py` |
| `server/storage.py` | `pytest server/tests/test_storage.py server/tests/test_retention.py` |
| `server/game.py` | `pytest server/tests/test_game.py server/tests/test_ws.py` |
| `server/media.py`, `server/clips.py` | `pytest server/tests/test_media.py server/tests/test_admin_games.py` |
| `server/ws.py` | `pytest server/tests/test_ws.py` |
| `server/net.py` | `pytest server/tests/test_net.py` |
| `server/retention.py` | `pytest server/tests/test_retention.py server/tests/test_status.py` |
| `server/ratelimit.py` | `pytest server/tests/test_ratelimit.py server/tests/test_admin.py` |
| `server/admin/status.py` | `pytest server/tests/test_status.py` |
| `server/admin/games.py` | `pytest server/tests/test_admin_games.py` |
| `server/admin/auth.py`, `admin/passwords.py`, `admin/hashpw.py` | `pytest server/tests/test_admin.py` |
| `server/admin/render.py`, `admin/routes.py` | `pytest server/tests/test_admin.py server/tests/test_admin_games.py server/tests/test_admin_delete.py server/tests/test_status.py` |
| `server/config.py`, `server/main.py` | full `pytest` (cross-cutting — no shortcut) |

Change spans several rows → run the union. Genuinely unsure → the module's own
`test_<name>.py` plus any row above that names it. A new test file → run it plus
its module's row.

Slow parts of the suite are the ffmpeg audio synth (`webm_*` fixtures) and
scrypt hashing, so `test_media`/`test_audio`/`test_admin*`/`test_status` are the
expensive files — another reason to skip them when they're not implicated.

## Verification depth — match it to the change

- **Server-rendered HTML/CSS tweak** in an `admin/` f-string or `render.py`, when
  a test already asserts the element: `curl -s <url> | grep` the rendered markup
  + the mapped pytest file. **No browser.**
- **New layout, real CSS-break risk, JS behaviour, or a user-reported visual
  bug**: one browser screenshot against the running `isafan` dev server.
- **Backend logic**: the mapped tests; browser only if a UI path could regress.

## Don't

- Don't chain `pytest && git commit && git push` in one shell call — separate
  steps, so a hang is visible and killable.
- Don't run the full `pytest` on every iteration.
- Don't spawn throwaway servers or PID-scrape to kill them — use `preview_start`
  / `preview_stop`.
