import json
import csv
import io
import os
import queue
import asyncio
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from beliefstate.tracker import BeliefTracker
from beliefstate.models import Belief

tracker_instance: Optional[BeliefTracker] = None
_sync_queue: queue.Queue = queue.Queue()
_activity_log: List[Dict[str, Any]] = []
_MAX_ACTIVITY = 500


class BeliefCreate(BaseModel):
    subject: str
    predicate: str
    value: str
    confidence: float = 0.9
    belief_type: str = "assertion"
    is_hypothetical: bool = False
    category: str = "identity"
    source: str = "user"
    source_quote: str = ""
    turn: int = 0


class SimulateRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    max_beliefs: Optional[int] = None
    belief_budget_tokens: Optional[int] = None
    similarity_threshold: Optional[float] = None
    contradiction_threshold: Optional[float] = None
    entailment_threshold: Optional[float] = None
    resolution_strategy: Optional[str] = None
    respect_strategy_for_updates: Optional[bool] = None
    enable_staleness_scoring: Optional[bool] = None
    staleness_threshold: Optional[float] = None
    belief_sort_strategy: Optional[str] = None
    min_injection_confidence: Optional[float] = None
    extract_prompt_template: Optional[str] = None


class ReExtractRequest(BaseModel):
    custom_prompt: Optional[str] = None
    message: Optional[str] = None


def set_tracker(tracker: BeliefTracker):
    global tracker_instance
    tracker_instance = tracker


def get_tracker() -> BeliefTracker:
    if tracker_instance is None:
        raise HTTPException(status_code=503, detail="Tracker not initialized")
    return tracker_instance


def get_event_queue() -> queue.Queue:
    return _sync_queue


async def push_tracker_event(event: Dict[str, Any]) -> None:
    """Callback registered on BeliefTracker to push real pipeline events to SSE."""
    _sync_queue.put_nowait(event)
    push_activity("tracking_event", event.get("session_id", "?"), event)


def push_activity(event_type: str, session_id: str, data: Dict[str, Any]):
    entry = {
        "type": event_type,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    _activity_log.append(entry)
    if len(_activity_log) > _MAX_ACTIVITY:
        _activity_log.pop(0)


def make_belief_dict(b: Belief) -> Dict[str, Any]:
    return {
        "subject": b.subject,
        "predicate": b.predicate,
        "value": b.value,
        "confidence": b.confidence,
        "belief_type": b.belief_type,
        "is_hypothetical": getattr(b, "is_hypothetical", False),
        "category": b.category or "general",
        "source": b.source,
        "source_quote": b.source_quote,
        "turn": b.turn,
        "resolution_note": getattr(b, "resolution_note", ""),
        "created_at": b.created_at.isoformat() if b.created_at else "",
    }


app = FastAPI(title="BeliefState Dashboard", version="0.2.0")


async def sse_event_generator():
    loop = asyncio.get_running_loop()
    sync_q = get_event_queue()
    while True:
        event = await loop.run_in_executor(None, sync_q.get)
        yield {"event": "update", "data": json.dumps(event)}


@app.get("/api/events")
async def events_endpoint(request: Request):
    return EventSourceResponse(sse_event_generator(), ping=15)


@app.get("/api/sessions")
async def list_sessions():
    tracker = get_tracker()
    if hasattr(tracker.store, "get_all_session_ids"):
        sessions = await tracker.store.get_all_session_ids()
    else:
        sessions = []
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}/beliefs")
async def get_beliefs(
    session_id: str,
    conversation_id: Optional[str] = None,
    include_hypothetical: bool = False,
    min_confidence: float = 0.0,
    source: Optional[str] = None,
    category: Optional[str] = None,
    belief_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
):
    tracker = get_tracker()
    beliefs = await tracker.store.get_beliefs(session_id, conversation_id)

    if search:
        s = search.lower()
        beliefs = [
            b
            for b in beliefs
            if s in b.subject.lower()
            or s in b.predicate.lower()
            or s in b.value.lower()
        ]
    if not include_hypothetical:
        beliefs = [b for b in beliefs if not getattr(b, "is_hypothetical", False)]
    if min_confidence > 0:
        beliefs = [b for b in beliefs if b.confidence >= min_confidence]
    if source:
        beliefs = [b for b in beliefs if b.source == source]
    if category:
        beliefs = [b for b in beliefs if (b.category or "general") == category]
    if belief_type:
        beliefs = [b for b in beliefs if b.belief_type == belief_type]

    total = len(beliefs)
    beliefs = sorted(beliefs, key=lambda b: b.turn, reverse=True)
    beliefs = beliefs[offset : offset + limit]

    return {"total": total, "beliefs": [make_belief_dict(b) for b in beliefs]}


@app.post("/api/sessions/{session_id}/beliefs")
async def create_belief(session_id: str, belief_data: BeliefCreate):
    tracker = get_tracker()
    belief = Belief(**belief_data.model_dump())
    await tracker.store.add_belief(session_id, belief)
    push_activity("belief_created", session_id, belief_data.model_dump())
    _sync_queue.put_nowait(
        {
            "type": "belief_created",
            "session_id": session_id,
            "belief": belief_data.model_dump(),
        }
    )
    return {"status": "created", "belief": belief_data.model_dump()}


@app.delete("/api/sessions/{session_id}/beliefs/{subject}/{predicate}")
async def delete_belief(session_id: str, subject: str, predicate: str):
    tracker = get_tracker()
    await tracker.store.remove_belief(session_id, subject, predicate)

    # Purge from resolver conflict tracking
    tracker.resolver.remove_belief(session_id, subject, predicate)

    push_activity(
        "belief_deleted", session_id, {"subject": subject, "predicate": predicate}
    )
    _sync_queue.put_nowait(
        {
            "type": "belief_deleted",
            "session_id": session_id,
            "subject": subject,
            "predicate": predicate,
        }
    )
    return {"status": "deleted"}


@app.get("/api/sessions/{session_id}/history")
async def get_history(
    session_id: str, subject: Optional[str] = None, predicate: Optional[str] = None
):
    tracker = get_tracker()
    history = []
    if hasattr(tracker.store, "get_audit_history"):
        if subject and predicate:
            history = await tracker.store.get_audit_history(
                session_id, subject, predicate
            )
        elif hasattr(tracker.store, "get_all_audit_history"):
            history = await tracker.store.get_all_audit_history(session_id)
    return {"history": history}


@app.get("/api/sessions/{session_id}/conflicts")
async def get_conflicts(session_id: str):
    tracker = get_tracker()
    resolver = tracker.resolver

    sid_conflicts = getattr(resolver, "conflict_history", {}).get(session_id, {})
    pending = getattr(resolver, "pending_conflicts", {}).get(session_id, [])

    all_beliefs = await tracker.store.get_beliefs(session_id)
    belief_map = {(b.subject.lower(), b.predicate.lower()): b for b in all_beliefs}

    conflicts = []
    seen_keys = set()
    for key, escalation_count in sid_conflicts.items():
        subject, predicate, new_subj, new_pred = key
        subj_lower = subject.lower()
        pred_lower = predicate.lower()
        cid = f"{subj_lower}/{pred_lower}"
        seen_keys.add(cid)

        current = belief_map.get((new_subj.lower(), new_pred.lower()))
        new_value = current.value if current else ""
        old_value = ""
        if current and current.resolution_note.startswith("overwrote:"):
            old_value = current.resolution_note[len("overwrote:") :]

        conflicts.append(
            {
                "id": cid,
                "existing_belief": {
                    "subject": subject,
                    "predicate": predicate,
                    "value": old_value,
                },
                "new_belief": {
                    "subject": new_subj,
                    "predicate": new_pred,
                    "value": new_value,
                },
                "score": current.confidence if current else 0.0,
                "reason": f"Conflicting values: '{old_value}' vs '{new_value}'"
                if old_value
                else f"Escalated {escalation_count}x",
                "resolution": "overwrite" if escalation_count > 0 else "pending",
                "resolution_note": current.resolution_note if current else "",
                "escalation_count": escalation_count,
                "created_at": current.created_at.isoformat()
                if current and current.created_at
                else "",
            }
        )

    if hasattr(tracker.store, "get_all_audit_history"):
        try:
            history = await tracker.store.get_all_audit_history(session_id)
            for h in history:
                if h.get("operation") in ("contradiction_update", "create"):
                    subj = h.get("subject", "")
                    pred = h.get("predicate", "")
                    cid = f"{subj.lower()}/{pred.lower()}"
                    if cid in seen_keys:
                        continue
                    if h.get("operation") == "create" and h.get("old_value") is None:
                        continue
                    conflicts.append(
                        {
                            "id": h.get("id", 0),
                            "existing_belief": {
                                "subject": subj,
                                "predicate": pred,
                                "value": h.get("old_value", ""),
                            },
                            "new_belief": {
                                "subject": subj,
                                "predicate": pred,
                                "value": h.get("new_value", ""),
                            },
                            "score": h.get("confidence", 0.0),
                            "reason": f"Conflicting values: '{h.get('old_value', '?')}' vs '{h.get('new_value', '?')}'",
                            "resolution": "overwrite",
                            "resolution_note": f"overwrote:{h['old_value']}"
                            if h.get("old_value")
                            else "",
                            "escalation_count": 0,
                            "created_at": h.get("created_at", ""),
                        }
                    )
        except Exception:
            pass

    return {"conflicts": conflicts, "pending": pending}


@app.get("/api/sessions/{session_id}/timeline/{subject}/{predicate}")
async def get_timeline(session_id: str, subject: str, predicate: str):
    tracker = get_tracker()
    history = []
    if hasattr(tracker.store, "get_audit_history"):
        history = await tracker.store.get_audit_history(session_id, subject, predicate)

    all_beliefs = await tracker.store.get_beliefs(session_id)

    turns: Dict[int, List[Dict]] = {}
    for b in all_beliefs:
        t = b.turn
        if t not in turns:
            turns[t] = []
        turns[t].append(make_belief_dict(b))

    return {
        "target": {"subject": subject, "predicate": predicate},
        "history": history,
        "turns": [
            {"turn": t, "beliefs": beliefs} for t, beliefs in sorted(turns.items())
        ],
    }


@app.get("/api/sessions/{session_id}/entity/{subject}")
async def get_entity_profile(session_id: str, subject: str):
    tracker = get_tracker()
    beliefs = await tracker.store.get_beliefs(session_id)
    entity_beliefs = [b for b in beliefs if b.subject.lower() == subject.lower()]

    turns = sorted(set(b.turn for b in entity_beliefs))
    total_beliefs = len(entity_beliefs)
    avg_confidence = sum(b.confidence for b in entity_beliefs) / max(total_beliefs, 1)
    categories = list(set(b.category or "general" for b in entity_beliefs))
    types = list(set(b.belief_type for b in entity_beliefs))

    return {
        "subject": subject,
        "total_beliefs": total_beliefs,
        "avg_confidence": round(avg_confidence, 3),
        "turns_span": len(turns),
        "categories": categories,
        "types": types,
        "beliefs": [
            make_belief_dict(b)
            for b in sorted(entity_beliefs, key=lambda x: x.turn, reverse=True)
        ],
    }


@app.get("/api/sessions/{session_id}/stats")
async def get_detailed_stats(session_id: str):
    tracker = get_tracker()
    beliefs = await tracker.store.get_beliefs(session_id)
    total = len(beliefs)
    if total == 0:
        return {
            "total_beliefs": 0,
            "by_category": {},
            "by_source": {},
            "by_type": {},
            "by_confidence_range": {},
            "by_hypothetical": {"yes": 0, "no": 0},
            "avg_confidence": 0,
            "latest_turn": 0,
            "entities": 0,
            "contradiction_count": 0,
        }

    by_cat: Dict[str, int] = {}
    by_src: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    conf_ranges: Dict[str, int] = {
        "0.0-0.5": 0,
        "0.5-0.7": 0,
        "0.7-0.85": 0,
        "0.85-0.95": 0,
        "0.95-1.0": 0,
    }
    hypo = 0
    total_conf = 0
    max_turn = 0
    entities = set()

    for b in beliefs:
        cat = b.category or "general"
        by_cat[cat] = by_cat.get(cat, 0) + 1
        by_src[b.source] = by_src.get(b.source, 0) + 1
        by_type[b.belief_type] = by_type.get(b.belief_type, 0) + 1
        total_conf += b.confidence
        max_turn = max(max_turn, b.turn)
        entities.add(b.subject.lower())
        if getattr(b, "is_hypothetical", False):
            hypo += 1
        c = b.confidence
        if c < 0.5:
            conf_ranges["0.0-0.5"] += 1
        elif c < 0.7:
            conf_ranges["0.5-0.7"] += 1
        elif c < 0.85:
            conf_ranges["0.7-0.85"] += 1
        elif c < 0.95:
            conf_ranges["0.85-0.95"] += 1
        else:
            conf_ranges["0.95-1.0"] += 1

    conflict_count = 0
    conflict_history = getattr(tracker.resolver, "conflict_history", {})
    sid_conflicts = conflict_history.get(session_id, {})
    conflict_count = len(sid_conflicts)
    if conflict_count == 0 and hasattr(tracker.store, "get_all_audit_history"):
        try:
            history = await tracker.store.get_all_audit_history(session_id)
            conflict_count = len(
                [h for h in history if h.get("operation") == "contradiction_update"]
            )
        except Exception:
            pass

    return {
        "total_beliefs": total,
        "by_category": by_cat,
        "by_source": by_src,
        "by_type": by_type,
        "by_confidence_range": conf_ranges,
        "by_hypothetical": {"yes": hypo, "no": total - hypo},
        "avg_confidence": round(total_conf / total, 3),
        "latest_turn": max_turn,
        "entities": len(entities),
        "contradiction_count": conflict_count,
    }


@app.get("/api/sessions/{session_id}/activity")
async def get_activity(session_id: str, limit: int = 50):
    filtered = [
        e
        for e in reversed(_activity_log)
        if e["session_id"] == session_id or e["session_id"] == "?"
    ]
    return {"activity": filtered[:limit]}


@app.get("/api/sessions/{session_id}/export/csv")
async def export_csv(session_id: str):
    tracker = get_tracker()
    beliefs = await tracker.store.get_beliefs(session_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "subject",
            "predicate",
            "value",
            "confidence",
            "belief_type",
            "category",
            "source",
            "turn",
            "is_hypothetical",
            "resolution_note",
        ]
    )
    for b in sorted(beliefs, key=lambda x: x.turn):
        writer.writerow(
            [
                b.subject,
                b.predicate,
                b.value,
                b.confidence,
                b.belief_type,
                b.category or "general",
                b.source,
                b.turn,
                getattr(b, "is_hypothetical", False),
                getattr(b, "resolution_note", ""),
            ]
        )

    csv_content = output.getvalue()
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=beliefs-{session_id}.csv"
        },
    )


@app.get("/api/sessions/compare")
async def compare_sessions(session_a: str, session_b: str):
    tracker = get_tracker()
    beliefs_a = await tracker.store.get_beliefs(session_a)
    beliefs_b = await tracker.store.get_beliefs(session_b)

    def key(b):
        return (b.subject.lower(), b.predicate.lower())

    map_a = {key(b): b for b in beliefs_a}
    map_b = {key(b): b for b in beliefs_b}

    only_in_a = []
    only_in_b = []
    changed = []
    same = []

    all_keys = set(map_a.keys()) | set(map_b.keys())
    for k in all_keys:
        ba = map_a.get(k)
        bb = map_b.get(k)
        if ba and not bb:
            only_in_a.append(make_belief_dict(ba))
        elif bb and not ba:
            only_in_b.append(make_belief_dict(bb))
        elif ba and bb:
            if ba.value != bb.value or ba.confidence != bb.confidence:
                changed.append(
                    {
                        "subject": k[0],
                        "predicate": k[1],
                        "old": make_belief_dict(ba),
                        "new": make_belief_dict(bb),
                    }
                )
            else:
                same.append(make_belief_dict(ba))

    return {
        "session_a": session_a,
        "session_b": session_b,
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "changed": changed,
        "same": same,
        "summary": {
            "total_a": len(beliefs_a),
            "total_b": len(beliefs_b),
            "only_in_a": len(only_in_a),
            "only_in_b": len(only_in_b),
            "changed": len(changed),
            "same": len(same),
        },
    }


@app.get("/api/store/stats")
async def get_store_stats():
    tracker = get_tracker()
    store = tracker.store
    stats = {"type": type(store).__name__}

    sessions = []
    if hasattr(store, "get_all_session_ids"):
        sessions = await store.get_all_session_ids()
    stats["sessions"] = len(sessions)

    total_beliefs = 0
    for s in sessions:
        try:
            total_beliefs += await store.belief_count(s)
        except Exception:
            pass
    stats["total_beliefs"] = total_beliefs

    try:
        stats["healthy"] = await store.health_check()
    except Exception:
        stats["healthy"] = False

    return stats


@app.get("/api/config")
async def get_config():
    tracker = get_tracker()
    c = tracker.config
    return {
        "max_beliefs": c.max_beliefs,
        "belief_budget_tokens": c.belief_budget_tokens,
        "similarity_threshold": c.similarity_threshold,
        "contradiction_threshold": c.contradiction_threshold,
        "entailment_threshold": c.entailment_threshold,
        "resolution_strategy": c.resolution_strategy,
        "respect_strategy_for_updates": c.respect_strategy_for_updates,
        "enable_staleness_scoring": c.enable_staleness_scoring,
        "staleness_threshold": c.staleness_threshold,
        "belief_sort_strategy": c.belief_sort_strategy,
        "min_injection_confidence": getattr(c, "min_injection_confidence", 0.0),
        "include_hypothetical_in_context": getattr(
            c, "include_hypothetical_in_context", False
        ),
        "store_type": c.store_type,
        "enable_dashboard": getattr(c, "enable_dashboard", False),
    }


@app.post("/api/config")
async def update_config(update: ConfigUpdate):
    tracker = get_tracker()
    c = tracker.config
    changed = []
    for field, value in update.model_dump(exclude_none=True).items():
        if hasattr(c, field) and getattr(c, field) != value:
            setattr(c, field, value)
            changed.append(field)
    push_activity("config_updated", "system", {"changed": changed})
    return {"status": "updated", "changed": changed}


@app.get("/api/provider/info")
async def get_provider_info():
    tracker = get_tracker()
    info: Dict[str, Any] = {}

    if tracker.internal_adapter:
        try:
            name = (
                getattr(tracker.internal_adapter, "display_name", None)
                or type(tracker.internal_adapter).__name__
            )
            model = getattr(tracker.internal_adapter, "model", None) or getattr(
                tracker.internal_adapter, "default_model", None
            )
            info["internal"] = {"name": name, "model": model}
        except Exception:
            info["internal"] = {"name": "unknown"}

    if tracker.app_adapter:
        try:
            name = (
                getattr(tracker.app_adapter, "display_name", None)
                or type(tracker.app_adapter).__name__
            )
            model = getattr(tracker.app_adapter, "model", None) or getattr(
                tracker.app_adapter, "default_model", None
            )
            info["app"] = {"name": name, "model": model}
        except Exception:
            info["app"] = {"name": "unknown"}

    if tracker.extractor and hasattr(tracker.extractor, "adapter"):
        try:
            name = (
                getattr(tracker.extractor.adapter, "display_name", None)
                or type(tracker.extractor.adapter).__name__
            )
            model = getattr(tracker.extractor.adapter, "model", None)
            info["extractor"] = {"name": name, "model": model}
        except Exception:
            info["extractor"] = {"name": "unknown"}

    return info


@app.post("/api/sessions/{session_id}/simulate")
async def simulate_injection(session_id: str, request: SimulateRequest):
    tracker = get_tracker()
    t0 = time.time()

    context_prompt = await tracker.get_context_prompt(
        session_id=session_id,
        conversation_id=request.conversation_id,
        current_user_message=request.message,
    )
    t1 = time.time()

    beliefs = await tracker.store.get_beliefs(session_id, request.conversation_id)
    total_beliefs = len(beliefs)

    extracted = []
    raw_llm = None
    if tracker.extractor:
        try:
            messages = [{"role": "user", "content": request.message}]
            new_beliefs = await tracker.extractor.extract_beliefs(
                messages,
                session_id=session_id,
                conversation_id=request.conversation_id,
            )
            extracted = [make_belief_dict(b) for b in new_beliefs]
        except Exception as e:
            raw_llm = f"Extraction error: {e}"
    t2 = time.time()

    token_estimate = len(context_prompt) // 4 if context_prompt else 0

    push_activity(
        "simulation",
        session_id,
        {
            "message": request.message[:100],
            "extracted": len(extracted),
            "context_tokens": token_estimate,
        },
    )

    return {
        "context_prompt": context_prompt,
        "extracted_beliefs": extracted,
        "would_inject": bool(context_prompt.strip()),
        "raw_llm": raw_llm,
        "timing_ms": {
            "context": round((t1 - t0) * 1000),
            "extraction": round((t2 - t1) * 1000),
            "total": round((t2 - t0) * 1000),
        },
        "token_estimate": token_estimate,
        "total_beliefs_in_store": total_beliefs,
    }


@app.post("/api/sessions/{session_id}/re-extract")
async def re_extract(session_id: str, request: ReExtractRequest):
    tracker = get_tracker()
    if not tracker.extractor:
        raise HTTPException(status_code=400, detail="No extractor configured")

    full_content = (
        "*No specific message provided. Re-extracting with existing store context.*"
    )
    if request.message:
        full_content = request.message

    messages = [{"role": "user", "content": full_content}]

    original_prompt = tracker.config.extract_prompt_template
    if request.custom_prompt:
        tracker.config.extract_prompt_template = request.custom_prompt

    try:
        extracted = await tracker.extractor.extract_beliefs(
            messages,
            session_id=session_id,
        )
        result = [make_belief_dict(b) for b in extracted]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if request.custom_prompt:
            tracker.config.extract_prompt_template = original_prompt

    return {"extracted": result, "count": len(result)}


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "beliefstate", "ui_dist")
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
