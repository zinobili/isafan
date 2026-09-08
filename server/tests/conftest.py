"""Shared fixtures. Env is set BEFORE any `server` import so the settings
singleton picks up an isolated data dir and a fixed public URL."""

import os
import subprocess
import tempfile

_TMP_DATA = tempfile.mkdtemp(prefix="isafan-test-")
os.environ["ISAFAN_DATA_DIR"] = _TMP_DATA
os.environ["ISAFAN_PUBLIC_URL"] = "http://testhost:8000"
os.environ["ISAFAN_MAX_CLIP_SECONDS"] = "5"
os.environ["ISAFAN_MAX_UPLOAD_BYTES"] = "2000000"
os.environ["ISAFAN_PURGE_INTERVAL"] = "0"  # no background retention loop under test
os.environ["ISAFAN_CREATE_RATE"] = "0"     # rate-limit disabled; tested in isolation

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from server import audio  # noqa: E402
from server.main import app, hub, registry  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate():
    """Every test starts with an empty registry and no live connections."""
    for game in registry.all():
        registry.drop(game.code)
    hub._conns.clear()
    yield
    for game in registry.all():
        registry.drop(game.code)
    hub._conns.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def webm_bytes() -> bytes:
    """~1s of tone as webm/opus — a decodable stand-in for a phone recording."""
    return _synth("sine=frequency=440:duration=1")


@pytest.fixture(scope="session")
def webm_long() -> bytes:
    """6s of tone — over the 5s test limit set in this conftest."""
    return _synth("sine=frequency=440:duration=6")


@pytest.fixture(scope="session")
def webm_quiet_then_loud() -> bytes:
    """1s silence then 1s tone, so a reversal check can assert the halves flip."""
    return _synth(
        "anullsrc=r=44100:cl=mono,atrim=0:1[a];sine=f=440:d=1[b];[a][b]concat=n=2:v=0:a=1[o]",
        filter_complex=True,
    )


def _synth(spec: str, *, filter_complex: bool = False) -> bytes:
    exe = audio.ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "a.webm")
        src = ["-filter_complex", spec, "-map", "[o]"] if filter_complex else ["-f", "lavfi", "-i", spec]
        subprocess.run(
            [exe, "-hide_banner", "-y", *src, "-c:a", "libopus", "-f", "webm", out],
            check=True,
            capture_output=True,
        )
        with open(out, "rb") as fh:
            return fh.read()
