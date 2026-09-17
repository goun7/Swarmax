-- SWARMAX v1 SQLite schema — paper §12.1 (verbatim) + append-only enforcement + schema versioning.
-- Production schema = this file + schema/migrations/002_f0_extensions.sql (paper §14, R12–R14).

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS fleet_agents (
    agent_id    VARCHAR(128) PRIMARY KEY,
    fleet_name  VARCHAR(64)  NOT NULL,
    role        VARCHAR(32)  NOT NULL,           -- planner|worker|reviewer|executor
    framework   VARCHAR(32)  DEFAULT 'custom',
    agent_version VARCHAR(64),
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(16)  DEFAULT 'active'    -- active|paused|quarantined
);

CREATE TABLE IF NOT EXISTS agent_task_events (
    event_id     VARCHAR(64) PRIMARY KEY,
    agent_id     VARCHAR(128) NOT NULL REFERENCES fleet_agents(agent_id),
    task_id      VARCHAR(64)  NOT NULL,
    session_id   VARCHAR(64),
    model_name   VARCHAR(64)  NOT NULL,
    input_tokens INTEGER      NOT NULL,
    output_tokens INTEGER     NOT NULL,
    cost_usd     NUMERIC(12,6) NOT NULL,
    latency_ms   INTEGER      NOT NULL,
    error_class  VARCHAR(32),
    status       VARCHAR(16)  NOT NULL,
    synthetic    BOOLEAN      DEFAULT 0,          -- sentez test verisi işareti (§7.3)
    ts           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_agent_time ON agent_task_events (agent_id, ts);

CREATE TABLE IF NOT EXISTS agent_drift_baselines (
    agent_id           VARCHAR(128) PRIMARY KEY,
    tool_distribution_json TEXT    NOT NULL,
    mean_cost_usd      NUMERIC(12,6) NOT NULL,
    mad_cost_usd       NUMERIC(12,6) NOT NULL,   -- EWMA σ yerine MAD (§3.2-4)
    p95_latency_ms     INTEGER   NOT NULL,
    ewma_mu            NUMERIC(12,6),
    ewma_sigma2        NUMERIC(12,6),
    calibration_until  TIMESTAMP,                 -- §3.3 kalibrasyon penceresi
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hitl_escalations (
    escalation_id  VARCHAR(64) PRIMARY KEY,
    agent_id       VARCHAR(128) NOT NULL REFERENCES fleet_agents(agent_id),
    task_id        VARCHAR(64)  NOT NULL,
    trigger_metric VARCHAR(64)  NOT NULL,
    trigger_value  DOUBLE PRECISION NOT NULL,
    reason         VARCHAR(32)  NOT NULL,          -- budget|permission|quality|unknown|drift|system_health
    evidence_ref   VARCHAR(128) NOT NULL,
    sla_deadline   TIMESTAMP    NOT NULL,
    status         VARCHAR(16)  DEFAULT 'open',
    resolved_by    VARCHAR(64),
    resolved_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hitl_sla ON hitl_escalations (status, sla_deadline);

CREATE TABLE IF NOT EXISTS evidence_ledger (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,  -- append-only; UPDATE/DELETE tetikleyicilerle yasaklanır
    event_type    VARCHAR(32) NOT NULL,
    payload_hash  CHAR(64)    NOT NULL,               -- SHA-256(payload)
    prev_hash     CHAR(64)    NOT NULL,               -- hash-chain
    ed25519_sig   BLOB        NOT NULL,               -- F2'de gerçek imzayla dolar (paper §7.1)
    created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- Append-only enforcement (§12.1; verified by tests/test_schema.py)
CREATE TRIGGER IF NOT EXISTS trg_evidence_ledger_no_update
BEFORE UPDATE ON evidence_ledger
BEGIN
    SELECT RAISE(ABORT, 'evidence_ledger is append-only: UPDATE forbidden');
END;

CREATE TRIGGER IF NOT EXISTS trg_evidence_ledger_no_delete
BEFORE DELETE ON evidence_ledger
BEGIN
    SELECT RAISE(ABORT, 'evidence_ledger is append-only: DELETE forbidden');
END;

-- Schema versioning (F0 schema-change test; paper §7.1)
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    note        TEXT,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO schema_version (version, note) VALUES (1, 'base §12.1 DDL + append-only triggers');
