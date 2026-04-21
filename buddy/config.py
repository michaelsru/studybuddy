import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# search upward from CWD; try .env.local first, fall back to .env
load_dotenv(find_dotenv(".env.local") or find_dotenv(".env"))

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
DB_PATH: Path = Path(os.getenv("DB_PATH", "~/.buddy/buddy.db")).expanduser()
ANKICONNECT_URL: str = os.getenv("ANKICONNECT_URL", "http://localhost:8765")
