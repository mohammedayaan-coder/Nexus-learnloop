"""
Nexus Learn Loop — Supabase PostgreSQL Persistence Adapter
Provides a seamless drop-in database client connecting Flask to Supabase.
Adheres to official Supabase Python client guidelines with server-role and auth key support.
"""

import os
from datetime import datetime, timezone
from services.streak_service import calculate_streak

_supabase_client = None


def get_supabase_client():
    """
    Initialize and cache the Supabase client.
    Requires SUPABASE_URL and either SUPABASE_SERVICE_ROLE_KEY (backend operations)
    or SUPABASE_KEY / SUPABASE_PUBLISHABLE_KEY.
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
        or os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
    )

    if not supabase_url or not supabase_key:
        return None

    try:
        from supabase import create_client, Client
        _supabase_client = create_client(supabase_url, supabase_key)
        return _supabase_client
    except ImportError:
        # supabase-py not yet installed in virtualenv
        return None


def is_supabase_enabled():
    """Check if the developer has configured Supabase environment variables."""
    return bool(
        os.getenv("USE_SUPABASE", "").lower() in ("1", "true")
        and os.getenv("SUPABASE_URL")
        and (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY"))
    )


def supabase_get_user_stats(user_id):
    """Fetch user stats directly from Supabase Postgres."""
    client = get_supabase_client()
    if not client or not user_id:
        return {}

    # Query learning activity
    act_res = client.table("learning_activity").select("xp_earned, completed_at").eq("user_id", str(user_id)).execute()
    activities = act_res.data or []
    total_xp = sum(a.get("xp_earned", 0) for a in activities)

    # Calculate real calendar streak
    act_dates = [a["completed_at"][:10] for a in activities if a.get("completed_at")]
    streak = calculate_streak(act_dates)

    # Query study sessions
    sessions_res = client.table("study_sessions").select("duration_minutes, completed_at").eq("user_id", str(user_id)).execute()
    sessions = sessions_res.data or []
    study_minutes = sum(s.get("duration_minutes", 0) for s in sessions)
    study_hours = round(study_minutes / 60, 1)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions_today = sum(1 for s in sessions if s.get("completed_at", "").startswith(today_str))

    # Query quiz results
    quiz_res = client.table("quiz_results").select("score, total_questions").eq("user_id", str(user_id)).execute()
    quizzes = quiz_res.data or []
    quizzes_solved = len(quizzes)
    correct_answers = sum(q.get("score", 0) for q in quizzes)
    questions_answered = sum(q.get("total_questions", 0) for q in quizzes)
    accuracy = round((correct_answers / questions_answered) * 100) if questions_answered else 0

    return {
        "xp": total_xp,
        "activities_completed": len(activities),
        "quizzes_solved": quizzes_solved,
        "correct_answers": correct_answers,
        "questions_answered": questions_answered,
        "study_minutes": study_minutes,
        "study_hours": study_hours,
        "sessions_today": sessions_today,
        "accuracy": accuracy,
        "streak": streak
    }
