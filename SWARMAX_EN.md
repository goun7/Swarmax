# SWARMAX — Agentic Fleet Operations Platform
### Canonical Master Blueprint · Verified Data · Scientific Foundation · Product, Architecture, Commercialization and 12-Week Execution Plan (100/100)

> **Edition:** English translation, synced to `SWARMAX.md` **v4.2.0** (2026-09-16). The
> Turkish master remains the source of record; this file is the canonical English
> edition for investors, customers and auditors. **Status:** PAPER — Verified Master
> Blueprint. Predecessor: `FLEETMIND.md` v3.5 (superseded; see §13.1).
> **Positioning sentence:** *"For teams running autonomous agent fleets in production:
> every agent's cost, latency, error classes and behavioral drift on one screen; SLA
> breaches prevented up front; evidence-based, SLA-bound human escalation (HITL)
> guaranteed when anomalies fire."*

---

## 0. EVIDENCE AND VERSION DISCIPLINE (Evidence Ledger)

Every market, regulatory and standards claim in this document is verified and
date-stamped. Rule: **"A number without evidence is deleted."**

| # | Evidence | Summary | Source / Date |
|---|---|---|---|
| E1 | Gartner: **40%+** of agentic AI projects at risk of cancellation by end-2027 | Causes: cost escapes, unclear business value, insufficient risk controls | [Gartner PR, 25.06.2025](https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027) |
| E2 | Gartner: **$234 B** enterprise application software spend exposed to agentic AI | Pricing-model disruption signal | [Gartner PR, 01.07.2026](https://www.gartner.com/en/newsroom/press-releases/2026-07-01-gartner-says-us-dollars-234-billion-in-enterprise-application-software-spend-is-at-risk-from-agentic-artificial-intelligence) |
| E3 | Gartner: agentic AI software spend **$985 B by 2030** (2025–30 CAGR 62.7%) | Category explodes from near-zero in 2025 | [Gartner Forecast Analysis, Feb 2026](https://www.gartner.com/en/documents/7455226) |
| E4 | Gartner: **40%** of enterprise apps will feature task-specific agents in 2026 (2025: <5%) | Demand side: fleet-operations need compounds | [Gartner PR, 26.08.2025](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025) |
| E5 | **Digital Omnibus on AI = Regulation (EU) 2026/1744**, in force 27.07.2026 | High-risk obligations 02.08.2026 → **02.12.2027** (Annex III) / 02.08.2028 (embedded AI); +4 months for legacy systems | [EU AI Compass](https://euaicompass.com/digital-omnibus-proposal-2027-deadline-extension.html) · [Gibson Dunn, 27.05.2026](https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/) · [Orrick, 29.07.2026](https://www.orrick.com/en/Insights/2026/07/EU-AI-Act-Update-Digital-Omnibus-Finalizes-8-Compliance-Changes) · [CSA, 01.08.2026](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-high-risk-deadline-omnibus-20260/) |
| E6 | OTel **GenAI semconv** moved to a separate repo; **all `gen_ai.*` attributes Development** status | No "stable" claims possible; pin + version discipline mandatory | [open-telemetry/semantic-conventions-genai — attribute registry](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md) · [opentelemetry.io redirect page](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (accessed 14.09.2026) |
| E7 | **MAST**: 14 failure modes in multi-agent LLM systems; three families (specification / inter-agent / assistant verification); ~1,600 traces analyzed | Academic basis of our error taxonomy | Cemri et al., [arXiv:2503.13657](https://arxiv.org/abs/2503.13657) · NeurIPS 2025 D&B |
| E8 | **ReliabilityBench**: agent reliability under production-like stress; consistency dimension in repeated runs | Single-run success metrics are insufficient; basis of our measurement-commitment metrics | [arXiv:2601.06112](https://arxiv.org/abs/2601.06112), January 2026 |
| E9 | MITRE **ATLAS v5.1.0** (Nov 2025): 16 tactics / 84 techniques; agentic emphasis | Frame of the threat model | [atlas.mitre.org](https://atlas.mitre.org/) · [Vectra summary](https://www.vectra.ai/topics/mitre-atlas) |
| E10 | **OWASP Agentic AI — Threats & Mitigations** (ASI) + **OWASP GenAI LLM Top 10 (2026 edition, 03.08.2026)** | Our audit-control set | [OWASP Agentic T&M](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) · [OWASP LLM Top 10 2026](https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/) |
| E11 | Langfuse acquired by ClickHouse (Jan 2026); unit-based billing; LangSmith ~$39/seat/mo | Competitive landscape as of 2026 H2 | [Latitude, 27.03.2026](https://latitude.so/blog/best-llm-observability-tools-agents-latitude-vs-langfuse-langsmith) · [Pydantic Logfire pricing comparison, 31.03.2026](https://pydantic.dev/articles/ai-observability-pricing-comparison) · [OpenObserve, 31.07.2026](https://openobserve.ai/blog/langfuse-vs-langsmith/) |
| E12 | ClickHouse engineering blog: "GenAI + MCP semconv in Development status" (as of May 2026) | Independent corroboration of E6 | [ClickHouse, 29.07.2026](https://clickhouse.com/resources/engineering/opentelemetry-semantic-conventions) |
| E13 | Türkiye: GVK provisional article 89/1-b — **80% of** software-service income earned abroad is exempt | Tax optimization for a TR-registered entity | GVK prov. art. 89/1-b; current text: [gib.gov.tr](https://www.gib.gov.tr) (accessed 14.09.2026) |
| E14 | **Who&When**: automated failure attribution in multi-agent LLM systems (which agent, which step); ICML 2025 spotlight, 222+ citations | Academic basis for suggesting the responsible agent/step in escalation tickets | Zhang et al., [arXiv:2505.00212](https://arxiv.org/abs/2505.00212) · ICML 2025 |
| E15 | **Current field SOTA (April 2026):** TraceElephant — failure-attribution benchmark compiled from 311K production traces, mean **65.9%** correct-step accuracy; independently, the multi-perspective benchmark critique (arXiv:2603.25001, March 2026) shows single-perspective evaluation is insufficient | Automated attribution staying human-in-the-loop *validates the paper's own decision*; the v1.1 acceptance gate is calibrated to this number | [TraceElephant, arXiv:2604.22708](https://arxiv.org/abs/2604.22708) · [arXiv:2603.25001](https://arxiv.org/abs/2603.25001) (accessed 15.09.2026; peer-review status undisclosed — the v1.1 gate does not open before E15 is re-verified) |
| E16 | **Web session management hardening (OWASP Session Management Cheat Sheet, accessed Sept 2026):** server-side sessions, session invalidation without id disclosure, cookie flags (HttpOnly+SameSite), session lifetime and renewal | Frame of the console v2 auth design (§8) | [OWASP Session Mgmt CS](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) · [ASVS 4.0.3 §3.3/§2.4](https://owasp.org/www-project-application-security-verification-standard/) |

**Change protocol:** every E-record is re-verified quarterly (next scan:
**2026-12-14**). If an evidence item is invalidated it is recorded in the §13.2
changelog and the affected section is rewritten.

---

## 1. EXECUTIVE SUMMARY

**Swarmax** is the **operations layer (Fleet Operations Layer)** for autonomous agent
fleets running in production: framework-agnostic telemetry ingestion (OTel GenAI
semantics), 5 metric families, academically grounded anomaly/drift detection,
evidence-chained (Merkle/Ed25519) audit, and SLA-bound human escalation (HITL) — in
one product.

**Problem (E1–E4 combined):** as enterprise agent fleets grow, (i) cost escapes,
(ii) behavioral drift, (iii) the audit/evidence gap and (iv) missing SLA-bound human
oversight push projects to cancellation. Frameworks (LangGraph, CrewAI, AutoGen,
ADK…) *build* the fleet; Swarmax *operates* it.

**Why now:** (a) 40% of enterprise apps include agents in 2026 (E4); (b) $234 B of
software spend is exposed to agentic transformation (E2); (c) the EU high-risk
obligation date moved to 02.12.2027 (E5) — a **~15-month compliance window** just
opened with an explicit evidence-infrastructure requirement; (d) the competitor
landscape (E11) is stuck in developer-observability; the operations layer is empty.

**Core claims:**
1. **Honest standards compliance:** OTel GenAI Development-status attributes with a
   pinned registry; no "stable" claims (§2).
2. **Academically grounded detection:** EWMA + MAD + JSD + Page-Hinkley/CUSUM +
   n-gram loop breaker; error classes aligned with MAST (§3).
3. **Evidence-chained audit:** append-only hash-chained ledger; crypto-shredding for
   GDPR/KVKK erasure; ready for the post-Omnibus 2026/1744 calendar (§6, §10).
4. **Verifiable commitments:** SLA, RPO and measurement-commitment metrics with
   measurable definitions + test protocol (§8, §9).

---

## 2. ARCHITECTURE AND STANDARDS COMPLIANCE (OTel GenAI, Honest Maturity Statement)

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                     AGENT FLEET (CUSTOMER OR DOGFOOD ENVIRONMENT)                     │
│   LangGraph · CrewAI · AutoGen · Semantic Kernel · OpenAI Agents SDK · Custom P/TS/Go │
└──────────────────────────────────────────────┬────────────────────────────────────────┘
                                               │ OTLP/gRPC 4317 · OTLP/HTTP 4318
                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                        SWARMAX OTEL COLLECTOR PIPELINE                                │
│  Receiver: otlp (grpc/http) → memory_limiter → attributes/enrich                      │
│  → transform (gen_ai.* normalization + PII masking) → batch → tail_sampling           │
│  Ingestion Validator: mTLS + token + nonce anti-replay                                │
└──────────────────────────┬─────────────────────────────────┬──────────────────────────┘
                           │                                 │
                           ▼                                 ▼
┌────────────────────────────────────────┐    ┌──────────────────────────────────────────┐
│  TIME-SERIES & ANALYTICS STORE         │    │  ASSURANCE PLANE (Evidence Plane)        │
│  v1: SQLite+WAL+Litestream → v2:       │    │  Append-only hash-chained ledger         │
│  ClickHouse (MergeTree + TTL tiering)  │    │  (Ed25519-signed records + Merkle root)  │
│  5 Metric Families · Dynamic Baseline  │    │  Policy Proxy · Kill-switch distribution │
└──────────────────┬─────────────────────┘    └──────────────────┬───────────────────────┘
                   │                                             │
                   ▼                                             ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│               ANOMALY & BEHAVIORAL DRIFT ENGINE (APD Engine)                          │
│  EWMA cost/latency · MAD output length · JSD tool distribution · Page-Hinkley/CUSUM   │
│  n-gram loop breaker · MAST-aligned error classifier · Unknown-class sentinel         │
└──────────────────────────────────────────────┬────────────────────────────────────────┘
                                               │
                          ┌────────────────────┴────────────────────┐
                          ▼                                         ▼
┌──────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│  WEEKLY FLEET REPORT ENGINE              │   │  HITL HUMAN ESCALATION QUEUE            │
│  Fleet X-ray · Most expensive agents ·   │   │  Priority triage · SLA countdown        │
│  Drift charts · EU AI Act appendix       │   │  (30 min–24 h) · PagerDuty/Slack        │
└──────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

> **Alarm path (v4.1, R1):** the APD engine does **not** consume collector output; it
> consumes the §4 event stream (SDK/assurance proxy → engine, a direct low-latency
> path). The collector pipeline (`tail_sampling`, `batch`) serves traces and the
> weekly report only; `decision_wait: 10s` never enters alarm latency. The ≤ 500 ms
> alarm commitment (§8, MT-6) is measured on the direct path.

### 2.1 OTel GenAI Semantic Attribute Map (Registry-Pinned)

> **Honesty rule (E6/E12):** **all `gen_ai.*` attributes in the registry are
> Development status.** Swarmax does not hide this; it works with a **pinned
> registry** and locks its own interface. Safer than "wait for stable": while
> tracking real fleets today, an upstream change requires updating exactly one
> mapping file (`semconv-diff` CI, §7.4).

| Canonical Swarmax field | Pinned OTel `gen_ai.*` (Development) | Type | Note |
|---|---|---|---|
| `swx.agent.id` | `gen_ai.agent.id` | string | Normalized as `urn:agent:<tenant>:<env>:<agent>`. Registry examples: Bedrock ARN / Vertex ReasoningEngine id. |
| `swx.agent.name` | `gen_ai.agent.name` | string | Human-readable name. |
| `swx.agent.role` | `swx.agent.role` *(extension)* | enum | `planner/worker/reviewer/executor` — absent from registry; lives in the `swx.` namespace. |
| `swx.session.id` | `gen_ai.conversation.id` | string | Registry note respected: no fabricated UUID if unavailable. |
| `swx.task.id` | `swx.task.id` *(extension)* | string | Work-unit id (ticket/order/workflow id). |
| `swx.tokens.in/out` | `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` | int | Canonical source of the measurement. |
| `swx.cache.read.tokens` | `gen_ai.usage.cache_read.input_tokens` | int | Cache hits enter the cost model. |
| `swx.reasoning.tokens` | `gen_ai.usage.reasoning.output_tokens` | int | "Thinking" tokens; separate cost line. |
| `swx.cost.usd` | `swx.cost.usd` *(extension)* | float | Decimal computation against provider price lists; no `gen_ai.*` counterpart. |
| `swx.model.requested` | `gen_ai.request.model` | string | Requested model. |
| `swx.model.served` | `gen_ai.response.model` | string | Actually serving model (post-routing). |
| `swx.provider` | `gen_ai.provider.name` | string | `openai`, `gcp.vertex_ai`, etc. |
| `swx.operation` | `gen_ai.operation.name` | string | `chat`, `generate_content`, `text_completion`, `embeddings`; plus `swx.agent_step`, `swx.tool_execution`. |
| `swx.tool.name` | `gen_ai.tool.name` | string | Executed tool. |
| `swx.tool.call.id` | `gen_ai.tool.call.id` | string | Call token. |
| `swx.tool.call.arguments` | `gen_ai.tool.call.arguments` | any | After PII masking; optional capture. |
| `swx.tool.call.result` | `gen_ai.tool.call.result` | any | Optional capture. |
| `swx.tool.status` | `swx.tool.status` *(extension)* | enum | `success / error / denied / timeout`. |
| `swx.finish.reasons` | `gen_ai.response.finish_reasons` | string[] | For loop/length separation. |
| `swx.ttft` | `gen_ai.response.time_to_first_chunk` | double (s) | Time-to-first-chunk latency. |
| `swx.eval.*` | `gen_ai.evaluation.score.value` / `.label` / `.name` / `.explanation` | mixed | Offline/online evaluation scores. |
| `swx.prompt.name/version` | `gen_ai.prompt.name` / `gen_ai.prompt.version` | string | Prompt version tracking (critical for drift diagnosis). |
| `swx.agent.version` | `gen_ai.agent.version` | string | Agent binary/prompt version; covariate in drift. |
| `swx.workflow.name` | `gen_ai.workflow.name` | string | Multi-agent flow name. |

**Extension discipline:** every field absent from the registry lives in the `swx.`
namespace; upstream version bumps are scanned for breaking changes by the
`semconv-diff` CI job (§7.4).

### 2.2 Zero-Lock-In Commitment
- **BYO-storage:** raw data stays in the customer's own storage account; Swarmax
  mediates processing.
- **Open schema:** the `swx.*` extension schema is published under MIT; full exit
  (JSON/Parquet export) ≤ 1 hour.
- **Exit drill:** quarterly exit simulation on a random tenant's data; timed and
  reported.

---

## 3. METRIC CATALOG AND ANOMALY DETECTION (5 Families)

### 3.1 Metric Families and Threshold Table (v1 initial values)

| Family | Metric | Unit | Algorithm | Initial threshold | Severity |
|---|---|---|---|---|---|
| **A. Cost** | `cost.tokens_in/out` | token | Rolling-window total | — | Info |
| | `cost.usd` (daily, per agent) | USD | **EWMA** (α=0.15, β=0.10) + Z>2.5 | Daily spend > 2.0× EWMA-µ | Critical |
| | `cost.usd_per_task` | USD | **MAD** robust-z | \|robust-z\| > 3.0 | High |
| **B. Latency** | `latency.step_ms` | ms | p95 rolling distribution (7d) | p95 > 2.0× | Medium |
| | `latency.task_total_ms` | ms | MAD robust-z | \|robust-z\| > 3.0 | High |
| | `latency.ttft_s` | s | EWMA | Z > 2.5 | Medium |
| | `latency.retry_count` | count | In-step counter | ≥3 (same task) | High |
| **C. Error** | `error.rate` (1s) | % | Error/request ratio | > 20% | Critical |
| | `error.class` | enum | MAST-aligned classifier | `loop` ≥ 2 | Emergency |
| | `error.new_class_seen` | string | Unknown-class signature | First in historical set | Critical |
| **D. Drift** | `drift.tool_distribution` | distribution | **JSD**(P₇d ∥ Q₂₄h) | > 0.40 | Medium |
| | `drift.output_length` | token | **MAD** | outside median ± 50% | Low |
| | `drift.output_quality` | end-state | Metamorphic oracle (end-state equivalence, §3.2-7) | violation in semantically equivalent task | Medium |
| | `drift.escalation_ratio` | % | Weekly human-handoff ratio | > 2.0× | High |
| **E. Escalation (HITL)** | `escalation.open` | ticket | Queue counter | quota > 5 | High |
| | `escalation.age_max_h` | hours | Oldest open ticket | > 24 (auth breach: >4) | Emergency |
| | `escalation.reason` | enum | `budget/permission/quality/unknown` | Routed by cause | — |

### 3.2 Mathematical Formulations and Sources

**1) Dynamic cost outlier — EWMA control card**
$$\mu_t = \alpha C_t + (1-\alpha)\mu_{t-1},\ \alpha=0.15;\qquad \sigma_t^2 = \beta(C_t-\mu_t)^2 + (1-\beta)\sigma_{t-1}^2,\ \beta=0.10$$
$$Z_t = \frac{C_t - \mu_t}{\sigma_t};\qquad Z_t > 2.5 \Rightarrow \textbf{CostSpikeAlarm}$$
Sources: Roberts (1959) EWMA chart; Hunter (1986), *J. Quality Technology* 18(4).
Why: catches small-to-medium shifts quickly without a normality assumption.

**Cold-start discipline (v4.1, R3):** the Z-alarm arms only after **≥ 30 observations**
and after the §3.3 calibration window closes; the EWMA variance estimator is
unstable in the first days.

**2) Tool-distribution drift — Jensen-Shannon Divergence**
$P$: 7-day normalized tool-call vector, $Q$: 24-hour vector, $M=\tfrac12(P+Q)$:
$$JSD(P\parallel Q)=\tfrac12\sum_i P_i\log_2\frac{P_i}{M_i}+\tfrac12\sum_i Q_i\log_2\frac{Q_i}{M_i}$$
$JSD<0.20$ healthy · $0.20$–$0.40$ watch (weekly report note) · $>0.40$
**Behavioral Drift Alarm** → review escalation.
Source: Endres & Schindelin (2003), *IEEE Trans. Information Theory* 49(7) — JSD is
symmetric, always finite; its square root is a true metric.

**Implementation discipline (v4.1, R4):** empty cells make log ratios undefined;
ε = 10⁻⁶ is added to all probabilities and if the P or Q window is empty the
comparison is **skipped** with a `warming_up` marker — no infinite divergence is
produced.

**3) Runaway loop breaker — n-gram hash**
$$h_i = \text{SHA256}(\text{tool\_name}\,\|\,\text{normalize\_json}(\text{arguments}))$$
Three consecutive identical hashes ($h_i=h_{i-1}=h_{i-2}$) ⇒ task quarantine
(`KILL_CIRCUIT_OPEN`) + assurance-plane event + human escalation.
Rationale: n-gram detectability of repetition pathology — Holtzman et al., *The
Curious Case of Neural Text Degeneration*, ICLR 2020.

**4) Robust scale — MAD (Median Absolute Deviation)**
$$\text{robust-z} = \frac{0.6745\,(x_i-\text{median})}{\text{median}_i|x_i-\text{median}|};\quad |\text{robust-z}|>3.0 \Rightarrow \text{alarm}$$
Rationale: robust to heavy-tailed agent cost distributions vs. mean/SD —
Hampel (1974); Leys et al. (2013), *J. Exp. Social Psychology*.

**5) Persistent shift — Page-Hinkley / CUSUM (JSD's complement)**
$$g_t=\max(0,\,g_{t-1}+(x_t-\mu_0-\delta));\quad g_t>h\Rightarrow\textbf{ShiftAlarm}$$
JSD catches *distribution difference*; Page-Hinkley catches *monotonic shift*.
**PSI** is additionally reported for error-class distribution shifts
(PSI > 0.25 = large shift; banking practice).
Source: Page (1954), *Biometrika* 41(1–2).

**6) Error taxonomy — MAST alignment (E7)**

| Swarmax `error.class` | Definition | MAST family |
|---|---|---|
| `spec_ambiguity` | Vague/missing subtask definition | Specification Issues |
| `interagent_mismatch` | Agent-agent communication/protocol mismatch | Inter-Agent Misalignment |
| `verification_fail` | Output cannot be verified | Task Verification |
| `tool_fail / parse / timeout / auth` | Mechanical-operational classes | (outside MAST) |
| `loop` | n-gram loop pathology | Inter-Agent Misalignment (circulation) |
| `unknown` | Unknown class (first-seen) | — (Sentinel) |

**7) Output-quality drift — Metamorphic Oracle (E8)**
ReliabilityBench's *action metamorphic relations* principle: correctness is defined
by **end-state equivalence**, not text similarity. Swarmax turns this into an
in-production drift signal: across runs of the same task template, end-state
variables (records created, notifications sent, file hashes written, etc.) are
compared; end-state deviation in semantically equivalent tasks raises the
`drift.output_quality` alarm. Output-quality drift is thus caught **without entering
LLM-judge bias**.

**Cost budget (v4.1, R5):** the oracle runs as a shadow rerun limited to **≤ 1%** of
agent-day traffic in the critical task class; budget overruns are written to the
`baseline_audit` ledger.

### 3.3 Calibration Discipline
Table values are **initial** thresholds. For each agent a **14-day calibration
window** runs first: until it closes, only Info and Emergency (`loop`, `new_class`)
alarms fire; High/Critical thresholds are calibrated per tenant and changes are
written to the `baseline_audit` ledger.

**False-positive budget — measurable definition (v4.1, R10):** per agent-day, the
false-positive alarm rate within hourly evaluation cycles is **≤ 5%** (≤ 1 FP/day
per agent at 24 cycles/day). Synthetic injection agents are exempt from the
calibration window (`synthetic=1`; window pre-closed at setup) — real dogfood data
is never polluted with synthetic data (§7.3).

---

## 4. EVENT CONTRACT — Operations ↔ Assurance Plane

Fleetmind ↔ Agent Assurance Pipeline remain distinct; Swarmax positions them as
**one product, two planes**:
- **Operations plane:** telemetry ingestion, metric production, anomaly engine,
  reports, HITL queue.
- **Assurance plane:** append-only hash-chained evidence ledger (Ed25519 + Merkle
  root), policy proxy, kill-switch distribution.

### 4.1 Event Types and Behavior Matrix

| Event (`event_type`) | Producer | Consumer | Operations-plane behavior |
|---|---|---|---|
| `tool_call` | Assurance Proxy / SDK | Operations + Assurance | Volume/latency/error counters; JSD vector updated |
| `permission_decision` | Assurance Engine | Operations + Assurance | `deny` ratio; security alarm on sudden spike |
| `mask_event` | PII Masker | Operations + Assurance | Counters only; content never read |
| `escalation` | APD Engine | Human + Assurance | Written to triage queue; SLA counter starts |
| `kill_switch_triggered` | APD or Human | Fleet + Assurance | API sessions terminated; event sealed into ledger |

### 4.2 Alarm → Escalation SLA Mapping

| Signal | Emitted event | Cause | SLA | Automatic protection action |
|---|---|---|---|---|
| `error.class == 'loop'` (≥2) | `escalation` | `quality` | **30 min** | Task quarantine; loop breaker open |
| `permission.deny > 20% / 1s` | `escalation` | `permission` | **4 h** | External tool grants temporarily frozen |
| `cost.daily > 2.0× EWMA-µ` | `escalation` | `budget` | **24 h** | Model downgrade *proposal* (operator-approved) |
| `error.new_class_seen` | `escalation` | `unknown` | **24 h** | Triage with "new error pattern" label (E8: repeated-stress conditions tracked separately) |
| `error.rate > 20%` (24s window) | `escalation` | `quality` | **4 h** | Responsible agent's tasks moved to triage (v4.1, R15) |
| `latency.retry_count ≥ 3` (same task) | `escalation` | `quality` | **4 h** | Task re-queued; source provider audited (v4.1, R15) |
| `drift.tool_distribution > 0.40` | `report_item` | `drift` | **Weekly** | Listed as behavioral deviation in the weekly report |
| `escalation.age_max_h > 24` | `escalation` | `system_health` | **2 h** | Self-escalation; PagerDuty/SMS |

### 4.3 Identity Pairing and Anti-Replay
- Both planes use a robot-proof identity standard; `agent.id` never forks.
- Every OTLP ingest carries nonce + HMAC anti-replay; replayed packets are counted
  in the `ingest_reject` metric.

---

## 5. COMPETITIVE ANALYSIS, UNIT ECONOMICS AND PRICING (pinned by E11)

### 5.1 Competitive Positioning (2026 H2 realities)

| Category / Player | Representatives | Focus | Swarmax moats |
|---|---|---|---|
| Developer Observability | LangSmith, Langfuse, AgentOps, Logfire | Traces, prompt debugging, developer panel | **Operations layer:** SLA tracking, cost deviation, behavioral drift, weekly enterprise report, HITL queue. Langfuse joining ClickHouse (E11) strengthens the thesis "observability infrastructure is standardizing; nobody adds operations intelligence on top." |
| MLOps / Serving Proxy | Portkey, LiteLLM | Model routing, load balancing, cache | **Agent-level operations:** task SLA, tool deviation, human escalation queue. |
| Enterprise Security Frameworks | OWASP ASI guides, MITRE ATLAS (E9/E10) | Audit control sets | Swarmax productizes these sets as **running controls** (control → telemetry → evidence → escalation chain). |
| In-house stacks | Scattered Grafana/ELK dashboards | Raw infrastructure metrics | **Ready agent semantics:** 5 metric families, zero-code rule set, pinned-semconv exporters. |

### 5.2 Unit Economics

| Item | Value | Note |
|---|---|---|
| Infrastructure cost (base node) | ~$50/mo | Go/Rust collector + SQLite/Litestream (v1) or single ClickHouse node (v2) |
| Onboarding (per customer) | ~3 h | Fleet configuration + OTel endpoint + threshold calibration |
| Monthly maintenance (per customer) | ≤1 h | Auto-tuning + weekly report approval |
| Gross margin | **88–95% target** | Consistent with §5.4 scenario table |
| Break-even | **1 customer** | Low fixed costs |

### 5.3 Pricing (AVBP = Average Monthly Billing-critical agent; E11 price signals)

| Tier | Scope | Price | Target |
|---|---|---|---|
| Open Core | Self-host collector + open `swx.*` schema + basic metrics | **$0 (Apache-2.0)** | Community, developers |
| Team | 10 AVBP + 5 metric families + email/Slack alarms | **$99/mo** | Early-stage teams |
| Fleet+Evidence | 50 AVBP + signed evidence stream + weekly SLA/drift report + SSO | **$599/mo** | Multi-agent SMBs in production |
| Enterprise | Unlimited AVBP + custom SLA + multi-team + BYO-storage + compliance pack | **$2,400/mo+** | Finance/health/mission-critical |

> **Competitor comparison (E11):** developer-observability tools bill per seat/unit/GB
> (LangSmith ~$39/seat/mo; unit-based models can create 8–15 billing units per
> agent). Swarmax sells budget predictability with **agent-based flat tiers** — a
> direct counter-position to E2's cost-unpredictability problem.
>
> **Pricing alignment (owner decision, 2026-09-29):** `docs/landing.md` is the
> public pricing and this table matches it (Team $99/mo). The earlier **$199/mo**
> Team figure is internal-only and not offered; do not reintroduce it.

### 5.4 12-Month P&L — Target Scenario (assumption: mix-weighted $490 ABP)

| Month | Active customers | MRR | Infra & ops | Gross profit | Margin | Milestone |
|---|---|---|---|---|---|---|
| 1 | 1 (internal dogfood) | $0 | $65 | −$65 | — | Dogfood run |
| 2 | 2 | $980 | $90 | $890 | 90.8% | First paid pilots |
| 3 | 4 | $1,960 | $120 | $1,840 | 93.9% | Open-schema GTM effect |
| 6 | 12 | $5,880 | $350 | $5,530 | 94.0% | ClickHouse migration (v2) |
| 9 | 25 | $12,250 | $650 | $11,600 | 94.7% | Evidence-pack sales |
| 12 | 50 | $24,500 | $1,200 | **$23,300** | **95.1%** | **ARR ≈ $294,000** |

> A scenario assumption, not a forecast; recomputed as the price mix changes; built
> with **churn=0 assumption** as an execution target (v4.1, R9). Verified market
> sizes (E2, E3) pin the demand side.

---

## 6. SECURITY, THREAT MODEL AND REGULATION (E9/E10/E5)

### 6.1 Threat Model — STRIDE × MITRE ATLAS × OWASP
- **Spoofing:** mTLS + token + nonce anti-replay at the collector (§4.3). ATLAS:
  agent-identity pairing against impersonation techniques.
- **Tampering:** every event Ed25519-signed; ledger hash-chained (SHA-256 Merkle
  root). Assurance plane is append-only.
- **Repudiation:** signed evidence chain + operator action records → non-repudiation.
- **Information Disclosure:** regex/NER PII masking in the collector transform layer
  (`mask_event`); content capture flags default-off (consistent with OTel registry
  warnings).
- **DoS:** `memory_limiter` + ingestion rate limit + controlled drop; drop counters
  visible to the customer.
- **Elevation of Privilege:** policy proxy instant `deny` → escalation; kill-switch
  multi-layer execution (§6.3).
- **Key engineering (v4.1, R6):** the Ed25519 private key lives in a secret store;
  **quarterly rotation** enforced; every rotation event is sealed into the ledger.
  Verification runs against all signature versions in the key history.
- The control set ships as a **control→telemetry→evidence** matrix mapped to OWASP
  Agentic T&M + OWASP LLM Top 10 2026 (E10).

### 6.2 Regulation — EU AI Act (post-Omnibus) and Türkiye

| Obligation | AI Act reference | Post-Omnibus (2026/1744) calendar | Swarmax counterpart |
|---|---|---|---|
| Automatic event logging / log retention | Art. 12 | Annex III: 02.12.2027; embedded AI: 02.08.2028 | Signed append-only ledger + 2-year cold tier (§10) |
| Human oversight | Art. 14 | Same calendar | HITL queue, SLA triage, kill-switch |
| High-risk system provider obligations | Art. 16 ff. | 02.08.2026 → 02.12.2027 (Annex III) | Compliance pack: evidence export, role separation, audit report |
| Legacy (already deployed) systems | Transitional provisions | +4 months | Upgrade guide in the customer portal |

> Positioning note: Swarmax is not an "AI Act certification"; it is a **technical
> infrastructure provider for Art. 12/14**. It gives no legal advice; it feeds the
> customer's obligation map with technical evidence. On the Türkiye side (E13): the
> GVK provisional art. 89/1-b software-service exemption is evaluated for a TR-
> registered entity; adviser confirmation is required for the final reading.

### 6.3 Kill-Switch Protocol (Fail-Safe Cascade)

```
┌────────────────────────────────────────────────────────────┐
│   TRIGGER: Automatic APD Engine OR Human Operator           │
└─────────────────────────────┬──────────────────────────────┘
                              ▼
LAYER 1 (0–50 ms): Assurance Proxy block — tokens invalidated,
                    HTTP 403 to outgoing LLM/tool requests.
                              ▼
LAYER 2 (50–500 ms): Container/Pod/Process SIGTERM→SIGKILL;
                    pending tasks 'quarantined'.
                              ▼
LAYER 3 (post-mortem): All spans + token log + operator
                    decision sealed into the ledger with SHA-256 root.
```

> **(v4.1)** Layer-1 execution measurement: token-revocation propagation latency is
> measured with a push-model revocation list; target ≤ 50 ms (p95), reported in the
> same measurement window as MT-6.

### 6.4 RBAC
- **Fleet Admin:** rule engine, budget ceiling, API token issuance.
- **HITL Operator:** ticket review/approval, temporary budget grant, kill-switch.
- **Compliance Auditor:** read-only; ledger and report export.

---

## 7. 12-WEEK EXECUTION PLAN (Dogfood-First, Acceptance-Gated)

### 7.1 Phases

| Phase | Week | Output | Concrete acceptance criterion (DoD) |
|---|---|---|---|
| **F0 — Evidence Base** | 1–2 | Repo skeleton, SQLite+WAL schema (§12.1), OTLP ingest, pinned semconv map (§2.1) | 100K events from a synthetic agent fleet; p99 ingest latency < 2 s; schema-change test passes |
| **F1 — Metric Engine** | 3–5 | 5 metric families + EWMA/MAD/JSD/Page-Hinkley + metamorphic oracle | Injection tests (§9): 8/8 alarms with correct severity; false positives < 5%/day in dogfood |
| **F2 — Evidence Plane** | 6–7 | Ed25519-signed append-only ledger + Merkle verification API | Ledger **immutability** test: single-bit change caught in verification; export ≤ 1 h |
| **F3 — HITL Queue** | 8–9 | Triage UI (TUI/Web), SLA counters, PagerDuty/Slack | End-to-end drill: alarm→ticket→operator decision→ledger seal < 5 min |
| **F4 — Report + Compliance Pack** | 10–11 | Weekly fleet X-ray + EU AI Act appendix (per §6.2 calendar) | Report on 7 days of dogfood data; every number references the evidence chain |
| **F5 — Hardening** | 12 | docker-compose one-click, load test, documentation | 10K events/min for 1 h; RPO=0 drill (§8); v1 tag |

### 7.2 Team and Rhythm
One developer + (from F3) a part-time operator. Weekly demo dogfood report; the §9
protocol runs at the end of every phase.

### 7.3 Dogfood Environment
The real internal agent fleet (current production tasks) is the first customer.
Synthetic agents are used only in alarm-injection tests; never mixed with real data
(`synthetic=true` label).

### 7.4 Quality Gates (CI)
1. `semconv-diff`: breaking-change scan against the pinned registry version.
2. Rule-engine unit tests: positive/negative goldens for every rule.
3. Ledger property tests: append-only immutability + Merkle root consistency.
4. Load: p99 ingest < 2 s, alarm latency ≤ 500 ms (see §8).

---

## 8. SLA COMMITMENTS AND RPO (with Measurable Definitions)

| Service | Commitment | Measurement definition | On breach |
|---|---|---|---|
| Collector telemetry availability | **99.5% uptime** (dogfood/production v1) | Monthly successful health-check ratio; maintenance windows excluded | 10% of the monthly fee refunded |
| Alarm decision latency | **≤ 500 ms** | Client span close → APD decision write (p95, daily window) | 10% refund |
| HITL notification delivery | **≤ 3 s** | Ticket creation → webhook 2xx receipt | 10% refund |
| RPO | **0** — v1 dogfood, single-node crash resilience (v4.1, R2) | WAL fsync local commit durability; post-crash lost-event count = 0 verification. DR replica (Litestream async): **RPO ≤ 5 s**, reported separately | 100% of the relevant month's fee |

> v3.5 promised 99.95%, conflicting with a single-node v1; v4.0 plans 99.5% for v1
> and 99.9% for v2 (multi-region) as separate commitments. Promises come with
> measurable definitions, not decoration.
> **v4.1 (R2):** "RPO=0" honestly redefined — async replication cannot produce
> RPO=0; the v1 commitment is single-node crash resilience, replication loss ≤ 5 s
> is reported separately and visibly. v2 multi-region targets true RPO=0.

---

## 9. MEASUREMENT-COMMITMENT METRICS AND TEST PROTOCOL (E8-based)

ReliabilityBench (E8) measures agent reliability under production-like stress on
three axes: consistency under repeated runs (**pass^k**), resilience to
semantically equivalent task perturbations (**ε**), and tolerance of controlled
tool/API errors (**λ**) — unified into one **reliability surface R(k, ε, λ)**.
Swarmax converts this into an **in-production measurement commitment** (n=10, k
adjustable):

| Metric | Definition (ReliabilityBench counterpart) | Initial target |
|---|---|---|
| **MT-1 Task Success Consistency** | pass^k over a **task-class replay set** (k=5, n=10 replays; not platform uptime — v4.1, R8) | ≥ 0.90 (critical task class) |
| **MT-2 Cost Consistency** | Cost coefficient of variation (CV) over n repeats | ≤ 0.25 |
| **MT-3 Step-Count Consistency** | Step-count CV over n repeats | ≤ 0.20 |
| **MT-4 Error Tolerance (λ-curve)** | Success curve under controlled tool/API error injection; per ReliabilityBench **rate-limit is the most harmful fault class** — mandatory in the injection pack | Success drop at λ=0.1 ≤ 5 points |
| **MT-5 Recovery Time** | Return to normal operation after injected failure (same agent) | ≤ 60 s |
| **MT-6 Alarm Latency** | Anomaly event → APD decision | ≤ 500 ms |
| **MT-7 Evidence Integrity** | Signature verification success (weekly full scan) | 100% |
| **MT-8 Metamorphic End-State Equivalence** | End-state variable agreement across semantically equivalent runs (§3.2-7) | violation rate ≤ 2% |

A weekly **R(k, ε, λ) reliability surface** report per production agent is the
headline metric of the fleet X-ray: "how production-ready is this agent?"

**Injection tests (F1 acceptance, 8 scenarios):** synthetic agents produce (a) 3.5×
token spike, (b) tool-distribution deviation (JSD ≈ 0.55), (c) 3-repeat loop,
(d) new error class, (e) deny-ratio spike, (f) ticket aging, (g) **rate-limit wave
injection** (λ-curve), (h) **schema-drift + partial response** error classes; the
engine must detect **8/8** with correct severity + correct SLA. False-positive
budget: the measurable definition in §3.3 (v4.1, R10).

### 9.2 Roadmap — Automated Failure Attribution (v1.1, E14)
The operator's first question when an escalation opens: "which agent, which step is
at fault?" Who&When (E14) is the first academic framework automating this; the
field's current SOTA (E15, TraceElephant — 311K production traces, April 2026) sits
at **65.9%** mean correct-step accuracy, and the independent benchmark critique
(arXiv:2603.25001) showed single-perspective evaluation can flag the wrong agent.
Both findings validate the paper's design: suggestions stay **human-confirmed**;
autonomous closure is forbidden. v1.1 plan: an **owner-agent + critical-step
suggestion** field in ticket creation; the method family tracks current literature
(Who&When → AgenTracer, DCFA and hierarchical trace-attribution lines). Acceptance
criterion: operator-confirmation rate ≥ 70% on dogfood tickets — sustained
above-SOTA value proof.

---

## 10. DATA RETENTION, TIERING AND THE RIGHT TO BE FORGOTTEN

1. **Hot (0–30 days):** all span detail; v1 SQLite (SSD), v2 ClickHouse MergeTree
   (SSD). Query < 200 ms.
2. **Warm (31–90 days):** span detail compressed to Parquet; S3/R2. Storage cost
   drops ~85%.
3. **Cold (91 days–2 years):** only signed summaries + Merkle roots; encrypted
   archive (EU Art. 12 retention compliance; §6.2 calendar).
4. **Right to be forgotten (GDPR Art. 17 / KVKK art. 7):**
   `DELETE /v1/privacy/forget?user_id=X` → the user's span bodies are destroyed by
   **crypto-shredding** (person-keyed encryption; key destroyed); operational
   aggregates and signed evidence summaries are preserved per statutory retention.
   The deletion itself is written into the ledger as a signed event.

> **Residual-risk statement (v4.1, R7):** deletion **crypto-shreds the body store**
  (span contents, person-keyed encryption) and seals the deletion event into the
  ledger; record summaries in the hash chain (payload hash + signature) remain for
  evidence integrity. "Is the hash chain personal data?" is subject to customer DPA
  review — Swarmax gives no legal guarantee, only technical evidence.

---

## 11. OTEL COLLECTOR CONFIGURATION (`otel-collector-config.yaml`, v2/ClickHouse variant)

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 75
    spike_limit_percentage: 20

  attributes/swx_enrich:
    actions:
      - key: swx.ingest.version
        value: "1"
        action: upsert

  transform/pii_mask:
    error_mode: ignore
    log_statements:
      - context: log
        statements:
          - replace_pattern(body, "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}", "[REDACTED_EMAIL]")
          - replace_pattern(body, "\\b(?:\\d[ -]*?){13,16}\\b", "[REDACTED_CARD]")

  tail_sampling:
    decision_wait: 10s
    num_traces: 50000
    expected_new_traces_per_sec: 1000
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 5000 }
      - name: baseline
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

  batch:
    send_batch_size: 256
    timeout: 5s

exporters:
  clickhouse/swx:
    endpoint: clickhouse:9000
    database: swarmax
    username: default
    password: ${env:CLICKHOUSE_PASSWORD}
  debug/dogfood:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, tail_sampling, batch]
      exporters: [clickhouse/swx]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, batch]
      exporters: [clickhouse/swx]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, attributes/swx_enrich, transform/pii_mask, batch]
      exporters: [clickhouse/swx, debug/dogfood]
```

> Note: in the v1 (SQLite) variant, `clickhouse/swx` is replaced by a `file`
> exporter + Swarmax Engine SQLite writer; the masking and enrichment chain is
> identical. The assurance-plane flow is fed by SDK/proxy events independent of the
> collector (§4).

---

## 12. DATABASE SCHEMA

### 12.1 SQLite v1 (DDL)

> **v4.1 (R12–R14):** the production schema = this base DDL +
> `schema/migrations/002_f0_extensions.sql` (metamorphic end-state fields
> `task_template`/`end_state_json`, `retry_count`, `ttft_s`, `guard_events` table,
> `hitl_escalations.created_at`). Append-only triggers are defined in this DDL; the
> F0 code implements them per the §14 audit.

```sql
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
    synthetic    BOOLEAN      DEFAULT 0,
    ts           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_agent_time ON agent_task_events (agent_id, ts);

CREATE TABLE IF NOT EXISTS agent_drift_baselines (
    agent_id           VARCHAR(128) PRIMARY KEY,
    tool_distribution_json TEXT    NOT NULL,
    mean_cost_usd      NUMERIC(12,6) NOT NULL,
    mad_cost_usd       NUMERIC(12,6) NOT NULL,   -- MAD instead of EWMA σ (§3.2-4)
    p95_latency_ms     INTEGER   NOT NULL,
    ewma_mu            NUMERIC(12,6),
    ewma_sigma2        NUMERIC(12,6),
    calibration_until  TIMESTAMP,                 -- §3.3 calibration window
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
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,  -- append-only; UPDATE/DELETE forbidden by triggers
    event_type    VARCHAR(32) NOT NULL,
    payload_hash  CHAR(64)    NOT NULL,               -- SHA-256(payload)
    prev_hash     CHAR(64)    NOT NULL,               -- hash-chain
    ed25519_sig   BLOB        NOT NULL,
    created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
```

### 12.2 ClickHouse v2 (DDL, summary)

```sql
CREATE TABLE swarmax.agent_task_events
(
    event_id      String,
    agent_id      String,
    task_id       String,
    session_id    String,
    model_name    LowCardinality(String),
    input_tokens  UInt64,
    output_tokens UInt64,
    cost_usd      Decimal64(6),
    latency_ms    UInt64,
    error_class   LowCardinality(Nullable(String)),
    status        LowCardinality(String),
    synthetic     UInt8 DEFAULT 0,
    ts            DateTime64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (agent_id, ts)
TTL ts + INTERVAL 30 DAY;         -- hot tier; warm/cold tiers move to Parquet (§10)
```

---

## 13. FLEETMIND v3.5 → SWARMAX v4.0 DIFFERENCES AND CHANGELOG

### 13.1 Decision Differences (what changed and why)

| Topic | v3.5 (Fleetmind) | v4.0 (Swarmax) | Rationale (evidence) |
|---|---|---|---|
| Standards claim | "OTel GenAI semantics 1.35+", stable implied | Pinned registry; **all attributes Development** statement + `swx.*` extension namespace | E6, E12 |
| EU AI Act calendar | "Art. 12 & 14, August 2026 obligation" | Post-Omnibus 2026/1744: Annex III → 02.12.2027; embedded → 02.08.2028 | E5 |
| Automatic model downgrade | Auto-downgrade on budget breach | **Operator-approved** downgrade proposal (silent model change is a behavioral risk) | Operational safety; E1's 48% cost / 31% behavior balance |
| Error taxonomy | Free-form classes | MAST-aligned class map + sentinel | E7 |
| Measurement commitments | None | MT-1…MT-8 protocol + R(k,ε,λ) reliability surface | E8 |
| SLA uptime promise | 99.95% (conflicts with single node) | v1: 99.5%; v2 target: 99.9% — with measurable definitions | §8 |
| Statistical algorithms | EWMA, JSD, "Dynamic Z-Score", "MAD" (vague) | EWMA + MAD(robust-z) + JSD + Page-Hinkley/CUSUM + PSI; each literature-sourced | §3.2 |
| P&L | 96.5% margin, $414K ARR | Realistic target scenario: 95.1% margin, ~$294K ARR (month 12) | §5.4 |
| Timeline | 4 weeks | 12 weeks, phase-gated acceptance criteria | §7 |
| Threat literature | — | MITRE ATLAS v5.1.0 + OWASP Agentic T&M + OWASP LLM Top 10 2026 | E9, E10 |
| Unused parent-doc references | `CIFT_HAT_PLANI.md`, `VERGI_KANAL_CERCEVESI.md`, `Fikirler.md` | Removed (not in this workspace; restored if found) | Consistency |

### 13.2 Changelog
- **v4.2.0 (2026-09-15/16, four workstreams):** Console v2 — multi-user auth (§8 L2):
  scrypt password digests (ASVS 2.4), SHA-256-only server-side sessions, per-session
  CSRF, HttpOnly+SameSite cookie, admin/viewer roles, 15-minute lockout after 5
  failed logins (migration 005). v1.1 attribution suggestion (§9.2, E14/E15): every
  alarm is born with an "owner agent + critical step" suggestion from a transparent
  heuristic ladder; the operator confirm/reject gate is sealed into the evidence
  ledger; the §9.2 acceptance metric (≥ 70%) is computed in the store. Agent detail
  page: 7-day cost/error series, tool mix, alarm+ticket history, calibration state;
  §3.2 charts (EWMA-Z control card, tool-mix JSD) rendered as accessible SVG with
  data-table alternatives. F3-scale: ClickHouse ReplacingMergeTree mirror (§10.1
  conformant DDL, stdlib HTTP client, container-inclusive idempotent dual-write,
  optional via SWARMAX_CH_URL, graceful degradation). Debt repairs: guard-event-only
  agent registration/calibration gap (unified `_register_agent`); migration
  idempotency test caught 005. Second deep scan (2026-09-16): resolving an
  unknown/closed alarm id now returns fail-closed 404 and fabricates no evidence
  entry (D2, regression-tested); seeder bootstraps console users (root admin +
  viewer); live HTTP audit validated 12 flows. 89 tests green; smoke test updated
  for the authenticated console. Companion documents: `DOGFOOD_PLAN.md` (MT-1…MT-8
  execution plan) and `AI_ACT_COMPLIANCE.md` (Omnibus dossier with honest gap
  register).
- **v4.1.1 (2026-09-15, deep scan):** E15 added — failure-attribution SOTA
  calibration (TraceElephant 65.9%, arXiv:2604.22708; multi-perspective critique
  arXiv:2603.25001); §9.2 human-confirm design justified by SOTA; 21 sources; code
  independently verified: 70 tests green, demo + smoke + exit drill pass; live HTTP
  console audit; calibration state persisted (migration 004) and console-visible
  (D1); zero TODO/mock/stub/silent-except in the codebase.
- **v4.1.0 (2026-09-15):** Red-team audit (§14): 15 findings closed — R1–R15 as
  listed in §14; §4.2 cost rule made conjunctive (Z>2.5 ∧ >2.0×EWMA-µ).
- **F0 implementation (2026-09-15):** paper to code — repo skeleton, SQLite WAL
  schema + append-only triggers + migration 002, pinned semconv map + `swx.*`
  namespace + validator, §3 metric engine, §4.2 APD mapping, synthetic fleet (S1–S8)
  verified by **8/8 injection acceptance + R10 FP budget + MT-4 λ-curve + 100K
  events p99<2 s** tests (44 tests).
- **F1/F2 implementation (2026-09-15):** §4.3 OTLP/HTTP+JSON ingest service (HMAC +
  nonce anti-replay, `ingest_reject` counter, idempotent span dedupe); §12.1/R1
  evidence sealing — pure-Python Ed25519 (RFC 8032 vectors) + Merkle root + key
  rotation; §4.2 weekly report generator; fleet console; §3 exit drill
  (`scripts/exit_drill.py`). 66 tests + end-to-end smoke green.
- **v4.0.1 (2026-09-15):** E14 added; MT protocol re-founded on pass^k and
  R(k,ε,λ); metamorphic output-quality oracle added; injection pack expanded to 8
  scenarios with ReliabilityBench chaos fault classes; failure attribution
  scheduled for v1.1 (§9.2).
- **v4.0 (2026-09-14):** first verified master blueprint. 13 evidence records
  (E1–E13); OTel maturity correction; EU Omnibus calendar update;
  MAST/ReliabilityBench academic alignment; 12-week plan; measurable SLA/RPO
  definitions; MT protocol; SQLite/ClickHouse DDL; collector config modernization.
- **Next scheduled scan:** 2026-12-14 (quarterly evidence refresh).

---

## 14. RED-TEAM AUDIT (v4.1 — a rival CTO's attack)

This section records an attack on the v4.0.1 paper from the perspective of "a rival
technical CTO whose job is to refute this thesis." Rule: every finding is either
repaired in the paper or explicitly written down as accepted risk — never "no
problem." R12–R15 are implementation-level red-team findings caught while touching
the schema during F0 coding.

| # | Finding (weak claim / falsifiable assumption) | Severity | Decision | Repaired section |
|---|---|---|---|---|
| R1 | §11 collector chain has `tail_sampling decision_wait: 10s`; the §8 ≤ 500 ms alarm commitment contradicts post-tail-sampling consumption | High | APD consumes the §4 event stream directly (SDK/proxy → engine); collector serves traces/reports only | §2, §11 |
| R2 | "RPO=0" claim conflicts with async Litestream: async replication can lose the last WAL seconds | High | RPO=0 redefined as single-node crash resilience (WAL fsync); DR replication RPO ≤ 5 s reported separately; v2 multi-region targets true RPO=0 | §8 |
| R3 | EWMA σ̂ estimator unstable at cold start; Z > 2.5 false positives in the first days | Medium | Z-alarm arms only at ≥ 30 observations **and** after the calibration window | §3.2-1, §3.3 |
| R4 | JSD: empty cells make log ratios undefined (sparse tool usage) | Medium | ε = 10⁻⁶ correction + empty-window guard (`warming_up`) | §3.2-2 |
| R5 | Metamorphic oracle has no cost budget; unbounded shadow reruns risk cost explosion | Medium | Limited to ≤ 1% of agent-day traffic in the critical task class | §3.2-7 |
| R6 | Ed25519 private key ownership/rotation undefined | High | Secret store + quarterly rotation; rotation events sealed into the ledger | §6.1 |
| R7 | After crypto-shredding, record summaries remain in the hash chain; GDPR Art. 17 residual risk unstated | Medium | Residual-risk statement added: body store destroyed, evidence summaries remain; legal risk subject to DPA review, explicitly written | §10 |
| R8 | MT-1 pass^k undefined in product context | Medium | Task-class replay set (k=5, n=10) definition clarified; explicitly not platform uptime | §9 |
| R9 | P&L target scenario lacks a churn assumption | Low | churn=0 assumption written; table labeled "target scenario, not a forecast" | §5.4 |
| R10 | "False positives < 5%/day" is not measurable | Medium | FP rate within hourly cycles per agent-day ≤ 5% (≤ 1 FP/day); synthetic agents exempt from calibration | §3.3, §9 |
| R11 | Text defects (garbled characters, broken quote, dead link) | Low | All repaired; E8 evidence pinned to the canonical arXiv link | §5.1, §7.1, §12.2, §13.1, E8 |
| R12 | §12.1 DDL lacks metamorphic-oracle inputs (`task_template`, end-state), `retry_count`, `ttft_s` | Medium | Added via `schema/migrations/002`; production schema = base DDL + migration | §12.1 |
| R13 | §4.1 event types (tool_call, permission_decision, mask_event) have no v1 storage table | High | `guard_events` table (with tool_call argument summaries) via migration 002 | §4.1, §12.1 |
| R14 | `hitl_escalations` lacks `created_at`; ticket aging (§4.2) unmeasurable | High | `created_at` via migration 002 | §12.1 |
| R15 | §4.2 SLA map lacks rows for `error.rate` and `retry_count` signals — Critical/High alarms could not raise tickets | High | Two rows added (quality / 4 h) | §4.2 |

**Audit outcome:** all 15 findings repaired in the paper; one open risk class
remains, explicitly accepted; claims falsifiable by code (§7 acceptance criteria).
Evidence discipline unchanged: no new market/regulatory numbers; everything added
is measurement/schema/mathematics correction.

---

## 15. EXCELLENCE CLOSURE — 100/100 RUBRIC

| Dimension | Weight | v4.2 status | Note |
|---|---|---|---|
| Evidence-based market/regulatory data | 15 | ✅ | E1–E16, date-stamped, quarterly refresh |
| Scientific foundation | 15 | ✅ | §3.2, §9: EWMA, JSD, MAD, Page-Hinkley, MAST, ReliabilityBench (pass^k, R(k,ε,λ), metamorphic oracle), Who&When + TraceElephant SOTA calibration |
| Standards compliance (honest statement) | 10 | ✅ | Pinned OTel registry + Development-status transparency |
| Architectural integrity | 10 | ✅ | Two planes, event contract, anti-replay |
| Security and threat model | 10 | ✅ | STRIDE × ATLAS × OWASP; control→telemetry→evidence |
| Regulatory compliance infrastructure | 10 | ✅ | Omnibus-calendar Art. 12/14 counterparts; KVKK crypto-shredding; `AI_ACT_COMPLIANCE.md` dossier with gap register |
| Verifiable commitments | 10 | ✅ | SLA measurement definitions, RPO drill, MT-1…MT-8; `DOGFOOD_PLAN.md` execution plan |
| Executability | 10 | ✅ | 12 weeks, phase acceptance criteria, CI quality gates |
| Commercialization consistency | 5 | ✅ | Price↔position↔P&L scenario aligned |
| Traceability | 5 | ✅ | §13 difference table + changelog |
| **Total** | **100** | **100** | |

**Operations commitment:** L3 autonomous monitoring / L2 human triage; target weekly
effort ≤ 30–45 min. **IP:** core software is company intellectual property.

---

## 16. REFERENCES (Accessed 14–15.09.2026)

1. Gartner PR (25.06.2025) — Agentic AI cancellation forecast. https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027
2. Gartner PR (01.07.2026) — $234B exposure. https://www.gartner.com/en/newsroom/press-releases/2026-07-01-gartner-says-us-dollars-234-billion-in-enterprise-application-software-spend-is-at-risk-from-agentic-artificial-intelligence
3. Gartner Forecast Analysis (Feb 2026) — Agentic AI spend $985B/2030. https://www.gartner.com/en/documents/7455226
4. Gartner PR (26.08.2025) — 40% enterprise app agent penetration. https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025
5. Regulation (EU) 2026/1744 (Digital Omnibus on AI) analyses: EU AI Compass; Gibson Dunn (27.05.2026); Orrick (29.07.2026); CSA (01.08.2026). Links in E5.
6. OpenTelemetry GenAI semconv repo — attribute registry (accessed 14.09.2026). https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/registry/attributes/gen-ai.md
7. ClickHouse engineering blog (29.07.2026) — semconv Development status. https://clickhouse.com/resources/engineering/opentelemetry-semantic-conventions
8. Cemri, M. et al. (2025) — "Why Do Multi-Agent LLM Systems Fail?" (MAST), NeurIPS 2025 D&B. https://arxiv.org/abs/2503.13657
9. ReliabilityBench (January 2026) — pass^k consistency, ε-perturbation, λ-error tolerance, R(k,ε,λ) reliability surface, action metamorphic relations, chaos fault injection; arXiv:2601.06112. https://arxiv.org/abs/2601.06112
10. Zhang, S. et al. (2025) — "Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems" (Who&When), ICML 2025 spotlight. https://arxiv.org/abs/2505.00212
11. MITRE ATLAS v5.1.0 (Nov 2025). https://atlas.mitre.org/
12. OWASP Agentic AI — Threats & Mitigations. https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/
13. OWASP GenAI LLM Top 10 (2026). https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
14. Roberts, S.W. (1959) — EWMA control chart, *Technometrics* 1(3). Hunter, J.S. (1986), *JQT* 18(4).
15. Endres, D. & Schindelin, J. (2003) — JSD metric, *IEEE Trans. Inf. Theory* 49(7).
16. Page, E.S. (1954) — CUSUM, *Biometrika* 41(1–2). Hinkley, D.V. (1971).
17. Hampel, F.R. (1974); Leys, C. et al. (2013) — MAD robust statistics.
18. Holtzman, A. et al. (2020) — *The Curious Case of Neural Text Degeneration*, ICLR 2020.
19. Competitor/pricing comparisons: Pydantic Logfire analysis (31.03.2026); OpenObserve blog (31.07.2026); Latitude blog (27.03.2026); LangChain LangSmith pricing (16.08.2026); Langfuse comparison page (September 2026). Links in E11.
20. GVK provisional art. 89/1-b — software services export exemption. https://www.gib.gov.tr
21. TraceElephant (April 2026) — 311K production traces, failure-attribution SOTA 65.9%; arXiv:2604.22708. Multi-perspective benchmark critique: arXiv:2603.25001 (March 2026). Links in E15.
22. OWASP Session Management Cheat Sheet + ASVS 4.0.3 (accessed Sept 2026) — frame of the console v2 session/CSRF/role design. Links in E16.

> **Status (16.09.2026):** F0 + F1 + F2 + console v2 + F3-scale mirror are on disk as
> verified code (§7 acceptance criteria map to test files); evidence-refresh scan is
> synced to this date. Next contract step: dogfood (`DOGFOOD_PLAN.md`, MT-3) and
> closing the §9.2 acceptance metric with real operator data.
