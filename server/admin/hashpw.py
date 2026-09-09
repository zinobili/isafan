"""Print a ready-to-paste ISAFAN_ADMIN_PASSWORD_HASH line for your .env file.

    python -m server.admin.hashpw               # prompt (input hidden)
    python -m server.admin.hashpw 'my password' # from argv (visible in shell history)

Output is the full `ISAFAN_ADMIN_PASSWORD_HASH='scrypt$...'` line, single-quoted
because the hash contains '$'. Copy the whole line into .env as-is.
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
    # Single-quote it: the hash contains '$', which python-dotenv would otherwise
    # try to expand as a variable reference in an unquoted .env value.
    print(f"ISAFAN_ADMIN_PASSWORD_HASH='{hash_password(password)}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
