-- v4.3.0 (2026-09-16): WS-B2 — GDPR/AI-Act erase path (gap B2 → code).
-- data_subjects: PII payloads are AEAD-encrypted (ChaCha20-Poly1305, RFC 8439)
-- under a per-subject DEK derived via HKDF-SHA256 from the deployment master
-- key. Erasure (Art. 17 / Md. 17) is crypto-shredding: tombstone the row and
-- revoke the DEK — append-only evidence is never rewritten.
CREATE TABLE IF NOT EXISTS data_subjects (
    subject_id     VARCHAR(64)  PRIMARY KEY,
    display_name   VARCHAR(128) NOT NULL,
    ciphertext_b64 TEXT         NOT NULL,
    nonce_b64      TEXT         NOT NULL,
    key_version    INTEGER      NOT NULL DEFAULT 1,
    registered_at  TEXT         NOT NULL,
    erased_at      TEXT
);

-- subject_keys: append-only key-custody history. Erasure revokes (revoked_at
-- + wrapped_key=NULL); rows are never deleted, so auditors see full custody.
CREATE TABLE IF NOT EXISTS subject_keys (
    custody_id   INTEGER      PRIMARY KEY AUTOINCREMENT,
    subject_id   VARCHAR(64)  NOT NULL REFERENCES data_subjects(subject_id),
    key_version  INTEGER      NOT NULL,
    wrapped_key  TEXT,
    note         VARCHAR(256) NOT NULL DEFAULT '',
    created_at   TEXT         NOT NULL,
    revoked_at   TEXT,
    UNIQUE(subject_id, key_version)
);

-- B4 (AI Act Md. 12(3) traceability): every alarm carries the seq of the
-- evidence-ledger entry that raised it (and the one that resolved it), so any
-- report/output can be linked to the tamper-evident chain without log spelunking.
ALTER TABLE alarms ADD COLUMN evidence_seq INTEGER;
ALTER TABLE alarms ADD COLUMN evidence_seq_resolved INTEGER;

INSERT INTO schema_version(version, note) VALUES (8, 'privacy: data subjects + key custody (crypto-shred); alarms.evidence_seq anchors');
