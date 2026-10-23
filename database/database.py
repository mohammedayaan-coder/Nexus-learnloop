"""SQLite persistence for Nexus Learn Loop."""

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


from services.streak_service import calculate_streak

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "instance" / "nexus.db"
SCHEMA_VERSION = 4


def get_default_database_path():
    """Return the configured SQLite path, using Vercel's writable scratch space there.

    Vercel Functions package application files on a read-only filesystem. `/tmp`
    is writable for the lifetime of a function instance, but is not durable storage.
    """
    configured_path = os.getenv("NEXUS_DATABASE_PATH", "").strip()
    if configured_path:
        return Path(configured_path).expanduser()
    if os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV"):
        return Path("/tmp") / "nexus-learnloop.db"
    return DEFAULT_DATABASE_PATH


class DatabaseMigrationError(RuntimeError):
    """Raised when an existing database cannot be upgraded without data loss."""


def connect(database_path=None):
    """Open a configured SQLite connection with foreign keys enabled."""
    path = Path(database_path) if database_path is not None else get_default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(database_path=None):
    """Initialize schema and apply safe, versioned migrations in place.

    Version 1 adds case-insensitive unique indexes for usernames and emails.
    Version 2 adds a nullable quiz idempotency key without changing existing rows.
    Version 3 adds account provenance and study retry tables without backfilling users.
    Version 4 adds an append-only account provenance review log.
    Existing collisions are reported without changing or deleting user rows.
    """
    with closing(connect(database_path)) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise DatabaseMigrationError(
                    f"Database schema version {version} is newer than this application supports "
                    f"(maximum {SCHEMA_VERSION})."
                )
            if version < 1:
                user_columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
                }
                if "is_demo" not in user_columns:
                    connection.execute(
                        "ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0"
                    )

                username_collisions = connection.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM users "
                    "GROUP BY username COLLATE NOCASE HAVING COUNT(*) > 1)"
                ).fetchone()[0]
                email_collisions = connection.execute(
                    "SELECT COUNT(*) FROM (SELECT 1 FROM users "
                    "GROUP BY email COLLATE NOCASE HAVING COUNT(*) > 1)"
                ).fetchone()[0]
                if username_collisions or email_collisions:
                    raise DatabaseMigrationError(
                        "Database migration 1 cannot enforce case-insensitive account uniqueness: "
                        f"found {username_collisions} username and {email_collisions} email collision groups. "
                        "Resolve those duplicate identities manually, preserving the associated user data, "
                        "then restart the application."
                    )

                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_nocase "
                    "ON users (username COLLATE NOCASE)"
                )
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_nocase "
                    "ON users (email COLLATE NOCASE)"
                )
                connection.execute("PRAGMA user_version = 1")

            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version < 2:
                quiz_columns = {
                    row["name"] for row in connection.execute("PRAGMA table_info(quiz_results)").fetchall()
                }
                if "idempotency_key" not in quiz_columns:
                    connection.execute("ALTER TABLE quiz_results ADD COLUMN idempotency_key TEXT")
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_quiz_results_user_idempotency "
                    "ON quiz_results (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
                )
                connection.execute("PRAGMA user_version = 2")

            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version < 3:
                # Existing accounts remain unclassified: is_demo's historical
                # default is not evidence that an account is genuine.
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS learner_account_provenance (
                        user_id INTEGER PRIMARY KEY,
                        account_kind TEXT NOT NULL CHECK (account_kind IN ('registered', 'demo')),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS study_session_submissions (
                        user_id INTEGER NOT NULL,
                        submission_key TEXT NOT NULL,
                        session_id INTEGER NOT NULL,
                        PRIMARY KEY (user_id, submission_key),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (session_id) REFERENCES study_sessions(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("PRAGMA user_version = 3")

            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version < 4:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS learner_provenance_reviews (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        previous_kind TEXT CHECK (previous_kind IS NULL OR previous_kind IN ('registered', 'demo')),
                        account_kind TEXT NOT NULL CHECK (account_kind IN ('registered', 'demo')),
                        reviewed_by TEXT NOT NULL,
                        evidence TEXT NOT NULL,
                        reviewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
                    )
                """)
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_provenance_reviews_user "
                    "ON learner_provenance_reviews (user_id, reviewed_at)"
                )
                connection.execute("PRAGMA user_version = 4")
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def create_user(username, email, password_hash, learning_goals="", is_demo=0, database_path=None):
    """Create a user and their initially empty learner profile atomically."""
    with closing(connect(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, is_demo) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, is_demo),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO learner_account_provenance (user_id, account_kind) VALUES (?, ?)",
            (user_id, "demo" if is_demo else "registered"),
        )
        cursor.execute(
            "INSERT INTO learner_profiles (user_id, learning_goals) VALUES (?, ?)",
            (user_id, learning_goals),
        )
        connection.commit()
        return user_id


def review_account_provenance(user_id, account_kind, reviewed_by, evidence, database_path=None):
    """Explicitly classify an existing account and append a review audit row.

    `evidence` must identify an independent registration/provenance record. This
    operation changes no account identity, XP, quiz, or study history.
    """
    if account_kind not in {"registered", "demo"}:
        raise ValueError("Account kind must be 'registered' or 'demo'.")
    reviewed_by = str(reviewed_by or "").strip()
    evidence = str(evidence or "").strip()
    if not reviewed_by or len(reviewed_by) > 120:
        raise ValueError("Reviewer must be identified in 1 to 120 characters.")
    if not evidence or len(evidence) > 1000:
        raise ValueError("Evidence reference is required (up to 1000 characters).")

    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT id, is_demo FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            connection.rollback()
            raise ValueError("Account does not exist.")
        if account_kind == "registered" and user["is_demo"]:
            connection.rollback()
            raise ValueError("A demo account cannot be approved as a registered learner.")
        previous = connection.execute(
            "SELECT account_kind FROM learner_account_provenance WHERE user_id = ?", (user_id,)
        ).fetchone()
        previous_kind = previous["account_kind"] if previous else None
        connection.execute(
            "INSERT INTO learner_account_provenance (user_id, account_kind) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET account_kind = excluded.account_kind",
            (user_id, account_kind),
        )
        connection.execute(
            """INSERT INTO learner_provenance_reviews
               (user_id, previous_kind, account_kind, reviewed_by, evidence)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, previous_kind, account_kind, reviewed_by, evidence),
        )
        connection.commit()
        return previous_kind


def get_user_by_login(login, database_path=None):
    with closing(connect(database_path)) as connection:
        return connection.execute(
            """
            SELECT id, username, email, password_hash, is_demo, created_at
            FROM users
            WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
            """,
            (login, login),
        ).fetchone()


def get_user(user_id, database_path=None):
    with closing(connect(database_path)) as connection:
        return connection.execute(
            """
            SELECT users.id, users.username, users.email, users.is_demo, users.created_at,
                   learner_profiles.bio, learner_profiles.learning_goals,
                   learner_profiles.skills
            FROM users
            LEFT JOIN learner_profiles ON learner_profiles.user_id = users.id
            WHERE users.id = ?
            """,
            (user_id,),
        ).fetchone()


def update_profile(user_id, bio, learning_goals, skills, database_path=None):
    with closing(connect(database_path)) as connection:
        cursor = connection.execute(
            """
            UPDATE learner_profiles
            SET bio = ?, learning_goals = ?, skills = ?
            WHERE user_id = ?
            """,
            (bio, learning_goals, skills, user_id),
        )
        connection.commit()
        return cursor.rowcount == 1


def record_learning_activity(user_id, activity_type, xp_earned, database_path=None, completed_at=None):
    with closing(connect(database_path)) as connection:
        if completed_at:
            cursor = connection.execute(
                """
                INSERT INTO learning_activity (user_id, activity_type, xp_earned, completed_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, activity_type, xp_earned, completed_at),
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO learning_activity (user_id, activity_type, xp_earned)
                VALUES (?, ?, ?)
                """,
                (user_id, activity_type, xp_earned),
            )
        connection.commit()
        return cursor.lastrowid


def record_study_session(user_id, duration_minutes, xp_earned=30, database_path=None):
    with closing(connect(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO study_sessions (user_id, duration_minutes, started_at, completed_at)
            VALUES (
                ?,
                ?,
                datetime('now', ?),
                CURRENT_TIMESTAMP
            )
            """,
            (user_id, duration_minutes, f"-{duration_minutes} minutes"),
        )
        session_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO learning_activity (user_id, activity_type, xp_earned)
            VALUES (?, 'study_session', ?)
            """,
            (user_id, xp_earned),
        )
        connection.commit()
        return session_id


def record_study_session_submission(user_id, duration_minutes, xp_earned, submission_key,
                                    database_path=None):
    """Record one timer completion per user/request key, atomically with its XP."""
    if not isinstance(submission_key, str) or not submission_key or len(submission_key) > 128:
        raise ValueError("A study session submission key between 1 and 128 characters is required.")
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT session_id FROM study_session_submissions WHERE user_id = ? AND submission_key = ?",
            (user_id, submission_key),
        ).fetchone()
        if existing:
            connection.commit()
            return existing["session_id"], False

        cursor = connection.execute(
            """INSERT INTO study_sessions (user_id, duration_minutes, started_at, completed_at)
               VALUES (?, ?, datetime('now', ?), CURRENT_TIMESTAMP)""",
            (user_id, duration_minutes, f"-{duration_minutes} minutes"),
        )
        session_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO learning_activity (user_id, activity_type, xp_earned) VALUES (?, 'study_session', ?)",
            (user_id, xp_earned),
        )
        connection.execute(
            "INSERT INTO study_session_submissions (user_id, submission_key, session_id) VALUES (?, ?, ?)",
            (user_id, submission_key, session_id),
        )
        connection.commit()
        return session_id, True


def record_quiz_submission(user_id, quiz_name, score, total_questions, xp_earned,
                           idempotency_key, database_path=None):
    """Create one quiz attempt per user/request key and return (result_id, created)."""
    if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 128:
        raise ValueError("A quiz submission key between 1 and 128 characters is required.")
    with closing(connect(database_path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT id FROM quiz_results WHERE user_id = ? AND idempotency_key = ?",
            (user_id, idempotency_key),
        ).fetchone()
        if existing:
            connection.commit()
            return existing["id"], False
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO quiz_results (user_id, idempotency_key, quiz_name, score, total_questions)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, idempotency_key, quiz_name, score, total_questions),
        )
        result_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO learning_activity (user_id, activity_type, xp_earned)
            VALUES (?, 'quiz', ?)
            """,
            (user_id, xp_earned),
        )
        connection.commit()
        return result_id, True


def record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned,
                       database_path=None, idempotency_key=None):
    """Record a quiz result; callers with a request key get retry-safe behavior."""
    if idempotency_key is not None:
        result_id, _created = record_quiz_submission(
            user_id, quiz_name, score, total_questions, xp_earned,
            idempotency_key, database_path,
        )
        return result_id
    with closing(connect(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO quiz_results (user_id, quiz_name, score, total_questions) VALUES (?, ?, ?, ?)",
            (user_id, quiz_name, score, total_questions),
        )
        result_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO learning_activity (user_id, activity_type, xp_earned) VALUES (?, 'quiz', ?)",
            (user_id, xp_earned),
        )
        connection.commit()
        return result_id


def get_quiz_result(user_id, result_id, database_path=None):
    with closing(connect(database_path)) as connection:
        return connection.execute(
            """
            SELECT id, quiz_name, score, total_questions, completed_at
            FROM quiz_results
            WHERE user_id = ? AND id = ?
            """,
            (user_id, result_id),
        ).fetchone()


def get_user_stats(user_id, database_path=None):
    with closing(connect(database_path)) as connection:
        stats = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN learning_activity.xp_earned > 0
                                  THEN learning_activity.xp_earned ELSE 0 END), 0) AS xp,
                (SELECT COUNT(*) FROM learning_activity WHERE user_id = ?) AS activities_completed,
                (SELECT COUNT(*) FROM quiz_results WHERE user_id = ?) AS quizzes_solved,
                (SELECT COALESCE(SUM(score), 0) FROM quiz_results WHERE user_id = ?) AS correct_answers,
                (SELECT COALESCE(SUM(total_questions), 0) FROM quiz_results WHERE user_id = ?) AS questions_answered,
                (SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions WHERE user_id = ?) AS study_minutes,
                (SELECT COUNT(*) FROM study_sessions
                 WHERE user_id = ? AND date(completed_at) = date('now')) AS sessions_today
            FROM learning_activity
            WHERE learning_activity.user_id = ?
            """,
            (user_id, user_id, user_id, user_id, user_id, user_id, user_id),
        ).fetchone()
        result = dict(stats)
        result["accuracy"] = (
            round(result["correct_answers"] * 100 / result["questions_answered"])
            if result["questions_answered"]
            else 0
        )
        result["study_hours"] = round(result["study_minutes"] / 60, 1)

        # True calendar day streak calculation
        activity_dates = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT date(completed_at) FROM learning_activity WHERE user_id = ? ORDER BY date(completed_at) DESC",
                (user_id,),
            ).fetchall()
        ]
        result["streak"] = calculate_streak(activity_dates)
        return result


def get_leaderboard(database_path=None, *, include_demo=True, require_xp_records=False):
    with closing(connect(database_path)) as connection:
        return connection.execute(
            """
            SELECT users.id, users.username, users.is_demo, learner_profiles.learning_goals,
                   COALESCE(SUM(CASE WHEN learning_activity.xp_earned > 0
                                     THEN learning_activity.xp_earned ELSE 0 END), 0) AS xp
            FROM users
            LEFT JOIN learner_account_provenance ON learner_account_provenance.user_id = users.id
            LEFT JOIN learner_profiles ON learner_profiles.user_id = users.id
            LEFT JOIN learning_activity ON learning_activity.user_id = users.id
            WHERE (? = 1 OR (users.is_demo = 0 AND learner_account_provenance.account_kind = 'registered'))
            GROUP BY users.id
            HAVING (? = 0 OR SUM(CASE WHEN learning_activity.xp_earned > 0
                                       THEN learning_activity.xp_earned ELSE 0 END) > 0)
            ORDER BY xp DESC, users.username COLLATE NOCASE ASC
            """,
            (int(include_demo), int(require_xp_records)),
        ).fetchall()


def get_activity_counts(user_id, database_path=None, days=210):
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    counts = [0] * days
    with closing(connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT date(completed_at) AS activity_day, COUNT(*) AS activity_count
            FROM learning_activity
            WHERE user_id = ? AND date(completed_at) BETWEEN ? AND ?
            GROUP BY date(completed_at)
            """,
            (user_id, first_day.isoformat(), today.isoformat()),
        ).fetchall()
    for row in rows:
        day_index = (date.fromisoformat(row["activity_day"]) - first_day).days
        counts[day_index] = row["activity_count"]
    return counts


def seed_defaults_if_empty(database_path=None):
    """Seed initial demo users and benchmark activities if the database is brand new."""
    from werkzeug.security import generate_password_hash

    with closing(connect(database_path)) as connection:
        user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count > 0:
            return

    demo_pwd = generate_password_hash("password123")

    # 1. Main demo learner (sample account)
    learner_id = create_user("learner", "learner@nexus.org", demo_pwd, "Web & Python Full-Stack", is_demo=1, database_path=database_path)
    update_profile(
        learner_id,
        "Full-stack Python & Flask developer. Building daily habits and leveling up.",
        "Web & Python Full-Stack",
        "Python, Flask, SQLite, HTML5, CSS3, Git",
        database_path,
    )

    # 2. Benchmark leaderboard peers (marked as is_demo=1)
    elena_id = create_user("Elena Rostova", "elena@nexus.org", demo_pwd, "Full-Stack Track", is_demo=1, database_path=database_path)
    update_profile(
        elena_id,
        "Senior full-stack learner & open source contributor.",
        "Full-Stack Track",
        "Python, React, PostgreSQL, Docker",
        database_path,
    )

    marcus_id = create_user("Marcus Chen", "marcus@nexus.org", demo_pwd, "DevOps Track", is_demo=1, database_path=database_path)
    update_profile(
        marcus_id,
        "DevOps & Cloud Infrastructure engineer in training.",
        "DevOps Track",
        "Kubernetes, Linux, Terraform, Python",
        database_path,
    )

    amina_id = create_user("Amina Diop", "amina@nexus.org", demo_pwd, "AI & Data Track", is_demo=1, database_path=database_path)
    update_profile(
        amina_id,
        "AI researcher & machine learning practitioner.",
        "AI & Data Track",
        "PyTorch, Transformers, Python, SQL",
        database_path,
    )

    devon_id = create_user("Devon Taylor", "devon@nexus.org", demo_pwd, "Frontend Track", is_demo=1, database_path=database_path)
    update_profile(
        devon_id,
        "Modern UI/UX developer crafting tactile experiences.",
        "Frontend Track",
        "JavaScript, CSS3, Vue, Figma",
        database_path,
    )

    # Seed activities for leaderboard peers
    record_learning_activity(elena_id, "quiz_mastery", 2840, database_path)
    record_learning_activity(marcus_id, "quiz_mastery", 2610, database_path)
    record_learning_activity(amina_id, "quiz_mastery", 2490, database_path)
    record_learning_activity(devon_id, "quiz_mastery", 1280, database_path)

    # Seed study sessions and quizzes for demo learner (~1,420 XP)
    for _ in range(8):
        record_study_session(learner_id, 25, xp_earned=30, database_path=database_path)

    for q in range(15):
        record_quiz_result(learner_id, f"Daily Challenge #{q+1}", 1, 1, 20, database_path=database_path)

    # Seed 7 consecutive days of activity for demo learner so true streak is 7 days
    today = datetime.now(timezone.utc).date()
    for d in range(7):
        act_date = today - timedelta(days=d)
        record_learning_activity(
            learner_id,
            "daily_streak_checkin",
            100,
            database_path=database_path,
            completed_at=f"{act_date.isoformat()} 12:00:00"
        )

    # Additional XP to hit 1,420 milestone
    record_learning_activity(learner_id, "streak_bonus", 180, database_path=database_path)

