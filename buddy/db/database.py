import aiosqlite
from pathlib import Path
from buddy.config import DB_PATH

_MIGRATION = Path(__file__).parent / "migrations" / "001_initial.sql"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    sql = _MIGRATION.read_text()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(sql)
        await db.commit()
