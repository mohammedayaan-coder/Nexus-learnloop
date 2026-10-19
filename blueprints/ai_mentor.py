"""
Nexus Learn Loop — AI Mentor Blueprint
Handles AI Mentor workspace, Gemini 3.8 / 2.0 API interaction, models listing, and tutor fallback.
"""

import os
from flask import Blueprint, render_template, request, jsonify
import requests

ai_mentor_bp = Blueprint("ai_mentor", __name__)


@ai_mentor_bp.route("/ai-agent")
@ai_mentor_bp.route("/ai_agent.html")
def ai_agent():
    """Interactive AI programming mentor interface."""
    return render_template("ai_agent.html")


@ai_mentor_bp.route("/api/ai-status", methods=["GET", "OPTIONS"])
def ai_status():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
    has_key = bool(api_key and (api_key.startswith("AIzaSy") or api_key.startswith("AQ.") or len(api_key) >= 30))
    masked_key = ""
    key_type = "none"
    if has_key:
        masked_key = f"{api_key[:6]}...{api_key[-4:]}"
        key_type = "auth_key (AQ.)" if api_key.startswith("AQ.") else "standard (AIzaSy)"

    return jsonify({
        "status": "online",
        "has_backend_key": has_key,
        "key_preview": masked_key,
        "key_type": key_type,
        "default_model": "gemini-3.8-flash",
        "supported_models": [
            "gemini-3.8-flash",
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ]
    })


@ai_mentor_bp.route("/api/ai-models", methods=["GET", "POST", "OPTIONS"])
def ai_models():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    api_key = ""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        api_key = data.get("apiKey", "").strip().strip('"').strip("'")
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")

    fallback_models = [
        "gemini-3.8-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    if not api_key:
        return jsonify({"success": True, "models": fallback_models}), 200

    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            supported = []
            for m in models_data:
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])
                if not methods or "generateContent" in methods:
                    supported.append(name)
            if "gemini-3.8-flash" not in supported:
                supported.insert(0, "gemini-3.8-flash")
            return jsonify({"success": True, "models": supported})
        err_json = res.json().get("error", {}) if res.content else {}
        return jsonify({
            "success": False,
            "error": err_json.get("message") or f"HTTP {res.status_code}",
            "models": fallback_models
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "models": fallback_models}), 200


@ai_mentor_bp.route("/api/ai-test-key", methods=["POST", "OPTIONS"])
def ai_test_key():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    key_to_test = data.get("apiKey", "").strip().strip('"').strip("'")
    if not key_to_test:
        key_to_test = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")

    if not key_to_test:
        return jsonify({"success": False, "error": "No API key provided or found in environment."}), 400

    test_model = data.get("model", "gemini-3.8-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{test_model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key_to_test
    }
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}],
        "generationConfig": {"maxOutputTokens": 5}
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=6)
        if res.status_code == 200:
            return jsonify({
                "success": True,
                "message": f"Connection successful with {test_model}!",
                "model": test_model
            })
        err_json = res.json().get("error", {}) if res.content else {}
        err_msg = err_json.get("message") or f"HTTP {res.status_code}"
        return jsonify({"success": False, "error": err_msg, "status_code": res.status_code}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@ai_mentor_bp.route("/api/ai-chat", methods=["POST", "OPTIONS"])
def ai_chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    topic = data.get("topic", "General")
    requested_model = data.get("model", "gemini-3.8-flash").strip()
    history = data.get("history", [])

    if not user_message:
        return jsonify({"reply": "Please ask a question about your programming topic!"}), 400

    # Read backend API key (or client-forwarded key if provided)
    client_key = data.get("apiKey", "").strip().strip('"').strip("'")
    api_key = client_key or os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")

    api_error = None
    if api_key:
        models_to_try = [requested_model] if requested_model else []
        for m in ["gemini-3.8-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"]:
            if m not in models_to_try:
                models_to_try.append(m)

        system_instruction = (
            "You are the Nexus Learn Loop AI Mentor, a friendly, concise programming tutor inspired by Duolingo. "
            f"The student is asking about: {topic}. "
            "Provide clear, encouraging explanations with brief code examples and best practices. Keep answers under 250 words."
        )

        contents = []
        if history and isinstance(history, list):
            for turn in history[-6:]:
                role = "user" if turn.get("role") == "user" else "model"
                text = turn.get("text", "").strip()
                if text:
                    contents.append({
                        "role": role,
                        "parts": [{"text": text}]
                    })

        contents.append({
            "role": "user",
            "parts": [{"text": f"Topic: {topic}\nQuestion: {user_message}"}]
        })

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 800, "temperature": 0.4}
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                res = requests.post(url, json=payload, headers=headers, timeout=9)
                if res.status_code == 200:
                    result_json = res.json()
                    candidates = result_json.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        reply_text = "".join(p.get("text", "") for p in parts if "text" in p)
                        if reply_text:
                            return jsonify({
                                "reply": reply_text,
                                "source": "gemini",
                                "model": model_name
                            })
                else:
                    err_data = res.json().get("error", {}) if res.content else {}
                    api_error = err_data.get("message") or f"HTTP {res.status_code}"
                    if res.status_code in (400, 401, 403):
                        break
            except Exception as e:
                api_error = str(e)
                continue

    # Fallback offline tutor
    msg_lower = user_message.lower().strip()
    if msg_lower in ["hi", "hello", "hey", "hola", "yo", "sup", "greetings"] or msg_lower.startswith(("hi ", "hello ", "hey ")):
        reply = (
            "**Hello! 👋 Welcome to Nexus Learn Loop!**\n\n"
            f"I'm your AI Mentor for **{topic}**. I'm here to help you:\n"
            "- Explain programming concepts (Python, Flask, SQL, Git, etc.)\n"
            "- Debug tricky syntax errors or logic issues\n"
            "- Walk through practice problems and daily quiz concepts\n\n"
            "What would you like to explore or learn today?"
        )
    elif "jinja" in msg_lower or "template" in msg_lower:
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

    if api_error:
        reply = (
            f"> [!WARNING]\n"
            f"> Gemini Live API notice: *{api_error}*. Showing offline response.\n"
            "> Check your `GEMINI_API_KEY` in `.env` or click **Set Gemini Key** in the UI to update.\n\n"
            f"{reply}"
        )

    return jsonify({"reply": reply, "source": "offline_tutor", "api_error": api_error})
