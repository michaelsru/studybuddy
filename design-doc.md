# Buddy — Study Assistant System Design

## Overview

Buddy is a session-based study assistant that guides users through a structured learning loop: priming → watch → recall → gap analysis → elaboration → application → card generation. It integrates with the user's personal Anki deck to avoid duplication and surface gaps.

---

## High-Level Architecture

```
┌─────────────────────────────────────────┐
│              React Frontend             │
│  (Session UI, Quiz, Card Editor)        │
└────────────────┬────────────────────────┘
                 │ HTTP / WebSocket
┌────────────────▼────────────────────────┐
│           Python Backend (FastAPI)      │
│  Session Manager │ Tool Executor        │
│  Claude API Client                      │
└──────┬──────────────────────┬───────────┘
       │                      │
┌──────▼──────┐     ┌─────────▼──────────┐
│  Gemini API │     │  AnkiConnect       │
│  (gemini-   │     │  (localhost:8765)  │
│  3.1-pro)   │     │  Anki must be open │
└─────────────┘     └────────────────────┘
```

---

## Session Flow

The seven steps map to distinct backend states. Each step transitions when the frontend signals completion.

| Step | Trigger | Buddy Action |
|------|---------|--------------|
| 1. Priming | User submits topic list | Generate 3–5 questions per topic from deck gaps |
| 2. Watch | User reads priming Qs, starts video | No action — user watches |
| 3. Recall Quiz | User signals "I've watched" | Generate quiz questions; accept free-text answers |
| 4. Gap Analysis | User submits quiz answers | Score answers semantically; identify weak areas |
| 5. Elaboration | Auto-follows gap analysis | Generate why/how follow-ups on weak areas |
| 6. Application | Auto-follows elaboration | Generate one applied challenge per weak area |
| 7. Card Proposals | User ready to generate cards | Propose cards; check deck for duplicates/gaps |

Steps 4–6 can be collapsed or skipped (see Presets below).

---

## Frontend Components

### Session Shell
- Step progress indicator (1–7)
- Current step view rendered below
- Preset selector and step-skip controls

### Step Views

**Step 1 — Topic Input**
- Multiline text field for topic list (pasted from YouTube AI chat)
- "Generate Priming Questions" button
- Displays priming questions when ready

**Step 2 — Watch Prompt**
- Static screen showing priming questions for reference
- "I've finished watching" button

**Step 3 — Recall Quiz**
- One question displayed at a time
- Free-text answer input
- Progress through all questions; submit when done

**Step 4–5 — Gap Analysis + Elaboration**
- Streamed conversational output from Buddy
- Displays scored areas (strong / weak / missing)
- Buddy follow-up questions rendered inline; user can respond

**Step 6 — Application Prompt**
- Challenge displayed as a card
- Optional free-text response field
- "Submit for feedback" or "Skip" action

**Step 7 — Card Proposals**
- List of proposed cards with front/back visible
- Per-card actions: Approve / Edit / Remove
- Card type badge: Basic | Cloze | Reversed
- Tag editor per card
- "Add Approved Cards to Anki" button

---

## Backend Structure

```
buddy/
├── main.py                  # FastAPI app, routes
├── session/
│   ├── manager.py           # Session state machine
│   └── models.py            # Session, Step, Answer data models
├── claude/
│   ├── client.py            # Gemini API wrapper (streaming)
│   └── prompts/             # System + step-specific prompt templates
│       ├── priming.py
│       ├── quiz.py
│       ├── gap_analysis.py
│       ├── elaboration.py
│       ├── application.py
│       └── card_generation.py
├── tools/
│   ├── anki.py              # AnkiConnect HTTP client
│   └── schemas.py           # Tool call schemas for Claude
└── config.py                # Env vars, model settings
```

---

## API Endpoints

All endpoints are session-scoped. Sessions are keyed by `session_id` (UUID).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/sessions` | Create new session |
| GET | `/sessions/{id}` | Get session state (includes current_step) |
| GET | `/sessions` | List sessions (filter by status) |
| POST | `/sessions/{id}/topics` | Submit topic list → advances to step 1 |
| POST | `/sessions/{id}/watched` | Signal watch complete → advances to step 3 |
| POST | `/sessions/{id}/answers` | Submit quiz answers → advances to step 4 |
| POST | `/sessions/{id}/elaboration/close` | User closes elaboration → advances to step 6 |
| POST | `/sessions/{id}/application` | Submit or skip application → advances to step 7 |
| GET | `/sessions/{id}/cards` | Get proposed card list |
| POST | `/sessions/{id}/cards/commit` | Add approved cards to Anki → marks session complete |
| WS | `/sessions/{id}/elaboration` | WebSocket for step 5 only |

---

## Step Transition Spec

Each step has exactly one trigger that advances `current_step`. The backend validates that the session is in the correct step before processing — out-of-order requests return a `409 Conflict`.

| Step | Name | Transition Trigger | Transition Type |
|------|------|--------------------|-----------------|
| 1 | Priming | `POST /topics` submitted + Gemini response complete | Automatic |
| 2 | Watch | `POST /watched` from user | Manual (user) |
| 3 | Recall Quiz | `POST /answers` submitted + Gemini response complete | Automatic |
| 4 | Gap Analysis | Gap analysis generation complete (backend, no user action) | Automatic |
| 5 | Elaboration | `POST /elaboration/close` from user | Manual (user) |
| 6 | Application | `POST /application` submitted or skipped | Manual (user) |
| 7 | Card Proposals | `POST /cards/commit` + Anki writes complete | Automatic |

### Step 4 → 5 transition (Gap Analysis → Elaboration)

Steps 4 and 5 are chained automatically on the backend. Once quiz answers are submitted:

1. Backend calls Gemini to score answers and produce gap analysis → persists to `gap_analysis` table
2. Backend immediately opens the elaboration context (persists first Buddy turn to `elaboration_turns`)
3. Response to `POST /answers` returns both the gap analysis result and the first elaboration message
4. Frontend renders gap analysis summary, then opens the WebSocket for step 5

No separate user action is needed to move from step 4 to step 5.

### Step 5 → 6 transition (Elaboration → Application)

Elaboration ends when the user explicitly closes it. Buddy may suggest closing, but does not force it.

- Buddy signals readiness to close by including `"suggest_close": true` in its WebSocket message (see WebSocket protocol below)
- Frontend renders a "Move on →" button when `suggest_close` is true, alongside the normal reply input
- User can continue replying or click "Move on →", which calls `POST /elaboration/close`
- `POST /elaboration/close` closes the WebSocket connection server-side and advances to step 6

If the user closes elaboration without Buddy suggesting it, that's valid — `POST /elaboration/close` is accepted at any point during step 5.

---

## WebSocket Protocol (Step 5 — Elaboration)

The WebSocket at `WS /sessions/{id}/elaboration` is the only persistent connection in Buddy. It is opened by the frontend at the start of step 5 and closed when the user advances to step 6.

### Message format (client → server)

```json
{
  "type": "user_message",
  "content": "I think ARP resolves IPs to MAC addresses by broadcasting..."
}
```

### Message format (server → client)

```json
{
  "type": "buddy_message",
  "content": "That's right — and what happens if the target is on a different subnet?",
  "suggest_close": false
}
```

When Buddy decides the weak area is sufficiently covered:

```json
{
  "type": "buddy_message",
  "content": "Good — I think we've covered ARP and subnetting well. Ready to move on to the application challenge?",
  "suggest_close": true
}
```

### Additional message types

| Type | Direction | Purpose |
|------|-----------|---------|
| `ping` | client → server | Keepalive |
| `pong` | server → client | Keepalive response |
| `error` | server → client | Gemini error or session state conflict |
| `close` | server → client | Sent after `POST /elaboration/close` is processed; signals frontend to tear down |

### Persistence during WebSocket session

Every message pair (user turn + Buddy reply) is persisted to `elaboration_turns` immediately after the Buddy response is complete. If the connection drops mid-session, the frontend can reconnect to `WS /sessions/{id}/elaboration` and the backend will resend the last Buddy message so the user can continue without losing context.

---

## Anki Toolchain (via AnkiConnect)

Buddy calls these tools internally during card generation and priming. The user never directly invokes them.

| Tool | Purpose |
|------|---------|
| `anki_search(query)` | Full-text search across deck fronts/backs |
| `anki_find_gaps(topics)` | Given a topic list, return subtopics with no card coverage |
| `anki_get_card_maturity(topic)` | Return young vs. mature card counts per topic |
| `anki_check_duplicate(front_text)` | Check if a near-match card already exists |
| `anki_add_card(front, back, deck, tags, card_type)` | Create a new card |

AnkiConnect requires Anki to be running locally with the AnkiConnect add-on installed (add-on code: `2055492159`).

---

## Data Models (Application Layer)

These are the Pydantic models used in the application layer. They map closely to the SQLite schema but are denormalized for convenience — e.g., a `Session` object loads all child records eagerly for small sessions.

### Session
```
Session
  id: UUID
  created_at: datetime
  preset: Enum(full | quick | low_energy | quiz | card_sprint)
  topics: List[str]
  step: Enum(1..7)
  priming_questions: List[str]
  quiz_questions: List[QuizQuestion]
  quiz_answers: List[QuizAnswer]
  gap_analysis: GapAnalysis
  card_proposals: List[CardProposal]
```

### QuizQuestion / Answer
```
QuizQuestion
  id: UUID
  text: str
  topic: str

QuizAnswer
  question_id: UUID
  answer_text: str
  score: Enum(strong | partial | missing)
  feedback: str
```

### GapAnalysis
```
GapAnalysis
  strong_areas: List[str]
  weak_areas: List[str]
  missing_areas: List[str]
  elaboration_followups: List[str]
```

### CardProposal
```
CardProposal
  id: UUID
  front: str
  back: str
  card_type: Enum(basic | cloze | reversed)
  tags: List[str]
  source_topic: str
  is_gap_card: bool
  duplicate_warning: bool
  approved: bool
```

---

## Session Presets

Presets set which steps are active at session creation. The user can also toggle individual steps.

| Preset | Active Steps |
|--------|-------------|
| Full | 1 → 2 → 3 → 4 → 5 → 6 → 7 |
| Quick Watch | 1 → 2 → 7 |
| Low Energy | 2 → 7 |
| Quiz Focus | 3 → 4 → 5 → 7 |
| Card Sprint | 1 → 7 (topics only, skip watch) |

---

## Claude Integration Notes

- Model: `gemini-3.1-pro-preview`
- Responses for steps 3–6 are streamed via SSE/WebSocket
- Each step uses a dedicated system prompt template with session context injected (topics, prior answers, gap analysis)
- Tool calls (Anki) are handled server-side; Claude is given tool results, not direct deck access
- Semantic scoring for quiz answers is done via a dedicated Claude prompt, not keyword matching

---

## Persistence (SQLite)

SQLite is used for full-fidelity session persistence. The DB lives at `~/.buddy/buddy.db` (configurable via env var). All session data is written progressively as steps complete, so a session can always be resumed from exactly where it was left.

### Strategy: Write-on-transition

Data is persisted at each step boundary, not continuously. When a step completes (e.g., quiz answers submitted), the backend flushes the full session state to SQLite before triggering the next step. This keeps writes predictable and avoids partial state corruption.

### Schema

```sql
-- Core session record
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,       -- UUID
    created_at      TEXT NOT NULL,          -- ISO8601 datetime
    updated_at      TEXT NOT NULL,
    title           TEXT,                   -- User-editable label, e.g. "TCP/IP deep dive"
    preset          TEXT NOT NULL,          -- full | quick | low_energy | quiz | card_sprint
    active_steps    TEXT NOT NULL,          -- JSON array of enabled step numbers, e.g. [1,2,3,4,5,6,7]
    current_step    INTEGER NOT NULL,       -- 1–7
    status          TEXT NOT NULL,          -- in_progress | completed | abandoned
    target_deck     TEXT                    -- Anki deck name to write cards to
);

-- Topics submitted at step 1
CREATE TABLE session_topics (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic           TEXT NOT NULL,
    position        INTEGER NOT NULL        -- Preserves input order
);

-- Priming questions generated at step 1
CREATE TABLE priming_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic_id        TEXT REFERENCES session_topics(id),
    question_text   TEXT NOT NULL,
    position        INTEGER NOT NULL
);

-- Quiz questions generated at step 3
CREATE TABLE quiz_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic_id        TEXT REFERENCES session_topics(id),
    question_text   TEXT NOT NULL,
    position        INTEGER NOT NULL
);

-- User answers to quiz questions (step 3)
CREATE TABLE quiz_answers (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    question_id     TEXT NOT NULL REFERENCES quiz_questions(id),
    answer_text     TEXT NOT NULL,
    score           TEXT NOT NULL,          -- strong | partial | missing
    feedback        TEXT NOT NULL           -- Buddy's per-answer feedback
);

-- Gap analysis results (step 4)
CREATE TABLE gap_analysis (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id) UNIQUE,
    strong_areas    TEXT NOT NULL,          -- JSON array of strings
    weak_areas      TEXT NOT NULL,          -- JSON array of strings
    missing_areas   TEXT NOT NULL           -- JSON array of strings
);

-- Elaboration exchanges (step 5) — stored as ordered conversation turns
CREATE TABLE elaboration_turns (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    role            TEXT NOT NULL,          -- buddy | user
    content         TEXT NOT NULL,
    position        INTEGER NOT NULL
);

-- Application challenge and user response (step 6)
CREATE TABLE application (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id) UNIQUE,
    challenge_text  TEXT NOT NULL,
    user_response   TEXT,                   -- NULL if skipped
    buddy_feedback  TEXT                    -- NULL if skipped
);

-- Card proposals generated at step 7
CREATE TABLE card_proposals (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic_id        TEXT REFERENCES session_topics(id),
    front           TEXT NOT NULL,
    back            TEXT NOT NULL,
    card_type       TEXT NOT NULL,          -- basic | cloze | reversed
    tags            TEXT NOT NULL,          -- JSON array of strings
    is_gap_card     INTEGER NOT NULL,       -- 0 | 1 (SQLite boolean)
    duplicate_warning INTEGER NOT NULL,     -- 0 | 1
    approved        INTEGER NOT NULL DEFAULT 0,
    committed       INTEGER NOT NULL DEFAULT 0,  -- 1 = added to Anki
    anki_note_id    INTEGER                 -- Anki note ID after commit, NULL until then
);
```

### Indexes

```sql
CREATE INDEX idx_session_topics_session ON session_topics(session_id);
CREATE INDEX idx_quiz_questions_session ON quiz_questions(session_id);
CREATE INDEX idx_quiz_answers_session   ON quiz_answers(session_id);
CREATE INDEX idx_card_proposals_session ON card_proposals(session_id);
CREATE INDEX idx_sessions_status        ON sessions(status);
CREATE INDEX idx_sessions_created       ON sessions(created_at);
```

### Resume Logic

On app start, the frontend calls `GET /sessions?status=in_progress` to check for an incomplete session. If one exists, the user is prompted to resume or abandon it. Resuming loads the full session state and renders the UI at `current_step`.

### Session History

`GET /sessions?status=completed&limit=20` returns a summary list for the history view. Each entry shows: title, created date, topics, weak areas, and how many cards were committed. The full session detail (all tables) is loadable on demand.

### Backend File Layout Addition

```
buddy/
├── db/
│   ├── database.py      # SQLite connection, init, migrations
│   ├── repository.py    # CRUD operations per table
│   └── migrations/      # Versioned schema files
│       └── 001_initial.sql
```

---

## Key Dependencies

| Dependency | Purpose |
|-----------|---------|
| FastAPI | Backend framework |
| httpx | Async HTTP client (AnkiConnect, Claude API) |
| Pydantic | Data models and validation |
| React | Frontend framework |
| Zustand or Redux | Frontend session state |
| AnkiConnect | Local Anki API bridge |
| Google Generative AI Python SDK | Gemini API client |
| aiosqlite | Async SQLite driver for Python |

---

## Open Questions / Future Considerations

- **Auth**: Currently single-user local tool. Multi-user hosting would require moving from SQLite to Postgres and adding auth middleware.
- **Anki deck format**: Which deck does Buddy write to by default? Should be configurable per session (stored in `sessions.target_deck`).
- **DB migrations**: Use a lightweight migration runner (e.g., `yoyo-migrations`) to handle schema changes as Buddy evolves.
- **Concept dependency graph**: Cross-session awareness (e.g., "you haven't studied IP but are watching TCP") — deferred to v2. Could be derived from the SQLite history.
- **Audio summary mode** (from Turbo AI): low-energy review via generated podcast — deferred to v2.