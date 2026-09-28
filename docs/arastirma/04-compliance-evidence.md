# 04 — AI Act record-keeping and what counts as evidence

The compliance claims in the README must be traceable. This file pins them.

---

## The regulation

**Regulation (EU) 2024/1689 ("the AI Act"), in force.**
https://eur-lex.europa.eu/eli/reg/2024/1689/oj

The provisions our copy touches:

- **Article 12 — Record-keeping** ("logging"): high-risk AI systems must keep
  logs of their activity, for a period proportionate to the purpose and to
  applicable Union or national law.
- **Article 14 — Human oversight:** the system must be designed so it can be
  overseen by natural persons, with measures enabling oversight *during the
  period of use*.
- **Article 9 — Risk management:** a continuous, documented risk-management
  process across the lifecycle.
- **Article 17 — Quality-management system** and the technical documentation
  obligations (Annex IV) for providers.

The design record in `SWARMAX.md` maps these to code; `AI_ACT_COMPLIANCE.md`
carries the dossier and the B1–B5 gap register that the drills exercise.

## What we may claim, stated precisely

1. **Swarmax provides technical machinery relevant to Art. 12 record-keeping**
   — an append-only, hash-chained, Merkle-sealed event ledger with Ed25519
   signatures (RFC 8032) and optional RFC 3161 counter-signatures. That is a
   logging implementation with a tamper-evidence property.
2. **Swarmax provides machinery relevant to Art. 14 oversight** — an SLA-alarmed
   triage queue with countdowns and self-escalation, and role-gated actions
   (admin vs viewer), behind scrypt-hashed console auth with CSRF protection.
3. **Swarmax provides machinery relevant to Art. 17/Annex IV traceability** —
   the export → rebuild → verify exit drill (`make drill`) produces an
   artefact an auditor can run themselves, and `make compliance-drill` walks
   the erasure path end to end.
4. **Swarmax provides a working GDPR Art. 17 erasure path** — RFC 8439
   crypto-shredding (ChaCha20-Poly1305, HKDF key derivation) so deletion
   destroys the wrapped DEK rather than redacting fields, with the erasure
   itself anchored in the evidence ledger.

## What we may NOT claim

Being explicit — these are the lines not to cross:

- **Swarmax is not "AI Act certified" or "compliant."** There is no
  certification for a logging tool; conformance is assessed *of the AI
  system*, by its provider, in context. Swarmax is a component a provider
  uses while building a conforming system. Saying otherwise would be the
  single fastest way to lose credibility with a real auditor.
- **A seal is not proof of correctness.** It proves *what was recorded and
  that it has not been altered since sealing*. It does not prove the record
  reflects reality ("garbage in, sealed garbage out"). Our own FAQ in
  `docs/landing.md` states this; keep it stated.
- **Timelines are the regulator's, not ours.** The design record references
  the Digital Omnibus adjustment of the high-risk timetable; dates there have
  moved before and can move again. If we quote a deadline in public copy,
  quote the instrument and the date we checked it, and re-check before each
  release. Do not hard-code a compliance deadline into evergreen copy.
- **Erasure is a path, not a guarantee.** Crypto-shredding destroys our copy
  of the key. Data that left the store — exports, downstream copies, the
  framework's own logs — is outside our reach and must be handled by the
  operator's data map.

## The evidence hierarchy we actually use

Ordered from weakest to strongest, so external copy stays at the right level:

| Level | What it is | Where |
|---|---|---|
| 1 | A dashboard view of current fleet state | `make console` |
| 2 | A queryable, hash-chained history | `evidence.py` append-only ledger |
| 3 | A sealed, signed, offline-verifiable chain | `make seal`, RFC 8032 vectors in `tests/test_ed25519.py` |
| 4 | A **third-party counter-signed** chain | `make trust-drill`, RFC 3161, verifies with `openssl ts -verify` |
| 5 | An auditor-runnable drill that exits 0 | `make compliance-drill`, `make drill` |

Level 4 is the paid-tier boundary and the defensible core of the commercial
model: self-signed evidence is legally weak where a third party's
timestamp is not. Everything below level 4 is the free, self-hostable
product.

## Related academic anchor

**AGATE (arXiv:2609.30830, 2026-09-25)** — https://arxiv.org/abs/2609.30830 —
independently argues for retaining "grounds with execution evidence for
forensic replay" at the harness boundary. See
[01-fleet-observability.md](01-fleet-observability.md). It is the citation to
use when a sceptical buyer asks whether "evidence-ledger" is a real concept
or our invention. Note it is a defense paper, not a compliance authority —
cite it for the *idea*, cite the AI Act for the *obligation*.
