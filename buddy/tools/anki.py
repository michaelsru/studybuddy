import logging
import httpx
from buddy.config import ANKICONNECT_URL, ANKI_CLOZE_MODEL
from buddy.tools.schemas import AnkiSearchResult, AnkiCardMaturity

logger = logging.getLogger(__name__)

# ── Errors ────────────────────────────────────────────────────────────────────

class AnkiUnavailableError(Exception):
    """AnkiConnect HTTP request failed — Anki is likely not running."""


class AnkiConnectError(Exception):
    """AnkiConnect returned a logical error in its response body."""


# ── Core HTTP helper ──────────────────────────────────────────────────────────

async def _invoke(action: str, **params) -> object:
    payload = {"action": action, "version": 6, "params": params}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(ANKICONNECT_URL, json=payload)
            r.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise AnkiUnavailableError(str(e)) from e

    body = r.json()
    if body.get("error"):
        raise AnkiConnectError(body["error"])
    return body["result"]


# ── Ping ──────────────────────────────────────────────────────────────────────

async def ping() -> bool:
    """Returns True if AnkiConnect is reachable."""
    await _invoke("version")
    return True


async def anki_deck_exists(deck: str) -> bool:
    """Return True if the named deck exists in Anki."""
    names: list[str] = await _invoke("deckNames")
    return deck in names


# ── Five tools ────────────────────────────────────────────────────────────────

async def anki_search(query: str) -> list[AnkiSearchResult]:
    """Full-text search across all notes. Returns parsed front/back/tags."""
    note_ids: list[int] = await _invoke("findNotes", query=query)
    if not note_ids:
        return []
    notes = await _invoke("notesInfo", notes=note_ids)
    results = []
    for n in notes:
        fields = n.get("fields", {})
        front = fields.get("Front", {}).get("value", "") or fields.get("Text", {}).get("value", "")
        back = fields.get("Back", {}).get("value", "")
        results.append(AnkiSearchResult(
            note_id=n["noteId"],
            front=front,
            back=back,
            tags=n.get("tags", []),
        ))
    return results


async def anki_find_gaps(topics: list[str]) -> list[str]:
    """Return topics with zero card coverage. Uses full-text search — no leading wildcards."""
    gaps = []
    for topic in topics:
        # Anki full-text search: quotes for exact phrase, Anki matches anywhere in note
        note_ids: list[int] = await _invoke("findNotes", query=f'"{topic}"')
        if not note_ids:
            gaps.append(topic)
    return gaps


async def anki_get_card_maturity(topic: str) -> AnkiCardMaturity:
    """Return young vs mature card counts for a topic."""
    card_ids: list[int] = await _invoke("findCards", query=f'"{topic}"')
    if not card_ids:
        return AnkiCardMaturity(topic=topic, young=0, mature=0)

    cards = await _invoke("getCardInfo", cards=card_ids)
    young = sum(1 for c in cards if c.get("interval", 0) < 21)
    mature = sum(1 for c in cards if c.get("interval", 0) >= 21)
    return AnkiCardMaturity(topic=topic, young=young, mature=mature)


async def anki_check_duplicate(front_text: str) -> bool:
    """Return True if a note with a near-matching front already exists."""
    note_ids: list[int] = await _invoke("findNotes", query=f'front:"{front_text}"')
    return len(note_ids) > 0


async def anki_add_card(
    front: str,
    back: str,
    deck: str,
    tags: list[str],
    card_type: str,  # "basic" | "cloze" | "reversed"
) -> int:
    """Add a card to Anki. Returns the new note ID."""
    if card_type == "cloze":
        model = ANKI_CLOZE_MODEL
        fields = {"Text": front, "Back Extra": back}
    elif card_type == "reversed":
        model = "Basic (and reversed card)"
        fields = {"Front": front, "Back": back}
    else:  # basic (default)
        model = "Basic"
        fields = {"Front": front, "Back": back}

    note = {
        "deckName": deck,
        "modelName": model,
        "fields": fields,
        "tags": tags,
        "options": {"allowDuplicate": False},
    }
    note_id: int = await _invoke("addNote", note=note)
    return note_id
