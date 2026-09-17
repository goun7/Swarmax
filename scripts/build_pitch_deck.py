#!/usr/bin/env python
"""Build the investor pitch deck (10 slides, print-ready HTML).

Zero-dependency: each slide is one printed page (A4 landscape hint via CSS).
Numbers are the verified ones from SWARMAX.md (E1–E16 evidence ledger);
nothing here is a forecast beyond the paper's own labeled target scenario.

  python scripts/build_pitch_deck.py    # -> dist/pitch_deck.html
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"

SLIDES = [
    ("Swarmax",
     "The <strong>operations layer</strong> for autonomous agent fleets",
     "Frameworks build the fleet. Swarmax <em>operates</em> it: cost, latency, "
     "error classes and behavioral drift on one screen — with SLA-bound human "
     "escalation and court-grade evidence."),
    ("The problem is cancellation, not adoption",
     "40%+ of agentic projects will be canceled by end-2027",
     "Gartner names the causes: cost escapes, unclear value, insufficient risk "
     "controls (E1). Meanwhile $234B of enterprise software spend is exposed to "
     "agentic AI (E2) and 40% of enterprise apps ship task-specific agents in "
     "2026 (E4). Fleets are coming; operations tooling is not."),
    ("Nobody sells operations",
     "The competitor gap is structural",
     "LangSmith, Langfuse (now ClickHouse), AgentOps and Logfire sell "
     "developer <em>observability</em>: traces, prompts, seats (E11). Portkey "
     "and LiteLLM sell routing. The operations layer — SLA queues, drift "
     "alarms, human-oversight workflow, sealed evidence — is empty."),
    ("The product",
     "Alarm → triage → evidence, in one loop",
     "OTel GenAI ingest (pinned registry, honest Development-status stance) → "
     "5 metric families (EWMA, MAD, JSD, Page-Hinkley, n-gram loop breaker) → "
     "SLA-bound alarm queue → operator resolve → Ed25519+Merkle sealed "
     "evidence ledger. Quarterly exit drill proves exportability."),
    ("Shipped, not promised",
     "F0+F1+F2+console+scale mirror are on disk, verified by tests",
     "119 tests green: 8/8 alarm-injection acceptance, RFC 8032 crypto "
     "vectors, anti-replay matrix, tamper detection, exit drill roundtrip, "
     "100K events p99 < 2s. Zero runtime dependencies (stdlib only). "
     "EU AI Act dossier and dogfood plan are companion documents."),
    ("Regulation is the deadline",
     "EU AI Act high-risk obligations land 02.12.2027 (E5)",
     "Omnibus (EU) 2026/1744 moved the calendar and kept Art. 12 logging + "
     "Art. 14 human oversight. Swarmax is the Art. 12/14 technical "
     "infrastructure provider: immutable signed logs, HITL queue, kill-switch "
     "cascade. ~15-month buyer window, open now."),
    ("Defensibility",
     "Three moats a dashboard cannot copy",
     "(1) Evidence chain: append-only, signed, offline-verifiable archive. "
     "(2) Regulatory packaging: AI Act dossier mapped to running code. "
     "(3) Measurement commitments: MT-1…MT-8 reliability protocol from "
     "ReliabilityBench + MAST-aligned taxonomy — academic spine, not vibes."),
    ("Business model",
     "Flat pricing per agent, not per seat",
     "Open core ($0, Apache-2.0) → Team $199/mo → Fleet+Evidence $599/mo → "
     "Enterprise $2,400/mo+. Agent-based tiers sell budget predictability — "
     "the direct counter to E2's cost-escape problem. Break-even at 1 "
     "customer; 88–95% target gross margin."),
    ("12-month plan",
     "Dogfood-first execution with acceptance gates",
     "Weeks 1–2 dogfood run (MT-1…MT-8 on our own fleet, plan on disk) → "
     "first paid pilots with evidence packs → ClickHouse scale-out at month "
     "6 → compliance-pack sales. Target scenario: 50 customers, ~$294K ARR "
     "by month 12 (paper-labeled target, churn=0 assumption stated)."),
    ("The ask",
     "Build the category: agent fleet operations",
     "Pre-seed to fund the 12-week plan, the dogfood milestone and the first "
     "five reference customers in the EU compliance window. Every claim in "
     "this deck traces to a dated evidence record or a running test — "
     "<em>that</em> is the product."),
]


def build() -> Path:
    slides_html = []
    for i, (title, sub, body) in enumerate(SLIDES, 1):
        slides_html.append(
            f"<section class='slide'>"
            f"<div class='kicker'>SWARMAX · investor deck · {i:02d}/10</div>"
            f"<h1>{title}</h1><h2>{sub}</h2><p>{body}</p>"
            f"</section>")
    doc = """<!doctype html><html><head><meta charset="utf-8">
<title>Swarmax — Investor Deck</title><style>
:root { color-scheme: light }
body { margin: 0; background: #10141a; font-family: 'Helvetica Neue', Arial, sans-serif }
.slide { width: 297mm; min-height: 209mm; box-sizing: border-box; margin: 24px auto;
         background: white; color: #10141a; padding: 28mm 32mm; page-break-after: always }
.kicker { font-size: 11pt; letter-spacing: .18em; text-transform: uppercase; color: #6b7280 }
h1 { font-size: 44pt; margin: 14mm 0 4mm; line-height: 1.05 }
h2 { font-size: 20pt; font-weight: 500; color: #1f2937; margin: 0 0 12mm }
p { font-size: 15pt; line-height: 1.65; max-width: 210mm; color: #111827 }
@media print { body { background: white } .slide { margin: 0; width: auto; min-height: auto;
  height: 100vh } @page { size: A4 landscape; margin: 0 } }
</style></head><body>""" + "\n".join(slides_html) + "</body></html>\n"
    DIST.mkdir(exist_ok=True)
    out = DIST / "pitch_deck.html"
    out.write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    out = build()
    print(f"built {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB) — "
          "open in a browser and print to PDF (A4 landscape).")
