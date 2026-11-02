"""Port precedence and join-link (public URL) resolution in server/config.py."""

import pytest

from server import config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("ISAFAN_PORT", "PORT", "ISAFAN_PUBLIC_URL", "RENDER_EXTERNAL_URL"):
        monkeypatch.delenv(name, raising=False)


def test_port_defaults_to_8000():
    assert config._port() == 8000


def test_port_uses_platform_port_when_isafan_port_unset(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert config._port() == 10000


def test_isafan_port_wins_over_platform_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("ISAFAN_PORT", "9001")
    assert config._port() == 9001


def test_blank_isafan_port_falls_through_to_platform_port(monkeypatch):
    monkeypatch.setenv("ISAFAN_PORT", "")
    monkeypatch.setenv("PORT", "10000")
    assert config._port() == 10000


def test_garbage_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("PORT", "abc")
    assert config._port() == 8000


def test_load_settings_reads_platform_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    assert config.load_settings().port == 10000


def test_render_external_url_is_used_when_no_explicit_url(monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://isafan.onrender.com/")
    monkeypatch.setattr(config, "lan_ips", lambda: ["10.0.0.5"])
    assert config._resolve_public_url(10000) == (
        "https://isafan.onrender.com",
        ("https://isafan.onrender.com",),
        "render",
    )


def test_explicit_public_url_wins_over_render(monkeypatch):
    monkeypatch.setenv("ISAFAN_PUBLIC_URL", "https://party.example.com")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://isafan.onrender.com")
    base, candidates, source = config._resolve_public_url(10000)
    assert (base, candidates, source) == (
        "https://party.example.com",
        ("https://party.example.com",),
        "config",
    )


def test_lan_detection_when_no_urls_set(monkeypatch):
    monkeypatch.setattr(config, "lan_ips", lambda: ["192.168.1.20", "10.8.0.2"])
    assert config._resolve_public_url(8000) == (
        "http://192.168.1.20:8000",
        ("http://192.168.1.20:8000", "http://10.8.0.2:8000"),
        "detected",
    )


def test_origin_fallback_when_nothing_found(monkeypatch):
    monkeypatch.setattr(config, "lan_ips", lambda: [])
    assert config._resolve_public_url(8000) == ("", (), "origin")
