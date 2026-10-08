CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    submitted_by TEXT NOT NULL DEFAULT 'anonymous',
    ups INT NOT NULL DEFAULT 0 CHECK (ups >= 0),
    downs INT NOT NULL DEFAULT 0 CHECK (downs >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());

-- parent_id points at another row in this same table. That self-reference is
-- what makes the thread a tree, and what makes reading it back a recursive
-- query rather than a join.
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    link_id INT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    parent_id INT REFERENCES comments(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT 'anonymous',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE INDEX IF NOT EXISTS links_created ON links (created_at DESC);
CREATE INDEX IF NOT EXISTS comments_link ON comments (link_id, parent_id, id);
