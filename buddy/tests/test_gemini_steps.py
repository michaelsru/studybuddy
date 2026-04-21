"""
Tests for Gemini-powered step endpoints. gemini.generate is mocked via AsyncMock
so no real API key is needed.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch
import respx
import httpx
from httpx import AsyncClient, ASGITransport
from buddy.main import app
from buddy.config import ANKICONNECT_URL

from buddy.session.models import (
    PrimingOut,
    QuizWorksheetOut,
    QuizQuestionItem,
    ScoringOut,
    AnswerScore,
    Score,
    GapAnalysisOut,
    ApplicationChallengeOut,
    CardProposalsOut,
    CardSpec,
    CardType,
)


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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _anki_ok(result):
    return httpx.Response(200, json={"result": result, "error": None})


async def _advance_to_step(client, step: int) -> tuple[str, dict]:
    """Helper: create session and advance to a given step."""
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]

    if step >= 2:
        with respx.mock:
            respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))  # anki_find_gaps
            with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = PrimingOut(questions=["Q1?", "Q2?", "Q3?"])
                await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP"]})

    if step >= 3:
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = QuizWorksheetOut(questions=[
                QuizQuestionItem(question_text="A?", question_type="short_answer", difficulty="medium", options=None, answer_key="Answer A"),
                QuizQuestionItem(question_text="B?", question_type="multiple_choice", difficulty="easy", options=["A) X", "B) Y", "C) Z", "D) W"], answer_key="A) X"),
                QuizQuestionItem(question_text="C?", question_type="fill_blank", difficulty="hard", options=None, answer_key="fill answer"),
            ])
            r = await client.post(f"/sessions/{sid}/watched")

    if step >= 5:
        quiz_qs = (await client.get(f"/sessions/{sid}")).json()["quiz_questions"]
        answers = [{"question_id": q["id"], "answer_text": "my answer"} for q in quiz_qs]
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            def side_effect(user, system, schema=None):
                if schema == ScoringOut:
                    return ScoringOut(answers=[
                        AnswerScore(question_id=a["question_id"], score=Score.partial, feedback="ok")
                        for a in answers
                    ])
                return GapAnalysisOut(strong_areas=[], weak_areas=["TCP handshake"], missing_areas=["ARP"])
            mock_gen.side_effect = side_effect
            r = await client.post(f"/sessions/{sid}/answers", json={"answers": answers})

    if step >= 6:
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = ApplicationChallengeOut(challenge_text="Describe a TCP scenario.")
            await client.post(f"/sessions/{sid}/elaboration/close")

    return sid, (await client.get(f"/sessions/{sid}")).json()


# ── Step 1 — Priming ──────────────────────────────────────────────────────────

async def test_step1_priming_uses_gemini(client):
    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))  # gaps = []
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = PrimingOut(questions=["What is TCP?", "How does ARP work?"])
            r = await client.post("/sessions", json={"preset": "full"})
            sid = r.json()["id"]
            r = await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP"]})

    assert r.status_code == 200
    data = r.json()
    assert data["priming_questions"] == ["What is TCP?", "How does ARP work?"]
    assert data["current_step"] == 2


async def test_step1_anki_unavailable_falls_back(client):
    """Anki closed → priming still works with gap-unaware fallback questions."""
    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(side_effect=httpx.ConnectError("refused"))
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = PrimingOut(questions=["Fallback Q?"])
            r = await client.post("/sessions", json={"preset": "full"})
            sid = r.json()["id"]
            r = await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP"]})

    assert r.status_code == 200
    assert r.json()["current_step"] == 2


async def test_step1_gemini_failure_falls_back(client):
    """Gemini error → fallback stub questions used."""
    from buddy.gemini.client import GeminiError
    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = GeminiError("timeout")
            r = await client.post("/sessions", json={"preset": "full"})
            sid = r.json()["id"]
            r = await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP"]})

    assert r.status_code == 200
    assert len(r.json()["priming_questions"]) == 3  # fallback has 3


# ── Step 3 — Quiz ────────────────────────────────────────────────────────────

async def test_step3_quiz_from_gemini(client):
    sid, _ = await _advance_to_step(client, 2)
    with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = QuizWorksheetOut(questions=[
            QuizQuestionItem(question_text="Q1?", question_type="short_answer", difficulty="medium", options=None, answer_key="k1"),
            QuizQuestionItem(question_text="Q2?", question_type="multiple_choice", difficulty="easy", options=["A) X", "B) Y", "C) Z", "D) W"], answer_key="A) X"),
            QuizQuestionItem(question_text="Q3?", question_type="calculation", difficulty="hard", options=None, answer_key="42"),
        ])
        r = await client.post(f"/sessions/{sid}/watched")

    assert r.status_code == 200
    qs = r.json()["quiz_questions"]
    assert len(qs) == 3
    assert qs[0]["question_text"] == "Q1?"
    assert qs[0]["question_type"] == "short_answer"
    assert qs[1]["question_type"] == "multiple_choice"
    assert qs[1]["options"] is not None
    assert qs[2]["question_type"] == "calculation"
    # answer_key NOT returned to frontend (only after submission)
    assert "answer_key" not in qs[0]


# ── Step 4 — Scoring + Gap Analysis ──────────────────────────────────────────

async def test_step4_scoring_and_gap_analysis(client):
    sid, data = await _advance_to_step(client, 3)
    quiz_qs = data["quiz_questions"]
    answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]

    call_count = 0
    def side_effect(user, system, schema):
        nonlocal call_count
        call_count += 1
        if schema == ScoringOut:
            return ScoringOut(answers=[
                AnswerScore(question_id=a["question_id"], score=Score.strong, feedback="Good")
                for a in answers
            ])
        return GapAnalysisOut(strong_areas=["TCP"], weak_areas=["ARP"], missing_areas=[])

    with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = side_effect
        r = await client.post(f"/sessions/{sid}/answers", json={"answers": answers})

    assert r.status_code == 200
    assert call_count == 2  # one scoring call + one gap analysis call
    data = r.json()
    assert data["current_step"] == 5
    assert data["gap_analysis"]["weak_areas"] == ["ARP"]
    assert data["quiz_answers"][0]["score"] == "strong"


async def test_step4_scoring_gemini_failure_uses_partial(client):
    from buddy.gemini.client import GeminiError
    sid, data = await _advance_to_step(client, 3)
    quiz_qs = data["quiz_questions"]
    answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]

    call_count = 0
    def side_effect(user, system, schema):
        nonlocal call_count
        call_count += 1
        if schema == ScoringOut:
            raise GeminiError("parse error")
        return GapAnalysisOut(strong_areas=[], weak_areas=["TCP"], missing_areas=[])

    with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = side_effect
        r = await client.post(f"/sessions/{sid}/answers", json={"answers": answers})

    assert r.status_code == 200
    assert all(a["score"] == "partial" for a in r.json()["quiz_answers"])


# ── Step 6 — Application Challenge ────────────────────────────────────────────

async def test_step6_application_challenge_from_gemini(client):
    sid, _ = await _advance_to_step(client, 5)
    with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = ApplicationChallengeOut(challenge_text="Debug this TCP issue.")
        r = await client.post(f"/sessions/{sid}/elaboration/close")

    assert r.status_code == 200
    assert r.json()["application"]["challenge_text"] == "Debug this TCP issue."


# ── Step 7 — Card Proposals ───────────────────────────────────────────────────

async def test_step7_cards_from_gemini_with_dupe_check(client):
    sid, _ = await _advance_to_step(client, 6)

    cards_out = CardProposalsOut(cards=[
        CardSpec(front="What is TCP?", back="A transport protocol", card_type=CardType.basic, tags=["tcp"], is_gap_card=False),
        CardSpec(front="TCP {{c1::three-way handshake}}", back="", card_type=CardType.cloze, tags=["tcp"], is_gap_card=True),
    ])
    with respx.mock:
        # card 1: dupe found; card 2: no dupe
        respx.post(ANKICONNECT_URL).mock(side_effect=[
            _anki_ok([99]),  # check_duplicate card 1 → dupe
            _anki_ok([]),    # check_duplicate card 2 → no dupe
        ])
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = cards_out
            r = await client.post(f"/sessions/{sid}/application", json={"response": None})

    assert r.status_code == 200
    proposals = r.json()["card_proposals"]
    assert len(proposals) == 2
    dupes = [p for p in proposals if p["duplicate_warning"]]
    assert len(dupes) == 1
    assert dupes[0]["front"] == "What is TCP?"


async def test_step7_skip_response_still_generates_cards(client):
    """Skipping application step (response=None) still generates cards."""
    sid, _ = await _advance_to_step(client, 6)

    with respx.mock:
        respx.post(ANKICONNECT_URL).mock(return_value=_anki_ok([]))
        with patch("buddy.gemini.client.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = CardProposalsOut(cards=[
                CardSpec(front="Q", back="A", card_type=CardType.basic, tags=[], is_gap_card=False)
            ])
            r = await client.post(f"/sessions/{sid}/application", json={"response": None})

    assert r.status_code == 200
    assert r.json()["application"]["user_response"] is None
    assert len(r.json()["card_proposals"]) == 1
