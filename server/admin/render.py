"""Minimal server-rendered HTML for the admin portal — a shared page shell plus
small escaping helpers. No templating engine: the portal is a handful of pages
and keeping it dependency-free matches the rest of the server."""

from __future__ import annotations

from html import escape as _esc

from fastapi.responses import HTMLResponse

esc = _esc


def human_bytes(n: int | None) -> str:
    if n is None:
        return "—"
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024:
            return f"{x:.0f} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{x:.1f} TB"


def post_button(
    action: str, label: str, csrf: str, *, danger: bool = False, confirm: str = ""
) -> str:
    """An inline single-button form that POSTs `action` with the CSRF token."""
    cls = "link danger" if danger else "link"
    onclick = f" onclick=\"return confirm('{esc(confirm)}')\"" if confirm else ""
    return (
        f'<form class="inline" method="post" action="{esc(action)}">'
        f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
        f'<button class="{cls}" type="submit"{onclick}>{esc(label)}</button>'
        "</form>"
    )


def human_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    s = int(max(0, seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background: #f6f7fb; color: #16181d; }
  header { display: flex; align-items: baseline; gap: 16px; padding: 14px 20px;
           background: #fff; border-bottom: 1px solid #e3e5ef; }
  header .brand { font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }
  header nav { display: flex; gap: 14px; align-items: baseline; margin-left: auto; }
  main { max-width: 900px; margin: 24px auto; padding: 0 20px; }
  h1 { font-size: 1.3rem; margin: 0 0 16px; }
  h2 { font-size: 1.05rem; margin: 24px 0 8px; }
  .card { background: #fff; border: 1px solid #e3e5ef; border-radius: 12px; padding: 18px; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border: 1px solid #e3e5ef; border-radius: 12px; overflow: hidden; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #e3e5ef; }
  tr:last-child td { border-bottom: 0; }
  th { background: #eef0f6; font-size: .8rem; text-transform: uppercase; letter-spacing: .04em; }
  form.inline { display: inline; }
  input { font: inherit; padding: 9px 11px; border: 1px solid #cfd2e0; border-radius: 8px; }
  button { font: inherit; font-weight: 600; padding: 9px 14px; border: 0; border-radius: 8px;
           background: #4c5bd4; color: #fff; cursor: pointer; }
  button.danger { background: #d33f3f; }
  button.secondary { background: none; color: inherit; border: 1px solid #cfd2e0; }
  button.link { background: none; color: #4c5bd4; padding: 0; }
  button.link.danger { background: none; color: #d33f3f; }
  button.link.refresh { font-size: 1.15rem; line-height: 1; vertical-align: middle; }
  h1 .refresh { margin: 0 6px; }
  .muted { color: #6b7080; }
  .err { color: #d33f3f; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  .stat { background: #fff; border: 1px solid #e3e5ef; border-radius: 10px; padding: 12px 14px; }
  .stat b { display: block; font-size: 1.3rem; }
  audio { width: 100%; margin: 4px 0; }
  [hidden] { display: none !important; }
  .rec-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 4px 0 10px; }
  button.rec { background: #d33f3f; }
  .rec-dot { width: 12px; height: 12px; border-radius: 50%; background: #d33f3f; opacity: .25; }
  .rec-dot.live { opacity: 1; animation: rec-pulse 1.1s ease-out infinite; }
  .rec-time { font-variant-numeric: tabular-nums; }
  @keyframes rec-pulse {
    0% { box-shadow: 0 0 0 0 rgba(211,63,63,.55); }
    70% { box-shadow: 0 0 0 10px rgba(211,63,63,0); }
    100% { box-shadow: 0 0 0 0 rgba(211,63,63,0); }
  }
  @media (prefers-reduced-motion: reduce) { .rec-dot.live { animation: none; } }
  @media (prefers-color-scheme: dark) {
    body { background: #0f1020; color: #eef0ff; }
    a { color: #9db0ff; }
    .card, .stat, header, table { background: #1a1b33; border-color: #2b2d52; }
    th { background: #24264a; }
    input { background: #0f1020; color: #eef0ff; border-color: #2b2d52; }
    button.link { color: #9db0ff; }
    button.secondary { border-color: #2b2d52; }
    .muted { color: #9aa0c8; }
    header { border-bottom-color: #2b2d52; }
  }
"""


# Vanilla (no build step) in-page recorder for the song-add form. Captures a
# take with MediaRecorder and drops it into the form's <input type=file> via a
# DataTransfer, so the existing multipart POST handler is unchanged. Degrades to
# the plain file input when the page isn't a secure context (plain-http LAN).
SONG_RECORDER_JS = """
(function () {
  var form = document.getElementById('song-add');
  if (!form) return;
  var fileInput = form.querySelector('input[type=file]');
  var fileRow = document.getElementById('rec-file-row');
  var ui = document.getElementById('rec-ui');
  var startBtn = document.getElementById('rec-start');
  var stopBtn = document.getElementById('rec-stop');
  var redoBtn = document.getElementById('rec-redo');
  var dot = document.getElementById('rec-dot');
  var timeEl = document.getElementById('rec-time');
  var statusEl = document.getElementById('rec-status');
  var preview = document.getElementById('rec-preview');

  var ok = window.isSecureContext === true && navigator.mediaDevices &&
           navigator.mediaDevices.getUserMedia && window.MediaRecorder &&
           window.DataTransfer;
  if (!ok) { ui.hidden = true; return; }

  var MIMES = ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/aac','audio/ogg;codecs=opus'];
  function pickMime() {
    for (var i = 0; i < MIMES.length; i++) {
      if (MediaRecorder.isTypeSupported(MIMES[i])) return MIMES[i];
    }
    return '';
  }
  function extFor(m) {
    m = (m || '').toLowerCase();
    if (m.indexOf('webm') >= 0) return 'webm';
    if (m.indexOf('mp4') >= 0 || m.indexOf('m4a') >= 0) return 'mp4';
    if (m.indexOf('aac') >= 0) return 'aac';
    if (m.indexOf('ogg') >= 0 || m.indexOf('opus') >= 0) return 'ogg';
    return 'webm';
  }
  function fmt(s) { return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2); }

  var rec = null, chunks = [], stream = null, t0 = 0, timer = null, url = '';

  function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }
  function toIdle() {
    stopTimer();
    if (url) { URL.revokeObjectURL(url); url = ''; }
    chunks = [];
    timeEl.textContent = '0:00';
    dot.classList.remove('live');
    startBtn.hidden = false; stopBtn.hidden = true; redoBtn.hidden = true;
    preview.hidden = true; preview.removeAttribute('src');
    if (fileRow) fileRow.hidden = false;
  }

  startBtn.addEventListener('click', function () {
    statusEl.textContent = 'Opening the mic…';
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      .then(function (s) {
        stream = s; chunks = [];
        var mime = pickMime();
        rec = mime ? new MediaRecorder(s, { mimeType: mime }) : new MediaRecorder(s);
        rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        rec.onstop = function () {
          stream.getTracks().forEach(function (tr) { tr.stop(); });
          stopTimer();
          var type = rec.mimeType || mime || 'audio/webm';
          var blob = new Blob(chunks, { type: type });
          var file = new File([blob], 'recording.' + extFor(type), { type: type });
          var dt = new DataTransfer(); dt.items.add(file);
          fileInput.files = dt.files;
          url = URL.createObjectURL(blob);
          preview.src = url; preview.hidden = false;
          dot.classList.remove('live');
          startBtn.hidden = true; stopBtn.hidden = true; redoBtn.hidden = false;
          if (fileRow) fileRow.hidden = true;
          statusEl.textContent = 'Recorded take ready — it uploads when you click "Add song".';
        };
        rec.start(250);
        t0 = Date.now(); timeEl.textContent = '0:00';
        dot.classList.add('live');
        startBtn.hidden = true; stopBtn.hidden = false; redoBtn.hidden = true;
        statusEl.textContent = 'Recording…';
        timer = setInterval(function () {
          timeEl.textContent = fmt(Math.floor((Date.now() - t0) / 1000));
        }, 250);
      })
      .catch(function (err) {
        statusEl.textContent = 'Mic unavailable: ' + ((err && err.message) || err);
      });
  });
  stopBtn.addEventListener('click', function () {
    if (rec && rec.state !== 'inactive') rec.stop();
  });
  redoBtn.addEventListener('click', function () {
    try { fileInput.value = ''; } catch (e) {}
    statusEl.textContent = '';
    toIdle();
  });
})();
"""


def page(title: str, body: str, *, user: str | None = None, csrf: str = "") -> HTMLResponse:
    nav = ""
    if user:
        nav = (
            '<nav>'
            '<a href="/admin">Status</a>'
            '<a href="/admin/games">Recordings</a>'
            '<a href="/admin/songs">Songs</a>'
            f'<span class="muted">{esc(user)}</span>'
            '<form class="inline" method="post" action="/admin/logout">'
            f'<input type="hidden" name="csrf" value="{esc(csrf)}">'
            '<button class="link" type="submit">Log out</button>'
            '</form>'
            '</nav>'
        )
    return HTMLResponse(
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)} · isafan admin</title><style>{_CSS}</style></head>"
        f'<body><header><span class="brand">isafan</span>'
        f'<span class="muted">admin</span>{nav}</header>'
        f"<main>{body}</main></body></html>"
    )
