"""
Nexus Learn Loop -- Authentication Blueprint

Fallback Strategy
-----------------
- Supabase Auth is tried FIRST for both login and registration.
- On ANY soft Supabase failure (rate limit, SMTP, network timeout)
  the system silently falls through to the local persistent store.
- Hard errors (email already registered) are surfaced to the user.
- Users are NEVER locked out due to Supabase free-tier limits.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import database.database as db
from database.supabase_client import (
    is_supabase_enabled,
    supabase_sign_in,
    supabase_sign_up,
)
from services.security import require_csrf

auth_bp = Blueprint("auth", __name__)

# Hard Supabase errors: email already taken, surface to user
_HARD_KEYWORDS = ["already registered", "user already exists", "email already", "email_exists"]
# Soft Supabase errors: transient, fall through to local store silently
_SOFT_KEYWORDS = ["rate limit", "over_email_send_rate_limit", "exceeded",
                  "smtp", "connection", "timeout", "service unavailable", "too many requests"]


def _wants_json():
    """Return True if the client expects a JSON response."""
    return (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def _is_soft_error(err_str):
    low = err_str.lower()
    return any(k in low for k in _SOFT_KEYWORDS)


def _is_hard_error(err_str):
    low = err_str.lower()
    return any(k in low for k in _HARD_KEYWORDS)


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login.html", methods=["GET", "POST"])
@require_csrf
def login():
    if request.method == "POST":
        login_input = request.form.get("username", "").strip()
        password    = request.form.get("password", "").strip()
        next_url    = (request.args.get("next") or request.form.get("next")
                       or url_for("dashboard.dashboard"))

        if not login_input or not password:
            err = "Please enter both your username/email and password."
            if _wants_json():
                return jsonify({"success": False, "error": err}), 400
            return redirect(url_for("auth.login", error=err))

        # 1. Try Supabase Auth
        if is_supabase_enabled():
            try:
                user, token, _ = supabase_sign_in(login_input, password)
                if user:
                    session["user_id"] = user["id"]
                    if token:
                        session["access_token"] = token
                    if _wants_json():
                        return jsonify({"success": True, "redirect": next_url})
                    return redirect(next_url)
            except Exception as e:
                print(f"[Auth] Supabase login soft-fail, trying local store: {e}")

        # 2. Fallback: local persistent store
        user = db.get_user_by_login(login_input)
        if user and user.get("password_hash") and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            if _wants_json():
                return jsonify({"success": True, "redirect": next_url})
            return redirect(next_url)

        err_msg = "Invalid username/email or password."
        if _wants_json():
            return jsonify({"success": False, "error": err_msg}), 401
        return redirect(url_for("auth.login", error=err_msg))

    return render_template("login.html")


# ---------------------------------------------------------------------------
# REGISTER
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
@auth_bp.route("/register.html", methods=["GET", "POST"])
@require_csrf
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email",    "").strip()
        password = request.form.get("password", "").strip()
        track    = request.form.get("track",    "Web and Python Full-Stack").strip()

        if not username or not email or not password:
            err = "All fields are required to create an account."
            if _wants_json():
                return jsonify({"success": False, "error": err}), 400
            return redirect(url_for("auth.register", error=err))

        if len(password) < 6:
            err = "Password must be at least 6 characters long."
            if _wants_json():
                return jsonify({"success": False, "error": err}), 400
            return redirect(url_for("auth.register", error=err))

        # Duplicate check against local store
        if db.get_user_by_login(username) or db.get_user_by_login(email):
            err = "An account with this username or email already exists. Please sign in."
            if _wants_json():
                return jsonify({"success": False, "error": err}), 409
            return redirect(url_for("auth.register", error=err))

        # 1. Try Supabase Auth (best-effort, NEVER blocks registration)
        supabase_uid   = None
        supabase_token = None

        if is_supabase_enabled():
            try:
                user_info, sb_err = supabase_sign_up(username, email, password, learning_goals=track)
                if user_info:
                    supabase_uid   = user_info["id"]
                    supabase_token = user_info.get("access_token")
                elif sb_err:
                    err_str = str(sb_err)
                    if _is_hard_error(err_str):
                        err = "An account with this email already exists. Please sign in instead."
                        if _wants_json():
                            return jsonify({"success": False, "error": err}), 409
                        return redirect(url_for("auth.register", error=err))
                    else:
                        # Soft error (rate limit, SMTP, etc.) -- fall through to local store
                        print(f"[Auth] Supabase register soft-fail, using local store: {sb_err}")
            except Exception as e:
                print(f"[Auth] Supabase register exception, using local store: {e}")

        # 2. Always persist locally (primary path when Supabase is rate-limited)
        password_hash = generate_password_hash(password)

        if supabase_uid:
            db.create_user(username=username, email=email, password_hash=password_hash,
                           learning_goals=track, password=password, user_id=supabase_uid)
            if not supabase_token:
                msg = "Account created! Please check your email to confirm it, then sign in."
                if _wants_json():
                    return jsonify({"success": True, "requires_confirmation": True,
                                    "message": msg, "redirect": url_for("auth.login")})
                return redirect(url_for("auth.login"))
            user_id = supabase_uid
        else:
            # Supabase unavailable -- create entirely in local store
            user_id = db.create_user(username=username, email=email, password_hash=password_hash,
                                     learning_goals=track, password=password)
            db.record_learning_activity(user_id, "signup", 50)

        session["user_id"] = user_id
        if supabase_token:
            session["access_token"] = supabase_token

        redirect_target = url_for("dashboard.dashboard")
        if _wants_json():
            return jsonify({"success": True, "redirect": redirect_target})
        return redirect(redirect_target)

    return render_template("register.html")


# ---------------------------------------------------------------------------
# LOGOUT
# ---------------------------------------------------------------------------

@auth_bp.route("/logout", methods=["POST", "GET"])
@require_csrf
def logout():
    """Sign out the current learner and invalidate the session."""
    session.clear()
    if _wants_json():
        return jsonify({"success": True, "redirect": url_for("dashboard.index")})
    return redirect(url_for("dashboard.index"))

