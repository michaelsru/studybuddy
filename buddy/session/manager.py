import json
import aiosqlite
from fastapi import HTTPException

from buddy.db import repository as repo

VALID_TRANSITIONS: dict[int, int] = {
    1: 2,
    2: 3,
    3: 4,  # answers -> gap analysis (transient)
    4: 5,  # gap analysis complete -> elaboration
    5: 6,
    6: 7,
}

# Preset → active steps
PRESET_STEPS: dict[str, list[int]] = {
    "full":        [1, 2, 3, 4, 5, 6, 7],
    "quick":       [1, 2, 7],
    "low_energy":  [2, 7],
    "quiz":        [3, 4, 5, 7],
    "card_sprint": [1, 7],
}


def assert_step(session: aiosqlite.Row, expected: int) -> None:
    if session["current_step"] != expected:
        raise HTTPException(
            status_code=409,
            detail=f"Session is at step {session['current_step']}, expected {expected}",
        )


async def advance_step(db: aiosqlite.Connection, session_id: str, from_step: int) -> int:
    next_step = VALID_TRANSITIONS.get(from_step)
    if next_step is None:
        raise HTTPException(status_code=409, detail=f"No transition defined from step {from_step}")
    await repo.update_session_step(db, session_id, next_step)
    return next_step


async def run_gap_analysis(
    db: aiosqlite.Connection, session_id: str, answers: list[dict]
) -> dict:
    """
    Stub — Phase 3 swaps this for a real Gemini call.
    Returns the gap analysis dict and persists it.
    """
    gap = {
        "strong_areas": ["Topic overview"],
        "weak_areas": ["Deep mechanics", "Edge cases"],
        "missing_areas": [],
    }
    await repo.upsert_gap_analysis(db, session_id, gap)
    return gap
