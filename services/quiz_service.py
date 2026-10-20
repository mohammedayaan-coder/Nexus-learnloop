"""Server-authoritative quiz grading and study session reward calculations."""

QUIZZES = {
    "jinja2-interpolation": {
        "id": "jinja2-interpolation",
        "title": "Python Jinja2 Expression Interpolation",
        "topic": "Flask 3.0 & Templates",
        "difficulty": "Medium",
        "questions": [{
            "id": "q1",
            "prompt": "Which Jinja2 syntax correctly evaluates and outputs the variable user_xp to the HTML response?",
            "code_snippet": '// app/templates/dashboard.html\n<div class="badge">\n  <!-- Target expression goes here -->\n  XP: [ ??? ]\n</div>',
            "options": {"A": "{% user_xp %}", "B": "{{ user_xp }}", "C": "<%= user_xp %>", "D": "${user_xp}"},
            "correct_option": "B",
            "explanation": "In Jinja2, {{ expression }} prints variable values with auto-escaping, while {% statement %} runs control-flow tags.",
        }],
        "pass_xp": 20,
        "attempt_xp": 5,
    },
    "python-list-comprehensions": {
        "id": "python-list-comprehensions",
        "title": "Python List Comprehensions & Filtering",
        "topic": "Python Core",
        "difficulty": "Easy",
        "questions": [{
            "id": "q1",
            "prompt": "Which expression filters scores >= 50 using an idiomatic Python list comprehension?",
            "code_snippet": "scores = [45, 88, 92, 30]\n# Target: [88, 92]",
            "options": {"A": "[for s in scores if s >= 50: s]", "B": "[s for s in scores if s >= 50]", "C": "scores.filter(lambda s: s >= 50)", "D": "[s if s >= 50 for s in scores]"},
            "correct_option": "B",
            "explanation": "The standard Python comprehension syntax is [expression for item in iterable if condition].",
        }],
        "pass_xp": 20,
        "attempt_xp": 5,
    },
}


def get_quiz(quiz_id="jinja2-interpolation"):
    return QUIZZES.get(quiz_id, QUIZZES["jinja2-interpolation"])


def evaluate_quiz_submission(quiz_id, user_answers):
    quiz = get_quiz(quiz_id)
    questions = quiz["questions"]
    if isinstance(user_answers, str):
        answers = {questions[0]["id"]: user_answers.strip().upper()}
    elif isinstance(user_answers, dict):
        answers = {key: str(value).strip().upper() for key, value in user_answers.items()}
    else:
        answers = {}

    details = []
    score = 0
    for question in questions:
        selected = answers.get(question["id"], "")
        correct = question["correct_option"].upper()
        is_correct = bool(selected and selected == correct)
        score += int(is_correct)
        details.append({"question_id": question["id"], "selected": selected,
                        "correct_option": correct, "is_correct": is_correct,
                        "explanation": question["explanation"]})

    total = len(questions)
    return {
        "quiz_id": quiz["id"], "quiz_name": quiz["title"], "score": score,
        "total_questions": total, "accuracy": round(score * 100 / total) if total else 0,
        "xp_earned": quiz["pass_xp"] if score else quiz["attempt_xp"],
        "passed": score > 0, "details": details,
    }


def validate_and_calculate_timer_reward(duration_minutes):
    try:
        minutes = int(duration_minutes)
    except (TypeError, ValueError):
        raise ValueError("Duration must be a valid integer number of minutes.")
    if minutes < 1 or minutes > 180:
        raise ValueError(f"Invalid study session duration ({minutes}m). Must be between 1 and 180 minutes.")
    xp = min(60, 30 + ((minutes - 25) // 10) * 10) if minutes >= 25 else max(5, int(minutes * 1.2))
    return minutes, xp
