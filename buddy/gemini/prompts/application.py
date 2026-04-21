SYSTEM = """You are Buddy, a study assistant. Generate a single applied challenge for the learner based on their weak areas.
The challenge should require synthesising knowledge, not just recalling facts. It should be answerable in 2–4 sentences."""

FEEDBACK_SYSTEM = """You are Buddy, a study assistant evaluating a learner's written response to an application challenge.
Give specific, constructive feedback (3–5 sentences): acknowledge what was correct, point out gaps, and suggest how to improve.
Be encouraging but rigorous."""


def build(weak_areas: list[str], missing_areas: list[str]) -> tuple[str, str]:
    areas = weak_areas + missing_areas
    focus = ", ".join(areas) if areas else "the studied topics"
    user = f"""Weak/missing areas: {focus}

Write one practical application challenge. It should describe a realistic scenario the learner must analyse or solve.
Return JSON: {{"challenge_text": "..."}}"""
    return SYSTEM, user


def build_feedback(challenge: str, response: str, weak_areas: list[str], missing_areas: list[str]) -> tuple[str, str]:
    areas = weak_areas + missing_areas
    focus = ", ".join(areas) if areas else "the studied topics"
    user = f"""Challenge: {challenge}

Weak/missing areas being tested: {focus}

Student response: {response}

Evaluate: does the response correctly address the challenge? Give specific feedback.
Return JSON: {{"feedback": "..."}}"""
    return FEEDBACK_SYSTEM, user
