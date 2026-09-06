import audioop
import wave

import pytest

from server import audio


def _half_rms(wav_path):
    with wave.open(str(wav_path), "rb") as w:
        n, sw, ch = w.getnframes(), w.getsampwidth(), w.getnchannels()
        frames = w.readframes(n)
    mid = (n // 2) * sw * ch
    return audioop.rms(frames[:mid], sw), audioop.rms(frames[mid:], sw)


def test_ffmpeg_available():
    assert audio.ffmpeg_available() is True


def test_wav_duration_from_header(tmp_path, webm_bytes):
    src = tmp_path / "in.webm"
    src.write_bytes(webm_bytes)
    out = tmp_path / "out.wav"
    audio.transcode_to_wav(src, out)

    d = audio.wav_duration_seconds(out)
    assert d == pytest.approx(1.0, abs=0.15)
    # canonical format
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        assert w.getsampwidth() == 2


def test_wav_duration_on_garbage_is_none(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav at all")
    assert audio.wav_duration_seconds(bad) is None
    assert audio.wav_duration_seconds(tmp_path / "missing.wav") is None


def test_reverse_actually_reverses(tmp_path, webm_quiet_then_loud):
    src = tmp_path / "in.webm"
    src.write_bytes(webm_quiet_then_loud)
    fwd, rev = tmp_path / "fwd.wav", tmp_path / "rev.wav"
    audio.transcode_to_wav(src, fwd)
    audio.reverse_to_wav(src, rev)

    f0, f1 = _half_rms(fwd)
    r0, r1 = _half_rms(rev)
    assert f1 > f0 * 5          # forward: quiet then loud
    assert r0 > r1 * 5          # reversed: loud then quiet


def test_reverse_rejects_non_audio(tmp_path):
    bad = tmp_path / "x.webm"
    bad.write_bytes(b"definitely not audio")
    with pytest.raises(audio.FfmpegError):
        audio.reverse_to_wav(bad, tmp_path / "out.wav")
