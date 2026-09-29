"""Local SQLite authentication with scrypt password hashes and role checks."""

from __future__ import annotations

from datetime import datetime, timezone
import base64
import hashlib
import hmac
import re
import sqlite3
from typing import Any

from codeguard.storage import DEFAULT_DATABASE_PATH, _database, initialize_database

USER = "USER"
DEVELOPER = "DEVELOPER"
_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_BYTES = 32
_USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+-]{2,253}$")


class AuthenticationError(ValueError):
    """Credentials or account operations were invalid."""


class AuthorizationError(PermissionError):
    """The authenticated role does not authorize an operation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12 or len(password) > 1024:
        raise AuthenticationError("Use a password between 12 and 1024 characters.")
    import secrets

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_BYTES
    )
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N,
        _SCRYPT_R,
        _SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 1024:
        return False
    try:
        algorithm, n_value, r_value, p_value, salt_text, digest_text = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        n_value, r_value, p_value = int(n_value), int(r_value), int(p_value)
        if n_value not in {1 << 14, 1 << 15} or r_value != 8 or p_value != 1:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.scrypt(
            str(password).encode("utf-8"),
            salt=salt,
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError, TypeError, UnicodeError, MemoryError):
        return False


def _safe_user(row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        key: row[key]
        for key in ("id", "username", "role", "display_name", "created_at", "last_login")
    }


def get_user(user_id: int, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any] | None:
    initialize_database(database_path)
    with _database(database_path) as connection:
        row = connection.execute(
            "SELECT id, username, role, display_name, created_at, last_login FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
    return _safe_user(row)


def register_user(username: str, password: str, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    username = str(username).strip()
    if not _USERNAME.fullmatch(username):
        raise AuthenticationError("Use a username or email with 3–254 supported characters.")
    password_hash = hash_password(password)
    initialize_database(database_path)
    try:
        with _database(database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, 'USER', ?)",
                (username, password_hash, _now()),
            )
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as error:
        raise AuthenticationError("An account with that username or email already exists.") from error
    user = get_user(user_id, database_path)
    assert user is not None
    return user


def bootstrap_developer(username: str, password: str, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    """Create the first developer account; subsequent bootstrap attempts are refused."""
    username = str(username).strip()
    if not _USERNAME.fullmatch(username):
        raise AuthenticationError("Use a username or email with 3–254 supported characters.")
    password_hash = hash_password(password)
    initialize_database(database_path)
    try:
        with _database(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM users WHERE role = 'DEVELOPER' LIMIT 1").fetchone():
                raise AuthenticationError("A developer account already exists; bootstrap is one-time only.")
            cursor = connection.execute(
                "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, 'DEVELOPER', ?)",
                (username, password_hash, _now()),
            )
            user_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as error:
        raise AuthenticationError("An account with that username or email already exists.") from error
    user = get_user(user_id, database_path)
    assert user is not None
    return user


def authenticate_user(username: str, password: str, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    initialize_database(database_path)
    with _database(database_path) as connection:
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (str(username).strip(),),
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            raise AuthenticationError("Invalid username/email or password.")
        user_id = int(row["id"])
        connection.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user_id))
    user = get_user(user_id, database_path)
    assert user is not None
    return user


def require_role(user_id: int, role: str | set[str], database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    user = get_user(user_id, database_path)
    roles = {role} if isinstance(role, str) else set(role)
    if user is None:
        raise AuthorizationError("Sign in to access this feature.")
    if user["role"] not in roles:
        raise AuthorizationError("Your account role is not permitted to access this feature.")
    return user


def update_profile(user_id: int, username: str, display_name: str, database_path=DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    require_role(user_id, {USER, DEVELOPER}, database_path)
    username = str(username).strip()
    display_name = str(display_name).strip()[:120]
    if not _USERNAME.fullmatch(username):
        raise AuthenticationError("Use a username or email with 3–254 supported characters.")
    initialize_database(database_path)
    try:
        with _database(database_path) as connection:
            connection.execute(
                "UPDATE users SET username = ?, display_name = ? WHERE id = ?",
                (username, display_name, int(user_id)),
            )
    except sqlite3.IntegrityError as error:
        raise AuthenticationError("An account with that username or email already exists.") from error
    user = get_user(user_id, database_path)
    assert user is not None
    return user


def list_users(actor_user_id: int, database_path=DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    require_role(actor_user_id, DEVELOPER, database_path)
    with _database(database_path) as connection:
        rows = connection.execute(
            "SELECT id, username, role, display_name, created_at, last_login FROM users ORDER BY id"
        ).fetchall()
    return [_safe_user(row) for row in rows if row is not None]
