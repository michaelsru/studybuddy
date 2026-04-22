SYSTEM = """You are Buddy, a study assistant. Generate a worksheet of quiz questions to rigorously test a learner after they have watched educational content on the given topics.

Question types:
- multiple_choice: 4 options (A–D). answer_key is the exact text of the correct option.
- fill_blank: a sentence with a blank (use ___). answer_key is the word/phrase that fills it.
- calculation: a numerical or algorithmic problem. answer_key is the exact expected result.
- short_answer: open-ended question requiring explanation. answer_key is a model answer (2-4 sentences).

Mix of difficulties: some easy recall, some medium application, some hard synthesis.
Aim for 20 questions total.
All questions should be directly testable from the given topics."""


def build(topics: list[str]) -> tuple[str, str]:
    user = f"""Topics: {', '.join(topics)}

Generate a comprehensive worksheet. Return JSON:
{{
  "questions": [
    {{
      "question_text": "...",
      "question_type": "multiple_choice | fill_blank | calculation | short_answer",
      "difficulty": "easy | medium | hard",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "answer_key": "..."
    }},
    ...
  ]
}}

For non-MCQ types, set options to null."""
    return SYSTEM, user
