"""Pinned OpenTelemetry GenAI semantic-convention attribute registry.

Source of truth (registry read 2026-10-23):
https://github.com/open-telemetry/semantic-conventions-genai
  -> model/gen-ai/registry.yaml @ main

Every ``gen_ai.*`` attribute in that registry is status **Development** (none is
Stable; verified again on 2026-10-23 against model/gen-ai/registry.yaml). That
is exactly why this snapshot is pinned and the validator (not a "stable spec")
is what enforces it. Bumping = editing ``PINNED_SEMCONV`` + re-running
``swarmax.semconv.validate`` in CI.

G51-5 revizyonu (2026-10-23): 2025-09-14 snapshot'undan bu yana kaynaktan
KALDIRILAN attribute'ler cikarildi (gen_ai.system, gen_ai.prompt,
gen_ai.completion, gen_ai.usage.cost). Yerlerine:
  - gen_ai.system     -> gen_ai.provider.name (enum provider)
  - gen_ai.prompt     -> (yok; prompt icerigi events ile gen_ai.input.messages)
  - gen_ai.usage.cost -> (kaynakta yok; swx.* extension ile takip edilir)
Tip eslemeleri: enum -> str; enum-or-str -> str; any -> json;
template[string] -> str.
"""
from __future__ import annotations

PINNED_SEMCONV = "open-telemetry/semantic-conventions-genai @ main, registry read 2026-10-23, all Development (79 attributes)"

# type: "str" | "str[]" | "int" | "double" | "bool" | "json"
GENAI_ATTRIBUTES: dict[str, str] = {
    "gen_ai.agent.description": "str",
    "gen_ai.agent.id": "str",
    "gen_ai.agent.name": "str",
    "gen_ai.agent.version": "str",
    "gen_ai.conversation.compacted": "bool",
    "gen_ai.conversation.id": "str",
    "gen_ai.data_source.id": "str",
    "gen_ai.embeddings.dimension.count": "int",
    "gen_ai.evaluation.explanation": "str",
    "gen_ai.evaluation.name": "str",
    "gen_ai.evaluation.score.label": "str",
    "gen_ai.evaluation.score.value": "double",
    "gen_ai.input.messages": "json",
    "gen_ai.main_agent.description": "str",
    "gen_ai.main_agent.id": "str",
    "gen_ai.main_agent.name": "str",
    "gen_ai.memory.query.text": "str",
    "gen_ai.memory.record.count": "int",
    "gen_ai.memory.record.id": "str",
    "gen_ai.memory.records": "json",
    "gen_ai.memory.store.id": "str",
    "gen_ai.operation.name": "str",
    "gen_ai.output.messages": "json",
    "gen_ai.output.type": "str",
    "gen_ai.prompt.name": "str",
    "gen_ai.prompt.variable": "str",
    "gen_ai.prompt.version": "str",
    "gen_ai.provider.name": "str",
    "gen_ai.request.choice.count": "int",
    "gen_ai.request.encoding_formats": "str[]",
    "gen_ai.request.frequency_penalty": "double",
    "gen_ai.request.max_tokens": "int",
    "gen_ai.request.model": "str",
    "gen_ai.request.presence_penalty": "double",
    "gen_ai.request.previous_response.id": "str",
    "gen_ai.request.reasoning.level": "str",
    "gen_ai.request.seed": "int",
    "gen_ai.request.stop_sequences": "str[]",
    "gen_ai.request.stream": "bool",
    "gen_ai.request.stream_cursor": "str",
    "gen_ai.request.temperature": "double",
    "gen_ai.request.top_k": "int",
    "gen_ai.request.top_p": "double",
    "gen_ai.response.finish_reasons": "str[]",
    "gen_ai.response.id": "str",
    "gen_ai.response.model": "str",
    "gen_ai.response.status": "str",
    "gen_ai.response.time_to_first_chunk": "double",
    "gen_ai.retrieval.documents": "json",
    "gen_ai.retrieval.query.text": "str",
    "gen_ai.retrieval.top_k": "int",
    "gen_ai.skill.description": "str",
    "gen_ai.skill.name": "str",
    "gen_ai.skill.resource.name": "str",
    "gen_ai.skill.source.uri": "str",
    "gen_ai.system_instructions": "json",
    "gen_ai.token.modality": "str",
    "gen_ai.tool.call.arguments": "json",
    "gen_ai.tool.call.id": "str",
    "gen_ai.tool.call.result": "json",
    "gen_ai.tool.definitions": "json",
    "gen_ai.tool.description": "str",
    "gen_ai.tool.name": "str",
    "gen_ai.tool.type": "str",
    "gen_ai.usage.audio.cache_read.input_tokens": "int",
    "gen_ai.usage.audio.input_tokens": "int",
    "gen_ai.usage.audio.output_tokens": "int",
    "gen_ai.usage.cache_read.input_tokens": "int",
    "gen_ai.usage.cache_write.input_tokens": "int",
    "gen_ai.usage.image.cache_read.input_tokens": "int",
    "gen_ai.usage.image.input_tokens": "int",
    "gen_ai.usage.image.output_tokens": "int",
    "gen_ai.usage.input_tokens": "int",
    "gen_ai.usage.output_tokens": "int",
    "gen_ai.usage.reasoning.output_tokens": "int",
    "gen_ai.usage.text.cache_read.input_tokens": "int",
    "gen_ai.usage.text.input_tokens": "int",
    "gen_ai.usage.text.output_tokens": "int",
    "gen_ai.workflow.name": "str",
}

_EVENT_NAMES = ("gen_ai.client.inference.operation.details",
                "gen_ai.client.token.usage")
# G51-5 (2026-10-23): "gen_ai.agent.definitions" ve "gen_ai.tool.definitions"
# guncel registry'de ayni zamanda birer ATTRIBUTE (any tip) — event listesinden
# cikarilarak attribute/event ayrimi net tutulur.


def genai_keys() -> list[str]:
    return sorted(GENAI_ATTRIBUTES)
