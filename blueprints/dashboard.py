"""
Nexus Learn Loop — Dashboard Blueprint
Handles public landing page, protected learner dashboard, user profile, and leaderboard.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import database.database as db
from services.security import login_required, require_csrf

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", methods=["GET"])
@dashboard_bp.route("/index.html", methods=["GET"])
def index():
    """Public landing page."""
    return render_template("index.html")


@dashboard_bp.route("/dashboard", methods=["GET"])
@dashboard_bp.route("/dashboard.html", methods=["GET"])
@login_required
def dashboard():
    """Learner dashboard showing live SQLite XP, streaks, and challenges."""
    user_id = session.get("user_id")
    stats = db.get_user_stats(user_id) if user_id else {}
    activity_counts = db.get_activity_counts(user_id) if user_id else []
    leaderboard = db.get_leaderboard()[:5]
    return render_template(
        "dashboard.html",
        stats=stats,
        activity_counts=activity_counts,
        leaderboard=leaderboard
    )


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@dashboard_bp.route("/profile.html", methods=["GET", "POST"])
@login_required
@require_csrf
def profile():
    """Learner profile view and settings editor."""
    user_id = session.get("user_id")
    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        learning_goals = request.form.get("learning_goals", "").strip()
        skills = request.form.get("skills", "").strip()
        if user_id:
            db.update_profile(user_id, bio, learning_goals, skills)
            db.record_learning_activity(user_id, "profile_update", 15)
            flash("Learner profile updated! +15 XP awarded.", "success")
        return redirect(url_for("dashboard.profile"))

    user_data = db.get_user(user_id) if user_id else None
    stats = db.get_user_stats(user_id) if user_id else {}
    activity_counts = db.get_activity_counts(user_id) if user_id else []
    return render_template(
        "profile.html",
        user=user_data,
        stats=stats,
        activity_counts=activity_counts
    )


@dashboard_bp.route("/leaderboard", methods=["GET"])
@dashboard_bp.route("/leaderboard.html", methods=["GET"])
def leaderboard():
    """Public community leaderboard."""
    rankings = db.get_leaderboard()
    return render_template("leaderboard.html", rankings=rankings)
