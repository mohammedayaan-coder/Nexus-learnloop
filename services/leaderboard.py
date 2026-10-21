"""Environment-aware learner ranking policy."""

from flask import current_app

import database.database as db


def get_ranked_learners():
    """Show fixtures in development; production requires registered provenance and positive XP."""
    production = current_app.config.get("RUNTIME_ENVIRONMENT") == "production"
    return db.get_leaderboard(
        include_demo=not production,
        require_xp_records=production,
    )
