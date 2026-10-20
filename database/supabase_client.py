"""
Nexus Learn Loop — Supabase PostgreSQL Persistence Adapter
Direct drop-in replacement for SQLite database operations.
Connects Flask directly to Supabase Auth and PostgreSQL tables:
- auth.users (User account credentials and auth tokens)
- public.learner_profiles (bio, learning_goals TEXT[], skills TEXT[])
- public.learning_activities (XP logs and completed activities)
- public.study_sessions (Focus timer duration and timestamps)
- public.quiz_results (Challenges, scores, total questions)
"""

import os
from datetime import date, datetime, timedelta, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from services.streak_service import calculate_streak

_supabase_client = None


def _log_err(prefix, e):
    """Quiet expected RLS permission errors so they do not spam the console."""
    err_str = str(e)
    if "42501" in err_str or "permission denied" in err_str.lower() or "PGRST205" in err_str:
        return
    print(f"[{prefix}]: {e}")


def get_supabase_url():
    """Retrieve Supabase Project URL from environment."""
    return os.getenv("SUPABASE_URL", "").strip()


def get_supabase_key():
    """Retrieve primary Supabase API key (service role preferred for backend, else anon)."""
    return (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )


def get_supabase_anon_key():
    """Retrieve Supabase Anon / Publishable key."""
    return os.getenv("SUPABASE_ANON_KEY", "").strip() or os.getenv("SUPABASE_KEY", "").strip()


def get_supabase_service_role_key():
    """Retrieve Supabase Service Role key if provided."""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if key and not key.startswith("sb_publishable_"):
        return key
    return None


def get_supabase_client(access_token=None):
    """
    Get a Supabase client.
    If access_token is provided, returns an authenticated client bound to that user
    so that PostgreSQL Row Level Security (auth.uid() = user_id) is enforced.
    Otherwise, returns the cached backend server client.
    """
    global _supabase_client
    url = get_supabase_url()
    anon_key = get_supabase_anon_key() or get_supabase_key()

    if not url or not anon_key:
        return None

    try:
        from supabase import create_client, ClientOptions

        if access_token:
            options = ClientOptions(headers={"Authorization": f"Bearer {access_token}"})
            return create_client(url, anon_key, options=options)

        if _supabase_client is not None:
            return _supabase_client

        # Prefer service role key if available for server-level queries
        svc_key = get_supabase_service_role_key()
        active_key = svc_key if svc_key else (get_supabase_key() or anon_key)
        _supabase_client = create_client(url, active_key)
        return _supabase_client
    except Exception as e:
        print(f"[Supabase Client Error]: {e}")
        return None


def is_supabase_enabled():
    """Check if Supabase is configured and ready."""
    use_supabase = os.getenv("USE_SUPABASE")
    if use_supabase is not None and use_supabase.strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    return bool(
        get_supabase_url()
        and (get_supabase_key() or get_supabase_anon_key())
    )


def _format_list_field(val):
    """Normalize array or string field into a comma-separated string for display."""
    if isinstance(val, (list, tuple)):
        return ", ".join(str(item).strip() for item in val if str(item).strip())
    if isinstance(val, str):
        # Could be Postgres array literal like '{item1,item2}'
        clean = val.strip()
        if clean.startswith("{") and clean.endswith("}"):
            items = [s.strip().strip('"') for s in clean[1:-1].split(",") if s.strip()]
            return ", ".join(items)
        return clean
    return ""


def _to_text_array(val):
    """Convert string or list into a Python list of strings for Postgres TEXT[] column."""
    if isinstance(val, (list, tuple)):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        clean = val.strip()
        if clean.startswith("{") and clean.endswith("}"):
            clean = clean[1:-1]
        items = [s.strip().strip('"') for s in clean.split(",") if s.strip()]
        return items if items else ([clean] if clean else [])
    return []


def _query_activities_table(client, query_builder_fn):
    """
    Execute query against public.learning_activities,
    falling back to public.learning_activity if plural table is not found.
    """
    for table_name in ("learning_activities", "learning_activity"):
        try:
            tbl = client.table(table_name)
            res = query_builder_fn(tbl).execute()
            return res.data or []
        except Exception as e:
            err_str = str(e)
            if "PGRST205" in err_str or "Could not find the table" in err_str:
                continue
            raise e
    return []


def _insert_activity_record(client, record):
    """Insert into learning_activities or learning_activity."""
    for table_name in ("learning_activities", "learning_activity"):
        try:
            res = client.table(table_name).insert(record).execute()
            if res.data:
                return res.data[0].get("id")
            return None
        except Exception as e:
            err_str = str(e)
            if "PGRST205" in err_str or "Could not find the table" in err_str:
                continue
            print(f"[Supabase Insert Activity Warning on {table_name}]: {e}")
            break
    return None


def _rpc_id(value):
    """Normalize scalar IDs returned by PostgREST RPC calls."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value) if value.isdigit() else value
    if isinstance(value, list) and value:
        return _rpc_id(value[0])
    if isinstance(value, dict):
        return _rpc_id(value.get("id"))
    return None


# ==============================================================================
# Authentication & User Management
# ==============================================================================

def supabase_sign_up(username, email, password, learning_goals="Web & Python Full-Stack"):
    """
    Register a user using Supabase Auth. The database trigger creates the
    profile and signup XP event atomically, including before email confirmation.
    """
    client = get_supabase_client()
    if not client:
        return None, "Supabase client not configured"

    try:
        # Try registering via Supabase Auth
        res = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "username": username,
                    "learning_goals": learning_goals,
                }
            }
        })
    except Exception as e:
        err_msg = str(e)
        if "already registered" in err_msg.lower() or "user already exists" in err_msg.lower():
            return None, f"An account with email '{email}' already exists."
        return None, err_msg

    user = res.user if res else None
    if not user:
        return None, "Failed to create user in Supabase Auth."

    user_id = str(user.id)
    session_data = res.session
    access_token = session_data.access_token if session_data else None

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "access_token": access_token,
        "is_demo": False,
        "created_at": getattr(user, "created_at", None) or datetime.now(timezone.utc).isoformat(),
        "session": session_data,
    }, None


def supabase_sign_in(login, password):
    """
    Authenticate against Supabase Auth using email or username.
    Returns (user_dict, access_token, error_message).
    """
    client = get_supabase_client()
    if not client:
        return None, None, "Supabase client not configured."

    login_str = (login or "").strip()
    email_to_use = login_str

    # If login is not an email, resolve email from username
    if "@" not in login_str:
        resolved_email = supabase_find_email_by_username(login_str)
        if resolved_email:
            email_to_use = resolved_email

    try:
        res = client.auth.sign_in_with_password({
            "email": email_to_use,
            "password": password
        })
    except Exception as e:
        err_msg = str(e)
        if "Invalid login credentials" in err_msg:
            return None, None, "Invalid credentials. Please check your username/email and password."
        if "Email not confirmed" in err_msg:
            return None, None, "Email not confirmed. Please check your email inbox to confirm your account."
        return None, None, err_msg

    if not res or not res.user:
        return None, None, "Invalid login credentials."

    user = res.user
    user_id = str(user.id)
    session_data = res.session
    access_token = session_data.access_token if session_data else None

    # Resolve username from user metadata
    metadata = getattr(user, "user_metadata", {}) or {}
    username = metadata.get("username") or login_str

    user_dict = {
        "id": user_id,
        "username": username,
        "email": user.email or email_to_use,
        "created_at": getattr(user, "created_at", "") or datetime.now(timezone.utc).isoformat(),
        "is_demo": False,
        "access_token": access_token,
    }
    return user_dict, access_token, None


def supabase_find_email_by_username(username):
    """Resolve a username through a service-role-only RPC; never expose emails publicly."""
    if not get_supabase_service_role_key():
        return None
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.rpc("lookup_auth_email_by_username", {"requested_username": username}).execute()
        if isinstance(res.data, str):
            return res.data
        if res.data and isinstance(res.data, list):
            return res.data[0]
    except Exception:
        pass

    return None


def supabase_get_user(user_id, access_token=None):
    """
    Fetch a user row with their profile information from Supabase.
    """
    if not user_id:
        return None

    client = get_supabase_client(access_token) or get_supabase_client()
    if not client:
        return None

    uid_str = str(user_id)
    profile_data = {}
    try:
        res = client.table("learner_profiles").select("*").eq("user_id", uid_str).limit(1).execute()
        if res.data:
            profile_data = res.data[0]
    except Exception as e:
        _log_err("Supabase Get User Profile Error", e)

    # Fetch user metadata from auth
    username = profile_data.get("username")
    email = profile_data.get("email")
    created_at = profile_data.get("created_at") or datetime.now(timezone.utc).isoformat()
    is_demo = False

    try:
        # If client has auth.get_user with access_token
        if access_token:
            u_res = client.auth.get_user(access_token)
            if u_res and u_res.user:
                email = u_res.user.email or email
                meta = u_res.user.user_metadata or {}
                username = meta.get("username") or username
                created_at = u_res.user.created_at or created_at
    except Exception:
        pass

    # Also check public.users if it exists for username/email
    try:
        u_table_res = client.table("users").select("*").eq("id", uid_str).limit(1).execute()
        if u_table_res.data:
            row = u_table_res.data[0]
            username = row.get("username") or username
            email = row.get("email") or email
            is_demo = bool(row.get("is_demo", False))
            created_at = row.get("created_at") or created_at
    except Exception:
        pass

    if not profile_data and not email and not username:
        return None

    raw_goals = profile_data.get("learning_goals", "")
    raw_skills = profile_data.get("skills", "")

    return {
        "id": uid_str,
        "username": username,
        "email": email,
        "created_at": created_at,
        "is_demo": is_demo,
        "bio": profile_data.get("bio", "") or "",
        "learning_goals": _format_list_field(raw_goals) or "Web & Python Full-Stack",
        "skills": _format_list_field(raw_skills) or "Python, Flask, Supabase",
    }


def supabase_update_profile(user_id, bio, learning_goals, skills, access_token=None):
    """
    Update learner profile in Supabase.
    Handles TEXT[] or TEXT columns dynamically.
    """
    if not user_id:
        return False

    client = get_supabase_client(access_token) or get_supabase_client()
    if not client:
        return False

    uid_str = str(user_id)
    goals_arr = _to_text_array(learning_goals)
    skills_arr = _to_text_array(skills)

    payload = {
        "bio": bio or "",
        "learning_goals": goals_arr,
        "skills": skills_arr,
    }

    try:
        res = client.table("learner_profiles").update(payload).eq("user_id", uid_str).execute()
        if res.data:
            return True
        # If no row updated, try upsert
        payload["user_id"] = uid_str
        client.table("learner_profiles").upsert(payload, on_conflict="user_id").execute()
        return True
    except Exception as e:
        # Fallback to string columns if text[] was rejected
        try:
            fallback_payload = {
                "bio": bio or "",
                "learning_goals": learning_goals or "",
                "skills": skills or "",
            }
            res = client.table("learner_profiles").update(fallback_payload).eq("user_id", uid_str).execute()
            if res.data:
                return True
            fallback_payload["user_id"] = uid_str
            client.table("learner_profiles").upsert(fallback_payload, on_conflict="user_id").execute()
            return True
        except Exception as pe:
            print(f"[Supabase Profile Update Error]: {pe}")
            return False


# ==============================================================================
# Learning Activities, Quizzes & Study Sessions
# ==============================================================================

def supabase_record_learning_activity(user_id, activity_type, xp_earned, completed_at=None, access_token=None):
    """Record an XP event into learning_activities in Supabase."""
    if not user_id:
        return None

    # Activity writes require the server's service-role client. End-user JWTs
    # cannot award XP directly under the schema's grants and RLS rules.
    client = get_supabase_client()
    if not client:
        return None

    record = {
        "user_id": str(user_id),
        "activity_type": str(activity_type),
        "xp_earned": int(xp_earned or 0),
    }
    if completed_at:
        record["completed_at"] = completed_at

    return _insert_activity_record(client, record)


def supabase_record_study_session(user_id, duration_minutes, xp_earned=30, access_token=None):
    """
    Insert a focus sprint into study_sessions and log the XP reward.
    """
    if not user_id:
        return None

    client = get_supabase_client()
    if not client:
        return None

    try:
        res = client.rpc("record_study_session_with_xp", {
            "p_user_id": str(user_id),
            "p_duration_minutes": int(duration_minutes),
            "p_xp_earned": int(xp_earned),
        }).execute()
        return _rpc_id(res.data)
    except Exception as e:
        print(f"[Supabase Record Study Session Warning]: {e}")
        return None


def supabase_record_quiz_result(user_id, quiz_name, score, total_questions, xp_earned, access_token=None):
    """
    Record quiz outcome in quiz_results and log XP in learning_activities.
    """
    if not user_id:
        return None

    client = get_supabase_client()
    if not client:
        return None

    try:
        res = client.rpc("record_quiz_result_with_xp", {
            "p_user_id": str(user_id),
            "p_quiz_name": str(quiz_name),
            "p_score": int(score),
            "p_total_questions": int(total_questions),
            "p_xp_earned": int(xp_earned),
        }).execute()
        return _rpc_id(res.data)
    except Exception as e:
        print(f"[Supabase Record Quiz Warning]: {e}")
        return None


def supabase_get_quiz_result(user_id, result_id, access_token=None):
    """Fetch a single quiz attempt by id."""
    if not user_id or not result_id:
        return None

    client = get_supabase_client(access_token) or get_supabase_client()
    if not client:
        return None

    try:
        res = (
            client.table("quiz_results")
            .select("id, quiz_name, score, total_questions, completed_at")
            .eq("user_id", str(user_id))
            .eq("id", result_id)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[Supabase Get Quiz Result Error]: {e}")
    return None


def supabase_get_user_stats(user_id, access_token=None):
    """
    Aggregate live stats for a user from Supabase PostgreSQL.
    """
    default_stats = {
        "xp": 0,
        "activities_completed": 0,
        "quizzes_solved": 0,
        "correct_answers": 0,
        "questions_answered": 0,
        "study_minutes": 0,
        "study_hours": 0.0,
        "sessions_today": 0,
        "accuracy": 0,
        "streak": 0
    }

    if not user_id:
        return default_stats

    client = get_supabase_client(access_token) or get_supabase_client()
    if not client:
        return default_stats

    uid_str = str(user_id)

    # 1. Activities & XP
    activities = []
    try:
        activities = _query_activities_table(
            client,
            lambda tbl: tbl.select("xp_earned, completed_at").eq("user_id", uid_str)
        )
    except Exception as e:
        _log_err("Supabase Stats Activities Error", e)

    total_xp = sum(a.get("xp_earned", 0) for a in activities)
    act_dates = [a["completed_at"][:10] for a in activities if a.get("completed_at")]
    streak = calculate_streak(act_dates)

    # 2. Study sessions
    sessions = []
    try:
        res = client.table("study_sessions").select("duration_minutes, completed_at").eq("user_id", uid_str).execute()
        sessions = res.data or []
    except Exception as e:
        _log_err("Supabase Stats Sessions Error", e)

    study_minutes = sum(s.get("duration_minutes", 0) for s in sessions)
    study_hours = round(study_minutes / 60, 1)

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sessions_today = sum(1 for s in sessions if str(s.get("completed_at", "")).startswith(today_str))

    # 3. Quiz results
    quizzes = []
    try:
        res = client.table("quiz_results").select("score, total_questions").eq("user_id", uid_str).execute()
        quizzes = res.data or []
    except Exception as e:
        _log_err("Supabase Stats Quizzes Error", e)

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


def supabase_get_activity_counts(user_id, days=210, access_token=None):
    """
    Generate 210-day activity counts for GitHub-style green heatmap.
    """
    counts = [0] * days
    if not user_id:
        return counts

    client = get_supabase_client(access_token) or get_supabase_client()
    if not client:
        return counts

    today = datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    uid_str = str(user_id)

    activities = []
    try:
        activities = _query_activities_table(
            client,
            lambda tbl: tbl.select("completed_at").eq("user_id", uid_str)
        )
    except Exception as e:
        _log_err("Supabase Heatmap Error", e)
        return counts

    for a in activities:
        raw_date = a.get("completed_at")
        if not raw_date:
            continue
        try:
            day_str = str(raw_date)[:10]
            act_date = date.fromisoformat(day_str)
            if first_day <= act_date <= today:
                day_idx = (act_date - first_day).days
                counts[day_idx] += 1
        except Exception:
            continue

    return counts


def supabase_get_leaderboard():
    """
    Fetch global learner rankings from Supabase PostgreSQL.
    """
    client = get_supabase_client()
    if not client:
        return []

    # First attempt: query leaderboard view
    try:
        res = client.table("leaderboard").select("*").order("xp", desc=True).limit(20).execute()
        if res.data:
            return [
                {
                    "id": r.get("id"),
                    "username": r.get("username") or "Learner",
                    "is_demo": bool(r.get("is_demo", False)),
                    "learning_goals": _format_list_field(r.get("learning_goals", "")),
                    "xp": r.get("xp", 0),
                }
                for r in res.data
            ]
    except Exception:
        pass

    return []
