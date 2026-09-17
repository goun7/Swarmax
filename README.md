# Swarmax — Evidence Base + Services (paper v4.3.2)

Agentic fleet operations layer. This repo implements the verified slices of
`SWARMAX.md` v4.3.2: SQLite evidence schema, pinned OTel GenAI semconv map, the §3
metric engine (EWMA / MAD / JSD / Page-Hinkley / loop breaker / MAST classifier /
metamorphic oracle), the §4.2 APD escalation map, the §7.3 synthetic fleet with the
**8/8 alarm-injection acceptance suite**, F1 OTLP ingest, F2 evidence sealing, the
§8 multi-user fleet console (OIDC SSO, multi-tenant), the §10.1 ClickHouse scale
mirror, and the §10.3 privacy toolkit (RFC 8439 crypto-shred, Art. 17 `/forget`).

## Quickstart

```bash
python -m pytest tests -q    # 88 tests — full acceptance stack
python demo.py               # human-readable 8/8 + FP budget + lambda-curve + ledger
python scripts/seed_fleet.py --reset   # realistic demo fleet -> data/swarmax.db
make console                 # http://127.0.0.1:8080
```

Console demo credentials (seeded by `scripts/seed_fleet.py`): `root` /
`swarmax-demo-admin` (admin triage) and `viewer` / `swarmax-demo-viewer`
(read-only). Bootstrap users with `swarmax.auth.bootstrap_admin` / `add_user` in
production and rotate these immediately.

Runtime deps: **none** (Python ≥ 3.10 stdlib). Dev: `pytest`. Optional: a
ClickHouse server for the scale mirror (`SWARMAX_CH_URL`).

## Layout

```
src/swarmax/schema/sqlite_v1.sql      §12.1 DDL + append-only triggers + WAL
src/swarmax/schema/migrations/00[2-9]_*.sql  alarms+seals, guard_events, calibration,
                                     auth+attribution, SSO/tenants, privacy, scale indexes
                                     (shipped inside the wheel — pip install works standalone)
src/swarmax/db.py              PRAGMA discipline, init + migration runner
src/swarmax/semconv/           pinned gen_ai registry + swx.* namespace + validator (R9)
src/swarmax/metrics/           statistics, loop_breaker, classifier, metamorphic, apd (§3, §4.2)
src/swarmax/fleet/emitter.py   synthetic fleet: baseline + S1–S8 injections (§7.3)
src/swarmax/pipeline.py        ingest → windows → APD facts → alarms (persisted + sealed)
src/swarmax/otlp.py            F1: OTLP/HTTP+JSON ingest, HMAC anti-replay (§4.3)
src/swarmax/ed25519.py         pure-Python Ed25519 (RFC 8032) for F2
src/swarmax/sealing.py         F2: Merkle sealing + verification + key rotation
src/swarmax/auth.py            console auth: scrypt, sessions, CSRF, lockout, SSO sessions (§8)
src/swarmax/sso.py             OIDC SSO with PKCE; HS256 + pure-stdlib RS256 verify
src/swarmax/coldstore.py       B1 cold tier: SigV4 S3-compatible archive + offline verify
src/swarmax/dogfood.py         dogfood SDK (batching OTLP emitter) + MT-6/MT-7 measurement
src/swarmax/attribution.py     v1.1 attribution suggestions, human-confirm gate (§9.2)
src/swarmax/ch.py              F3-scale: ClickHouse ReplacingMergeTree mirror (§10.1)
src/swarmax/report.py          weekly fleet report (§4.2 weekly path)
src/swarmax/console.py         console v2: auth'd multi-user UI + /agent/<id> drill-down
src/swarmax/exit_drill.py      quarterly exit drill (export → rebuild → verify)
tests/                         119 tests: schema, semconv, metrics, 8/8, perf, otlp,
                               ed25519, sealing, report/console/drill, auth,
                               attribution, console-v2, calibration, sso, coldstore,
                               dogfood, console-sso, pdf-package
config/otelcol-config.yaml     tail-sampled collector (§12.2)
```

## Acceptance (§7)

| DoD | Result |
|---|---|
| 100K synthetic events, p99 ingest < 2 s (512-span batches) | `tests/test_performance.py` |
| Schema-change test passes (migrations 002–005 idempotent) | `tests/test_schema.py` |
| 8/8 injections detected w/ correct severity + SLA | `tests/test_scenarios.py` |
| FP budget ≤ 5% of hourly cycles (R10) | `tests/test_scenarios.py::test_baseline_produces_zero_false_positives` |
| MT-4 λ-curve: ≤ 5-point drop at λ=0.1 | `tests/test_scenarios.py` |
| Evidence chain verifiable, append-only | `tests/test_schema.py`, `test_scenarios.py` |
| F2 seals verify; tamper detected | `tests/test_sealing.py`, `test_ed25519.py` (RFC 8032) |
| OTLP replay rejected, spans accepted | `tests/test_otlp.py` |
| Console auth: CSRF, roles, lockout, agent page | `tests/test_auth.py`, `tests/test_console_v2.py` |
| Chart PNG export + weekly report email (RFC 5322, PNG attachments) | `tests/test_ui_export.py` |
| 10M events on real ClickHouse: per-agent queries < 200 ms (§10.1) | `make scale-gate-ch` (env: `SWARMAX_CH_URL`) |
| Exit drill roundtrip PASS | `tests/test_report_console_drill.py` |

## Services

```bash
make otlp        # F1 ingest :4318 — set SWX_INGEST_SECRET; OTLP/JSON + X-SWX-* HMAC headers
make console     # fleet console :8080 — login, SLA queue, resolve, seal, attribution, agent pages
make seal        # seal the evidence ledger now (Ed25519 + Merkle, §12.1/R1)
make drill       # quarterly exit drill: export → rebuild → verify (exit code 0 = PASS)
make ch-mirror   # one-shot ClickHouse mirror pass (no-op unless SWARMAX_CH_URL is set)
make cold-archive / cold-verify  # B1: S3-compatible signed archive + offline chain verify (SigV4, stdlib)
make dogfood-demo  # dogfood week-1 day 1: SDK → OTLP ingest → MT-6/MT-7 cards (DOGFOOD_PLAN.md)
make pdf / pitch-deck  # print-ready HTML: blueprints + investor deck -> dist/
python scripts/smoke_e2e.py   # end-to-end: ingest → alarms → seal → console (auth) + report
```

Alarm map (§4.2, implemented verbatim in `metrics/apd.py`): loop≥2 → Emergency/30m;
deny>20% → Critical/4h; daily cost > 2×EWMA-µ ∧ Z>2.5 → Critical/24h; new-class →
Critical/24h; error-rate>20%/24s → Critical/4h; retries≥3 → High/4h; JSD>0.40 →
Medium/weekly; ticket-age>24h → Emergency/2h self-escalation.

Paper: [`SWARMAX.md`](SWARMAX.md) (v4.3.2, single source of record, Turkish).
English edition: [`SWARMAX_EN.md`](SWARMAX_EN.md). Companion documents:
[`DOGFOOD_PLAN.md`](DOGFOOD_PLAN.md) (MT-1…MT-8 execution) and
[`AI_ACT_COMPLIANCE.md`](AI_ACT_COMPLIANCE.md) (EU AI Act dossier). Investor summary:
[`SWARMAX_ONEPAGER.md`](SWARMAX_ONEPAGER.md).
