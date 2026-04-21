from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel


class Preset(str, Enum):
    full = "full"
    quick = "quick"
    low_energy = "low_energy"
    quiz = "quiz"
    card_sprint = "card_sprint"


class CardType(str, Enum):
    basic = "basic"
    cloze = "cloze"
    reversed = "reversed"


class Score(str, Enum):
    strong = "strong"
    partial = "partial"
    missing = "missing"


# ── Request bodies ──────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    preset: Preset = Preset.full
    target_deck: str | None = None


class TopicsSubmit(BaseModel):
    topics: list[str]


class AnswerItem(BaseModel):
    question_id: str
    answer_text: str


class AnswersSubmit(BaseModel):
    answers: list[AnswerItem]


class ApplicationSubmit(BaseModel):
    response: str | None = None  # None = skipped


class CardCommit(BaseModel):
    approved_ids: list[str]


# ── Child record shapes ──────────────────────────────────────────────────────

class QuizQuestion(BaseModel):
    id: str
    question_text: str
    topic: str | None


class QuizAnswer(BaseModel):
    id: str
    question_id: str
    answer_text: str
    score: Score
    feedback: str


class GapAnalysis(BaseModel):
    strong_areas: list[str]
    weak_areas: list[str]
    missing_areas: list[str]


class ElaborationTurn(BaseModel):
    id: str
    role: str  # "buddy" | "user"
    content: str
    position: int


class ApplicationOut(BaseModel):
    id: str
    challenge_text: str
    user_response: str | None
    buddy_feedback: str | None


class CardProposal(BaseModel):
    id: str
    front: str
    back: str
    card_type: CardType
    tags: list[str]
    source_topic: str | None
    is_gap_card: bool
    duplicate_warning: bool
    approved: bool
    committed: bool
    anki_note_id: int | None


# ── Session summaries / detail ───────────────────────────────────────────────

class SessionSummary(BaseModel):
    id: str
    title: str | None
    preset: Preset
    current_step: int
    status: str
    created_at: str
    weak_areas: list[str]
    cards_committed: int


class SessionDetail(BaseModel):
    id: str
    title: str | None
    preset: Preset
    active_steps: list[int]
    current_step: int
    status: str
    created_at: str
    updated_at: str
    target_deck: str | None
    topics: list[str]
    priming_questions: list[str]
    quiz_questions: list[QuizQuestion]
    quiz_answers: list[QuizAnswer]
    gap_analysis: GapAnalysis | None
    elaboration_turns: list[ElaborationTurn]
    application: ApplicationOut | None
    card_proposals: list[CardProposal]
