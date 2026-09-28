# 02 — Measuring and attacking the cost of AI agents

Sources fetched 2026-09-28 from the arXiv API.

---

## FragToken — covert inference-cost inflation as an attack surface

**Wang et al., "FragToken: Amplifying LLM Inference Costs through
Noncanonical Token Generation", arXiv:2609.31552, 2026-09-25.**
https://arxiv.org/abs/2609.31552

The single most useful paper for our pricing page. From the abstract:

> "an attacker can train the model to favor such sequences, systematically
> increasing the number of autoregressive decoding steps **without a
> proportional increase in visible response length** … Across the four models,
> FragToken achieves a three-benchmark average **token inflation ratio (TIR)
> ranging from 1.99 to 2.46**, while causing only minor degradation in model
> utility."

What it changes about how we talk about cost tracking:

- Cost inflation is an **attack**, not just waste. It survives naive
  monitoring because the visible response length is unchanged — the inflation
  is in the token stream, which only the telemetry layer sees.
- Our cost alarm (`daily cost > 2× EWMA ∧ robust Z > 2.5`) is calibrated for
  exactly this regime: a ~2× step change against an EWMA baseline with a
  robust z-score. FragToken's 1.99–2.46× TIR sits squarely inside the
  detector's sensitivity band.
- **The copy implication:** stop describing cost tracking as a budgeting
  feature. It is a security control. "What did it cost?" and "is someone
  inflating the bill?" are the same measurement.
- **The honest limit:** FragToken is a training-time/supply-chain attack (the
  model itself is modified), so Swarmax detects the *symptom* in your
  spend; it does not attribute it to a poisoned model. Say that.

---

## Sparse multi-agent debate — the accuracy/cost frontier

**"Do We Need Complex Topology Control? Distinct-Peer Random Routing Improves
Cost-Efficiency in Sparse Multi-Agent Debate", arXiv:2609.27150,
2026-09-22.** https://arxiv.org/abs/2609.27150

> "a simple random-without-replacement routing policy … consistently improves
> the accuracy-cost trade-off of sparse MAD."

Why it matters: multi-agent topologies are being chosen on an accuracy-cost
curve. The people making that choice need the cost half of the curve
*measured*, per agent, per round — which is what Swarmax's per-agent cost
series provides. A fleet that debates in rounds has a cost structure visible
only at the fleet level (round-by-round, agent-by-agent), which is our exact
grain.

---

## KITE — inference cost as a first-class architectural metric

**Hu et al., "KITE: KV-Inariant Transformer Expansion for Efficient Agentic
LLM Scaling", arXiv:2609.27294, 2026-09-23.**
https://arxiv.org/abs/2609.27294

> "the architectural choice determines how much computation is spent during
> training, prompt processing, and autoregressive decoding … [SST] reduces
> estimated inference cost by 6.7% and 31.6%."

Context, not a Swarmax citation: inference cost is now a headline
architectural objective for model builders, which means buyer-side cost
pressure is structural, not seasonal. The model-side work (KITE) lowers cost
per token; our work (Swarmax) makes the *fleet-level* cost legible so an
operator can tell whether the savings actually arrived. These are
complementary — mention it in investor conversation, not in the README.

---

## What Swarmax actually measures (and does not)

Stated precisely so external copy stays honest:

- **Measured:** per-task `input_tokens` / `output_tokens` / `cost_usd` /
  `latency_ms`, as reported by the agent's own emission, mapped from pinned
  `gen_ai.usage.*` semconv plus our `swx.*` extensions (cache-read tokens enter
  the cost model, since cache hits are not free to compute).
- **Derived:** EWMA cost control cards, robust MAD-based z-scores, per-agent
  daily cost series, the alarm map in `metrics/apd.py`.
- **NOT measured:** per-turn quality, prompt-level statistics (we deliberately
  do not store raw prompts), or true provider billing. Our `cost_usd` is a
  *reported estimate*; reconciliation against the provider invoice is the
  operator's job. If a customer needs invoice-true cost accounting, that is a
  paid-tier feature we should scope, not a claim we make now.

---

## Open question worth tracking

FragToken's threat model is a compromised model. A natural follow-up for us:
a **canary-task cost baseline** — a fixed, known-cost workload run on a
schedule whose cost is compared against the model's historical distribution.
That would catch supply-chain inflation even when no real traffic exists to
compare against. It is a small addition to `metrics/` and would make a
credible Pro-tier feature. Not built yet; do not advertise it.
