-- SWARMAX F1/F2 extensions: persisted alarms (console/report SLA queue) and
-- evidence seals (F2 Ed25519 + Merkle, paper §12.1/§14 R1).
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id       VARCHAR(64) PRIMARY KEY,
    agent_id       VARCHAR(128) NOT NULL,
    task_id        VARCHAR(64),
    signal         VARCHAR(64)  NOT NULL,
    event_type     VARCHAR(16)  NOT NULL,   -- escalation | report_item
    reason         VARCHAR(32)  NOT NULL,
    severity       VARCHAR(16)  NOT NULL,
    sla_hours      REAL         NOT NULL,
    sla_deadline   TIMESTAMP    NOT NULL,
    trigger_value  REAL,
    protection     TEXT,
    status         VARCHAR(16)  DEFAULT 'open',   -- open | resolved
    created_at     TIMESTAMP    NOT NULL,
    resolved_by    VARCHAR(64),
    resolved_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alarms_open ON alarms (status, severity, created_at);

CREATE TABLE IF NOT EXISTS evidence_seals (
    seal_id             VARCHAR(64) PRIMARY KEY,
    root_hash           CHAR(64)    NOT NULL,   -- Merkle root over payload_hash chain
    covers_through_seq  INTEGER     NOT NULL,
    public_key          BLOB        NOT NULL,   -- 32-byte Ed25519 public key
    ed25519_sig         BLOB        NOT NULL,   -- 64-byte signature (root || covers)
    sealed_at           TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (3, 'F1/F2: alarms SLA queue + evidence_seals (Ed25519/Merkle)');
