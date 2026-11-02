"""Static hosting for the built SPA, with a history-API fallback so deep links
like /host survive a hard refresh.

Path rules (the path param arrives already percent-decoded once by the ASGI
server; it is never decoded again, so `%252e` stays a literal `%2e`):

- null bytes, backslashes, colons, `//` (including a leading one), and any segment starting with `.`
  (which covers `..` and dotfiles like `.env`) -> 404;
- the file, after following symlinks, must be a regular file inside the static
  root;
- a miss on a file-like path (has an extension or is under `assets/`) -> plain
  404, so a stale hashed chunk fails loudly instead of being served HTML;
- any other miss -> index.html (SPA route).

Cache-Control: index.html (including the fallback) is `no-cache`; hashed
`assets/*` are immutable for a year; anything else gets an hour.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse, Response

INDEX_CACHE = "no-cache"
ASSET_CACHE = "public, max-age=31536000, immutable"
OTHER_CACHE = "public, max-age=3600"

_BAD_SUBSTRINGS = ("\x00", "\\", ":", "//")


def _refused(rel: str) -> bool:
    # A leading "/" means the URL started with "//": an absolute path once
    # joined to the root.
    if rel.startswith("/") or any(bad in rel for bad in _BAD_SUBSTRINGS):
        return True
    return any(seg.startswith(".") for seg in rel.split("/"))


def _file_like(rel: str) -> bool:
    segments = rel.split("/")
    return segments[0] == "assets" or "." in segments[-1]


def _inside(root: Path, rel: str) -> Path | None:
    """The real path of `rel` if it is a regular file within `root` that is
    spelled exactly `rel` once resolved. The exact-spelling check gives each
    file one URL: it refuses Windows 8.3 short names (`ENV~1` -> `.env`),
    case aliases, trailing dots/spaces, and symlinks into dot-directories."""
    try:
        real = (root / rel).resolve()
        if real == root or root not in real.parents:
            return None
        if real.relative_to(root).as_posix() != rel:
            return None
        return real if real.is_file() else None
    except (OSError, RuntimeError, ValueError):  # loops, ENAMETOOLONG, EACCES
        return None


def _not_found() -> Response:
    return PlainTextResponse("not found", status_code=404)


def mount_spa(app: FastAPI, static_dir: Path) -> bool:
    """Register the catch-all static route if `static_dir/index.html` exists.
    Must be called after every other route. Returns whether it mounted."""
    root = static_dir.resolve()
    index = (root / "index.html").resolve()
    if not index.is_file():
        return False

    def serve_index() -> Response:
        return FileResponse(index, headers={"Cache-Control": INDEX_CACHE})

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(full_path: str) -> Response:
        rel = full_path
        # /api is the JSON API's space: never answer it with the SPA (e.g. a
        # HEAD to a GET-only API route would otherwise land here).
        if _refused(rel) or rel == "api" or rel.startswith("api/"):
            return _not_found()
        if rel:
            found = _inside(root, rel)
            if found is not None:
                if found == index:
                    return serve_index()
                cache = ASSET_CACHE if rel.split("/")[0] == "assets" else OTHER_CACHE
                return FileResponse(found, headers={"Cache-Control": cache})
            if _file_like(rel):
                return _not_found()
        return serve_index()

    return True
