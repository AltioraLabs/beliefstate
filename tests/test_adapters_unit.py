"""Unit tests for adapter classes (mock-based, no network calls)."""

import pytest
from unittest.mock import MagicMock

from beliefstate.call import LLMCall, LLMResponse


# ---------------------------------------------------------------------------
# OpenAI Adapter
# ---------------------------------------------------------------------------
class TestOpenAIAdapter:
    def test_to_llm_call_from_kwargs(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
        call = adapter.to_llm_call(messages=messages, model="gpt-4o")
        assert isinstance(call, LLMCall)
        assert call.messages == messages
        assert call.system == "You are helpful."
        assert call.metadata["model"] == "gpt-4o"

    def test_to_llm_call_from_args(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        messages = [{"role": "user", "content": "Hi"}]
        call = adapter.to_llm_call(messages)
        assert call.messages == messages

    def test_to_llm_response_dict(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        response_dict = {"choices": [{"message": {"content": "Hello!"}}]}
        resp = adapter.to_llm_response(response_dict)
        assert isinstance(resp, LLMResponse)
        assert resp.text == "Hello!"

    def test_to_llm_response_object(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi there"
        resp = adapter.to_llm_response(mock_response)
        assert resp.text == "Hi there"

    def test_inject_context_no_system(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        messages = [{"role": "user", "content": "Hi"}]
        _, new_kwargs = adapter.inject_context("Be helpful", messages=messages)
        assert new_kwargs["messages"][0]["role"] == "system"
        assert new_kwargs["messages"][0]["content"] == "Be helpful"

    def test_inject_context_with_system(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        messages = [
            {"role": "system", "content": "Original"},
            {"role": "user", "content": "Hi"},
        ]
        _, new_kwargs = adapter.inject_context("Additional context", messages=messages)
        assert new_kwargs["messages"][0]["content"] == "Original\n\nAdditional context"

    @pytest.mark.asyncio
    async def test_generate_no_client_raises(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        adapter.model = "gpt-4o"
        adapter.timeout = 30
        adapter.retry_config = MagicMock()
        adapter.retry_config.max_retries = 0

        call = LLMCall(messages=[{"role": "user", "content": "Hi"}])
        with pytest.raises(RuntimeError, match="not installed or configured"):
            await adapter.generate(call)

    @pytest.mark.asyncio
    async def test_get_embeddings_no_client_raises(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        adapter.client = None
        adapter.log = MagicMock()

        with pytest.raises(RuntimeError, match="not installed or configured"):
            await adapter.get_embeddings(["hello"])

    @pytest.mark.asyncio
    async def test_get_embeddings_empty_list(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter(client=MagicMock())
        result = await adapter.get_embeddings([])
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        from beliefstate.adapters.openai import OpenAIAdapter

        adapter = OpenAIAdapter.__new__(OpenAIAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        assert await adapter.health_check() is False


# ---------------------------------------------------------------------------
# Anthropic Adapter
# ---------------------------------------------------------------------------
class TestAnthropicAdapter:
    def test_to_llm_call(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        messages = [{"role": "user", "content": "Hi"}]
        call = adapter.to_llm_call(
            messages=messages, system="Be helpful", model="claude-3"
        )
        assert call.messages == messages
        assert call.system == "Be helpful"
        assert call.metadata["model"] == "claude-3"

    def test_to_llm_response_dict(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        response_dict = {"content": [{"text": "Hello from Claude"}]}
        resp = adapter.to_llm_response(response_dict)
        assert resp.text == "Hello from Claude"

    def test_to_llm_response_object(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Claude says hi")]
        resp = adapter.to_llm_response(mock_response)
        assert resp.text == "Claude says hi"

    def test_inject_context(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        _, new_kwargs = adapter.inject_context("Extra context", system="Base")
        assert new_kwargs["system"] == "Base\n\nExtra context"

    def test_inject_context_no_existing(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        _, new_kwargs = adapter.inject_context("Context only")
        assert new_kwargs["system"] == "Context only"

    @pytest.mark.asyncio
    async def test_get_embedding_raises(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        with pytest.raises(NotImplementedError, match="does not natively"):
            await adapter.get_embedding("test")

    @pytest.mark.asyncio
    async def test_get_embeddings_raises(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter(client=MagicMock())
        with pytest.raises(NotImplementedError, match="does not natively"):
            await adapter.get_embeddings(["test"])

    @pytest.mark.asyncio
    async def test_generate_no_client_raises(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        adapter.model = "claude-3"
        adapter.timeout = 30
        adapter.retry_config = MagicMock()
        adapter.retry_config.max_retries = 0

        call = LLMCall(messages=[{"role": "user", "content": "Hi"}])
        with pytest.raises(RuntimeError, match="not installed or configured"):
            await adapter.generate(call)

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        from beliefstate.adapters.anthropic import AnthropicAdapter

        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        assert await adapter.health_check() is False


# ---------------------------------------------------------------------------
# Gemini Adapter
# ---------------------------------------------------------------------------
class TestGeminiAdapter:
    def test_to_llm_call_from_string(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        call = adapter.to_llm_call("Hello Gemini")
        assert len(call.messages) == 1
        assert call.messages[0]["role"] == "user"
        assert call.messages[0]["content"] == "Hello Gemini"

    def test_to_llm_call_from_list(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        contents = [
            {"role": "user", "parts": "Hi"},
            {"role": "model", "parts": "Hello"},
        ]
        call = adapter.to_llm_call(contents)
        assert len(call.messages) == 2
        assert call.messages[0]["content"] == "Hi"
        assert call.messages[1]["content"] == "Hello"

    def test_to_llm_response_dict(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        resp = adapter.to_llm_response({"text": "Gemini response"})
        assert resp.text == "Gemini response"

    def test_to_llm_response_object(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        mock_response = MagicMock()
        mock_response.text = "Gemini says"
        resp = adapter.to_llm_response(mock_response)
        assert resp.text == "Gemini says"

    def test_inject_context_no_config(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        _, new_kwargs = adapter.inject_context("System prompt")
        assert new_kwargs["config"] is not None

    def test_inject_context_dict_config(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        _, new_kwargs = adapter.inject_context(
            "Extra", config={"system_instruction": "Base"}
        )
        assert new_kwargs["config"]["system_instruction"] == "Base\n\nExtra"

    @pytest.mark.asyncio
    async def test_generate_no_client_raises(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        adapter.model = "gemini-2.0-flash"
        adapter.timeout = 30
        adapter.retry_config = MagicMock()
        adapter.retry_config.max_retries = 0

        call = LLMCall(messages=[{"role": "user", "content": "Hi"}])
        with pytest.raises(RuntimeError, match="not installed"):
            await adapter.generate(call)

    @pytest.mark.asyncio
    async def test_get_embeddings_no_client_raises(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter.client = None
        adapter.log = MagicMock()

        with pytest.raises(RuntimeError, match="not installed"):
            await adapter.get_embeddings(["hello"])

    @pytest.mark.asyncio
    async def test_get_embeddings_empty(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter(client=MagicMock())
        result = await adapter.get_embeddings([])
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        from beliefstate.adapters.gemini import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        assert await adapter.health_check() is False


# ---------------------------------------------------------------------------
# Ollama Adapter
# ---------------------------------------------------------------------------
class TestOllamaAdapter:
    def test_to_llm_call(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hi"},
        ]
        call = adapter.to_llm_call(messages=messages, model="llama3.2")
        assert call.messages == messages
        assert call.system == "Be helpful"
        assert call.metadata["model"] == "llama3.2"

    def test_to_llm_response_dict(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        response_dict = {"message": {"content": "Ollama says hi"}}
        resp = adapter.to_llm_response(response_dict)
        assert resp.text == "Ollama says hi"

    def test_to_llm_response_object(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        mock_response = MagicMock()
        mock_response.message.content = "Ollama response"
        resp = adapter.to_llm_response(mock_response)
        assert resp.text == "Ollama response"

    def test_inject_context_in_kwargs(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        messages = [{"role": "user", "content": "Hi"}]
        _, new_kwargs = adapter.inject_context("Context", messages=messages)
        assert new_kwargs["messages"][0]["role"] == "system"
        assert new_kwargs["messages"][0]["content"] == "Context"

    def test_inject_context_appends_to_system(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        messages = [
            {"role": "system", "content": "Base"},
            {"role": "user", "content": "Hi"},
        ]
        _, new_kwargs = adapter.inject_context("Extra", messages=messages)
        assert new_kwargs["messages"][0]["content"] == "Base\n\nExtra"

    def test_dereference_schema(self):
        from beliefstate.adapters.ollama import _dereference_schema

        schema = {
            "type": "object",
            "$defs": {"Foo": {"type": "string"}},
            "properties": {"bar": {"$ref": "#/$defs/Foo"}},
        }
        result = _dereference_schema(schema)
        assert "$defs" not in result
        assert result["properties"]["bar"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_generate_no_client_raises(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter.__new__(OllamaAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        adapter.model = "llama3.2"
        adapter.host = "http://localhost"
        adapter.port = 11434
        adapter.timeout = 30
        adapter.retry_config = MagicMock()
        adapter.retry_config.max_retries = 0

        call = LLMCall(messages=[{"role": "user", "content": "Hi"}])
        with pytest.raises(RuntimeError, match="not installed"):
            await adapter.generate(call)

    @pytest.mark.asyncio
    async def test_get_embedding_no_client_raises(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter.__new__(OllamaAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        adapter.model = "llama3.2"
        adapter.host = "http://localhost"
        adapter.port = 11434
        adapter.timeout = 30
        adapter.retry_config = MagicMock()
        adapter.retry_config.max_retries = 0

        with pytest.raises(RuntimeError, match="not installed"):
            await adapter.get_embedding("test")

    @pytest.mark.asyncio
    async def test_get_embeddings_empty(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter(client=MagicMock())
        result = await adapter.get_embeddings([])
        assert result == []

    @pytest.mark.asyncio
    async def test_health_check_no_client(self):
        from beliefstate.adapters.ollama import OllamaAdapter

        adapter = OllamaAdapter.__new__(OllamaAdapter)
        adapter.client = None
        adapter.log = MagicMock()
        assert await adapter.health_check() is False
