"""Shared facts about stored clip files: which upload formats we accept, the
MIME type to serve each extension as, and which filenames inside a
``games/<code>/`` folder are real clips (vs. traversal / junk).

Used by the audio upload+download routes (`media.py`) and the admin recordings
browser (`admin/`).
"""

from __future__ import annotations

import re

# The file-input fallback (plain-http LAN pages) uploads whatever the phone's
# own recorder produces — iOS gives m4a/caf, or a .mov when it opens the video
# recorder; Android often 3gp/amr. ffmpeg content-sniffs and takes the audio
# stream regardless; these maps just keep the stored filename sane.
EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/opus": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
    "audio/3gpp": "3gp",
    "video/3gpp": "3gp",
    "audio/amr": "amr",
    "audio/x-caf": "caf",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}
MEDIA_TYPE_BY_EXT = {
    "wav": "audio/wav",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "mov": "video/quicktime",
    "aac": "audio/aac",
    "mp3": "audio/mpeg",
    "3gp": "audio/3gpp",
    "amr": "audio/amr",
    "caf": "audio/x-caf",
}
SOURCE_EXTS = tuple(MEDIA_TYPE_BY_EXT)

_ORIGINAL_NAMES = ("original_reversed.wav", "original_forward.wav")
_ATTEMPT_REVERSED_RE = re.compile(r"^attempt_[A-Za-z0-9_-]{1,16}_reversed\.wav$")
_ATTEMPT_SOURCE_RE = re.compile(
    r"^attempt_[A-Za-z0-9_-]{1,16}_source\.(" + "|".join(SOURCE_EXTS) + r")$"
)


def is_allowed_clip_name(name: str) -> bool:
    """True for the fixed set of clip filenames a game folder can hold — the
    reversed/forward originals, an ``original_source.<ext>``, and per-attempt
    reversed / source files. Everything else (game.json, traversal, odd
    extensions) is rejected."""
    if name in _ORIGINAL_NAMES:
        return True
    if name.startswith("original_source.") and name.split(".")[-1] in SOURCE_EXTS:
        return True
    return bool(_ATTEMPT_REVERSED_RE.match(name) or _ATTEMPT_SOURCE_RE.match(name))


def media_type_for(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower()
    return MEDIA_TYPE_BY_EXT.get(ext, "application/octet-stream")
