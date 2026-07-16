import pytest
from unittest.mock import MagicMock, AsyncMock

from beliefstate.adapters.base import ProviderAdapter
from beliefstate.adapters.cohere import CohereAdapter
from beliefstate.call import LLMCall


@pytest.mark.asyncio
async def test_cohere_adapter_generate_and_embed():
    from cohere import AsyncClient

    # Mock the native SDK client; we inject it so no network calls happen.
    mock_client = MagicMock(spec=AsyncClient)

    # v7 NonStreamedChatResponse — has .text directly
    chat_resp = MagicMock()
    chat_resp.text = "cohere reply"
    mock_client.chat = AsyncMock(return_value=chat_resp)

    emb_resp = MagicMock()
    emb_resp.embeddings = [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embed = AsyncMock(return_value=emb_resp)

    adapter = CohereAdapter(
        client=mock_client,
        model="command-r-plus-08-2024",
        embed_model="embed-english-v3.0",
    )
    assert isinstance(adapter, ProviderAdapter)

    # 1. generate
    call = LLMCall(messages=[{"role": "user", "content": "hello"}])
    resp = await adapter.generate(call)
    assert resp.text == "cohere reply"
    mock_client.chat.assert_called_once()
    _, kwargs = mock_client.chat.call_args
    assert kwargs["message"] == "hello"
    assert kwargs["model"] == "command-r-plus-08-2024"

    # 2. embeddings
    embs = await adapter.get_embeddings(["hello", "world"])
    assert embs == [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embed.assert_called_once_with(
        texts=["hello", "world"],
        model="embed-english-v3.0",
        input_type="search_document",
    )


@pytest.mark.asyncio
async def test_cohere_adapter_role_mapping():
    """assistant -> chatbot mapping for Cohere's Command chat format.

    Verifies that chat_history entries with role='assistant' are converted
    to 'chatbot', and the last user message is passed as the 'message' param.
    """
    from cohere import AsyncClient

    mock_client = MagicMock(spec=AsyncClient)
    chat_resp = MagicMock()
    chat_resp.text = "ok"
    mock_client.chat = AsyncMock(return_value=chat_resp)

    adapter = CohereAdapter(client=mock_client)
    call = LLMCall(
        messages=[
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    )
    await adapter.generate(call)
    kwargs = mock_client.chat.call_args[1]
    chat_history = kwargs["chat_history"]
    roles = [m["role"] for m in chat_history]
    assert "chatbot" in roles
    assert "assistant" not in roles
    assert kwargs["message"] == "hi"  # last user message
    assert kwargs["preamble"] == "be brief"  # system prompt → preamble
