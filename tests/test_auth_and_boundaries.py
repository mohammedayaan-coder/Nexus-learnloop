"""
Automated tests for Nexus Learn Loop — Authentication Boundaries & Session Security
Runs natively via Python's built-in unittest module.
"""

import unittest
import os
import secrets
import tempfile
from pathlib import Path
from unittest import mock
from app import create_app
import database.database as db
from werkzeug.security import check_password_hash
from services.security import get_secret_key


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

    def test_stale_session_is_cleared_when_accessing_protected_route(self):
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 999999
            current_session["extra"] = "stale"
        response = self.client.get("/profile", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as current_session:
            self.assertNotIn("user_id", current_session)
            self.assertNotIn("extra", current_session)

    def test_public_page_routes_render(self):
        for path in ("/", "/leaderboard", "/quiz", "/result", "/timer", "/resources", "/lwb", "/ai-agent"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_login_form_has_csrf_token_and_no_prefilled_password(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="csrf_token"', response.data)
        self.assertNotIn(b'value="password123"', response.data)

    def test_api_current_user_unauthenticated(self):
        """Unauthenticated /api/current-user returns is_authenticated: False."""
        res = self.client.get("/api/current-user")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["is_authenticated"])
        self.assertEqual(data["user"]["username"], "Guest")

    def test_ai_status_never_returns_configured_key_material(self):
        marker = "test-secret-material-that-must-not-leak"
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": marker}):
            response = self.client.get("/api/ai-status")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(marker.encode(), response.data)

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

        stored_user = db.get_user_by_login("newcoder")
        self.assertTrue(check_password_hash(stored_user["password_hash"], "securepassword123"))
        self.assertNotEqual(stored_user["password_hash"], "securepassword123")

    def test_registration_rejects_duplicate_and_short_password(self):
        short = self.client.post("/register", data={
            "username": "shortpass", "email": "short@test.com", "password": "short"
        })
        self.assertEqual(short.status_code, 400)
        self.assertFalse(db.get_user_by_login("shortpass"))

        duplicate = self.client.post("/register", data={
            "username": "LEARNER", "email": "different@test.com", "password": "validpass123"
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_login_clears_prior_session_state(self):
        with self.client.session_transaction() as current_session:
            current_session["untrusted_value"] = "discard me"
            current_session["_csrf_token"] = "old-token"

        response = self.client.post("/login", data={"username": "learner", "password": "password123"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as current_session:
            self.assertIn("user_id", current_session)
            self.assertNotIn("untrusted_value", current_session)
            self.assertNotIn("_csrf_token", current_session)

    def test_state_change_requires_csrf_outside_testing_mode(self):
        self.app.config["TESTING"] = False
        response = self.client.post("/register", data={
            "username": "csrfuser", "email": "csrf@test.com", "password": "validpass123"
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(db.get_user_by_login("csrfuser"))

    def test_state_change_accepts_a_valid_csrf_token(self):
        self.app.config["TESTING"] = False
        token = "a-valid-session-bound-token"
        with self.client.session_transaction() as current_session:
            current_session["_csrf_token"] = token
        response = self.client.post("/register", data={
            "csrf_token": token, "username": "csrfuser", "email": "csrf@test.com",
            "password": "validpass123",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(db.get_user_by_login("csrfuser"))

    def test_production_requires_long_environment_secret(self):
        with mock.patch.dict(os.environ, {"FLASK_ENV": "production", "SECRET_KEY": "short"}):
            with self.assertRaises(RuntimeError):
                get_secret_key()
        strong_key = secrets.token_urlsafe(32)
        with mock.patch.dict(os.environ, {"FLASK_ENV": "production", "SECRET_KEY": strong_key}):
            self.assertEqual(get_secret_key(), strong_key)

    def test_production_never_seeds_demo_data(self):
        environment = {"FLASK_ENV": "production", "SECRET_KEY": secrets.token_urlsafe(32)}
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(db, "init_db"), \
                mock.patch.object(db, "seed_defaults_if_empty") as seed:
            create_app()
        seed.assert_not_called()

    def test_test_environment_seeds_demo_data(self):
        environment = {"FLASK_ENV": "testing", "SECRET_KEY": secrets.token_urlsafe(32)}
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(db, "init_db"), \
                mock.patch.object(db, "seed_defaults_if_empty") as seed:
            create_app()
        seed.assert_called_once_with()

    def test_database_initialization_failure_stops_app_startup(self):
        environment = {"FLASK_ENV": "production", "SECRET_KEY": secrets.token_urlsafe(32)}
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(db, "init_db", side_effect=OSError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "Database initialization failed"):
                create_app()

    def test_user_cannot_read_another_users_quiz_result(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        from database.database import record_quiz_result
        result_id = record_quiz_result(1, "Owned quiz", 1, 1, 20)

        with self.client.session_transaction() as current_session:
            current_session["user_id"] = 2
        result = self.client.get(f"/result?id={result_id}")
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(b"Owned quiz", result.data)

    def test_profile_quiz_and_timer_writes_persist_for_signed_in_user(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]

        profile_response = self.client.post("/profile", data={
            "bio": "Testing profile persistence", "learning_goals": "Flask", "skills": "Python"
        })
        self.assertEqual(profile_response.status_code, 302)
        self.assertEqual(db.get_user(user_id)["bio"], "Testing profile persistence")

        before_quizzes = db.get_user_stats(user_id)["quizzes_solved"]
        quiz_response = self.client.post("/quiz", data={"quiz_id": "jinja2-interpolation", "selected_option": "B"})
        self.assertEqual(quiz_response.status_code, 302)
        self.assertEqual(db.get_user_stats(user_id)["quizzes_solved"], before_quizzes + 1)

        before_minutes = db.get_user_stats(user_id)["study_minutes"]
        timer_response = self.client.post("/timer", data={"duration_minutes": "25"})
        self.assertEqual(timer_response.status_code, 302)
        self.assertEqual(db.get_user_stats(user_id)["study_minutes"], before_minutes + 25)

    def test_authenticated_activity_api_records_session(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        response = self.client.post("/api/record-study-session", json={"duration_minutes": 25})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_login_invalid_credentials(self):
        """Invalid credentials fail authentication and do not grant session."""
        res = self.client.post("/login", data={
            "username": "learner",
            "password": "wrongpassword"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        api_res = self.client.get("/api/current-user")
        self.assertFalse(api_res.get_json()["is_authenticated"])

    def test_login_lookup_is_case_insensitive_for_username_and_email(self):
        response = self.client.post("/login", data={
            "username": "LEARNER@NEXUS.ORG", "password": "password123"
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.get("/api/current-user").get_json()["is_authenticated"])

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
