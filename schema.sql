PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, display_name TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT UNIQUE, source_file TEXT,
 section TEXT NOT NULL, subsection TEXT NOT NULL, stem TEXT NOT NULL,
 option_a TEXT NOT NULL, option_b TEXT NOT NULL, option_c TEXT NOT NULL,
 option_d TEXT NOT NULL, option_e TEXT, correct_option TEXT NOT NULL,
 correct_option_text TEXT, explanation TEXT NOT NULL, provenance TEXT,
 review_status TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_questions_taxonomy ON questions(section, subsection);
CREATE TABLE IF NOT EXISTS attempts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
 session_token TEXT NOT NULL, selected_option TEXT NOT NULL, is_correct INTEGER NOT NULL,
 elapsed_ms INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(user_id, created_at);
CREATE TABLE IF NOT EXISTS study_sessions (
 token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 section TEXT, subsection TEXT, requested_count INTEGER NOT NULL,
 question_ids TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at TEXT
);
CREATE TABLE IF NOT EXISTS flashcard_templates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT UNIQUE, section TEXT NOT NULL,
 subsection TEXT NOT NULL, front TEXT NOT NULL, back TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_progress (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 card_id INTEGER NOT NULL REFERENCES flashcard_templates(id) ON DELETE CASCADE,
 repetitions INTEGER NOT NULL DEFAULT 0, interval_days INTEGER NOT NULL DEFAULT 0,
 ease_factor REAL NOT NULL DEFAULT 2.5, due_date TEXT NOT NULL,
 last_reviewed_at TEXT, PRIMARY KEY(user_id, card_id)
);
CREATE TABLE IF NOT EXISTS bookmarks (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id, question_id)
);
