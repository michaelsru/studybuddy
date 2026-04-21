import json
import logging
from datetime import datetime, timezone
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from buddy.config import DEFAULT_ANKI_DECK
from buddy.db import repository as repo
from buddy.db.deps import get_db_dep
from buddy.session import manager
from buddy.tools import anki
from buddy.tools.anki import AnkiConnectError, AnkiUnavailableError
from buddy.gemini import client as gemini
from buddy.gemini.client import GeminiError
from buddy.gemini.prompts import quiz as quiz_prompt
from buddy.gemini.prompts import gap_analysis as gap_prompt
from buddy.gemini.prompts import priming as priming_prompt
from buddy.gemini.prompts import card_generation as card_prompt
from buddy.gemini.prompts import application as app_prompt
from buddy.session.models import (
    AnswersSubmit,
    ApplicationSubmit,
    ApplicationChallengeOut,
    CardCommit,
    CardProposal,
    CardProposalsOut,
    CardType,
    GapAnalysis,
    GapAnalysisOut,
    ElaborationTurn,
    ApplicationOut,
    ApplicationFeedbackOut,
    PrimingOut,
    QuizAnswer,
    QuizQuestion,
    QuizQuestionsOut,
    QuizWorksheetOut,
    ScoringOut,
    Score,
    Preset,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    TopicsSubmit,
)

router = APIRouter()
DB = Annotated[aiosqlite.Connection, Depends(get_db_dep)]
logger = logging.getLogger(__name__)


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
    # answer_key revealed only after answers are submitted
    qs_key_map = {r["id"]: r["answer_key"] for r in quiz_qs} if quiz_as else {}
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
                question_type=r["question_type"] if r["question_type"] else "short_answer",
                options=json.loads(r["options"]) if r["options"] else None,
                difficulty=r["difficulty"] if r["difficulty"] else "medium",
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
                answer_key=qs_key_map.get(r["question_id"]),
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

    # Anki gap check — degrades gracefully if Anki is closed
    try:
        gaps = await anki.anki_find_gaps(body.topics)
    except AnkiUnavailableError:
        logger.warning("Anki unavailable during priming — using gap-unaware prompt")
        gaps = []

    system, user = priming_prompt.build(body.topics, gaps)
    try:
        result = await gemini.generate(user, system, schema=PrimingOut)
        questions = result.questions
    except GeminiError as e:
        logger.warning("Gemini priming failed, using fallback: %s", e)
        questions = [
            f"What do you already know about {body.topics[0]}?",
            "What aspects are you most uncertain about?",
            "What outcome do you expect from watching this?",
        ]

    await repo.insert_priming_questions(db, session_id, questions, topic_ids[0])
    await manager.advance_step(db, session_id, 1)
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/watched", response_model=SessionDetail)
async def signal_watched(session_id: str, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 2)

    topics = await repo.get_topics(db, session_id)
    topic_names = [r["topic"] for r in topics]

    system, user = quiz_prompt.build(topic_names)
    try:
        result = await gemini.generate(user, system, schema=QuizWorksheetOut)
        question_dicts = [
            {
                "question_text": q.question_text,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "options": q.options,
                "answer_key": q.answer_key,
            }
            for q in result.questions
        ]
    except GeminiError as e:
        logger.warning("Gemini quiz generation failed, using fallback: %s", e)
        topic = topic_names[0] if topic_names else "the topic"
        question_dicts = [
            {"question_text": f"Explain the core concept of {topic} in your own words.", "question_type": "short_answer", "difficulty": "medium", "options": None, "answer_key": ""},
            {"question_text": f"What are the most important components of {topic}?", "question_type": "short_answer", "difficulty": "medium", "options": None, "answer_key": ""},
            {"question_text": f"Describe a scenario where understanding {topic} would be critical.", "question_type": "short_answer", "difficulty": "hard", "options": None, "answer_key": ""},
        ]

    await repo.insert_quiz_questions(db, session_id, question_dicts)
    await manager.advance_step(db, session_id, 2)
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/answers", response_model=SessionDetail)
async def submit_answers(session_id: str, body: AnswersSubmit, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 3)

    quiz_qs = await repo.get_quiz_questions(db, session_id)
    qs_by_id = {r["id"]: dict(r) for r in quiz_qs}  # dict() so .get() works

    # Build QA pairs with answer_key and options so Gemini marks against the key
    qa_pairs = [
        {
            "question_id": a.question_id,
            "question_text": qs_by_id.get(a.question_id, {}).get("question_text", ""),
            "question_type": qs_by_id.get(a.question_id, {}).get("question_type", "short_answer"),
            "options": json.loads(qs_by_id[a.question_id]["options"]) if (a.question_id in qs_by_id and qs_by_id[a.question_id]["options"]) else None,
            "answer_key": qs_by_id.get(a.question_id, {}).get("answer_key", ""),
            "answer_text": a.answer_text,
        }
        for a in body.answers
    ]

    # Batch scoring — Gemini marks against answer key for all types
    system, user = gap_prompt.build(qa_pairs)
    try:
        scoring = await gemini.generate(user, system, schema=ScoringOut)
        scored = [
            {
                "question_id": s.question_id,
                "answer_text": next((a.answer_text for a in body.answers if a.question_id == s.question_id), ""),
                "score": s.score.value,
                "feedback": s.feedback,
            }
            for s in scoring.answers
        ]
    except GeminiError as e:
        logger.warning("Gemini scoring failed, using fallback: %s", e)
        scored = [
            {"question_id": a.question_id, "answer_text": a.answer_text, "score": "partial", "feedback": "Scoring unavailable."}
            for a in body.answers
        ]

    await repo.insert_quiz_answers(db, session_id, scored)

    # Gap analysis — second Gemini call using scored answers
    strong, weak, missing = [], [], []
    for s in scored:
        if s["score"] == "strong":
            strong.append(s["question_id"])
        elif s["score"] == "missing":
            missing.append(s["question_id"])
        else:
            weak.append(s["question_id"])

    # Pass Q+A context for richer gap analysis
    gap_qa = [
        {
            "question_id": s["question_id"],
            "question_text": qs_by_id.get(s["question_id"], ""),
            "answer_text": s["answer_text"],
        }
        for s in scored
    ]
    gap_system, gap_user = gap_prompt.build_gap_analysis(gap_qa, scored)
    try:
        gap_result = await gemini.generate(gap_user, gap_system, schema=GapAnalysisOut)
        gap_dict = {
            "strong_areas": gap_result.strong_areas,
            "weak_areas": gap_result.weak_areas,
            "missing_areas": gap_result.missing_areas,
        }
    except GeminiError as e:
        logger.warning("Gemini gap analysis failed, using scoring fallback: %s", e)
        gap_dict = {"strong_areas": strong, "weak_areas": weak, "missing_areas": missing}

    await repo.upsert_gap_analysis(db, session_id, gap_dict)
    await manager.advance_step(db, session_id, 3)  # → step 4

    # Opening elaboration turn from Buddy
    gap_row = await repo.get_gap_analysis(db, session_id)
    if gap_row:
        weak = json.loads(gap_row["weak_areas"])
        missing = json.loads(gap_row["missing_areas"])
        focus = ", ".join((weak + missing)[:3]) or "the studied topics"
        opening = f"Let's explore your gaps in {focus}. What's your current mental model for this?"
    else:
        opening = "Let's dig into the areas where you had gaps. What's your current understanding?"

    await repo.append_elaboration_turn(db, session_id, "buddy", opening)
    await manager.advance_step(db, session_id, 4)  # → step 5
    return await _load_detail(db, session_id)


@router.post("/sessions/{session_id}/elaboration/close", response_model=SessionDetail)
async def close_elaboration(session_id: str, db: DB):
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 5)

    gap = await repo.get_gap_analysis(db, session_id)
    weak = json.loads(gap["weak_areas"]) if gap else []
    missing = json.loads(gap["missing_areas"]) if gap else []

    system, user = app_prompt.build(weak_areas=weak, missing_areas=missing)
    try:
        result = await gemini.generate(user, system, schema=ApplicationChallengeOut)
        challenge = result.challenge_text
    except GeminiError as e:
        logger.warning("Gemini application challenge failed, using fallback: %s", e)
        focus = (weak + missing)[0] if (weak + missing) else "the topic"
        challenge = f"Apply your understanding of {focus}: describe a real-world scenario and how you would handle it."

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

    # Generate real feedback via Gemini if user responded
    if body.response is not None:
        gap_row_for_feedback = await repo.get_gap_analysis(db, session_id)
        weak_fb = json.loads(gap_row_for_feedback["weak_areas"]) if gap_row_for_feedback else []
        miss_fb = json.loads(gap_row_for_feedback["missing_areas"]) if gap_row_for_feedback else []
        fb_system, fb_user = app_prompt.build_feedback(challenge, body.response, weak_fb, miss_fb)
        try:
            fb_result = await gemini.generate(fb_user, fb_system, schema=ApplicationFeedbackOut)
            feedback = fb_result.feedback
        except GeminiError as e:
            logger.warning("Gemini application feedback failed: %s", e)
            feedback = "Unable to generate feedback at this time."
    else:
        feedback = None
    await repo.upsert_application(db, session_id, challenge, body.response, feedback)

    topics = await repo.get_topics(db, session_id)
    topic_names = [r["topic"] for r in topics]
    gap_row = await repo.get_gap_analysis(db, session_id)
    strong = json.loads(gap_row["strong_areas"]) if gap_row else []
    weak = json.loads(gap_row["weak_areas"]) if gap_row else []
    missing = json.loads(gap_row["missing_areas"]) if gap_row else []
    elab_turns = await repo.get_elaboration_turns(db, session_id)
    elab = [{"role": t["role"], "content": t["content"]} for t in elab_turns]

    system, user = card_prompt.build(
        topics=topic_names,
        strong_areas=strong,
        weak_areas=weak,
        missing_areas=missing,
        elaboration_turns=elab,
    )
    try:
        result = await gemini.generate(user, system, schema=CardProposalsOut)
        cards = result.cards
    except GeminiError as e:
        logger.warning("Gemini card generation failed, using fallback: %s", e)
        cards = []

    # Check duplicates at generation time (advisory)
    card_dicts = []
    for card in cards:
        try:
            is_dupe = await anki.anki_check_duplicate(card.front)
        except (AnkiUnavailableError, AnkiConnectError):
            is_dupe = False
        card_dicts.append({
            "front": card.front,
            "back": card.back,
            "card_type": card.card_type.value,
            "tags": card.tags,
            "is_gap_card": card.is_gap_card,
            "duplicate_warning": is_dupe,
        })

    await repo.insert_card_proposals(db, session_id, card_dicts)
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
    logger = logging.getLogger(__name__)
    session = await repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    manager.assert_step(session, 7)

    deck = session["target_deck"] or DEFAULT_ANKI_DECK

    # Validate deck before touching anything
    if body.approved_ids:
        try:
            if not await anki.anki_deck_exists(deck):
                raise HTTPException(
                    status_code=400,
                    detail=f"Anki deck '{deck}' not found. Create it in Anki or set target_deck on this session."
                )
        except AnkiUnavailableError:
            raise HTTPException(status_code=503, detail="AnkiConnect unreachable — is Anki open?")

    # Batch fetch — avoids N+1
    proposals = await repo.get_card_proposals_by_ids(db, body.approved_ids)

    # Mark approved in DB upfront so frontend can distinguish approved-but-failed
    for proposal in proposals:
        await repo.update_card_approved(db, proposal["id"])

    for proposal in proposals:
        try:
            is_dupe = await anki.anki_check_duplicate(proposal["front"])
        except (AnkiUnavailableError, AnkiConnectError) as e:
            logger.warning("Anki check_duplicate failed for %s: %s", proposal["id"], e)
            is_dupe = False

        if is_dupe:
            await repo.update_card_duplicate_warning(db, proposal["id"])
            continue

        try:
            note_id = await anki.anki_add_card(
                front=proposal["front"],
                back=proposal["back"],
                deck=deck,
                tags=json.loads(proposal["tags"]),
                card_type=proposal["card_type"],
            )
            await repo.update_card_committed(db, proposal["id"], anki_note_id=note_id)
        except AnkiUnavailableError as e:
            logger.error("AnkiConnect unavailable mid-commit: %s", e)
            raise HTTPException(status_code=503, detail="AnkiConnect unavailable — partial commit saved")
        except AnkiConnectError as e:
            logger.warning("anki_add_card failed for %s: %s", proposal["id"], e)

    await repo.update_session_status(db, session_id, "completed")
    return await _load_detail(db, session_id)

