"""
Automated tests for Nexus Learn Loop — Authentication Boundaries & Session Security
Runs natively via Python's built-in unittest module.
"""

import unittest
import tempfile
from pathlib import Path
from app import create_app
import database.database as db


class AuthAndBoundariesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.temp_dir.name) / "test_nexus.db"
        db.init_db(str(self.test_db))
        db.seed_defaults_if_empty(str(self.test_db))

        self.original_default = db.DEFAULT_DATABASE_PATH
        db.DEFAULT_DATABASE_PATH = self.test_db

        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        db.DEFAULT_DATABASE_PATH = self.original_default
        self.temp_dir.cleanup()

    def test_guest_cannot_access_dashboard(self):
        """Guest visitors must not silently login as demo learner; should be redirected."""
        res = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])

    def test_guest_cannot_access_profile(self):
        """Guest visitors must be redirected to login when visiting /profile."""
        res = self.client.get("/profile", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers["Location"])

    def test_api_current_user_unauthenticated(self):
        """Unauthenticated /api/current-user returns is_authenticated: False."""
        res = self.client.get("/api/current-user")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["is_authenticated"])
        self.assertEqual(data["user"]["username"], "Guest")

    def test_user_registration_and_dashboard_access(self):
        """New user can register and access their personal dashboard."""
        reg_res = self.client.post("/register", data={
            "username": "newcoder",
            "email": "newcoder@test.com",
            "password": "securepassword123",
            "track": "Web & Python Full-Stack"
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        # User should now be authenticated
        api_res = self.client.get("/api/current-user")
        data = api_res.get_json()
        self.assertTrue(data["is_authenticated"])
        self.assertEqual(data["user"]["username"], "newcoder")

        # Can access dashboard
        dash_res = self.client.get("/dashboard")
        self.assertEqual(dash_res.status_code, 200)

    def test_login_invalid_credentials(self):
        """Invalid credentials fail authentication and do not grant session."""
        res = self.client.post("/login", data={
            "username": "learner",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        api_res = self.client.get("/api/current-user")
        self.assertFalse(api_res.get_json()["is_authenticated"])

    def test_logout_clears_session(self):
        """Logging out clears session."""
        self.client.post("/login", data={
            "username": "learner",
            "password": "password123"
        }, follow_redirects=True)

        api_res = self.client.get("/api/current-user")
        self.assertTrue(api_res.get_json()["is_authenticated"])

        logout_res = self.client.post("/logout", follow_redirects=False)
        self.assertEqual(logout_res.status_code, 302)

        api_res_after = self.client.get("/api/current-user")
        self.assertFalse(api_res_after.get_json()["is_authenticated"])


if __name__ == "__main__":
    unittest.main()
