"""One-time interactive command to create the first local developer account."""

from __future__ import annotations

import argparse
import getpass

from codeguard.auth import AuthenticationError, bootstrap_developer


def main() -> int:
    parser = argparse.ArgumentParser(description="Create CodeGuard's first developer account.")
    parser.add_argument("username", help="Developer username or email")
    args = parser.parse_args()
    password = getpass.getpass("New developer password (12+ characters): ")
    confirmation = getpass.getpass("Confirm developer password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    try:
        user = bootstrap_developer(args.username, password)
    except AuthenticationError as error:
        parser.error(str(error))
    print(f"Developer account created for {user['username']} (user id {user['id']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
