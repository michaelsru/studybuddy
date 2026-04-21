import json
import uuid
from datetime import datetime, timezone

import aiosqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Sessions ─────────────────────────────────────────────────────────────────

async def create_session(db: aiosqlite.Connection, preset: str, active_steps: list[int]) -> str:
    id = _uuid()
    now = _now()
    await db.execute(
        """INSERT INTO sessions
           (id, created_at, updated_at, preset, active_steps, current_step, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (id, now, now, preset, json.dumps(active_steps), 1, "in_progress"),
    )
    await db.commit()
    return id


async def get_session(db: aiosqlite.Connection, id: str) -> aiosqlite.Row | None:
    async with db.execute("SELECT * FROM sessions WHERE id = ?", (id,)) as cur:
        return await cur.fetchone()


async def list_sessions(
    db: aiosqlite.Connection, status: str | None = None, limit: int = 20
) -> list[aiosqlite.Row]:
    if status:
        async with db.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ) as cur:
            return await cur.fetchall()
    async with db.execute(
        "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
    ) as cur:
        return await cur.fetchall()


async def update_session_step(db: aiosqlite.Connection, id: str, step: int) -> None:
    await db.execute(
        "UPDATE sessions SET current_step = ?, updated_at = ? WHERE id = ?",
        (step, _now(), id),
    )
    await db.commit()


async def update_session_status(db: aiosqlite.Connection, id: str, status: str) -> None:
    await db.execute(
        "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), id),
    )
    await db.commit()


async def update_session_title(db: aiosqlite.Connection, id: str, title: str) -> None:
    await db.execute(
        "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
        (title, _now(), id),
    )
    await db.commit()


# ── Topics ────────────────────────────────────────────────────────────────────

async def insert_topics(db: aiosqlite.Connection, session_id: str, topics: list[str]) -> list[str]:
    """Returns list of topic IDs in order."""
    ids = []
    for i, topic in enumerate(topics):
        id = _uuid()
        await db.execute(
            "INSERT INTO session_topics (id, session_id, topic, position) VALUES (?, ?, ?, ?)",
            (id, session_id, topic, i),
        )
        ids.append(id)
    await db.commit()
    return ids


async def get_topics(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM session_topics WHERE session_id = ? ORDER BY position", (session_id,)
    ) as cur:
        return await cur.fetchall()


# ── Priming Questions ─────────────────────────────────────────────────────────

async def insert_priming_questions(
    db: aiosqlite.Connection, session_id: str, questions: list[str], topic_id: str | None = None
) -> None:
    for i, q in enumerate(questions):
        await db.execute(
            "INSERT INTO priming_questions (id, session_id, topic_id, question_text, position) VALUES (?, ?, ?, ?, ?)",
            (_uuid(), session_id, topic_id, q, i),
        )
    await db.commit()


async def get_priming_questions(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM priming_questions WHERE session_id = ? ORDER BY position", (session_id,)
    ) as cur:
        return await cur.fetchall()


# ── Quiz Questions ────────────────────────────────────────────────────────────

async def insert_quiz_questions(
    db: aiosqlite.Connection, session_id: str, questions: list[str], topic_id: str | None = None
) -> list[str]:
    ids = []
    for i, q in enumerate(questions):
        id = _uuid()
        await db.execute(
            "INSERT INTO quiz_questions (id, session_id, topic_id, question_text, position) VALUES (?, ?, ?, ?, ?)",
            (id, session_id, topic_id, q, i),
        )
        ids.append(id)
    await db.commit()
    return ids


async def get_quiz_questions(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM quiz_questions WHERE session_id = ? ORDER BY position", (session_id,)
    ) as cur:
        return await cur.fetchall()


# ── Quiz Answers ──────────────────────────────────────────────────────────────

async def insert_quiz_answers(
    db: aiosqlite.Connection, session_id: str, answers: list[dict]
) -> None:
    """Each dict: {question_id, answer_text, score, feedback}"""
    for a in answers:
        await db.execute(
            "INSERT INTO quiz_answers (id, session_id, question_id, answer_text, score, feedback) VALUES (?, ?, ?, ?, ?, ?)",
            (_uuid(), session_id, a["question_id"], a["answer_text"], a["score"], a["feedback"]),
        )
    await db.commit()


async def get_quiz_answers(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM quiz_answers WHERE session_id = ?", (session_id,)
    ) as cur:
        return await cur.fetchall()


# ── Gap Analysis ──────────────────────────────────────────────────────────────

async def upsert_gap_analysis(db: aiosqlite.Connection, session_id: str, data: dict) -> None:
    """data keys: strong_areas, weak_areas, missing_areas — all list[str]"""
    existing = await get_gap_analysis(db, session_id)
    if existing:
        await db.execute(
            "UPDATE gap_analysis SET strong_areas=?, weak_areas=?, missing_areas=? WHERE session_id=?",
            (
                json.dumps(data["strong_areas"]),
                json.dumps(data["weak_areas"]),
                json.dumps(data["missing_areas"]),
                session_id,
            ),
        )
    else:
        await db.execute(
            "INSERT INTO gap_analysis (id, session_id, strong_areas, weak_areas, missing_areas) VALUES (?, ?, ?, ?, ?)",
            (
                _uuid(),
                session_id,
                json.dumps(data["strong_areas"]),
                json.dumps(data["weak_areas"]),
                json.dumps(data["missing_areas"]),
            ),
        )
    await db.commit()


async def get_gap_analysis(db: aiosqlite.Connection, session_id: str) -> aiosqlite.Row | None:
    async with db.execute(
        "SELECT * FROM gap_analysis WHERE session_id = ?", (session_id,)
    ) as cur:
        return await cur.fetchone()


# ── Elaboration Turns ─────────────────────────────────────────────────────────

async def append_elaboration_turn(
    db: aiosqlite.Connection, session_id: str, role: str, content: str
) -> None:
    async with db.execute(
        "SELECT COUNT(*) FROM elaboration_turns WHERE session_id = ?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
        position = row[0]
    await db.execute(
        "INSERT INTO elaboration_turns (id, session_id, role, content, position) VALUES (?, ?, ?, ?, ?)",
        (_uuid(), session_id, role, content, position),
    )
    await db.commit()


async def get_elaboration_turns(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM elaboration_turns WHERE session_id = ? ORDER BY position", (session_id,)
    ) as cur:
        return await cur.fetchall()


# ── Application ───────────────────────────────────────────────────────────────

async def upsert_application(
    db: aiosqlite.Connection,
    session_id: str,
    challenge: str,
    response: str | None = None,
    feedback: str | None = None,
) -> None:
    existing = await get_application(db, session_id)
    if existing:
        await db.execute(
            "UPDATE application SET challenge_text=?, user_response=?, buddy_feedback=? WHERE session_id=?",
            (challenge, response, feedback, session_id),
        )
    else:
        await db.execute(
            "INSERT INTO application (id, session_id, challenge_text, user_response, buddy_feedback) VALUES (?, ?, ?, ?, ?)",
            (_uuid(), session_id, challenge, response, feedback),
        )
    await db.commit()


async def get_application(db: aiosqlite.Connection, session_id: str) -> aiosqlite.Row | None:
    async with db.execute(
        "SELECT * FROM application WHERE session_id = ?", (session_id,)
    ) as cur:
        return await cur.fetchone()


# ── Card Proposals ────────────────────────────────────────────────────────────

async def insert_card_proposals(
    db: aiosqlite.Connection, session_id: str, cards: list[dict]
) -> None:
    """Each dict: {front, back, card_type, tags, topic_id?, is_gap_card, duplicate_warning}"""
    for c in cards:
        await db.execute(
            """INSERT INTO card_proposals
               (id, session_id, topic_id, front, back, card_type, tags, is_gap_card, duplicate_warning)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _uuid(),
                session_id,
                c.get("topic_id"),
                c["front"],
                c["back"],
                c["card_type"],
                json.dumps(c.get("tags", [])),
                int(c.get("is_gap_card", False)),
                int(c.get("duplicate_warning", False)),
            ),
        )
    await db.commit()


async def get_card_proposals(db: aiosqlite.Connection, session_id: str) -> list[aiosqlite.Row]:
    async with db.execute(
        "SELECT * FROM card_proposals WHERE session_id = ?", (session_id,)
    ) as cur:
        return await cur.fetchall()


async def update_card_committed(
    db: aiosqlite.Connection, card_id: str, anki_note_id: int | None = None
) -> None:
    await db.execute(
        "UPDATE card_proposals SET committed = 1, anki_note_id = ? WHERE id = ?",
        (anki_note_id, card_id),
    )
    await db.commit()


async def count_committed_cards(db: aiosqlite.Connection, session_id: str) -> int:
    async with db.execute(
        "SELECT COUNT(*) FROM card_proposals WHERE session_id = ? AND committed = 1", (session_id,)
    ) as cur:
        row = await cur.fetchone()
        return row[0]
