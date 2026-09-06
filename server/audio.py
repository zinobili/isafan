"""ffmpeg wrappers: reverse + transcode to a canonical WAV, plus a WAV-header
duration read (no subprocess).

The ffmpeg binary is resolved once, in order:
  1. ISAFAN_FFMPEG (explicit path)
  2. the binary bundled with imageio-ffmpeg (installed as a dependency)
  3. `ffmpeg` on PATH
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

from .config import settings

_FFMPEG_TIMEOUT = 90  # seconds; clips are short, this is just a safety net


class FfmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    if settings.ffmpeg_path:
        return settings.ffmpeg_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FfmpegError(
        "ffmpeg not found — install imageio-ffmpeg, put ffmpeg on PATH, "
        "or set ISAFAN_FFMPEG"
    )


def ffmpeg_available() -> bool:
    try:
        ffmpeg_exe()
        return True
    except FfmpegError:
        return False


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
        capture_output=True,
        timeout=_FFMPEG_TIMEOUT,
    )


def wav_duration_seconds(path: Path) -> float | None:
    """Exact duration of a PCM WAV from its header. `None` if it can't be read
    or holds no audio. Use this on our own transcoded output — browser
    MediaRecorder blobs often carry no container duration, but a PCM WAV always
    does, and reading the header needs no subprocess."""
    try:
        with wave.open(str(path), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
    except (wave.Error, OSError, EOFError):
        return None
    return frames / rate if rate and frames else None


def _to_wav(src: Path, dst: Path, *, reverse: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    args = ["-y", "-i", str(src)]
    if reverse:
        args += ["-af", "areverse"]
    args += ["-ac", "1", "-ar", str(settings.audio_sample_rate), "-c:a", "pcm_s16le", str(dst)]
    proc = _run(args)
    if proc.returncode != 0 or not dst.exists():
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-4:]
        raise FfmpegError("ffmpeg failed: " + " / ".join(tail))


def reverse_to_wav(src: Path, dst: Path) -> None:
    """Reverse `src` (any decodable audio) into a canonical mono 16-bit WAV."""
    _to_wav(src, dst, reverse=True)


def transcode_to_wav(src: Path, dst: Path) -> None:
    """Same canonical WAV, without reversing (used from later phases)."""
    _to_wav(src, dst, reverse=False)
