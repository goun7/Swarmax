-- v4.2.0 (2026-09-15): console multi-user auth (§8 L2 two-person ops model) and
-- v1.1 attribution suggestions (§9.2, E14/E15).
--
-- console_users: scrypt password hashes (OWASP ASVS 2.4 shape salt$n$r$p$hash),
--   role 'admin' (resolve/seal/user mgmt) or 'viewer' (read-only).
-- console_sessions: server-side sessions; only SHA-256(token) is stored, tokens
--   themselves never hit disk (rotation on login, 12h expiry, per-session CSRF).
-- attribution_suggestions: per-alarm "responsible agent + critical step" hint
--   (Who&When-aligned heuristic, SOTA-calibrated human-confirm gate §9.2 E15).
CREATE TABLE IF NOT EXISTS console_users (
    user_id    VARCHAR(64)  PRIMARY KEY,
    username   VARCHAR(64)  NOT NULL UNIQUE,
    pw_hash    VARCHAR(256) NOT NULL,
    role       VARCHAR(16)  NOT NULL DEFAULT 'viewer'
               CHECK (role IN ('admin', 'viewer')),
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS console_sessions (
    token_hash VARCHAR(64)  PRIMARY KEY,      -- sha256 hex of the bearer token
    user_id    VARCHAR(64)  NOT NULL REFERENCES console_users(user_id),
    csrf_token VARCHAR(64)  NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP    NOT NULL
);

CREATE TABLE IF NOT EXISTS attribution_suggestions (
    alarm_id           VARCHAR(64) PRIMARY KEY REFERENCES alarms(alarm_id),
    suggested_agent_id VARCHAR(128) NOT NULL,
    suggested_step     VARCHAR(256) NOT NULL,
    confidence         REAL         NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    method             VARCHAR(128) NOT NULL,
    note               VARCHAR(512),
    confirmed          INTEGER,               -- NULL=pending, 1=accepted, 0=rejected
    confirmed_by       VARCHAR(64),
    confirmed_at       TIMESTAMP,
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON console_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_attribution_confirmed ON attribution_suggestions (confirmed);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (5, 'console auth (users/sessions/CSRF) + v1.1 attribution suggestions (§8, §9.2)');
