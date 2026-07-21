"""Advanced tests for BeliefTracker — helpers, GDPR, context injection, staleness, stats."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from beliefstate.config import TrackerConfig
from beliefstate.models import Belief
from beliefstate.tracker import (
    BeliefTracker,
    session_context,
    calculate_staleness_score,
    estimate_tokens,
    _detect_adapter,
    _ensure_aware,
)


def make_config(**kwargs):
    store_kwargs = kwargs.pop("store_kwargs", {"db_path": ":memory:"})
    return TrackerConfig(
        enable_background_tasks=False, store_kwargs=store_kwargs, **kwargs
    )


# ── Pure helper function tests ───────────────────────────────────────────


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # "hello" = 5 chars → ceil(5/4) = 2 tokens
        assert estimate_tokens("hello") == 2

    def test_longer_string(self):
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_default_backend_is_heuristic(self):
        # Default keeps the historical behaviour so callers/tests stay stable.
        assert estimate_tokens("hello world") == estimate_tokens(
            "hello world", backend="heuristic"
        )

    def test_empty_string_any_backend(self):
        assert estimate_tokens("", backend="tiktoken") == 0

    def test_tiktoken_backend_counts_tokens(self):
        pytest.importorskip("tiktoken")
        # A known phrase encodes to a small, stable token count with cl100k_base.
        assert estimate_tokens("hello world", backend="tiktoken") == 2

    def test_tiktoken_backend_with_model(self):
        pytest.importorskip("tiktoken")
        n = estimate_tokens("The quick brown fox", backend="tiktoken", model="gpt-4o")
        assert n > 0

    def test_tiktoken_unknown_model_falls_back_to_encoding(self):
        pytest.importorskip("tiktoken")
        # An unknown model name must not raise; it uses cl100k_base instead.
        n = estimate_tokens("hello", backend="tiktoken", model="not-a-real-model")
        assert n > 0

    def test_tiktoken_beats_heuristic_on_cjk(self):
        pytest.importorskip("tiktoken")
        # CJK text is badly under-counted by len/4; tiktoken counts more tokens.
        cjk = "你好世界，这是一个测试。"
        assert estimate_tokens(cjk, backend="tiktoken") > estimate_tokens(cjk)

    def test_falls_back_to_heuristic_when_tiktoken_missing(self, monkeypatch):
        import beliefstate.tracker as tracker_mod

        # Simulate tiktoken being unavailable regardless of the environment.
        monkeypatch.setattr(
            tracker_mod, "_get_tiktoken_encoder", lambda model: None
        )
        text = "a" * 100
        assert estimate_tokens(text, backend="tiktoken") == 25


class TestEnsureAware:
    def test_naive_datetime_becomes_aware(self):
        naive = datetime(2024, 1, 1, 12, 0, 0)
        aware = _ensure_aware(naive)
        assert aware.tzinfo is not None
        assert aware.tzinfo == timezone.utc

    def test_already_aware_unchanged(self):
        aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = _ensure_aware(aware)
        assert result == aware


class TestCalculateStalenessScore:
    def test_recent_belief_high_score(self):
        b = Belief(
            subject="U",
            predicate="p",
            value="v",
            confidence=1.0,
            turn=1,
            source="user",
            last_referenced_at=datetime.now(timezone.utc),
        )
        score = calculate_staleness_score(b)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_old_belief_lower_score(self):
        b = Belief(
            subject="U",
            predicate="p",
            value="v",
            confidence=1.0,
            turn=1,
            source="user",
            last_referenced_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        score = calculate_staleness_score(b)
        assert score < 0.5  # 1.0 / (10 + 1) ≈ 0.09

    def test_low_confidence_capped(self):
        b = Belief(
            subject="U",
            predicate="p",
            value="v",
            confidence=0.5,
            turn=1,
            source="user",
            last_referenced_at=datetime.now(timezone.utc),
        )
        score = calculate_staleness_score(b)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_no_last_referenced_falls_back_to_created_at(self):
        b = MagicMock()
        b.last_referenced_at = None
        b.created_at = datetime.now(timezone.utc)
        b.confidence = 0.8
        score = calculate_staleness_score(b)
        assert score == pytest.approx(0.8, abs=0.01)


# ── Adapter auto-detection ───────────────────────────────────────────────


class TestDetectAdapter:
    def test_unknown_type_returns_generic(self):
        result = MagicMock()
        result.__class__.__module__ = "some.unknown.module"
        result.__class__.__name__ = "SomeResult"
        adapter = _detect_adapter(result)
        # Should be a GenericAdapter (has to_llm_call, to_llm_response)
        assert hasattr(adapter, "to_llm_call")
        assert hasattr(adapter, "to_llm_response")


# ── Session management ───────────────────────────────────────────────────


class TestSessionManagement:
    def test_set_session(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        tracker.set_session("user_42")
        assert session_context.get() == "user_42"
        # Reset
        session_context.set("default")


# ── get_beliefs / get_stats / get_summary ────────────────────────────────


class TestTrackerQueryMethods:
    @pytest.mark.asyncio
    async def test_get_beliefs_returns_stored(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        b = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("s1", b)

        beliefs = await tracker.get_beliefs("s1")
        assert len(beliefs) == 1
        assert beliefs[0].value == "Python"

    @pytest.mark.asyncio
    async def test_get_stats_empty_session(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        stats = await tracker.get_stats_dict("empty_session")
        assert stats["total_beliefs"] == 0
        assert stats["avg_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_get_stats_with_beliefs(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b1 = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=0.8,
            turn=1,
            source="user",
        )
        b2 = Belief(
            subject="USER",
            predicate="lives in",
            value="Paris",
            confidence=1.0,
            turn=2,
            source="user",
        )
        await tracker.store.add_belief("s1", b1)
        await tracker.store.add_belief("s1", b2)

        stats = await tracker.get_stats_dict("s1")
        assert stats["total_beliefs"] == 2
        assert stats["avg_confidence"] == pytest.approx(0.9, abs=0.01)
        assert stats["by_subject"]["user"] == 2
        assert stats["by_source"]["user"] == 2

    @pytest.mark.asyncio
    async def test_get_summary_empty(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        summary = await tracker.get_summary("empty")
        assert summary == ""

    @pytest.mark.asyncio
    async def test_get_summary_max_beliefs(self):
        config = make_config(max_beliefs=2)
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        for i in range(5):
            b = Belief(
                subject="USER",
                predicate=f"fact_{i}",
                value=f"v{i}",
                confidence=1.0,
                turn=i,
                source="user",
            )
            await tracker.store.add_belief("s1", b)

        summary = await tracker.get_summary("s1")
        # Should only have 2 beliefs (max_beliefs=2)
        assert summary.count("- user") == 2


# ── GDPR clear_session ───────────────────────────────────────────────────


class TestGDPRDeletion:
    @pytest.mark.asyncio
    async def test_clear_session_returns_receipt(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("gdpr_test_session", b)

        receipt = await tracker.clear_session("gdpr_test_session")
        assert receipt.session_id == "gdpr_test_session"
        assert receipt.beliefs_deleted == 1
        assert receipt.deleted_at is not None

        # Verify beliefs are actually gone
        assert await tracker.get_beliefs("gdpr_test_session") == []

    @pytest.mark.asyncio
    async def test_clear_session_empty(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        receipt = await tracker.clear_session("empty_session")
        assert receipt.beliefs_deleted == 0


# ── Context injection ────────────────────────────────────────────────────


class TestContextInjection:
    @pytest.mark.asyncio
    async def test_get_context_prompt_respects_max_beliefs(self):
        config = make_config(
            max_beliefs=3,
            enable_staleness_scoring=False,
        )
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        for i in range(10):
            b = Belief(
                subject="USER",
                predicate=f"fact_{i}",
                value=f"v{i}",
                confidence=1.0,
                turn=i,
                source="user",
            )
            await tracker.store.add_belief("s1", b)

        prompt = await tracker.get_context_prompt("s1")
        # Should only include 3 beliefs
        assert prompt.count("- user") == 3

    @pytest.mark.asyncio
    async def test_get_context_prompt_filters_hypothetical(self):
        config = make_config(
            enable_staleness_scoring=False,
        )
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b_real = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
            is_hypothetical=False,
        )
        b_hypo = Belief(
            subject="USER",
            predicate="would_buy",
            value="Ferrari",
            confidence=0.9,
            turn=2,
            source="user",
            is_hypothetical=True,
        )
        await tracker.store.add_belief("s1", b_real)
        await tracker.store.add_belief("s1", b_hypo)

        prompt = await tracker.get_context_prompt("s1")
        assert "Python" in prompt
        assert "Ferrari" not in prompt

    @pytest.mark.asyncio
    async def test_get_context_prompt_empty_session(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        prompt = await tracker.get_context_prompt("empty")
        assert prompt == ""

    @pytest.mark.asyncio
    async def test_get_context_prompt_sort_by_recency(self):
        config = make_config(
            belief_sort_strategy="recency",
            enable_staleness_scoring=False,
        )
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b1 = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
        )
        b2 = Belief(
            subject="USER",
            predicate="hates",
            value="Java",
            confidence=1.0,
            turn=10,
            source="user",
        )
        await tracker.store.add_belief("s1", b1)
        await tracker.store.add_belief("s1", b2)

        prompt = await tracker.get_context_prompt("s1")
        # Most recent (turn=10) should appear first
        java_pos = prompt.find("Java")
        python_pos = prompt.find("Python")
        assert java_pos < python_pos


# ── clear_beliefs / remove_belief ────────────────────────────────────────


class TestClearAndRemove:
    @pytest.mark.asyncio
    async def test_clear_beliefs(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("s1", b)
        await tracker.clear_beliefs("s1")
        assert await tracker.get_beliefs("s1") == []

    @pytest.mark.asyncio
    async def test_remove_specific_belief(self):
        config = make_config()
        mock_adapter = MagicMock()
        tracker = BeliefTracker(config=config, adapter=mock_adapter)

        b1 = Belief(
            subject="USER",
            predicate="likes",
            value="Python",
            confidence=1.0,
            turn=1,
            source="user",
        )
        b2 = Belief(
            subject="USER",
            predicate="lives in",
            value="Paris",
            confidence=1.0,
            turn=2,
            source="user",
        )
        await tracker.store.add_belief("s1", b1)
        await tracker.store.add_belief("s1", b2)

        await tracker.remove_belief("s1", "USER", "likes")
        remaining = await tracker.get_beliefs("s1")
        assert len(remaining) == 1
        assert remaining[0].value == "Paris"


# ── auto_inject tests ────────────────────────────────────────────────────


class TestAutoInject:
    @pytest.mark.asyncio
    async def test_auto_inject_default_true(self):
        config = make_config()
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.to_llm_call.return_value = MagicMock()
        mock_adapter.to_llm_response.return_value = MagicMock()

        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        tracker.set_session("session_auto_inject")

        # Add a belief to store
        b = Belief(
            subject="USER",
            predicate="likes",
            value="coffee",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("session_auto_inject", b)

        received_args = []
        received_kwargs = {}

        @tracker.wrap
        async def call_llm(*args, **kwargs):
            nonlocal received_args, received_kwargs
            received_args = args
            received_kwargs = kwargs
            return "dummy response"

        messages = [{"role": "user", "content": "hello"}]
        await call_llm(messages=messages)

        # Verify messages kwargs has injected belief context
        injected_messages = received_kwargs["messages"]
        assert len(injected_messages) == 2
        assert injected_messages[0]["role"] == "system"
        assert "coffee" in injected_messages[0]["content"]

    @pytest.mark.asyncio
    async def test_auto_inject_explicit_false(self):
        config = make_config()
        mock_adapter = MagicMock()
        mock_adapter.to_llm_call.return_value = MagicMock()
        mock_adapter.to_llm_response.return_value = MagicMock()

        tracker = BeliefTracker(config=config, adapter=mock_adapter)
        tracker.set_session("session_auto_inject_false")

        # Add a belief to store
        b = Belief(
            subject="USER",
            predicate="likes",
            value="coffee",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("session_auto_inject_false", b)

        received_kwargs = {}

        @tracker.wrap(auto_inject=False)
        async def call_llm(*args, **kwargs):
            nonlocal received_kwargs
            received_kwargs = kwargs
            return "dummy response"

        messages = [{"role": "user", "content": "hello"}]
        await call_llm(messages=messages)

        # Verify messages kwargs does not have injected belief context
        assert received_kwargs["messages"] == messages

    @pytest.mark.asyncio
    async def test_auto_inject_with_different_providers(self):
        config = make_config()

        # Test Anthropic style: injects into kwargs["system"]
        from beliefstate.adapters.anthropic import AnthropicAdapter

        anthropic_adapter = AnthropicAdapter()

        tracker = BeliefTracker(config=config, adapter=anthropic_adapter)
        tracker.set_session("session_anthropic")

        b = Belief(
            subject="USER",
            predicate="likes",
            value="tea",
            confidence=1.0,
            turn=1,
            source="user",
        )
        await tracker.store.add_belief("session_anthropic", b)

        received_kwargs = {}

        @tracker.wrap
        async def call_llm(*args, **kwargs):
            nonlocal received_kwargs
            received_kwargs = kwargs
            # Return a valid Anthropic-like dict response
            return {"content": [{"text": "response text"}]}

        await call_llm(messages=[{"role": "user", "content": "hi"}], system="Be polite")
        assert "tea" in received_kwargs["system"]
        assert "Be polite" in received_kwargs["system"]
