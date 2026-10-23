"""
Automated tests for Nexus Learn Loop — Authentication Boundaries & Session Security
Runs natively via Python's built-in unittest module.
"""

import unittest
import os
import re
import secrets
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import mock
from app import create_app
import database.database as db
from werkzeug.security import check_password_hash, generate_password_hash
from services.security import get_runtime_environment, get_secret_key


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

    def next_quiz_submission_id(self):
        response = self.client.get("/quiz")
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="submission_id" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode("ascii")

    def next_study_submission_id(self):
        response = self.client.get("/timer")
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="submission_id" value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode("ascii")

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

    def test_vercel_environment_is_detected_as_production_and_requires_secret(self):
        with mock.patch.dict(os.environ, {
            "VERCEL_ENV": "production", "FLASK_ENV": "", "APP_ENV": "", "ENV": "",
        }, clear=False):
            self.assertEqual(get_runtime_environment(), "production")
            with mock.patch.dict(os.environ, {"SECRET_KEY": ""}):
                with self.assertRaisesRegex(RuntimeError, "high-entropy SECRET_KEY"):
                    get_secret_key()

    def test_vercel_production_app_starts_without_seeding_demo_data(self):
        database_path = Path(self.temp_dir.name) / "vercel.db"
        environment = {"VERCEL_ENV": "production", "FLASK_ENV": "", "APP_ENV": "", "ENV": "",
                       "SECRET_KEY": secrets.token_urlsafe(32),
                       "NEXUS_DATABASE_PATH": str(database_path)}
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(db, "seed_defaults_if_empty") as seed:
            vercel_app = create_app()
        self.assertEqual(vercel_app.config["RUNTIME_ENVIRONMENT"], "production")
        seed.assert_not_called()

    def test_vercel_preview_requires_a_strong_secret(self):
        with mock.patch.dict(os.environ, {"VERCEL_ENV": "preview", "SECRET_KEY": ""}):
            self.assertEqual(get_runtime_environment(), "preview")
            with self.assertRaisesRegex(RuntimeError, "high-entropy SECRET_KEY"):
                get_secret_key()

    def test_top_level_app_import_succeeds_in_vercel_production(self):
        database_path = Path(self.temp_dir.name) / "vercel-import.db"
        environment = os.environ.copy()
        environment.update({
            "VERCEL": "1",
            "VERCEL_ENV": "production",
            "FLASK_ENV": "",
            "APP_ENV": "",
            "ENV": "",
            "SECRET_KEY": secrets.token_urlsafe(32),
            "NEXUS_DATABASE_PATH": str(database_path),
        })
        completed = subprocess.run(
            [sys.executable, "-c", "import app; assert hasattr(app.app, 'wsgi_app')"],
            cwd=Path(__file__).resolve().parent.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_production_never_seeds_demo_data(self):
        environment = {"FLASK_ENV": "production", "SECRET_KEY": secrets.token_urlsafe(32)}
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(db, "init_db"), \
                mock.patch.object(db, "seed_defaults_if_empty") as seed:
            create_app()
        seed.assert_not_called()

    def test_production_leaderboard_excludes_demo_and_unearned_accounts(self):
        strong_hash = generate_password_hash("securepass123")
        first_id = db.create_user("real-first", "first@example.test", strong_hash)
        second_id = db.create_user("real-second", "second@example.test", strong_hash)
        empty_id = db.create_user("real-empty", "empty@example.test", strong_hash)
        db.record_learning_activity(first_id, "quiz", 80)
        db.record_learning_activity(second_id, "quiz", 120)

        production_secret = secrets.token_urlsafe(32)
        with mock.patch.dict(os.environ, {"FLASK_ENV": "production", "SECRET_KEY": production_secret}), \
                mock.patch.object(db, "init_db"):
            production_app = create_app()
        production_app.config["TESTING"] = True
        client = production_app.test_client()

        api_rows = client.get("/api/leaderboard").get_json()["rankings"]
        self.assertEqual([row["id"] for row in api_rows], [second_id, first_id])
        self.assertEqual([row["xp"] for row in api_rows], [120, 80])
        self.assertNotIn(empty_id, [row["id"] for row in api_rows])
        self.assertFalse(any(row["is_demo"] for row in api_rows))

        demo_id = db.get_user_by_login("learner")["id"]
        with client.session_transaction() as current_session:
            current_session["user_id"] = demo_id
        self.assertFalse(client.get("/api/current-user").get_json()["is_authenticated"])

        with client.session_transaction() as current_session:
            current_session["user_id"] = first_id
        current_user = client.get("/api/current-user").get_json()
        self.assertEqual(current_user["stats"]["rank"], 2)
        with client.session_transaction() as current_session:
            current_session["user_id"] = empty_id
        self.assertEqual(client.get("/api/current-user").get_json()["stats"]["rank"], "-")
        with client.session_transaction() as current_session:
            current_session["user_id"] = first_id
        dashboard_response = client.get("/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn(b"real-second", dashboard_response.data)
        leaderboard_response = client.get("/leaderboard")
        self.assertEqual(leaderboard_response.status_code, 200)
        self.assertIn(b"real-second", leaderboard_response.data)
        self.assertIn(b">80 XP<", leaderboard_response.data)
        self.assertNotIn(b">120 XP<", leaderboard_response.data.split(b"Community Leaderboard", 1)[0])
        for sample_name in (b"Elena Rostova", b"Marcus Chen", b"Amina Diop"):
            self.assertNotIn(sample_name, leaderboard_response.data)

        with mock.patch.dict(os.environ, {
            "FLASK_ENV": "testing", "SECRET_KEY": secrets.token_urlsafe(32),
        }), mock.patch.object(db, "init_db"), \
                mock.patch.object(db, "seed_defaults_if_empty"):
            development_app = create_app()
        development_app.config["TESTING"] = True
        development_page = development_app.test_client().get("/leaderboard")
        for sample_name in (b"Elena Rostova", b"Marcus Chen", b"Amina Diop"):
            self.assertIn(sample_name, development_page.data)

    def test_legacy_provenance_approval_is_audited_and_preserves_history(self):
        legacy_id = db.create_user(
            "legacy-approved", "legacy-approved@example.test",
            generate_password_hash("securepass123"),
        )
        db.record_learning_activity(legacy_id, "quiz", 75)
        db.record_quiz_result(legacy_id, "Existing attempt", 2, 3, 20)
        with closing(db.connect()) as connection:
            connection.execute(
                "DELETE FROM learner_account_provenance WHERE user_id = ?", (legacy_id,)
            )
            connection.commit()
        before = db.get_user_stats(legacy_id)

        # A reviewer must explicitly classify the legacy account with an evidence reference.
        with self.assertRaises(ValueError):
            db.review_account_provenance(legacy_id, "registered", "operator-1", "")
        db.review_account_provenance(
            legacy_id, "registered", "operator-1", "registration ticket REG-1042",
        )
        after = db.get_user_stats(legacy_id)
        self.assertEqual(after["xp"], before["xp"])
        self.assertEqual(after["quizzes_solved"], before["quizzes_solved"])
        with closing(db.connect()) as connection:
            audit = connection.execute(
                "SELECT previous_kind, account_kind, reviewed_by, evidence "
                "FROM learner_provenance_reviews WHERE user_id = ?", (legacy_id,),
            ).fetchone()
            self.assertEqual(tuple(audit), (None, "registered", "operator-1", "registration ticket REG-1042"))

        self.app.config["RUNTIME_ENVIRONMENT"] = "production"
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = legacy_id
        rankings = self.client.get("/api/leaderboard").get_json()["rankings"]
        approved = next(row for row in rankings if row["id"] == legacy_id)
        current = self.client.get("/api/current-user").get_json()
        self.assertEqual(approved["xp"], 95)
        self.assertEqual(current["stats"]["xp"], approved["xp"])
        self.assertEqual(current["stats"]["rank"], next(
            rank for rank, row in enumerate(rankings, 1) if row["id"] == legacy_id
        ))
        page = self.client.get("/leaderboard")
        self.assertIn(b"95 XP", page.data)

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
        quiz_response = self.client.post("/quiz", data={
            "quiz_id": "jinja2-interpolation", "selected_option": "B",
            "submission_id": self.next_quiz_submission_id(),
        })
        self.assertEqual(quiz_response.status_code, 302)
        self.assertEqual(db.get_user_stats(user_id)["quizzes_solved"], before_quizzes + 1)

        before_minutes = db.get_user_stats(user_id)["study_minutes"]
        timer_response = self.client.post("/timer", data={
            "duration_minutes": "25", "submission_id": self.next_study_submission_id(),
        })
        self.assertEqual(timer_response.status_code, 302)
        self.assertEqual(db.get_user_stats(user_id)["study_minutes"], before_minutes + 25)

    def test_repeated_profile_saves_do_not_award_xp_or_activity(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]
        before_stats = db.get_user_stats(user_id)
        before_leaderboard = next(
            row["xp"] for row in db.get_leaderboard() if row["id"] == user_id
        )

        for index in range(3):
            response = self.client.post("/profile", data={
                "bio": f"Profile bio {index}",
                "learning_goals": f"Goal {index}",
                "skills": f"Skill {index}",
            })
            self.assertEqual(response.status_code, 302)

        after_stats = db.get_user_stats(user_id)
        after_leaderboard = next(
            row["xp"] for row in db.get_leaderboard() if row["id"] == user_id
        )
        self.assertEqual(after_stats["xp"], before_stats["xp"])
        self.assertEqual(after_stats["activities_completed"], before_stats["activities_completed"])
        self.assertEqual(after_stats["streak"], before_stats["streak"])
        self.assertEqual(after_leaderboard, before_leaderboard)

        profile = db.get_user(user_id)
        self.assertEqual(profile["bio"], "Profile bio 2")
        self.assertEqual(profile["learning_goals"], "Goal 2")
        self.assertEqual(profile["skills"], "Skill 2")

        page = self.client.get("/profile")
        self.assertIn(b"Update your bio, goals, and skills", page.data)
        self.assertIn(b"Save Profile", page.data)
        self.assertNotIn(b"+15 XP", page.data)

    def test_quiz_result_and_dashboard_show_persisted_stats_and_refresh_is_read_only(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]
        before = db.get_user_stats(user_id)

        submitted = self.client.post("/quiz", data={
            "quiz_id": "jinja2-interpolation", "selected_option": "B",
            "submission_id": self.next_quiz_submission_id(),
        })
        self.assertEqual(submitted.status_code, 302)
        result_url = submitted.headers["Location"]
        after_submission = db.get_user_stats(user_id)
        self.assertEqual(after_submission["quizzes_solved"], before["quizzes_solved"] + 1)
        self.assertEqual(after_submission["xp"], before["xp"] + 20)

        result_page = self.client.get(result_url)
        self.assertEqual(result_page.status_code, 200)
        self.assertIn(f">{after_submission['streak']} Days<".encode(), result_page.data)
        self.assertIn(f">{after_submission['xp']} XP<".encode(), result_page.data)
        self.assertIn(b">100%<", result_page.data)
        self.assertNotIn(b"8 Days", result_page.data)

        dashboard_page = self.client.get("/dashboard")
        self.assertEqual(dashboard_page.status_code, 200)
        self.assertIn(f'data-stat="streak-val">{after_submission["streak"]}'.encode(), dashboard_page.data)
        formatted_xp = f'{after_submission["xp"]:,}'
        self.assertIn(f'data-stat="xp-val">{formatted_xp}'.encode(), dashboard_page.data)

        # The quiz route uses POST/Redirect/GET; refreshing the result GET adds no result or XP.
        self.client.get(result_url)
        after_refresh = db.get_user_stats(user_id)
        self.assertEqual(after_refresh["quizzes_solved"], after_submission["quizzes_solved"])
        self.assertEqual(after_refresh["xp"], after_submission["xp"])

    def test_quiz_retry_is_idempotent_and_new_submission_allows_retake(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]
        before = db.get_user_stats(user_id)
        submission_id = self.next_quiz_submission_id()
        payload = {
            "quiz_id": "jinja2-interpolation", "selected_option": "B",
            "submission_id": submission_id,
        }

        first = self.client.post("/quiz", data=payload)
        second = self.client.post("/quiz", data=payload)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(first.headers["Location"], second.headers["Location"])
        after = db.get_user_stats(user_id)
        self.assertEqual(after["quizzes_solved"], before["quizzes_solved"] + 1)
        self.assertEqual(after["xp"], before["xp"] + 20)

        retake = self.client.post("/quiz", data={
            "quiz_id": "jinja2-interpolation", "selected_option": "B",
            "submission_id": self.next_quiz_submission_id(),
        })
        self.assertEqual(retake.status_code, 302)
        after_retake = db.get_user_stats(user_id)
        self.assertEqual(after_retake["quizzes_solved"], before["quizzes_solved"] + 2)
        self.assertEqual(after_retake["xp"], before["xp"] + 40)

    def test_authenticated_activity_api_records_session(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        response = self.client.post("/api/record-study-session", json={
            "duration_minutes": 25, "submission_id": "study-api-attempt-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_study_session_retry_awards_xp_once_and_ignores_submitted_xp(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]
        before = db.get_user_stats(user_id)
        submission_id = self.next_study_submission_id()
        payload = {"duration_minutes": "25", "submission_id": submission_id,
                   "xp_earned": "999999"}

        first = self.client.post("/timer", data=payload)
        second = self.client.post("/timer", data=payload)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        after = db.get_user_stats(user_id)
        self.assertEqual(after["xp"], before["xp"] + 30)
        self.assertEqual(after["study_minutes"], before["study_minutes"] + 25)

    def test_zero_xp_header_and_logged_in_header_use_own_persisted_xp(self):
        fresh_id = db.create_user("zero-xp-user", "zero@example.test", generate_password_hash("securepass123"))
        with self.client.session_transaction() as current_session:
            current_session["user_id"] = fresh_id
        zero_page = self.client.get("/leaderboard")
        self.assertIn(b">0 XP<", zero_page.data)

        db.record_learning_activity(fresh_id, "quiz", 35)
        leader_id = db.create_user("higher-xp-user", "higher@example.test", generate_password_hash("securepass123"))
        db.record_learning_activity(leader_id, "quiz", 90)
        own_page = self.client.get("/leaderboard")
        header = own_page.data.split(b"<!-- MAIN LEADERBOARD -->", 1)[0]
        self.assertIn(b">35 XP<", header)
        self.assertNotIn(b">90 XP<", header)

    def test_quiz_api_requires_and_honors_submission_idempotency_key(self):
        self.client.post("/login", data={"username": "learner", "password": "password123"})
        user_id = db.get_user_by_login("learner")["id"]
        before = db.get_user_stats(user_id)
        missing_key = self.client.post("/api/record-quiz", json={"selected_option": "B"})
        self.assertEqual(missing_key.status_code, 400)

        payload = {"selected_option": "B", "submission_id": "api-attempt-1"}
        first = self.client.post("/api/record-quiz", json=payload).get_json()
        retry = self.client.post("/api/record-quiz", json=payload).get_json()
        self.assertTrue(first["created"])
        self.assertFalse(retry["created"])
        self.assertEqual(first["result_id"], retry["result_id"])
        after = db.get_user_stats(user_id)
        self.assertEqual(after["quizzes_solved"], before["quizzes_solved"] + 1)
        self.assertEqual(after["xp"], before["xp"] + 20)

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
