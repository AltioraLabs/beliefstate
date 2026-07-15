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

    block = MagicMock()
    block.type = "text"
    block.text = "cohere reply"
    chat_msg = MagicMock()
    chat_msg.content = [block]
    chat_resp = MagicMock()
    chat_resp.message = chat_msg
    mock_client.chat = AsyncMock(return_value=chat_resp)

    emb_resp = MagicMock()
    emb_resp.embeddings = [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embed = AsyncMock(return_value=emb_resp)

    adapter = CohereAdapter(
        client=mock_client,
        model="command-r-plus",
        embed_model="embed-english-v3.0",
    )
    assert isinstance(adapter, ProviderAdapter)

    # 1. generate
    call = LLMCall(messages=[{"role": "user", "content": "hello"}])
    resp = await adapter.generate(call)
    assert resp.text == "cohere reply"
    mock_client.chat.assert_called_once()
    _, kwargs = mock_client.chat.call_args
    assert kwargs["messages"][0]["role"] == "user"
    assert kwargs["model"] == "command-r-plus"

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
    """assistant -> chatbot mapping for Cohere's Command chat format."""
    from cohere import AsyncClient

    mock_client = MagicMock(spec=AsyncClient)
    block = MagicMock()
    block.type = "text"
    block.text = "ok"
    chat_msg = MagicMock()
    chat_msg.content = [block]
    chat_resp = MagicMock()
    chat_resp.message = chat_msg
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
    mapped = mock_client.chat.call_args[1]["messages"]
    roles = [m["role"] for m in mapped]
    assert "chatbot" in roles
    assert "assistant" not in roles
