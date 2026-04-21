import pytest
import respx
import httpx
from buddy.tools import anki
from buddy.tools.anki import AnkiConnectError, AnkiUnavailableError
from buddy.config import ANKICONNECT_URL

ANKI_URL = ANKICONNECT_URL


def anki_response(result=None, error=None):
    return {"result": result, "error": error}


# ── anki_search ───────────────────────────────────────────────────────────────

@respx.mock
async def test_anki_search_returns_parsed_results():
    respx.post(ANKI_URL).mock(side_effect=[
        httpx.Response(200, json=anki_response([1, 2])),
        httpx.Response(200, json=anki_response([
            {"noteId": 1, "fields": {"Front": {"value": "Q1"}, "Back": {"value": "A1"}}, "tags": ["tcp"]},
            {"noteId": 2, "fields": {"Front": {"value": "Q2"}, "Back": {"value": "A2"}}, "tags": []},
        ])),
    ])
    results = await anki.anki_search("TCP")
    assert len(results) == 2
    assert results[0].front == "Q1"
    assert results[0].tags == ["tcp"]


@respx.mock
async def test_anki_search_empty():
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response([])))
    results = await anki.anki_search("nonexistent")
    assert results == []


# ── anki_find_gaps ────────────────────────────────────────────────────────────

@respx.mock
async def test_anki_find_gaps_covered_topic_excluded():
    # TCP has cards, Subnetting does not
    respx.post(ANKI_URL).mock(side_effect=[
        httpx.Response(200, json=anki_response([42])),   # TCP → 1 note
        httpx.Response(200, json=anki_response([])),      # Subnetting → 0 notes
    ])
    gaps = await anki.anki_find_gaps(["TCP", "Subnetting"])
    assert gaps == ["Subnetting"]


@respx.mock
async def test_anki_find_gaps_empty_deck_all_gaps():
    """Empty deck: every topic should be returned as a gap."""
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response([])))
    gaps = await anki.anki_find_gaps(["TCP", "ARP", "DNS"])
    assert gaps == ["TCP", "ARP", "DNS"]


# ── anki_get_card_maturity ────────────────────────────────────────────────────

@respx.mock
async def test_anki_get_card_maturity():
    respx.post(ANKI_URL).mock(side_effect=[
        httpx.Response(200, json=anki_response([1, 2, 3])),
        httpx.Response(200, json=anki_response([
            {"interval": 5},   # young
            {"interval": 30},  # mature
            {"interval": 25},  # mature
        ])),
    ])
    result = await anki.anki_get_card_maturity("TCP")
    assert result.young == 1
    assert result.mature == 2


@respx.mock
async def test_anki_get_card_maturity_empty():
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response([])))
    result = await anki.anki_get_card_maturity("unknown")
    assert result.young == 0
    assert result.mature == 0


# ── anki_check_duplicate ──────────────────────────────────────────────────────

@respx.mock
async def test_anki_check_duplicate_found():
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response([99])))
    assert await anki.anki_check_duplicate("What is TCP?") is True


@respx.mock
async def test_anki_check_duplicate_not_found():
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response([])))
    assert await anki.anki_check_duplicate("What is TCP?") is False


# ── anki_add_card ─────────────────────────────────────────────────────────────

@respx.mock
async def test_anki_add_card_basic():
    route = respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response(1234)))
    note_id = await anki.anki_add_card("Q", "A", "Default", [], "basic")
    assert note_id == 1234
    body = route.calls[0].request.read()
    import json
    payload = json.loads(body)
    assert payload["params"]["note"]["modelName"] == "Basic"
    assert "Front" in payload["params"]["note"]["fields"]


@respx.mock
async def test_anki_add_card_cloze_uses_correct_model():
    route = respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response(5678)))
    await anki.anki_add_card("{{c1::concept}}", "", "Default", [], "cloze")
    import json
    payload = json.loads(route.calls[0].request.read())
    assert payload["params"]["note"]["modelName"] == "Cloze"
    assert "Text" in payload["params"]["note"]["fields"]


@respx.mock
async def test_anki_add_card_reversed_uses_correct_model():
    route = respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response(9999)))
    await anki.anki_add_card("Q", "A", "Default", [], "reversed")
    import json
    payload = json.loads(route.calls[0].request.read())
    assert payload["params"]["note"]["modelName"] == "Basic (and reversed card)"


@respx.mock
async def test_anki_add_card_anki_error_raises():
    respx.post(ANKI_URL).mock(return_value=httpx.Response(200, json=anki_response(None, error="duplicate")))
    with pytest.raises(AnkiConnectError):
        await anki.anki_add_card("Q", "A", "Default", [], "basic")


# ── error types ───────────────────────────────────────────────────────────────

@respx.mock
async def test_anki_unavailable_raises_correct_error():
    respx.post(ANKI_URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(AnkiUnavailableError):
        await anki.ping()
