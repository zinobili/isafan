import pytest

from server.storage import LocalDiskStorage, build_storage


@pytest.fixture
def store(tmp_path):
    return LocalDiskStorage(tmp_path)


def test_bytes_round_trip_and_nested_dirs(store):
    store.put_bytes("games/ABCD/original_reversed.wav", b"\x00\x01\x02")
    assert store.get_bytes("games/ABCD/original_reversed.wav") == b"\x00\x01\x02"


def test_text_helpers(store):
    store.put_text("games/ABCD/game.json", '{"a": 1}')
    assert store.get_text("games/ABCD/game.json") == '{"a": 1}'


def test_put_is_atomic_leaves_no_tmp(store, tmp_path):
    store.put_bytes("k.bin", b"hi")
    assert not list(tmp_path.rglob("*.tmp"))


def test_delete_file_and_dir(store, tmp_path):
    store.put_bytes("games/ABCD/a.wav", b"x")
    store.put_bytes("games/ABCD/b.wav", b"y")
    store.delete("games/ABCD/a.wav")
    assert not (tmp_path / "games/ABCD/a.wav").exists()
    store.delete("games/ABCD")               # whole folder
    assert not (tmp_path / "games/ABCD").exists()
    store.delete("games/ABCD")               # already gone -> no error


def test_list_children(store):
    assert store.list_children("games") == []          # nothing yet
    store.put_bytes("games/ABCD/original_reversed.wav", b"x")
    store.put_bytes("games/WXYZ/game.json", b"{}")
    store.put_text("games/ABCD/game.json", "{}")
    assert store.list_children("games") == ["ABCD", "WXYZ"]
    assert set(store.list_children("games/ABCD")) == {"original_reversed.wav", "game.json"}


def test_size(store):
    assert store.size("games/ABCD/x.wav") is None       # missing
    store.put_bytes("games/ABCD/x.wav", b"\x00" * 321)
    assert store.size("games/ABCD/x.wav") == 321
    assert store.size("games/ABCD") is None             # a dir, not a file


def test_local_path_is_under_root(store, tmp_path):
    p = store.local_path("games/ABCD/x.wav")
    assert p is not None and tmp_path.resolve() in p.parents


def test_path_traversal_is_rejected(store):
    for bad in ("../escape", "games/../../etc/passwd", "a/../../b"):
        with pytest.raises(ValueError):
            store.local_path(bad)
        with pytest.raises(ValueError):
            store.put_bytes(bad, b"x")


def test_build_storage(tmp_path):
    assert isinstance(build_storage("local", tmp_path), LocalDiskStorage)
    with pytest.raises(ValueError):
        build_storage("s3", tmp_path)
