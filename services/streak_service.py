"""
Nexus Learn Loop — Real Calendar Streak Service
Calculates consecutive calendar-day activity streaks based on recorded UTC dates.
"""

from datetime import date, datetime, timedelta, timezone


def calculate_streak(activity_dates):
    """
    Given an iterable of date objects (or ISO date strings),
    calculate the active consecutive-day streak.
    
    Rules:
    - If user was active today: streak includes today and counts backward consecutive days.
    - If user was active yesterday (but not yet today): streak is active and preserved for today.
    - If user was neither active today nor yesterday: streak is broken (0).
    """
    if not activity_dates:
        return 0

    parsed_dates = set()
    for d in activity_dates:
        if isinstance(d, str):
            try:
                parsed_dates.add(date.fromisoformat(d[:10]))
            except ValueError:
                continue
        elif isinstance(d, (date, datetime)):
            parsed_dates.add(d if isinstance(d, date) else d.date())

    if not parsed_dates:
        return 0

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    # Determine starting anchor point
    if today in parsed_dates:
        current_check = today
    elif yesterday in parsed_dates:
        current_check = yesterday
    else:
        return 0

    streak = 0
    while current_check in parsed_dates:
        streak += 1
        current_check -= timedelta(days=1)

    return streak
