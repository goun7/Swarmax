# Research notes — Swarmax

Working research file for the positioning and the technical claims. Every
source below was fetched directly (arXiv API or the vendor site) on
2026-09-28; abstracts are quoted from the primary record, not from a search
snippet. If a claim in our copy cannot be traced to one of these, it does not
go in the README.

Kısa özet (TR): Dört alan tarandı — (1) ajan filo gözlemlenebilirliği,
(2) ajan maliyeti, (3) Postiz pivot modeli, (4) AI Act kanıt/uyum. En önemli
bulgu: akademik literatür Swarmax'ın tezini doğruluyor — AGATE (arXiv
2609.30830) bağımsız olarak "etki defteri + adli tekrar oynatma" mimarisi
öneriyor; FragToken (2609.31552) token maliyetini gizlice 2-2.5× şişiren
saldırılar gösteriyor ki maliyet alarmı bir lüks değil güvenlik gereği;
FRAIL (2609.30940) bireysel olarak güvenli ajan karalarının sistem düzeyinde
nasıl çöktüğünü kanıtlıyor (filo düzeyinde izleme şart).

## Files

| File | Topic |
|---|---|
| [01-fleet-observability.md](01-fleet-observability.md) | Agent fleet observability & runtime evidence (2025–2026) |
| [02-agent-cost.md](02-agent-cost.md) | Measuring and attacking the cost of AI agents |
| [03-postiz-pivot-model.md](03-postiz-pivot-model.md) | The "X for AI agents" pattern and how Swarmax applies it |
| [04-compliance-evidence.md](04-compliance-evidence.md) | EU AI Act record-keeping and what counts as evidence |

## Sources verified this session

| # | Source | Link | Date |
|---|---|---|---|
| 1 | AGATE: Provenance-Based Runtime Defense Against Compositional Attacks on LLM Agents | https://arxiv.org/abs/2609.30830 | 2026-09-25 |
| 2 | Financial Fragility in Societies of LLM Agents (FRAIL) | https://arxiv.org/abs/2609.30940 | 2026-09-25 |
| 3 | FragToken: Amplifying LLM Inference Costs through Noncanonical Token Generation | https://arxiv.org/abs/2609.31552 | 2026-09-25 |
| 4 | KITE: KV-Invariant Transformer Expansion for Efficient Agentic LLM Scaling | https://arxiv.org/abs/2609.27294 | 2026-09-23 |
| 5 | Do We Need Complex Topology Control? (sparse multi-agent debate cost-efficiency) | https://arxiv.org/abs/2609.27150 | 2026-09-22 |
| 6 | WhatWorkedBench: Benchmarking Experimental Understanding in AI Agents | https://arxiv.org/abs/2609.27490 | 2026-09-23 |
| 7 | DeceptGuard: A Constitutional Oversight Framework For Detecting Deception in LLM Agents | https://arxiv.org/abs/2603.13791 | 2026-03-14 |
| 8 | Postiz — The Agentic Social Media Scheduling Platform | https://postiz.com | accessed 2026-09-28 |
| 9 | Regulation (EU) 2024/1689 (AI Act), esp. Art. 9/12/14 | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | in force |

## The three findings that matter most for the product

1. **The evidence-ledger pattern is independently emerging in the literature.**
   AGATE (2026) puts an "effect ledger" at the agent-harness boundary, keeps
   "execution evidence for forensic replay", and makes decisions *without an
   LLM in the decision path*. Swarmax's sealed evidence ledger is not a
   marketing invention — it is convergent with where the field is going. Our
   differentiation is that ours is Merkle-sealed and offline-verifiable, and
   that we sell it as a product rather than shipping it inside a defense
   paper.

2. **Cost monitoring is a security control, not a budgeting nicety.** FragToken
   (2026) shows an attacker can inflate inference cost ~2.0–2.5× *covertly*
   (token inflation ratio 1.99–2.46 across four LLMs) while preserving model
   utility, so it is not visible in the response length. Swarmax's
   cost-anomaly alarm (daily cost > 2× EWMA ∧ Z > 2.5) is exactly the
   detector this threat needs — and the README should say so, because it
   converts "cost tracking" from a finance feature into a security feature.

3. **Fleet-level failure is real and is not visible per-agent.** FRAIL (2026)
   shows individually protective agent decisions producing system failures —
   77% of baseline bank-run episodes and 83% of debt-rollover episodes end in
   failure with *no agent instructed to destabilise*. This is the empirical
   argument for fleet-level (not per-run) monitoring, and it is the single
   best academic support for our "the framework shows you a trace, nobody
   shows you the fleet" positioning.
