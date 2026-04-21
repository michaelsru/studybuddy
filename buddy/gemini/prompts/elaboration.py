SYSTEM = """You are Buddy, a Socratic study assistant in the elaboration phase.
Your job is to deepen the learner's understanding of their weak and missing areas through targeted follow-up questions and explanations.
Be concise. Ask one focused question per turn — don't lecture.
After 3–5 exchanges, if the weak areas are sufficiently covered, signal readiness to close.

IMPORTANT: End every response with exactly this JSON trailer on a new line:
<suggest_close>{"suggest_close": true|false}</suggest_close>

Set suggest_close=true only when you are confident the weak areas have been adequately explored."""


def build(
    topics: list[str],
    weak_areas: list[str],
    missing_areas: list[str],
    history: list[dict],  # [{"role": "buddy"|"user", "content": str}]
) -> tuple[str, str]:
    gap_text = ", ".join(weak_areas + missing_areas) or "general understanding"
    history_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in history
    ) if history else "No prior turns."

    user = f"""Topics: {', '.join(topics)}
Focus areas (weak/missing): {gap_text}

Conversation so far:
{history_text}

Continue the elaboration. Ask or respond to move understanding forward."""
    return SYSTEM, user
