"""Local SQLite registration and session authentication routes."""

import sqlite3
from urllib.parse import urlsplit

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import database.database as db
from services.security import require_csrf

auth_bp = Blueprint("auth", __name__)


def _wants_json():
    return request.is_json or "application/json" in request.headers.get("Accept", "")


def _safe_next(value):
    """Accept only a local relative URL for post-login redirects."""
    if not value:
        return url_for("dashboard.dashboard")
    parsed = urlsplit(value)
    if (parsed.scheme or parsed.netloc or not value.startswith("/")
            or value.startswith(("//", "/\\")) or "\\" in value):
        return url_for("dashboard.dashboard")
    return value


@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login.html", methods=["GET", "POST"])
@require_csrf
def login():
    if request.method == "GET":
        return render_template("login.html", next_url=_safe_next(request.args.get("next")))

    identity = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        identity = str(payload.get("username", payload.get("email", ""))).strip()
        password = str(payload.get("password", ""))
    next_url = _safe_next(request.args.get("next") or request.form.get("next"))

    user = db.get_user_by_login(identity) if identity and password else None
    if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
        message = "Invalid username/email or password."
        if _wants_json():
            return jsonify({"success": False, "error": message}), 401
        return render_template("login.html", error=message, next_url=next_url)

    # Flask's default session is a signed client cookie. Clearing it prevents
    # pre-authentication state from carrying into the authenticated session.
    session.clear()
    session["user_id"] = user["id"]
    if _wants_json():
        return jsonify({"success": True, "redirect": next_url})
    return redirect(next_url)


@auth_bp.route("/register", methods=["GET", "POST"])
@auth_bp.route("/register.html", methods=["GET", "POST"])
@require_csrf
def register():
    if request.method == "GET":
        return render_template("register.html")

    payload = request.get_json(silent=True) or {} if request.is_json else request.form
    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    track = str(payload.get("track", "Web & Python Full-Stack")).strip()

    error = None
    error_status = 400
    if not username or not email or not password:
        error = "All fields are required to create an account."
    elif len(username) > 80 or len(email) > 254 or len(track) > 120:
        error = "One or more fields are too long."
    elif "@" not in email or email.startswith("@") or email.endswith("@"):
        error = "Enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters long."
    elif db.get_user_by_login(username) or db.get_user_by_login(email):
        error = "An account with this username or email already exists. Please sign in."
        error_status = 409

    if error:
        if _wants_json():
            return jsonify({"success": False, "error": error}), error_status
        return render_template("register.html", error=error), error_status

    try:
        user_id = db.create_user(username, email, generate_password_hash(password), learning_goals=track)
    except sqlite3.IntegrityError:
        # Covers a duplicate arriving between the lookup and insert.
        message = "An account with this username or email already exists. Please sign in."
        if _wants_json():
            return jsonify({"success": False, "error": message}), 409
        return render_template("register.html", error=message), 409

    session.clear()
    session["user_id"] = user_id
    if _wants_json():
        return jsonify({"success": True, "redirect": url_for("dashboard.dashboard")}), 201
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.route("/logout", methods=["POST"])
@require_csrf
def logout():
    session.clear()
    if _wants_json():
        return jsonify({"success": True, "redirect": url_for("dashboard.index")})
    return redirect(url_for("dashboard.index"))
