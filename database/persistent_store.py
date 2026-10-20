"""
Nexus Learn Loop — Persistent Local JSON Store
Reliable file-based persistence (instance/nexus_store.json) without any SQLite dependencies.
Used for local-only accounts when Supabase is not configured, and for tests.
"""

import os
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from services.streak_service import calculate_streak

STORE_PATH = Path(__file__).resolve().parent.parent / "instance" / "nexus_store.json"

_data = {
    "users": {},
    "profiles": {},
    "activities": [],
    "sessions": [],
    "quizzes": [],
    "seq": {"activity": 1, "session": 1, "quiz": 1}
}


def _load():
    global _data
    if STORE_PATH.exists():
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except Exception as e:
            print(f"[Persistent Store Load Warning]: {e}")


def _save():
    try:
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, indent=2, default=str)
    except Exception as e:
        print(f"[Persistent Store Save Warning]: {e}")


# Load on import
_load()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _day(value):
    if not value:
        return datetime.now(timezone.utc).date().isoformat()
    return str(value)[:10]


def create_user(username, email, password_hash, learning_goals="Web & Python Full-Stack", is_demo=0, user_id=None):
    _load()
    uid = str(user_id or uuid4())
    _data["users"][uid] = {
        "id": uid,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "is_demo": bool(is_demo),
        "created_at": _now(),
    }
    _data["profiles"][uid] = {
        "user_id": uid,
        "bio": f"Passionate {learning_goals} learner building daily habits.",
        "learning_goals": learning_goals or "Web & Python Full-Stack",
        "skills": "Python, Flask, Supabase, Git",
    }
    _save()
    return uid


def get_user_by_login(login):
    _load()
    needle = (login or "").strip().casefold()
    for user in _data["users"].values():
        if user["username"].casefold() == needle or user["email"].casefold() == needle:
            return dict(user)
    return None


def get_user(user_id):
    _load()
    uid = str(user_id)
    user = _data["users"].get(uid)
    if not user:
        return None
    profile = _data["profiles"].get(uid, {})
    return {
        **user,
        "bio": profile.get("bio", ""),
        "learning_goals": profile.get("learning_goals", "Web & Python Full-Stack"),
        "skills": profile.get("skills", "Python, Flask, Supabase, Git"),
    }


def update_profile(user_id, bio, learning_goals, skills):
    _load()
    uid = str(user_id)
    if uid not in _data["profiles"]:
        _data["profiles"][uid] = {"user_id": uid}
    _data["profiles"][uid]["bio"] = bio
    _data["profiles"][uid]["learning_goals"] = learning_goals
    _data["profiles"][uid]["skills"] = skills
    _save()
    return True


def record_learning_activity(user_id, activity_type, xp_earned, completed_at=None):
    _load()
    seq = _data["seq"]["activity"]
    _data["seq"]["activity"] += 1
    _data["activities"].append({
        "id": seq,
        "user_id": str(user_id),
        "activity_type": str(activity_type),
        "xp_earned": int(xp_earned or 0),
        "completed_at": completed_at or _now(),
    })
    _save()
    return seq


def record_study_session(user_id, duration_minutes, xp_earned=30):
    _load()
    seq = _data["seq"]["session"]
    _data["seq"]["session"] += 1
    now = datetime.now(timezone.utc)
    started_at = (now - timedelta(minutes=duration_minutes)).isoformat()
    completed_at = now.isoformat()
    _data["sessions"].append({
        "id": seq,
        "user_id": str(user_id),
        "duration_minutes": int(duration_minutes),
        "started_at": started_at,
        "completed_at": completed_at,
    })
    _save()
    record_learning_activity(user_id, "study_session", xp_earned, completed_at=completed_at)
    return seq


def record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned):
    _load()
    seq = _data["seq"]["quiz"]
    _data["seq"]["quiz"] += 1
    completed_at = _now()
    _data["quizzes"].append({
        "id": seq,
        "user_id": str(user_id),
        "quiz_name": str(quiz_name),
        "score": int(score),
        "total_questions": int(total_questions),
        "completed_at": completed_at,
    })
    _save()
    record_learning_activity(user_id, "quiz", xp_earned, completed_at=completed_at)
    return seq


def get_quiz_result(user_id, result_id):
    _load()
    uid = str(user_id)
    rid = int(result_id) if str(result_id).isdigit() else result_id
    for row in _data["quizzes"]:
        if str(row["user_id"]) == uid and row["id"] == rid:
            return dict(row)
    return None


def get_user_stats(user_id):
    _load()
    uid = str(user_id)
    activities = [a for a in _data["activities"] if a["user_id"] == uid]
    quizzes = [q for q in _data["quizzes"] if q["user_id"] == uid]
    sessions = [s for s in _data["sessions"] if s["user_id"] == uid]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    correct = sum(q.get("score", 0) for q in quizzes)
    questions = sum(q.get("total_questions", 0) for q in quizzes)
    minutes = sum(s.get("duration_minutes", 0) for s in sessions)
    act_dates = [_day(a.get("completed_at")) for a in activities]

    return {
        "xp": sum(a.get("xp_earned", 0) for a in activities),
        "activities_completed": len(activities),
        "quizzes_solved": len(quizzes),
        "correct_answers": correct,
        "questions_answered": questions,
        "study_minutes": minutes,
        "study_hours": round(minutes / 60, 1),
        "sessions_today": sum(1 for s in sessions if _day(s.get("completed_at")) == today),
        "accuracy": round(correct * 100 / questions) if questions else 0,
        "streak": calculate_streak(act_dates),
    }


def get_leaderboard():
    _load()
    rows = []
    for uid, user in _data["users"].items():
        profile = _data["profiles"].get(uid, {})
        xp = sum(a.get("xp_earned", 0) for a in _data["activities"] if a["user_id"] == uid)
        rows.append({
            "id": uid,
            "username": user["username"],
            "is_demo": user.get("is_demo", False),
            "learning_goals": profile.get("learning_goals", ""),
            "xp": xp,
        })
    rows.sort(key=lambda r: (-r["xp"], r["username"].casefold()))
    return rows


def get_activity_counts(user_id, days=210):
    _load()
    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    counts = [0] * days
    uid = str(user_id)
    for activity in _data["activities"]:
        if activity["user_id"] != uid:
            continue
        try:
            day_str = _day(activity.get("completed_at"))
            act_date = date.fromisoformat(day_str)
            if first_day <= act_date <= today:
                counts[(act_date - first_day).days] += 1
        except Exception:
            continue
    return counts


def seed_defaults_if_empty():
    _load()
    if len(_data["users"]) > 0:
        return

    from werkzeug.security import generate_password_hash
    pwd_hash = generate_password_hash("password123")

    # 1. Main demo learner account
    learner_id = create_user("learner", "learner@nexus.org", pwd_hash, "Web & Python Full-Stack", is_demo=1)
    update_profile(learner_id, "Full-stack Python & Flask developer. Building daily habits and leveling up.", "Web & Python Full-Stack", "Python, Flask, Supabase, Git")

    # Seed 7 consecutive days of check-ins for demo learner
    today = datetime.now(timezone.utc).date()
    for d in range(7):
        act_date = today - timedelta(days=d)
        record_learning_activity(learner_id, "daily_streak_checkin", 100, completed_at=f"{act_date.isoformat()}T12:00:00Z")

    for _ in range(8):
        record_study_session(learner_id, 25, xp_earned=30)
    for q in range(15):
        record_quiz_result(learner_id, f"Daily Challenge #{q+1}", 1, 1, 20)
    record_learning_activity(learner_id, "streak_bonus", 180)

    # 2. Benchmark leaderboard peers
    peers = [
        ("Elena Rostova", "elena@nexus.org", "Full-Stack Track", 2840, "Senior full-stack learner & open source contributor.", "Python, React, PostgreSQL, Docker"),
        ("Marcus Chen", "marcus@nexus.org", "DevOps Track", 2610, "DevOps & Cloud Infrastructure engineer in training.", "Kubernetes, Linux, Terraform, Python"),
        ("Amina Diop", "amina@nexus.org", "AI & Data Track", 2490, "AI researcher & machine learning practitioner.", "PyTorch, Transformers, Python, SQL"),
        ("Devon Taylor", "devon@nexus.org", "Frontend Track", 1280, "Modern UI/UX developer crafting tactile experiences.", "JavaScript, CSS3, Vue, Figma"),
    ]
    for name, email, track, xp, bio, skills in peers:
        uid = create_user(name, email, pwd_hash, track, is_demo=1)
        update_profile(uid, bio, track, skills)
        record_learning_activity(uid, "quiz_mastery", xp)
