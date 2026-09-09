"""S3Storage against an in-process moto mock — same behaviour contract as
LocalDiskStorage (see test_storage.py)."""

import boto3
import pytest
from moto import mock_aws

from server.s3storage import S3Storage


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="isafan-test")
        yield S3Storage(bucket="isafan-test", prefix="prod", client=client)


def test_bytes_and_text_round_trip(s3):
    s3.put_bytes("games/ABCD/original_reversed.wav", b"\x00\x01\x02")
    assert s3.get_bytes("games/ABCD/original_reversed.wav") == b"\x00\x01\x02"
    s3.put_text("games/ABCD/game.json", '{"a": 1}')
    assert s3.get_text("games/ABCD/game.json") == '{"a": 1}'
    with pytest.raises(FileNotFoundError):
        s3.get_bytes("games/ABCD/missing.wav")


def test_prefix_is_applied(s3):
    s3.put_bytes("k.bin", b"hi")
    raw = s3._s3.list_objects_v2(Bucket="isafan-test")["Contents"]
    assert [o["Key"] for o in raw] == ["prod/k.bin"]


def test_list_children_one_level(s3):
    assert s3.list_children("games") == []
    s3.put_bytes("games/ABCD/original_reversed.wav", b"x")
    s3.put_bytes("games/ABCD/game.json", b"{}")
    s3.put_bytes("games/WXYZ/game.json", b"{}")
    assert s3.list_children("games") == ["ABCD", "WXYZ"]
    assert set(s3.list_children("games/ABCD")) == {"original_reversed.wav", "game.json"}


def test_delete_object_and_folder(s3):
    s3.put_bytes("games/ABCD/a.wav", b"x")
    s3.put_bytes("games/ABCD/b.wav", b"y")
    s3.delete("games/ABCD/a.wav")
    assert s3.list_children("games/ABCD") == ["b.wav"]
    s3.delete("games/ABCD")               # whole "folder"
    assert s3.list_children("games") == []
    s3.delete("games/ABCD")               # already gone -> no error


def test_size_modified_total(s3):
    assert s3.size("nope") is None and s3.modified_at("nope") is None
    s3.put_bytes("a/one.wav", b"\x00" * 100)
    s3.put_bytes("a/two.wav", b"\x00" * 50)
    assert s3.size("a/one.wav") == 100
    assert s3.size("a") is None           # a prefix, not an object
    assert isinstance(s3.modified_at("a/one.wav"), float)
    assert s3.total_bytes() == 150


def test_serving(s3):
    assert s3.local_path("a/one.wav") is None
    assert s3.file_response("missing.wav", media_type="audio/wav") is None
    s3.put_bytes("games/ABCD/original_reversed.wav", b"RIFFxxxx")
    resp = s3.file_response("games/ABCD/original_reversed.wav", media_type="audio/wav")
    assert resp.body == b"RIFFxxxx"
    assert resp.media_type == "audio/wav"
    assert resp.headers["cache-control"] == "no-store"


def test_from_env_needs_a_bucket(monkeypatch):
    monkeypatch.delenv("ISAFAN_S3_BUCKET", raising=False)
    with pytest.raises(ValueError):
        S3Storage.from_env()


def test_from_env_reads_config(monkeypatch):
    monkeypatch.setenv("ISAFAN_S3_BUCKET", "b")
    monkeypatch.setenv("ISAFAN_S3_PREFIX", "prod")
    monkeypatch.setenv("ISAFAN_S3_REGION", "us-east-1")
    with mock_aws():
        store = S3Storage.from_env()
    assert store._bucket == "b" and store._prefix == "prod"
