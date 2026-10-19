"""
Nexus Learn Loop — Authentication Blueprint
Handles user registration, login, logout, and session lifecycle.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import database.database as db
from services.security import require_csrf, generate_csrf_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
@auth_bp.route("/login.html", methods=["GET", "POST"])
@require_csrf
def login():
    if request.method == "POST":
        login_input = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        next_url = request.args.get("next") or request.form.get("next") or url_for("dashboard.dashboard")

        if not login_input or not password:
            flash("Please enter both your username/email and password.", "error")
            return render_template("login.html")

        user = db.get_user_by_login(login_input)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['username']}! Streak active.", "success")
            return redirect(next_url)
        else:
            flash("Invalid credentials. Please check your username/email and password.", "error")
            return render_template("login.html")

    return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@auth_bp.route("/register.html", methods=["GET", "POST"])
@require_csrf
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        track = request.form.get("track", "Web & Python Full-Stack").strip()

        if not username or not email or not password:
            flash("All fields are required to create an account.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html")

        # Check existing username or email
        if db.get_user_by_login(username):
            flash(f"Username '{username}' is already taken. Please choose another.", "error")
            return render_template("register.html")
        if db.get_user_by_login(email):
            flash(f"An account with email '{email}' already exists. Please sign in.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        user_id = db.create_user(username, email, password_hash, learning_goals=track)
        db.record_learning_activity(user_id, "signup", 50)
        session["user_id"] = user_id
        flash(f"Account created successfully! Welcome to your learning loop, {username}. +50 XP awarded!", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("register.html")


@auth_bp.route("/logout", methods=["POST", "GET"])
@require_csrf
def logout():
    """Sign out the current learner. POST is preferred for state modification."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("dashboard.index"))
