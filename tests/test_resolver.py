import pytest
from beliefstate.models import Belief
from beliefstate.resolver import BeliefResolver
from beliefstate.store.sqlite import SQLiteStore


@pytest.mark.asyncio
async def test_resolver_overwrite():
    store = SQLiteStore(db_path=":memory:")
    resolver = BeliefResolver(store=store, strategy="overwrite")

    b_old = Belief(
        subject="USER",
        predicate="likes",
        value="Python",
        confidence=1.0,
        turn=1,
        source="user",
    )
    b_new = Belief(
        subject="USER",
        predicate="likes",
        value="Rust",
        confidence=1.0,
        turn=2,
        source="user",
    )

    # Store old belief first
    await store.add_belief("session_1", b_old)

    # Resolve contradiction
    await resolver.resolve("session_1", [(b_old, b_new, 0.9, "User changed mind")])

    # Check that new belief replaced the old one
    beliefs = await store.get_beliefs("session_1")
    assert len(beliefs) == 1
    assert beliefs[0].value == "Rust"

    # Check pending conflict notes
    conflicts = resolver.pop_pending_conflicts("session_1")
    assert len(conflicts) == 1
    assert "Previously stated: 'Python'. Now asserting: 'Rust'" in conflicts[0]


@pytest.mark.asyncio
async def test_resolver_keep_old():
    store = SQLiteStore(db_path=":memory:")
    resolver = BeliefResolver(store=store, strategy="keep_old")

    b_old = Belief(
        subject="USER",
        predicate="likes",
        value="Python",
        confidence=1.0,
        turn=1,
        source="user",
    )
    b_new = Belief(
        subject="USER",
        predicate="likes",
        value="Rust",
        confidence=1.0,
        turn=2,
        source="user",
    )

    # Store old belief first
    await store.add_belief("session_1", b_old)

    # Resolve contradiction
    await resolver.resolve("session_1", [(b_old, b_new, 0.9, "User changed mind")])

    # Check that old belief was NOT replaced (remains Python)
    beliefs = await store.get_beliefs("session_1")
    assert len(beliefs) == 1
    assert beliefs[0].value == "Python"


@pytest.mark.asyncio
async def test_resolver_raise():
    store = SQLiteStore(db_path=":memory:")
    resolver = BeliefResolver(store=store, strategy="raise")

    b_old = Belief(
        subject="USER",
        predicate="likes",
        value="Python",
        confidence=1.0,
        turn=1,
        source="user",
    )
    b_new = Belief(
        subject="USER",
        predicate="likes",
        value="Rust",
        confidence=1.0,
        turn=2,
        source="user",
    )

    # Store old belief first
    await store.add_belief("session_1", b_old)

    # Resolve contradiction should raise ValueError
    with pytest.raises(ValueError, match="Contradiction detected"):
        await resolver.resolve("session_1", [(b_old, b_new, 0.9, "User changed mind")])


@pytest.mark.asyncio
async def test_resolver_conflict_history_enriched():
    """Validate the /conflicts endpoint logic: conflict_history entries
    produce enriched dicts with old_value parsed from resolution_note."""
    store = SQLiteStore(db_path=":memory:")
    resolver = BeliefResolver(store=store, strategy="overwrite")

    b_old = Belief(
        subject="Color",
        predicate="is",
        value="Blue",
        confidence=1.0,
        turn=1,
        source="user",
    )
    b_new = Belief(
        subject="Color",
        predicate="is",
        value="Red",
        confidence=1.0,
        turn=2,
        source="user",
    )

    await store.add_belief("s1", b_old)
    await resolver.resolve("s1", [(b_old, b_new, 0.85, "User changed favorite")])

    # conflict_history should have the entry
    sid_conflicts = resolver.conflict_history.get("s1", {})
    assert len(sid_conflicts) == 1

    # Simulate what the /conflicts endpoint does
    key = next(iter(sid_conflicts))
    subject, predicate, new_subj, new_pred = key
    all_beliefs = await store.get_beliefs("s1")
    belief_map = {(b.subject.lower(), b.predicate.lower()): b for b in all_beliefs}
    current = belief_map.get((new_subj.lower(), new_pred.lower()))

    assert current is not None
    assert current.value == "Red"
    assert current.resolution_note == "overwrote:Blue"

    old_value = ""
    if current and current.resolution_note.startswith("overwrote:"):
        old_value = current.resolution_note[len("overwrote:") :]
    assert old_value == "Blue"


@pytest.mark.asyncio
async def test_resolver_remove_belief_cleans_conflict_history():
    """Validate resolver.remove_belief() purges entries from conflict tracking."""
    store = SQLiteStore(db_path=":memory:")
    resolver = BeliefResolver(store=store, strategy="overwrite")

    b_old = Belief(
        subject="X", predicate="y", value="old", confidence=1.0, turn=1, source="user"
    )
    b_new = Belief(
        subject="X", predicate="y", value="new", confidence=1.0, turn=2, source="user"
    )

    await store.add_belief("s1", b_old)
    await resolver.resolve("s1", [(b_old, b_new, 0.9, "conflict")])

    assert len(resolver.conflict_history.get("s1", {})) == 1
    assert len(resolver.pending_conflicts.get("s1", [])) == 1

    resolver.remove_belief("s1", "X", "y")

    assert len(resolver.conflict_history.get("s1", {})) == 0
    assert len(resolver.pending_conflicts.get("s1", [])) == 0
