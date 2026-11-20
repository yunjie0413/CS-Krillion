-- D1 schema. Apply locally:  npm run db:local
-- and in production:         npx wrangler d1 execute cs-krillion --remote --file schema.sql
CREATE TABLE IF NOT EXISTS rounds (
  run_id      TEXT    NOT NULL,
  day         TEXT    NOT NULL,
  round       INTEGER NOT NULL,
  prompt_id   TEXT    NOT NULL,
  started_at  INTEGER NOT NULL,
  answer_key  TEXT,
  points      INTEGER,
  tier        TEXT,
  finished_at INTEGER,
  guesses     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (run_id, day, round)
);

-- How often each correct answer has been given, across all days a prompt was played.
CREATE TABLE IF NOT EXISTS answer_counts (
  prompt_id  TEXT    NOT NULL,
  entity_key TEXT    NOT NULL,
  n          INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (prompt_id, entity_key)
);
