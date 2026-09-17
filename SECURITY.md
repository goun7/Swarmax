# Security Policy

Swarmax exists to make agent operations *provable*. Security issues here are
product issues — treat them as first-class.

## Supported versions

| Version | Supported |
|---|---|
| 4.3.x   | yes |
| < 4.3   | no (evidence schema changed; migrate first) |

## Reporting a vulnerability

Email the maintainers privately (see the repository's `SECURITY` contact
field / maintainer profile). Please do **not** open a public issue for
anything touching signing keys, seal verification, auth, or the privacy
(crypto-shred) path. Expect an initial reply within 72 hours and a fix or a
mitigation plan within 30 days; coordinated disclosure preferred.

## Security-relevant surfaces (what matters most)

- **Evidence chain & seals** (`evidence.py`, `sealing.py`, `ed25519.py`,
  `tsa.py`): append-only enforcement (SQL triggers), Ed25519 signatures,
  Merkle roots, RFC 3161 countersign binding. Tamper must always be detected;
  verification must never throw-and-forget.
- **Ingest trust** (`otlp.py`): HMAC anti-replay (key id, timestamp window,
  nonce cache, signature over method+path+timestamp+nonce+body).
- **Console auth** (`auth.py`, `console.py`): scrypt password hashes (ASVS 2.4),
  server-side sessions with only SHA-256 stored, per-session CSRF, HttpOnly
  cookies, admin/viewer roles, lockout after failures, OWASP secure headers.
- **Privacy / Art. 17** (`privacy/`): per-subject random DEKs wrapped under
  the master key (RFC 8439 + RFC 5869, OpenSSL cross-checked); crypto-shred
  must make data undecryptable for *everyone*, including the master-key
  holder, without rewriting the ledger.
- **Multi-tenancy**: tenant stamps on ingest; tenant isolation is tested
  (`tests/test_hardening_f5.py`).

## What we will not accept in patches

- Silently swallowing verification failures.
- Reducing entropy, shortening nonces, or loosening replay windows "temporarily".
- Introducing runtime dependencies into the stdlib-only core.

Report, verify, fix — in that order. The evidence chain is the product.
