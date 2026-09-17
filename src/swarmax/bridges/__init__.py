"""Bridges — feed the production ingest path from foreign platforms.

``langfuse_pull`` pulls traces from a Langfuse deployment's public API and
re-emits generation-level observations as signed ``gen_ai.*`` spans to
Swarmax OTLP/HTTP ingest (HMAC anti-replay, §4.3). Zero extra dependencies:
urllib only, both sides.

The emitter here uses **deterministic span ids** (hash of the source
observation id), so re-pulling the same window is idempotent end-to-end —
the server dedupes, safe under at-least-once delivery.
"""
from .langfuse_pull import LangfuseBridge, main as langfuse_main  # noqa: F401
from .otel_relay import OtelRelay, serve as relay_serve, main as relay_main  # noqa: F401
