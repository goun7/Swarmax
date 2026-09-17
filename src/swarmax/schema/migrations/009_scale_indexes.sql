-- v4.3.1 (2026-09-16): WS-C F5 hardening — scale gate found the gap: console
-- time-window queries (24h activity, hourly rollups, SLA windows) scanned the
-- full 1M-row event table because ts is only the SECOND column of
-- idx_task_agent_time. Dedicated time indexes + a covering index bring the
-- §10.1 warm-tier contract (query < 200 ms) within reach at 1M events.
CREATE INDEX IF NOT EXISTS idx_task_ts ON agent_task_events (ts);
CREATE INDEX IF NOT EXISTS idx_guard_ts ON guard_events (ts);

-- status+ts composite for the error-rate fact window scans
CREATE INDEX IF NOT EXISTS idx_task_agent_status_ts
    ON agent_task_events (agent_id, status, ts);

-- covering index for the per-agent aggregates (all columns the console sums;
-- keeps the per-agent table + agent-page scalars inside the index itself)
CREATE INDEX IF NOT EXISTS idx_task_agent_cover
    ON agent_task_events (agent_id, ts, cost_usd, status, input_tokens,
                          output_tokens);

INSERT INTO schema_version(version, note) VALUES (9, 'F5 scale indexes: ts range + agent/status/ts + covering (200ms gate)');
