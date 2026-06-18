# BeliefState: A Universal LLM Belief State Tracker

**BeliefState** is an asynchronous, zero-latency belief state tracking layer for Python applications. It seamlessly intercepts Large Language Model (LLM) chats, extracts factual beliefs, resolves contradictions via an LLM judge, and saves them to persistent storage (SQLite or Redis) — completely in the background.

It supports **OpenAI, Anthropic, Gemini, Ollama, and LiteLLM** natively, and features a highly flexible **Dual-Adapter Architecture** that allows you to use different providers for your application vs your background tracking logic.

---

## 🚀 Features

*   **Zero-Latency Tracking**: Extraction and conflict detection run in fire-and-forget background tasks.
*   **Production-Grade Resilience**: Automatic retry with exponential backoff, configurable timeouts, and stateful circuit breakers to fail-fast during LLM API outages.
*   **Health Checks & Monitoring**: Built-in health check methods for all adapters to verify provider connectivity before runtime.
*   **Structured Logging**: Observable operations across all adapters and integrations for production debugging and monitoring.
*   **Dual-Adapter Architecture**: Use an expensive model (like Claude) for your app, and a cheap/local model (like Ollama or OpenAI) for belief extraction and embeddings.
*   **Persistent Task Queues**: Pluggable dispatcher support to run background tracking via **Celery** or **Redis Queue (RQ)** to ensure no beliefs are lost on server crashes.
*   **Embedding Batching**: Combines multiple belief embedding requests into a single API call to prevent rate limit triggers, with a robust fallback to individual requests.
*   **Smart Contradiction Resolution**: Uses semantic embeddings to group related facts, and an NLI judge to gracefully resolve contradictions (Overwrite, Keep Old, or Raise).
*   **Plug-and-Play Integrations**: Includes helpers for `LangChain` Callbacks, `FastAPI` (ASGI), and `Flask` (WSGI) with automatic session validation.

---

## 📦 Installation

To install the core package:
```bash
pip install beliefstate
```

To install with extras (e.g., Redis, Celery, RQ, or LiteLLM):
```bash
pip install "beliefstate[redis,celery,rq,litellm]"
```

---

## 🛠️ Quickstart

The easiest way to track beliefs is using the `@tracker.wrap` decorator around your existing LLM function.

```python
import asyncio
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.adapters import OpenAIAdapter

# 1. Configure the Tracker
config = TrackerConfig(
    enable_background_tasks=True,
    store_type="sqlite",
    store_kwargs={"db_path": "user_beliefs.db"}
)

# 2. Initialize the Adapter and Tracker
adapter = OpenAIAdapter(model="gpt-4o", embed_model="text-embedding-3-small")
tracker = BeliefTracker(config=config, adapter=adapter)

# 3. Wrap your standard application logic
@tracker.wrap
async def chat(messages):
    import openai
    client = openai.AsyncClient()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    return response

async def main():
    # Set the unique session/user ID
    tracker.set_session("user_123")
    
    # Run your app normally! The tracker intercepts and extracts silently.
    await chat([{"role": "user", "content": "I am a Python developer living in Tokyo."}])

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🏭 Production Readiness

BeliefState includes comprehensive production-grade features for reliable deployment:

### ✅ Automatic Retry & Timeout Handling
All adapters automatically retry transient errors (rate limits, timeouts, connection issues) with exponential backoff:

```python
from beliefstate.adapters import OpenAIAdapter, RetryConfig

# Configure retry strategy
retry_config = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True  # Prevents thundering herd
)

adapter = OpenAIAdapter(
    retry_config=retry_config,
    timeout=30.0  # Configurable per adapter
)
```

### ✅ Health Checks
Verify provider connectivity before processing requests:

```python
# Check if OpenAI API is available
is_healthy = await adapter.health_check()
if not is_healthy:
    logger.error("OpenAI is not responding")
    # Fallback or fail-fast
```

### ✅ Structured Logging
All components include structured logging for observability:

```
[OpenAI] Initialized model=gpt-4o-mini embed_model=text-embedding-3-small
[OpenAI] Attempt 1/3: generate
[FastAPI] Request started request_id=abc-123 session_id=user_123
[FastAPI] Request completed request_id=abc-123 latency_seconds=0.234
```

### ✅ API Key Validation
Automatic validation of API keys at initialization with clear error messages.

### ✅ Traditional Resilience Config (TrackerConfig)
You can also tune the retry behavior and circuit breakers directly in `TrackerConfig`:

```python
config = TrackerConfig(
    # API Retries (exponential backoff)
    retry_max_attempts=5,
    retry_min_wait=2.0,       # seconds
    retry_max_wait=30.0,      # seconds
    retry_multiplier=2.0,

    # Circuit Breakers (fail-fast to protect your app)
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_timeout=30.0
)
```

---

## � Supported Providers

### OpenAI
```python
from beliefstate.adapters import OpenAIAdapter

adapter = OpenAIAdapter(
    model="gpt-4o",
    embed_model="text-embedding-3-small",
    timeout=30.0
)
# Features: ✅ Retry, ✅ Timeout, ✅ Health Check, ✅ Structured Logging
```

### Anthropic (Claude)
```python
from beliefstate.adapters import AnthropicAdapter

adapter = AnthropicAdapter(
    model="claude-3-5-sonnet-latest",
    timeout=30.0
)
# Features: ✅ Retry, ✅ Timeout, ✅ Health Check, ✅ Structured Logging
# Note: For embeddings, use OpenAI or Ollama as internal_adapter
```

### Google Gemini
```python
from beliefstate.adapters import GeminiAdapter

adapter = GeminiAdapter(
    model="gemini-2.0-flash",
    embed_model="text-embedding-004",
    timeout=30.0,
    safety_settings=[...]  # Optional safety configuration
)
# Features: ✅ Retry, ✅ Timeout, ✅ Health Check, ✅ Safety Settings
```

### Ollama (Local)
```python
from beliefstate.adapters import OllamaAdapter

adapter = OllamaAdapter(
    model="llama3.2",
    embed_model="nomic-embed-text",
    host="http://localhost",
    port=11434
)
# Features: ✅ Retry, ✅ Timeout, ✅ Health Check, ✅ Local Deployment
```

### LiteLLM (Multi-Provider)
```python
from beliefstate.adapters import LiteLLMAdapter

# Route to any of 100+ providers
adapter = LiteLLMAdapter(
    model="azure/gpt-4",  # or "bedrock/anthropic.claude-3-sonnet"
    embed_model="cohere/embed-english-v3.0"
)
# Features: ✅ Retry, ✅ Timeout, ✅ Health Check, ✅ Multi-Provider
```

---

## �🚂 Pluggable Background Dispatchers (Celery / RQ)

To offload tracking to a durable background worker, you can inject a pluggable `TaskDispatcher`.

### Option A: Celery Dispatcher

```python
from celery import Celery
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.dispatcher import CeleryDispatcher

celery_app = Celery("tasks", broker="redis://localhost:6379/0")

# Inject CeleryDispatcher into the tracker
tracker = BeliefTracker(
    config=TrackerConfig(),
    adapter=app_adapter,
    dispatcher=CeleryDispatcher(celery_app=celery_app)
)
```

### Option B: RQ (Redis Queue) Dispatcher

```python
from redis import Redis
from rq import Queue
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.dispatcher import RQDispatcher

redis_conn = Redis(host="localhost", port=6379)
queue = Queue("belief-state-tasks", connection=redis_conn)

# Inject RQDispatcher into the tracker
tracker = BeliefTracker(
    config=TrackerConfig(),
    adapter=app_adapter,
    dispatcher=RQDispatcher(queue=queue)
)
```

### Worker Setup
In your background worker file, register the global tracker so that tasks enqueued by name can execute the tracking synchronously on the worker process:

```python
from beliefstate.dispatcher import register_global_tracker
from my_app import tracker # Import your initialized BeliefTracker

# Register the tracker inside your celery/rq worker startup script
register_global_tracker(tracker)
```

---

## 🧠 The Dual-Adapter Architecture

If your main application uses a provider that doesn't support embeddings (like Anthropic), or if you want to use a cheaper local model for tracking to save costs, you can use the **Dual-Adapter Architecture**.

```python
from beliefstate.adapters import AnthropicAdapter, OllamaAdapter

# Your main app uses Claude 3.5 Sonnet
app_adapter = AnthropicAdapter(model="claude-3-5-sonnet-latest")

# But the background tracker uses local Llama 3 for free!
bg_adapter = OllamaAdapter(model="llama3", embed_model="nomic-embed-text")

tracker = BeliefTracker(
    config=config,
    adapter=app_adapter,             # Intercepts the Claude API payload
    internal_adapter=bg_adapter      # Runs extraction, embeddings, and judge calls
)
```

### 🔌 Multi-Provider Routing with LiteLLM

If your application relies on enterprise cloud providers (like Azure OpenAI, AWS Bedrock, or Cohere), you can leverage the `LiteLLMAdapter` to unified-route completion and embedding requests.

```python
from beliefstate.adapters import LiteLLMAdapter

# Configure dynamic routing via LiteLLM
enterprise_adapter = LiteLLMAdapter(
    model="azure/gpt-4o",
    embed_model="cohere/embed-english-v3.0"
)

tracker = BeliefTracker(
    config=config,
    adapter=enterprise_adapter
)
```

---

## 🗄️ Stores

Stores determine where the extracted facts live. You can configure them via `TrackerConfig(store_type="...")` or inject them directly.

- **`sqlite`** (`SQLiteStore`): Asynchronous, persistent single-file database. Perfect for single-server production apps. (Use `db_path=":memory:"` for transient tests).
- **`redis`** (`RedisStore`): Distributed caching. Essential if running multiple application workers (e.g., behind a load balancer).

---

## 🔌 Framework Integrations

BeliefState ships with helpers for major frameworks to handle session tracking automatically with production-grade error handling.

### FastAPI (ASGI) - Production Ready
```python
from fastapi import FastAPI
from beliefstate import FastAPIBeliefTrackerMiddleware

app = FastAPI()
app.add_middleware(
    FastAPIBeliefTrackerMiddleware,
    header_name="X-Session-ID"
)
# Features: ✅ Session validation, ✅ Error recovery, ✅ Structured logging
# Automatically sets session_context from incoming header X-Session-ID
```

### Flask (WSGI) - Production Ready
```python
from flask import Flask
from beliefstate import FlaskBeliefTrackerMiddleware, register_flask_hooks

app = Flask(__name__)
# 1. WSGI Middleware context propagation
app.wsgi_app = FlaskBeliefTrackerMiddleware(app.wsgi_app, header_name="X-Session-ID")

# 2. Flask request lifetime hooks (alternative/additional)
register_flask_hooks(app, header_name="X-Session-ID")

# Features: ✅ Thread-safe, ✅ Session validation, ✅ Error recovery, ✅ Structured logging
```

### ASGI (Generic) - Production Ready
```python
from starlette.applications import Starlette
from beliefstate import BeliefTrackerASGIMiddleware

app = Starlette()
app.add_middleware(
    BeliefTrackerASGIMiddleware,
    header_name="X-Session-ID"
)
# Features: ✅ HTTP & WebSocket support, ✅ Error handling, ✅ Logging
```

### LlamaIndex
```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from beliefstate import LlamaIndexBeliefTrackerCallback

callback_handler = LlamaIndexBeliefTrackerCallback(tracker=tracker)
Settings.callback_manager = CallbackManager([callback_handler])
```

### OpenAI Assistant Observer
```python
import asyncio
from beliefstate import observe_run

# Poll run status and dispatch thread messages chronologically to background tracker
asyncio.create_task(
    observe_run(
        tracker=tracker,
        client=openai_client,
        thread_id=thread_id,
        run_id=run.id,
        session_id="session_123"
    )
)
```

### LangChain
```python
from beliefstate import session_context, BeliefTrackerLangchainCallback

# 1. Set active session ID context
session_context.set("user_123")

# 2. Initialize and attach callback
handler = BeliefTrackerLangchainCallback(tracker=tracker)
await llm.ainvoke("Hello!", config={"callbacks": [handler]})
```

---

## 📚 Documentation

For detailed information about production deployment, see:
- **[PRODUCTION_ENHANCEMENTS.md](./PRODUCTION_ENHANCEMENTS.md)** - Comprehensive production readiness guide
- **[documentation.md](./documentation.md)** - Developer reference guide
- **[ADAPTER_AUDIT_REPORT.md](./ADAPTER_AUDIT_REPORT.md)** - Adapter audit findings and recommendations

---

## 📜 License
MIT License
