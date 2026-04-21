import aiosqlite
from buddy.db.database import get_db


async def get_db_dep():
    db = await get_db()
    try:
        yield db
    finally:
        await db.close()
