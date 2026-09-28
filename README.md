<div align="center">

<img src="assets/logo-mark-256.png" width="128" alt="Swarmax logo" title="Swarmax">

# Swarmax

**The audit and operations layer for AI agent fleets.**

<img src="assets/banner-v2.png" width="100%" alt="Swarmax — audit and operations for AI agent fleets">

</div>

[![CI](https://github.com/goun7/Swarmax/actions/workflows/ci.yml/badge.svg)](https://github.com/goun7/Swarmax/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/swarmax)](https://pypi.org/project/swarmax/)
[![Python](https://img.shields.io/pypi/pyversions/swarmax)](https://pypi.org/project/swarmax/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

---

## What it is

**Swarmax is the monitoring and audit layer that sits beside your agent
framework and watches the fleet in production.** If Datadog is how you know
your services are healthy, Swarmax is how you know your agents are — and how
you prove it. It is not a framework and does not run your agents; it consumes
the events they already emit.

## The problem

Every team running autonomous agents gets asked the same three questions, and
frameworks do not answer them:

- *Is this fleet actually working?* Traces show you a single run. Nobody shows
  you that the fleet is drifting, looping, or quietly failing at a rate that
  would page a human.
- *What did it cost?* Token bills arrive as one aggregate number. Which agent,
  which task, which tool loop burned the budget is usually unknowable until
  someone complains.
- *Can you prove any of it?* When a customer, an auditor or a regulator asks
  *"what did your agents do in March?"*, a dashboard screenshot is not
  evidence. Logs are mutable, and you cannot demonstrate a negative ("this
  record has not been altered since it was written").

Swarmax answers all three, and it is built around the third one.

## What is different

Three things we have not found anywhere else:

- **Sealed evidence, not logs.** Every task event lands in an append-only
  ledger. The ledger is periodically sealed with Ed25519 signatures and a
  Merkle root — tampering breaks verification — and each seal can be
  counter-signed by an independent RFC 3161 timestamp authority. When an
  auditor asks what your agents did, you hand over a chain that verifies
  offline, with no need to trust your server.
- **Alarms with a deadline.** Detection thresholds feed an escalation map
  where every alarm class carries an SLA: a runaway tool loop is Emergency
  with a 30-minute clock; an unseen error signature is Critical with 24 hours.
  Open alarms count down in the console and self-escalate when the clock
  expires. Alert fatigue is a measured, budgeted quantity (false-positive
  budget ≤ 5 % of evaluation cycles).
- **Compliance as a command.** The EU AI Act asks providers for logging,
  traceability and deletion guarantees. Swarmax ships a working privacy
  toolkit (RFC 8439 crypto-shredding, an Article 17 `/forget` endpoint,
  S3-compatible signed cold archive) and a compliance drill an auditor can
  run themselves: `make compliance-drill`.

Everything is Python ≥ 3.10 stdlib — **zero runtime dependencies** — so it
fits on a small VPS next to your agents, or scales to tens of millions of
events on ClickHouse. Every crypto and ingest path is pinned to its RFC with
published test vectors.

## In 30 seconds

```bash
pip install swarmax                       # stdlib-only; no dependency resolution
swarmax-init                             # create or upgrade the evidence store

python -c "
from swarmax import SwarmaxClient
c = SwarmaxClient('http://127.0.0.1:4318', 'my-key', b'my-secret')
c.set_agent('support-bot', model='gpt-4o-mini')
with c.span():                            # timed block -> signed telemetry
    run_my_agent_step()
c.guard('web_search', fn, q)              # tool call + runaway-loop protection
c.flush()
"

make seal                                 # seal the ledger: tampering breaks it
```

Every event above lands in an append-only, Merkle-sealed ledger that verifies
offline — a dashboard screenshot is not evidence, this is.

## Quickstart

```bash
pip install swarmax           # stdlib-only; no dependencies to resolve
# or from source:
git clone https://github.com/goun7/Swarmax.git
cd Swarmax
pip install -e .

swarmax-init                # create or upgrade a store (schema v10)
python demo.py              # synthetic fleet: 8/8 alarm classes + FP budget
make seed && make console   # realistic demo fleet -> http://127.0.0.1:8080
```

Demo console logins (created by the seeder — rotate immediately in
production): `root` / `swarmax-demo-admin`, `viewer` / `swarmax-demo-viewer`.

### Integrate in five minutes

```python
from swarmax import SwarmaxClient

client = SwarmaxClient("http://127.0.0.1:4318", "my-key", b"my-secret")
client.set_agent("support-bot", model="gpt-4o-mini")
with client.span():                 # timed block -> real telemetry
    run_my_agent_step()
client.guard("web_search", fn, q)   # tool call + runaway-loop protection
client.flush()
```

Full walkthrough: [`examples/quickstart.py`](examples/quickstart.py).
Node/Bun: [`examples/js/swarmax.js`](examples/js/swarmax.js) (zero-dependency
mini SDK with the same three call styles).

Already tracing with Langfuse? Mirror your fleet without touching your app:

```bash
python -m swarmax.bridges.langfuse_pull --help
```

Any framework exporting OpenTelemetry (LangChain, CrewAI, AutoGen,
OpenLLMetry…): run the signing relay and point `OTEL_EXPORTER_OTLP_ENDPOINT`
at it — unsigned OTLP is rejected, so nothing reaches the ledger unsigned:

```bash
swarmax-otel-relay --help
```

### Development

```bash
python -m pytest tests -q      # 171 tests: RFC vectors, alarm injection, sealing, perf
python scripts/smoke_e2e.py    # end-to-end: ingest -> alarms -> seal -> console
make js-test                   # Node SDK contract tests
```

## What's inside

| Module | What it does |
|---|---|
| `pipeline.py` | ingest → rolling windows → per-agent facts → APD alarms |
| `otlp.py` | OTLP/HTTP+JSON ingest with HMAC anti-replay (`gen_ai.*` / `swx.*` semconv) |
| `metrics/` | EWMA control cards, robust MAD z-scores, JSD tool-mix drift, Page-Hinkley, n-gram loop breaker, MAST-aligned classifier, metamorphic end-state oracle |
| `metrics/apd.py` | Alarm & Protection Dispatcher — the escalation map |
| `sealing.py` + `ed25519.py` | Merkle sealing, key rotation, RFC 8032 signatures (pure Python, vectors-tested) |
| `tsa.py` | RFC 3161 timestamping client — counter-signs seals against a real TSA |
| `auth.py` / `sso.py` | console auth (scrypt, sessions, CSRF, lockout) + OIDC SSO with PKCE |
| `ch.py` | ClickHouse ReplacingMergeTree mirror — 10 M events, per-agent queries < 200 ms |
| `coldstore.py` | AWS SigV4 archive to any S3-compatible store + offline chain verify |
| `privacy/` | ChaCha20-Poly1305 crypto-shredding, HKDF, `/forget` (RFC 8439 / 5869) |
| `console.py` | multi-tenant web console: SLA queue, agent drill-down, PNG chart export, weekly report download/e-mail |
| `dogfood.py` | fleet SDK (`FleetSdk`) + `SwarmaxClient` facade (task / span / guard) |
| `bridges/langfuse_pull.py` | Langfuse → Swarmax pull bridge: maps GENERATION observations to signed `gen_ai.*` spans (idempotent) |
| `bridges/otel_relay.py` | signing relay: any framework's unsigned OTLP/HTTP → signed Swarmax ingest (fail-closed 503) |

## Acceptance gates (all enforced in CI or by drills)

| Gate | Where |
|---|---|
| 100K events, p99 ingest < 2 s (512-span batches) | `tests/test_performance.py` |
| 8/8 alarm classes detected, correct severity + SLA | `tests/test_scenarios.py` |
| False positives ≤ 5 % of hourly cycles | `test_scenarios.py::test_baseline_produces_zero_false_positives` |
| Tamper → seal verification fails | `tests/test_sealing.py` |
| Ed25519 against RFC 8032 vectors | `tests/test_ed25519.py` |
| ChaCha20-Poly1305 against RFC 8439 (cross-checked with OpenSSL) | `tests/test_privacy_crypto.py` |
| OTLP replay rejected | `tests/test_otlp.py` |
| 10M events on real ClickHouse, worst per-agent query 78 ms | `make scale-gate-ch` |
| Exit drill: export → rebuild → verify | `make drill` |
| TSA counter-signature verifies with `openssl ts -verify` | `make trust-drill` |

## Operations

```bash
make otlp             # ingest service :4318  (set SWX_INGEST_SECRET)
make console          # fleet console :8080 (set SWARMAX_ADMIN_PASSWORD in production)
make seal             # seal the evidence ledger now
make drill            # quarterly exit drill (exit 0 = PASS)
make compliance-drill # executable auditor walkthrough (re-runnable)
make ch-mirror        # one-shot ClickHouse mirror pass
make cold-archive / cold-verify
make trust-drill      # RFC 3161 counter-signed sealing drill (live TSA)
```

The alarm map (`metrics/apd.py`): loop ≥ 2 → Emergency/30m · deny > 20 % →
Critical/4h · daily cost > 2×EWMA ∧ Z > 2.5 → Critical/24h · unseen error
class → Critical/24h · error rate > 20 %/24h → Critical/4h · retries ≥ 3 →
High/4h · JSD > 0.40 → Medium/weekly · ticket age > 24h → Emergency/2h with
self-escalation.

## Scope and limits — read this before you adopt it

Swarmax observes, alarms, proves and deletes. It deliberately does **not**:

- **run your agents** — it has no LLM client, no prompt store, no model
  gateway; point it at events your framework already emits;
- **replay or roll back tasks** — the evidence is for proving what happened,
  not re-running it;
- **score answer quality** — vitals that need raw prompts or pixels (per-turn
  hallucination scoring, toxicity checks) stay with the framework that
  produced them; Swarmax consumes their events;
- **act as your LLM gateway** — it measures cost from the tokens reported to
  it, it does not sit in the request path.

Deployment limits that are true today, not on a roadmap slide:

- **single node per fleet** — the honest unit is one sealed store per fleet;
  multi-node active-active and a managed cloud are planned, not shipped;
- **single-tenant console per store** — the multi-tenant schema exists, but
  there is no organisation-level isolation layer above it yet;
- **the seal clock is wall time** — sealing is driven by a scheduler or
  `make seal`; there is no real-time sealing guarantee;
- **OpenTelemetry GenAI semconv is still Development-stage** upstream —
  Swarmax pins a specific revision and extends it with a `swx.*` namespace
  rather than chasing a moving target.

## Documents

- `SWARMAX.md` — the full design record (Turkish), single source of record
- `SWARMAX_EN.md` — English edition
- `AI_ACT_COMPLIANCE.md` — the compliance dossier the drills exercise
- `DOGFOOD_PLAN.md` — the MT-1…MT-8 measurement protocol
- `CHANGELOG.md` · `CONTRIBUTING.md` · `SECURITY.md`

## License

Apache-2.0. Free to self-host, fork and run — the operation of it is what we
sell.

<div align="center">
<img src="assets/logo-mono.svg" width="56" alt="" style="vertical-align:middle">
&nbsp;<sub>Seven points, one chain — measure everything, seal what matters.</sub>
</div>
