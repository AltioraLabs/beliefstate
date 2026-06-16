import pytest
from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock
from beliefstate import BeliefTracker, TrackerConfig
from beliefstate.adapters.base import ProviderAdapter
from beliefstate.adapters.openai import OpenAIAdapter
from beliefstate.adapters.anthropic import AnthropicAdapter
from beliefstate.adapters.gemini import GeminiAdapter
from beliefstate.adapters.ollama import OllamaAdapter
from beliefstate.adapters.litellm import LiteLLMAdapter
from beliefstate.call import LLMCall, LLMResponse

def test_protocol_runtime_checks() -> None:
    # Verify the runtime checkable protocol works
    class MockValidProvider:
        def to_llm_call(self, *args, **kwargs) -> LLMCall:
            return LLMCall(messages=[])
            
        def to_llm_response(self, response: Any) -> LLMResponse:
            return LLMResponse(text="ok", raw_response=None)
            
        async def generate(self, call: LLMCall) -> LLMResponse:
            return LLMResponse(text="ok", raw_response=None)

        async def get_embedding(self, text: str) -> list[float]:
            return [0.1]

        async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
            return [[0.1]]

    p = MockValidProvider()
    assert isinstance(p, ProviderAdapter)
    
    with patch("beliefstate.adapters.litellm.HAS_LITELLM", True):
        litellm_adapter = LiteLLMAdapter()
        assert isinstance(litellm_adapter, ProviderAdapter)


@pytest.mark.asyncio
async def test_tracker_decorator_wrap() -> None:
    config = TrackerConfig(enable_background_tasks=False) # Run synchronously for testing
    
    # Mock adapter
    mock_adapter = MagicMock()
    mock_adapter.to_llm_call.return_value = LLMCall(messages=[{"role": "user", "content": "hello"}])
    mock_adapter.to_llm_response.return_value = LLMResponse(text="response text", raw_response=None)
    
    # Mock generation/embedding internally for the extractor
    mock_adapter.generate = AsyncMock(return_value=LLMResponse(
        text='[{"subject": "USER", "predicate": "said", "value": "hello", "confidence": 1.0}]',
        raw_response=None
    ))
    mock_adapter.get_embedding = AsyncMock(return_value=[0.1, 0.2])
    
    tracker = BeliefTracker(config=config, adapter=mock_adapter)

    @tracker.wrap
    async def dummy_agent(msg: str):
        return f"Response: {msg}"

    res = await dummy_agent("hello")
    assert res == "Response: hello"
    assert tracker.turn_counter == 1


@pytest.mark.asyncio
async def test_litellm_adapter():
    with patch("beliefstate.adapters.litellm.HAS_LITELLM", True), \
         patch("beliefstate.adapters.litellm.litellm") as mock_litellm:
         
        # Mock completion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="litellm completion"))]
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        
        # Mock embedding
        mock_emb_data = [
            {"embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]}
        ]
        mock_emb_resp = MagicMock()
        mock_emb_resp.data = mock_emb_data
        mock_litellm.aembedding = AsyncMock(return_value=mock_emb_resp)
        
        adapter = LiteLLMAdapter(model="gpt-4o", embed_model="text-embedding-3")
        
        # 1. Test generate
        call = LLMCall(messages=[{"role": "user", "content": "hello"}])
        resp = await adapter.generate(call)
        assert resp.text == "litellm completion"
        mock_litellm.acompletion.assert_called_once()
        
        # 2. Test get_embeddings batching
        embs = await adapter.get_embeddings(["hello", "world"])
        assert embs == [[0.1, 0.2], [0.3, 0.4]]
        mock_litellm.aembedding.assert_called_once_with(
            model="text-embedding-3",
            input=["hello", "world"]
        )
