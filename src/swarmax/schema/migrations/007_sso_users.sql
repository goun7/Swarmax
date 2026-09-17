-- v4.2.1 (2026-09-16): WS-C fix — SSO identities become real console_users rows
-- (sessions FK to console_users; sso_links maps identity → username).
-- Auto-provisioned identities get a NULL password hash (no password login).
CREATE TABLE IF NOT EXISTS sso_users_backfill_done (
    done INTEGER PRIMARY KEY CHECK (done = 1)
);

INSERT INTO console_users (user_id, username, pw_hash, role)
SELECT 'sso-' || link_id, l.username,
       COALESCE((SELECT pw_hash FROM console_users u WHERE u.username = l.username), ''),
       l.role
FROM sso_links l
WHERE NOT EXISTS (SELECT 1 FROM console_users u WHERE u.username = l.username);

INSERT OR IGNORE INTO sso_users_backfill_done (done) VALUES (1);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (7, 'SSO identities as console_users (session FK integrity)');
