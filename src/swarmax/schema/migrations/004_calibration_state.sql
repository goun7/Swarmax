-- D1 (deep-scan 2026-09-15): durable per-agent calibration state (§3.3).
-- Previously the 14-day calibration window lived only in FleetApd memory, so a
-- process restart silently re-opened every production agent's window. Now the
-- window is persisted at first sight and survives restarts; the console reads
-- this table to show operators who is still calibrating (suppression visible).
CREATE TABLE IF NOT EXISTS agent_calibration (
    agent_id          VARCHAR(128) PRIMARY KEY,
    calibration_until TIMESTAMP NOT NULL,   -- opened_at + 14 days
    closed            INTEGER NOT NULL DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (4, 'D1: durable per-agent calibration state (§3.3), console-visible');
