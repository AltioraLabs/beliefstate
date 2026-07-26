import asyncio
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

MOCK_BELIEFS = [
    {
        "subject": "User",
        "predicate": "name",
        "value": "Sarah",
        "confidence": 0.99,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "I am Sarah",
        "turn": 1,
        "resolution_note": "",
    },
    {
        "subject": "User",
        "predicate": "works as",
        "value": "ML Engineer",
        "confidence": 0.97,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "ML engineer",
        "turn": 1,
        "resolution_note": "",
    },
    {
        "subject": "Startup",
        "predicate": "located in",
        "value": "Berlin",
        "confidence": 0.97,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "Berlin",
        "turn": 1,
        "resolution_note": "",
    },
    {
        "subject": "Budget",
        "predicate": "is",
        "value": "USD 20000",
        "confidence": 0.85,
        "belief_type": "update",
        "is_hypothetical": False,
        "category": "constraint",
        "source": "user",
        "source_quote": "budget is USD 20000",
        "turn": 3,
        "resolution_note": "overwrote:USD 12000",
    },
    {
        "subject": "Database",
        "predicate": "is",
        "value": "MongoDB",
        "confidence": 0.85,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "technical",
        "source": "user",
        "source_quote": "using MongoDB",
        "turn": 4,
        "resolution_note": "",
    },
    {
        "subject": "Framework",
        "predicate": "is",
        "value": "TensorFlow",
        "confidence": 0.85,
        "belief_type": "update",
        "is_hypothetical": False,
        "category": "technical",
        "source": "user",
        "source_quote": "switched to TensorFlow",
        "turn": 5,
        "resolution_note": "overwrote:PyTorch",
    },
    {
        "subject": "Team",
        "predicate": "has member",
        "value": "Jake (Backend)",
        "confidence": 0.85,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "Jake is Backend",
        "turn": 2,
        "resolution_note": "",
    },
    {
        "subject": "Team",
        "predicate": "has member",
        "value": "Priya (Frontend)",
        "confidence": 0.85,
        "belief_type": "update",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "Priya is Frontend",
        "turn": 6,
        "resolution_note": "overwrote:Li",
    },
    {
        "subject": "Team",
        "predicate": "has member",
        "value": "Omar (Data)",
        "confidence": 0.85,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "user",
        "source_quote": "Omar is Data",
        "turn": 2,
        "resolution_note": "",
    },
    {
        "subject": "Project",
        "predicate": "is building",
        "value": "real-time recommendation engine",
        "confidence": 0.99,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "planning",
        "source": "user",
        "source_quote": "recommendation engine",
        "turn": 1,
        "resolution_note": "",
    },
    {
        "subject": "Latency",
        "predicate": "target is",
        "value": "100ms",
        "confidence": 0.99,
        "belief_type": "update",
        "is_hypothetical": False,
        "category": "constraint",
        "source": "user",
        "source_quote": "latency target 100ms",
        "turn": 7,
        "resolution_note": "",
    },
    {
        "subject": "PostgreSQL",
        "predicate": "is no longer in stack",
        "value": "true",
        "confidence": 0.85,
        "belief_type": "update",
        "is_hypothetical": False,
        "category": "state",
        "source": "user",
        "source_quote": "removed PostgreSQL",
        "turn": 4,
        "resolution_note": "",
    },
    {
        "subject": "Redis",
        "predicate": "is",
        "value": "in-memory data store",
        "confidence": 0.85,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "technical",
        "source": "assistant",
        "source_quote": "",
        "turn": 2,
        "resolution_note": "",
    },
    {
        "subject": "assistant",
        "predicate": "prefers",
        "value": "TensorFlow",
        "confidence": 0.99,
        "belief_type": "assertion",
        "is_hypothetical": False,
        "category": "identity",
        "source": "assistant",
        "source_quote": "",
        "turn": 5,
        "resolution_note": "",
    },
]


@app.get("/api/sessions")
async def list_sessions():
    return {
        "sessions": ["demo-session-001", "demo-session-002", "support_bot_user_7821"]
    }


@app.get("/api/sessions/{session_id}/beliefs")
async def get_beliefs(session_id: str):
    return {"total": len(MOCK_BELIEFS), "beliefs": MOCK_BELIEFS}


@app.get("/api/sessions/{session_id}/stats")
async def get_stats(session_id: str):
    return {
        "total_beliefs": 14,
        "by_category": {
            "identity": 5,
            "technical": 4,
            "planning": 1,
            "constraint": 2,
            "state": 1,
        },
        "by_source": {"user": 11, "assistant": 3},
        "by_type": {"assertion": 10, "update": 4},
        "by_confidence_range": {
            "0.0-0.5": 0,
            "0.5-0.7": 0,
            "0.7-0.85": 0,
            "0.85-0.95": 1,
            "0.95-1.0": 3,
        },
        "by_hypothetical": {"yes": 0, "no": 14},
        "avg_confidence": 0.91,
        "latest_turn": 7,
        "entities": 9,
        "contradiction_count": 3,
    }


@app.get("/api/sessions/{session_id}/history")
async def get_history(session_id: str):
    return {
        "history": [
            {
                "id": "1",
                "existing_belief": {
                    "subject": "Budget",
                    "predicate": "is",
                    "value": "USD 12000",
                },
                "new_belief": {
                    "subject": "Budget",
                    "predicate": "is",
                    "value": "USD 20000",
                },
                "score": 0.92,
                "reason": "Budget changed",
                "resolution": "overwrite",
                "resolution_note": "overwrote:USD 12000",
                "created_at": "2026-06-29T10:00:00Z",
            },
        ]
    }


@app.get("/api/sessions/{session_id}/conflicts")
async def get_conflicts(session_id: str):
    return {
        "conflicts": [
            {
                "id": "budget/is",
                "existing_belief": {
                    "subject": "Budget",
                    "predicate": "is",
                    "value": "USD 12000",
                },
                "new_belief": {
                    "subject": "Budget",
                    "predicate": "is",
                    "value": "USD 20000",
                },
                "score": 0.92,
                "reason": "Conflicting values: 'USD 12000' vs 'USD 20000'",
                "resolution": "overwrite",
                "resolution_note": "overwrote:USD 12000",
                "escalation_count": 1,
                "created_at": "2026-06-29T10:00:00Z",
            },
            {
                "id": "framework/is",
                "existing_belief": {
                    "subject": "Framework",
                    "predicate": "is",
                    "value": "PyTorch",
                },
                "new_belief": {
                    "subject": "Framework",
                    "predicate": "is",
                    "value": "TensorFlow",
                },
                "score": 0.85,
                "reason": "Conflicting values: 'PyTorch' vs 'TensorFlow'",
                "resolution": "overwrite",
                "resolution_note": "overwrote:PyTorch",
                "escalation_count": 1,
                "created_at": "2026-06-29T10:05:00Z",
            },
            {
                "id": "team/has member",
                "existing_belief": {
                    "subject": "Team",
                    "predicate": "has member",
                    "value": "Li",
                },
                "new_belief": {
                    "subject": "Team",
                    "predicate": "has member",
                    "value": "Priya (Frontend)",
                },
                "score": 0.75,
                "reason": "Conflicting values: 'Li' vs 'Priya (Frontend)'",
                "resolution": "overwrite",
                "resolution_note": "overwrote:Li",
                "escalation_count": 2,
                "created_at": "2026-06-29T10:10:00Z",
            },
        ],
        "pending": [],
    }


@app.get("/api/sessions/{session_id}/activity")
async def get_activity(session_id: str):
    return {
        "activity": [
            {
                "type": "tracking_event",
                "session_id": session_id,
                "timestamp": "2026-06-29T10:15:00Z",
                "data": {"type": "update"},
            },
        ]
    }


@app.get("/api/sessions/{session_id}/entity/{subject}")
async def get_entity(session_id: str, subject: str):
    bs = [b for b in MOCK_BELIEFS if b["subject"].lower() == subject.lower()]
    return {
        "subject": subject,
        "total_beliefs": len(bs),
        "avg_confidence": round(sum(b["confidence"] for b in bs) / max(len(bs), 1), 3),
        "turns_span": len(set(b["turn"] for b in bs)),
        "categories": list(set(b["category"] for b in bs)),
        "types": list(set(b["belief_type"] for b in bs)),
        "beliefs": bs,
    }


@app.get("/api/sessions/{session_id}/timeline/{subject}/{predicate}")
async def get_timeline(session_id: str, subject: str, predicate: str):
    return {
        "target": {"subject": subject, "predicate": predicate},
        "history": [],
        "turns": [],
    }


@app.get("/api/sessions/compare")
async def compare(a: str = "session-a", b: str = "session-b"):
    return {
        "session_a": a,
        "session_b": b,
        "only_in_a": MOCK_BELIEFS[:3],
        "only_in_b": MOCK_BELIEFS[3:6],
        "changed": [],
        "same": MOCK_BELIEFS[6:],
        "summary": {
            "total_a": 14,
            "total_b": 11,
            "only_in_a": 3,
            "only_in_b": 3,
            "changed": 0,
            "same": 7,
        },
    }


@app.get("/api/store/stats")
async def store_stats():
    return {"type": "SQLiteStore", "sessions": 3, "total_beliefs": 42, "healthy": True}


@app.get("/api/config")
async def get_config():
    return {
        "max_beliefs": 50,
        "belief_budget_tokens": 500,
        "similarity_threshold": 0.82,
        "contradiction_threshold": 0.70,
        "entailment_threshold": 0.85,
        "resolution_strategy": "overwrite",
        "respect_strategy_for_updates": False,
        "enable_staleness_scoring": True,
        "staleness_threshold": 0.1,
        "belief_sort_strategy": "confidence_recency",
        "min_injection_confidence": 0.0,
        "include_hypothetical_in_context": False,
        "store_type": "sqlite",
        "enable_dashboard": True,
    }


@app.get("/api/provider/info")
async def provider_info():
    return {
        "internal": {"name": "OpenAIAdapter", "model": "gpt-4o-mini"},
        "app": {"name": "OpenAIAdapter", "model": "gpt-4o"},
        "extractor": {"name": "OpenAIAdapter", "model": "gpt-4o-mini"},
    }


@app.post("/api/sessions/{session_id}/simulate")
async def simulate(session_id: str, request: Request):
    await request.json()
    return {
        "context_prompt": "[Constraints]\n- Budget is USD 20000\n- Latency target is 100ms",
        "extracted_beliefs": [MOCK_BELIEFS[3]],
        "would_inject": True,
        "raw_llm": None,
        "timing_ms": {"context": 12, "extraction": 345, "total": 357},
        "token_estimate": 87,
        "total_beliefs_in_store": 14,
    }


@app.get("/api/events")
async def events(request: Request):
    async def gen():
        while True:
            await asyncio.sleep(30)
            yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(gen())


dist = os.path.join(os.path.dirname(__file__), "..", "beliefstate", "ui_dist")
app.mount("/", StaticFiles(directory=dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    print("\nDashboard with mock data: http://localhost:8000\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)
