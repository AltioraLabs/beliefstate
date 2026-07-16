"""CohereAdapter verification script for beliefstate PR #12.

1. Initializes CohereAdapter + BeliefTracker
2. Runs automated tests (run_all_tests)
3. Executes real generate() call (chat)
4. Executes real get_embeddings() call
5. Prints summary for PR verification proof
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Read API key from file (gitignored) or env
KEY_FILE = "/data/agent-folder/.cohere_key"
if os.path.exists(KEY_FILE):
    with open(KEY_FILE) as f:
        api_key = f.read().strip()
    os.environ["COHERE_API_KEY"] = api_key
elif "COHERE_API_KEY" not in os.environ:
    print(
        "ERROR: COHERE_API_KEY not set. Create /data/agent-folder/.cohere_key or export it."
    )
    sys.exit(1)


async def main():
    from beliefstate import BeliefTracker, TrackerConfig
    from beliefstate.adapters.cohere import CohereAdapter
    from beliefstate.call import LLMCall
    from tests import run_all_tests

    session_id = f"cohere-demo-{int(time.time())}"
    print("=" * 60)
    print("BELIEFSTATE COHERE ADAPTER — VERIFICATION")
    print("=" * 60)

    # 1. Initialize adapter
    print("\n[1] Initializing CohereAdapter...")
    adapter = CohereAdapter(
        model="command-r-plus-08-2024", embed_model="embed-english-v3.0"
    )
    print(f"    Adapter: {adapter.__class__.__name__}")
    print(f"    Model: {adapter.model}")
    print(f"    Embed model: {adapter.embed_model}")
    print(f"    Client: {type(adapter.client).__name__}")

    # 2. Create tracker
    print("\n[2] Creating BeliefTracker...")
    config = TrackerConfig(
        store_type="sqlite",
        store_kwargs={"db_path": ":memory:"},
        max_beliefs=100,
        enable_background_tasks=False,
        task_dispatcher_type="sync",
        enable_dashboard=False,
    )
    tracker = BeliefTracker(config=config, adapter=adapter)
    print(f"    Tracker: {tracker.__class__.__name__} OK")

    # 3. Health check
    print("\n[3] Health check...")
    health = await adapter.health_check()
    print(f"    Health check: {'PASS' if health else 'FAIL'}")
    if not health:
        print("    ERROR: Adapter health check failed")
        return 1

    # 4. Real generate() call
    print("\n[4] Real generate() call...")
    call = LLMCall(
        messages=[
            {
                "role": "user",
                "content": "Say 'Hello from beliefstate Cohere adapter verification' and nothing else. Be concise.",
            },
        ],
        kwargs={"model": "command-r-plus-08-2024", "temperature": 0.0},
    )
    t0 = time.time()
    response = await adapter.generate(call)
    elapsed = (time.time() - t0) * 1000
    print(f"    Response: {response.text[:120]}")
    print(f"    Latency: {elapsed:.0f}ms")

    # 5. Real get_embeddings()
    print("\n[5] Real get_embeddings() call...")
    texts = ["beliefstate is a belief tracking library", "Cohere provides embeddings"]
    t0 = time.time()
    embeddings = await adapter.get_embeddings(texts)
    elapsed = (time.time() - t0) * 1000
    print(f"    Embeddings: {len(embeddings)} vectors")
    print(f"    Dimension: {len(embeddings[0])}")
    print(f"    Latency: {elapsed:.0f}ms")

    # 6. Run automated tests
    print("\n[6] Running automated tests (run_all_tests)...")
    results = await run_all_tests(tracker, session_id)
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    print(f"    Tests: {passed}/{total} passed")
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"    [{status}] {r.get('name')}")

    # 7. Summary
    print("\n" + "=" * 60)
    if health and passed == total:
        print("ALL CHECKS PASSED — Cohere adapter works correctly")
        print("=" * 60)
        return 0
    else:
        print(f"ISSUES: health={health}, tests={passed}/{total}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
