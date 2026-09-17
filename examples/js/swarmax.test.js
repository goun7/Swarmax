/** swarmax.js tests — zero-dep: `node --test examples/js/` */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const http = require("http");
const crypto = require("crypto");

const { SwarmaxClient, LoopDetected, buildSpan } = require("./swarmax.js");

const SECRET = "test-secret";

/** Minimal fake of swarmax.otlp.OtlpIngest: validates HMAC, stores bodies. */
function fakeIngest(store) {
  const srv = http.createServer((req, res) => {
    let chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const body = Buffer.concat(chunks);
      const ts = req.headers["x-swx-timestamp"];
      const nonce = req.headers["x-swx-nonce"];
      const sig = req.headers["x-swx-signature"];
      const expect = crypto.createHmac("sha256", SECRET)
        .update(`${ts}.${nonce}`).update(body).digest("hex");
      if (sig !== expect || store.nonces.has(nonce)) {
        res.statusCode = sig !== expect ? 401 : 409;
        res.end("{}");
        return;
      }
      store.nonces.add(nonce);
      store.bodies.push(JSON.parse(body.toString("utf8")));
      res.statusCode = 200;
      res.end("{}");
    });
  });
  return srv;
}

function client(url) {
  return new SwarmaxClient(url, "js-key", SECRET, { agentId: "js-bot", model: "m-1" });
}

test("span envelope carries gen_ai/swx attributes", () => {
  const env = buildSpan({
    agentId: "a", taskId: "t-1", model: "m", costUsd: 0.01,
    tokensIn: 10, tokensOut: 4, latencyMs: 30,
    error: null, startNs: 1000n, durationNs: 30n, seq: 1,
  });
  const span = env.resourceSpans[0].scopeSpans[0].spans[0];
  const map = Object.fromEntries(span.attributes.map((a) => [a.key, a.value]));
  assert.equal(map["gen_ai.request.model"].stringValue, "m");
  assert.equal(map["swx.agent.id"].stringValue, "a");
  assert.equal(map["gen_ai.usage.input_tokens"].intValue, "10");
  assert.equal(span.status.code, 0);
  assert.match(span.traceId, /^[0-9a-f]{32}$/);
});

test("task + flush over real HTTP with valid HMAC", async () => {
  const store = { bodies: [], nonces: new Set() };
  const srv = fakeIngest(store);
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${srv.address().port}`;
  const c = client(url);
  const tid = c.task("t-1", { tokensIn: 120, tokensOut: 45, latencyMs: 300, costUsd: 0.02 });
  assert.equal(tid, "t-1");
  assert.equal(await c.flush(), 1);
  assert.equal(c.sentSpans, 1);
  const span = store.bodies[0].resourceSpans[0].scopeSpans[0].spans[0];
  const map = Object.fromEntries(span.attributes.map((a) => [a.key, a.value]));
  assert.equal(map["swx.task.id"].stringValue, "t-1");
  assert.equal(map["gen_ai.usage.cost"].doubleValue, 0.02);
  srv.closeAllConnections?.();
  await new Promise((r) => srv.close(r));
});

test("span() measures elapsed time and records error name", async () => {
  const store = { bodies: [], nonces: new Set() };
  const srv = fakeIngest(store);
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${srv.address().port}`;
  const c = client(url);
  const s = c.span("t-2");
  try {
    await new Promise((r) => setTimeout(r, 15));
    s.end(new RangeError("boom"));
    await c.flush();
    const span = store.bodies[0].resourceSpans[0].scopeSpans[0].spans[0];
    const map = Object.fromEntries(span.attributes.map((a) => [a.key, a.value]));
    assert.equal(map["error.type"].stringValue, "RangeError");
    assert.ok(span.timeEndedUnixNano >= span.timeUnixNano);
  } finally {
    srv.closeAllConnections?.();
    await new Promise((r) => srv.close(r));
  }
});

test("guard blocks the third identical call and records loop", async () => {
  const store = { bodies: [], nonces: new Set() };
  const srv = fakeIngest(store);
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${srv.address().port}`;
  const c = client(url);
  let calls = 0;
  const tool = async (q) => { calls += 1; return `r:${q}`; };
  assert.equal(await c.guard("tool", tool, "x"), "r:x");
  assert.equal(await c.guard("tool", tool, "x"), "r:x");
  await assert.rejects(() => c.guard("tool", tool, "x"), LoopDetected);
  assert.equal(calls, 2);
  await c.flush();
  const loopSpan = store.bodies[0].resourceSpans[0].scopeSpans[0].spans
    .find((sp) => sp.attributes.some((a) => a.key === "error.type" &&
                                          a.value.stringValue === "loop"));
  assert.ok(loopSpan, "blocked attempt recorded as error.type=loop");
  srv.closeAllConnections?.();
  await new Promise((r) => srv.close(r));
});

test("guard streak resets on a distinct call", async () => {
  const store = { bodies: [], nonces: new Set() };
  const srv = fakeIngest(store);
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  const url = `http://127.0.0.1:${srv.address().port}`;
  const c = client(url);
  const tool = async (q) => q;
  await c.guard("tool", tool, "x");
  await c.guard("tool", tool, "x");
  assert.equal(await c.guard("tool", tool, "y"), "y");   // reset
  await c.guard("tool", tool, "x");
  await c.guard("tool", tool, "x");
  await assert.rejects(() => c.guard("tool", tool, "x"), LoopDetected);
  srv.closeAllConnections?.();
  await new Promise((r) => srv.close(r));
});
