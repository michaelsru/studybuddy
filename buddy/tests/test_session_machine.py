import pytest
from httpx import AsyncClient, ASGITransport
from buddy.main import app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    import importlib, buddy.config as cfg, buddy.db.database as db_mod
    importlib.reload(cfg)
    importlib.reload(db_mod)
    await db_mod.init_db()  # ASGITransport doesn't fire lifespan events
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
    # Create
    r = await client.post("/sessions", json={"preset": "full"})
    sid = r.json()["id"]

    # Step 1 → 2
    r = await client.post(f"/sessions/{sid}/topics", json={"topics": ["TCP/IP", "Subnetting"]})
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 2
    assert data["title"].startswith("TCP/IP")
    assert len(data["priming_questions"]) == 3

    # Step 2 → 3
    r = await client.post(f"/sessions/{sid}/watched")
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 3
    assert len(data["quiz_questions"]) == 3

    # Step 3 → 5 (via 4 internally)
    quiz_qs = data["quiz_questions"]
    answers = [{"question_id": q["id"], "answer_text": "my answer"} for q in quiz_qs]
    r = await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 5
    assert data["gap_analysis"] is not None
    assert len(data["elaboration_turns"]) == 1

    # Step 5 → 6
    r = await client.post(f"/sessions/{sid}/elaboration/close")
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 6
    assert data["application"] is not None

    # Step 6 → 7
    r = await client.post(f"/sessions/{sid}/application", json={"response": "my answer"})
    assert r.status_code == 200
    data = r.json()
    assert data["current_step"] == 7
    assert len(data["card_proposals"]) == 2

    # Commit all cards
    card_ids = [c["id"] for c in data["card_proposals"]]
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

    await client.post(f"/sessions/{sid}/topics", json={"topics": ["DNS"]})
    await client.post(f"/sessions/{sid}/watched")
    r = await client.get(f"/sessions/{sid}")
    quiz_qs = r.json()["quiz_questions"]
    answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]
    await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
    await client.post(f"/sessions/{sid}/elaboration/close")
    await client.post(f"/sessions/{sid}/application", json={"response": None})

    r = await client.get(f"/sessions/{sid}")
    cards = r.json()["card_proposals"]
    # Approve only the first card
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

    await client.post(f"/sessions/{sid}/topics", json={"topics": ["HTTP"]})
    await client.post(f"/sessions/{sid}/watched")
    r = await client.get(f"/sessions/{sid}")
    quiz_qs = r.json()["quiz_questions"]
    answers = [{"question_id": q["id"], "answer_text": "ans"} for q in quiz_qs]
    await client.post(f"/sessions/{sid}/answers", json={"answers": answers})
    await client.post(f"/sessions/{sid}/elaboration/close")
    await client.post(f"/sessions/{sid}/application", json={"response": None})

    r = await client.post(f"/sessions/{sid}/cards/commit", json={"approved_ids": []})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
