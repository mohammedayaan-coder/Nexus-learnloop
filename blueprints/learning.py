"""Quiz, focus timer, curated resources, and study room routes."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

import database.database as db
from services.quiz_service import evaluate_quiz_submission, get_quiz, validate_and_calculate_timer_reward
from services.security import login_required, require_csrf

learning_bp = Blueprint("learning", __name__)


def _active_user_id():
    user_id = session.get("user_id")
    if not user_id or not db.get_user(user_id):
        session.clear()
        return None
    return user_id


@learning_bp.route("/quiz", methods=["GET", "POST"])
@learning_bp.route("/quiz.html", methods=["GET", "POST"])
@require_csrf
def quiz():
    if request.method == "POST":
        user_id = _active_user_id()
        if not user_id:
            flash("Please sign in or register to submit quizzes and earn XP.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.quiz")))
        result = evaluate_quiz_submission(
            request.form.get("quiz_id", "jinja2-interpolation"),
            request.form.get("selected_option", "").strip().upper(),
        )
        result_id = db.record_quiz_result(
            user_id, result["quiz_name"], result["score"],
            result["total_questions"], result["xp_earned"],
        )
        session["last_quiz_result_id"] = result_id
        flash(f"Challenge recorded. +{result['xp_earned']} XP awarded.", "success")
        return redirect(url_for("learning.result", id=result_id))
    return render_template("quiz.html", quiz_data=get_quiz("jinja2-interpolation"))


@learning_bp.route("/result", methods=["GET", "POST"])
@learning_bp.route("/result.html", methods=["GET", "POST"])
@require_csrf
def result():
    user_id = _active_user_id()
    result_id = request.args.get("id") or session.get("last_quiz_result_id")
    if request.method == "POST":
        if not user_id:
            flash("Please sign in to track and record quiz results.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.quiz")))
        evaluated = evaluate_quiz_submission(
            request.form.get("quiz_id", "jinja2-interpolation"),
            request.form.get("selected_option", "").strip().upper(),
        )
        result_id = db.record_quiz_result(
            user_id, evaluated["quiz_name"], evaluated["score"],
            evaluated["total_questions"], evaluated["xp_earned"],
        )
        session["last_quiz_result_id"] = result_id
    quiz_result = db.get_quiz_result(user_id, result_id) if user_id and result_id else None
    stats = db.get_user_stats(user_id) if user_id else {}
    return render_template("result.html", quiz_result=quiz_result, stats=stats)


@learning_bp.route("/timer", methods=["GET", "POST"])
@learning_bp.route("/timer.html", methods=["GET", "POST"])
@require_csrf
def timer():
    user_id = _active_user_id()
    if request.method == "POST":
        if not user_id:
            flash("Please sign in to record your study session and earn focus XP.", "info")
            return redirect(url_for("auth.login", next=url_for("learning.timer")))
        try:
            minutes, xp = validate_and_calculate_timer_reward(request.form.get("duration_minutes", 25))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("learning.timer"))
        db.record_study_session(user_id, minutes, xp_earned=xp)
        flash(f"Study sprint ({minutes} min) recorded. +{xp} XP awarded.", "success")
        return redirect(url_for("dashboard.dashboard"))
    return render_template("timer.html", stats=db.get_user_stats(user_id) if user_id else {})


@learning_bp.route("/resources")
@learning_bp.route("/resources.html")
def resources():
    return render_template("resources.html")


@learning_bp.route("/lwb")
@learning_bp.route("/lwb.html")
def lwb():
    return render_template("lwb.html")
