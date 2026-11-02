"""SPA static handler (server/spa.py): path guards, SPA fallback, 404s for
missing files, and cache headers. Mounted on a throwaway app over a tiny fake
dist in tmp_path so it doesn't depend on `npm run build`."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import spa

INDEX = "<!doctype html><title>isafan</title>"


@pytest.fixture
def dist(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX)
    (root / "assets" / "app-abc123.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    (root / ".env").write_text("SECRET=1")
    (tmp_path / "outside.txt").write_text("outside")
    return root


@pytest.fixture
def web(dist):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    assert spa.mount_spa(app, dist)
    return TestClient(app)


def _raw_get(client: TestClient, raw_path: str):
    """Send a path byte-for-byte, bypassing httpx's URL normalisation (which
    would otherwise collapse `..` before the request leaves the client)."""
    import httpx

    url = httpx.URL("http://testserver/").copy_with(raw_path=raw_path.encode("latin-1"))
    return client.get(url)


# --- SPA fallback + files ------------------------------------------------------

def test_root_and_deep_link_serve_index_no_cache(web):
    for path in ("/", "/host", "/join/ABCD", "/host/"):
        r = web.get(path)
        assert r.status_code == 200, path
        assert r.text == INDEX
        assert r.headers["cache-control"] == spa.INDEX_CACHE


def test_index_html_directly_is_no_cache(web):
    r = web.get("/index.html")
    assert r.status_code == 200 and r.headers["cache-control"] == spa.INDEX_CACHE


def test_asset_is_immutable(web):
    r = web.get("/assets/app-abc123.js")
    assert r.status_code == 200 and r.text == "console.log(1)"
    assert r.headers["cache-control"] == spa.ASSET_CACHE


def test_other_file_gets_short_cache(web):
    r = web.get("/favicon.svg")
    assert r.status_code == 200
    assert r.headers["cache-control"] == spa.OTHER_CACHE


def test_head_works(web):
    r = web.head("/assets/app-abc123.js")
    assert r.status_code == 200 and r.headers["cache-control"] == spa.ASSET_CACHE


def test_missing_asset_and_file_are_plain_404(web):
    for path in ("/assets/x.js", "/foo.png", "/assets", "/assets/", "/assets/sub/route"):
        r = web.get(path)
        assert r.status_code == 404, path
        assert INDEX not in r.text


def test_routes_registered_before_the_catch_all_still_win(web):
    assert web.get("/api/health").json() == {"ok": True}


# --- traversal / guards -------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "/../outside.txt",
    "/assets/../../outside.txt",
    "/%2e%2e/outside.txt",
    "/%2E%2E/outside.txt",
    "/assets/%2e%2e/%2e%2e/outside.txt",
    "/.env",
    "/%2eenv",
    "/assets/.hidden",
    "/..%5coutside.txt",
    "/assets%5c..%5c..%5coutside.txt",
    "/favicon.svg%00.png",
    "/index.html%00",
    "/C:/Windows/win.ini",
    "/c%3a%5cwindows%5cwin.ini",
    "//etc/passwd",
    "/assets//app-abc123.js",
])
def test_traversal_and_odd_paths_are_404(web, raw):
    r = _raw_get(web, raw)
    assert r.status_code == 404, raw
    assert "outside" not in r.text and "SECRET" not in r.text and INDEX not in r.text


def test_double_encoding_is_not_decoded_twice(web):
    # %252e -> "%2e" after the one decode: a literal name, not "." -> treated as
    # an unknown SPA route / missing file, never as traversal.
    r = _raw_get(web, "/%252e%252e/outside.txt")
    assert r.status_code == 404
    assert "outside" not in r.text


def test_symlink_escaping_the_root_is_refused(web, dist, tmp_path):
    link = dist / "assets" / "leak.txt"
    try:
        os.symlink(tmp_path / "outside.txt", link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this machine")
    r = web.get("/assets/leak.txt")
    assert r.status_code == 404 and "outside" not in r.text


def test_refused_unit():
    for bad in ("..", "/etc/passwd", "a/../b", ".env", "a/.git/config", "a\\b", "c:x", "a//b", "a\x00b"):
        assert spa._refused(bad), bad
    for ok in ("", "host", "host/", "assets/app.js", "a..b.js", "join/ABCD"):
        assert not spa._refused(ok), ok


def test_not_mounted_without_index(tmp_path):
    app = FastAPI()
    assert spa.mount_spa(app, tmp_path / "missing") is False


# --- the real app: /api misses stay JSON ------------------------------------------

def test_api_miss_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "not found"}


def test_short_names_case_aliases_and_trailing_dots_are_refused(web, dist):
    (dist / ".secretdir").mkdir()
    (dist / ".secretdir" / "key.txt").write_text("SECRET=2")
    for path in ("/ENV~1", "/SECRET~1/key.txt", "/ASSETS/app-abc123.js",
                 "/index.html.", "/assets/app-abc123.js.", "/Favicon.svg"):
        r = _raw_get(web, path)
        assert "SECRET" not in r.text, path
        assert r.headers.get("cache-control") != spa.ASSET_CACHE, path


def test_overlong_name_is_404_not_500(web):
    r = web.get("/" + "a" * 300 + ".js")
    assert r.status_code == 404
    r = web.get("/" + "a" * 300)
    assert r.status_code == 200 and r.text == INDEX


def test_404_has_no_cache_header(web):
    r = web.get("/assets/x.js")
    assert r.status_code == 404 and "cache-control" not in r.headers


def test_api_paths_never_get_the_spa(web):
    for path in ("/api", "/api/whatever", "/api/x.js"):
        r = web.get(path)
        assert r.status_code == 404 and INDEX not in r.text, path


def test_head_on_api_routes_is_not_the_spa(client):
    for path in ("/api/nope", "/api/health"):
        r = client.head(path)
        assert r.status_code in (404, 405), (path, r.status_code)
        assert "no-cache" not in r.headers.get("cache-control", ""), path
