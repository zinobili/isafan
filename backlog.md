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
- [ ] **Join-time privacy notice** — one line on the join / solo-intro screen:
      recordings are kept up to 24 h for a safety check, then deleted.
- [ ] **Visible recording indicator** while the mic/recorder is live (partly
      there via the REC dot; make it unmissable on the player screen).
- [ ] **Rate-limit** game + `/api/solo` creation (per-IP token bucket).
- [ ] **Wake Lock API** during a round so phones don't sleep mid-record.
- [ ] **Reconnect phase-resync polish** — on silent rejoin, make sure the
      client lands on the correct phase screen with no stale local state.
- [ ] Confirm upload size / duration caps + content-type checks are enforced
      everywhere (caps exist; audit the video-recorder path).

### Phase 6 — Admin portal

- [ ] `/admin` login — username + password from config (hashed, e.g. argon2),
      signed session cookie, failed-login throttling, HTTPS-only.
- [ ] **Status page** — uptime, active games, players per game, `data/` disk
      usage, count + age of stored clips, next purge time.
- [ ] **Recordings browser** — list games (id, created, expiry); per game the
      original + every attempt with inline `<audio>` playback (reversed and
      forward), for policy review.
- [ ] **Delete now** — remove a single clip or a whole game before the 24 h
      auto-purge. All reads/writes go through the `Storage` interface so it
      keeps working after a move to object storage.
- [ ] **Song library manager** — this is where the preloaded songs and relay
      material get prepared (see "Feature ideas"). Add / record / re-upload a
      reference clip, name it, listen back, enable / disable it, and for relay
      songs mark the line boundaries. Writes go through `Storage`
      (`assets/songs/<slug>/…` + a manifest) so the game code just reads them.

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
