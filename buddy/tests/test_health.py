import pytest
from httpx import AsyncClient, ASGITransport
from buddy.main import app


@pytest.fixture
async def client(tmp_path, monkeypatch):
    # Point DB to a temp file so tests don't touch ~/.buddy/buddy.db
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    # Re-import config after env patch
    import importlib, buddy.config as cfg
    importlib.reload(cfg)
    import buddy.db.database as db_mod
    importlib.reload(db_mod)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
