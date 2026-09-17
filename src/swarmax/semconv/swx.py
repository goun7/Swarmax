"""``swx.*`` extension namespace — Swarmax's own attributes under the OpenTelemetry
extension-namespace discipline (paper §3.1, R9): everything Swarmax needs that the
pinned GenAI registry does not provide lives here, never as a fake ``gen_ai.*`` key.
"""
from __future__ import annotations

SWX_ATTRIBUTES: dict[str, str] = {
    # fleet identity
    "swx.fleet.name": "str",
    "swx.agent.role": "str",            # planner|worker|reviewer|executor
    "swx.agent.version": "str",
    # task / metamorphic oracle inputs (R12)
    "swx.task.template": "str",
    "swx.task.instance": "str",
    "swx.end_state.json": "str",
    "swx.metamorphic.kind": "str",      # instance_perturb | paraphrase | scale_order
    "swx.metamorphic.baseline_ref": "str",
    # reliability mechanics (§3.2, §3.3)
    "swx.retry.count": "int",
    "swx.ttft.s": "double",
    "swx.budget.usd": "double",
    "swx.permission.decision": "str",   # allow|deny
    "swx.mask.count": "int",
    "swx.loop.hash": "str",             # §3.2-3 loop-breaker signature
    "swx.reasoning.slice.hash": "str",  # §3.2-6 head/tail slice hash
    "swx.drift.score": "double",
    "swx.drift.kind": "str",            # tool_dist | cost | latency | output_quality | unknown
    "swx.guard.event": "str",
    "swx.hitl.reason": "str",           # §4.1 reason taxonomy
    "swx.hitl.escalation_id": "str",
    "swx.slo.adopted": "bool",
    # evidence (§12.1)
    "swx.evidence.seq": "int",
    "swx.evidence.event_type": "str",
    "swx.evidence.payload_hash": "str",
    "swx.evidence.prev_hash": "str",
    # test discipline (§7.3)
    "swx.synthetic": "bool",
    "swx.scenario": "str",              # injection scenario id (S1..S8)
    "swx.model_tag": "str",
}
