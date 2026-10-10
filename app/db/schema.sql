CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    source_url TEXT,
    body_markdown TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id),
    platform TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'rejected', 'published')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY,
    variant_id INTEGER NOT NULL REFERENCES variants(id),
    scheduled_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publishes (
    id INTEGER PRIMARY KEY,
    variant_id INTEGER NOT NULL REFERENCES variants(id),
    slot_id INTEGER NOT NULL REFERENCES slots(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'succeeded', 'failed', 'uncertain')),
    started_at TEXT,
    platform_message_id TEXT
);

CREATE TABLE IF NOT EXISTS publish_attempts (
    id INTEGER PRIMARY KEY,
    publish_id INTEGER NOT NULL REFERENCES publishes(id),
    result TEXT NOT NULL,
    error TEXT,
    attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_slots_scheduled_at ON slots(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_variants_post_id ON variants(post_id);
CREATE INDEX IF NOT EXISTS idx_attempts_publish_id ON publish_attempts(publish_id);

-- The same variant cannot have two slots at the same time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_slots_variant_time
    ON slots(variant_id, scheduled_at);