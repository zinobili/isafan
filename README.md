# isafan — reverse-audio party game

A Jackbox-style party game built around **reversed audio**: one person sings and
records, everyone hears it played backwards and tries to mimic *that*, then each
attempt is reversed again so the group can judge who landed closest.

Architecture, options, and the full roadmap live in the plan doc:
`~/.claude/plans/i-want-to-create-vectorized-parnas.md`.

## Status — Phase 1 (skeleton)

Done:

- FastAPI server: `/api/health`, `/api/games/{code}`, `/ws` WebSocket hub.
- `Storage` abstraction with a local-disk backend (audio + `game.json` land here).
- In-memory game registry with readable 4-char room codes.
- Create a game, join by code, live-updating lobby, reconnect/rejoin.
- Svelte + Vite SPA: `/` join, `/host` host screen with QR code, `/debug` WS check.

Not yet: audio recording/reversal, the round loop, voting, retention task,
admin portal (Phases 2–7).

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

## Configuration

All optional — see `.env.example`. Environment variables are read at startup
(`ISAFAN_PORT`, `ISAFAN_MAX_PLAYERS`, `ISAFAN_DATA_DIR`, …).

## Layout

```
server/   FastAPI app — config, storage, game model, ws hub, entrypoint
web/      Svelte + Vite SPA — routes/, lib/ (socket client, router, lobby)
data/     runtime only (gitignored): per-game folders, game.json
```
