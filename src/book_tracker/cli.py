"""``book-tracker`` command line: create the first Admin at installation (FR-006, R12)."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import TypeAdapter, ValidationError

from book_tracker.auth.passwords import hash_password
from book_tracker.persistence import accounts
from book_tracker.persistence.db import Database
from book_tracker.schemas.auth import Password
from book_tracker.settings import Settings

_password = TypeAdapter(Password)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-tracker")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="Create the first Admin account")
    create.add_argument("--login", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument(
        "--if-missing", action="store_true", help="Do nothing (exit 0) if an Admin already exists"
    )
    return parser


def _read_password() -> str:
    from_env = os.environ.get("BOOK_TRACKER_ADMIN_PASSWORD")
    if from_env is not None:
        return from_env
    first = getpass.getpass("Password for the new Admin: ")
    second = getpass.getpass("Repeat the password: ")
    if first != second:
        raise ValueError("The passwords don't match")
    return first


async def create_admin(settings: Settings, login: str, display_name: str, if_missing: bool) -> int:
    database = Database.from_url(settings.database_url)
    try:
        async with database.sessionmaker() as db:
            if await accounts.admin_exists(db):
                if if_missing:
                    print("An Admin account already exists; nothing to do.")
                    return 0
                print("An Admin account already exists; not creating another.", file=sys.stderr)
                return 1
            try:
                password = _password.validate_python(_read_password())
            except ValidationError:
                print("The password must be at least 8 characters.", file=sys.stderr)
                return 1
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            await accounts.create_user(
                db,
                display_name=" ".join(display_name.split()),
                login=login.strip(),
                password_hash=hash_password(password),
                role="admin",
                must_change_password=False,  # the installer chose this password
            )
            await db.commit()
        print(f"Created Admin account {login!r}.")
        return 0
    finally:
        await database.engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "create-admin":
        settings = Settings()  # from the environment
        return asyncio.run(create_admin(settings, args.login, args.display_name, args.if_missing))
    return 2  # pragma: no cover - argparse rejects unknown commands


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
