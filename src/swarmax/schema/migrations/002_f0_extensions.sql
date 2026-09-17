-- SWARMAX F0 extensions (paper §14: R12, R13, R14)
-- R12: metamorphic oracle inputs + retry/ttft fields
ALTER TABLE agent_task_events ADD COLUMN task_template TEXT;
ALTER TABLE agent_task_events ADD COLUMN end_state_json TEXT;
ALTER TABLE agent_task_events ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE agent_task_events ADD COLUMN ttft_s REAL;

-- R14: ticket aging needs an open-time
ALTER TABLE hitl_escalations ADD COLUMN created_at TIMESTAMP;

-- R13: §4.1 guard-plane events get first-class storage
CREATE TABLE IF NOT EXISTS guard_events (
    event_id       VARCHAR(64) PRIMARY KEY,
    agent_id       VARCHAR(128) NOT NULL,
    task_id        VARCHAR(64),
    event_type     VARCHAR(32) NOT NULL,   -- tool_call | permission_decision | mask_event
    decision       VARCHAR(16),            -- allow | deny (permission_decision)
    tool_name      VARCHAR(128),
    arguments_json TEXT,                   -- §3.2-3 loop hash girdisi (maskeden sonra)
    synthetic      BOOLEAN DEFAULT 0,
    ts             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_guard_agent_time ON guard_events (agent_id, ts);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (2, 'F0 extensions: metamorphic fields, retry/ttft, guard_events, escalation created_at');
