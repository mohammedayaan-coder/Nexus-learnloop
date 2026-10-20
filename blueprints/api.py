"""JSON endpoints used to hydrate pages and persist learner activity."""

from flask import Blueprint, jsonify, request, session

import database.database as db
from services.quiz_service import evaluate_quiz_submission, validate_and_calculate_timer_reward
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
    if not user:
        session.clear()
        return jsonify({"success": True, "is_authenticated": False})
    stats = db.get_user_stats(user_id)
    rankings = db.get_leaderboard()
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
    return jsonify({"success": True, "rankings": [dict(row) for row in db.get_leaderboard()]})


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
    session_id = db.record_study_session(session["user_id"], minutes, xp_earned=xp)
    return jsonify({"success": True, "session_id": session_id, "duration_minutes": minutes,
                    "xp_awarded": xp, "stats": db.get_user_stats(session["user_id"])})


@api_bp.route("/record-quiz", methods=["POST"])
@login_required
@require_csrf
def api_record_quiz():
    data = request.get_json(silent=True) or {}
    evaluated = evaluate_quiz_submission(data.get("quiz_id", "jinja2-interpolation"),
                                         data.get("answers") or data.get("selected_option", ""))
    result_id = db.record_quiz_result(session["user_id"], evaluated["quiz_name"],
                                      evaluated["score"], evaluated["total_questions"], evaluated["xp_earned"])
    session["last_quiz_result_id"] = result_id
    return jsonify({"success": True, "result_id": result_id, "quiz_name": evaluated["quiz_name"],
                    "score": evaluated["score"], "total_questions": evaluated["total_questions"],
                    "accuracy": evaluated["accuracy"], "xp_earned": evaluated["xp_earned"],
                    "passed": evaluated["passed"], "stats": db.get_user_stats(session["user_id"])})
