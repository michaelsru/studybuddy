import json
import logging
from typing import AsyncIterator, Type, TypeVar
from pydantic import BaseModel
from google import genai
from google.genai import types
from buddy.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiError(Exception):
    """Gemini API or parse failure."""


def _client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY not set")
    return genai.Client(api_key=GEMINI_API_KEY)


async def generate(user: str, system: str, schema: Type[T]) -> T:
    """One-shot structured JSON call. Parses into schema."""
    client = _client()
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
    )
    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=user,
            config=config,
        )
        text = response.text
    except Exception as e:
        raise GeminiError(f"Gemini API error: {e}") from e

    try:
        return schema.model_validate_json(text)
    except Exception as e:
        raise GeminiError(f"Failed to parse Gemini response into {schema.__name__}: {e}\nRaw: {text[:500]}") from e


async def stream(user: str, system: str) -> AsyncIterator[str]:
    """Streaming call yielding text tokens."""
    client = _client()
    config = types.GenerateContentConfig(system_instruction=system)
    try:
        async for chunk in await client.aio.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=user,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as e:
        raise GeminiError(f"Gemini stream error: {e}") from e

