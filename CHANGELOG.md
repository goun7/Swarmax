# Changelog

All notable changes to Swarmax. Dates are UTC.

## v4.3.3 — 2026-09-17

### Added

- **Five-minute integration facade**: `swarmax.SwarmaxClient` — `task()`
  one-liner, `span()` timed blocks with error capture, and `guard()`
  loop-protected tool calls (client-side §3.2-3 breaker raising
  `LoopDetected`). All paths emit signed `gen_ai.*` spans over the
  production OTLP path; `examples/quickstart.py` is the copy-paste start.
- **Langfuse pull bridge** (`swarmax.bridges.langfuse_pull`): maps
  GENERATION observations from any Langfuse deployment to signed spans —
  deterministic span ids make re-syncs idempotent; zero dependencies.
- **Node/Bun mini SDK** (`examples/js/swarmax.js`): zero-dependency JS SDK
  mirroring the Python facade (task/span/guard, X-SWX-* HMAC signing);
  tested with `node --test examples/js/` (5/5).
- **OTel signing relay** (`swarmax-otel-relay`): accepts unsigned OTLP/HTTP
  from any OpenTelemetry-exporting framework and forwards it as signed
  batches to Swarmax ingest — fail-closed 503 so nothing is dropped silently.
- **Brand set**: `assets/` logo + banner (single-geometry generator
  `scripts/gen_brand.py`, project's own PNG rasterizer).

## v4.3.2 — 2026-09-17

Packaging + UI export + production scale evidence + monetization decision
(paper v4.3.2, §5.3/§10.1).

- **Monetization decided (§5.3):** hybrid trust-moat model — the core stays
  Apache-2.0 and complete (nothing moves behind a paywall; no license-switch
  trap). Revenue: managed cloud ($199/$599/$2.400+ tiers), **Evidence Trust
  Services** (RFC 3161 HSM countersignature of weekly seal roots, auditor
  portal, independent verification API — $350/mo; first-90-days focus), and
  an enterprise module built only after a paid pilot validates demand.
- **Publishing hygiene (pre-PyPI):** `keys/` and `data/` excluded via
  .gitignore; internal-only documents (FLEETMIND.md, ESKI_KIMLIK.md) kept out
  of the public set; personal-path/email scan clean; `twine check` PASSED for
  wheel + sdist; placeholder PyPI URLs removed until repo is live.
- **T3.1 countersigning shipped (Trust Services):** `swarmax.tsa` pure-stdlib
  RFC 3161 client (hand-built DER, byte-compat verified against
  `openssl ts -query` — FreeTSA's rejection of the DEFAULT-omitted version and
  missing NULL params caught via this comparison); `evidence_seals.tsa_token`
  (migration 010); `seal_ledger(tsa_url=...)` + `verify_seals` chain/Ed25519/
  binding triple check; TSA outage fails closed. Live proof: `make trust-drill`
  against real FreeTSA — seal PASS + `openssl ts -verify` PKI PASS.
- **Turkey structure decision (docs/TR_KURULUS_KARAR.md):** sole proprietorship
  now (NACE 62.01.01, export income → GVK 89/13 100% reduction), 20/B exception
  certificate in parallel, TGB/foreign entities eliminated, Ltd./A.Ş. deferred
  with written triggers (investment/co-founder).

- **Packaging fixed for real installs:** SQLite DDL + migrations moved into
  `src/swarmax/schema/` and shipped as package data — a pip-installed wheel
  can now `init_db_with_migrations()` standalone (schema_version 9). Single
  source of truth for the version: `swarmax.__version__` (4.3.2, pyproject
  aligned). py3.14 classifier added.
- **Chart PNG export (§5):** every console chart (sparkline, EWMA Z, JSD,
  cost, errors, 24h activity) gets a geometry-identical PNG twin via
  `swarmax.raster` (RFC 2083-structured stdlib PNG) + `metrics.charts.Canvas`;
  `GET /chart/<name>.png` (admin-only, honesty gate on empty windows).
- **Weekly report delivery (§4.2/§5):** `GET /report/weekly` (HTML or .md
  download) and `GET /report/weekly.eml` — RFC 5322 multipart email with the
  digest + all six PNG attachments; `SWARMAX_REPORT_FROM/TO` headers.
- **Dogfood day-1 MT-6 scenario:** the week-1 runner now ships a first-seen
  'loop' signature over the real OTLP path and measures the evaluate→alarm
  round trip (§3.3: Emergency-class signals fire during calibration).
- **F3-scale production evidence:** `scripts/scale_gate_ch.py` proves the
  §10.1 hot-tier contract against a real ClickHouse server (24.8 official):
  10,000,050 rows server-side generated, worst per-agent query 78.4 ms
  (threshold 200 ms), live mirror round-trip ok. Result anchored as evidence
  ledger entry #17 (`scale_gate_passed`). Real bug found & fixed en route:
  `ch.mirror_events` had never actually been executed against a server —
  `insert_rows()` now speaks the true ClickHouse HTTP INSERT wire format.
- 146 tests green (9 new UI-export tests).

## v4.3.1 — 2026-09-16

Ops package (B2 wrap-up) + F5 hardening + publishing baseline.

- Privacy seeding (2 demo subjects), `swarmax.dpo.DpoReport` (daily Art. 17
  report), `scripts/compliance_drill.py` (auditor walk: record → forget →
  crypto-shred → anchor → cold archive → offline verify → tamper reject).
- F5: OWASP secure headers on every console response; 1M-event scale-gate
  tests; tenant-isolation, hot-restart recovery, ingest flood tests;
  migration 009 covering indexes (page-view queries 4–25 ms @1M).
- Apache-2.0 LICENSE; pyproject metadata + entry points; GitHub Actions CI
  (test matrix, nightly scale gate, compliance drills).
- AI Act gap register B2–B5 fully closed in code (crypto-shredding RFC 8439
  cross-checked vs OpenSSL, report evidence anchors, UPGRADE_GUIDE,
  LABELING_TEMPLATES).

## v4.3.0 — 2026-09-16

Paper-only items moved to code; AI Act B1–B5 closed.

- RFC 8439 ChaCha20-Poly1305 + RFC 5869 HKDF in `swarmax.privacy.crypto`
  (per-subject random DEKs, wrap under master key, crypto-shred without
  ledger rewrite), pipeline/OTLP/console integration, `/forget` endpoint.
- `alarms.evidence_seq(_resolved)` anchors; weekly report "Evidence anchors"
  section; `UPGRADE_GUIDE.md`; `LABELING_TEMPLATES.md` (Art. 13 pack).

## v4.2.1 — 2026-09-16

Dogfood SDK + cold tier + SSO/tenants + pitch deck.

- `swarmax.dogfood`: OTLP emitter SDK, MT-6/MT-7 measurement cards, week-1
  day-1 runner (`make dogfood-demo`).
- `swarmax.coldstore`: SigV4 S3-compatible archive (S3/R2/MinIO), offline
  chain verification, tamper rejection (`make cold-archive/cold-verify`).
- `swarmax.sso`: OIDC/PKCE, HS256 + pure-stdlib RS256, console callback,
  auto-join viewer, email-domain→tenant mapping (migrations 006/007).
- `scripts/build_pitch_deck.py`: 10-slide print-HTML investor deck.

## v4.2.0 — 2026-09-15

Console v2 multi-user auth, attribution v1.1, agent drill-down, F3-scale
ClickHouse mirror module, D2 fail-closed resolve, seeder console users.

See SWARMAX.md §16 for the full v4.1.x and earlier history.
