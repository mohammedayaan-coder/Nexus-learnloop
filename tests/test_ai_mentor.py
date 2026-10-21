"""Mocked integration tests for the AI mentor's Gemini request flow."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import database.database as db
from app import create_app


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=None, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.json_error = json_error
        self.headers = headers or {}

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class AIMentorTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "ai-test.db"
        self.original_database_path = db.DEFAULT_DATABASE_PATH
        db.DEFAULT_DATABASE_PATH = self.database_path
        db.init_db(self.database_path)
        self.environment_patcher = mock.patch.dict(
            os.environ, {"FLASK_ENV": "testing", "GEMINI_API_KEY": "server-test-key"},
        )
        self.environment_patcher.start()
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.environment_patcher.stop()
        db.DEFAULT_DATABASE_PATH = self.original_database_path
        self.temp_dir.cleanup()

    def test_chat_success_uses_server_key_selected_topic_history_and_greeting_guidance(self):
        response_body = {"candidates": [{"content": {"parts": [{
            "text": "Hi! Welcome back. What would you like to explore in databases today?"
        }]}}]}
        with mock.patch("blueprints.ai_mentor.requests.post", return_value=FakeResponse(response_body)) as post:
            response = self.client.post("/api/ai-chat", json={
                "message": "hiiii", "topic": "Database", "model": "gemini-3.8-flash",
                "apiKey": "client-submitted-key",
                "history": [{"role": "user", "text": "I am learning SQL."},
                            {"role": "model", "text": "We were discussing indexes."}],
            })

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "gemini")
        self.assertIn("Hi!", result["reply"])
        self.assertEqual(result["model"], "gemini-3.8-flash")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "server-test-key")
        self.assertEqual(kwargs["timeout"], (3.05, 12.0))
        payload = kwargs["json"]
        self.assertIn("warm, concise learning tutor", payload["systemInstruction"]["parts"][0]["text"])
        self.assertIn("only greets you", payload["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][1]["role"], "model")
        self.assertIn("Selected topic: Database", payload["contents"][2]["parts"][0]["text"])
        self.assertIn("hiiii", payload["contents"][2]["parts"][0]["text"])

    def test_503_recovers_on_bounded_retry(self):
        response_body = {"candidates": [{"content": {"parts": [{"text": "Recovered answer"}]}}]}
        responses = [
            FakeResponse({"error": {"status": "UNAVAILABLE", "message": "High demand"}}, 503),
            FakeResponse(response_body),
        ]
        with mock.patch("blueprints.ai_mentor.requests.post", side_effect=responses) as post, \
                mock.patch("blueprints.ai_mentor.time.sleep") as sleep:
            response = self.client.post("/api/ai-chat", json={"message": "help"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "Recovered answer")
        self.assertEqual(response.get_json()["source"], "gemini")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()

    def test_repeated_503_exhausts_retries_with_clear_unavailable_error(self):
        upstream = FakeResponse({"error": {
            "status": "UNAVAILABLE", "message": "Temporary demand overload",
        }}, 503)
        with mock.patch("blueprints.ai_mentor.requests.post", return_value=upstream) as post, \
                mock.patch("blueprints.ai_mentor.time.sleep"):
            response = self.client.post("/api/ai-chat", json={"message": "help"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(response.get_json()["source"], "gemini_error")
        self.assertIn("temporarily unavailable", response.get_json()["error"])
        self.assertNotIn("reply", response.get_json())

    def test_upstream_logs_include_status_but_redact_secret_material(self):
        upstream = FakeResponse({"error": {
            "status": "UNAVAILABLE", "message": "Temporary failure; API key=AIza012345678901234567890123456789",
        }}, 503)
        with self.assertLogs("blueprints.ai_mentor", level="WARNING") as captured, \
                mock.patch("blueprints.ai_mentor.requests.post", return_value=upstream), \
                mock.patch("blueprints.ai_mentor.time.sleep"):
            self.client.post("/api/ai-chat", json={"message": "help"})
        logs = " ".join(captured.output)
        self.assertIn("HTTP 503", logs)
        self.assertIn("UNAVAILABLE", logs)
        self.assertNotIn("AIza012345678901234567890123456789", logs)

    def test_429_retries_and_respects_retry_after(self):
        success = FakeResponse({"candidates": [{"content": {"parts": [{"text": "After limit"}]}}]})
        limited = FakeResponse({"error": {"status": "RESOURCE_EXHAUSTED", "message": "Rate limited"}},
                               429, headers={"Retry-After": "1"})
        with mock.patch("blueprints.ai_mentor.requests.post", side_effect=[limited, success]), \
                mock.patch("blueprints.ai_mentor.time.sleep") as sleep:
            response = self.client.post("/api/ai-chat", json={"message": "help"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "After limit")
        self.assertEqual(sleep.call_args.args[0], 1.0)

    def test_gemini_timeout_returns_clear_non_success(self):
        with mock.patch("blueprints.ai_mentor.requests.post", side_effect=requests.Timeout) as post, \
                mock.patch("blueprints.ai_mentor.time.sleep"):
            response = self.client.post("/api/ai-chat", json={"message": "help", "topic": "Python"})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(post.call_count, 3)
        result = response.get_json()
        self.assertFalse(result["success"])
        self.assertEqual(result["source"], "gemini_error")
        self.assertIn("too long", result["error"])
        self.assertNotIn("reply", result)

    def test_invalid_or_empty_gemini_response_is_not_reported_as_success(self):
        responses = [
            FakeResponse({"candidates": []}),
            FakeResponse(json_error=ValueError("invalid json")),
        ]
        for fake_response in responses:
            with self.subTest(fake_response=fake_response), \
                    mock.patch("blueprints.ai_mentor.requests.post", return_value=fake_response):
                response = self.client.post("/api/ai-chat", json={"message": "help"})
                self.assertEqual(response.status_code, 502)
                self.assertFalse(response.get_json()["success"])
                self.assertNotIn("reply", response.get_json())

    def test_non_retryable_http_errors_are_distinguished_and_safe(self):
        cases = [
            (400, "request format or parameters"),
            (401, "authentication failed"),
            (403, "denied access"),
        ]
        for status_code, expected_message in cases:
            with self.subTest(status=status_code), \
                    mock.patch("blueprints.ai_mentor.requests.post", return_value=FakeResponse(
                        {"error": {"status": "UPSTREAM_ERROR", "message": "sensitive provider detail"}},
                        status_code=status_code,
                    )) as post:
                response = self.client.post("/api/ai-chat", json={"message": "help"})
            self.assertEqual(response.status_code, 502)
            self.assertFalse(response.get_json()["success"])
            self.assertIn(expected_message, response.get_json()["error"])
            self.assertNotIn(b"sensitive provider detail", response.data)
            self.assertNotIn("reply", response.get_json())
            post.assert_called_once()

    def test_unsupported_model_is_rejected_before_request(self):
        with mock.patch("blueprints.ai_mentor.requests.post") as post:
            response = self.client.post("/api/ai-chat", json={
                "message": "help", "model": "gemini-2.0-flash",
            })
        self.assertEqual(response.status_code, 400)
        post.assert_not_called()

    def test_missing_server_key_returns_unavailable_without_calling_provider(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}), \
                mock.patch("blueprints.ai_mentor.requests.post") as post:
            response = self.client.post("/api/ai-chat", json={"message": "help"})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["success"])
        self.assertNotIn("reply", response.get_json())
        post.assert_not_called()

    def test_status_reports_configuration_without_claiming_live_service(self):
        response = self.client.get("/api/ai-status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "configured")
        self.assertTrue(data["has_backend_key"])
        self.assertNotIn("online", data["status"])
        self.assertNotIn("key", str(data).lower().replace("has_backend_key", ""))


if __name__ == "__main__":
    unittest.main()
