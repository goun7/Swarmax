/**
 * swarmax.js demo — same three styles as examples/quickstart.py.
 * Fix ENDPOINT/KEY/SECRET, run: node examples/js/demo.js
 */
"use strict";

const { SwarmaxClient, LoopDetected } = require("./swarmax.js");

const ENDPOINT = "http://127.0.0.1:4318";
const KEY_ID = "my-first-key";
const SECRET = "dev-secret";

async function runMyAgentStep() { return "ok"; }
async function myTool(q) { return `result:${q}`; }

async function main() {
  const client = new SwarmaxClient(ENDPOINT, KEY_ID, SECRET);
  client.setAgent("my-first-js-agent", "gpt-4o-mini");
  client.defaultCostUsd = 0.002;

  // 1) explicit task record
  client.task("task-001", { tokensIn: 120, tokensOut: 45, latencyMs: 800 });

  // 2) timed block (also captures the error name on failure)
  const s = client.span("task-002");
  const outcome = await runMyAgentStep();
  s.end();
  console.log("recorded:", outcome);

  // 3) loop-protected tool call — 3rd identical call throws LoopDetected
  for (const q of ["a", "a", "a"]) {
    try {
      console.log("myTool ->", await client.guard("my_tool", myTool, q));
    } catch (e) {
      if (e instanceof LoopDetected) console.log("BLOCKED:", e.message);
      else throw e;
    }
  }

  console.log("spans sent:", await client.flush());
}

main().catch((e) => { console.error(e); process.exit(1); });
