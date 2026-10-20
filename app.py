"""
Nexus Learn Loop — Application Entrypoint
A competitive, gamified learning platform for Nexus learners, inspired by Duolingo & GitHub.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import requests
from database import database as database_service

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.urandom(32)
app.config["DATABASE"] = os.getenv(
    "DATABASE_PATH",
    str(Path(app.instance_path) / "nexus.db"),
)

# Enable CORS for local file:// previews
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.context_processor
def inject_user():
    user_id = session.get("user_id")
    user = database_service.get_user_by_id(user_id) if user_id is not None else None
    if user is None:
        if user_id is not None:
            session.pop("user_id", None)
        return {
            "current_user": SimpleNamespace(
                is_authenticated=False,
                username="Learner",
                xp=0,
            )
        }

    stats = database_service.get_user_stats(user["id"])
    return {
        "current_user": SimpleNamespace(
            is_authenticated=True,
            id=user["id"],
            username=user["username"],
            email=user["email"],
            xp=stats["total_xp"],
        )
    }


@app.teardown_appcontext
def close_database(_error):
    database_service.close_db(_error)


with app.app_context():
    database_service.init_db()


@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")

@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    user_id = session.get("user_id")
    stats = database_service.get_user_stats(user_id) if user_id else {
        "total_xp": 0,
        "study_minutes": 0,
        "study_session_count": 0,
        "quiz_count": 0,
        "accuracy_percent": 0,
        "correct_answers": 0,
        "total_questions": 0,
    }
    return render_template("dashboard.html", stats=stats)

@app.route("/quiz", methods=["GET", "POST"])
@app.route("/quiz.html", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        user_id = session.get("user_id")
        if user_id is None:
            flash("Sign in to save your quiz result.", "error")
            return redirect(url_for("login"))
        answer = request.form.get("answer", "").strip().upper()
        if answer not in {"A", "B", "C", "D"}:
            flash("Select an answer before submitting the quiz.", "error")
            return redirect(url_for("quiz"))
        database_service.record_quiz_result(
            user_id,
            "Python Jinja2 Expression Interpolation",
            int(answer == "B"),
            1,
        )
        return redirect(url_for("result"))
    return render_template("quiz.html")

@app.route("/result")
@app.route("/result.html")
def result():
    user_id = session.get("user_id")
    quiz_result = database_service.get_latest_quiz_result(user_id) if user_id else None
    return render_template("result.html", quiz_result=quiz_result)

@app.route("/leaderboard")
@app.route("/leaderboard.html")
def leaderboard():
    return render_template("leaderboard.html")

@app.route("/timer")
@app.route("/timer.html")
def timer():
    return render_template("timer.html")


@app.route("/study-sessions", methods=["POST"])
def save_study_session():
    user_id = session.get("user_id")
    if user_id is None:
        flash("Sign in to save your study session.", "error")
        return redirect(url_for("login"))

    try:
        duration_minutes = int(request.form.get("duration_minutes", ""))
        started_at = datetime.fromisoformat(
            request.form.get("started_at", "").replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        flash("The study session details are invalid.", "error")
        return redirect(url_for("timer"))

    if not 1 <= duration_minutes <= 180:
        flash("Study sessions must be between 1 and 180 minutes.", "error")
        return redirect(url_for("timer"))
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if started_at > now or (now - started_at).total_seconds() > 4 * 60 * 60:
        flash("The study session start time is invalid.", "error")
        return redirect(url_for("timer"))

    database_service.record_study_session(
        user_id,
        duration_minutes,
        started_at.astimezone(timezone.utc).isoformat(),
    )
    flash("Study session recorded! +30 XP awarded.", "success")
    return redirect(url_for("dashboard"))

@app.route("/resources")
@app.route("/resources.html")
def resources():
    return render_template("resources.html")

@app.route("/profile.html", methods=["GET", "POST"])
@app.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if request.method == "POST":
        if user_id is None:
            flash("Sign in to update your learner profile.", "error")
            return redirect(url_for("login"))
        database_service.update_learner_profile(
            user_id,
            request.form.get("bio", "").strip()[:1000],
            request.form.get("learning_goals", "").strip()[:2000],
            request.form.get("skills", "").strip()[:1000],
        )
        flash("Your learner profile has been updated.", "success")
        return redirect(url_for("profile"))

    user = database_service.get_user_by_id(user_id) if user_id is not None else None
    learner_profile = (
        database_service.get_learner_profile(user_id)
        if user_id is not None
        else None
    )
    stats = (
        database_service.get_user_stats(user_id)
        if user_id is not None
        else {
            "total_xp": 0,
            "quiz_count": 0,
            "accuracy_percent": 0,
            "study_minutes": 0,
        }
    )
    return render_template(
        "profile.html",
        profile_user=user,
        learner_profile=learner_profile,
        stats=stats,
    )

@app.route("/lwb")
@app.route("/lwb.html")
def lwb():
    return render_template("lwb.html")

@app.route("/ai-agent")
@app.route("/ai_agent.html")
def ai_agent():
    return render_template("ai_agent.html")

@app.route("/api/ai-chat", methods=["POST", "OPTIONS"])
def ai_chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    topic = data.get("topic", "General")

    if not user_message:
        return jsonify({"reply": "Please ask a question about your programming topic!"}), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # Query Google Gemini with multi-model fallback (e.g. gemini-2.5-flash, gemini-flash-latest)
    if api_key:
        models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]
        system_instruction = (
            "You are the Nexus Learn Loop AI Mentor, a friendly, concise programming tutor inspired by Duolingo. "
            f"The student is asking about: {topic}. "
            "Provide clear, encouraging explanations with brief code examples and best practices. Keep answers under 200 words."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_instruction}\n\nStudent Query: {user_message}"}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 600,
                "temperature": 0.4
            }
        }

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    result_json = res.json()
                    candidates = result_json.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        reply_text = candidates[0]["content"]["parts"][0]["text"]
                        return jsonify({"reply": reply_text})
            except Exception:
                continue

    # Intelligent contextual tutor fallback
    msg_lower = user_message.lower()

    if "jinja" in msg_lower or "template" in msg_lower:
        reply = (
            "**Jinja2 Template Interpolation**\n\n"
            "In Flask and Jinja2 templates:\n"
            "- Use `{{ expression }}` to render variables and evaluate expressions safely with auto-escaping.\n"
            "- Use `{% statement %}` for control flow like loops and conditionals (`for`, `if`).\n\n"
            "```html\n"
            "<!-- Safe rendering with default value -->\n"
            "<h1>Welcome, {{ user.name | default('Learner') }}</h1>\n"
            "```\n\n"
            "Use filters with the pipe `|` symbol, such as `| length`, `| upper`, or `| round`."
        )
    elif "sqlite" in msg_lower or "index" in msg_lower or "database" in msg_lower or "sql" in msg_lower:
        reply = (
            "**SQLite Query Optimization & Indexes**\n\n"
            "An index speeds up searches on frequently filtered columns:\n\n"
            "```sql\n"
            "-- Create an index on the user streak column\n"
            "CREATE INDEX idx_user_streak ON users(streak);\n\n"
            "-- Composite index for leaderboard rankings\n"
            "CREATE INDEX idx_rankings ON users(xp DESC, streak DESC);\n"
            "```\n\n"
            "💡 Always verify index usage by prefixing your query with `EXPLAIN QUERY PLAN`."
        )
    elif "git" in msg_lower or "conflict" in msg_lower or "branch" in msg_lower:
        reply = (
            "**Git Merge Conflicts & Branching**\n\n"
            "To resolve a merge conflict cleanly:\n"
            "1. Check status: `git status`\n"
            "2. Edit files to remove conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)\n"
            "3. Stage and commit:\n\n"
            "```bash\n"
            "git add <resolved-file>\n"
            "git commit -m \"fix: resolve merge conflict\"\n"
            "```"
        )
    elif "python" in msg_lower or "list" in msg_lower or "function" in msg_lower:
        reply = (
            "**Python Best Practices**\n\n"
            "List comprehensions allow clean, readable array transformations:\n\n"
            "```python\n"
            "# Transform and filter in one line\n"
            "raw_scores = [12, 45, 88, 92, 100]\n"
            "passing = [s for s in raw_scores if s >= 50]\n"
            "# Result: [88, 92, 100]\n"
            "```\n\n"
            "They are more performant and idiomatic than appending in a traditional loop."
        )
    elif "timer" in msg_lower or "pomodoro" in msg_lower or "focus" in msg_lower:
        reply = (
            "**Study Timer & Pomodoro Method**\n\n"
            "The 25-minute Pomodoro sprint is optimal for sustained cognitive focus:\n"
            "1. Work with zero distractions for 25 minutes.\n"
            "2. Take a 5-minute break.\n"
            "3. After 4 sprints, take a longer 15-30 minute break.\n\n"
            "Completing sessions on the Nexus Study Timer earns you +30 XP!"
        )
    else:
        reply = (
            f"**Nexus AI Mentor ({topic})**\n\n"
            f"Regarding your question on '{user_message}':\n\n"
            "1. **Core Concept**: Break complex problems into atomic, testable units.\n"
            "2. **Implementation**: Build incrementally, validating output at each step.\n"
            "3. **Practice**: Reinforce your knowledge by solving daily challenges and logging focus sessions on the platform."
        )

    return jsonify({"reply": reply})

@app.route("/login", methods=["GET", "POST"])
@app.route("/login.html", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database_service.get_user_by_identifier(identifier)
        if user is None or not database_service.verify_password(user, password):
            flash("Invalid username/email or password.", "error")
            return render_template("login.html"), 401
        session.clear()
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
@app.route("/register.html", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not 3 <= len(username) <= 30:
            flash("Username must be between 3 and 30 characters.", "error")
            return render_template("register.html"), 400
        if not email or len(email) > 254 or "@" not in email:
            flash("Enter a valid email address.", "error")
            return render_template("register.html"), 400
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html"), 400
        try:
            user = database_service.create_user(username, email, password)
        except sqlite3.IntegrityError:
            flash("That username or email is already registered.", "error")
            return render_template("register.html"), 409
        session.clear()
        session["user_id"] = user["id"]
        flash("Account created successfully! Welcome to your learning loop.", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
