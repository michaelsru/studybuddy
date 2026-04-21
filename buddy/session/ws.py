import json
import logging
import re
from fastapi import WebSocket, WebSocketDisconnect
from buddy.db.database import get_db
from buddy.db import repository as repo
from buddy.session import manager
from buddy.gemini import client as gemini
from buddy.gemini.client import GeminiError
from buddy.gemini.prompts import elaboration as elab_prompt

logger = logging.getLogger(__name__)

_TRAILER_RE = re.compile(r"<suggest_close>(\{.*?\})</suggest_close>", re.DOTALL)


def _strip_trailer(text: str) -> tuple[str, bool]:
    match = _TRAILER_RE.search(text)
    if not match:
        return text.strip(), False
    clean = _TRAILER_RE.sub("", text).strip()
    try:
        suggest_close = json.loads(match.group(1)).get("suggest_close", False)
    except Exception:
        suggest_close = False
    return clean, bool(suggest_close)


async def elaboration_ws(session_id: str, ws: WebSocket):
    db = await get_db()
    try:
        session = await repo.get_session(db, session_id)
        if not session or session["current_step"] != 5:
            await ws.close(code=4000)
            return

        await ws.accept()

        # On connect: resend last Buddy turn (reconnect support)
        turns = await repo.get_elaboration_turns(db, session_id)
        last_buddy = next((t for t in reversed(turns) if t["role"] == "buddy"), None)
        if last_buddy:
            await ws.send_json({"type": "buddy_message", "content": last_buddy["content"], "suggest_close": False})

        try:
            while True:
                data = await ws.receive_json()
                msg_type = data.get("type")

                if msg_type == "ping":
                    await ws.send_json({"type": "pong"})
                    continue

                if msg_type != "user_message":
                    continue

                content = data.get("content", "").strip()
                if not content:
                    continue

                # Persist user turn BEFORE Gemini call (reconnect safety)
                await repo.append_elaboration_turn(db, session_id, "user", content)

                # Reload all turns for context
                all_turns = await repo.get_elaboration_turns(db, session_id)
                history = [{"role": t["role"], "content": t["content"]} for t in all_turns]

                gap_row = await repo.get_gap_analysis(db, session_id)
                topics_rows = await repo.get_topics(db, session_id)
                topic_names = [r["topic"] for r in topics_rows]
                weak = json.loads(gap_row["weak_areas"]) if gap_row else []
                missing = json.loads(gap_row["missing_areas"]) if gap_row else []

                system, prompt = elab_prompt.build(topic_names, weak, missing, history)

                # Stream response, collect full text for persistence
                full_text = ""
                try:
                    async for token in gemini.stream(prompt, system):
                        full_text += token
                        # Stream tokens without the trailer to client
                        clean_so_far, _ = _strip_trailer(full_text)
                        await ws.send_json({"type": "token", "content": token})
                except GeminiError as e:
                    logger.error("Gemini stream error: %s", e)
                    await ws.send_json({"type": "error", "content": str(e)})
                    continue

                clean_content, suggest_close = _strip_trailer(full_text)

                # Persist completed Buddy turn
                await repo.append_elaboration_turn(db, session_id, "buddy", clean_content)

                await ws.send_json({
                    "type": "buddy_message",
                    "content": clean_content,
                    "suggest_close": suggest_close,
                })

        except WebSocketDisconnect:
            logger.info("Elaboration WS disconnected for session %s", session_id)
        except Exception as e:
            logger.error("Elaboration WS error: %s", e)
            try:
                await ws.send_json({"type": "error", "content": "Internal error"})
            except Exception:
                pass
    finally:
        await db.close()
