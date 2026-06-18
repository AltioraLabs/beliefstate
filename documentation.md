# BeliefState: Developer Reference Guide

**BeliefState** is a lightweight, zero-latency, production-grade belief state tracking package for Python LLM applications. It runs silently in the background, intercepting your LLM chats to extract factual beliefs (facts), detect semantic contradictions, and persist them to durable databases.

---

## 📖 Table of Contents
1. [Core Concepts](#-core-concepts)
2. [Key Features](#-key-features)
3. [Production Readiness](#-production-readiness)
4. [Architecture Overview](#-architecture-overview)
5. [Quickstart Guide](#-quickstart-guide)
6. [Adapter Reference](#-adapter-reference)
7. [Class Reference](#-class-reference)
   - [BeliefTracker](#1-belieftracker)
   - [Provider Adapters](#2-provider-adapters)
   - [Belief Stores](#3-belief-stores)
   - [Task Dispatchers](#4-task-dispatchers)
8. [Resilience & Performance Options](#-resilience--performance-options)
   - [Exponential Backoff & Circuit Breakers](#1-exponential-backoff--circuit-breakers)
   - [Embedding Batching](#2-embedding-batching)
9. [Framework Integrations](#-framework-integrations)
   - [FastAPI / ASGI](#1-fastapi--asgi)
   - [Flask / WSGI](#2-flask--wsgi)
   - [LangChain Callback](#3-langchain-callback)
10. [Production Deployment Guide](#-production-deployment-guide)

---

## 🧠 Core Concepts

When building conversational agents, maintaining a persistent, conflict-free state of what the user has claimed (their "beliefs") is vital. Relying solely on the LLM's conversation history leads to:
*   **Context Window Pollution**: The history becomes too long to fit or becomes expensive.
*   **Silent Contradictions**: The user claims something new that contradicts an earlier claim (e.g. "I hate Python" vs "I write Python code"), and the LLM gets confused.
*   **Volatile Memory**: If the session resets, all user preferences are permanently lost.

**BeliefState** intercepts the conversation turn, extracts claims as structured triples `(Subject, Predicate, Value)` (e.g. `("USER", "likes", "Python")`), computes embeddings, checks for semantic similarities with previous claims, runs an NLI (Natural Language Inference) check to resolve contradictions, and updates the store.

---

## ✨ Key Features

1.  **Zero-Latency Design**: All belief extraction, embedding calculation, and conflict resolutions run asynchronously in the background so your user gets the LLM response instantly without blocking.
2.  **Dual-Adapter Architecture**: Inject different adapters. Run your user-facing app on Anthropic's Claude, but configure the background tracking pipeline on OpenAI or a local Ollama model to save costs.
3.  **Durable Multi-node Stores**: Supports SQLite for single-instance setups (with `:memory:` for testing) and Redis for high-scale, load-balanced worker clusters.
4.  **Bulletproof Resilience**: Powered by `tenacity` retries with exponential backoff and a stateful circuit breaker to avoid freezing your app during model API outages.
5.  **Pluggable Background Dispatchers**: Seamless integration with **Celery** or **Redis Queue (RQ)** to enqueue background tracking tasks onto persistent queues.
6.  **Embedding Batching**: Merges multiple individual embedding requests into a single batch payload to prevent rate limiting, with a robust fallback to individual requests on failure.

---

## 🏭 Production Readiness

BeliefState is designed for production deployment with enterprise-grade reliability features.

### Automatic Retry & Timeout Handling

All adapters include intelligent retry logic with exponential backoff:

```python
from beliefstate.adapters.common import RetryConfig, is_transient_error

# Configure retry strategy
retry_config = RetryConfig(
    max_retries=3,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True  # Prevents thundering herd
)

adapter = OpenAIAdapter(retry_config=retry_config, timeout=30.0)
```

**Retry Logic:**
- Transient errors (rate limits, timeouts, connection issues) → automatically retried
- Permanent errors (auth failures, invalid params) → fail fast
- Total timeout window includes retry delays

**Timeout Options:**
- Per-adapter configuration (default: 30 seconds)
- Total timeout with retries: ~120s (timeout × (max_retries + 1))
- Health check timeout: 5s (hardcoded)

### Health Checks

Verify provider availability before processing requests:

```python
# Check if provider is accessible
is_healthy = await adapter.health_check()
if not is_healthy:
    logger.error("Provider unavailable - using fallback")
    # Implement fallback logic
```

**Recommended Startup Validation:**

```python
@app.on_event("startup")
async def verify_providers():
    adapters = [openai_adapter, ollama_adapter]
    for adapter in adapters:
        if not await adapter.health_check():
            logger.critical(f"{adapter} unavailable - aborting startup")
            sys.exit(1)
```

### Structured Logging

All components include structured logging for production observability:

```python
# Logs include request context and metadata
[OpenAI] Generate completed model=gpt-4o-mini latency_seconds=0.234
[FastAPI] Request started request_id=abc-123 session_id=user_123
[Anthropic] Health check passed
[Ollama] Get embeddings failed with permanent error model=nomic-embed-text
```

### Error Categorization

The `is_transient_error()` function automatically classifies errors:

```python
from beliefstate.adapters.common import is_transient_error, TransientError, PermanentError

try:
    response = await adapter.generate(call)
except Exception as e:
    if is_transient_error(e):
        # Retry logic will handle this
        pass
    else:
        # Permanent error - fail fast
        logger.error(f"Permanent error: {e}")
        raise
```

### API Key Validation

All adapters validate API keys at initialization with clear error messages:

```python
# This will raise ValueError with helpful guidance if OPENAI_API_KEY is not set
adapter = OpenAIAdapter()
# Error: OpenAI API key is not configured. Set OPENAI_API_KEY or pass api_key explicitly.
```

---

## 📐 Architecture Overview

```
                          ┌──────────────────────────┐
                          │    Main Application      │
                          └─────────────┬────────────┘
                                        │
                                        ▼ (@tracker.wrap)
                          ┌──────────────────────────┐
                          │      BeliefTracker       │
                          └─────────────┬────────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
              ┌─────────────────────┐       ┌─────────────────────┐
              │   App Adapter       │       │  Internal Adapter   │
              │  (User-facing LLM)  │       │ (Resilience wrapped)│
              └─────────────────────┘       └──────────┬──────────┘
                                                       │
                                                       ▼ (Task Dispatcher)
                                            ┌─────────────────────┐
                                            │    Task Queue       │
                                            │   (Celery / RQ)     │
                                            └──────────┬──────────┘
                                                       │
                                                       ▼ (Worker execution)
                                            ┌─────────────────────┐
                                            │   BeliefExtractor   │
                                            └──────────┬──────────┘
                                                       │
                                                       ▼ (Batch Embeddings)
                                            ┌─────────────────────┐
                                            │ContradictionDetector│
                                            └──────────┬──────────┘
                                                       │
                                                       ▼
                                            ┌─────────────────────┐
                                            │   BeliefResolver    │
                                            └──────────┬──────────┘
                                                       │
                                                       ▼
                                            ┌─────────────────────┐
                                            │    BeliefStore      │
                                            │   (SQLite/Redis)    │
                                            └─────────────────────┘
```

---

## 🛠️ Quickstart Guide

### 1. Installation
Install the core package, along with any optional production extras:
```bash
# Core package only
pip install beliefstate

# Install with all extras
pip install "beliefstate[redis,celery,rq,litellm]"
```

### 2. Basic SQLite Integration
```python
import asyncio
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.adapters import OpenAIAdapter

# 1. Configuration
config = TrackerConfig(
    store_type="sqlite",
    store_kwargs={"db_path": "beliefs.db"},
    enable_background_tasks=True
)

# 2. Setup adapter & tracker
adapter = OpenAIAdapter(model="gpt-4o", embed_model="text-embedding-3-small")
tracker = BeliefTracker(config=config, adapter=adapter)

# 3. Decorate your LLM call
@tracker.wrap
async def call_assistant(messages):
    import openai
    client = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    return response

# 4. Execute a conversation
async def main():
    tracker.set_session("session_abc_123")
    
    messages = [{"role": "user", "content": "Hello! I am John, and I prefer dark mode."}]
    res = await call_assistant(messages=messages)
    print("AI Response:", res.choices[0].message.content)
    
    # Check what beliefs were saved
    await asyncio.sleep(1.0) # wait briefly for background task to complete
    beliefs = await tracker.store.get_beliefs("session_abc_123")
    for b in beliefs:
         print(f"Stored Fact: [{b.subject}] {b.predicate} '{b.value}'")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔌 Adapter Reference

### OpenAI Adapter
```python
from beliefstate.adapters import OpenAIAdapter
from beliefstate.adapters.common import RetryConfig

adapter = OpenAIAdapter(
    model="gpt-4o-mini",
    embed_model="text-embedding-3-small",
    timeout=30.0,
    retry_config=RetryConfig(max_retries=3)
)
```
**Features**: ✅ Retry ✅ Timeout ✅ Health Check ✅ Structured Logging

### Anthropic Adapter
```python
from beliefstate.adapters import AnthropicAdapter

adapter = AnthropicAdapter(
    model="claude-3-5-sonnet-latest",
    timeout=30.0
)
# Note: Embeddings not supported natively. Use internal_adapter for embeddings.
```
**Features**: ✅ Retry ✅ Timeout ✅ Health Check ✅ Structured Logging

### Gemini Adapter
```python
from beliefstate.adapters import GeminiAdapter

adapter = GeminiAdapter(
    model="gemini-2.0-flash",
    embed_model="text-embedding-004",
    timeout=30.0,
    safety_settings=[
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
)
```
**Features**: ✅ Retry ✅ Timeout ✅ Health Check ✅ Safety Settings

### Ollama Adapter (Local)
```python
from beliefstate.adapters import OllamaAdapter

adapter = OllamaAdapter(
    model="llama3.2",
    embed_model="nomic-embed-text",
    host="http://localhost",
    port=11434  # or use OLLAMA_HOST env var
)
```
**Features**: ✅ Retry ✅ Timeout ✅ Health Check ✅ Batch Embeddings ✅ Local Deployment

### LiteLLM Adapter (Multi-Provider)
```python
from beliefstate.adapters import LiteLLMAdapter

# Azure OpenAI
adapter = LiteLLMAdapter(
    model="azure/gpt-4",
    embed_model="text-embedding-3-small"
)

# AWS Bedrock
adapter = LiteLLMAdapter(
    model="bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
)

# Supports 100+ providers via LiteLLM routing
```
**Features**: ✅ Retry ✅ Timeout ✅ Health Check ✅ Multi-Provider Routing

---

## 📜 Class Reference

### 1. `BeliefTracker`
The primary orchestrator of the package.

*   `__init__(self, config: TrackerConfig, adapter: ProviderAdapter, store: Optional[Store] = None, internal_adapter: Optional[ProviderAdapter] = None, dispatcher: Optional[TaskDispatcher] = None)`
    *   `config`: Configuration instance.
    *   `adapter`: User-facing LLM adapter.
    *   `store`: Database store instance (defaults to `SQLiteStore`).
    *   `internal_adapter`: Adapter for belief operations (defaults to `adapter`).
    *   `dispatcher`: Background task dispatcher (defaults to `AsyncioDispatcher`).
*   `wrap(self, func)`: Decorator to wrap async LLM calls.
*   `set_session(self, session_id: str)`: Sets the current session ID in the thread-local context.
*   `get_pending_conflicts(self, session_id: Optional[str] = None) -> List[str]`: Retrieves and pops queued contradiction warning strings to inject into the next user prompt.

### 2. Provider Adapters
Adapters implement the `ProviderAdapter` Protocol to standardise native SDK payloads:

**Production Features (All Adapters)**:
- ✅ Automatic retry with exponential backoff
- ✅ Configurable request timeouts
- ✅ API key validation at initialization
- ✅ Health check capability
- ✅ Structured logging with request context
- ✅ Error categorization (transient vs. permanent)
- ✅ Graceful error recovery

**Available Adapters**:
*   `OpenAIAdapter`: Uses the official `AsyncOpenAI` client.
*   `AnthropicAdapter`: Uses the `AsyncAnthropic` client. (No native embeddings; recommend OpenAI or Ollama for internal_adapter).
*   `GeminiAdapter`: Uses the official `google-genai` client with safety settings.
*   `OllamaAdapter`: Uses local Ollama servers via `ollama.AsyncClient` with configurable host/port.
*   `LiteLLMAdapter`: Uses `litellm` library to route to any of 100+ providers (Azure, Bedrock, Anthropic, OpenAI, Cohere, etc.).

**Common Constructor Parameters**:
```python
adapter = SomeAdapter(
    model="model-name",
    embed_model="embedding-model-name",
    timeout=30.0,  # Per-adapter timeout in seconds
    retry_config=RetryConfig(max_retries=3)  # Optional custom retry strategy
)
```

**Common Methods**:
```python
# Generate text response
response = await adapter.generate(call)

# Generate embeddings
embeddings = await adapter.get_embeddings(texts)

# Check provider health
is_healthy = await adapter.health_check()
```


### 3. Belief Stores
Durable backends implementing `Store`:
*   `SQLiteStore`: Uses `aiosqlite` for local persistent storage. (Pass `db_path=":memory:"` for tests).
*   `RedisStore`: Uses asynchronous `redis` to store beliefs as serialized hashes. Perfect for distributed systems.

### 4. Task Dispatchers
Pluggable strategies for background execution:
*   `AsyncioDispatcher`: Runs tasks asynchronously in the current loop.
*   `SyncDispatcher`: Runs tasks blocking in the execution thread.
*   `CeleryDispatcher`: Pushes serialized payloads to a Celery queue via `send_task()`.
*   `RQDispatcher`: Pushes serialized payloads directly to an RQ Queue.

---

## 🛡️ Resilience & Performance Options

### 1. Exponential Backoff & Circuit Breakers
BeliefState wraps your internal LLM adapter calls inside a `ResilientAdapterWrapper`. When transient errors (like HTTP 429 Rate Limits, HTTP 502/503 Gateways, or DNS timeouts) occur:
*   **Tenacity Retries**: It retries the API request with exponential backoff up to `retry_max_attempts`.
*   **Fail-fast Circuit Breaker**: If the adapter fails consecutively beyond the `circuit_breaker_failure_threshold`, the circuit breaker trips to `OPEN`. Subsequent calls fail-fast immediately without invoking the network, protecting your app's capacity. After `circuit_breaker_recovery_timeout` (default `30s`), the circuit enters `HALF-OPEN` to test recovery.

Configure these in `TrackerConfig`:
```python
config = TrackerConfig(
    retry_max_attempts=5,
    retry_min_wait=2.0,
    retry_max_wait=30.0,
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_recovery_timeout=30.0
)
```

### 2. Embedding Batching
Instead of making single HTTP requests for each extracted belief, `BeliefExtractor` collects all valid beliefs and submits them to `adapter.get_embeddings(texts)` in a single batch call.
*   **Fallback Resolution**: If the batch embedding API call raises an exception (e.g. payload too large), the extractor automatically falls back to requesting embeddings individually, ensuring no beliefs are ever lost.

---

## 🔌 Framework Integrations

### 1. FastAPI / ASGI
The `FastAPIBeliefTrackerMiddleware` automatically extracts a session or user ID from incoming request headers and registers it into the tracker's context.

```python
from fastapi import FastAPI
from beliefstate import FastAPIBeliefTrackerMiddleware

app = FastAPI()
app.add_middleware(
    FastAPIBeliefTrackerMiddleware, 
    header_name="X-Session-ID"
)
```

### 2. Flask / WSGI
The `FlaskBeliefTrackerMiddleware` maps session context variables from standard WSGI environ environments:

```python
from flask import Flask
from beliefstate import FlaskBeliefTrackerMiddleware

app = Flask(__name__)
app.wsgi_app = FlaskBeliefTrackerMiddleware(
    app.wsgi_app, 
    header_name="X-Session-ID"
)
```

### 3. LlamaIndex Callback Handler
Automatically intercept chats executed inside a LlamaIndex application. Requires `llama-index-core`:

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from beliefstate import LlamaIndexBeliefTrackerCallback

callback_handler = LlamaIndexBeliefTrackerCallback(tracker=tracker)
Settings.callback_manager = CallbackManager([callback_handler])
```

### 4. OpenAI Assistant Run Observer
Asynchronously observe thread-based Assistant runs and track beliefs when completed. Requires `openai`:

```python
import asyncio
from beliefstate import observe_run

# Start assistant run
run = await client.beta.threads.runs.create(
    thread_id=thread_id,
    assistant_id=assistant_id
)

# Background-observe the run until complete, then extract and track beliefs
asyncio.create_task(
    observe_run(
        tracker=tracker,
        client=client,
        thread_id=thread_id,
        run_id=run.id,
        session_id="session_123"
    )
)
```

### 5. LangChain Callback
Allows seamless interception of LangChain chain executions without wrapping functions manually:

```python
from langchain_openai import ChatOpenAI
from beliefstate import session_context, BeliefTrackerLangchainCallback

# Set session ID context
session_context.set("user_123")

callback = BeliefTrackerLangchainCallback(tracker=tracker)
model = ChatOpenAI(callbacks=[callback])
```

---

## 🚢 Production Deployment Guide

When deploying to production, we recommend using a persistent task queue to safeguard against process crashes.

### Step 1: Initialize the Tracker with Celery/RQ Dispatcher
Configure the web server to enqueue background tasks:

```python
# app.py
from celery import Celery
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.dispatcher import CeleryDispatcher

celery_app = Celery("my_app", broker="redis://localhost:6379/0")

config = TrackerConfig(store_type="redis")
tracker = BeliefTracker(
    config=config,
    adapter=app_adapter,
    dispatcher=CeleryDispatcher(celery_app=celery_app)
)
```

### Step 2: Configure the Worker Process
Background workers must be registered with the global tracker so they can successfully execute enqueued belief tasks.

```python
# tasks.py (Celery Worker Startup)
from app import celery_app, tracker
from beliefstate.dispatcher import register_global_tracker

# 1. Register the global tracker
register_global_tracker(tracker)

# 2. Define the celery task enqueued by the dispatcher
@celery_app.task(name="beliefstate.dispatcher.execute_tracking_task")
def celery_tracking_worker(call_dict, response_dict, session_id, turn):
    from beliefstate.dispatcher import execute_tracking_task
    execute_tracking_task(call_dict, response_dict, session_id, turn)
```

Start the Celery worker normally:
```bash
celery -A tasks worker --loglevel=info
```


---

## 🔌 Framework Integrations - Production Ready

### 1. FastAPI / ASGI - Production Ready
The `FastAPIBeliefTrackerMiddleware` automatically extracts a session or user ID from incoming request headers and registers it into the tracker's context.

**Features**: ✅ Session Validation ✅ Error Recovery ✅ Structured Logging ✅ Graceful Degradation

```python
from fastapi import FastAPI, Depends
from beliefstate import FastAPIBeliefTrackerMiddleware, get_session_id

app = FastAPI()
app.add_middleware(
    FastAPIBeliefTrackerMiddleware, 
    header_name="X-Session-ID"
)

# Optional: Use dependency injection for session context
@app.post("/chat")
async def chat(message: str, session_id: str = Depends(get_session_id)):
    # session_id automatically set in tracker context
    return {"response": "ok"}
```

### 2. Flask / WSGI - Production Ready
The `FlaskBeliefTrackerMiddleware` maps session context variables from WSGI environments with thread-safe request hooks.

**Features**: ✅ Thread-Safe ✅ Session Validation ✅ Error Recovery ✅ Exception Tracking

```python
from flask import Flask
from beliefstate import FlaskBeliefTrackerMiddleware, register_flask_hooks

app = Flask(__name__)

# Method 1: WSGI Middleware
app.wsgi_app = FlaskBeliefTrackerMiddleware(app.wsgi_app, header_name="X-Session-ID")

# Method 2: Flask request hooks (alternative or in addition)
register_flask_hooks(app, header_name="X-Session-ID")

@app.route("/chat", methods=["POST"])
def chat():
    # Session context automatically available
    return {"response": "ok"}
```

### 3. LangChain Callback
Allows seamless interception of LangChain chain executions without wrapping functions manually:

```python
from langchain_openai import ChatOpenAI
from beliefstate import session_context, BeliefTrackerLangchainCallback

# Set session ID context
session_context.set("user_123")

callback = BeliefTrackerLangchainCallback(tracker=tracker)
model = ChatOpenAI(callbacks=[callback])
```

### 4. LlamaIndex Callback Handler
Automatically intercept chats executed inside a LlamaIndex application. Requires `llama-index-core`:

```python
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from beliefstate import LlamaIndexBeliefTrackerCallback

callback_handler = LlamaIndexBeliefTrackerCallback(tracker=tracker)
Settings.callback_manager = CallbackManager([callback_handler])
```

### 5. OpenAI Assistant Run Observer
Asynchronously observe thread-based Assistant runs and track beliefs when completed. Requires `openai`:

```python
import asyncio
from beliefstate import observe_run

# Start assistant run
run = await client.beta.threads.runs.create(
    thread_id=thread_id,
    assistant_id=assistant_id
)

# Background-observe the run until complete, then extract and track beliefs
asyncio.create_task(
    observe_run(
        tracker=tracker,
        client=client,
        thread_id=thread_id,
        run_id=run.id,
        session_id="session_123"
    )
)
```

---

## 🚢 Production Deployment Guide

When deploying to production, we recommend using a persistent task queue to safeguard against process crashes.

### Step 1: Initialize the Tracker with Celery/RQ Dispatcher
Configure the web server to enqueue background tasks:

```python
# app.py
from celery import Celery
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.dispatcher import CeleryDispatcher

celery_app = Celery("my_app", broker="redis://localhost:6379/0")

config = TrackerConfig(store_type="redis")
tracker = BeliefTracker(
    config=config,
    adapter=app_adapter,
    dispatcher=CeleryDispatcher(celery_app=celery_app)
)
```

### Step 2: Configure the Worker Process
Background workers must be registered with the global tracker so they can successfully execute enqueued belief tasks.

```python
# tasks.py (Celery Worker Startup)
from app import celery_app, tracker
from beliefstate.dispatcher import register_global_tracker

# 1. Register the global tracker
register_global_tracker(tracker)

# 2. Define the celery task enqueued by the dispatcher
@celery_app.task(name="beliefstate.dispatcher.execute_tracking_task")
def celery_tracking_worker(call_dict, response_dict, session_id, turn):
    from beliefstate.dispatcher import execute_tracking_task
    execute_tracking_task(call_dict, response_dict, session_id, turn)
```

Start the Celery worker normally:
```bash
celery -A tasks worker --loglevel=info
```

### Deployment Checklist

- [ ] Set all required environment variables (API keys for OpenAI, Anthropic, Gemini, etc.)
- [ ] Configure retry strategy if needed (non-default)
- [ ] Set timeout appropriately for your infrastructure
- [ ] Run health checks on startup
- [ ] Configure structured logging aggregation
- [ ] Set up monitoring/alerting on health checks
- [ ] Test with production-like load
- [ ] Document API key rotation process
- [ ] Set up request tracing/correlation IDs
- [ ] Verify timeout windows work with infrastructure
- [ ] Review PRODUCTION_ENHANCEMENTS.md for complete guidance
