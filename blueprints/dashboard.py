"""Landing page, learner dashboard, profiles, and leaderboard routes."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import database.database as db
from services.leaderboard import get_ranked_learners
from services.security import login_required, require_csrf

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@dashboard_bp.route("/index.html")
def index():
    return render_template("index.html")


@dashboard_bp.route("/dashboard")
@dashboard_bp.route("/dashboard.html")
@login_required
def dashboard():
    user_id = session["user_id"]
    rankings = get_ranked_learners()
    rank = next((position for position, learner in enumerate(rankings, 1)
                 if learner["id"] == user_id), "-")
    stats = db.get_user_stats(user_id)
    stats["rank"] = rank
    return render_template(
        "dashboard.html",
        stats=stats,
        activity_counts=db.get_activity_counts(user_id),
        leaderboard=rankings[:5],
        user_id=user_id,
    )


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@dashboard_bp.route("/profile.html", methods=["GET", "POST"])
@login_required
@require_csrf
def profile():
    user_id = session["user_id"]
    if request.method == "POST":
        bio = request.form.get("bio", "").strip()
        learning_goals = request.form.get("learning_goals", "").strip()
        skills = request.form.get("skills", "").strip()
        if any(len(value) > limit for value, limit in ((bio, 2000), (learning_goals, 250), (skills, 1000))):
            flash("One or more profile fields are too long.", "error")
        elif db.update_profile(user_id, bio, learning_goals, skills):
            flash("Learner profile updated.", "success")
        return redirect(url_for("dashboard.profile"))

    return render_template(
        "profile.html",
        user=db.get_user(user_id),
        stats=db.get_user_stats(user_id),
        activity_counts=db.get_activity_counts(user_id),
    )


@dashboard_bp.route("/leaderboard")
@dashboard_bp.route("/leaderboard.html")
def leaderboard():
    return render_template("leaderboard.html", rankings=get_ranked_learners())
