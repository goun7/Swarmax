"""The five-minute integration — copy this file and edit three strings.

1) run an ingest anywhere (even your laptop):
     pip install swarmax
     SWX_INGEST_SECRET=dev-secret swarmax-ingest
2) copy this file next to your agent code, fix ENDPOINT/KEY/SECRET,
   and wrap ONE of the three call styles:
     client.task("task-id")          # explicit, after each task
     with client.span() as s: ...    # timed block, error-capturing
     client.guard("tool", fn, ...)   # tool call + runaway-loop protection
3) watch the fleet console:  swarmax-console
"""
from swarmax import SwarmaxClient

ENDPOINT = "http://127.0.0.1:4318"
KEY_ID = "my-first-key"
SECRET = b"dev-secret"          # same value as SWX_INGEST_SECRET


def run_my_agent_step() -> str:  # your existing agent logic goes here
    return "ok"


def my_tool(q: str) -> str:      # any tool/function your agent calls
    return f"result:{q}"


def main() -> None:
    client = SwarmaxClient(ENDPOINT, KEY_ID, SECRET)
    client.set_agent("my-first-agent", model="gpt-4o-mini")
    client.default_cost_usd = 0.002           # or pass cost_usd= per call

    # 1) explicit task record
    client.task("task-001", tokens_in=120, tokens_out=45, latency_ms=800)

    # 2) timed block — latency + exceptions become real telemetry
    with client.span() as s:
        outcome = run_my_agent_step()
    print("recorded:", outcome, "->", s.recorded_task_id)

    # 3) loop-protected tool call — 3rd identical call raises LoopDetected
    for q in ("a", "a", "a"):
        try:
            print(my_tool.__name__, "->", client.guard("my_tool", my_tool, q))
        except Exception as exc:              # swarmax.LoopDetected on the 3rd
            print("BLOCKED:", exc)

    print("spans sent:", client.flush())


if __name__ == "__main__":
    main()
