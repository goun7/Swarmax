# Swarmax Upgrade Guide — v1.0.x (B3)

**Audience:** operators replacing an in-house agent-monitoring stack (or a
general-purpose observability tool used for agents) with Swarmax v1.0.x.
**Promise:** every step is reversible; no data leaves your infrastructure;
cutover can be staged per agent fleet.

## 1. What you are leaving behind (typical legacy setups)

| Legacy pattern | Risk it carries | Swarmax replacement |
|---|---|---|
| Log file + grep for agent failures | No SLA, no evidence, silent loops run for hours | §4.2 alarm→triage→evidence chain with SLA deadlines |
| General APM (traces only) | `gen_ai.*` still Development-stage; token/cost semantics absent | Pinned semconv mapping (E6) + cost/latency EWMA (§3.2) |
| Spreadsheet triage | No tamper-evidence; audit = screenshots | Ed25519 + Merkle sealed evidence ledger (§12) |
| Home-grown kill switch | Kill decisions are autonomous and unauditable | Human-confirm gate (§9.2) + attribution suggestion |

## 2. Pre-flight checklist (30 minutes)

1. **Python 3.11+** on the host (`python --version`). No packages beyond the
   stdlib are required (§7 F0 zero-dependency rule).
2. **Disk:** ≥ 2× your expected 30-day event volume (SQLite hot tier, §10.1).
3. **Secrets:** generate an ingest HMAC secret (`SWX_INGEST_SECRET`) and a
   32-byte master key (`SWARMAX_MASTER_KEY`, hex). Do not reuse the demo
   defaults; the dev fallback is clearly labeled in code.
4. **Ports:** ingest `:4318`, console `:8080` (or map your own).
5. **Backups:** if you migrate from an old Swarmax store, run
   `python scripts/exit_drill.py --db <old.db>` first — chain and seals must
   verify before any copy is made.

## 3. Cutover, staged per fleet (one afternoon)

```bash
# 1) boot ingest + console on the new store
make seed                      # or: python scripts/seed_fleet.py --db new.db
make console                   # login: $SWARMAX_ADMIN / $SWARMAX_ADMIN_PASSWORD

# 2) point ONE pilot agent's OTLP exporter at the new endpoint
#    (keep the old system running in parallel — shadow mode)
#    exporter endpoint: http://<host>:4318/v1/traces
#    headers: X-SWX-Key / X-SWX-Timestamp / X-SWX-Nonce / X-SWX-Signature

# 3) verify identity pairing + anti-replay on the pilot
curl -s http://<host>:4318/metrics   # received / accepted / ingest_reject

# 4) run one evaluation cycle and triage the alarm queue in the console
# 5) seal the evidence ledger; run the exit drill
make seal && make drill

# 6) roll the remaining fleets over, oldest first; retire the old stack last
```

**Rollback:** point the exporter back at the old system. Swarmax keeps no
exclusive lock on your data — the store is a single SQLite file you own.

## 4. Mapping your old data in (optional, one-shot)

Legacy CSV/JSON exports map onto `agent_task_events`:

| Legacy column | Swarmax field | Note |
|---|---|---|
| agent/run id | `agent_id` | normalize to `urn:agent:<tenant>:<env>:<name>` |
| timestamp | `ts` | UTC, `YYYY-MM-DD HH:MM:SS` |
| model | `model_name` | free text |
| tokens in/out | `input_tokens` / `output_tokens` | ints |
| cost | `cost_usd` | USD; convert at import time |
| status/error | `status` / `error_class` | use the MAST-aligned taxonomy (§3.2-6) |
| tool name + args | guard_events `tool_name` / `arguments_json` | enables JSD drift + loop detection |

Import via a small script using `swarmax.pipeline.Pipeline.ingest()` — the
same idempotent path production traffic uses (dedupe on `event_id`).

## 5. Post-cutover verification (the honest gate)

- [ ] `python scripts/exit_drill.py --db <db>` → `chain_ok=True seals_ok=True`
- [ ] Console: login works, queue triages, seal verifies (`verified=True`)
- [ ] One forced failure per agent class produces the expected §4.2 alarm
      (see `tests/test_scenarios.py` for the eight reference scenarios)
- [ ] `SWARMAX_MASTER_KEY` and `SWX_INGEST_SECRET` stored in your secret
      manager; demo defaults absent from production env
- [ ] Weekly report renders with evidence anchors (`ledger#N` links)

## 6. Known limits (stated, not hidden)

- Single-node SQLite hot tier: the ClickHouse mirror (`swarmax.ch`) exists and
  is dual-write safe, but v1.0.x does not yet fail over automatically.
- SSO is OIDC/PKCE with HS256+RS256; SAML is out of scope for v1.0.x.
- Cold-tier archive (`swarmax.coldstore`) targets any S3-compatible object
  store; tape/Glacier Deep Archive retrieval latency is your operator concern.
