"""AI mentor page and optional Gemini-backed chat endpoints."""

import os

import requests
from flask import Blueprint, jsonify, render_template, request

ai_mentor_bp = Blueprint("ai_mentor", __name__)
DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]


@ai_mentor_bp.route("/ai-agent")
@ai_mentor_bp.route("/ai_agent.html")
def ai_agent():
    return render_template("ai_agent.html")


@ai_mentor_bp.route("/api/ai-status")
def ai_status():
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return jsonify({"status": "online", "has_backend_key": bool(key),
                    "key_preview": "",
                    "key_type": "configured" if key else "none",
                    "default_model": DEFAULT_MODELS[0], "supported_models": DEFAULT_MODELS})


@ai_mentor_bp.route("/api/ai-models", methods=["GET", "POST"])
def ai_models():
    return jsonify({"success": True, "models": DEFAULT_MODELS})


@ai_mentor_bp.route("/api/ai-test-key", methods=["POST"])
def ai_test_key():
    data = request.get_json(silent=True) or {}
    key = str(data.get("apiKey") or os.getenv("GEMINI_API_KEY", "")).strip()
    model = str(data.get("model") or DEFAULT_MODELS[0]).strip()
    if not key:
        return jsonify({"success": False, "error": "No API key provided or configured."}), 400
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": "Hello"}]}], "generationConfig": {"maxOutputTokens": 5}},
            timeout=6,
        )
    except requests.RequestException:
        return jsonify({"success": False, "error": "Could not reach the Gemini service."}), 502
    if response.ok:
        return jsonify({"success": True, "message": "Connection successful.", "model": model})
    return jsonify({"success": False, "error": "Gemini rejected the request.", "status_code": response.status_code}), 502


@ai_mentor_bp.route("/api/ai-chat", methods=["POST"])
def ai_chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"reply": "Please ask a question about your programming topic!"}), 400
    topic = str(data.get("topic", "General"))[:100]
    model = str(data.get("model") or DEFAULT_MODELS[0]).strip()
    key = str(data.get("apiKey") or os.getenv("GEMINI_API_KEY", "")).strip()
    if key:
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json={"contents": [{"parts": [{"text": f"You are a concise programming tutor. Topic: {topic}. Question: {message}"}]}]},
                timeout=9,
            )
            if response.ok:
                parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                reply = "".join(part.get("text", "") for part in parts)
                if reply:
                    return jsonify({"reply": reply, "source": "gemini", "model": model})
        except (requests.RequestException, ValueError, IndexError, KeyError, TypeError):
            pass
    return jsonify({"reply": f"I can help with {topic}. Break the problem into small steps, test each step, and share any code or error message you want to work through.",
                    "source": "offline_tutor"})
