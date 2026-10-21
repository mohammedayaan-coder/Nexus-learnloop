"""JSON endpoints used to hydrate pages and persist learner activity."""

from flask import Blueprint, current_app, jsonify, request, session

import database.database as db
from services.quiz_service import evaluate_quiz_submission, validate_and_calculate_timer_reward
from services.leaderboard import get_ranked_learners
from services.security import login_required, require_csrf

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _rank_for(user_id, rankings):
    for rank, row in enumerate(rankings, 1):
        if row["id"] == user_id:
            return rank
    return "-"


@api_bp.route("/current-user")
def current_user_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({
            "success": True,
            "is_authenticated": False,
            "user": {"id": None, "username": "Guest", "email": "", "bio": "",
                     "learning_goals": "Web & Python Full-Stack", "skills": "Python, Flask, SQLite", "created_at": ""},
            "stats": {"xp": 0, "streak": 0, "rank": "-", "study_hours": 0.0,
                      "study_minutes": 0, "quizzes_solved": 0, "accuracy": 0, "sessions_today": 0},
        })
    user = db.get_user(user_id)
    if (not user or (user["is_demo"] and
                     current_app.config.get("RUNTIME_ENVIRONMENT") == "production")):
        session.clear()
        return jsonify({"success": True, "is_authenticated": False})
    stats = db.get_user_stats(user_id)
    rankings = get_ranked_learners()
    return jsonify({
        "success": True,
        "is_authenticated": True,
        "user": {"id": user["id"], "username": user["username"], "email": user["email"],
                 "bio": user["bio"] or "", "learning_goals": user["learning_goals"] or "Web & Python Full-Stack",
                 "skills": user["skills"] or "Python, Flask, SQLite", "created_at": user["created_at"] or ""},
        "stats": {key: stats.get(key, default) for key, default in {
            "xp": 0, "streak": 0, "rank": _rank_for(user_id, rankings), "study_hours": 0.0,
            "study_minutes": 0, "quizzes_solved": 0, "accuracy": 0, "sessions_today": 0,
            "questions_answered": 0,
        }.items()},
    })


@api_bp.route("/leaderboard")
def api_leaderboard():
    return jsonify({"success": True, "rankings": [dict(row) for row in get_ranked_learners()]})


@api_bp.route("/activity-counts")
@login_required
def api_activity_counts():
    return jsonify({"success": True, "counts": db.get_activity_counts(session["user_id"], days=210)})


@api_bp.route("/record-study-session", methods=["POST"])
@login_required
@require_csrf
def api_record_study_session():
    data = request.get_json(silent=True) or {}
    try:
        minutes, xp = validate_and_calculate_timer_reward(data.get("duration_minutes", 25))
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    try:
        session_id, created = db.record_study_session_submission(
            session["user_id"], minutes, xp_earned=xp, submission_key=data.get("submission_id", ""),
        )
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    return jsonify({"success": True, "session_id": session_id, "duration_minutes": minutes,
                    "created": created, "xp_awarded": xp if created else 0,
                    "stats": db.get_user_stats(session["user_id"])})


@api_bp.route("/record-quiz", methods=["POST"])
@login_required
@require_csrf
def api_record_quiz():
    data = request.get_json(silent=True) or {}
    evaluated = evaluate_quiz_submission(data.get("quiz_id", "jinja2-interpolation"),
                                         data.get("answers") or data.get("selected_option", ""))
    submission_id = data.get("submission_id")
    try:
        result_id, created = db.record_quiz_submission(
            session["user_id"], evaluated["quiz_name"], evaluated["score"],
            evaluated["total_questions"], evaluated["xp_earned"], submission_id,
        )
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    session["last_quiz_result_id"] = result_id
    return jsonify({"success": True, "created": created, "result_id": result_id, "quiz_name": evaluated["quiz_name"],
                    "score": evaluated["score"], "total_questions": evaluated["total_questions"],
                    "accuracy": evaluated["accuracy"], "xp_earned": evaluated["xp_earned"],
                    "passed": evaluated["passed"], "stats": db.get_user_stats(session["user_id"])})
