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
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT is_demo FROM users WHERE username='existing'").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)

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


if __name__ == "__main__":
    unittest.main()
