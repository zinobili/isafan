"""S3-compatible object storage backend (AWS S3, Cloudflare R2, MinIO, …).

Enabled with ``ISAFAN_STORAGE=s3``. Storage keys map straight to object keys
under an optional ``ISAFAN_S3_PREFIX``. `local_path` is always None — callers
serve clips through `file_response`, which reads the (small) object into memory.

Config (env):
    ISAFAN_S3_BUCKET      required
    ISAFAN_S3_REGION       e.g. us-east-1 / auto (R2)
    ISAFAN_S3_ENDPOINT     custom endpoint URL (R2 / MinIO); omit for AWS
    ISAFAN_S3_PREFIX       key prefix, e.g. "prod"
    ISAFAN_S3_ACCESS_KEY / ISAFAN_S3_SECRET_KEY   omit to use the ambient
                                                 AWS credential chain (IAM role)
"""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from starlette.responses import Response

from .storage import Storage

_PAGE = 1000  # S3 delete_objects / list page cap


class S3Storage(Storage):
    def __init__(self, *, bucket: str, prefix: str = "", client=None, **client_kwargs) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._s3 = client or boto3.client("s3", **client_kwargs)

    @classmethod
    def from_env(cls) -> "S3Storage":
        bucket = os.environ.get("ISAFAN_S3_BUCKET", "").strip()
        if not bucket:
            raise ValueError("ISAFAN_STORAGE=s3 requires ISAFAN_S3_BUCKET")
        kwargs: dict = {
            "config": Config(
                signature_version="s3v4", s3={"addressing_style": "path"}
            )
        }
        if region := os.environ.get("ISAFAN_S3_REGION", "").strip():
            kwargs["region_name"] = region
        if endpoint := os.environ.get("ISAFAN_S3_ENDPOINT", "").strip():
            kwargs["endpoint_url"] = endpoint
        ak = os.environ.get("ISAFAN_S3_ACCESS_KEY", "").strip()
        sk = os.environ.get("ISAFAN_S3_SECRET_KEY", "").strip()
        if ak and sk:
            kwargs["aws_access_key_id"] = ak
            kwargs["aws_secret_access_key"] = sk
        return cls(bucket=bucket, prefix=os.environ.get("ISAFAN_S3_PREFIX", ""), **kwargs)

    # --- key mapping ------------------------------------------------

    def _key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def _pages(self, **kw):
        token = None
        while True:
            if token:
                kw["ContinuationToken"] = token
            resp = self._s3.list_objects_v2(Bucket=self._bucket, **kw)
            yield resp
            if not resp.get("IsTruncated"):
                return
            token = resp["NextContinuationToken"]

    # --- Storage interface ---------------------------------------

    def put_bytes(self, key: str, data: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=self._key(key), Body=data)

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=self._key(key))
        except ClientError as exc:
            raise FileNotFoundError(key) from exc
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        full = self._key(key)
        keys = {full}  # the object itself, if any
        for page in self._pages(Prefix=full + "/"):  # plus everything "under" it
            keys.update(o["Key"] for o in page.get("Contents", []))
        ordered = list(keys)
        for i in range(0, len(ordered), _PAGE):
            self._s3.delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in ordered[i : i + _PAGE]]},
            )

    def list_children(self, prefix: str) -> list[str]:
        base = self._key(prefix).rstrip("/") + "/"
        names: set[str] = set()
        for page in self._pages(Prefix=base, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                names.add(cp["Prefix"][len(base) :].rstrip("/"))
            for o in page.get("Contents", []):
                rest = o["Key"][len(base) :]
                if rest and "/" not in rest:
                    names.add(rest)
        return sorted(n for n in names if n)

    def _head(self, key: str) -> dict | None:
        try:
            return self._s3.head_object(Bucket=self._bucket, Key=self._key(key))
        except ClientError:
            return None

    def size(self, key: str) -> int | None:
        head = self._head(key)
        return head["ContentLength"] if head else None

    def modified_at(self, key: str) -> float | None:
        head = self._head(key)
        return head["LastModified"].timestamp() if head else None

    def total_bytes(self) -> int:
        base = f"{self._prefix}/" if self._prefix else ""
        return sum(
            o["Size"]
            for page in self._pages(Prefix=base)
            for o in page.get("Contents", [])
        )

    def local_path(self, key: str) -> Path | None:
        return None

    def file_response(self, key: str, *, media_type: str) -> Response | None:
        try:
            data = self.get_bytes(key)
        except FileNotFoundError:
            return None
        return Response(
            data, media_type=media_type, headers={"Cache-Control": "no-store"}
        )
