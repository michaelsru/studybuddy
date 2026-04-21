import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from buddy.main import app
from buddy.config import ANKICONNECT_URL
from buddy.session.models import (
    PrimingOut, QuizWorksheetOut, QuizQuestionItem, ScoringOut, AnswerScore, Score,
    GapAnalysisOut, ApplicationChallengeOut, ApplicationFeedbackOut, CardProposalsOut, CardSpec, CardType,
)


def _anki_ok(result):
    return httpx.Response(200, json={"result": result, "error": None})


def _mock_anki_add(note_id: int = 1234):
    return respx.post(ANKICONNECT_URL).mock(side_effect=[
        _anki_ok([]),            # check_duplicate → no dupe
        _anki_ok(note_id),       # add_card → note_id
    ])


_WORKSHEET = QuizWorksheetOut(questions=[
    QuizQuestionItem(question_text="A?", question_type="short_answer", difficulty="medium", options=None, answer_key="Ans A"),
    QuizQuestionItem(question_text="B?", question_type="multiple_choice", difficulty="easy", options=["A) X", "B) Y", "C) Z", "D) W"], answer_key="A) X"),
    QuizQuestionItem(question_text="C?", question_type="fill_blank", difficulty="hard", options=None, answer_key="fill"),
])


def _gemini_side_effect(question_ids: list[str]):
    def _side(user, system, schema=None):
        if schema == PrimingOut:
            return PrimingOut(questions=["Q1?", "Q2?"])
        if schema == QuizWorksheetOut:
            return _WORKSHEET
        if schema == ScoringOut:
            return ScoringOut(answers=[
                AnswerScore(question_id=qid, score=Score.partial, feedback="ok")
                for qid in question_ids
            ])
        if schema == GapAnalysisOut:
            return GapAnalysisOut(strong_areas=[], weak_areas=["TCP"], missing_areas=[])
        if schema == ApplicationChallengeOut:
            return ApplicationChallengeOut(challenge_text="Describe a TCP scenario.")
        if schema == ApplicationFeedbackOut:
            return ApplicationFeedbackOut(feedback="Good effort — you identified the key concepts.")
        if schema == CardProposalsOut:
            return CardProposalsOut(cards=[
                CardSpec(front="What is TCP?", back="A protocol", card_type=CardType.basic, tags=[], is_gap_card=False),
                CardSpec(front="What is ARP?", back="Address resolution", card_type=CardType.basic, tags=[], is_gap_card=True),
            ])
        return None
    return _side


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    import importlib, buddy.config as cfg, buddy.db.database as db_mod
    importlib.reload(cfg)
    importlib.reload(db_mod)
    await db_mod.init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_create_session(client):
    r = await client.post("/sessions", json={"preset": "full"})
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 1
    assert data["status"] == "in_progress"
    assert data["active_steps"] == [1, 2, 3, 4, 5, 6, 7]


async def test_full_sequence(client):
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]

    with respx.mock, patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = _gemini_side_effect([])  # q_ids filled in dynamically below

        # Step 1 → 2
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))  # anki_find_gaps
        r = await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP", "Subnetting"]})
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == 2
        assert data["title"].startswith("TCP/IP")
        assert len(data["priming_questions"]) >= 1

        # Step 2 → 3
        r = await client.post(f"/sessions/{sid}/watched")
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == 3
        assert len(data["quiz_questions"]) == 3

        # Step 3 → 5
        quiz_qs = data["quiz_questions"]
        q_ids = [q["id"] for q in quiz_qs]
        mock_gen.side_effect = _gemini_side_effect(q_ids)
        answers = [{"question_id": q["id"], "answer_text": "my answer"} for q in quiz_qs]
        r = await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == 5
        assert data["gap_analysis"] is not None
        assert len(data["elaboration_turns"]) >= 1

        # Step 5 → 6
        r = await client.post(f"/sessions/{sid}/elaboration/close")
        assert r.status_code == 200
        assert r.json()["current_step"] == 6

        # Step 6 → 7 (Anki dupe checks for 2 cards)
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))  # no dupes
        r = await client.post(f"/sessions/{sid}/application", json={"response": "my answer"})
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == 7
        assert len(data["card_proposals"]) == 2

    # Commit all cards
    card_ids = [c["id"] for c in data["card_proposals"]]
    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(side_effect=[
            _anki_ok(["Default"]),  # deckNames
            _anki_ok([]),           # check card 1
            _anki_ok(1001),         # add card 1
            _anki_ok([]),           # check card 2
            _anki_ok(1002),         # add card 2
        ])
        r = await client.post(f"/sessions/{sid}/cards/commit", json={"approved_ids": card_ids})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert all(c["committed"] for c in data["card_proposals"])


async def test_out_of_order_returns_409(client):
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]
    # Try to signal watched before submitting topics
    r = await client.post(f"/sessions/{sid}/watched")
    assert r.status_code == 409


async def test_partial_commit(client):
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]

    with respx.mock, patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))
        mock_gen.side_effect = _gemini_side_effect([])

        await client.post(f"/sessions/{sid}/topics", json={"topics": ["DNS"]})
        await client.post(f"/sessions/{sid}/watched")
        r = await client.get(f"/sessions/{sid}")
        quiz_qs = r.json()["quiz_questions"]
        q_ids = [q["id"] for q in quiz_qs]
        mock_gen.side_effect = _gemini_side_effect(q_ids)
        answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]
        await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
        await client.post(f"/sessions/{sid}/elaboration/close")
        await client.post(f"/sessions/{sid}/application", json={"response": None})

    r = await client.get(f"/sessions/{sid}")
    cards = r.json()["card_proposals"]
    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(side_effect=[
            _anki_ok(["Default"]),  # deckNames
            _anki_ok([]),           # check card 1
            _anki_ok(2001),         # add card 1
        ])
        r = await client.post(
            f"/sessions/{sid}/cards/commit",
            json={"approved_ids": [cards[0]["id"]]},
        )
    assert r.status_code == 200
    result = r.json()
    committed = [c for c in result["card_proposals"] if c["committed"]]
    not_committed = [c for c in result["card_proposals"] if not c["committed"]]
    assert len(committed) == 1
    assert len(not_committed) == 1
    assert result["status"] == "completed"


async def test_zero_approved_commit(client):
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]

    with respx.mock, patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))
        mock_gen.side_effect = _gemini_side_effect([])

        await client.post(f"/sessions/{sid}/topics", json={"topics": ["HTTP"]})
        await client.post(f"/sessions/{sid}/watched")
        r = await client.get(f"/sessions/{sid}")
        quiz_qs = r.json()["quiz_questions"]
        q_ids = [q["id"] for q in quiz_qs]
        mock_gen.side_effect = _gemini_side_effect(q_ids)
        answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]
        await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
        await client.post(f"/sessions/{sid}/elaboration/close")
        await client.post(f"/sessions/{sid}/application", json={"response": None})

    with respx.mock:
        r = await client.post(f"/sessions/{sid}/cards/commit", json={"approved_ids": []})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
