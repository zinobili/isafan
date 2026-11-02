# Render onboarding — work checklist

The work queue for putting isafan on Render's free tier. Agents: **read this
whole file first**, then take the first unchecked item whose "Needs" are met.
Update the status markers and the log at the bottom as you go. This file is the
single source of truth for this round; `backlog.md` only points here.

Model setup: the singer1stFan / FI1M service (one free Render web service that
serves the SPA and the API from one origin; created by hand in the dashboard,
`render.yaml` kept as documentation only).

**Status markers:** `[ ]` todo · `[~]` in progress (add who/when) · `[x]` done
(add commit) · `[!]` blocked (say on what, and add it to "Waiting on the human")

---

## Locked decisions

- **One service, Docker runtime.** The existing `Dockerfile` builds the SPA
  (Node) and runs FastAPI with ffmpeg bundled. No native Python runtime, so no
  `.nvmrc` / `engines`; the versions are fixed in the Dockerfile.
- **Created by hand in the dashboard** (New → Web Service → Docker), not a
  Blueprint, which asks for a card. Render does **not** read `render.yaml`;
  every settings change must be made in the dashboard as well.
- **Storage: Cloudflare R2** via the existing `ISAFAN_STORAGE=s3` backend. The
  free tier's disk is wiped on every deploy and sleep, which would lose the
  admin song library.
- **Branches:** all work lands on `dev`. `main` auto-deploys on Render, so
  `main` only moves by a fast-forward from `dev` **with the human's OK**.
- **No keep-awake cron** for now.

## Engineering items (agents can do these)

Do them **in order, one at a time, on `dev`**. Items 1–4 touch overlapping files
(`server/main.py`, `server/ws.py`), so they must not run in parallel. One
commit per item. Test with the `isafan-dev` skill's file→test map while
iterating, and run the full `pytest` before any push.

### 1. [x] Port and join link (d91005e)
- **Needs:** nothing.
- `server/config.py`: port = `ISAFAN_PORT`, else `PORT`, else 8000.
- `Dockerfile`: drop `ISAFAN_PORT=8000` from `ENV` so Render's `PORT` wins.
  Keep `EXPOSE 8000` only as a hint, or remove it.
- `server/config.py` `_resolve_public_url`: order is `ISAFAN_PUBLIC_URL`, then
  `RENDER_EXTERNAL_URL` (Render sets it; source `"render"`), then LAN detection,
  then origin. Without this the QR code points at the container's `10.x`
  address.
- `Dockerfile`: bump the build stage `node:20-slim` → `node:22-slim` (20 is EOL).
- `.env.example` / README Configuration: mention `PORT` and `RENDER_EXTERNAL_URL`.
- **Done when:** tests cover the port precedence and `RENDER_EXTERNAL_URL`;
  full `pytest` passes (config is cross-cutting).

### 2. [x] Real client IP behind proxies (a9698df; review fixes 18c43c1)
- **Needs:** 1.
- Add `client_ip(headers, peer_host, trusted_hops)` to `server/net.py`. With
  `trusted_hops = N > 0`, walk `X-Forwarded-For` from the right and trust
  exactly N hops (the same idea as FI1M's `trustProxy: (_addr, hop) => hop < N`).
  With 0, return the peer address (today's behaviour, so local runs don't change).
- New setting `ISAFAN_TRUST_PROXY` (int, default 0) in `config.py` and
  `.env.example`.
- Use it at all three call sites: `server/main.py` `_client_ip`,
  `server/admin/auth.py` `client_ip`, `server/ws.py` (`ws.client.host`, about
  line 128).
- Do **not** turn on uvicorn's `proxy_headers` as well. That would count hops
  twice.
- **Done when:** `test_net.py` covers 0 hops, N hops, a header shorter than N,
  a spoofed left-most entry, and garbage values; `test_ratelimit.py`,
  `test_admin.py` and `test_ws.py` pass.
- Live hop count gets confirmed in item 8. Don't guess it from FI1M (that one
  had Cloudflare in front, while plain `onrender.com` may differ).

### 3. [x] Harden the static handler and add cache headers (04228fe; review fixes in log)
- **Needs:** 1. (Can follow 2 directly.)
- In `server/main.py` `spa()`:
  - Decode once. Refuse null bytes, `\`, `:`, `//`, and any segment starting
    with `.` (blocks `..` and `.env`) → 404.
  - The resolved path **and its realpath** must stay inside `_STATIC`. Serve
    regular files only.
  - Miss on a file-like path (has an extension or is under `assets/`) → plain
    404, **not** `index.html`, so a stale chunk fails loudly.
  - Path with no extension → `index.html` (SPA fallback, unchanged).
  - `Cache-Control`: `index.html` (including the fallback) → `no-cache`;
    `assets/*` → `public, max-age=31536000, immutable`; everything else →
    `public, max-age=3600`.
- `/api/*` misses keep returning a JSON 404 (already true; keep the test).
- **Done when:** a new `server/tests/test_static.py` (build a tiny fake dist in
  `tmp_path`) covers traversal (`..`, `%2e%2e`, `.env`, backslash, null byte),
  the SPA fallback for `/host`, a 404 for a missing `/assets/x.js` and
  `/foo.png`, the three cache headers, and an `/api/nope` JSON 404. Add the new
  file to the `isafan-dev` skill's test map.

### 4. [x] Graceful shutdown of WebSockets (93c7b67)
- **Needs:** 1. Touches `server/ws.py`, so not in parallel with 2.
- On lifespan shutdown (SIGTERM on every deploy and sleep), the `Hub` closes
  every open socket with code `1012` (service restart) before the retention
  task is cancelled. Check that `web/src/lib/socket.ts` reconnects on 1012 (it
  should already, through its normal reconnect and resync path); change it
  only if not.
- **Done when:** a `test_ws.py` case shows that open sockets get a 1012 close
  when the app shuts down.

### 5. [ ] `render.yaml` (documentation only)
- **Needs:** 1–4 (so it describes the final env vars).
- Repo root. `runtime: docker`, `plan: free`, `branch: main`,
  `autoDeploy: true`, `healthCheckPath: /api/health`, service name `isafan`.
- `envVars`: `ISAFAN_TRUST_PROXY` (value from item 8; put a placeholder and a
  comment until then), `ISAFAN_STORAGE=s3`, `ISAFAN_S3_REGION=auto`,
  `ISAFAN_DATA_DIR=/data`. Secrets have **`sync: false` and no value**:
  `ISAFAN_S3_BUCKET`, `ISAFAN_S3_ENDPOINT`, `ISAFAN_S3_ACCESS_KEY`,
  `ISAFAN_S3_SECRET_KEY`, `ISAFAN_ADMIN_USER`, `ISAFAN_ADMIN_PASSWORD_HASH`,
  `ISAFAN_ADMIN_SECRET`. No `ISAFAN_PUBLIC_URL` needed (item 1 uses
  `RENDER_EXTERNAL_URL`).
- Header comment: "Not read by Render — the service was created by hand. Keep
  in step with the dashboard."

### 6. [ ] Local container smoke test
- **Needs:** 1–5.
- `docker build -t isafan .` then
  `docker run --rm -e PORT=10000 -p 10000:10000 isafan` (local storage is
  fine here).
- Check: `curl localhost:10000/api/health`; `curl -I` an `assets/*` file and
  `/host` for the cache headers; a traversal URL gets a 404; one solo round in
  the browser pane at `http://localhost:10000/solo` (record with a synthetic
  mic or the file fallback). Stop the container afterwards.
- Record what you checked in the log. Docker 20.10 is installed on the dev box.

### 7. [ ] README "Deploy (Render)" section
- **Needs:** 5. Fill the live URL in after the human finishes H2.
- Add next to the existing "Deploy (Docker)" section: the live URL, the
  dashboard settings (same as `render.yaml`), the env vars and where secrets
  live, the release flow (`dev` → fast-forward `main` with OK → auto-deploy),
  free-tier limits (sleeps after about 15 min, about 1 min cold start, rooms
  lost on sleep or deploy, audio safe in R2), and the warning that **dashboard
  settings must be kept in step with `render.yaml`**. Update the Status
  section.

### 8. [ ] Post-deploy verification
- **Needs:** H1, H2 done and the first deploy live.
- Agent part: `curl` `<live>/api/health`; check the cache headers and a 404 on
  the live URL; open `<live>/host` in the browser pane and confirm the QR /
  join link shows the `onrender.com` URL; confirm the WebSocket connects
  (lobby loads); create a solo game and upload a clip, which proves the R2
  write from Render.
- Hop count: add a **temporary** line to the admin status page,
  "Your IP as seen: X · raw X-Forwarded-For: Y", behind admin login (never
  public). The human compares it with their real IP and picks
  `ISAFAN_TRUST_PROXY`. Remove the line afterwards in its own commit.
- Also check (from the item 2 review): send a request with your own extra
  `X-Forwarded-For: 6.6.6.6` header line and confirm Render's appended entry
  ends up **right-most** in the raw value. If Render puts its line first,
  `client_ip` must stop joining multiple header lines.
- Human part: H3 and H4.

## Waiting on the human

Agents add anything that needs a person here, with the date, the question, and
the default you'll assume if the change is reversible.

- **H1. [ ] R2 bucket.** Create the bucket (e.g. `isafan-prod`) and an API
  token with read/write on it. Paste the values straight into the Render
  dashboard; never into chat, the repo, or this file.
- **H2. [ ] Create the Render service.** New → Web Service → this repo →
  Docker, branch `main`, plan Free, health check `/api/health`, auto-deploy on.
  Env vars as listed in `render.yaml` (generate the admin hash with
  `python -m server.admin.hashpw`). Then tell the agent the live URL.
- **H3. [ ] Pick the trust-proxy hop count** from the item 8 status line, set
  `ISAFAN_TRUST_PROXY` in the dashboard, and confirm two phones on different
  networks get different IPs.
  - *From the item 2 security review (2026-11-02):* set N to the **shortest
    real path**. If Cloudflare is ever put in front while the `onrender.com`
    URL stays reachable, N=2 lets anyone hitting `onrender.com` directly
    spoof their IP (and lock a chosen victim out of admin login). Then
    either keep N=1 or add a secret-header check first.
  - Until H3 is done, `ISAFAN_TRUST_PROXY=0` on Render means every visitor
    shares the proxy's IP: 10 game creates a minute site-wide, and 5 bad
    admin logins lock the admin out for everyone for 15 min. Fine for a
    friends-only soft launch; do H3 soon after the first deploy.
- **H4. [ ] Real-phone test over HTTPS:** in-page recording on Android Chrome
  and iPhone Safari, one full multi-device round, and admin login.
- **H5. [ ] Release OKs.** Every fast-forward of `main` needs a yes in chat.

---

## Agent roles for this round

| Role | Who runs it | Does | Doesn't |
|---|---|---|---|
| **Lead** | the main Claude session | Owns this file. Picks the next item, briefs the implementer, reviews and commits, keeps "Waiting on the human" and the log up to date, asks the human. | Doesn't merge to `main` without an OK. |
| **Backend implementer** | subagent (general-purpose), one item at a time | Items 1–4: Python/FastAPI changes plus tests, following `isafan-dev`. Returns a diff summary and the test output. | Doesn't commit, push, or touch items it wasn't given. |
| **Security reviewer** | subagent, read-only, after items 2 and 3 | Tries to break the IP parsing (spoofed XFF) and the static guards (encodings, symlinks). Reports findings only. | Doesn't edit code. |
| **DevOps** | lead or a subagent | Items 5 and 6: `render.yaml`, Docker build and run, cache-header checks. | Doesn't touch the Render dashboard or secrets. |
| **Docs** | lead | Item 7. | |
| **Human** | you | H1–H5. | |

Not needed this round: a frontend or design role (no `web/` changes expected
beyond a possible reconnect tweak in item 4).

Reviews can overlap with the next item: the reviewer only reads, so it can
check item N while the implementer works on N+1.

## Away mode (the human isn't at the desk)

The human starts it with something like "away mode: work the Render checklist".
The session must be in **auto mode**, or permission prompts will stop the work.

1. **Loop:** take the first unblocked item, then implement, run the mapped
   tests, review, commit on `dev`, tick it here, and add a log line. Repeat.
2. **Blocked on a question?** Don't stop and wait.
   - If the answer is reversible and has a sensible default: write the
     question and the default under "Waiting on the human", proceed on the
     default, and say so in the commit message.
   - If it isn't reversible, or it's a human step: mark the item `[!]`, add it
     under "Waiting on the human", and move to the next unblocked item.
3. **Push** `dev` to `origin` after each finished item (only after the full
   `pytest` passes). **Never** push or fast-forward `main`, never open the
   Render dashboard, never handle secret values.
4. **When everything left is blocked** (or the queue is empty): finish with a
   short summary of what's done, what's waiting and why, send a push
   notification, and stop. Don't burn time polling.
5. When the human is back, start with the "Waiting on the human" list.

## Log

Newest last. One line per event: date · item · what happened · commit.

- 2026-11-02 · — · checklist written.
- 2026-11-02 · setup · `dev` branched from `main`; checklist committed. Human chose: lead writes items 1–4 itself (no implementer subagent), read-only security-reviewer subagent after 2 and 3; away mode on. · 4f8de6a
- 2026-11-02 · 1 · `PORT` fallback + `RENDER_EXTERNAL_URL` join link, Dockerfile node:22 and no pinned port, new `test_config.py`; full pytest 129 passed. · d91005e
- 2026-11-02 · 2 · `net.client_ip` / `connection_ip`, `ISAFAN_TRUST_PROXY` (default 0) wired into main, admin auth and the WS `Hub`; tests in `test_net.py` + `test_ratelimit.py`; full pytest 143 passed. · a9698df
- 2026-11-02 · 2 · security-reviewer subagent started on a9698df.
- 2026-11-02 · 3 · handler moved to new `server/spa.py` (`mount_spa`, called last in `main.py`) so tests can mount it over a fake dist; guards also refuse a leading `/` (URL `//etc/passwd`); GET + HEAD; `test_static.py` added (symlink case skips on Windows without symlink rights). · 04228fe
- 2026-11-02 · 3 · security-reviewer subagent started on 04228fe.
- 2026-11-02 · 2 · review back: 1 high (rate-limiter `_gc` goes quadratic with many keys), IPv6 /128 keys, uvicorn `proxy_headers` on by default, plus notes for H3/item 8. Fixes follow item 4.
- 2026-11-02 · 4 · `Hub.close_all()` (1012) tracks every accepted socket and runs first on lifespan shutdown; `socket.ts` already reconnects on any close it didn't start, so no web change; 2 tests in `test_ws.py`; full pytest 173 passed. · 93c7b67
- 2026-11-02 · 2 · review fixes: limiter GC amortised + LRU cap (was quadratic: 21 s for 20k keys), IPv6 keyed by /64, zone ids / v4-mapped normalised, uvicorn `proxy_headers=False`. Not fixed (out of scope, low): the admin login throttle also charges successful logins. Config notes added to H3 / item 8. · 18c43c1
- 2026-11-02 · 3 · review back: no traversal on Linux. Fixed: exact-spelling realpath check (Windows 8.3 `ENV~1` -> `.env` leak on dev boxes, case/trailing-dot aliases), ENAMETOOLONG/EACCES now 404 not 500, resolved `index`, `/api` + HEAD never fall through to the SPA. Symlink test still only runs where symlinks are allowed. · this commit
