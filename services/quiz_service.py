"""
Nexus Learn Loop — Server-Authoritative Quiz & Timer Reward Service
Validates questions, checks answers against the server answer key,
and calculates real scores, accuracy, and XP rewards.
"""

QUIZZES = {
    "jinja2-interpolation": {
        "id": "jinja2-interpolation",
        "title": "Python Jinja2 Expression Interpolation",
        "topic": "Flask 3.0 & Templates",
        "difficulty": "Medium",
        "questions": [
            {
                "id": "q1",
                "prompt": "Which Jinja2 syntax correctly evaluates and outputs the variable user_xp to the HTML response?",
                "code_snippet": '// app/templates/dashboard.html\n<div class="badge">\n  <!-- Target expression goes here -->\n  XP: [ ??? ]\n</div>',
                "options": {
                    "A": "{% user_xp %}",
                    "B": "{{ user_xp }}",
                    "C": "<%= user_xp %>",
                    "D": "${user_xp}",
                },
                "correct_option": "B",
                "explanation": "In Jinja2, {{ expression }} prints variable values with auto-escaping, while {% statement %} runs control-flow tags.",
            }
        ],
        "pass_xp": 20,
        "attempt_xp": 5,
    },
    "python-list-comprehensions": {
        "id": "python-list-comprehensions",
        "title": "Python List Comprehensions & Filtering",
        "topic": "Python Core",
        "difficulty": "Easy",
        "questions": [
            {
                "id": "q1",
                "prompt": "Which expression filters scores >= 50 using an idiomatic Python list comprehension?",
                "code_snippet": "scores = [45, 88, 92, 30]\n# Target: [88, 92]",
                "options": {
                    "A": "[for s in scores if s >= 50: s]",
                    "B": "[s for s in scores if s >= 50]",
                    "C": "scores.filter(lambda s: s >= 50)",
                    "D": "[s if s >= 50 for s in scores]",
                },
                "correct_option": "B",
                "explanation": "The standard Python comprehension syntax is [expression for item in iterable if condition].",
            }
        ],
        "pass_xp": 20,
        "attempt_xp": 5,
    },
}


def get_quiz(quiz_id="jinja2-interpolation"):
    """Fetch quiz definition by ID or return default."""
    return QUIZZES.get(quiz_id, QUIZZES["jinja2-interpolation"])


def evaluate_quiz_submission(quiz_id, user_answers):
    """
    Evaluate submitted answers against the authoritative answer key on the server.
    
    :param quiz_id: str key from QUIZZES
    :param user_answers: dict of {question_id: selected_option} OR a single option string
    :return: dict with validated score, total_questions, xp_earned, accuracy, details
    """
    quiz = get_quiz(quiz_id)
    questions = quiz["questions"]
    total_questions = len(questions)

    # Normalize answers input
    if isinstance(user_answers, str):
        # Single question shorthand (e.g. "B")
        first_qid = questions[0]["id"]
        answers_dict = {first_qid: user_answers.strip().upper()}
    elif isinstance(user_answers, dict):
        answers_dict = {k: str(v).strip().upper() for k, v in user_answers.items()}
    else:
        answers_dict = {}

    score = 0
    details = []

    for q in questions:
        qid = q["id"]
        selected = answers_dict.get(qid, "")
        correct = q["correct_option"].upper()
        is_correct = bool(selected and selected == correct)
        if is_correct:
            score += 1
        details.append({
            "question_id": qid,
            "selected": selected,
            "correct_option": correct,
            "is_correct": is_correct,
            "explanation": q["explanation"],
        })

    accuracy = round((score / total_questions) * 100) if total_questions > 0 else 0
    # Server calculates XP — client can never spoof or dictate this
    xp_earned = quiz["pass_xp"] if score > 0 else quiz["attempt_xp"]

    return {
        "quiz_id": quiz["id"],
        "quiz_name": quiz["title"],
        "score": score,
        "total_questions": total_questions,
        "accuracy": accuracy,
        "xp_earned": xp_earned,
        "passed": score > 0,
        "details": details,
    }


def validate_and_calculate_timer_reward(duration_minutes):
    """
    Validate that duration is within allowed physiological focus ranges
    and calculate legitimate server-side XP reward.
    
    Allowed range: 1 to 180 minutes.
    """
    try:
        minutes = int(duration_minutes)
    except (ValueError, TypeError):
        raise ValueError("Duration must be a valid integer number of minutes.")

    if minutes < 1 or minutes > 180:
        raise ValueError(f"Invalid study session duration ({minutes}m). Must be between 1 and 180 minutes.")

    # Server calculates XP:
    # 25-minute Pomodoro sprint earns 30 XP
    # Scaled proportionally: ~1.2 XP per min, min 5 XP, max 60 XP per single session
    if minutes >= 25:
        xp = min(60, 30 + ((minutes - 25) // 10) * 10)
    else:
        xp = max(5, int(minutes * 1.2))

    return minutes, xp
