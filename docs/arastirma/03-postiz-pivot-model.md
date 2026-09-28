# 03 — The Postiz pivot model and how Swarmax applies it

The brief directs us to study Postiz's "7× pivot" path and its "X for AI
agents" positioning. Postiz's own site (fetched 2026-09-28) is the primary
evidence for what the pattern looks like when it is done well.

---

## What Postiz actually does today

Source: https://postiz.com (accessed 2026-09-28). Verbatim from the page:

> "**Postiz: The Agentic Social Media Scheduling Platform**
> Postiz is the agentic social media scheduler: AI agents plan, generate and
> schedule posts to 30+ networks, and you review everything in one visual
> calendar."

Its positioning statements, as they appear on the page:

- Headline value: "Run your social media on autopilot with AI agents"
- Entry point: "Start for $0" / "Your first 7 days cost $0"
- Buyer segmentation by *how they integrate*, not by company size:
  "AI-first marketers" (prompt it from Claude/ChatGPT), "Developers" (OAuth2,
  SDK, public API), "Automation teams" (n8n / Make.com / Zapier)
- Agent-agnostic by design: "Works with any agent: Claude / ChatGPT / Grok Bot
  / Muse / …", exposed through a **CLI and an MCP server**.

The pricing page accessible from the site shows a free start plus paid tiers;
the public copy leads with $0 entry, not with the paid price.

## The pattern, abstracted

Postiz's move is *not* a pivot into a new category. It is a **re-positioning
of an existing, proven category around the new buyer**:

1. **Keep the category.** Postiz stays a social-media scheduler. Scheduling,
   calendars, analytics — all still there. The category is already funded and
   understood; the buyer already has budget for it.
2. **Change the protagonist.** The unit of work becomes the *agent*, not the
   human marketer. The product is described in terms of what the agent does
   and what the human *reviews*.
3. **Re-cut the buyer segments by integration surface** (prompt-from-agent /
   build-on-API / wire-into-automation) instead of by company size.
4. **Be agent-agnostic and meet the agent where it works** — CLI, MCP server,
   public API. Do not pick a winner among agent frameworks.
5. **$0 entry, paid tiers above.** The open/self-serve tier is free because
   the switching cost is adoption, and the paid tiers sell the things an
   individual does not buy (team, scale, trust).

## How Swarmax applies the same model

| Postiz | Swarmax | Notes |
|---|---|---|
| Social-media scheduling | **Monitoring & audit** | Both are pre-existing, funded categories ("observability", "compliance"). We are not inventing a budget line. |
| "The Agentic Social Media Scheduling Platform" | **"The audit and operations layer for AI agent fleets"** | Same grammar: [proven category] re-anchored on the agent. |
| Agents plan/generate/schedule; humans review in a calendar | Agents act; **humans triage an SLA queue** and verify sealed evidence | The human's role moves from operator to reviewer/approver — the same emotional shift Postiz sells. |
| Works with any agent: Claude / ChatGPT / Grok / Muse, via CLI + MCP | Works with any framework: LangChain / CrewAI / AutoGen / Langfuse, via **OTLP relay + pull bridge** | The integration surface is our version of "MCP server and CLI". Agent-agnostic is the moat against framework churn. |
| Developers / AI-first marketers / Automation teams | **Platform engineers / agent owners / compliance & audit** | Re-cut by integration surface (already-tracing / building / regulated), not by headcount. |
| Start for $0, paid tiers above | **Open core $0, $29 Pro (sealed evidence), $99 Team (SSO + SLA queue)** | Identical structure; see `docs/landing.md`. |

## Where the analogy deliberately stops

Saying it plainly, because it is the difference between a positioning and a
delusion:

- **Postiz's risk is taste.** If agents post bad content, a brand is
  embarrassed. Swarmax's risk is **money and legal exposure**: a missed
  runaway loop burns real budget, and a broken evidence chain fails a real
  audit. Our buyer's failure mode is not "cringe", it is "the regulator
  opens a file".
- **The review burden is asymmetric.** Reviewing a social calendar is a
  pleasant, high-frequency, low-stakes act. Reviewing an SLA alarm queue is
  rare and high-stakes, and it must work when nobody is looking — hence the
  countdown clocks and self-escalation rather than a pretty calendar.
- **Trust is the product, not a feature.** Postiz can ship a Canva-like
  editor. Swarmax's equivalent of "pretty" is *verifiability*: RFC vectors,
  offline chain verification, a drill an auditor runs. The moment we trade
  verifiability for UX, we have lost the position.
- **Postiz is further along on distribution.** They have a wall of customer
  testimonials and a working paid funnel. We have none. Copying the
  *positioning* does not copy the traction; `docs/landing.md` says so
  explicitly in the "social proof — honest version" section.

## What we take, concretely

Three changes to make in our external copy, all derived from the pattern:

1. **Lead with the agent doing the work and the human reviewing it** — not
   with a list of metrics. Our hero already does this ("Can you prove what
   your agents did?").
2. **Re-cut the "for whom" by integration surface**, not by company size:
   *already-tracing* (Langfuse/OTLP users), *building* (framework-native
   teams), *regulated* (AI-Act-visible operators).
3. **Keep the $0 tier genuinely full-featured** and put the paid line exactly
   where Postiz does: at the moment an individual's needs become an
   organisation's needs. For us that line is *proof* (sealed evidence,
   counter-signatures) and *operations* (SSO, SLA queue) — not basic
   monitoring behind a paywall.
