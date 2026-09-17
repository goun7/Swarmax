/**
 * swarmax.js — mini SDK: send agent-task telemetry to a Swarmax ingest.
 *
 * Zero dependencies (Node 18+/Bun). Three styles, mirroring the Python facade:
 *
 *   const { SwarmaxClient } = require("./swarmax.js");        // or import
 *   const client = new SwarmaxClient("http://127.0.0.1:4318", "key", "secret");
 *   client.setAgent("js-agent", "gpt-4o-mini");
 *
 *   client.task("task-1", { tokensIn: 120, latencyMs: 300 });  // 1) explicit
 *   const s = client.span(); await step(); s.end();            // 2) timed block
 *   await client.guard("tool", fn, arg);                       // 3) loop-protected
 *
 * Emits signed OTLP/HTTP+JSON (X-SWX-* HMAC headers) — the wire contract
 * validated by swarmax.otlp.OtlpIngest. Deterministic span ids per task id
 * make retries idempotent (server dedupes).
 */
"use strict";

const crypto = require("crypto");

class LoopDetected extends Error {
  constructor(toolName) {
    super(`runaway loop: '${toolName}' called identically 3+ times in a row (swx §3.2-3)`);
    this.name = "LoopDetected";
  }
}

function kv(k, v) {
  let value;
  if (typeof v === "boolean") value = { boolValue: v };
  else if (Number.isInteger(v)) value = { intValue: String(v) };
  else if (typeof v === "number") value = { doubleValue: v };
  else value = { stringValue: String(v) };
  return { key: k, value };
}

function hexId(bytes, seed) {
  const h = crypto.createHash("sha256");
  h.update(seed != null ? String(seed) : crypto.randomBytes(32));
  return h.digest("hex").slice(0, bytes * 2);
}

/** One OTLP resourceSpans envelope carrying one gen_ai span. */
function buildSpan({ agentId, taskId, model, costUsd, tokensIn, tokensOut,
                     latencyMs, error, startNs, durationNs, seq }) {
  const attrs = [
    kv("gen_ai.operation.name", "chat"),
    kv("gen_ai.request.model", model),
    kv("gen_ai.usage.input_tokens", tokensIn | 0),
    kv("gen_ai.usage.output_tokens", tokensOut | 0),
    kv("gen_ai.usage.cost", Number(costUsd) || 0),
    kv("swx.agent.id", agentId),
    kv("swx.task.id", taskId),
    kv("swx.agent.version", "swarmax-js-1"),
    kv("swx.seq", seq),
  ];
  if (error) attrs.push(kv("error.type", String(error).slice(0, 64)));
  const traceId = hexId(16, `${agentId}|${taskId}`);
  const spanId = hexId(8, `${agentId}|${taskId}|${seq}`);
  return {
    resourceSpans: [{
      resource: { attributes: [kv("service.name", "swarmax-js")] },
      scopeSpans: [{
        spans: [{
          traceId, spanId, name: "gen_ai.chat",
          timeUnixNano: String(startNs),
          timeEndedUnixNano: String(startNs + durationNs),
          attributes: attrs,
          status: { code: error ? 2 : 0 },
        }],
      }],
    }],
  };
}

class SwarmaxClient {
  constructor(endpoint, keyId, secret, opts = {}) {
    const u = new URL(endpoint.includes("://") ? endpoint : `http://${endpoint}`);
    this.host = u.hostname;
    this.port = u.port || (u.protocol === "https:" ? 443 : 80);
    this.https = u.protocol === "https:";
    this.keyId = keyId;
    this.secret = Buffer.from(secret, "utf8");
    this.agentId = opts.agentId || "js-app";
    this.model = opts.model || "unknown";
    this.defaultCostUsd = opts.defaultCostUsd || 0;
    this.timeoutMs = opts.timeoutMs || 5000;
    this.batch = [];
    this.sentSpans = 0;
    this.rejected = 0;
    this._seq = 0;
    this._lastHash = "";
    this._sameCalls = 0;
  }

  setAgent(agentId, model) {
    this.agentId = agentId;
    if (model) this.model = model;
    return this;
  }

  /** 1) Explicit task record. Returns the task id. */
  task(taskId, o = {}) {
    this._seq += 1;
    taskId = taskId || `${this.agentId}-${this._seq}`;
    const latencyMs = o.latencyMs != null ? o.latencyMs : 0;
    const now = process.hrtime.bigint();
    this.batch.push(buildSpan({
      agentId: this.agentId, taskId,
      model: o.model || this.model,
      costUsd: o.costUsd != null ? o.costUsd : this.defaultCostUsd,
      tokensIn: o.tokensIn || 0, tokensOut: o.tokensOut || 0,
      latencyMs, error: o.error || null,
      startNs: now - BigInt(Math.max(0, latencyMs)) * 1000000n,
      durationNs: BigInt(Math.max(0, latencyMs)) * 1000000n,
      seq: this._seq,
    }));
    return taskId;
  }

  /** 2) Timed block: const s = client.span(); ... ; s.end(); */
  span(taskId, o = {}) {
    const t0 = process.hrtime.bigint();
    const self = this;
    return {
      end(err = null) {
        const ms = Number(process.hrtime.bigint() - t0) / 1e6;
        const name = err ? (err.name || String(err).split(":")[0]) : null;
        return self.task(taskId, { ...o, latencyMs: Math.round(ms), error: name });
      },
      async run(fn) {
        try {
          const out = await fn();
          this.end(null);
          return out;
        } catch (e) {
          this.end(e.name || "Error");
          throw e;
        }
      },
    };
  }

  /** 3) Loop-protected tool call — 3rd identical call throws LoopDetected. */
  async guard(toolName, fn, ...args) {
    const h = crypto.createHash("sha256")
      .update(JSON.stringify([toolName, args]))
      .digest("hex");
    if (h === this._lastHash && this._sameCalls >= 2) {
      this.task(undefined, { error: "loop", latencyMs: 0 });
      throw new LoopDetected(toolName);
    }
    const t0 = process.hrtime.bigint();
    let out;
    try {
      out = await fn(...args);
    } catch (e) {
      const ms = Number(process.hrtime.bigint() - t0) / 1e6;
      this.task(undefined, { error: e.name || "Error", latencyMs: Math.round(ms) });
      throw e;
    }
    const ms = Number(process.hrtime.bigint() - t0) / 1e6;
    this.task(undefined, { latencyMs: Math.round(ms) });
    if (h === this._lastHash) this._sameCalls += 1;
    else { this._lastHash = h; this._sameCalls = 1; }
    return out;
  }

  _sign(body, nonce) {
    const ts = String(Math.floor(Date.now() / 1000));
    const sig = crypto.createHmac("sha256", this.secret)
      .update(`${ts}.${nonce}`).update(body).digest("hex");
    return {
      "X-SWX-Key": this.keyId,
      "X-SWX-Timestamp": ts,
      "X-SWX-Nonce": nonce,
      "X-SWX-Signature": sig,
      "Content-Type": "application/json",
    };
  }

  /** Push queued spans over the wire; returns span count sent. */
  async flush() {
    if (this.batch.length === 0) return 0;
    const spans = this.batch;
    this.batch = [];
    const body = Buffer.from(JSON.stringify(spans[spans.length - 1]));
    const res = await fetch(`http${this.https ? "s" : ""}://${this.host}:${this.port}/v1/traces`, {
      method: "POST",
      headers: this._sign(body, crypto.randomBytes(12).toString("hex")),
      body,
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (res.ok) { this.sentSpans += spans.length; return spans.length; }
    this.rejected += spans.length;
    throw new Error(`swarmax ingest ${res.status}`);
  }
}

module.exports = { SwarmaxClient, LoopDetected, buildSpan };
module.exports.default = SwarmaxClient;
