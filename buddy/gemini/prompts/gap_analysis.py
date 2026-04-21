SYSTEM = """You are Buddy, a study assistant marking a student's quiz worksheet.
For each question, compare the student's answer to the answer key.
Score semantically — credit correct reasoning even if phrasing differs from the key.
- "strong": fully correct or captures all key ideas
- "partial": partly correct — has the right direction but misses important details
- "missing": incorrect, blank, or shows fundamental misunderstanding

For multiple_choice and fill_blank, be stricter: mark "missing" if the student clearly chose wrong.
Always include the correct answer in your feedback so the student can learn from it."""

GAP_SYSTEM = """You are Buddy, a study assistant identifying knowledge gaps from scored quiz answers.
Categorise topics into strong, weak, and missing based on the learner's answers.
Be specific — name the concepts, not just "topic 1"."""


def build(qa_pairs: list[dict]) -> tuple[str, str]:
    """qa_pairs: [{question_id, question_text, question_type, answer_text, answer_key}]"""
    lines = []
    for p in qa_pairs:
        opts = ""
        if p.get("options"):
            opts = f"\nOptions: {', '.join(p['options'])}"
        lines.append(
            f"Q (id={p['question_id']}, type={p['question_type']}):{opts}\n"
            f"  Question: {p['question_text']}\n"
            f"  Answer key: {p['answer_key']}\n"
            f"  Student answer: {p['answer_text']}"
        )

    user = f"""Mark these quiz answers:

{chr(10).join(chr(10) + l for l in lines)}

Return JSON:
{{
  "answers": [
    {{
      "question_id": "...",
      "score": "strong|partial|missing",
      "feedback": "1-2 sentences. Include the correct answer.",
      "answer_key": "..."
    }},
    ...
  ]
}}"""
    return SYSTEM, user


def build_gap_analysis(qa_pairs: list[dict], scored: list[dict]) -> tuple[str, str]:
    """Build gap analysis prompt from Q+A pairs and their scores."""
    lines = []
    for s in scored:
        q = next((p["question_text"] for p in qa_pairs if p["question_id"] == s["question_id"]), "")
        lines.append(f"Q: {q}\nA: {s['answer_text']}\nScore: {s['score']} — {s.get('feedback', '')}")

    user = f"""Scored quiz answers:

{"".join(chr(10)*2 + l for l in lines)}

Based on these scores, identify the learner's strong, weak, and missing areas.
Use specific concept names, not generic descriptions.
Return JSON:
{{
  "strong_areas": ["..."],
  "weak_areas": ["..."],
  "missing_areas": ["..."]
}}"""
    return GAP_SYSTEM, user

