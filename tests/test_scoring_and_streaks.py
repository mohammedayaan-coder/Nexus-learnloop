"""
Automated tests for Nexus Learn Loop — Server-Authoritative Scoring & Real Streaks
Runs natively via Python's built-in unittest module.
"""

import unittest
from datetime import date, timedelta
from services.quiz_service import evaluate_quiz_submission, validate_and_calculate_timer_reward
from services.streak_service import calculate_streak


class ScoringAndStreaksTestCase(unittest.TestCase):
    def test_streak_calculation_continuous(self):
        """Consecutive dates ending today should calculate exact streak."""
        today = date.today()
        dates = [today - timedelta(days=i) for i in range(5)]
        self.assertEqual(calculate_streak(dates), 5)

    def test_streak_calculation_active_yesterday(self):
        """Active yesterday preserves streak for today until day ends."""
        yesterday = date.today() - timedelta(days=1)
        dates = [yesterday - timedelta(days=i) for i in range(4)]
        self.assertEqual(calculate_streak(dates), 4)

    def test_streak_calculation_broken(self):
        """Activity from 3 days ago with no activity yesterday or today yields 0 streak."""
        old_date = date.today() - timedelta(days=3)
        self.assertEqual(calculate_streak([old_date]), 0)

    def test_quiz_authoritative_scoring_correct(self):
        """Option B is correct for jinja2-interpolation, earning 20 XP and score 1."""
        res = evaluate_quiz_submission("jinja2-interpolation", "B")
        self.assertEqual(res["score"], 1)
        self.assertEqual(res["total_questions"], 1)
        self.assertEqual(res["accuracy"], 100)
        self.assertEqual(res["xp_earned"], 20)
        self.assertTrue(res["passed"])

    def test_quiz_authoritative_scoring_incorrect(self):
        """Option A is wrong, earning attempt XP (5) and score 0."""
        res = evaluate_quiz_submission("jinja2-interpolation", "A")
        self.assertEqual(res["score"], 0)
        self.assertEqual(res["total_questions"], 1)
        self.assertEqual(res["accuracy"], 0)
        self.assertEqual(res["xp_earned"], 5)
        self.assertFalse(res["passed"])

    def test_timer_validation_valid(self):
        """25-minute Pomodoro is valid and awards 30 XP."""
        mins, xp = validate_and_calculate_timer_reward(25)
        self.assertEqual(mins, 25)
        self.assertEqual(xp, 30)

    def test_timer_validation_invalid_low(self):
        """0 minutes is rejected with ValueError."""
        with self.assertRaises(ValueError):
            validate_and_calculate_timer_reward(0)

    def test_timer_validation_invalid_high(self):
        """250 minutes exceeds maximum 180 min and is rejected."""
        with self.assertRaises(ValueError):
            validate_and_calculate_timer_reward(250)

    def test_timer_validation_non_integer(self):
        """String letters are rejected."""
        with self.assertRaises(ValueError):
            validate_and_calculate_timer_reward("not_a_number")


if __name__ == "__main__":
    unittest.main()
