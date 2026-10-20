"""
Nexus Learn Loop — REST API Blueprint
Provides JSON endpoints for client hydration, leaderboard, authenticated activity tracking,
and server-authoritative scoring backed by Supabase.
"""

from flask import Blueprint, request, jsonify, session
import database.database as db
from services.security import login_required
from services.quiz_service import evaluate_quiz_submission, validate_and_calculate_timer_reward

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/current-user", methods=["GET", "OPTIONS"])
def current_user_api():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    user_id = session.get("user_id")
    token = session.get("access_token")

    if not user_id:
        return jsonify({
            "success": True,
            "is_authenticated": False,
            "user": {
                "id": None,
                "username": "Guest",
                "email": "",
                "bio": "",
                "learning_goals": "Web & Python Full-Stack",
                "skills": "Python, Flask, Supabase",
                "created_at": ""
            },
            "stats": {
                "xp": 0,
                "streak": 0,
                "rank": "-",
                "study_hours": 0.0,
                "study_minutes": 0,
                "quizzes_solved": 0,
                "accuracy": 0,
                "sessions_today": 0
            }
        })

    user_row = db.get_user(user_id, access_token=token)
    if not user_row:
        session.pop("user_id", None)
        session.pop("access_token", None)
        return jsonify({"success": True, "is_authenticated": False}), 200

    stats = db.get_user_stats(user_id, access_token=token)
    leaderboard = db.get_leaderboard()
    user_rank = 1
    for idx, row in enumerate(leaderboard, start=1):
        if str(row["id"]) == str(user_id):
            user_rank = idx
            break

    return jsonify({
        "success": True,
        "is_authenticated": True,
        "user": {
            "id": user_row["id"],
            "username": user_row["username"],
            "email": user_row["email"],
            "bio": user_row.get("bio") or "",
            "learning_goals": user_row.get("learning_goals") or "Web & Python Full-Stack",
            "skills": user_row.get("skills") or "Python, Flask, Supabase",
            "created_at": user_row.get("created_at") or ""
        },
        "stats": {
            "xp": stats.get("xp", 0),
            "streak": stats.get("streak", 0),
            "rank": user_rank,
            "study_hours": stats.get("study_hours", 0.0),
            "study_minutes": stats.get("study_minutes", 0),
            "quizzes_solved": stats.get("quizzes_solved", 0),
            "accuracy": stats.get("accuracy", 0),
            "sessions_today": stats.get("sessions_today", 0)
        }
    })


@api_bp.route("/leaderboard", methods=["GET"])
def api_leaderboard():
    rankings = db.get_leaderboard()
    return jsonify({
        "success": True,
        "rankings": [
            {
                "id": r["id"],
                "username": r["username"],
                "learning_goals": r.get("learning_goals", ""),
                "xp": r.get("xp", 0),
                "is_demo": bool(r.get("is_demo", False))
            }
            for r in rankings
        ]
    })


@api_bp.route("/record-study-session", methods=["POST", "OPTIONS"])
@login_required
def api_record_study_session():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    user_id = session.get("user_id")
    token = session.get("access_token")
    data = request.get_json(silent=True) or {}
    raw_duration = data.get("duration_minutes", 25)

    try:
        duration, server_xp = validate_and_calculate_timer_reward(raw_duration)
    except ValueError as err:
        return jsonify({"success": False, "error": str(err)}), 400

    session_id = db.record_study_session(user_id, duration, xp_earned=server_xp, access_token=token)
    stats = db.get_user_stats(user_id, access_token=token)
    return jsonify({
        "success": True,
        "session_id": session_id,
        "duration_minutes": duration,
        "xp_awarded": server_xp,
        "stats": stats
    })


@api_bp.route("/record-quiz", methods=["POST", "OPTIONS"])
@login_required
def api_record_quiz():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    user_id = session.get("user_id")
    token = session.get("access_token")
    data = request.get_json(silent=True) or {}
    quiz_id = data.get("quiz_id", "jinja2-interpolation")
    answers = data.get("answers") or data.get("selected_option") or "B"

    # Server evaluates answers and calculates reward — client cannot spoof!
    eval_result = evaluate_quiz_submission(quiz_id, answers)

    result_id = db.record_quiz_result(
        user_id=user_id,
        quiz_name=eval_result["quiz_name"],
        score=eval_result["score"],
        total_questions=eval_result["total_questions"],
        xp_earned=eval_result["xp_earned"],
        access_token=token,
    )
    session["last_quiz_result_id"] = result_id
    stats = db.get_user_stats(user_id, access_token=token)

    return jsonify({
        "success": True,
        "result_id": result_id,
        "quiz_name": eval_result["quiz_name"],
        "score": eval_result["score"],
        "total_questions": eval_result["total_questions"],
        "accuracy": eval_result["accuracy"],
        "xp_earned": eval_result["xp_earned"],
        "passed": eval_result["passed"],
        "stats": stats
    })


@api_bp.route("/activity-counts", methods=["GET"])
@login_required
def api_activity_counts():
    user_id = session.get("user_id")
    token = session.get("access_token")
    counts = db.get_activity_counts(user_id, days=210, access_token=token)
    return jsonify({"success": True, "counts": counts})
