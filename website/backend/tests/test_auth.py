from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai import main
from aegis_ai.auth import AccountStore
from aegis_ai.settings import Settings


class AuthApiTests(unittest.TestCase):
    def test_register_login_me_and_logout_use_hashed_passwords(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            settings = Settings(_env_file=None, aegis_database_path="data/test.sqlite3")
            store = AccountStore(project_root, settings)

            with patch.object(main, "account_store", store), TestClient(main.app) as client:
                register = client.post(
                    "/api/auth/register",
                    json={
                        "name": "Gabriel",
                        "email": "gabriel@example.com",
                        "password": "correct horse",
                        "confirm_password": "correct horse",
                    },
                )
                self.assertEqual(register.status_code, 200)
                payload = register.json()
                self.assertEqual(payload["token_type"], "bearer")
                self.assertTrue(payload["token"].startswith("aegis_"))
                self.assertEqual(payload["user"]["email"], "gabriel@example.com")
                self.assertEqual(payload["user"]["role"], "user")
                self.assertEqual(payload["user"]["status"], "active")

                with closing(store._connect()) as conn:  # noqa: SLF001 - test verifies storage safety.
                    row = conn.execute("select password_hash from user_accounts where email = ?", ("gabriel@example.com",)).fetchone()
                self.assertIsNotNone(row)
                self.assertNotEqual(row["password_hash"], "correct horse")
                self.assertIn("pbkdf2_sha256", row["password_hash"])

                login = client.post(
                    "/api/auth/login",
                    json={"email": "gabriel@example.com", "password": "correct horse", "remember_me": True},
                )
                self.assertEqual(login.status_code, 200)
                token = login.json()["token"]

                me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json()["user"]["name"], "Gabriel")

                logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(logout.status_code, 200)

                expired = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(expired.status_code, 401)

    def test_register_rejects_duplicate_email_and_password_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AccountStore(Path(tmp), Settings(_env_file=None, aegis_database_path="data/test.sqlite3"))

            with patch.object(main, "account_store", store), TestClient(main.app) as client:
                mismatch = client.post(
                    "/api/auth/register",
                    json={
                        "name": "Aegis User",
                        "email": "user@example.com",
                        "password": "long-password",
                        "confirm_password": "different-password",
                    },
                )
                self.assertEqual(mismatch.status_code, 400)

                first = client.post(
                    "/api/auth/register",
                    json={
                        "name": "Aegis User",
                        "email": "user@example.com",
                        "password": "long-password",
                        "confirm_password": "long-password",
                    },
                )
                self.assertEqual(first.status_code, 200)

                duplicate = client.post(
                    "/api/auth/register",
                    json={
                        "name": "Another User",
                        "email": "USER@example.com",
                        "password": "long-password",
                        "confirm_password": "long-password",
                    },
                )
                self.assertEqual(duplicate.status_code, 400)


if __name__ == "__main__":
    unittest.main()
