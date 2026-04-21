Buddy — Implementation Strategy
Guiding Principles
Build the thinnest possible vertical slice first, then expand. At every phase, something should be runnable and testable end-to-end. Never build a full layer in isolation before connecting it to the rest of the system.

Phase 0 — Project Scaffold (Day 1)
Get the repo structure, tooling, and dev environment in place before writing any feature code. This phase should take a few hours.
Backend

Initialize a Python project with uv or poetry for dependency management
Set up FastAPI app with a single health check route (GET /health)
Configure aiosqlite connection and run the initial schema migration (001_initial.sql)
Add python-dotenv for env var management (Gemini API key, DB path, AnkiConnect URL)
Set up pytest with pytest-asyncio for async test support

Frontend

Scaffold with Vite + React + TypeScript
Add React Router for page routing (session list, session detail)
Add Zustand for session state
Add a basic API client module (src/api/client.ts) — just a thin wrapper around fetch
Confirm frontend can hit GET /health and render a response

Shared

Git repo with a .env.example listing all required env vars
README.md with setup instructions (Anki + AnkiConnect prerequisite, Python version, Node version)
docker-compose.yml is optional at this stage but useful if you want the backend containerized later

Exit criteria: Backend starts, DB initializes, frontend loads in browser, health check succeeds.

Phase 1 — Session Lifecycle (No AI)
Build the full session state machine without any Gemini calls. This lets you validate the DB schema, API contracts, and frontend routing before AI complexity enters the picture.
Backend

Implement all session CRUD: POST /sessions, GET /sessions, GET /sessions/{id}
Implement the step transition endpoints as stubs — they accept the right request shape and advance current_step in the DB, but return hardcoded placeholder data instead of calling Gemini
Implement POST /sessions/{id}/topics, /watched, /answers, /elaboration/close, /application, /cards/commit — all as stubs
Implement the SQLite repository layer (db/repository.py) — one function per DB operation, no business logic
Implement the session state machine (session/manager.py) — validates current step before any transition, returns 409 if out of order

Frontend

Build the Session Shell: step progress indicator, current step router
Build the session list / history page
Build Step 1 UI: topic input, submit button, display placeholder priming questions
Build Step 2 UI: priming questions displayed, "I've watched" button
Build Step 3 UI: quiz question display, free-text input, progress through questions
Wire all frontend step transitions to the stub API endpoints

Testing

Unit test the session state machine: valid transitions pass, invalid ones return 409
Unit test the repository layer: write, read, update for each table
Integration test the full step sequence against a test SQLite DB: create session → submit topics → signal watched → submit answers → close elaboration → submit application → commit cards
Frontend: manually walk through the full flow using stub data to confirm UI routing is correct

Exit criteria: You can walk through all 7 steps in the browser against stub backend data. DB reflects correct state at each step. No AI calls yet.

Phase 2 — AnkiConnect Integration
Build and validate the Anki toolchain before connecting it to Gemini. Anki needs to be open during development.
Backend

Implement tools/anki.py with all five tools: anki_search, anki_find_gaps, anki_get_card_maturity, anki_check_duplicate, anki_add_card
Add a connection check at startup: if AnkiConnect is unreachable, log a warning but don't crash (Anki being closed is a recoverable state)
Implement POST /sessions/{id}/cards/commit for real: iterate approved card proposals, call anki_check_duplicate, then anki_add_card, persist anki_note_id and committed flag

Testing

Unit test each Anki tool with a mock AnkiConnect HTTP server (use respx or pytest-httpx to mock responses)
Manual integration test against real Anki: add a card, confirm it appears in the deck, confirm duplicate detection works
Test the commit endpoint: approve a subset of card proposals, commit, verify correct cards appear in Anki and committed flags are set in DB

Exit criteria: Cards can be written to Anki from the backend. Duplicate detection works. Anki being closed returns a clean error.

Phase 3 — Gemini Integration (Step by Step)
Introduce Gemini one step at a time, replacing stubs. Don't wire all steps at once — you want to be able to isolate failures.
Backend — Gemini client

Implement claude/client.py (despite the folder name from the design doc, this wraps the Gemini API)
Support both one-shot calls (steps 1, 3, 4, 6, 7) and streaming (step 5)
Implement prompt templates for each step under claude/prompts/

Step order to implement
Step 3 first (Recall Quiz generation) — simplest prompt: given topics, generate quiz questions. Easy to evaluate output quality manually. Replace the step 3 stub with a real Gemini call.
Step 4 next (Gap Analysis) — takes quiz answers as input, returns structured scores. Implement semantic scoring here. Validate that the JSON output shape matches GapAnalysis model. Use Pydantic to parse and validate Gemini's response.
Step 1 (Priming Questions) — now that you know what gap analysis looks like, priming can query the Anki toolchain for existing card coverage and generate questions targeted at gaps. This is the first step that combines Gemini + Anki tools.
Step 7 (Card Proposals) — most complex prompt. Takes topics + gap analysis + elaboration turns as context, calls anki_check_duplicate per proposed card, returns structured card list. Build the card proposal UI in the frontend to support approve/edit/remove at this point.
Step 6 (Application Challenge) — straightforward: given weak areas, generate a challenge. One-shot call, no tools needed.
Step 5 last (Elaboration WebSocket) — most complex to implement. See below.
Step 5 — WebSocket elaboration

Implement WS /sessions/{id}/elaboration in FastAPI using websockets
On connect: load session, validate step is 5, send last Buddy message (for reconnect support)
On user message: append to elaboration_turns, call Gemini with full conversation history, stream response back token by token, persist completed Buddy turn
Implement suggest_close logic: after each Buddy response, call a lightweight Gemini classification prompt ("is this topic sufficiently covered?") to set the flag
Implement POST /elaboration/close: mark step complete, advance to step 6, send close WebSocket message

Frontend additions

Step 5: WebSocket client hook (useElaboration), chat-style message display, streaming text rendering, "Move on →" button appears when suggest_close is true
Step 7: Card proposal list with approve/edit/remove per card, tag editor, "Add to Anki" button

Testing

Unit test each prompt template: given known input, assert output parses correctly into the expected Pydantic model
Test suggest_close classification: construct elaboration turns where coverage is clearly complete vs. clearly incomplete, assert flag is set correctly
Test WebSocket reconnect: drop connection mid-conversation, reconnect, confirm last message is resent and conversation continues cleanly
Manual end-to-end: run a real study session on a topic you know well, evaluate output quality at each step

Exit criteria: Full session loop works end-to-end with real Gemini calls. Cards land in Anki. WebSocket elaboration is stable.

Phase 4 — Session Resume + History
Now that sessions are fully functional, add the resume and history flows.
Backend

GET /sessions?status=in_progress — return incomplete sessions for resume prompt
GET /sessions?status=completed&limit=20 — return session summaries for history view
Ensure GET /sessions/{id} returns enough data to fully reconstruct UI state at any step

Frontend

On app load: check for in-progress sessions, show resume/abandon prompt if found
Session history page: list completed sessions with topic, date, weak areas, cards committed
Session detail view: read-only replay of a completed session (priming questions, quiz answers with scores, gap analysis, elaboration turns, cards generated)

Testing

Test resume: start a session, kill the backend, restart, confirm session resumes at correct step with correct data
Test history: complete several sessions, confirm list is correct and detail view renders properly

Exit criteria: Sessions survive backend restarts. History is browsable and readable.

Phase 5 — Preset System + Step Skipping
Backend

On POST /sessions, accept preset and optional active_steps override
Session state machine respects active_steps: skipped steps are automatically advanced through without triggering their logic
Validate preset combinations are coherent (e.g., Quiz Focus requires at least one prior quiz answer — surface a warning if the deck has none)

Frontend

Preset selector on session creation screen
Per-step skip toggle in the session shell (visible but not intrusive)
Skipped steps are shown as greyed out in the progress indicator, not invisible

Testing

Test each preset: confirm correct steps are executed and skipped steps don't fire Gemini calls
Test mid-session step skip: user skips elaboration partway through, confirm advance to application works cleanly

Exit criteria: All five presets work correctly. Individual step skipping works during a live session.

Phase 6 — Polish + Hardening
Error handling

Gemini API errors: surface clearly in UI, allow retry without losing session state
AnkiConnect unreachable: show persistent warning banner, disable card commit until resolved
WebSocket drops: auto-reconnect with exponential backoff, show reconnecting indicator

Edge cases

Empty deck (first-time user): priming and gap analysis should degrade gracefully with no Anki data
Gemini returns malformed JSON: retry with a stricter prompt before surfacing an error
All quiz answers scored "strong": elaboration should acknowledge this and suggest_close immediately

Performance

Priming question generation and card proposal generation can be slow for large topic lists — add a loading state with progress indication
Cache AnkiConnect responses within a session (deck doesn't change during a session)

Testing

Run a full session with Anki closed — confirm clean error states throughout
Run a full session with the Gemini API key invalid — confirm errors are surfaced without data loss
Load test the WebSocket with rapid message sends

Exit criteria: The app handles failure modes gracefully without losing session data. Ready for daily use.

Layering Summary
Phase 0 — Scaffold
Phase 1 — Session state machine + DB + Frontend routing (no AI)
Phase 2 — AnkiConnect tools
Phase 3 — Gemini, one step at a time (3 → 4 → 1 → 7 → 6 → 5)
Phase 4 — Resume + History
Phase 5 — Presets + Step skipping
Phase 6 — Polish + Hardening
The key discipline is Phase 1 before Phase 3. Getting the state machine and DB right without AI in the picture means that when Gemini calls fail or produce bad output, you know the problem is in the AI layer, not the plumbing.