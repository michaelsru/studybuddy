import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from buddy.db.database import init_db
from buddy.session.router import router as session_router
from buddy.tools import anki
from buddy.tools.anki import AnkiUnavailableError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await anki.ping()
        logger.info("AnkiConnect reachable")
    except AnkiUnavailableError:
        logger.warning("AnkiConnect unreachable — card features will be unavailable")
    yield


app = FastAPI(title="Buddy", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import WebSocket
from buddy.session import ws as elab_ws

app.include_router(session_router)


@app.websocket("/sessions/{session_id}/elaboration")
async def elaboration_endpoint(session_id: str, websocket: WebSocket):
    await elab_ws.elaboration_ws(session_id, websocket)



@app.get("/health")
async def health():
    return {"status": "ok"}
