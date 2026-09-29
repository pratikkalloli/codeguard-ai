"""Streamlit AppTest coverage for login, role navigation, and empty/error states."""

import tempfile
import unittest
from pathlib import Path
import csv
import json
import subprocess
import sys
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from codeguard.auth import bootstrap_developer, get_user, register_user
import frontend.phase20_ui as phase20_ui

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Phase20UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.database = Path(cls.temp.name) / "ui-test.db"
        cls.user = register_user("ui-user@example.test", "temporary user password", cls.database)
        cls.developer = bootstrap_developer("ui-dev@example.test", "temporary developer password", cls.database)
        cls.entry = Path(cls.temp.name) / "app.py"
        cls.entry.write_text(
            "import os, sys\n"
            f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
            f"os.environ['CODEGUARD_DATABASE_PATH'] = {str(cls.database)!r}\n"
            "from frontend.phase20_ui import render_application\n"
            "render_application()\n",
            encoding="utf-8",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def _app(self):
        return AppTest.from_file(str(self.entry)).run(timeout=60)

    def _login(self, *, developer: bool = False):
        at = self._app()
        if developer:
            at.radio[0].set_value("DEVELOPER ACCESS").run(timeout=60)
        at.text_input[0].set_value(self.developer["username"] if developer else self.user["username"])
        at.text_input[1].set_value("temporary developer password" if developer else "temporary user password")
        at.button[0].click().run(timeout=60)
        return at

    @staticmethod
    def _select_page(at, page: str, *, developer: bool = False, timeout: int = 60):
        key = "cg_navigation_developer" if developer else "cg_navigation_user"
        at.radio(key=key).set_value(page).run(timeout=timeout)

    def test_landing_registration_login_and_user_dashboard(self) -> None:
        at = self._app()
        self.assertEqual(len(at.exception), 0)
        at.radio[0].set_value("GET STARTED").run(timeout=60)
        self.assertIn("Create a user account", [item.value for item in at.subheader])
        at.text_input[0].set_value("new-user@example.test")
        at.text_input[1].set_value("temporary registration password")
        at.text_input[2].set_value("temporary registration password")
        at.button[0].click().run(timeout=60)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(get_user(at.session_state["cg_user_id"], self.database)["username"], "new-user@example.test")
        self.assertTrue(any("No evaluations yet." in item.value for item in at.info))

    def test_phase20_module_imports_from_outside_project_root(self) -> None:
        probe = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); import phase20_ui, codeguard; "
            "expected = (Path(sys.argv[2]) / 'backend' / 'src').resolve(); "
            "actual = Path(codeguard.__file__).resolve(); "
            "assert actual.is_relative_to(expected), (actual, expected)"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe, str(PROJECT_ROOT / "frontend"), str(PROJECT_ROOT)],
            cwd=self.temp.name,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_user_pages_render_and_do_not_expose_developer_navigation(self) -> None:
        at = self._login()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(list(at.radio[0].options), ["HOME", "NEW EVALUATION", "MY EVALUATIONS", "COMPARE", "PROFILE"])
        for page in ("NEW EVALUATION", "MY EVALUATIONS", "COMPARE", "PROFILE"):
            self._select_page(at, page)
            self.assertEqual(len(at.exception), 0, page)
            if page == "MY EVALUATIONS":
                self.assertTrue(any("No evaluations" in item.value for item in at.info))

    def test_developer_login_and_separate_console_navigation(self) -> None:
        at = self._login(developer=True)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(list(at.radio[0].options), ["OVERVIEW", "EVALUATIONS", "LOGS", "SYSTEM HEALTH", "DOCKER", "ML", "EVIDENCE", "DATASETS", "USERS", "SETTINGS"])
        self.assertIn("No evaluations yet.", [item.value for item in at.info])
        for page in ("EVALUATIONS", "LOGS", "SYSTEM HEALTH", "DOCKER", "ML", "EVIDENCE", "USERS", "SETTINGS"):
            self._select_page(at, page, developer=True, timeout=90)
            self.assertEqual(len(at.exception), 0, page)

    def test_developer_dataset_page_uses_temporary_review_database(self) -> None:
        root = Path(self.temp.name) / "dataset-fixture"
        metadata_dir = root / "data" / "ml" / "research_dataset"
        metadata_dir.mkdir(parents=True)
        source_metadata = PROJECT_ROOT / "data" / "ml" / "research_dataset" / "dataset_metadata.json"
        (metadata_dir / "dataset_metadata.json").write_text(source_metadata.read_text(encoding="utf-8"), encoding="utf-8")
        phase16_root = root / "data" / "ml" / "phase16"
        queue = phase16_root / "review" / "review_queue.csv"
        queue.parent.mkdir(parents=True)
        source_queue = PROJECT_ROOT / "data" / "ml" / "phase16" / "review" / "review_queue.csv"
        with source_queue.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fieldnames = reader.fieldnames
            first = next(reader)
        with queue.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(first)
        with patch.object(phase20_ui, "PROJECT_ROOT", root), patch.object(phase20_ui, "PHASE16_DIR", phase16_root):
            at = self._login(developer=True)
            self._select_page(at, "DATASETS", developer=True, timeout=90)
        self.assertEqual(len(at.exception), 0)
        self.assertTrue((phase16_root / "review" / "reviews.sqlite3").is_file())
        self.assertEqual(at.radio(key="cg_navigation_developer").value, "DATASETS")
        self.assertGreaterEqual(len(at.metric), 1)

    def test_wrong_password_and_user_developer_login_are_rejected(self) -> None:
        at = self._app()
        at.text_input[0].set_value(self.user["username"])
        at.text_input[1].set_value("wrong password here")
        at.button[0].click().run(timeout=60)
        self.assertNotIn("cg_user_id", at.session_state)
        self.assertTrue(any("Invalid username/email or password" in item.value for item in at.error))
        at = self._app()
        at.radio[0].set_value("DEVELOPER ACCESS").run(timeout=60)
        at.text_input[0].set_value(self.user["username"])
        at.text_input[1].set_value("temporary user password")
        at.button[0].click().run(timeout=60)
        self.assertNotIn("cg_user_id", at.session_state)
        self.assertTrue(any("does not have developer access" in item.value for item in at.error))


if __name__ == "__main__":
    unittest.main()
