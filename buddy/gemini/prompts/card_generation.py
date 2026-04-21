SYSTEM = """You are Buddy, a study assistant. Generate Anki-quality flashcards from a study session.
Cards should be atomic, clear, and testable. Prefer cloze cards for definitions and mechanisms.
Use reversed cards only for concept pairs that are meaningfully bidirectional.
Avoid duplicating cards that already exist in the learner's deck (marked duplicate_warning=true)."""

MAX_ELAB_TURNS = 10  # configurable truncation guard


def build(
    topics: list[str],
    strong_areas: list[str],
    weak_areas: list[str],
    missing_areas: list[str],
    elaboration_turns: list[dict],  # [{"role": "buddy"|"user", "content": str}]
) -> tuple[str, str]:
    gap_summary = []
    if weak_areas:
        gap_summary.append(f"Weak: {', '.join(weak_areas)}")
    if missing_areas:
        gap_summary.append(f"Missing: {', '.join(missing_areas)}")
    if strong_areas:
        gap_summary.append(f"Strong: {', '.join(strong_areas)}")

    # Truncate to last N turns to avoid context bloat
    turns = elaboration_turns[-MAX_ELAB_TURNS:]
    elab_text = "\n".join(f"{t['role'].upper()}: {t['content']}" for t in turns) if turns else "None"

    user = f"""Topics: {', '.join(topics)}
Gap analysis: {'; '.join(gap_summary) or 'None'}

Elaboration conversation (last {MAX_ELAB_TURNS} turns):
{elab_text}

Generate 4–8 Anki flashcards. Focus on weak and missing areas. For each card specify:
- front, back (strings)
- card_type: "basic" | "cloze" | "reversed"
- tags: list of short strings
- is_gap_card: true if targeting a weak/missing area

Return JSON:
{{
  "cards": [
    {{"front": "...", "back": "...", "card_type": "basic", "tags": ["topic"], "is_gap_card": false}},
    ...
  ]
}}"""
    return SYSTEM, user
