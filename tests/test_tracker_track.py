"""Tests for BeliefTracker.track_sync() and track_async() methods."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from beliefstate.tracker import BeliefTracker, GenericAdapter
from beliefstate.config import TrackerConfig
from beliefstate.call import LLMCall


@pytest.fixture
def mock_tracker():
    config = TrackerConfig(
        store_type="sqlite",
        store_kwargs={"db_path": ":memory:"},
        enable_background_tasks=False,
    )
    adapter = MagicMock(spec=GenericAdapter)
    tracker = BeliefTracker(config=config, adapter=adapter)
    tracker.set_session("test-session")
    return tracker


class TestGenericAdapter:
    def test_to_llm_call_from_kwargs(self):
        adapter = GenericAdapter()
        messages = [{"role": "user", "content": "Hi"}]
        call = adapter.to_llm_call(messages=messages)
        assert call.messages == messages

    def test_to_llm_call_from_args(self):
        adapter = GenericAdapter()
        messages = [{"role": "user", "content": "Hi"}]
        call = adapter.to_llm_call(messages)
        assert call.messages == messages

    def test_to_llm_response_with_content(self):
        adapter = GenericAdapter()
        mock_obj = MagicMock()
        mock_obj.content = "Hello"
        resp = adapter.to_llm_response(mock_obj)
        assert resp.text == "Hello"

    def test_to_llm_response_with_text(self):
        adapter = GenericAdapter()
        mock_obj = MagicMock(spec=["text"])
        mock_obj.text = "Hi"
        resp = adapter.to_llm_response(mock_obj)
        assert resp.text == "Hi"

    def test_to_llm_response_with_choices(self):
        adapter = GenericAdapter()
        mock_choice = MagicMock()
        mock_choice.message.content = "Choice text"
        mock_obj = MagicMock(spec=["choices"])
        mock_obj.choices = [mock_choice]
        resp = adapter.to_llm_response(mock_obj)
        assert resp.text == "Choice text"

    def test_to_llm_response_dict(self):
        adapter = GenericAdapter()
        resp = adapter.to_llm_response({"content": "From dict"})
        assert resp.text == "From dict"

    def test_to_llm_response_empty(self):
        adapter = GenericAdapter()
        resp = adapter.to_llm_response(None)
        assert resp.text == ""

    @pytest.mark.asyncio
    async def test_generate_raises(self):
        adapter = GenericAdapter()
        with pytest.raises(NotImplementedError, match="cannot generate"):
            await adapter.generate(LLMCall(messages=[]))

    @pytest.mark.asyncio
    async def test_get_embedding_raises(self):
        adapter = GenericAdapter()
        with pytest.raises(NotImplementedError, match="cannot generate embeddings"):
            await adapter.get_embedding("test")

    @pytest.mark.asyncio
    async def test_get_embeddings_raises(self):
        adapter = GenericAdapter()
        with pytest.raises(NotImplementedError, match="cannot generate embeddings"):
            await adapter.get_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_health_check(self):
        adapter = GenericAdapter()
        assert await adapter.health_check() is False

    def test_inject_context(self):
        adapter = GenericAdapter()
        result = adapter.inject_context("prompt", key="val")
        assert result == {"key": "val"}


class TestBeliefTrackerTrack:
    @pytest.mark.asyncio
    async def test_track_async_calls_background(self, mock_tracker):
        with patch.object(
            mock_tracker, "_track_background", new_callable=AsyncMock
        ) as mock_bg:
            call_dict = {
                "messages": [{"role": "user", "content": "My name is Alice"}],
                "kwargs": {},
                "system": None,
                "metadata": {},
            }
            response_dict = {
                "text": "Hello Alice! Nice to meet you.",
                "raw_response": None,
                "metadata": {},
            }
            await mock_tracker.track_async(call_dict, response_dict, "test-session", 1)
            mock_bg.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_async_no_adapter(self):
        config = TrackerConfig(
            store_type="sqlite",
            store_kwargs={"db_path": ":memory:"},
            enable_background_tasks=False,
        )
        tracker = BeliefTracker(config=config)
        tracker.set_session("test")

        call_dict = {
            "messages": [{"role": "user", "content": "test"}],
            "kwargs": {},
            "system": None,
            "metadata": {},
        }
        response_dict = {
            "text": "response",
            "raw_response": None,
            "metadata": {},
        }
        with patch.object(
            tracker, "_track_background", new_callable=AsyncMock
        ) as mock_bg:
            await tracker.track_async(call_dict, response_dict, "test", 1)
            mock_bg.assert_called_once()
