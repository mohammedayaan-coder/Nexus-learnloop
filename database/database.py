"""SQLite persistence for Nexus Learn Loop."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from flask import current_app, g
from werkzeug.security import check_password_hash, generate_password_hash


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "instance" / "nexus.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db() -> sqlite3.Connection:
    """Return the request-scoped SQLite connection."""
    if "database" not in g:
        database_path = Path(current_app.config.get("DATABASE", DEFAULT_DATABASE_PATH))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        g.database = connection
    return g.database


def close_db(_error: BaseException | None = None) -> None:
    connection = g.pop("database", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    """Create any missing application tables without replacing existing data."""
    connection = get_db()
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def create_user(username: str, email: str, password: str) -> sqlite3.Row:
    connection = get_db()
    with connection:
        cursor = connection.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, generate_password_hash(password)),
        )
        user_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO learner_profiles (user_id) VALUES (?)",
            (user_id,),
        )
    user = get_user_by_id(user_id)
    if user is None:
        raise RuntimeError("Newly created user could not be loaded.")
    return user


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def get_user_by_identifier(identifier: str) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT id, username, email, password_hash, created_at
        FROM users
        WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE
        """,
        (identifier, identifier),
    ).fetchone()


def verify_password(user: sqlite3.Row, password: str) -> bool:
    return check_password_hash(user["password_hash"], password)


def get_learner_profile(user_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT id, user_id, bio, learning_goals, skills
        FROM learner_profiles
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()


def update_learner_profile(
    user_id: int,
    bio: str,
    learning_goals: str,
    skills: str,
) -> None:
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO learner_profiles (user_id, bio, learning_goals, skills)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                bio = excluded.bio,
                learning_goals = excluded.learning_goals,
                skills = excluded.skills
            """,
            (user_id, bio, learning_goals, skills),
        )


def record_learning_activity(user_id: int, activity_type: str, xp_earned: int) -> int:
    if xp_earned < 0:
        raise ValueError("XP earned cannot be negative.")
    with get_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO learning_activity (user_id, activity_type, xp_earned)
            VALUES (?, ?, ?)
            """,
            (user_id, activity_type, xp_earned),
        )
        return int(cursor.lastrowid)


def record_study_session(
    user_id: int,
    duration_minutes: int,
    started_at: str,
) -> int:
    if not 1 <= duration_minutes <= 180:
        raise ValueError("Study session duration must be between 1 and 180 minutes.")
    with get_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO study_sessions (user_id, duration_minutes, started_at)
            VALUES (?, ?, ?)
            """,
            (user_id, duration_minutes, started_at),
        )
        session_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO learning_activity (user_id, activity_type, xp_earned)
            VALUES (?, 'study_session', 30)
            """,
            (user_id,),
        )
        return session_id


def record_quiz_result(
    user_id: int,
    quiz_name: str,
    score: int,
    total_questions: int,
) -> int:
    if total_questions <= 0 or score < 0 or score > total_questions:
        raise ValueError("Quiz score must be between zero and the number of questions.")
    xp_earned = 20 if score == total_questions else 0
    with get_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO quiz_results (user_id, quiz_name, score, total_questions)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, quiz_name, score, total_questions),
        )
        result_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO learning_activity (user_id, activity_type, xp_earned)
            VALUES (?, 'quiz', ?)
            """,
            (user_id, xp_earned),
        )
        return result_id


def get_latest_quiz_result(user_id: int) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT id, quiz_name, score, total_questions, completed_at
        FROM quiz_results
        WHERE user_id = ?
        ORDER BY completed_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def get_user_stats(user_id: int) -> dict[str, Any]:
    connection = get_db()
    activity = connection.execute(
        """
        SELECT COALESCE(SUM(xp_earned), 0) AS total_xp,
               COUNT(*) AS activity_count
        FROM learning_activity
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    study = connection.execute(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS study_minutes,
               COUNT(*) AS study_session_count
        FROM study_sessions
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    quizzes = connection.execute(
        """
        SELECT COUNT(*) AS quiz_count,
               COALESCE(SUM(score), 0) AS correct_answers,
               COALESCE(SUM(total_questions), 0) AS total_questions
        FROM quiz_results
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    return {
        "total_xp": activity["total_xp"],
        "activity_count": activity["activity_count"],
        "study_minutes": study["study_minutes"],
        "study_session_count": study["study_session_count"],
        "quiz_count": quizzes["quiz_count"],
        "correct_answers": quizzes["correct_answers"],
        "total_questions": quizzes["total_questions"],
        "accuracy_percent": (
            round(quizzes["correct_answers"] * 100 / quizzes["total_questions"])
            if quizzes["total_questions"]
            else 0
        ),
    }