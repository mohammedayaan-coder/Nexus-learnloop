"""In-memory store used only by automated tests (NEXUS_MEMORY_DB=1)."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from services.streak_service import calculate_streak

_users = {}
_profiles = {}
_activities = []
_sessions = []
_quizzes = []
_activity_seq = 1
_session_seq = 1
_quiz_seq = 1


def reset():
    global _users, _profiles, _activities, _sessions, _quizzes
    global _activity_seq, _session_seq, _quiz_seq
    _users = {}
    _profiles = {}
    _activities = []
    _sessions = []
    _quizzes = []
    _activity_seq = 1
    _session_seq = 1
    _quiz_seq = 1


def _now():
    return datetime.now(timezone.utc)


def _parse_completed_at(completed_at):
    if completed_at is None:
        return _now()
    if isinstance(completed_at, datetime):
        return completed_at
    text = str(completed_at)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _day(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def create_user(username, email, password_hash, learning_goals="", is_demo=0, database_path=None, user_id=None):
    user_id = str(user_id) if user_id else str(uuid4())
    _users[user_id] = {
        "id": user_id,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "is_demo": bool(is_demo),
        "created_at": _now().isoformat(),
    }
    _profiles[user_id] = {
        "user_id": user_id,
        "bio": "",
        "learning_goals": learning_goals or "",
        "skills": "",
    }
    return user_id


def get_user_by_login(login, database_path=None):
    needle = (login or "").casefold()
    for user in _users.values():
        if user["username"].casefold() == needle or user["email"].casefold() == needle:
            return dict(user)
    return None


def get_user(user_id, database_path=None):
    user = _users.get(str(user_id))
    if not user:
        return None
    profile = _profiles.get(str(user_id), {})
    return {
        **user,
        "bio": profile.get("bio", ""),
        "learning_goals": profile.get("learning_goals", ""),
        "skills": profile.get("skills", ""),
    }


def update_profile(user_id, bio, learning_goals, skills, database_path=None):
    key = str(user_id)
    if key not in _profiles:
        return False
    _profiles[key]["bio"] = bio
    _profiles[key]["learning_goals"] = learning_goals
    _profiles[key]["skills"] = skills
    return True


def record_learning_activity(user_id, activity_type, xp_earned, database_path=None, completed_at=None):
    global _activity_seq
    row_id = _activity_seq
    _activity_seq += 1
    _activities.append({
        "id": row_id,
        "user_id": str(user_id),
        "activity_type": activity_type,
        "xp_earned": xp_earned,
        "completed_at": _parse_completed_at(completed_at),
    })
    return row_id


def record_study_session(user_id, duration_minutes, xp_earned=30, database_path=None):
    global _session_seq
    now = _now()
    row_id = _session_seq
    _session_seq += 1
    _sessions.append({
        "id": row_id,
        "user_id": str(user_id),
        "duration_minutes": duration_minutes,
        "started_at": now - timedelta(minutes=duration_minutes),
        "completed_at": now,
    })
    record_learning_activity(user_id, "study_session", xp_earned, database_path=database_path)
    return row_id


def record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned, database_path=None):
    global _quiz_seq
    row_id = _quiz_seq
    _quiz_seq += 1
    _quizzes.append({
        "id": row_id,
        "user_id": str(user_id),
        "quiz_name": quiz_name,
        "score": score,
        "total_questions": total_questions,
        "completed_at": _now().isoformat(),
    })
    record_learning_activity(user_id, "quiz", xp_earned, database_path=database_path)
    return row_id


def get_quiz_result(user_id, result_id, database_path=None):
    for row in _quizzes:
        if str(row["user_id"]) == str(user_id) and str(row["id"]) == str(result_id):
            return dict(row)
    return None


def get_user_stats(user_id, database_path=None):
    uid = str(user_id)
    activities = [a for a in _activities if a["user_id"] == uid]
    quizzes = [q for q in _quizzes if q["user_id"] == uid]
    sessions = [s for s in _sessions if s["user_id"] == uid]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    correct = sum(q["score"] for q in quizzes)
    questions = sum(q["total_questions"] for q in quizzes)
    minutes = sum(s["duration_minutes"] for s in sessions)
    return {
        "xp": sum(a["xp_earned"] for a in activities),
        "activities_completed": len(activities),
        "quizzes_solved": len(quizzes),
        "correct_answers": correct,
        "questions_answered": questions,
        "study_minutes": minutes,
        "study_hours": round(minutes / 60, 1),
        "sessions_today": sum(1 for s in sessions if _day(s["completed_at"]) == today),
        "accuracy": round(correct * 100 / questions) if questions else 0,
        "streak": calculate_streak([_day(a["completed_at"]) for a in activities]),
    }


def get_leaderboard(database_path=None):
    rows = []
    for user in _users.values():
        profile = _profiles.get(user["id"], {})
        xp = sum(a["xp_earned"] for a in _activities if a["user_id"] == user["id"])
        rows.append({
            "id": user["id"],
            "username": user["username"],
            "is_demo": user["is_demo"],
            "learning_goals": profile.get("learning_goals", ""),
            "xp": xp,
        })
    rows.sort(key=lambda r: (-r["xp"], r["username"].casefold()))
    return rows


def get_activity_counts(user_id, database_path=None, days=210):
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    counts = [0] * days
    uid = str(user_id)
    for activity in _activities:
        if activity["user_id"] != uid:
            continue
        day = date.fromisoformat(_day(activity["completed_at"]))
        if first_day <= day <= today:
            counts[(day - first_day).days] += 1
    return counts


def seed_defaults_if_empty(database_path=None):
    if len(_users) > 0:
        return
    from werkzeug.security import generate_password_hash
    pwd = generate_password_hash("password123")
    uid = create_user("learner", "learner@nexus.org", pwd, "Web & Python Full-Stack", is_demo=1)
    update_profile(uid, "Passionate developer", "Web & Python Full-Stack", "Python, Flask, Supabase")
    record_learning_activity(uid, "quiz_mastery", 1420)
