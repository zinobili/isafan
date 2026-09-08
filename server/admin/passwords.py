"""Password hashing for the admin login. Standard library only (`hashlib.scrypt`
+ `hmac`), so it can be imported before the app config loads — e.g. by the
`hashpw` helper or the test conftest.

Encoded form: ``scrypt$<n>$<r>$<p>$<salt_b64>$<dk_b64>`` (all base64 urlsafe,
unpadded). Verifying re-derives the key with the parameters stored in the string
and compares in constant time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

# 2**14 keeps memory at ~16 MB (128 * N * r), under hashlib.scrypt's default
# 32 MB cap, and costs a few tens of ms — plenty for a single admin password.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(txt: str) -> bytes:
    pad = "=" * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = salt or os.urandom(_SALT_BYTES)
    dk = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, dk_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = _unb64(salt_b64)
        expected = _unb64(dk_b64)
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk, expected)
