"""Pinned OpenTelemetry GenAI semantic-convention attribute registry.

Paper refs: §3.1, §14 R9. Source of truth (read 2025-09-14):
https://github.com/open-telemetry/semantic-conventions-genai — docs/registry/attributes/gen-ai.md

Every ``gen_ai.*`` attribute in that registry is status **Development** (none is Stable),
which is exactly why the paper pins this snapshot and ships a validator instead of
claiming a stable version. Bumping = editing ``PINNED_SEMCONV`` + re-running
``swarmax.semconv.validate`` in CI.
"""
from __future__ import annotations

from dataclasses import dataclass

PINNED_SEMCONV = "open-telemetry/semantic-conventions-genai @ main, registry read 2025-09-14, all Development"

# type: "str" | "str[]" | "int" | "double" | "bool"
GENAI_ATTRIBUTES: dict[str, str] = {
    "gen_ai.system": "str",                      # provider (e.g. openai)
    "gen_ai.operation.name": "str",              # chat | text_completion | embed | execute_tool ...
    "gen_ai.provider.name": "str",               # added by registry (non-spec'd name preferred over system)
    "gen_ai.request.model": "str",
    "gen_ai.request.max_tokens": "int",
    "gen_ai.request.temperature": "double",
    "gen_ai.request.top_p": "double",
    "gen_ai.request.stop_sequences": "str[]",
    "gen_ai.request.frequency_penalty": "double",
    "gen_ai.request.presence_penalty": "double",
    "gen_ai.request.seed": "int",
    "gen_ai.request.choice_count": "int",
    "gen_ai.response.model": "str",
    "gen_ai.response.id": "str",
    "gen_ai.response.finish_reasons": "str[]",
    "gen_ai.output.type": "str",                 # text | json | image | speech ...
    "gen_ai.output.mime_type": "str",
    "gen_ai.usage.input_tokens": "int",
    "gen_ai.usage.output_tokens": "int",
    "gen_ai.usage.cost": "double",               # experimental in registry; we pin it for cost tracking
    "gen_ai.prompt": "str",                      # deprecated (events preferred); kept pinned
    "gen_ai.completion": "str",                  # deprecated (events preferred); kept pinned
    "gen_ai.conversation.id": "str",
    "gen_ai.agent.name": "str",
    "gen_ai.agent.id": "str",
    "gen_ai.agent.description": "str",
    "gen_ai.tool.name": "str",
    "gen_ai.tool.description": "str",
    "gen_ai.tool.call.id": "str",
    "gen_ai.tool.type": "str",
    "gen_ai.data_source.id": "str",
    "error.type": "str",
}

_EVENT_NAMES = ("gen_ai.client.inference.operation.details",
                "gen_ai.client.token.usage",
                "gen_ai.agent.definitions",
                "gen_ai.tool.definitions")


def genai_keys() -> list[str]:
    return sorted(GENAI_ATTRIBUTES)
