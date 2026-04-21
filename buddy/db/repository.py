import aiosqlite
from buddy.db.database import get_db


async def ping_db() -> bool:
    db = await get_db()
    await db.close()
    return True
