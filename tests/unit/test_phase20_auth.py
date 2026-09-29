"""Local account, role, evaluation-isolation, and log-redaction tests."""

import json
import tempfile
import unittest
from pathlib import Path

from codeguard.access import get_accessible_evaluation, list_accessible_evaluations
from codeguard.auth import (
    DEVELOPER,
    USER,
    AuthenticationError,
    AuthorizationError,
    authenticate_user,
    bootstrap_developer,
    hash_password,
    list_users,
    register_user,
    require_role,
    verify_password,
)
from codeguard.events import list_events, log_event
from codeguard.storage import save_evaluation


class Phase20AuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "phase20.db"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_passwords_are_scrypt_hashes_and_round_trip(self) -> None:
        encoded = hash_password("long correct horse battery")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertNotIn("long correct horse battery", encoded)
        self.assertTrue(verify_password("long correct horse battery", encoded))
        self.assertFalse(verify_password("incorrect password", encoded))

    def test_registration_login_and_invalid_credentials(self) -> None:
        user = register_user("reviewer@example.test", "long correct horse battery", self.database)
        self.assertEqual(user["role"], USER)
        self.assertNotIn("password", user)
        self.assertNotIn("password_hash", user)
        self.assertEqual(authenticate_user("REVIEWER@example.test", "long correct horse battery", self.database)["id"], user["id"])
        with self.assertRaises(AuthenticationError):
            authenticate_user("reviewer@example.test", "wrong password", self.database)

    def test_invalid_password_and_duplicate_registration_are_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            register_user("short", "bad", self.database)
        register_user("abc", "long correct horse battery", self.database)
        with self.assertRaises(AuthenticationError):
            register_user("ABC", "another long password here", self.database)

    def test_developer_bootstrap_is_one_time_and_role_checked(self) -> None:
        developer = bootstrap_developer("dev@example.test", "a different long password", self.database)
        self.assertEqual(developer["role"], DEVELOPER)
        with self.assertRaises(AuthenticationError):
            bootstrap_developer("other@example.test", "another different password", self.database)
        self.assertEqual(require_role(developer["id"], DEVELOPER, self.database)["role"], DEVELOPER)
        user = register_user("user@example.test", "a third long password", self.database)
        with self.assertRaises(AuthorizationError):
            require_role(user["id"], DEVELOPER, self.database)
        with self.assertRaises(AuthorizationError):
            list_users(user["id"], self.database)

    def test_user_isolation_and_developer_all_access(self) -> None:
        user_one = register_user("first@example.test", "first user password here", self.database)
        user_two = register_user("second@example.test", "second user password here", self.database)
        developer = bootstrap_developer("dev@example.test", "developer password here", self.database)
        own_id = save_evaluation("My question", "My answer", [], "", database_path=self.database, owner_user_id=user_one["id"])
        other_id = save_evaluation("Private question", "Private answer", [], "", database_path=self.database, owner_user_id=user_two["id"])
        self.assertEqual([row["id"] for row in list_accessible_evaluations(user_one["id"], database_path=self.database)], [own_id])
        self.assertIsNone(get_accessible_evaluation(user_one["id"], other_id, database_path=self.database))
        self.assertEqual(len(list_accessible_evaluations(developer["id"], database_path=self.database)), 2)
        self.assertIsNotNone(get_accessible_evaluation(developer["id"], other_id, database_path=self.database))

    def test_structured_events_are_filterable_and_secrets_redacted(self) -> None:
        user = register_user("logger@example.test", "logger account password", self.database)
        developer = bootstrap_developer("logs-dev@example.test", "a logs developer password", self.database)
        log_event(
            "EVALUATION_FAILED", user_id=user["id"], evaluation_id=1285, level="ERROR",
            component="docker", status="failed", error_type="TimeoutError",
            details={"password": "dont-log-this", "api_key": "sk-test-secret-123456", "stage": "run"},
            database_path=self.database,
        )
        rows = list_events(developer["id"], errors_only=True, evaluation_id="1285", database_path=self.database)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evaluation_id"], "EVL-0001285")
        self.assertEqual(rows[0]["details"]["password"], "[REDACTED]")
        self.assertNotIn("dont-log-this", json.dumps(rows))
        self.assertEqual(rows[0]["actor"], user["username"])


if __name__ == "__main__":
    unittest.main()
