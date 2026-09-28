# 01 — Agent fleet observability (2025–2026)

What the literature actually establishes, and what it means for Swarmax.
Sources fetched 2026-09-28 from the arXiv API.

---

## AGATE — provenance and execution evidence at the harness boundary

**Zhang et al., "AGATE: Provenance-Based Runtime Defense Against
Compositional Attacks on LLM Agents", arXiv:2609.30830, 2026-09-25.**
https://arxiv.org/abs/2609.30830

The closest academic relative to Swarmax's design. Verbatim from the
abstract:

> "an authorization and data-provenance gate at instrumented agent-harness
> boundaries … Source registration connects observed inputs to subsequent
> transfers, while an **effect ledger tracks repeated requests**. Deterministic
> checks make decisions without an LLM in the decision path and **retain their
> grounds with execution evidence for forensic replay**."

Why it matters to us:

- The **effect ledger** is the same primitive as our evidence ledger — a
  durable record of what the agent did, kept for after-the-fact proof, not
  for steering the model. Convergent independent design is the strongest
  validation available without a citation.
- **"Without an LLM in the decision path"** is exactly our fail-closed
  philosophy: alarms are deterministic thresholds over measured facts
  (`metrics/apd.py`), not a second LLM opining on the first one. We should say
  this out loud — it is a real differentiator against "AI watching the AI"
  products.
- AGATE integrates three production harnesses via adapters "without modifying
  host code". That is the same integration thesis as our OTLP signing relay
  and Langfuse bridge: do not touch the app, sit at the boundary.
- **Honest caveat:** AGATE's authors found "six of eleven benign
  file-processing scenarios contain denial events" — provenance policies have
  a real utility cost. Swarmax's equivalent risk is false-positive alarms;
  that is why the ≤ 5 % false-positive budget exists as a *measured* gate and
  not a hope.

---

## FRAIL — fleet-level failure is invisible per-agent

**Fu, Xu & Ren, "Financial Fragility in Societies of LLM Agents: Coordination
Failures and Stabilizing Mechanisms", arXiv:2609.30940, 2026-09-25.**
https://arxiv.org/abs/2609.30940

Agents that are each individually safe, jointly failing:

> "Across seven leading LLMs, we find widespread collective fragility even
> when no agent is instructed to destabilize the system: **77% of baseline
> bank-run episodes and 83% of debt-rollover episodes end in failure** …
> individually capable agents do not automatically form safe [systems],
> highlighting **system-level evaluation** … as central problems."

Why it matters to us:

- This is the empirical backbone of our positioning sentence. A per-run trace
  of each agent in a failing FRAIL episode looks fine; the failure lives in
  the *interaction*. Anything that only shows you one trace at a time cannot
  see it.
- It justifies fleet-scoped aggregates as first-class: our rolling windows,
  per-agent facts and cross-agent drift (JSD tool-mix) exist precisely to make
  the interaction visible.
- It also marks the limit: FRAIL studies emergent *coordination* failure.
  Swarmax detects the symptoms (drift, loops, error-rate, cost spikes), not
  the game-theoretic cause. Do not claim we "prevent emergent
  miscoordination" — we make it visible while there is still time to act.

---

## DeceptGuard — what can and cannot be observed about an agent

**Mukhopadhyay, "DeceptGuard: A Constitutional Oversight Framework For
Detecting Deception in LLM Agents", arXiv:2603.13791, 2026-03-14.**
https://arxiv.org/abs/2603.13791

Three monitoring regimes compared — black-box (actions/outputs only),
CoT-aware, and activation-probe:

> "CoT-aware and activation-probe monitors substantially outperform their
> black-box counterparts (mean pAUROC improvement of +0.097) … as agents learn
> to suppress overt behavioral signals, chain-of-thought becomes the primary
> detection surface but is itself increasingly unreliable due to
> **post-training faithfulness degradation**."

Why it matters to us — it draws the honest boundary of Swarmax's reach:

- Swarmax is a **black-box** monitor by construction: it sees events the agent
  emits (tool calls, tokens, costs, errors), not hidden states or faithful
  reasoning. DeceptGuard quantifies what that costs (~0.1 pAUROC) against
  internal-signal monitors.
- So we must never claim to detect deception, scheming or intent. We detect
  *behavioural* signatures: loops, drift, error-rate, cost anomalies. That is
  a smaller, true claim.
- The corollary is a product boundary, not a weakness: Swarmax consumes what
  the framework exports, so it works with any provider and any model —
  including closed-weight ones where activation probes are impossible. That
  portability is worth more than +0.097 pAUROC for a fleet product.

---

## WhatWorkedBench — agents are weak at knowing what they did

**Ning et al., "WhatWorkedBench: Benchmarking Experimental Understanding in
AI Agents", arXiv:2609.27490, 2026-09-23.** https://arxiv.org/abs/2609.27490

Agents must "submit a response surface, a table predicting scores for every
configuration"; effect recovery from observations is low (0.632 → 0.698 with
a Gaussian process fit).

Why it matters to us: agents are unreliable narrators of their own behaviour
and impact. The operational consequence is that you cannot ask the agent what
it did — you have to have measured it independently. That is the whole reason
an evidence layer exists outside the agent. It also argues for our
metamorphic end-state oracle: assert properties of the outcome, do not trust
the agent's self-report.

---

## Gap statement — what the literature does not give us

Being explicit about what we could not find, because it is also our
opportunity:

- No 2025–2026 paper we found ships a **tamper-evident, offline-verifiable
  evidence store as a product** for agent fleets. AGATE has the ledger; it is
  a defense paper, not a deployable service with an SLA queue and a `/forget`
  endpoint. The gap between "effect ledger in a paper" and "sealed store an
  auditor can run a drill against" is where Swarmax lives.
- We did not find fleet-observability benchmarks that measure **detection
  latency** under realistic event mixes; our own p99-ingest and alarm
  gates are the only evidence we have, and they are self-reported.
- The one-pager cites a NeurIPS-2025 failure taxonomy (MAST); a direct arXiv
  record for it could not be located in this session, so it is not cited
  here. Do not quote it in external copy until it is verified at the source.
