import aiosqlite
from pathlib import Path
from buddy.config import DB_PATH

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    async with aiosqlite.connect(DB_PATH) as db:
        for path in migration_files:
            if path.name == "001_initial.sql":
                # Multi-statement DDL — use executescript
                await db.executescript(path.read_text())
            else:
                # Incremental migrations — run per-statement, ignore duplicate errors
                for statement in path.read_text().split(";"):
                    stmt = statement.strip()
                    if not stmt or stmt.startswith("--"):
                        continue
                    try:
                        await db.execute(stmt)
                    except Exception:
                        pass  # e.g. duplicate column on ALTER TABLE
        await db.commit()
