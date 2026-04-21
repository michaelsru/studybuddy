import json
import pytest
import aiosqlite
from buddy.db.database import init_db, get_db
from buddy.db import repository as repo


@pytest.fixture
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    import importlib, buddy.config as cfg, buddy.db.database as db_mod
    importlib.reload(cfg)
    importlib.reload(db_mod)
    await db_mod.init_db()
    conn = await db_mod.get_db()
    yield conn
    await conn.close()


async def test_create_and_get_session(db):
    id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    row = await repo.get_session(db, id)
    assert row is not None
    assert row["preset"] == "full"
    assert row["current_step"] == 1
    assert json.loads(row["active_steps"]) == [1, 2, 3, 4, 5, 6, 7]


async def test_get_session_unknown_returns_none(db):
    row = await repo.get_session(db, "nonexistent-id")
    assert row is None


async def test_update_session_step(db):
    id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    await repo.update_session_step(db, id, 3)
    row = await repo.get_session(db, id)
    assert row["current_step"] == 3


async def test_update_session_title(db):
    id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    await repo.update_session_title(db, id, "TCP/IP — Apr 21")
    row = await repo.get_session(db, id)
    assert row["title"] == "TCP/IP — Apr 21"


async def test_topics_roundtrip(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    await repo.insert_topics(db, session_id, ["TCP/IP", "Subnetting"])
    rows = await repo.get_topics(db, session_id)
    assert [r["topic"] for r in rows] == ["TCP/IP", "Subnetting"]
    assert rows[0]["position"] == 0


async def test_priming_questions_roundtrip(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    qs = ["Q1", "Q2", "Q3"]
    await repo.insert_priming_questions(db, session_id, qs)
    rows = await repo.get_priming_questions(db, session_id)
    assert [r["question_text"] for r in rows] == qs


async def test_quiz_roundtrip(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    q_ids = await repo.insert_quiz_questions(db, session_id, ["Q1", "Q2"])
    answers = [
        {"question_id": q_ids[0], "answer_text": "ans1", "score": "strong", "feedback": "good"},
        {"question_id": q_ids[1], "answer_text": "ans2", "score": "missing", "feedback": "try again"},
    ]
    await repo.insert_quiz_answers(db, session_id, answers)
    ans_rows = await repo.get_quiz_answers(db, session_id)
    assert len(ans_rows) == 2
    assert ans_rows[0]["score"] == "strong"


async def test_gap_analysis_roundtrip(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    data = {"strong_areas": ["A"], "weak_areas": ["B"], "missing_areas": []}
    await repo.upsert_gap_analysis(db, session_id, data)
    row = await repo.get_gap_analysis(db, session_id)
    assert json.loads(row["weak_areas"]) == ["B"]

    # Upsert again — should update not duplicate
    data2 = {"strong_areas": ["A", "C"], "weak_areas": [], "missing_areas": ["D"]}
    await repo.upsert_gap_analysis(db, session_id, data2)
    row2 = await repo.get_gap_analysis(db, session_id)
    assert json.loads(row2["strong_areas"]) == ["A", "C"]
    assert json.loads(row2["missing_areas"]) == ["D"]


async def test_elaboration_turns_ordering(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    await repo.append_elaboration_turn(db, session_id, "buddy", "Hello")
    await repo.append_elaboration_turn(db, session_id, "user", "Hi")
    await repo.append_elaboration_turn(db, session_id, "buddy", "Let's go")
    rows = await repo.get_elaboration_turns(db, session_id)
    assert [r["role"] for r in rows] == ["buddy", "user", "buddy"]
    assert [r["position"] for r in rows] == [0, 1, 2]


async def test_card_proposals_partial_commit(db):
    session_id = await repo.create_session(db, "full", [1, 2, 3, 4, 5, 6, 7])
    await repo.insert_card_proposals(db, session_id, [
        {"front": "Q1", "back": "A1", "card_type": "basic", "tags": [], "is_gap_card": False, "duplicate_warning": False},
        {"front": "Q2", "back": "A2", "card_type": "basic", "tags": [], "is_gap_card": False, "duplicate_warning": False},
    ])
    rows = await repo.get_card_proposals(db, session_id)
    assert len(rows) == 2

    await repo.update_card_committed(db, rows[0]["id"])
    rows2 = await repo.get_card_proposals(db, session_id)
    committed = [r for r in rows2 if r["committed"]]
    not_committed = [r for r in rows2 if not r["committed"]]
    assert len(committed) == 1
    assert len(not_committed) == 1

    count = await repo.count_committed_cards(db, session_id)
    assert count == 1
