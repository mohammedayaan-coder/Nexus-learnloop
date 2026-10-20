"""
Nexus Learn Loop — Application Entrypoint
A competitive, gamified learning platform for Nexus learners.
Modular architecture with Flask blueprints, server-authoritative scoring, and strict account boundaries.
"""

import os
from flask import Flask, session
import database.database as db
from services.security import (
    get_secret_key,
    get_runtime_environment,
    generate_csrf_token,
    configure_safe_cors,
)

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AuthenticatedUser:
    """Wrapper representing a logged-in learner with live database stats."""
    def __init__(self, user_row, stats_row=None, rank=1):
        self.is_authenticated = True
        self.id = user_row["id"]
        self.username = user_row["username"]
        self.email = user_row["email"]
        self.created_at = user_row["created_at"]
        self.bio = user_row["bio"] or ""
        self.learning_goals = user_row["learning_goals"] or "Web & Python Full-Stack"
        self.skills = user_row["skills"] or "Python, Flask, SQLite"
        self.is_demo = bool(user_row["is_demo"]) if "is_demo" in user_row.keys() else False

        stats = stats_row or {}
        self.xp = stats.get("xp", 0)
        self.activities_completed = stats.get("activities_completed", 0)
        self.quizzes_solved = stats.get("quizzes_solved", 0)
        self.correct_answers = stats.get("correct_answers", 0)
        self.questions_answered = stats.get("questions_answered", 0)
        self.study_minutes = stats.get("study_minutes", 0)
        self.study_hours = stats.get("study_hours", 0.0)
        self.sessions_today = stats.get("sessions_today", 0)
        self.accuracy = stats.get("accuracy", 0)
        self.rank = rank
        # True calendar day streak calculated in database layer
        self.streak = stats.get("streak", 0)


class AnonymousUser:
    """Explicit guest visitor representation. Never silently signs in as demo user."""
    is_authenticated = False
    id = None
    username = "Guest"
    email = ""
    created_at = ""
    bio = ""
    learning_goals = "Web & Python Full-Stack"
    skills = "Python, Flask, SQLite"
    is_demo = False
    xp = 0
    activities_completed = 0
    quizzes_solved = 0
    correct_answers = 0
    questions_answered = 0
    study_minutes = 0
    study_hours = 0.0
    sessions_today = 0
    accuracy = 0
    rank = "-"
    streak = 0


def get_current_user():
    """Resolve currently authenticated session user or return AnonymousUser."""
    user_id = session.get("user_id")
    if user_id:
        user_row = db.get_user(user_id)
        if user_row:
            stats = db.get_user_stats(user_id)
            leaderboard = db.get_leaderboard()
            user_rank = 1
            for idx, row in enumerate(leaderboard, start=1):
                if row["id"] == user_id:
                    user_rank = idx
                    break
            return AuthenticatedUser(user_row, stats, user_rank)
        # Clear stale or deleted user session state completely.
        session.clear()
    return AnonymousUser()


def create_app():
    """Application factory for Nexus Learn Loop."""
    app = Flask(__name__)
    app.secret_key = get_secret_key()

    # Session cookie hardening
    environment = get_runtime_environment()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=environment == "production",
    )

    # Fail startup explicitly when SQLite cannot be initialized. Never seed
    # benchmark accounts or sample activity into a production database.
    with app.app_context():
        try:
            db.init_db()
        except Exception as e:
            raise RuntimeError("Database initialization failed; application startup stopped.") from e
        if environment in {"development", "dev", "test", "testing"}:
            db.seed_defaults_if_empty()

    # Secure CORS handler (avoids wildcard '*' with credentials)
    @app.after_request
    def apply_cors_headers(response):
        return configure_safe_cors(response)

    # Context processors for templates
    @app.context_processor
    def inject_context():
        return {
            "current_user": get_current_user(),
            "csrf_token": generate_csrf_token,
        }

    # Register modular blueprints
    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.learning import learning_bp
    from blueprints.ai_mentor import ai_mentor_bp
    from blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(ai_mentor_bp)
    app.register_blueprint(api_bp)

    return app


app = create_app()

if __name__ == "__main__":
    # Debug mode is OFF by default for security; enable via FLASK_DEBUG=1
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(debug=debug_mode, port=5000)
