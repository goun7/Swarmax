-- v4.2.1 (2026-09-16): WS-C — SSO identity links and tenant support (§8).
-- sso_links: one console identity per (issuer, subject) pair; created/linked by
-- an admin, or auto-provisioned as 'viewer' when SWARMAX_SSO_AUTOJOIN=1.
CREATE TABLE IF NOT EXISTS sso_links (
    link_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    issuer         VARCHAR(256) NOT NULL,
    subject        VARCHAR(256) NOT NULL,
    username       VARCHAR(64)  NOT NULL UNIQUE,
    role           VARCHAR(16)  NOT NULL DEFAULT 'viewer',  -- admin|viewer
    email          VARCHAR(256),
    tenant_id      VARCHAR(64)  REFERENCES tenants(tenant_id),
    created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (issuer, subject)
);

-- tenants: fleet namespaces. v1 keeps tenant_id NULL = 'default' tenant so
-- existing stores upgrade in place; alarms/events gain the column for the
-- partitioned deployment model (§8 multi-team).
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id      VARCHAR(64)  PRIMARY KEY,
    display_name   VARCHAR(128) NOT NULL,
    sso_domain     VARCHAR(256),             -- email-domain → tenant mapping
    created_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO tenants (tenant_id, display_name)
VALUES ('default', 'Default Fleet'), ('alpha', 'Alpha Team'), ('beta', 'Beta Team');

ALTER TABLE fleet_agents ADD COLUMN tenant_id VARCHAR(64) REFERENCES tenants(tenant_id);
ALTER TABLE alarms ADD COLUMN tenant_id VARCHAR(64) REFERENCES tenants(tenant_id);

CREATE INDEX IF NOT EXISTS idx_agents_tenant ON fleet_agents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_alarms_tenant ON alarms (tenant_id);

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (6, 'SSO identity links + tenant columns (§8 multi-user/multi-team)');
