-- v4.3.2 (2026-09-17): Evidence Trust Services T3.1 — third-party countersign.
-- tsa_token: raw RFC 3161 TimeStampResp (application/timestamp-reply) from the
-- TSA over the seal message (root || covers). NULL = seal predates countersign
-- or offline mode; verification treats absence as "no countersign", presence
-- as binding-checked. ALTER keeps all existing seals valid.
ALTER TABLE evidence_seals ADD COLUMN tsa_token BLOB;

INSERT OR REPLACE INTO schema_version (version, note)
VALUES (10, 'T3.1: evidence_seals.tsa_token (RFC 3161 countersign, optional)');
