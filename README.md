# isafan — reverse-audio party game

A Jackbox-style party game built around **reversed audio**: one person sings and
records, everyone hears it played backwards and tries to mimic *that*, then each
attempt is reversed again so the group can judge who landed closest.

Architecture, options, and the full roadmap live in the plan doc:
`~/.claude/plans/i-want-to-create-vectorized-parnas.md`.

## Status — Phase 2 (audio I/O)

Done:

- **Phase 1** — FastAPI server (`/api/health`, `/api/games/{code}`, `/ws`),
  `Storage` abstraction (local disk), in-memory game registry with readable
  4-char codes, create/join/live lobby/rejoin, Svelte + Vite SPA
  (`/` join, `/host`, `/debug`).
- **Phase 2** — host records the song → `POST /api/games/{code}/original` →
  server reverses + transcodes to a canonical 16 kHz mono WAV with ffmpeg →
  players fetch and play it from `GET /api/games/{code}/audio/original_reversed.wav`.
  Phases `HOST_RECORDING` / `REVERSING` / `REVERSED_PLAYBACK` drive the UI.
  ffmpeg ships via the `imageio-ffmpeg` dependency — no system install.

Not yet: the audience recording + reveal loop, single-device mode, voting,
retention task, admin portal (Phases 3–7).

> The in-app browser blocks microphone capture, so the actual `MediaRecorder`
> path (record → encode → upload) still needs a check on a real Android phone and
> a real iPhone — formats differ (webm/opus vs mp4/aac) and the server transcodes
> both, but only real devices confirm it.

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
code (or open `/debug` to exercise the WebSocket directly).

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
networks). A VPN on this machine can block phone↔PC LAN traffic. Microphone
recording needs HTTPS, so a same-Wi-Fi `http://` setup only covers the
join/lobby flow — use a tunnel for the full game.

## Configuration

All optional — see `.env.example`. Read at startup from the environment or a
local `.env` file. Notable: `ISAFAN_PUBLIC_URL` (join-link / QR base address),
`ISAFAN_PORT`, `ISAFAN_MAX_PLAYERS`, `ISAFAN_DATA_DIR`.

## Layout

```
server/   FastAPI app — config, storage, game model, ws hub, entrypoint
web/      Svelte + Vite SPA — routes/, lib/ (socket client, router, lobby)
data/     runtime only (gitignored): per-game folders, game.json
```
