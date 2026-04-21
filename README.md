# Buddy

Session-based study assistant. Primes you before a video, quizzes you after, identifies gaps, elaborates on weak areas, and writes Anki cards.

## Prerequisites

- **Python ≥ 3.13** via [pyenv](https://github.com/pyenv/pyenv) (virtualenv: `studybuddy`)
- **Node ≥ 20**
- **Anki** running with [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on (`2055492159`)

## Setup

### Backend

```bash
cd buddy
cp ../.env.example .env   # fill in GEMINI_API_KEY
pip install -r requirements-dev.txt
uvicorn buddy.main:app --reload
```

Runs on `http://localhost:8000`. DB is created at `~/.buddy/buddy.db` on first start.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Runs on `http://localhost:5173`.

## Running Tests

```bash
cd buddy
pytest
```
