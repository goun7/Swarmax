# Contributing to Swarmax

Thanks for looking at Swarmax — an agentic-fleet operations layer: SLA-alarmed
triage, sealed evidence, AI-Act-ready privacy. The paper (`SWARMAX.md`,
Turkish) is the single source of record; the code is the proof.

## Ground rules

- **Zero runtime dependencies** (§7 F0). Stdlib only. If you need a library,
  the honest answer is usually: write the 50 lines yourself, pin the spec,
  and test against the RFC vectors (see `privacy/crypto.py` for the pattern).
- **No mocks in committed code.** Test doubles that speak real wire formats
  are fine (see `tests/test_tsa.py`); hiding unimplemented behaviour is not.
- **Honesty gates:** empty data must say "no data yet", never render a fake;
  failures must fail closed (see `sealing.py` countersign path).
- Every wire format gets **three** pieces: implementation, spec reference in
  the docstring, and a test pinned to a published vector (RFC 8439, RFC 8032,
  RFC 3161 byte-compat vs `openssl ts`, …).

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests -p no:warnings        # full battery (~1 min)
make demo && make drill                      # scenario + exit drills
make compliance-drill                        # auditor walkthrough
make trust-drill                             # live FreeTSA countersign (network)
make scale-gate-ch                           # 10M ClickHouse gate (needs SWARMAX_CH_URL)
```

## Pull requests

1. One logical change; tests included; `pytest` green before you push.
2. If the change touches the evidence chain, seals, or the paper's §3/§4
   formulas: update `SWARMAX.md` §13.2 (changelog) and reference the section.
3. Schema changes = a new numbered migration in `src/swarmax/schema/migrations/`,
   `schema_version` expectations updated in `tests/test_schema.py`.
4. CI runs the full matrix (3.10–3.14) plus nightly scale gates — a PR that
   only passes locally with a fast disk is not done.

## Licensing

Apache-2.0. By contributing you agree your work is licensed under it. The
core stays open by design (paper §5.3); paid services live in operations and
trust infrastructure, not in this repository's lock-up.
