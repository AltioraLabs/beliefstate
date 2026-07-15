import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast

from beliefstate.adapters.base import ProviderAdapter
from beliefstate.adapters.common import (
    RetryConfig,
    retry_with_backoff,
    with_timeout,
    validate_api_key,
    StructuredLogger,
    PermanentError,
)
from beliefstate.call import LLMCall, LLMResponse

logger = logging.getLogger(__name__)

try:
    from cohere import AsyncClient
except ImportError:
    AsyncClient = Any  # type: ignore[misc, assignment]


_ROLE_MAP = {"assistant": "chatbot"}


class CohereAdapter(ProviderAdapter):
    """Adapter for Cohere Command models (chat + embeddings)."""

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = "command-r-plus",
        embed_model: str = "embed-english-v3.0",
        embed_kwargs: Optional[Dict[str, Any]] = None,
        input_type: str = "search_document",
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
        health_check_timeout: float = 5.0,
    ):
        self.model = model
        self.embed_model = embed_model
        self.embed_kwargs = embed_kwargs or {}
        self.input_type = input_type
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.health_check_timeout = health_check_timeout
        self.log = StructuredLogger(__name__, "Cohere")

        if client:
            self.client = client
        else:
            try:
                from cohere import AsyncClient

                api_key = os.getenv("COHERE_API_KEY")
                validate_api_key(api_key, "Cohere")
                self.client = AsyncClient(api_key=api_key)
                self.log.info("Initialized", model=model, embed_model=embed_model)
            except ImportError:
                self.log.error("Cohere SDK not installed")
                self.client = None
            except ValueError as e:
                self.log.error(f"Configuration error: {e}")
                self.client = None

    def to_llm_call(self, *args: Any, **kwargs: Any) -> LLMCall:
        messages = kwargs.get("messages", [])
        if not messages and len(args) > 0 and isinstance(args[0], list):
            messages = args[0]

        system_prompt = None
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "system":
                system_prompt = m.get("content")
            elif hasattr(m, "role") and m.role == "system":
                system_prompt = m.content

        return LLMCall(
            messages=messages,
            kwargs=kwargs,
            system=system_prompt,
            metadata={"model": kwargs.get("model", self.model)},
        )

    def _map_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        out = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role")
                content = m.get("content")
            else:
                role = getattr(m, "role", None)
                content = getattr(m, "content", None)
            if role == "assistant":
                role = "chatbot"
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
            out.append({"role": role, "content": content})
        return out

    def to_llm_response(self, response: Any) -> LLMResponse:
        if isinstance(response, dict):
            text = response.get("text") or response.get("message", {}).get(
                "content", ""
            )
        else:
            blocks = response.message.content
            text = "".join(
                getattr(b, "text", "")
                for b in blocks
                if getattr(b, "type", None) == "text"
            )
        return LLMResponse(text=text, raw_response=response)

    def inject_context(
        self,
        context_prompt: str,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        messages = kwargs.get("messages", [])
        in_kwargs = "messages" in kwargs
        arg_idx = -1

        if not messages and len(args) > 0 and isinstance(args[0], list):
            messages = args[0]
            in_kwargs = False
            arg_idx = 0

        if not messages:
            in_kwargs = True
            messages = []

        new_messages = [m.copy() if isinstance(m, dict) else m for m in messages]
        system_idx = -1
        for idx, m in enumerate(new_messages):
            if isinstance(m, dict) and m.get("role") == "system":
                system_idx = idx
                break
            elif hasattr(m, "role") and m.role == "system":
                system_idx = idx
                break

        if system_idx != -1:
            m = new_messages[system_idx]
            if isinstance(m, dict):
                orig = m.get("content", "")
                m["content"] = f"{orig}\n\n{context_prompt}" if orig else context_prompt
            else:
                orig = getattr(m, "content", "")
                m.content = f"{orig}\n\n{context_prompt}" if orig else context_prompt
        else:
            new_messages.insert(0, {"role": "system", "content": context_prompt})

        if in_kwargs:
            new_kwargs = kwargs.copy()
            new_kwargs["messages"] = new_messages
            return args, new_kwargs
        elif arg_idx != -1:
            new_args = list(args)
            new_args[arg_idx] = new_messages
            return tuple(new_args), kwargs

        return args, kwargs

    async def _generate_with_backoff(
        self, call: LLMCall, response_format: Optional[Any] = None
    ) -> LLMResponse:
        kwargs = call.kwargs.copy()
        kwargs["messages"] = self._map_messages(call.messages)
        if "model" not in kwargs:
            kwargs["model"] = self.model
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0.0

        response = await self.client.chat(**kwargs)
        return self.to_llm_response(response)

    async def generate(
        self, call: LLMCall, response_format: Optional[Any] = None
    ) -> LLMResponse:
        if not self.client:
            raise RuntimeError(
                "Cohere client not installed or configured. Install with `pip install beliefstate[cohere]`."
            )

        try:

            async def api_call() -> LLMResponse:
                return cast(
                    LLMResponse,
                    await retry_with_backoff(
                        self._generate_with_backoff,
                        call,
                        response_format,
                        config=self.retry_config,
                    ),
                )

            result = await with_timeout(
                api_call(),
                self.timeout * (self.retry_config.max_retries + 1),
                "Cohere generate",
            )
            return cast(LLMResponse, result)
        except PermanentError:
            self.log.error("Generate failed with permanent error", model=self.model)
            raise
        except asyncio.TimeoutError:
            self.log.error("Generate timed out", timeout=self.timeout, model=self.model)
            raise
        except Exception as e:
            self.log.error(
                "Generate failed unexpectedly", error=str(e), model=self.model
            )
            raise

    async def _get_embeddings_with_backoff(self, texts: List[str]) -> List[List[float]]:
        kwargs: Dict[str, Any] = {
            "texts": texts,
            "model": self.embed_model,
            "input_type": self.input_type,
        }
        kwargs.update(self.embed_kwargs)
        response = await self.client.embed(**kwargs)
        return cast(List[List[float]], response.embeddings)

    async def get_embedding(self, text: str) -> List[float]:
        res = await self.get_embeddings([text])
        return res[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not self.client:
            raise RuntimeError(
                "Cohere client not installed or configured. Install with `pip install beliefstate[cohere]`."
            )
        if not texts:
            return []

        try:

            async def api_call() -> List[List[float]]:
                return cast(
                    List[List[float]],
                    await retry_with_backoff(
                        self._get_embeddings_with_backoff,
                        texts,
                        config=self.retry_config,
                    ),
                )

            result = await with_timeout(
                api_call(),
                self.timeout * (self.retry_config.max_retries + 1),
                f"Cohere embeddings ({len(texts)} texts)",
            )
            return cast(List[List[float]], result)
        except PermanentError:
            self.log.error(
                "Get embeddings failed with permanent error",
                model=self.embed_model,
                count=len(texts),
            )
            raise
        except asyncio.TimeoutError:
            self.log.error(
                "Get embeddings timed out",
                timeout=self.timeout,
                model=self.embed_model,
                count=len(texts),
            )
            raise
        except Exception as e:
            self.log.error(
                "Get embeddings failed unexpectedly",
                error=str(e),
                model=self.embed_model,
                count=len(texts),
            )
            raise

    async def health_check(self) -> bool:
        if not self.client:
            self.log.warning("Health check failed: client not configured")
            return False
        try:
            await with_timeout(
                self.client.chat(message="ok", model=self.model),
                timeout_seconds=self.health_check_timeout,
                operation_name="Cohere health check",
            )
            self.log.debug("Health check passed")
            return True
        except Exception as e:
            self.log.warning(f"Health check failed: {e}")
            return False
