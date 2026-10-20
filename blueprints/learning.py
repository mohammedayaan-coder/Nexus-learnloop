"""
Nexus Learn Loop — Learning Blueprint
Handles daily challenges, quiz grading, focus timer sprints, resources, and study buddy rooms with Supabase.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import database.database as db
from services.security import login_required, require_csrf
from services.quiz_service import evaluate_quiz_submission, validate_and_calculate_timer_reward, get_quiz

learning_bp = Blueprint("learning", __name__)


@learning_bp.route("/quiz", methods=["GET", "POST"])
@learning_bp.route("/quiz.html", methods=["GET", "POST"])
def quiz():
    """Daily challenge quiz page and server-authoritative submission."""
    if request.method == "POST":
        user_id = session.get("user_id")
        token = session.get("access_token")
        if not user_id:
            flash("Please sign in or register to submit quizzes and earn XP.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.quiz")))

        quiz_id = request.form.get("quiz_id", "jinja2-interpolation")
        selected = request.form.get("selected_option", "").strip().upper()

        # Authoritative server-side evaluation: client cannot spoof score or XP!
        eval_result = evaluate_quiz_submission(quiz_id, selected)

        result_id = db.record_quiz_result(
            user_id=user_id,
            quiz_name=eval_result["quiz_name"],
            score=eval_result["score"],
            total_questions=eval_result["total_questions"],
            xp_earned=eval_result["xp_earned"],
            access_token=token,
        )
        session["last_quiz_result_id"] = result_id

        if eval_result["passed"]:
            flash(f"Challenge completed! +{eval_result['xp_earned']} XP awarded.", "success")
        else:
            flash(f"Challenge recorded. Keep practicing! +{eval_result['xp_earned']} XP awarded.", "info")

        return redirect(url_for("learning.result", id=result_id))

    quiz_data = get_quiz("jinja2-interpolation")
    return render_template("quiz.html", quiz_data=quiz_data)


@learning_bp.route("/result", methods=["GET", "POST"])
@learning_bp.route("/result.html", methods=["GET", "POST"])
def result():
    """Quiz outcome and celebratory score summary."""
    user_id = session.get("user_id")
    token = session.get("access_token")
    result_id = request.args.get("id") or session.get("last_quiz_result_id")

    # If POSTed directly from static form
    if request.method == "POST":
        if not user_id:
            flash("Please sign in to track and record quiz results.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.quiz")))

        quiz_id = request.form.get("quiz_id", "jinja2-interpolation")
        selected = request.form.get("selected_option", "").strip().upper()
        eval_result = evaluate_quiz_submission(quiz_id, selected)

        result_id = db.record_quiz_result(
            user_id=user_id,
            quiz_name=eval_result["quiz_name"],
            score=eval_result["score"],
            total_questions=eval_result["total_questions"],
            xp_earned=eval_result["xp_earned"],
            access_token=token,
        )
        session["last_quiz_result_id"] = result_id

    quiz_result = db.get_quiz_result(user_id, result_id, access_token=token) if (user_id and result_id) else None
    stats = db.get_user_stats(user_id, access_token=token) if user_id else {}
    return render_template("result.html", quiz_result=quiz_result, stats=stats)


@learning_bp.route("/timer", methods=["GET", "POST"])
@learning_bp.route("/timer.html", methods=["GET", "POST"])
def timer():
    """Pomodoro and deep-hack focus timer."""
    user_id = session.get("user_id")
    token = session.get("access_token")
    if request.method == "POST":
        if not user_id:
            flash("Please sign in to record your study session and earn focus XP.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.timer")))

        raw_duration = request.form.get("duration_minutes", 25)
        try:
            validated_duration, server_xp = validate_and_calculate_timer_reward(raw_duration)
        except ValueError as err:
            flash(str(err), "error")
            return redirect(url_for("learning.timer"))

        db.record_study_session(user_id, validated_duration, xp_earned=server_xp, access_token=token)
        flash(f"Study sprint ({validated_duration} min) recorded in Supabase! +{server_xp} XP awarded.", "success")
        return redirect(url_for("dashboard.dashboard"))

    stats = db.get_user_stats(user_id, access_token=token) if user_id else {}
    return render_template("timer.html", stats=stats)


@learning_bp.route("/resources")
@learning_bp.route("/resources.html")
def resources():
    """Curated roadmaps and documentation resources."""
    return render_template("resources.html")


@learning_bp.route("/lwb")
@learning_bp.route("/lwb.html")
def lwb():
    """Learn With Buddies (LWB) collaborative study space preview."""
    return render_template("lwb.html")
