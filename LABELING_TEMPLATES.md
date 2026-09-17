# AI Transparency & Labeling Templates (B5) — v1.1

**Scope:** ready-to-use wording for the AI-Act Art. 13 / Md. 13 "instructions
for use" disclosures that every Swarmax customer must attach to their own
agent product. Swarmax supplies the templates (this file + the JSON block);
the deployer is responsible for filling them truthfully and keeping them with
the product documentation.

**Language rule (Art. 13):** instructions ship in the language(s) required by
the member state of deployment. This template pack is provided in English and
Turkish; translate the filled result as needed.

---

## T1. End-user AI disclosure (minimum notice)

**EN:**
> This service uses autonomous AI agents to [PURPOSE]. Agent actions are
> monitored continuously (statistics, behavioral drift, runaway-loop guards)
> and any high-risk action requires human approval before execution. You can
> reach a human operator at [CONTACT]. Personal data processed by the agents
> is erased on request within [SLA] days via cryptographic key destruction.

**TR:**
> Bu hizmet, [AMAÇ] için otonom yapay zekâ ajanları kullanır. Ajan eylemleri
> sürekli izlenir (istatistiksel kartlar, davranışsal sürüklenme, döngü
> koruması) ve yüksek riskli her eylem insan onayı olmadan icra edilmez.
> Bir insan operatöre [İLETİŞİM] üzerinden ulaşabilirsiniz. Ajanların
> işlediği kişisel veriler, talebiniz üzerine [SÜRE] gün içinde kriptografik
> anahtar imhası ile silinir.

## T2. Operator instructions for use (Art. 13 core, fill-in)

| Field | Value to fill |
|---|---|
| Product / system identity | [NAME + version] |
| Intended purpose & foreseeable misuse | [PURPOSE / NOT-FOR list] |
| Autonomy level & human-approval gate | §9.2 gate: ON (attribution confirmed per alarm) |
| Monitored metrics (summary) | EWMA cost/error control cards, tool-mix JSD drift, Page-Hinkley, MAD robust-z, metamorphic end-state oracle |
| Alarm classes & SLA | §4.2 SLA map: Emergency 1h → Info 72h; queue in fleet console |
| Evidence & tamper evidence | append-only hash-chained ledger, Ed25519 signatures, Merkle seals; weekly exit drill |
| Personal data handling | per-subject ChaCha20-Poly1305 encryption; Art. 17 erasure = crypto-shred (key destruction), 2-year cold archive signed |
| Operator training requirement | triage walkthrough + quarterly exit-drill participation |
| Log retention | 30 days hot (SQLite), weekly sealed archives, 2 years cold tier |

## T3. Machine-readable disclosure block (embed in product manifest)

```json
{
  "swarmax_disclosure": {
    "schema": "swarmax.labeling.v1",
    "ai_present": true,
    "autonomy": "supervised",
    "human_approval_gate": true,
    "monitoring": ["ewma_control_card", "jsd_drift", "page_hinkley",
                    "mad_robust_z", "metamorphic_oracle", "loop_breaker"],
    "evidence": {"ledger": "hash_chained", "signatures": "ed25519",
                  "seals": "merkle"},
    "privacy": {"encryption": "chacha20-poly1305",
                 "erasure": "crypto_shred", "cold_archive_years": 2},
    "contact": "OPERATOR_CONTACT",
    "filled_by": "DEPLOYER_OF_RECORD",
    "date": "YYYY-MM-DD"
  }
}
```

## T4. Erasure-request intake form (Art. 17 / Md. 17)

> **Data subject request — erasure**
> 1. Identity verification: [PROCEEDURE]
> 2. Subject identifier in Swarmax (`swx.subject.id`): [ID]
> 3. Confirm scope: events bound to subject in evidence ledger via
>    `subject_event_bound` anchors: [LIST ledger# refs]
> 4. Action: console → Privacy → erase (crypto-shred) — destroys the
>    subject DEK; all bound payloads become permanently undecryptable.
> 5. Record: `subject_erased` anchored in the ledger; response to data
>    subject within [30] days including the anchor reference.

## T5. What Swarmax does NOT claim (honesty annex)

- Swarmax is a **technical-infrastructure provider for Art. 12/14 logging,
  monitoring and evidence**; it is not a conformity assessment, certificate,
  or legal advice.
- Deployers remain responsible for classification of their system (Annex III
  high-risk or not) and for the accuracy of filled templates.
- `gen_ai.*` OTel attributes are Development-stage (E6); customers accept
  pinned-registry maintenance as part of operation.
