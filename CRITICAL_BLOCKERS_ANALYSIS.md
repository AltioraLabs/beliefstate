# BeliefState: Critical Blockers - Verified Status

## Status Summary
This document audits the 4 "CRITICAL" blockers identified in the requirements against the actual codebase.

---

## BLOCKER #1: Belief @dataclass vs Pydantic BaseModel

**STATUS**: ✅ **ALREADY FIXED**

**Finding**: `models.py` already uses Pydantic BaseModel with field validation:
```python
class Belief(BaseModel):
    subject: str
    predicate: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)  # ← Validation present
    turn: int
    source: str
    embedding: List[float] = Field(default_factory=list)
```

**Verification**:
- RedisStore calls `belief.model_dump_json()` → works ✅
- SQLiteStore calls `Belief()` constructor → works ✅
- Field validation `ge=0.0, le=1.0` → present ✅

**Action**: No fix needed for this task. Can mark #1 as complete, but add architecture enhancements:
- Add `embedding_model: str` field (Task #7)
- Add `created_at: datetime` field for TTL tracking
- Add session context if needed

---

## BLOCKER #2: LocalNLIJudge Event Loop Blocking

**STATUS**: ✅ **ALREADY FIXED**

**Finding**: `judge.py` LocalNLIJudge.check() already uses `run_in_executor()`:

```python
async def check(self, old: Belief, new: Belief) -> Tuple[bool, float, str]:
    # ...
    loop = asyncio.get_running_loop()
    pipeline_fn = self._pipeline
    
    # ✅ Runs in thread pool, doesn't block event loop
    res = await loop.run_in_executor(
        None, 
        lambda: pipeline_fn({"text": premise, "text_pair": hypothesis})
    )
```

**Verification**:
- CPU-bound NLI inference wrapped in executor ✅
- Event loop not blocked ✅

**Action**: No fix needed for this task. Mark #2 as complete.

---

## BLOCKER #3: SQLiteBeliefStore Persistent Connection

**STATUS**: ✅ **PARTIALLY FIXED** (reuses connection, but no lifecycle mgmt)

**Finding**: SQLiteStore uses `_get_connection()` for connection reuse:

```python
async def _get_connection(self) -> Any:
    if self._conn is None:
        # ...
        self._conn = await aiosqlite.connect(self.db_path)
        # ...
    return self._conn  # ← Reused across all calls
```

**What works**:
- Connection is reused (not reopened per call) ✅
- `:memory:` database works because same connection is reused ✅
- File-based DB avoids connection pool exhaustion ✅

**What's missing**:
- No explicit `open()` / `close()` / context manager interface
- Connection never cleaned up (no `__del__` or `await close()`)
- Tests can't do `async with store: ...` cleanup

**Action**: Add lifecycle management:
```python
async def open(self) -> None:
    """Explicitly open and initialize the database."""
    await self._get_connection()

async def close(self) -> None:
    """Explicitly close the database connection."""
    if self._conn:
        await self._conn.close()
        self._conn = None

async def __aenter__(self):
    await self.open()
    return self

async def __aexit__(self, *args):
    await self.close()
```

This is an **enhancement**, not a critical blocker. The current code works but lacks hygiene.

---

## BLOCKER #4: Demo Mock Mode Bypasses Pipeline

**STATUS**: ⚠️ **PARTIALLY VERIFIED**

**Finding**: Current `demo.py` uses real Ollama, not mocks:

```python
@tracker.wrap
async def chat_with_ollama(messages):
    client = ollama.AsyncClient()
    response = await client.chat(model="qwen2.5:7b", messages=messages)
    return response
```

**Analysis**:
- ✅ Uses real Ollama (not hardcoded mock)
- ✅ Real extractor runs (not replaced with mock)
- ✅ Real adapter normalization happens
- ✅ Real pipeline executes
- ⚠️ Problem: Requires Ollama running locally to execute

**Why previous note said "mock mode"**:
- The requirement snippet mentioned: "When OPENAI_API_KEY is absent, demo.py replaces the entire extractor with hardcoded mock"
- This doesn't exist in current code
- The current demo just calls real Ollama

**Improvement Opportunity**:
Use `respx` to mock HTTP calls so demo works without external services:
```python
with respx.mock:
    respx.post("https://api.ollama.ai/chat").mock(
        return_value=httpx.Response(200, json=MOCK_RESPONSE)
    )
    await chat_with_ollama(messages)
```

This is an **enhancement for reliability**, not a critical blocker.

---

## SUMMARY: Which Blockers Are Real?

| # | Blocker | Status | Impact | Action |
|---|---------|--------|--------|--------|
| 1 | Belief dataclass | ✅ Fixed | None | Mark complete |
| 2 | Event loop blocking | ✅ Fixed | None | Mark complete |
| 3 | SQLite connection | ⚠️ Works but inelegant | Low | Add lifecycle mgmt (enhancement) |
| 4 | Demo mocking | ✅ Uses real Ollama | Low | Add respx mocking (improvement) |

---

## Actual Blockers to Address

The real issues are in the **ARCH** category (tasks #5-10):

1. **Dual-adapter pattern**: ✅ **ALREADY IMPLEMENTED**
   - `internal_adapter` parameter exists in `BeliefTracker.__init__`
   - Used for background tasks (extraction, detection)
   - Working as designed

2. **No max_beliefs enforcement**: ⚠️ **REAL ISSUE**
   - Current: `get_context_prompt()` iterates all beliefs
   - Needed: Cap at `config.max_beliefs` (default 50)

3. **No embedding_model versioning**: Dimension mismatch crashes silently
   - Current: Embeddings lack source info
   - Needed: Store `embedding_model` field per belief

4. **No ASK escalation**: Same conflict loops forever
   - Current: ASK conflict notes stack infinitely
   - Needed: Track conflicts, escalate to BLOCK if unresolved

5. **Distributed dispatcher session leak**: Celery/RQ lose session context
   - Current: ContextVar doesn't cross process boundary
   - Needed: Serialize session_id in task payload

6. **No entailment deduplication**: Duplicate beliefs clutter store
   - Current: "likes Python" and "enjoys Python" both stored
   - Needed: Use entailment score to deduplicate

---

## Revised Task Priority

**Mark complete (already done)**:
- #1 Belief Pydantic ✅
- #2 Event loop ✅
- #5 Dual-adapter ✅ (already in tracker.py)

**Real fixes needed (ARCH + missing features)**:
1. Add `max_beliefs` cap to `get_context_prompt()` (Task #6)
2. Add embedding_model field to prevent dimension mismatch (Task #7)
3. Implement ASK escalation logic (Task #8)
4. Fix Celery/RQ session_id propagation (Task #9)
5. Add entailment deduplication (Task #10)
6. Add public query API (Task #11)
7. Implement adapter auto-detection (Task #12)
8. Add streaming support (Task #13)
9. Store-level TTL (Task #14)
10. OpenTelemetry integration (Task #15)

**Nice-to-have enhancements**:
- #3 SQLite lifecycle management (open/close context mgr)
- #4 Demo respx mocking for reliability

