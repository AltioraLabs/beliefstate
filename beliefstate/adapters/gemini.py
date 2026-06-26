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
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


class GeminiAdapter(ProviderAdapter):
    """Adapter for Google GenAI API (google-genai) with production-ready robustness.

    Features:
    - Automatic retry with exponential backoff for transient errors
    - Configurable request timeouts
    - Structured logging for debugging
    - Health check mechanism
    - Safety settings handling
    - API key validation at initialization

    NOTE: Uses google-genai library (experimental). For production, consider
    using the stable google-cloud-aiplatform library.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = "gemini-2.0-flash",
        embed_model: str = "text-embedding-004",
        embed_kwargs: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        retry_config: Optional[RetryConfig] = None,
        health_check_timeout: float = 5.0,
        safety_settings: Optional[List[Dict[str, str]]] = None,
    ):
        self.model = model
        self.embed_model = embed_model
        self.embed_kwargs = embed_kwargs or {}
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.health_check_timeout = health_check_timeout
        self.safety_settings = safety_settings or []
        self.log = StructuredLogger(__name__, "Gemini")

        if client:
            self.client = client
        else:
            try:
                from google import genai

                api_key = os.getenv("GOOGLE_API_KEY")
                validate_api_key(api_key, "Google Gemini")
                self.client = genai.Client(api_key=api_key)
                self.log.info(
                    "Initialized",
                    model=model,
                    embed_model=embed_model,
                    note="Using experimental google-genai library",
                )
            except ImportError:
                self.log.error("google-genai SDK not installed")
                self.client = None
            except ValueError as e:
                self.log.error(f"Configuration error: {e}")
                self.client = None

    def to_llm_call(self, *args: Any, **kwargs: Any) -> LLMCall:
        contents = kwargs.get("contents", [])
        if not contents and len(args) > 0:
            contents = args[0]

        messages = []
        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
        elif isinstance(contents, list):
            for m in contents:
                if isinstance(m, dict):
                    role = "user" if m.get("role") == "user" else "assistant"
                    messages.append(
                        {
                            "role": role,
                            "content": str(m.get("parts", m.get("content", ""))),
                        }
                    )
                elif hasattr(m, "role"):
                    role = "user" if m.role == "user" else "assistant"
                    text = m.parts[0].text if getattr(m, "parts", None) else ""
                    messages.append({"role": role, "content": text})
                elif isinstance(m, str):
                    messages.append({"role": "user", "content": m})

        config = kwargs.get("config", {})
        system_instruction = None
        if hasattr(config, "system_instruction"):
            system_instruction = str(config.system_instruction)
        elif isinstance(config, dict) and "system_instruction" in config:
            system_instruction = str(config["system_instruction"])

        return LLMCall(
            messages=messages,
            kwargs=kwargs,
            system=system_instruction,
            metadata={"model": kwargs.get("model", self.model)},
        )

    def to_llm_response(self, response: Any) -> LLMResponse:
        if isinstance(response, dict):
            text = response.get("text", "")
        else:
            text = getattr(response, "text", "")

        return LLMResponse(text=text, raw_response=response)

    def inject_context(
        self,
        context_prompt: str,
        *args: Any,
        **kwargs: Any,
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        """Inject context prompt into Gemini config.system_instruction."""
        new_kwargs = kwargs.copy()
        config = new_kwargs.get("config")

        if config is None:
            try:
                from google.genai import types

                config = types.GenerateContentConfig(system_instruction=context_prompt)
                new_kwargs["config"] = config
            except ImportError:
                new_kwargs["config"] = {"system_instruction": context_prompt}
        else:
            if hasattr(config, "system_instruction"):
                try:
                    orig_system = getattr(config, "system_instruction", "")
                    new_system = (
                        f"{orig_system}\n\n{context_prompt}"
                        if orig_system
                        else context_prompt
                    )
                    if hasattr(config, "model_copy"):
                        config = config.model_copy(
                            update={"system_instruction": new_system}
                        )
                    else:
                        import copy

                        config = copy.copy(config)
                        config.system_instruction = new_system
                    new_kwargs["config"] = config
                except Exception:
                    orig_system = getattr(config, "system_instruction", "")
                    config.system_instruction = (
                        f"{orig_system}\n\n{context_prompt}"
                        if orig_system
                        else context_prompt
                    )
            elif isinstance(config, dict):
                config = config.copy()
                orig_system = config.get("system_instruction", "")
                config["system_instruction"] = (
                    f"{orig_system}\n\n{context_prompt}"
                    if orig_system
                    else context_prompt
                )
                new_kwargs["config"] = config

        return args, new_kwargs

    async def _generate_with_backoff(
        self, call: LLMCall, response_format: Optional[Any] = None
    ) -> LLMResponse:
        """Internal method that actually calls the API."""
        from google.genai import types

        # Combine messages into a simple string for internal tracker calls (like json extraction)
        formatted_contents = ""
        for m in call.messages:
            formatted_contents += f"{m.get('role', 'user')}: {m.get('content', '')}\n"

        config_args: Dict[str, Any] = {}
        if call.system:
            config_args["system_instruction"] = call.system

        if response_format:
            config_args["response_mime_type"] = "application/json"
            if isinstance(response_format, dict):
                config_args["response_schema"] = response_format
            else:
                try:
                    config_args["response_schema"] = response_format.model_json_schema()
                except Exception:
                    config_args["response_schema"] = response_format

        # Add safety settings
        if self.safety_settings:
            config_args["safety_settings"] = self.safety_settings

        generate_config = (
            types.GenerateContentConfig(**config_args) if config_args else None
        )

        response = await self.client.aio.models.generate_content(
            model=self.model, contents=formatted_contents, config=generate_config
        )
        return self.to_llm_response(response)

    async def generate(
        self, call: LLMCall, response_format: Optional[Any] = None
    ) -> LLMResponse:
        """Generate a response with automatic retry and timeout handling.

        Args:
            call: LLMCall with messages and parameters
            response_format: Optional response schema (for structured output)

        Returns:
            LLMResponse with generated text

        Raises:
            RuntimeError: If Gemini client is not configured
            asyncio.TimeoutError: If request exceeds timeout
            PermanentError: If error is not transient
        """
        if not self.client:
            raise RuntimeError(
                "Google GenAI client not installed. Install with `pip install google-genai`."
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
                "Gemini generate",
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
        """Internal method that actually calls the embeddings API."""
        kwargs = {"model": self.embed_model, "contents": texts}
        if self.embed_kwargs:
            kwargs.update(self.embed_kwargs)

        response = await self.client.aio.models.embed_content(**kwargs)
        return [list(emb.values) for emb in response.embeddings]

    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        res = await self.get_embeddings([text])
        return res[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for multiple texts with automatic retry and timeout.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If Gemini client is not configured
            asyncio.TimeoutError: If request exceeds timeout
            PermanentError: If error is not transient
        """
        if not self.client:
            raise RuntimeError(
                "Google GenAI client not installed. Install with `pip install google-genai`."
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
                f"Gemini embeddings ({len(texts)} texts)",
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
        """Check if Gemini API is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """
        if not self.client:
            self.log.warning("Health check failed: client not configured")
            return False

        try:
            # Try to generate minimal content with a short timeout
            await with_timeout(
                self.client.aio.models.generate_content(
                    model=self.model,
                    contents="ok",
                ),
                timeout_seconds=self.health_check_timeout,
                operation_name="Gemini health check",
            )
            self.log.debug("Health check passed")
            return True
        except Exception as e:
            self.log.warning(f"Health check failed: {e}")
            return False
