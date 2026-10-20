"""
Nexus Learn Loop — Unified Persistence Layer
Supabase is authoritative for cloud accounts; the JSON store is used locally.
"""

"""Unified persistence API: Supabase for cloud accounts, JSON for local accounts."""

import os
from dotenv import load_dotenv
load_dotenv()

from database.supabase_client import (
    is_supabase_enabled,
    supabase_get_user,
    supabase_update_profile,
    supabase_record_learning_activity,
    supabase_record_study_session,
    supabase_record_quiz_result,
    supabase_get_quiz_result,
    supabase_get_user_stats,
    supabase_get_leaderboard,
    supabase_get_activity_counts,
)
import database.memory_store as mem
import database.persistent_store as pstore


def _use_memory():
    """Check if in-memory test store is requested (e.g. during automated tests)."""
    return bool(os.getenv("NEXUS_MEMORY_DB") == "1")


def _active_store():
    return mem if _use_memory() else pstore


def _use_cloud():
    """Supabase is the sole write store when configured; JSON is local-only otherwise."""
    return is_supabase_enabled() and not _use_memory()


def _is_cloud_user(user_id, access_token=None):
    if not _use_cloud():
        return False
    try:
        return bool(supabase_get_user(user_id, access_token=access_token))
    except Exception:
        return False


def init_db(database_path=None):
    """
    Initialize database persistence.
    Seeds default benchmark peers if empty.
    """
    if _use_cloud():
        return
    if _use_memory() or database_path:
        mem.reset()
        mem.seed_defaults_if_empty()
        return

    pstore.seed_defaults_if_empty()


def create_user(username, email, password_hash=None, learning_goals="", is_demo=0, database_path=None, password="password123", user_id=None):
    """
    Create a new learner account.
    Stores a local account when cloud signup is unavailable.
    """
    store = _active_store()

    # Create local persistent record
    assigned_id = store.create_user(
        username=username,
        email=email,
        password_hash=password_hash,
        learning_goals=learning_goals,
        is_demo=is_demo,
        user_id=user_id,
    )

    return assigned_id


def get_user_by_login(login, database_path=None):
    """Lookup a user by email or username, returning their password_hash for auth."""
    store = _active_store()
    user = store.get_user_by_login(login)
    if user:
        return user

    return None


def get_user(user_id, database_path=None, access_token=None):
    """Retrieve learner profile by user_id."""
    store = _active_store()

    # Try Supabase if token or cloud profile exists
    if is_supabase_enabled() and not _use_memory():
        try:
            cloud_user = supabase_get_user(user_id, access_token=access_token)
            if cloud_user and cloud_user.get("email"):
                return cloud_user
        except Exception:
            pass

    # Fall back to persistent local store
    return store.get_user(user_id)


def update_profile(user_id, bio, learning_goals, skills, database_path=None, access_token=None):
    """Update learner bio, learning goals, and skills."""
    store = _active_store()

    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_update_profile(user_id, bio, learning_goals, skills, access_token=access_token)
        except Exception:
            return False

    return store.update_profile(user_id, bio, learning_goals, skills)


def record_learning_activity(user_id, activity_type, xp_earned, database_path=None, completed_at=None, access_token=None):
    """Log an activity event and XP award."""
    store = _active_store()
    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_record_learning_activity(user_id, activity_type, xp_earned, completed_at=completed_at, access_token=access_token)
        except Exception:
            return None

    return store.record_learning_activity(user_id, activity_type, xp_earned, completed_at=completed_at)


def record_study_session(user_id, duration_minutes, xp_earned=30, database_path=None, access_token=None):
    """Record focus timer sprint and award XP."""
    store = _active_store()
    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_record_study_session(user_id, duration_minutes, xp_earned=xp_earned, access_token=access_token)
        except Exception:
            return None

    return store.record_study_session(user_id, duration_minutes, xp_earned=xp_earned)


def record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned, database_path=None, access_token=None):
    """Save challenge quiz results and award XP."""
    store = _active_store()
    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned, access_token=access_token)
        except Exception:
            return None

    return store.record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned)


def get_quiz_result(user_id, result_id, database_path=None, access_token=None):
    """Fetch quiz attempt outcome."""
    store = _active_store()
    if _is_cloud_user(user_id, access_token):
        try:
            res = supabase_get_quiz_result(user_id, result_id, access_token=access_token)
            if res:
                return res
        except Exception:
            pass

    return store.get_quiz_result(user_id, result_id)


def get_user_stats(user_id, database_path=None, access_token=None):
    """Fetch live XP, streak, accuracy, and study minutes."""
    store = _active_store()
    local_stats = store.get_user_stats(user_id)

    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_get_user_stats(user_id, access_token=access_token)
        except Exception:
            pass

    return local_stats


def get_leaderboard(database_path=None):
    """Fetch global XP rankings."""
    store = _active_store()
    if _use_cloud():
        try:
            return supabase_get_leaderboard()
        except Exception:
            pass

    return store.get_leaderboard()


def get_activity_counts(user_id, database_path=None, days=210, access_token=None):
    """Fetch 210-day activity array for heatmap."""
    store = _active_store()
    if _is_cloud_user(user_id, access_token):
        try:
            return supabase_get_activity_counts(user_id, days=days, access_token=access_token)
        except Exception:
            pass

    return store.get_activity_counts(user_id, days=days)


def seed_defaults_if_empty(database_path=None):
    """Ensure benchmark demo peers are populated."""
    init_db(database_path)
