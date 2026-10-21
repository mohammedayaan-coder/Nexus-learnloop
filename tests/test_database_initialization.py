"""SQLite initialization and non-destructive migration tests."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import database.database as db


class DatabaseInitializationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "migration-test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_database_migrates_and_enforces_case_insensitive_uniqueness(self):
        db.init_db(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

        db.create_user("Casey", "casey@example.test", "hash", database_path=self.database_path)
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_user("casey", "other@example.test", "hash", database_path=self.database_path)
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_user("other", "CASEY@example.test", "hash", database_path=self.database_path)

    def test_legacy_users_table_gets_is_demo_column_without_losing_rows(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, "
                "email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, "
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                ("existing", "existing@example.test", "existing-hash"),
            )
            connection.commit()

        db.init_db(self.database_path)
        db.record_learning_activity(1, "legacy_activity", 250, database_path=self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT is_demo FROM users WHERE username='existing'").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM learning_activity WHERE user_id=1").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM learner_account_provenance WHERE user_id=1").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
        self.assertEqual(db.get_user_stats(1, database_path=self.database_path)["xp"], 250)
        self.assertEqual(db.get_leaderboard(
            database_path=self.database_path, include_demo=False, require_xp_records=True,
        ), [])

    def test_case_collisions_block_migration_without_deleting_users(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
            connection.executemany(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                [("Morgan", "one@example.test", "hash-1"),
                 ("morgan", "two@example.test", "hash-2")],
            )
            connection.commit()

        with self.assertRaises(db.DatabaseMigrationError):
            db.init_db(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 0)

    def test_migrations_add_idempotency_and_provenance_without_changing_history(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    quiz_name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total_questions INTEGER NOT NULL,
                    completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO users (username, email, password_hash)
                VALUES ('history-user', 'history@example.test', 'hash');
                INSERT INTO quiz_results (user_id, quiz_name, score, total_questions)
                VALUES (1, 'Saved attempt', 1, 1);
                PRAGMA user_version = 1;
            """)

        db.init_db(self.database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(quiz_results)")}
            self.assertIn("idempotency_key", columns)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)
            self.assertEqual(connection.execute(
                "SELECT id, quiz_name, score, total_questions FROM quiz_results"
            ).fetchone(), (1, "Saved attempt", 1, 1))
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM learner_account_provenance"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM study_session_submissions"
            ).fetchone()[0], 0)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM learner_provenance_reviews"
            ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
