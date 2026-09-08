"""Print an ISAFAN_ADMIN_PASSWORD_HASH value for your .env file.

    python -m server.admin.hashpw               # prompt (input hidden)
    python -m server.admin.hashpw 'my password' # from argv (visible in shell history)
"""

from __future__ import annotations

import getpass
import sys

from .passwords import hash_password


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        password = argv[1]
    else:
        password = getpass.getpass("admin password: ")
        if password != getpass.getpass("confirm: "):
            print("passwords did not match", file=sys.stderr)
            return 1
    if not password:
        print("empty password", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
