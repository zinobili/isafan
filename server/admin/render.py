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
  button.link { background: none; color: #4c5bd4; padding: 0; }
  button.link.danger { background: none; color: #d33f3f; }
  button.link.refresh { font-size: 1.15rem; line-height: 1; margin-left: -6px; }
  .muted { color: #6b7080; }
  .err { color: #d33f3f; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  .stat { background: #fff; border: 1px solid #e3e5ef; border-radius: 10px; padding: 12px 14px; }
  .stat b { display: block; font-size: 1.3rem; }
  audio { width: 100%; margin: 4px 0; }
  @media (prefers-color-scheme: dark) {
    body { background: #0f1020; color: #eef0ff; }
    a { color: #9db0ff; }
    .card, .stat, header, table { background: #1a1b33; border-color: #2b2d52; }
    th { background: #24264a; }
    input { background: #0f1020; color: #eef0ff; border-color: #2b2d52; }
    button.link { color: #9db0ff; }
    .muted { color: #9aa0c8; }
    header { border-bottom-color: #2b2d52; }
  }
"""


def page(title: str, body: str, *, user: str | None = None, csrf: str = "") -> HTMLResponse:
    nav = ""
    if user:
        nav = (
            '<nav>'
            '<a href="/admin">Status</a>'
            '<button class="link refresh" type="button" title="Refresh this page" '
            'aria-label="Refresh this page" onclick="location.reload()">↻</button>'
            '<a href="/admin/games">Recordings</a>'
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
