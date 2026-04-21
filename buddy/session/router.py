import json
from datetime import datetime, timezone
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from buddy.db import repository as repo
from buddy.db.deps import get_db_dep
from buddy.session import manager
from buddy.session.models import (
    AnswersSubmit,
    ApplicationSubmit,
    CardCommit,
    CardProposal,
    CardType,
    GapAnalysis,
    ElaborationTurn,
    ApplicationOut,
    QuizAnswer,
    QuizQuestion,
    Score,
    Preset,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    TopicsSubmit,
)

router = APIRouter()
DB = Annotated[aiosqlite.Connection, Depends(get_db_dep)]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_label() -> str:
    return datetime.now(timezone.utc).strftime("%b %-d")


def _build_detail(
    session: aiosqlite.Row,
    topics,
    priming,
    quiz_qs,
    quiz_as,
    gap_row,
    elab_turns,
    app_row,
    cards,
) -> SessionDetail:
    return SessionDetail(
        id=session["id"],
        title=session["title"],
        preset=session["preset"],
        active_steps=json.loads(session["active_steps"]),
        current_step=session["current_step"],
        status=session["status"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        target_deck=session["target_deck"],
        topics=[r["topic"] for r in topics],
        priming_questions=[r["question_text"] for r in priming],
        quiz_questions=[
            QuizQuestion(
                id=r["id"],
                question_text=r["question_text"],
                topic=r["topic_id"],
            )
            for r in quiz_qs
        ],
        quiz_answers=[
            QuizAnswer(
                id=r["id"],
                question_id=r["question_id"],
                answer_text=r["answer_text"],
                score=r["score"],
                feedback=r["feedback"],
            )
            for r in quiz_as
        ],
        gap_analysis=GapAnalysis(
            strong_areas=json.loads(gap_row["strong_areas"]),
            weak_areas=json.loads(gap_row["weak_areas"]),
            missing_areas=json.loads(gap_row["missing_areas"]),
        ) if gap_row else None,
        elaboration_turns=[
            ElaborationTurn(
                id=r["id"],
                role=r["role"],
                content=r["content"],
                position=r["position"],
            )
            for r in elab_turns
        ],
        application=ApplicationOut(
            id=app_row["id"],
            challenge_text=app_row["challenge_text"],
            user_response=app_row["user_response"],
            buddy_feedback=app_row["buddy_feedback"],
        ) if app_row else None,
        card_proposals=[
            CardProposal(
                id=r["id"],
                front=r["front"],
                back=r["back"],
                card_type=r["card_type"],
                tags=json.loads(r["tags"]),
                source_topic=r["topic_id"],
                is_gap_card=bool(r["is_gap_card"]),
                duplicate_warning=bool(r["duplicate_warning"]),
                approved=bool(r["approved"]),
                committed=bool(r["committed"]),
                anki_note_id=r["anki_note_id"],
            )
            for r in cards
        ],
    )


async def _load_detail(db: aiosqlite.Connection, session_id: str) -> SessionDetail:
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    topics = await repo.get_topics(db, session_id)
    priming = await repo.get_priming_questions(db, session_id)
    quiz_qs = await repo.get_quiz_questions(db, session_id)
    quiz_as = await repo.get_quiz_answers(db, session_id)
    gap_row = await repo.get_gap_analysis(db, session_id)
    elab = await repo.get_elaboration_turns(db, session_id)
    app_row = await repo.get_application(db, session_id)
    cards = await repo.get_card_proposals(db, session_id)
    return _build_detail(session, topics, priming, quiz_qs, quiz_as, gap_row, elab, app_row, cards)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionDetail)
async def create_session(body: SessionCreate, db: DB):
    active_steps = manager.PRESET_STEPS[body.preset.value]
    session_id = await repo.create_session(db, body.preset.value, active_steps)
    return await _load_detail(db, session_id)


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(db: DB, status: str | None = None, limit: int = 20):
    rows = await repo.list_sessions(db, status=status, limit=limit)
    result = []
    for r in rows:
        gap_row = await repo.get_gap_analysis(db, r["id"])
        weak = json.loads(gap_row["weak_areas"]) if gap_row else []
        committed = await repo.count_committed_cards(db, r["id"])
        result.append(SessionSummary(
            id=r["id"],
            title=r["title"],
            preset=r["preset"],
            current_step=r["current_step"],
            status=r["status"],
            created_at=r["created_at"],
            weak_areas=weak,
            cards_committed=committed,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: DB):
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/topics", response_model=SessionDetail)
async def submit_topics(session_id: str, body: TopicsSubmit, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 1)

    topic_ids = await repo.insert_topics(db, session_id, body.topics)

    # Auto-title from first topic + date
    title = f"{body.topics[0]} — {_date_label()}"
    await repo.update_session_title(db, session_id, title)

    # Stub priming questions (Phase 3: replaced with Gemini call)
    stub_priming = [
        f"What do you already know about {body.topics[0]}?",
        "What aspects are you most uncertain about?",
        "What's the key outcome you expect from watching this?",
    ]
    await repo.insert_priming_questions(db, session_id, stub_priming, topic_ids[0])
    await manager.advance_step(db, session_id, 1)
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/watched", response_model=SessionDetail)
async def signal_watched(session_id: str, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 2)

    topics = await repo.get_topics(db, session_id)
    topic = topics[0]["topic"] if topics else "the topic"

    # Stub quiz questions (Phase 3: replaced with Gemini call)
    stub_questions = [
        f"Explain the core concept of {topic} in your own words.",
        f"What are the most important components of {topic}?",
        f"Describe a scenario where understanding {topic} would be critical.",
    ]
    await repo.insert_quiz_questions(db, session_id, stub_questions)
    await manager.advance_step(db, session_id, 2)
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/answers", response_model=SessionDetail)
async def submit_answers(session_id: str, body: AnswersSubmit, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 3)

    # Stub scoring (Phase 3: real semantic scoring via Gemini)
    answers = [
        {
            "question_id": a.question_id,
            "answer_text": a.answer_text,
            "score": "partial",
            "feedback": "Stub feedback — real scoring added in Phase 3.",
        }
        for a in body.answers
    ]
    await repo.insert_quiz_answers(db, session_id, answers)

    # Explicit gap analysis trigger site — swap stub for Gemini in Phase 3
    await manager.run_gap_analysis(db, session_id, answers)
    await manager.advance_step(db, session_id, 3)  # -> step 4

    # Stub first elaboration turn, then advance to step 5
    await repo.append_elaboration_turn(
        db, session_id, "buddy",
        "Let's dig into the areas where you had gaps. What's your current understanding of the weak areas identified?"
    )
    await manager.advance_step(db, session_id, 4)  # -> step 5
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/elaboration/close", response_model=SessionDetail)
async def close_elaboration(session_id: str, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 5)

    gap = await repo.get_gap_analysis(db, session_id)
    weak = json.loads(gap["weak_areas"]) if gap else ["the topic"]
    challenge = f"Apply your understanding of {weak[0]}: describe a real-world scenario and how you would handle it."

    await repo.upsert_application(db, session_id, challenge)
    await manager.advance_step(db, session_id, 5)
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/application", response_model=SessionDetail)
async def submit_application(session_id: str, body: ApplicationSubmit, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 6)

    app_row = await repo.get_application(db, session_id)
    challenge = app_row["challenge_text"] if app_row else "Challenge"
    feedback = None if body.response is None else "Stub feedback — real evaluation added in Phase 3."
    await repo.upsert_application(db, session_id, challenge, body.response, feedback)

    topics = await repo.get_topics(db, session_id)
    topic = topics[0]["topic"] if topics else "the topic"

    # Stub card proposals (Phase 3: real Gemini call)
    stub_cards = [
        {
            "front": f"What is {topic}?",
            "back": f"A foundational concept covered in your study session on {topic}.",
            "card_type": "basic",
            "tags": ["stub", topic.lower()[:20]],
            "is_gap_card": False,
            "duplicate_warning": False,
        },
        {
            "front": f"Key mechanism of {topic}:",
            "back": "{{c1::Fill this in after Phase 3 Gemini integration}}",
            "card_type": "cloze",
            "tags": ["stub", "gap"],
            "is_gap_card": True,
            "duplicate_warning": False,
        },
    ]
    await repo.insert_card_proposals(db, session_id, stub_cards)
    await manager.advance_step(db, session_id, 6)
    return await _load_detail(db, session_id)


@router.get("/sessions/{session_id}/cards", response_model=list[CardProposal])
async def get_cards(session_id: str, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = await repo.get_card_proposals(db, session_id)
    return [
        CardProposal(
            id=r["id"],
            front=r["front"],
            back=r["back"],
            card_type=r["card_type"],
            tags=json.loads(r["tags"]),
            source_topic=r["topic_id"],
            is_gap_card=bool(r["is_gap_card"]),
            duplicate_warning=bool(r["duplicate_warning"]),
            approved=bool(r["approved"]),
            committed=bool(r["committed"]),
            anki_note_id=r["anki_note_id"],
        )
        for r in rows
    ]


@router.post("/sessions/{session_id}/cards/commit", response_model=SessionDetail)
async def commit_cards(session_id: str, body: CardCommit, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 7)

    # Only commit approved IDs — zero approved is valid
    for card_id in body.approved_ids:
        # Phase 2: real anki_add_card call goes here; stub uses None for note_id
        await repo.update_card_committed(db, card_id, anki_note_id=None)

    await repo.update_session_status(db, session_id, "completed")
    return await _load_detail(db, session_id)
