from datetime import datetime, timezone

import pytest

pytest.importorskip("duckdb")

from beliefstate.models import Belief
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate import DuckDBStore as TopLevelDuckDBStore
from beliefstate.store import DuckDBStore
from beliefstate.store.duckdb import DuckDBStore as DirectDuckDBStore


def _make_belief(
    subject: str = "USER",
    predicate: str = "likes",
    value: str = "Python",
    **kwargs: object,
) -> Belief:
    defaults = {
        "confidence": 1.0,
        "turn": 1,
        "source": "user",
        "embedding": [1.0, 0.0, 0.0],
    }
    defaults.update(kwargs)
    return Belief(
        subject=subject,
        predicate=predicate,
        value=value,
        **defaults,
    )


@pytest.mark.asyncio
async def test_duckdb_store_exported():
    assert DuckDBStore is DirectDuckDBStore
    assert TopLevelDuckDBStore is DirectDuckDBStore


@pytest.mark.asyncio
async def test_duckdb_tracker_config_integration():
    config = TrackerConfig(store_type="duckdb", store_kwargs={"db_path": ":memory:"})
    tracker = BeliefTracker(config=config)

    assert isinstance(tracker.store, DirectDuckDBStore)


@pytest.mark.asyncio
async def test_duckdb_add_get_update_remove():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        belief = _make_belief(session_id="s1")
        await store.add_belief("s1", belief)

        retrieved = await store.get_beliefs("s1")
        assert len(retrieved) == 1
        assert retrieved[0].subject == "user"
        assert retrieved[0].value == "Python"
        assert retrieved[0].session_id == "s1"

        updated = _make_belief(value="DuckDB", turn=2, session_id="s1")
        await store.update_belief("s1", updated)

        beliefs = await store.get_beliefs("s1")
        assert len(beliefs) == 1
        assert beliefs[0].value == "DuckDB"

        await store.remove_belief("s1", "USER", "likes")
        assert await store.get_beliefs("s1") == []


@pytest.mark.asyncio
async def test_duckdb_search_beliefs_with_native_similarity():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        await store.add_belief(
            "s1",
            _make_belief(value="apples", embedding=[1.0, 0.0, 0.0]),
        )
        await store.add_belief(
            "s1",
            _make_belief(
                predicate="hates",
                value="bananas",
                turn=2,
                embedding=[0.0, 1.0, 0.0],
            ),
        )

        results = await store.search_beliefs(
            "s1", [1.0, 0.1, 0.0], threshold=0.7, limit=5
        )

        assert len(results) == 1
        assert results[0].value == "apples"


@pytest.mark.asyncio
async def test_duckdb_search_skips_empty_and_mismatched_embeddings():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        await store.add_belief(
            "s1",
            _make_belief(value="match", embedding=[1.0, 0.0, 0.0]),
        )
        await store.add_belief(
            "s1",
            _make_belief(
                predicate="knows",
                value="empty",
                turn=2,
                embedding=[],
            ),
        )
        await store.add_belief(
            "s1",
            _make_belief(
                predicate="uses",
                value="different dimension",
                turn=3,
                embedding=[1.0, 0.0],
            ),
        )

        results = await store.search_beliefs(
            "s1", [1.0, 0.0, 0.0], threshold=0.7, limit=5
        )

    assert len(results) == 1
    assert results[0].value == "match"


@pytest.mark.asyncio
async def test_duckdb_conversation_filtering():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        await store.add_belief(
            "s1",
            _make_belief(value="Python", conversation_id="c1"),
        )
        await store.add_belief(
            "s1",
            _make_belief(
                predicate="hates",
                value="Java",
                turn=2,
                conversation_id="c2",
            ),
        )

        conv1 = await store.get_beliefs("s1", conversation_id="c1")
        assert len(conv1) == 1
        assert conv1[0].value == "Python"

        results = await store.search_beliefs(
            "s1", [1.0, 0.0, 0.0], threshold=0.5, conversation_id="c2"
        )
        assert len(results) == 1
        assert results[0].value == "Java"


@pytest.mark.asyncio
async def test_duckdb_file_persistence(tmp_path):
    db_path = tmp_path / "beliefs.duckdb"

    async with DirectDuckDBStore(db_path=str(db_path)) as store:
        await store.add_belief("s1", _make_belief(session_id="s1"))

    async with DirectDuckDBStore(db_path=str(db_path)) as store:
        beliefs = await store.get_beliefs("s1")

    assert len(beliefs) == 1
    assert beliefs[0].value == "Python"


@pytest.mark.asyncio
async def test_duckdb_upsert_rejects_stale_belief():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        newer = _make_belief(value="newer", turn=5, session_id="s1")
        older = _make_belief(value="older", turn=4, session_id="s1")

        assert await store.upsert(newer) is True
        assert await store.upsert(older) is False

        beliefs = await store.get_beliefs("s1")
        assert len(beliefs) == 1
        assert beliefs[0].value == "newer"


@pytest.mark.asyncio
async def test_duckdb_audit_history_records_changes():
    async with DirectDuckDBStore(db_path=":memory:") as store:
        created_at = datetime.now(timezone.utc)
        await store.add_belief(
            "s1",
            _make_belief(value="first", created_at=created_at, session_id="s1"),
        )
        await store.add_belief(
            "s1",
            _make_belief(value="second", turn=2, session_id="s1"),
        )

        history = await store.get_audit_history("s1", "user", "likes")

    assert [entry["operation"] for entry in history] == [
        "create",
        "contradiction_update",
    ]
    assert history[1]["old_value"] == "first"
    assert history[1]["new_value"] == "second"
