SYSTEM = """You are Buddy, a study assistant. Generate priming questions to prime a learner before they watch an educational video.
Questions should activate prior knowledge and direct attention to the most important concepts.
If Anki gap topics are provided, weight questions toward those gaps."""


def build(topics: list[str], gaps: list[str]) -> tuple[str, str]:
    gap_note = f"\nKnowledge gaps (no cards in Anki): {', '.join(gaps)}" if gaps else ""
    user = f"""Topics: {', '.join(topics)}{gap_note}

Generate 3–5 priming questions to focus attention while watching. Questions should be open-ended and thought-provoking.
Return JSON: {{"questions": ["...", ...]}}"""
    return SYSTEM, user
