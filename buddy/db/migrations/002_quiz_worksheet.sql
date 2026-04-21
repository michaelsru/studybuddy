-- Migration 002: quiz worksheet columns
-- SQLite doesn't support IF NOT EXISTS on ALTER TABLE.
-- Run these idempotently by catching errors in database.py.
ALTER TABLE quiz_questions ADD COLUMN question_type TEXT NOT NULL DEFAULT 'short_answer';
ALTER TABLE quiz_questions ADD COLUMN options       TEXT;
ALTER TABLE quiz_questions ADD COLUMN difficulty    TEXT NOT NULL DEFAULT 'medium';
ALTER TABLE quiz_questions ADD COLUMN answer_key    TEXT;
