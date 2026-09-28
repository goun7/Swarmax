# Swarmax — Landing Page (single page)

Public page draft. Owner decision pending on pricing tier names and numbers
(see the note under the pricing table). Keep the copy hype-free: every claim
below maps to a command or a test in the repository.

---

## Hero

> **Your AI agents are in production. Can you prove what they did?**
>
> Swarmax is the audit and operations layer for AI agent fleets. Sealed
> evidence, SLA-alarmed triage, and AI-Act-ready erasure — in one
> zero-dependency Python service that sits beside the framework you already
> use.

**[ Audit your AI agents → ]** · **[ Read the code → ]** · Apache-2.0 ·
zero runtime dependencies · 171 tests, all green

---

## The 30-second pitch

Every team running autonomous agents gets asked the same three questions.
The framework answers none of them.

| The question | Dashboards | Swarmax |
|---|---|---|
| *Is the fleet working?* | one trace at a time | fleet-wide drift, loop and error alarms, each with an SLA clock |
| *What did it cost?* | one aggregate bill | cost per agent, per task, per tool loop |
| *Can you prove it?* | a screenshot (mutable) | an offline-verifiable, timestamped evidence chain |

**Positioning.** Datadog is how you know your services are healthy. Swarmax
is how you know your *agents* are — and how you prove it. Frameworks
(LangGraph, CrewAI, AutoGen…) build fleets; nobody operates them. That gap is
the product.

---

## How it works (three steps, no rip-and-replace)

1. **Emit what you already have.** If your stack exports OpenTelemetry, point
   it at the signing relay. If you use Langfuse, run the pull bridge. Nothing
   in your app changes.
2. **Watch the fleet.** Swarmax ingests, computes per-agent facts and raises
   alarms with deadlines — a runaway tool loop is Emergency/30 min, an unseen
   error class is Critical/24 h.
3. **Prove it.** The ledger seals periodically under Ed25519 + Merkle, with
   optional RFC 3161 counter-signatures from an independent timestamp
   authority. Hand the chain to an auditor; it verifies offline.

---

## The 10-second demo (film script)

Three cuts, one story: **see it → drill in → prove it.**

| Time | Cut | What appears on screen | What the viewer hears |
|---|---|---|---|
| 0.0–3.5 s | Terminal → browser | `make seed && make console`; the fleet console opens on the **SLA queue**: open alarms with live countdowns, severities colour-coded | "Every alarm has a deadline. The clock, not a human, decides when it escalates." |
| 3.5–7.0 s | Agent drill-down | Click a red alarm → the agent page: EWMA-Z and tool-mix JSD charts (accessible SVG with data tables), cost line ticking up | "One page per agent: cost, drift, error mix — the fleet's vitals, not one trace." |
| 7.0–10.0 s | Terminal | Edit a row in the ledger by hand → `make drill` prints **chain_ok=False**, verification FAILS in red | "Tamper with the evidence and the chain breaks. That is what an auditor buys." |

End frame: the Swarmax mark + "Prove what your agents did."

Props needed: one laptop, one terminal, one browser. No camera cuts beyond
the three above — the product is the whole demo.

---

## Pricing (proposed — owner decision pending)

Open core, Apache-2.0. The free tier is the full monitoring product, not a
crippled one; paid tiers sell **proof and operations**, not features.

| Tier | Price | Agents | What you buy |
|---|---|---|---|
| **Open Core** | **$0** forever | unlimited (self-hosted) | full monitoring, alarms, console, crypto-shredding — Apache-2.0 |
| **Pro** | **$29 / mo** | 5 | sealed evidence + RFC 3161 counter-signatures + weekly report e-mail |
| **Team** | **$99 / mo** | 25 | OIDC SSO, SLA escalation queue, e-mail reports, priority support |
| **Fleet + Proof** | $599 / mo | 50 | evidence delivery package + auditor portal + independent verification API |
| **Enterprise** | from $2,400 / mo | BYO | SAML / SIEM / HA (written only after a paid pilot proves the need) |

**Why a $29 entry point.** Postiz validated $29/mo as the price an individual
developer pays without asking anyone. Swarmax's buyer is different — the
person answerable for the agents — but the $29 tier still works as the
"upgrade from self-signed evidence" step: it is cheap enough to expense, and
it is the first tier where the proof is worth more than the price.

**Open decision (flag for the owner):** the strategy doc prices Team at
$199/mo. The $29–$99 spread above follows the Postiz model from the brief and
gives a lower, frictionless first paid step. If the evidence-trust position
holds, $199 for Team is defensible and lifts MRR faster — but it pushes the
first paid conversation up the ladder. Pick one; the table above assumes the
brief's model. Unit economics in the strategy doc (88–95 % margin,
breakeven at 1 customer) survive either choice.

---

## Social proof — honest version

There are no customer logos yet. Until there are, say exactly this:

> Swarmax is in dogfood. The measurement protocol (MT-1…MT-8) and its results
> are public in the repository, and the 10 M-event scale gate ran on real
> hardware (worst per-agent query 78 ms). No paying customers yet — we would
> rather show you the drill than a logo wall.

Do not fill this section with invented testimonials.

---

## FAQ (answers an honest buyer asks)

**Does it run my agents?**
No. It has no LLM client and sits out of the request path. It watches the
events your framework already emits.

**What if I am already on Langfuse / LangSmith / OpenTelemetry?**
Keep it. Run the Langfuse pull bridge or the OTLP signing relay; Swarmax
consumes from them and adds the evidence layer on top.

**Is the evidence legally meaningful?**
Seals are RFC 8032 Ed25519 over a Merkle root, optionally counter-signed by
an external RFC 3161 timestamp authority and verifiable with `openssl
ts -verify`. That is real cryptographic proof of *what was recorded and that
it has not changed* — it is not proof that the record reflects reality
(garbage in, sealed garbage out). Say it that way.

**What does it NOT do?**
It does not score answer quality, replay tasks, act as a model gateway, or
run multi-node active-active yet. One sealed store per fleet is the honest
unit today. Full list in the README's "Scope and limits".

**How do I leave?**
`make drill` runs the quarterly exit drill: export → rebuild on a clean store
→ verify. Exit 0 means your evidence leaves with you intact.

---

## Call to action

> **Audit your AI agents before someone else asks to.**
>
> ```bash
> git clone https://github.com/goun7/Swarmax.git
> cd Swarmax && pip install -e . && swarmax-init && make console
> ```

Primary CTA: **[ Run the compliance drill ]** (`make compliance-drill`, exit 0
= PASS, re-runnable).
Secondary CTA: **[ Read the design record ]** (`SWARMAX_EN.md`).

---

## Page notes for the builder

- Hero image: `assets/banner-v2.png`; mark: `assets/logo-mark-256.png`.
- Keep the three-column comparison table above the fold; it is the whole
  pitch in one scan.
- The pricing table is the only section that must not be published until the
  owner resolves the $99 vs $199 Team question.
- No motion, no auto-playing video, no fake "trusted by" strip. The product
  is a compliance tool; the page should read like one.
