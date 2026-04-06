CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    recovery_contact VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS recovery_contact VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS paid BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS golfers (
    id SERIAL PRIMARY KEY,
    espn_id VARCHAR(20),
    name VARCHAR(100) NOT NULL,
    tier INTEGER NOT NULL CHECK (tier >= 1 AND tier <= 6),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS picks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    golfer_id INTEGER NOT NULL REFERENCES golfers(id),
    tier INTEGER NOT NULL CHECK (tier >= 1 AND tier <= 6),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, tier)
);

CREATE TABLE IF NOT EXISTS golfer_scores (
    golfer_id INTEGER PRIMARY KEY REFERENCES golfers(id),
    round_1 INTEGER,
    round_2 INTEGER,
    round_3 INTEGER,
    round_4 INTEGER,
    total_strokes INTEGER,
    to_par VARCHAR(10),
    status VARCHAR(10) DEFAULT 'active',
    position VARCHAR(10),
    thru VARCHAR(10),
    current_round INTEGER DEFAULT 0,
    current_round_par TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tournament_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    status VARCHAR(20) DEFAULT 'pre',
    current_round INTEGER DEFAULT 0,
    last_poll_at TIMESTAMP,
    tournament_name VARCHAR(100) DEFAULT 'The Masters 2026',
    espn_event_id VARCHAR(20)
);

INSERT INTO tournament_state (id) VALUES (1) ON CONFLICT DO NOTHING;

ALTER TABLE golfers ADD COLUMN IF NOT EXISTS dg_name VARCHAR(200);

CREATE TABLE IF NOT EXISTS golfer_projections (
    id SERIAL PRIMARY KEY,
    golfer_id INTEGER REFERENCES golfers(id),
    projected_to_par NUMERIC,
    mc_probability NUMERIC,
    win_probability NUMERIC,
    snapshot_time TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_golfer_proj_time ON golfer_projections(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_golfer_proj_golfer ON golfer_projections(golfer_id);

CREATE TABLE IF NOT EXISTS team_projections (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    projected_total NUMERIC,
    snapshot_time TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_team_proj_time ON team_projections(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_team_proj_user ON team_projections(user_id);
