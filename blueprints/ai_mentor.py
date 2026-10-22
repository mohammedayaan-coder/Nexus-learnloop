"""AI mentor page and Gemini-backed chat endpoints."""

import logging
import os
import re
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from flask import Blueprint, current_app, jsonify, render_template, request

from services.security import login_required, require_csrf

ai_mentor_bp = Blueprint("ai_mentor", __name__)
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-lite-latest"
SUPPORTED_MODELS = (DEFAULT_MODEL,)
ALLOWED_TOPICS = {"Python", "Frontend", "Database", "DevOps", "General"}
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_TURNS = 12
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")
MAX_GEMINI_ATTEMPTS = 2
GEMINI_DEADLINE_SECONDS = 20.0
GEMINI_CONNECT_TIMEOUT_SECONDS = 3.05
GEMINI_READ_TIMEOUT_SECONDS = 15.0
GEMINI_BLOCKED_REASONS = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}


def _get_gemini_api_key():
    """Read GEMINI_API_KEY from Flask configuration or server environment."""
    if current_app:
        key = current_app.config.get("GEMINI_API_KEY")
        if key:
            return str(key).strip()
    return os.getenv("GEMINI_API_KEY", "").strip()


def _request_model(model):
    requested = str(model or DEFAULT_MODEL).strip()
    if not MODEL_PATTERN.fullmatch(requested) or requested not in SUPPORTED_MODELS:
        raise ValueError("Choose a supported Gemini model.")
    return requested


def _clean_history(history):
    if not isinstance(history, list):
        return []
    turns = []
    for item in history[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "model"}:
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            turns.append({"role": item["role"], "parts": [{"text": text.strip()[:MAX_MESSAGE_LENGTH]}]})
    return turns


def _gemini_reply(response):
    """Parse only a text candidate; malformed, empty, or blocked responses fail closed."""
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return None
    if candidates[0].get("finishReason") in GEMINI_BLOCKED_REASONS:
        return None
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    text = "".join(
        part.get("text", "") for part in parts
        if isinstance(part, dict) and part.get("thought") is not True
        and isinstance(part.get("text"), str)
    ).strip()
    return text or None


def _gemini_response_blocked(response):
    """Recognize provider safety blocks without exposing provider response text."""
    try:
        payload = response.json()
    except (ValueError, TypeError, AttributeError):
        return False
    if not isinstance(payload, dict):
        return False
    feedback = payload.get("promptFeedback")
    if isinstance(feedback, dict) and isinstance(feedback.get("blockReason"), str):
        return True
    candidates = payload.get("candidates")
    return (
        isinstance(candidates, list)
        and any(isinstance(candidate, dict) and candidate.get("finishReason") in GEMINI_BLOCKED_REASONS
                for candidate in candidates)
    )


def _service_error(message, status=502):
    return jsonify({"success": False, "error": message, "source": "gemini_error"}), status


def _provider_error(response):
    """Return a small, redacted view of Google's structured error response."""
    try:
        body = response.json()
    except (ValueError, TypeError, AttributeError):
        body = {}
    error = body.get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        error = {}
    provider_status = str(error.get("status", "UNKNOWN"))[:64]
    message = str(error.get("message", ""))
    message = re.sub(r"(?i)(AIza[0-9A-Za-z_-]{20,}|AQ\.[0-9A-Za-z._-]+)", "[redacted]", message)
    message = re.sub(r"(?i)(bearer\s+)\S+", r"\1[redacted]", message)
    message = re.sub(
        r"(?i)(api[_ -]?key|authorization|token|secret)(\s*[:=]\s*)\S+",
        r"\1\2[redacted]", message,
    )
    message = " ".join(message.split())[:240]
    reasons = []
    for detail in error.get("details", []) if isinstance(error.get("details"), list) else []:
        if isinstance(detail, dict):
            reason = detail.get("reason")
            if isinstance(reason, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", reason):
                reasons.append(reason)
    return {
        "status": provider_status,
        "message": message or "[no provider message]",
        "reasons": reasons[:4],
        "body": body if isinstance(body, dict) else {},
    }


def _retry_after_seconds(response, provider_error):
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("Retry-After")
    if value:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    error = provider_error["body"].get("error", {})
    details = error.get("details", []) if isinstance(error, dict) else []
    for detail in details:
        detail_type = detail.get("@type", "") if isinstance(detail, dict) else ""
        if isinstance(detail_type, str) and detail_type.endswith("RetryInfo"):
            retry_delay = detail.get("retryDelay", "")
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)s", str(retry_delay))
            if match:
                return float(match.group(1))
    return None


def _is_retryable(response, provider_error):
    status = response.status_code
    # Do not replay slow/unavailable generations: this can turn a provider 503
    # into a route deadline timeout and make the learner wait through duplicates.
    if status in {500, 502}:
        return True
    if status == 429:
        reasons = {reason.lower() for reason in provider_error["reasons"]}
        # A depleted daily/project quota will not clear through a short retry.
        retry_after = provider_error.get("retry_after")
        return "quota_exceeded" not in reasons and (retry_after is None or retry_after <= 1.0)
    return False


def _generate_with_retry(model, key, payload):
    """Make at most one fast transient retry within a short total budget."""
    deadline = time.monotonic() + GEMINI_DEADLINE_SECONDS
    url = GEMINI_ENDPOINT.format(model=model)
    last_response = None
    last_error = None

    for attempt in range(MAX_GEMINI_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connect_timeout = min(GEMINI_CONNECT_TIMEOUT_SECONDS, max(0.1, remaining / 3))
        read_timeout = min(GEMINI_READ_TIMEOUT_SECONDS, max(0.1, remaining - connect_timeout))
        attempt_started = time.monotonic()
        try:
            response = requests.post(
                url,
                headers={"x-goog-api-key": key},
                json=payload,
                timeout=(connect_timeout, read_timeout),
            )
            if response.ok:
                logger.info(
                    "Gemini upstream category=success http_status=%s attempt=%s duration_ms=%s",
                    response.status_code, attempt + 1,
                    int((time.monotonic() - attempt_started) * 1000),
                )
                return response, None
            info = _provider_error(response)
            retry_after = _retry_after_seconds(response, info)
            info["retry_after"] = retry_after
            logger.warning(
                "Gemini upstream category=provider_error http_status=%s status=%s reasons=%s attempt=%s duration_ms=%s",
                response.status_code, info["status"], ",".join(info["reasons"]), attempt + 1,
                int((time.monotonic() - attempt_started) * 1000),
            )
            last_response, last_error = response, info
            if not _is_retryable(response, info):
                break
        except requests.Timeout as error:
            logger.warning(
                "Gemini upstream category=timeout type=%s attempt=%s duration_ms=%s",
                type(error).__name__, attempt + 1,
                int((time.monotonic() - attempt_started) * 1000),
            )
            last_response, last_error = None, {"status": "TIMEOUT", "message": "[request timed out]", "reasons": []}
            # A read timeout means generation is already slow; don't repeat it.
            break
        except requests.ConnectionError as error:
            logger.warning(
                "Gemini upstream category=connection_error type=%s attempt=%s duration_ms=%s",
                type(error).__name__, attempt + 1,
                int((time.monotonic() - attempt_started) * 1000),
            )
            last_response, last_error = None, {"status": "CONNECTION_ERROR", "message": "[connection failed]", "reasons": []}
            retry_after = None
        except requests.RequestException as error:
            logger.warning(
                "Gemini upstream category=request_error type=%s attempt=%s duration_ms=%s",
                type(error).__name__, attempt + 1,
                int((time.monotonic() - attempt_started) * 1000),
            )
            last_response, last_error = None, {"status": "REQUEST_ERROR", "message": "[request failed]", "reasons": []}
            break

        if attempt + 1 >= MAX_GEMINI_ATTEMPTS:
            break
        remaining = deadline - time.monotonic()
        backoff = random.uniform(0, min(4.0, 0.5 * (2 ** attempt)))
        delay = max(retry_after or 0.0, backoff)
        if remaining <= 0 or delay >= remaining:
            break
        time.sleep(delay)

    return last_response, last_error


def _upstream_failure(response, info):
    status = response.status_code if response is not None else None
    if status == 400:
        return _service_error("Gemini rejected the request format or parameters. Please try again later.", 502)
    if status == 401:
        return _service_error("Gemini authentication failed. The server API key needs attention.", 502)
    if status == 403:
        return _service_error("Gemini denied access. The server key or project permissions need attention.", 502)
    if status == 429:
        return _service_error("Gemini is rate-limiting this service. Please try again shortly.", 503)
    if status == 503 or status in {408, 500, 502, 504}:
        return _service_error("Gemini is temporarily unavailable. Please try again shortly.", 503)
    if info and info["status"] == "TIMEOUT":
        return _service_error("Gemini took too long to respond. Please try again shortly.", 504)
    if info and info["status"] in {"CONNECTION_ERROR", "REQUEST_ERROR"}:
        return _service_error("Could not reach Gemini. Please try again shortly.", 503)
    return _service_error("Gemini could not complete this request. Please try again shortly.", 502)


@ai_mentor_bp.route("/ai-agent")
@ai_mentor_bp.route("/ai_agent.html")
def ai_agent():
    return render_template("ai_agent.html")


@ai_mentor_bp.route("/api/ai-status")
def ai_status():
    configured = bool(_get_gemini_api_key())
    return jsonify({
        "status": "configured" if configured else "unconfigured",
        "has_backend_key": configured,
        "default_model": DEFAULT_MODEL,
        "supported_models": list(SUPPORTED_MODELS),
    })


@ai_mentor_bp.route("/api/ai-models", methods=["GET", "POST"])
def ai_models():
    return jsonify({"success": True, "models": list(SUPPORTED_MODELS)})


@ai_mentor_bp.route("/api/ai-test-key", methods=["POST"])
@login_required
@require_csrf
def ai_test_key():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid connection-test request."}), 400
    key = _get_gemini_api_key()
    try:
        model = _request_model(data.get("model"))
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    if not key:
        return jsonify({"success": False, "error": "AI Mentor is temporarily unavailable. Please try again later."}), 503
    try:
        response = requests.post(
            GEMINI_ENDPOINT.format(model=model),
            headers={"x-goog-api-key": key},
            json={"contents": [{"parts": [{"text": "Reply with OK."}]}],
                  "generationConfig": {"maxOutputTokens": 5}},
            timeout=(3.05, 15),
        )
    except requests.RequestException as error:
        logger.warning("Gemini connection test failed (%s)", type(error).__name__)
        return _service_error("Could not reach Gemini. Please try again shortly.")
    if not response.ok:
        logger.warning("Gemini connection test returned HTTP %s", response.status_code)
        return _service_error("Gemini rejected the connection test.")
    try:
        if _gemini_reply(response):
            return jsonify({"success": True, "message": "Gemini connection verified.", "model": model})
    except (ValueError, TypeError, AttributeError):
        pass
    return _service_error("Gemini returned an unreadable connection-test response.")


@ai_mentor_bp.route("/api/ai-chat", methods=["POST"])
@login_required
@require_csrf
def ai_chat():
    if request.is_json and request.get_json(silent=True) is None and request.data.strip():
        return jsonify({"success": False, "error": "Invalid JSON in chat request."}), 400
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Invalid chat request."}), 400
    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "Enter a message for the AI Mentor."}), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"success": False, "error": f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters."}), 400
    message = message.strip()
    try:
        model = _request_model(data.get("model"))
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400

    requested_topic = data.get("topic")
    topic = requested_topic if isinstance(requested_topic, str) and requested_topic in ALLOWED_TOPICS else "General"
    key = _get_gemini_api_key()
    if not key:
        return _service_error("AI Mentor is temporarily unavailable. Please try again later.", 503)

    contents = _clean_history(data.get("history"))
    contents.append({"role": "user", "parts": [{"text": f"Selected topic: {topic}\n{message}"}]})
    payload = {
        "systemInstruction": {"parts": [{"text": (
            "You are the Nexus Learn Loop AI Mentor, a warm, concise learning tutor. "
            "Keep the learner's selected topic central to your answer. If the learner only greets you, "
            "greet them naturally and ask one useful follow-up about what they want to learn. "
            "Use recent conversation turns when relevant. Do not claim you completed actions you cannot perform."
        )}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 800, "temperature": 0.4},
    }
    response, error_info = _generate_with_retry(model, key, payload)
    if response is None or not response.ok:
        return _upstream_failure(response, error_info)
    try:
        reply = _gemini_reply(response)
    except (ValueError, TypeError, AttributeError) as error:
        logger.warning("Gemini response parsing failed (%s)", type(error).__name__)
        reply = None
    if not reply:
        if _gemini_response_blocked(response):
            return _service_error("Gemini could not answer that prompt. Please rephrase it and try again.", 422)
        return _service_error("Gemini returned an empty or unreadable answer. Please try again.")
    return jsonify({"success": True, "reply": reply, "source": "gemini", "model": model})
