import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app import app, database_service


class DatabaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        app.config.update(TESTING=True, DATABASE=str(self.database_path))
        with app.app_context():
            database_service.init_db()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def register(self):
        return self.client.post(
            "/register",
            data={
                "username": "nexuslearner",
                "email": "learner@example.com",
                "password": "safe-password-123",
            },
        )

    def test_registration_stores_password_hash_and_creates_profile(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)

        with closing(sqlite3.connect(self.database_path)) as connection:
            user = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                ("nexuslearner",),
            ).fetchone()
            profile = connection.execute(
                "SELECT user_id, bio, learning_goals, skills FROM learner_profiles"
            ).fetchone()

        self.assertIsNotNone(user)
        self.assertNotEqual(user[1], "safe-password-123")
        self.assertEqual(profile, (user[0], "", "", ""))

    def test_login_uses_username_or_email_and_feature_pages_render(self):
        self.register()
        self.client.get("/logout")
        bad_login = self.client.post(
            "/login",
            data={"username": "learner@example.com", "password": "incorrect-password"},
        )
        self.assertEqual(bad_login.status_code, 401)

        login = self.client.post(
            "/login",
            data={"username": "learner@example.com", "password": "safe-password-123"},
        )
        self.assertEqual(login.status_code, 302)

        for path in ("/dashboard", "/profile", "/timer", "/quiz", "/result"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_profile_and_study_session_are_saved_with_xp_activity(self):
        self.register()
        self.client.post(
            "/profile",
            data={
                "bio": "Backend learner",
                "learning_goals": "Build useful projects",
                "skills": "Python, SQL",
            },
        )
        response = self.client.post(
            "/study-sessions",
            data={
                "duration_minutes": "25",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)

        with closing(sqlite3.connect(self.database_path)) as connection:
            profile = connection.execute(
                "SELECT bio, learning_goals, skills FROM learner_profiles"
            ).fetchone()
            study_session = connection.execute(
                "SELECT duration_minutes FROM study_sessions"
            ).fetchone()
            activity = connection.execute(
                "SELECT activity_type, xp_earned FROM learning_activity"
            ).fetchone()

        self.assertEqual(profile, ("Backend learner", "Build useful projects", "Python, SQL"))
        self.assertEqual(study_session, (25,))
        self.assertEqual(activity, ("study_session", 30))

    def test_quiz_saves_score_and_only_awards_xp_for_correct_answer(self):
        self.register()
        self.client.post("/quiz", data={"answer": "A"})
        self.client.post("/quiz", data={"answer": "B"})

        with closing(sqlite3.connect(self.database_path)) as connection:
            results = connection.execute(
                "SELECT score, total_questions FROM quiz_results ORDER BY id"
            ).fetchall()
            quiz_xp = connection.execute(
                "SELECT xp_earned FROM learning_activity WHERE activity_type = 'quiz' ORDER BY id"
            ).fetchall()

        self.assertEqual(results, [(0, 1), (1, 1)])
        self.assertEqual(quiz_xp, [(0,), (20,)])

    def test_study_session_requires_login_and_valid_duration(self):
        anonymous_response = self.client.post(
            "/study-sessions",
            data={"duration_minutes": "25", "started_at": datetime.now(timezone.utc).isoformat()},
        )
        self.assertEqual(anonymous_response.status_code, 302)

        self.register()
        invalid_response = self.client.post(
            "/study-sessions",
            data={"duration_minutes": "0", "started_at": datetime.now(timezone.utc).isoformat()},
        )
        self.assertEqual(invalid_response.status_code, 302)

        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM study_sessions").fetchone()[0],
                0,
            )


if __name__ == "__main__":
    unittest.main()