-- Core session record
CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    title           TEXT,
    preset          TEXT NOT NULL,
    active_steps    TEXT NOT NULL,
    current_step    INTEGER NOT NULL,
    status          TEXT NOT NULL,
    target_deck     TEXT
);

CREATE TABLE IF NOT EXISTS session_topics (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    topic       TEXT NOT NULL,
    position    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS priming_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic_id        TEXT REFERENCES session_topics(id),
    question_text   TEXT NOT NULL,
    position        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic_id        TEXT REFERENCES session_topics(id),
    question_text   TEXT NOT NULL,
    position        INTEGER NOT NULL,
    question_type   TEXT NOT NULL DEFAULT 'short_answer',
    options         TEXT,
    difficulty      TEXT NOT NULL DEFAULT 'medium',
    answer_key      TEXT
);

CREATE TABLE IF NOT EXISTS quiz_answers (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    question_id TEXT NOT NULL REFERENCES quiz_questions(id),
    answer_text TEXT NOT NULL,
    score       TEXT NOT NULL,
    feedback    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gap_analysis (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id) UNIQUE,
    strong_areas  TEXT NOT NULL,
    weak_areas    TEXT NOT NULL,
    missing_areas TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS elaboration_turns (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    position    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS application (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id) UNIQUE,
    challenge_text  TEXT NOT NULL,
    user_response   TEXT,
    buddy_feedback  TEXT
);

CREATE TABLE IF NOT EXISTS card_proposals (
    id                TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL REFERENCES sessions(id),
    topic_id          TEXT REFERENCES session_topics(id),
    front             TEXT NOT NULL,
    back              TEXT NOT NULL,
    card_type         TEXT NOT NULL,
    tags              TEXT NOT NULL,
    is_gap_card       INTEGER NOT NULL,
    duplicate_warning INTEGER NOT NULL,
    approved          INTEGER NOT NULL DEFAULT 0,
    committed         INTEGER NOT NULL DEFAULT 0,
    anki_note_id      INTEGER
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_session_topics_session ON session_topics(session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_session ON quiz_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_answers_session   ON quiz_answers(session_id);
CREATE INDEX IF NOT EXISTS idx_card_proposals_session ON card_proposals(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status        ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created       ON sessions(created_at);
