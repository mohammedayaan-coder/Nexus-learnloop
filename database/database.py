"""SQLite persistence for Nexus Learn Loop."""

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


from services.streak_service import calculate_streak

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "instance" / "nexus.db"


def connect(database_path=None):
    """Open a configured SQLite connection with foreign keys enabled."""
    path = Path(database_path or DEFAULT_DATABASE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(database_path=None):
    """Create the application tables and indexes if they do not exist."""
    with closing(connect(database_path)) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Safe migration for existing databases to add is_demo
        try:
            connection.execute("ALTER TABLE users ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        connection.commit()


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
            "INSERT INTO learner_profiles (user_id, learning_goals) VALUES (?, ?)",
            (user_id, learning_goals),
        )
        connection.commit()
        return user_id


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


def record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned, database_path=None):
    with closing(connect(database_path)) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO quiz_results (user_id, quiz_name, score, total_questions)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, quiz_name, score, total_questions),
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
                COALESCE(SUM(learning_activity.xp_earned), 0) AS xp,
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


def get_leaderboard(database_path=None):
    with closing(connect(database_path)) as connection:
        return connection.execute(
            """
            SELECT users.id, users.username, users.is_demo, learner_profiles.learning_goals,
                   COALESCE(SUM(learning_activity.xp_earned), 0) AS xp
            FROM users
            LEFT JOIN learner_profiles ON learner_profiles.user_id = users.id
            LEFT JOIN learning_activity ON learning_activity.user_id = users.id
            GROUP BY users.id
            ORDER BY xp DESC, users.username COLLATE NOCASE ASC
            """
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

