# isafan — reverse-audio party game

A Jackbox-style party game built around **reversed audio**: one person sings and
records, everyone hears it played backwards and tries to mimic *that*, then each
attempt is reversed again so the group can judge who landed closest.

Architecture, options, and the full roadmap live in the plan doc:
`~/.claude/plans/i-want-to-create-vectorized-parnas.md`.

## Status — Phase 4 (multi-device audience loop)

Done:

- **Phase 1** — FastAPI server (`/api/health`, `/api/games/{code}`, `/ws`),
  `Storage` abstraction (local disk), in-memory game registry with readable
  4-char codes, create/join/live lobby/rejoin, Svelte + Vite SPA.
- **Phase 2** — host records the song → `POST /api/games/{code}/original` →
  server reverses + transcodes to a canonical 16 kHz mono WAV with ffmpeg →
  players fetch and play the reversed clip. ffmpeg ships via `imageio-ffmpeg`.
- **Phase 3** — `/solo` pass-the-phone flow, no WebSocket: name players →
  record → hear it backwards → each player mimics in turn
  (`POST /api/games/{code}/attempts`) → reveal forwards → show-of-hands vote.
- **Phase 4** — the same loop across the host screen + phones. Host WS verbs
  `start_audience_recording` / `start_reveal` / `next_round` drive the phases;
  players submit takes to `/attempts` (one per player, re-record replaces it)
  and cast `vote` messages (one each, not their own take). Host screen shows a
  submission checklist then a live vote tally; player screens show a recorder
  then a vote list. Late joins are blocked once the round starts.

Not yet: retention task, admin portal (Phases 5–7).

> On a plain-http LAN page the browser blocks in-page recording, so the record
> control falls back to the phone's own voice recorder via a file input (see
> "Recording over plain HTTP"). The in-page `MediaRecorder` path still wants a
> check on a real Android phone and a real iPhone over HTTPS (formats differ:
> webm/opus vs mp4/aac; the server transcodes both). Flows were verified
> in-browser with a synthetic mic and headless end to end.

## Prerequisites

- Python 3.10+ (a venv built from the Anaconda interpreter is fine)
- Node 18+ and npm

## Setup

```bash
# backend
python -m venv .venv
.venv\Scripts\python -m pip install -r server/requirements.txt   # Windows
# .venv/bin/pip install -r server/requirements.txt               # macOS/Linux

# frontend
npm --prefix web install
```

## Run — development (two processes, hot reload)

```bash
# terminal 1: API + WebSocket on :8000
.venv\Scripts\python -m uvicorn server.main:app --reload

# terminal 2: UI on :5173 (proxies /api and /ws to :8000)
npm --prefix web run dev
```

Open <http://localhost:5173>. Host a game in one tab, join from another with the
code.

## Run — single process (what phones will hit)

```bash
npm --prefix web run build            # emits web/dist
.venv\Scripts\python -m server        # serves API, WS, and the built SPA on :8000
```

Open <http://localhost:8000>.

## Play from a phone (same Wi-Fi)

Just run the server and open <http://localhost:8000/host> on this machine. When
`ISAFAN_PUBLIC_URL` is unset the server auto-detects this machine's LAN IP and
builds the QR / join link from it (`http://<lan-ip>:8000/...`); the address it
chose is printed on startup. Scan it from a phone on the same Wi-Fi.

If the phone can't reach that address, the host screen shows a "Phone can't
reach it? Try:" row under the QR — tap another detected address (e.g. when a VPN
adapter was picked first) and the QR updates. Or pin one yourself:
`ISAFAN_PUBLIC_URL=http://192.168.1.20:8000` in a `.env` file (also how you'd
point it at a tunnel URL).

Notes: Windows Firewall may prompt to allow port 8000 (allow it for Private
networks). A VPN on this machine can block phone↔PC LAN traffic.

### Recording over plain HTTP

`getUserMedia` (in-page recording) only works in a secure context — HTTPS or
`localhost`. On a phone hitting `http://<lan-ip>:8000` it's blocked, so the
record control automatically falls back to a **file input**: the phone opens its
own voice recorder, and the clip is uploaded through the same pipeline. Slightly
clunkier (no in-page REC timer), but zero setup and works on iOS and Android.

For the polished in-page recorder without a tunnel, serve HTTPS with a
locally-trusted cert:

```bash
mkcert -install                         # once, trusts a local CA on this machine
mkcert 192.168.1.20 localhost 127.0.0.1 # -> 192.168.1.20+2.pem  + -key.pem
```

Then set `ISAFAN_SSL_CERT` / `ISAFAN_SSL_KEY` (and
`ISAFAN_PUBLIC_URL=https://192.168.1.20:8000`) and run `python -m server`. On
each phone, install the mkcert root CA once — `mkcert -CAROOT` shows where
`rootCA.pem` lives; on iOS install the profile then enable it under Settings →
General → About → Certificate Trust Settings, on Android use "Install a
certificate → CA certificate". After that the phone trusts `https://<lan-ip>`
and records in-page.

## Tests

```bash
.venv\Scripts\python -m pip install -r server/requirements-dev.txt
.venv\Scripts\python -m pytest          # server: game model, storage, audio, ws + http endpoints
npm --prefix web run check              # web: svelte-check
```

The server tests synthesize tiny audio clips with the bundled ffmpeg and drive
the API/WebSocket through Starlette's `TestClient`; they use an isolated temp
data dir (no `./data` writes).

## Configuration

All optional — see `.env.example`. Read at startup from the environment or a
local `.env` file. Notable: `ISAFAN_PUBLIC_URL` (join-link / QR base address),
`ISAFAN_PORT`, `ISAFAN_MAX_PLAYERS`, `ISAFAN_DATA_DIR`.

## Layout

```
server/   FastAPI app — config, storage, game model, ws hub, audio, entrypoint
server/tests/   pytest suite
web/      Svelte + Vite SPA — routes/, lib/ (socket client, router, components)
data/     runtime only (gitignored): per-game folders, game.json + audio clips
```
