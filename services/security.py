"""
Nexus Learn Loop — Deployment Security & Auth Guards
Provides CSRF protection, origin validation, production secret configuration,
and route authentication boundaries.
"""

import os
import secrets
from functools import wraps
from flask import session, request, redirect, url_for, flash, jsonify, abort, current_app


def get_secret_key():
    """
    Retrieve SECRET_KEY from environment.
    Enforces a strict secret in production, with a secure random key for development.
    """
    env = os.getenv("FLASK_ENV", os.getenv("ENV", "development")).lower()
    secret = os.getenv("SECRET_KEY", "").strip()

    if env == "production":
        if not secret or secret == "nexus-learn-loop-dev-secret-key-2026":
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION: A strong SECRET_KEY environment variable "
                "must be explicitly set when running in production mode."
            )
        return secret

    # Development or testing fallback
    return secret or "nexus-learn-loop-dev-secret-key-2026"


def generate_csrf_token():
    """Generate or retrieve a cryptographically secure CSRF token in the session."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf_token(token):
    """Verify that the provided token matches the session CSRF token."""
    expected = session.get("_csrf_token")
    if not expected or not token:
        return False
    return secrets.compare_digest(str(expected), str(token))


def require_csrf(f):
    """Decorator to enforce CSRF token verification on state-modifying requests."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app and (current_app.config.get("TESTING") or current_app.config.get("WTF_CSRF_ENABLED") is False):
            return f(*args, **kwargs)

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Check form data, JSON payload, or X-CSRF-Token header
            token = (
                request.form.get("csrf_token")
                or (request.get_json(silent=True) or {}).get("csrf_token")
                or request.headers.get("X-CSRF-Token")
            )
            # Allow API clients or testing to pass if CSRF is validated or header matches
            if not validate_csrf_token(token):
                # If JSON API request, return 403 JSON
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"success": False, "error": "CSRF token validation failed."}), 403
                flash("Your session security token expired. Please try again.", "error")
                return redirect(request.referrer or url_for("dashboard.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    """
    Enforces authentication boundaries.
    Requires an active user_id in the session.
    Redirects guest visitors to login with an informative flash message,
    or returns 401 Unauthorized for JSON API routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Authentication required. Please sign in to perform this action.",
                    "is_authenticated": False
                }), 401
            flash("Please sign in or create an account to access this page.", "info")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def configure_safe_cors(response):
    """
    Restrict CORS headers to permitted application origins.
    Avoids wildcard '*' when session cookies are used.
    """
    origin = request.headers.get("Origin")
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]

    # Allow local file preview or exact origin matches
    if origin and (origin in allowed_origins or origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:")):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-CSRF-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS,PUT,DELETE"

    return response
