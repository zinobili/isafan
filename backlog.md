# Backlog

Shipped work and how to run it live in [README.md](README.md). This file is
what's **not** built yet. Rough priority order within each section.

---

## Planned phases (engineering — Claude)

### Phase 5 — Retention & safety hardening

- [x] **24 h auto-purge task** — `server/retention.py`: a background loop
      (`ISAFAN_PURGE_INTERVAL`, default 1 h) that deletes each game's folder
      (audio + `game.json`) once it's older than `ISAFAN_GAME_TTL`, via the
      `Storage` interface. Sweeps once on startup, then on the interval. Age
      comes from `game.json`'s `createdAt`, falling back to folder mtime.
- [x] **Join-time privacy notice** — `PrivacyNote.svelte` on the join / solo
      intro screens; the window ("kept up to N hours") is read from
      `/api/config`'s `retentionHours`, which tracks `ISAFAN_GAME_TTL`.
- [x] **Visible recording indicator** while the mic/recorder is live — a fixed
      full-width red "Recording — your mic is live" banner in `RecordControl`
      (warming + hot), on top of the existing inline REC row.
- [x] **Rate-limit** game + `/api/solo` creation (per-IP token bucket) —
      `server/ratelimit.py`, applied to `POST /api/solo` (429) and the WS
      `create` verb (`rate_limited` error). `ISAFAN_CREATE_RATE` /
      `ISAFAN_CREATE_RATE_WINDOW`; in-process only (revisit in Phase 7).
- [x] **Wake Lock API** during a round so phones don't sleep mid-record —
      `web/src/lib/wakelock.ts`, held for the duration of a take in
      `RecordControl`, re-acquired on `visibilitychange`. No-op where
      unsupported.
- [x] **Reconnect phase-resync polish** — `socket.ts` exposes a `resyncNonce`
      bumped when a silent `rejoin` completes; Host/Join key the recorder and
      clear transient upload/error state on it, so the screen re-derives purely
      from the fresh `game` snapshot.
- [x] Confirm upload size / duration caps + content-type checks are enforced
      everywhere — both `/original` and `/attempts` run through
      `_ingest_reversed` (stream cap + early `Content-Length` reject + ffmpeg
      audio sniff + duration cap). Regression tests cover both paths and the
      iOS video-recorder (`.mov` / `video/*`) upload.

### Phase 6 — Admin portal

- [x] `/admin` login — `server/admin/`: username + scrypt password hash from
      config (`python -m server.admin.hashpw`), HMAC-signed session cookie
      (key derived from the hash, so a password change ends all sessions),
      per-IP failed-login throttle, `Secure` cookie unless
      `ISAFAN_ADMIN_INSECURE=1`. Portal 404s until it's configured. CSRF-guarded
      logout. Server-rendered HTML, no new deps.
- [x] **Status page** — `/admin`: uptime, active games (phase / round /
      connected / age), stored game folders, stored-clip count + bytes, `data/`
      disk usage + volume headroom, next purge time
      (`retention.last_sweep_at` + interval). `server/admin/status.py`. Every
      admin page has an in-page "↻ Refresh" button; the status heading shows the
      snapshot time. Solo games register on "Start" (not on first reversal), so
      they show here while the original is still being recorded.
- [x] **Recordings browser** — `/admin/games` (code, mode, phase, players,
      takes, age, time-to-expiry); `/admin/games/<code>` shows the original
      (reversed / forward / source) and every attempt as inline `<audio>` plus
      any unlinked clips, streamed via an auth-gated route. Reads go through
      `Storage`, so games that have left memory stay reviewable.
- [x] **Delete now** — CSRF-guarded `POST /admin/games/<code>/delete` (whole
      game + `registry.drop`) and `.../clips/<name>/delete` (one file), both via
      the `Storage` interface. Buttons on the browser pages.
- [x] **Song library manager** (Phase 6b) — `server/songs.py` (`SongLibrary`
      over `Storage`, manifest + per-slug `source`/`reversed`/`forward` clips
      under `assets/songs/`, outside `games/`). `/admin/songs`: upload to add,
      enable/disable, rename, delete, inline playback; `/admin/songs/<slug>`
      also has a relay line-boundary editor (`{startMs,endMs,label}` rows with
      `#t=` segment preview). Ingest shares `server/ingest.py` with the game
      upload path; `ISAFAN_MAX_SONG_SECONDS` caps reference clips.
      Still to wire: "pick a song" in the host lobby / solo flow (Preloaded
      song library feature idea) and the `relay` game mode.

### Phase 7 — Online hosting

- [ ] **`S3Storage`** implementation behind the existing `Storage` interface;
      select via `ISAFAN_STORAGE=s3` + bucket/credentials config.
- [ ] **Dockerfile** (app + bundled ffmpeg + built SPA) and a deploy to a
      managed container host with real TLS and a small persistent volume.
- [ ] Revisit whether game state needs a shared store (Redis) once there's
      more than one instance; today it's in-process only.

### Known gaps / smaller polish

- [ ] **Real-device recording check over HTTPS** — the in-page `MediaRecorder`
      path (webm/opus vs iOS mp4/aac) has only been exercised with a synthetic
      mic. Verify on a real Android phone and a real iPhone via mkcert or a
      tunnel.
- [ ] **"Use headphones" prompt** for multi-device — each phone plays the
      reversed clip while its mic is hot; nudge players to plug in earbuds.
- [ ] **Synchronised playback** ("play at T" timestamp) if simultaneous
      listening ever needs to feel tight; not critical while each player
      records against their own local playback.
- [ ] **Stable tunnel URL** guidance — named Cloudflare tunnel / reserved
      ngrok domain so the join link survives a restart.
- [ ] Reveal playbars show `0:00 / 0:00` until first play (a side effect of
      `preload="none"`, chosen to stop the mobile load stampede). Revisit if
      it reads as broken — could show the known `durationMs` as a label.

---

## Feature ideas (product)

### Intro / how-to-play guide

A short illustrated walkthrough at the start of the journey so first-timers
know what's coming.

- [ ] A **swipeable widget** (a few slides, one picture + one line each)
      covering the loop: record a song → hear it backwards → sing the
      backwards version → play everyone's take forwards → vote.
- [ ] **Skip** button on every slide, and a "Got it" on the last.
- [ ] Remember it was seen (`localStorage`) so returning players skip straight
      in; a small "How to play" link somewhere to reopen it.
- [ ] Shown before the join / host / solo choice (or on first landing).
- [ ] Illustrations: owner supplies them, or start with simple emoji / SVG
      placeholders.

### Preloaded song library

Host / solo player shouldn't have to record a song on the spot.

- [ ] Reference clips are **added through the admin portal's song library
      manager** (Phase 6), not dropped in as files. The portal stores each one
      and pre-computes its reversed + forward WAV.
- [ ] "Pick a song" option on the host LOBBY screen and the solo `original`
      step, alongside "record your own".
- [ ] `game.original` gets populated from the library entry instead of an
      upload; everything downstream is unchanged.

### Group relay mode ("everyone sings one line")

Instead of one person mimicking the whole clip, split a song into lines and
give each player one **reversed line** to sing back; the reveal stitches the
reversed-attempts in order to reconstruct the whole song (e.g. "Happy Birthday
to You" — 4 lines, 4 players).

- [ ] New game mode (`relay`) alongside `multi` / `solo`.
- [ ] The "original" for a relay is a library song with **line-boundary
      timestamps set in the admin portal's song library manager**.
- [ ] Assign lines to players (round-robin, or let them claim one).
- [ ] Each player records only their line; host reveal plays every reversed
      line back-to-back so the group hears the song rebuilt.
- [ ] Scoring stays "audience decides" — vote per player, or just enjoy the
      reconstruction.

---

## Content to prepare (owner: you)

Once the **admin portal's song library manager** (Phase 6) exists, do all of
this through it — no file drops:

- [ ] Record / upload a handful of well-known short songs or phrases, sung
      cleanly, a few seconds each, for the preloaded library.
- [ ] For each song you want in **relay mode**, mark the line boundaries
      (start with "Happy Birthday to You" — 4 lines).

Separately:

- [ ] Slide illustrations for the intro / how-to-play guide (optional — can
      ship with emoji / SVG placeholders first).
