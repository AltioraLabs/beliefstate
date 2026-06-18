# BeliefState: Current Project State Analysis

## 1. CORE DESIGN PRINCIPLES

### 1.1 Zero-Latency Background Processing
- **Primary Goal**: User-facing LLM responses return instantly without blocking on tracking overhead
- **Implementation**: All belief extraction, contradiction detection, and resolution runs asynchronously in background tasks
- **Dispatcher Pattern**: Pluggable dispatchers (`AsyncioDispatcher`, `CeleryDispatcher`, `RQDispatcher`) decouple the tracking pipeline from the main request flow
- **Trade-off**: Accepts eventual consistency in favor of user experience

### 1.2 Dual-Adapter Architecture
- **Problem Solved**: Expensive models (Claude, GPT-4) shouldn't be used for background extraction; cheaper models can do the job
- **Design**: Separate `app_adapter` (user-facing LLM) from `internal_adapter` (background tracking LLM)
- **Benefit**: Cost optimization without sacrificing user experience
- **Example**: Use Anthropic Claude for user interaction, Ollama (local) or OpenAI (cheap) for background tracking

### 1.3 Transparent Interception
- **Mechanism**: `@tracker.wrap` decorator on async LLM functions
- **Non-invasive**: Doesn't modify user code or SDK logic; just captures inputs/outputs
- **Protocol-based**: Works with any LLM provider via the `ProviderAdapter` protocol
- **Fail-safe**: Tracker errors never crash the user's application

### 1.4 Semantic Contradiction Resolution
- **Approach**: Embeddings + NLI (Natural Language Inference) for intelligent conflict detection
- **Not String Matching**: "I love Python" vs "I hate Python" are detected as contradictions even with different wording
- **Pluggable Judges**: `LLMJudge` (uses an LLM), `LocalNLIJudge` (uses HuggingFace model)
- **Configurable Strategies**: `overwrite` (prefer new), `keep_old` (prefer existing), `raise` (throw error)

### 1.5 Production-Grade Resilience
- **Exponential Backoff**: Retries with configurable min/max wait and multiplier (powered by `tenacity`)
- **Circuit Breaker**: Stateful circuit breaker (CLOSED → OPEN → HALF-OPEN) to fail-fast during LLM API outages
- **Transient Error Detection**: Distinguishes retryable errors (rate limits, 5xx) from permanent errors (auth, validation)
- **Separate Breakers**: One for LLM generation, one for embeddings

### 1.6 Persistent Belief State
- **Problem Solved**: Context window pollution; silent contradictions; volatile session memory
- **Solution**: Facts stored in SQLite (single-server) or Redis (distributed)
- **Retrieval**: Vector similarity search to find candidate contradictions
- **Lifecycle**: Facts persist across sessions until explicitly removed or contradicted

---

## 2. PACKAGE STRUCTURE

```
beliefstate/
├── __init__.py                          # Public API exports
├── tracker.py                           # BeliefTracker orchestrator (main entry point)
├── config.py                            # TrackerConfig (all configuration)
├── call.py                              # LLMCall, LLMResponse (universal models)
├── models.py                            # Belief (core data model)
│
├── adapters/                            # Provider-specific normalization
│   ├── base.py                          # ProviderAdapter protocol
│   ├── openai.py                        # OpenAI adapter
│   ├── anthropic.py                     # Anthropic adapter
│   ├── gemini.py                        # Google Gemini adapter
│   ├── ollama.py                        # Local Ollama adapter
│   ├── litellm.py                       # Multi-provider LiteLLM adapter
│   └── __init__.py                      # Adapter exports
│
├── store/                               # Persistent storage backends
│   ├── base.py                          # Store protocol
│   ├── sqlite.py                        # SQLite store
│   ├── redis.py                         # Redis store
│   └── __init__.py                      # Store exports
│
├── integrations/                        # Framework integrations
│   ├── asgi.py                          # ASGI middleware (FastAPI, Starlette, etc.)
│   ├── fastapi.py                       # FastAPI-specific helpers
│   ├── flask.py                         # Flask middleware & hooks
│   ├── wsgi.py                          # Generic WSGI middleware
│   ├── langchain.py                     # LangChain callback handler
│   ├── llamaindex.py                    # LlamaIndex callback handler
│   ├── openai.py                        # OpenAI Assistant observer
│   └── __init__.py                      # Integration exports
│
├── extractor.py                         # BeliefExtractor (parse facts from text)
├── detector.py                          # ContradictionDetector (semantic conflict detection)
├── resolver.py                          # BeliefResolver (handle conflict resolution)
├── judge.py                             # LLMJudge & LocalNLIJudge (NLI for contradiction)
├── dispatcher.py                        # Task dispatchers (Asyncio, Celery, RQ, Sync)
├── resilience.py                        # ResilientAdapterWrapper (retries + circuit breaker)
└── py.typed                             # PEP 561 marker for mypy
```

**Key Layering**:
1. **Entry**: User app calls decorated LLM function
2. **Normalization**: `ProviderAdapter` converts native SDK format → `LLMCall`/`LLMResponse`
3. **Tracking**: `BeliefTracker.wrap` captures call/response, dispatches background task
4. **Pipeline**: Background dispatcher routes to extraction → detection → resolution
5. **Storage**: Facts persisted in configurable store (SQLite/Redis)
6. **Integration**: Middleware/callbacks inject session context into framework lifecycle

---

## 3. KEY DATA MODELS

### 3.1 Belief (Core Model)
```python
class Belief(BaseModel):
    subject: str              # Entity (e.g., "USER", "ASSISTANT")
    predicate: str            # Relation (e.g., "likes", "works in")
    value: str                # Object (e.g., "Python", "Tokyo")
    confidence: float         # 0.0-1.0 (extraction confidence)
    turn: int                 # Conversation turn when extracted
    source: str               # "user" | "assistant"
    embedding: List[float]    # Vector representation for similarity search
```

**Semantics**:
- Triple-based representation: `(subject, predicate, value)`
- Example: `Belief(subject="USER", predicate="likes", value="Python", confidence=0.95, turn=1, source="user", embedding=[...])`
- Subject normalization: "I" → "USER", "you" (from user) → "ASSISTANT", "I" (from assistant) → "ASSISTANT"

### 3.2 LLMCall (Universal Call Representation)
```python
class LLMCall(BaseModel):
    messages: List[Dict[str, Any]]         # OpenAI-style message list
    kwargs: Dict[str, Any]                 # Additional provider params
    system: Optional[str]                  # System prompt (if extracted)
    metadata: Dict[str, Any]               # Custom metadata
```

**Purpose**: Normalize across OpenAI, Anthropic, Gemini, Ollama, LiteLLM

### 3.3 LLMResponse (Universal Response Representation)
```python
class LLMResponse(BaseModel):
    text: str                              # Extracted text content
    raw_response: Any                      # Original SDK response object
    metadata: Dict[str, Any]               # Custom metadata (tokens, model, etc.)
```

**Purpose**: Normalize across different provider response formats

### 3.4 TrackerConfig (Covered Separately in Section 4)

---

## 4. TrackerConfig: Complete Reference

### 4.1 Store Configuration

```python
# Store settings
store_type: str = Field(
    default="sqlite", 
    description="Type of storage: 'sqlite' | 'redis'"
)
store_kwargs: Dict[str, Any] = Field(
    default_factory=dict,
    description="Additional kwargs for the store"
)
# Example:
# store_kwargs = {"db_path": "beliefs.db"}          # for SQLite
# store_kwargs = {"url": "redis://localhost:6379"}  # for Redis
```

### 4.2 Detection Settings
```python
# Similarity & contradiction thresholds
similarity_threshold: float = Field(
    default=0.82,
    description="Embedding cosine similarity threshold (0.0-1.0)"
)
contradiction_threshold: float = Field(
    default=0.70,
    description="LLM judge confidence threshold for contradiction (0.0-1.0)"
)
# Higher thresholds = stricter (fewer false positives but miss some real contradictions)
```

### 4.3 LLM Prompts
```python
# Belief extraction prompt
extract_prompt_template: str = Field(
    default=DEFAULT_EXTRACT_PROMPT,
    description="Template for instructing LLM to extract beliefs"
)
# Includes:
# - Rules for subject normalization (I→USER, you→ASSISTANT)
# - Output format (JSON array of {subject, predicate, value, confidence})
# - Examples

# Contradiction detection prompt
judge_prompt_template: str = Field(
    default=DEFAULT_JUDGE_PROMPT,
    description="Template for instructing LLM judge to detect contradictions"
)
# Includes:
# - Format for comparing premise vs hypothesis
# - Output format ({relationship, score, reason})
```

### 4.4 Task Behavior
```python
enable_background_tasks: bool = Field(
    default=True,
    description="Run tracking async (fire-and-forget) vs sync (blocking)"
)
# True = user gets response immediately; tracking happens in background
# False = useful for testing; blocks until tracking completes
```

### 4.5 Resilience Settings
```python
# Exponential backoff retry configuration
retry_max_attempts: int = Field(default=5)
retry_min_wait: float = Field(default=2.0)       # seconds
retry_max_wait: float = Field(default=30.0)      # seconds
retry_multiplier: float = Field(default=2.0)     # exponential multiplier

# Circuit breaker configuration
enable_circuit_breaker: bool = Field(default=True)
circuit_breaker_failure_threshold: int = Field(default=5)
circuit_breaker_recovery_timeout: float = Field(default=30.0)  # seconds
```

**Retry Flow Example**:
- Attempt 1: immediate
- Attempt 2: wait 2s
- Attempt 3: wait 4s (2 * 2)
- Attempt 4: wait 8s (4 * 2)
- Attempt 5: wait 16s (8 * 2)
- If all fail: raise exception

**Circuit Breaker Flow**:
- CLOSED (normal): allows requests
- After 5 consecutive failures: OPEN (rejects immediately)
- After 30s cooldown: HALF-OPEN (test recovery with 1 request)
- If success: back to CLOSED

### 4.6 Task Dispatcher Configuration
```python
task_dispatcher_type: str = Field(
    default="asyncio",
    description="Dispatcher type: 'asyncio' | 'sync' | 'celery' | 'rq'"
)
dispatcher_kwargs: Dict[str, Any] = Field(
    default_factory=dict,
    description="Initialization kwargs for the dispatcher"
)

# Examples:
# "asyncio" → AsyncioDispatcher() [default, in-process]
# "sync" → SyncDispatcher() [blocking, for testing]
# "celery" → CeleryDispatcher(celery_app=app) [persistent queue]
# "rq" → RQDispatcher(queue=queue) [Redis Queue]
```

---

## 5. THE PROVIDER PROTOCOL

### 5.1 ProviderAdapter Protocol
```python
@runtime_checkable
class ProviderAdapter(Protocol):
    """Interface for translating between native SDK and universal formats."""

    def to_llm_call(self, *args: Any, **kwargs: Any) -> LLMCall:
        """Convert native SDK args/kwargs → LLMCall"""
        ...

    def to_llm_response(self, response: Any) -> LLMResponse:
        """Convert native SDK response → LLMResponse"""
        ...

    async def generate(
        self, 
        call: LLMCall, 
        response_format: Optional[Any] = None
    ) -> LLMResponse:
        """Execute generation using this provider"""
        ...

    async def get_embedding(self, text: str) -> List[float]:
        """Generate single embedding"""
        ...

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings (preferred for performance)"""
        ...
```

### 5.2 Adapter Implementations

| Adapter | Provider | Model Support | Embedding Support | Notes |
|---------|----------|---------------|--------------------|-------|
| `OpenAIAdapter` | OpenAI | GPT-4, GPT-3.5 | text-embedding-3-* | Uses official `openai` SDK |
| `AnthropicAdapter` | Anthropic | Claude 3.5 Sonnet | ❌ No native embeddings | Use with `internal_adapter` for embeddings |
| `GeminiAdapter` | Google | Gemini Pro, Flash | ✅ Embedding support | Uses `google-genai` SDK |
| `OllamaAdapter` | Local | Any local model | Local embeddings | Free, runs locally; good for `internal_adapter` |
| `LiteLLMAdapter` | Multi-provider | 100+ models | Via LiteLLM routing | Azure, Bedrock, Cohere, etc. |

### 5.3 Adapter Normalization Example
```python
# User wraps their OpenAI call
@tracker.wrap
async def call_openai():
    client = openai.AsyncOpenAI()
    return await client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )

# Behind the scenes:
# 1. OpenAIAdapter.to_llm_call() extracts messages + kwargs
# 2. Returns universal LLMCall(messages=[...], kwargs={...})
# 3. LLMResponse captured from native response
# 4. Extraction uses internal_adapter to generate beliefs
```

### 5.4 Dual-Adapter Usage Pattern
```python
from beliefstate.adapters import AnthropicAdapter, OllamaAdapter

# Expensive main adapter for user-facing requests
app_adapter = AnthropicAdapter(model="claude-3-5-sonnet-latest")

# Cheap background adapter for extraction & embeddings
bg_adapter = OllamaAdapter(model="llama3", embed_model="nomic-embed-text")

tracker = BeliefTracker(
    config=config,
    adapter=app_adapter,              # Intercepts Claude API
    internal_adapter=bg_adapter       # Uses Ollama for background tasks
)
```

---

## 6. THE MIDDLEWARE PIPELINE

### 6.1 BeliefTracker.wrap Decorator Pipeline

**Flow**:
```
User calls decorated LLM function
         ↓
   wrapper() executes
         ↓
   1. Get session_id from context
   2. Increment turn_counter
         ↓
   3. Execute user's LLM function (blocking)
         ↓
   4. Normalize with app_adapter:
      - to_llm_call(*args, **kwargs)
      - to_llm_response(native_response)
         ↓
   5. Dispatch background tracking (fire-and-forget)
         ↓
   6. Return native_response to user immediately
```

### 6.2 Background Tracking Pipeline (_track_background)
```
Dispatcher routes to _track_background()
         ↓
   1. EXTRACTION PHASE:
      - Extract beliefs from last user message
      - Extract beliefs from assistant response
      - Call BeliefExtractor.extract()
      - Generate batch embeddings for all beliefs
         ↓
   2. DETECTION PHASE:
      - Call ContradictionDetector.detect(session_id, new_beliefs)
      - Vector similarity search: find candidate old beliefs
      - For each match: LLMJudge.check() for semantic contradiction
         ↓
   3. RESOLUTION PHASE:
      - Call BeliefResolver.resolve() with contradictions
      - Apply strategy: overwrite/keep_old/raise
      - Update store with resolved beliefs
      - Queue conflict notes for next prompt injection
         ↓
   4. STORAGE PHASE:
      - Add non-contradictory beliefs to store
      - Errors silently logged (never crash main app)
```

### 6.3 Session Context Management
```python
# ContextVar for thread-local session tracking
session_context: ContextVar[str] = ContextVar("session_id", default="default")

# User sets session
tracker.set_session("user_123")

# Within decorated function, session is available globally
# Even in async context switches (ContextVar handles this)
```

### 6.4 Framework Middleware Integrations

#### ASGI Middleware (FastAPI, Starlette, Litestar, Quart)
```python
app.add_middleware(
    FastAPIBeliefTrackerMiddleware,
    header_name="X-Session-ID"  # Extract session from header
)

# Pipeline:
# Request arrives with X-Session-ID header
#   → Middleware extracts header value
#   → Sets session_context for this request
#   → Calls decorated LLM function (session already set)
#   → Reset context after response
```

#### WSGI Middleware (Flask)
```python
# Option A: WSGI middleware
app.wsgi_app = FlaskBeliefTrackerMiddleware(
    app.wsgi_app,
    header_name="X-Session-ID"
)

# Option B: Flask hooks (recommended)
register_flask_hooks(app, header_name="X-Session-ID")

# Pipeline:
# @app.before_request
#   → Extract session from header
#   → Set session_context
# @app.teardown_request
#   → Reset context
```

#### LangChain Integration
```python
from beliefstate import session_context, BeliefTrackerLangchainCallback

# 1. Set session ID explicitly
session_context.set("user_123")

# 2. Attach callback to LangChain chain
handler = BeliefTrackerLangchainCallback(tracker=tracker)
await chain.ainvoke("Hello!", config={"callbacks": [handler]})
```

---

## 7. INTEGRATION MODES

### 7.1 Decorator Mode (Simplest)
```python
@tracker.wrap
async def call_llm():
    response = await client.chat.completions.create(...)
    return response

# Usage:
tracker.set_session("user_123")
await call_llm()  # Tracking happens automatically in background
```

### 7.2 Manual Async Mode
```python
# For cases where decorator is not practical
native_response = await client.chat.completions.create(...)

call = adapter.to_llm_call(messages)
response = adapter.to_llm_response(native_response)

await tracker.track_async(
    call.model_dump(),
    response.model_dump(),
    session_id="user_123",
    turn=1
)
```

### 7.3 Manual Sync Mode (For Workers)
```python
# In Celery/RQ worker process
tracker.track_sync(
    call_dict,
    response_dict,
    session_id="user_123",
    turn=1
)
```

### 7.4 Middleware Mode (Framework Integrated)
```python
# FastAPI
app.add_middleware(FastAPIBeliefTrackerMiddleware, header_name="X-Session-ID")

@app.post("/chat")
async def chat(message: str):
    # session_id automatically set from header
    response = await llm_call(message)
    return response

# Client sends:
# POST /chat
# Header: X-Session-ID: user_123
```

### 7.5 Callback Mode (LangChain / LlamaIndex)
```python
# LangChain
handler = BeliefTrackerLangchainCallback(tracker=tracker)
chain = my_chain | handler

# LlamaIndex
Settings.callback_manager = CallbackManager([
    LlamaIndexBeliefTrackerCallback(tracker=tracker)
])
```

---

## 8. CONTRADICTION DETECTION PIPELINE

### 8.1 Full Detection Flow
```
New beliefs extracted from LLM response
         ↓
   For each new belief:
         ↓
   1. EMBEDDING CHECK:
      - Skip if embedding is empty
      - Use new_belief.embedding as query vector
         ↓
   2. VECTOR SIMILARITY SEARCH:
      - Query store.search_beliefs(embedding, threshold=0.82)
      - Returns top 5 candidate old beliefs
      - Cosine similarity: dot(v1, v2) / (||v1|| * ||v2||)
         ↓
   3. NLI JUDGMENT:
      For each candidate:
         - Compare premise (old_belief) vs hypothesis (new_belief)
         - Call LLMJudge.check(old_belief, new_belief)
         - Returns (is_contradiction, score, reason)
         ↓
   4. FILTER BY THRESHOLD:
      - Only keep if score >= contradiction_threshold (0.70)
         ↓
   5. COLLECT CONTRADICTIONS:
      - List of (old_belief, new_belief, score, reason) tuples
```

### 8.2 Similarity Search Algorithm
```python
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Cosine similarity between two vectors."""
    if not v1 or not v2:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)

# Range: -1.0 (opposite) to 1.0 (identical), typically 0.0-1.0 for embeddings
# threshold=0.82 means "find beliefs at least 82% similar in meaning"
```

### 8.3 NLI Judge Options

#### LLMJudge (Uses LLM)
```python
judge = LLMJudge(adapter=internal_adapter, config=config)

# Sends to LLM:
# "Premise: {old_belief}. Hypothesis: {new_belief}. Contradict?"
# LLM returns: {"relationship": "contradiction", "score": 0.95, "reason": "..."}
# Advantage: High accuracy, context-aware
# Disadvantage: Slower, costs API calls
```

#### LocalNLIJudge (Uses HuggingFace)
```python
judge = LocalNLIJudge(model_name="cross-encoder/nli-deberta-v3-xsmall")

# Uses local cross-encoder model
# Advantage: Fast, free, runs offline
# Disadvantage: May be less nuanced for domain-specific contradictions
```

### 8.4 Contradiction Example

**Scenario**: User says "I hate Python" then later says "I love Python"

```python
# First turn: new_belief_1
Belief(
    subject="USER",
    predicate="hates",
    value="Python",
    embedding=[0.1, 0.2, ...],  # embedding for "USER hates Python"
    source="user"
)

# Second turn: new_belief_2
Belief(
    subject="USER",
    predicate="loves",
    value="Python",
    embedding=[0.15, 0.22, ...],  # embedding for "USER loves Python"
    source="user"
)

# Detection:
# 1. Vector search finds belief_1 (high similarity to belief_2)
# 2. LLMJudge.check(belief_1, belief_2) → (True, 0.92, "Direct contradiction")
# 3. Resolver applies strategy (e.g., "overwrite"):
#    - Remove belief_1 from store
#    - Add belief_2 to store
```

### 8.5 Resolution Strategies

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `"overwrite"` | Prefer new belief | User changing mind; latest info is authoritative |
| `"keep_old"` | Ignore new belief | Legacy code; old facts are more reliable |
| `"raise"` | Throw error | Audit mode; flag all contradictions for review |

---

## 9. RESILIENCE & ERROR HANDLING

### 9.1 ResilientAdapterWrapper
Wraps any provider adapter with:
1. **Exponential backoff retries** (via `tenacity`)
2. **Circuit breaker** (fail-fast protection)

```python
# Two independent breakers:
llm_breaker → for generate() calls
embed_breaker → for get_embedding(s) calls

# Each breaker has:
- failure_threshold: 5 (trip after 5 failures)
- recovery_timeout: 30.0 seconds (cooldown before retry)
- state: "CLOSED" | "OPEN" | "HALF-OPEN"
```

### 9.2 Transient Error Detection
```python
def is_transient_error(exc: BaseException) -> bool:
    """Only retry on transient errors."""
    
    # Do NOT retry on developer errors:
    if isinstance(exc, (ValueError, TypeError, KeyError, ValidationError)):
        return False
    
    # Do NOT retry on auth/permission errors:
    if "auth" in exc.__class__.__name__.lower():
        return False
    
    # DO retry on network/rate limit errors:
    if status_code in [429, 500, 502, 503]:
        return True
    
    # DO retry on connection/timeout errors:
    if "timeout" in exc.__class__.__name__.lower():
        return True
```

### 9.3 Embedding Batching with Fallback
```python
# Preferred: batch all embeddings in one call
embeddings = await adapter.get_embeddings(texts)  # 1 API call

# If batch fails: fallback to individual requests
for text in texts:
    embedding = await adapter.get_embedding(text)  # N API calls
    # Never lose the belief, just slower
```

---

## 10. CURRENT LIMITATIONS & FUTURE CONSIDERATIONS

### Current State
- ✅ Single-session tracking works well
- ✅ Multi-provider support (5+ adapters)
- ✅ Resilience patterns implemented
- ✅ Framework integrations available

### Known Limitations
- SQLite doesn't support true vector search (uses sequential scan)
- Redis vector search limited (basic cosine similarity)
- LLMJudge can be slow (LLM API call per contradiction check)
- No built-in observability/metrics collection
- No belief expiry/TTL mechanism

### Future Enhancements (Potential)
- Vector database integration (Weaviate, Milvus, Pinecone)
- Streaming belief extraction for large responses
- Caching of LLM judge decisions
- Metrics & observability (OpenTelemetry)
- Belief versioning / audit trail
- Multi-tenant session isolation
- GraphQL query API for beliefs
