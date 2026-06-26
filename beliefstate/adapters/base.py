from typing import Any, List, Protocol, runtime_checkable, Optional
from beliefstate.call import LLMCall, LLMResponse


@runtime_checkable
class ProviderAdapter(Protocol):
    """Protocol for translating between native SDK formats and our universal models.

    All adapters should implement:
    - to_llm_call: Convert native args to universal LLMCall
    - to_llm_response: Convert native response to universal LLMResponse
    - generate: Execute generation with retry and timeout handling
    - get_embedding/get_embeddings: Generate embeddings
    - health_check: Verify provider is accessible
    """

    def to_llm_call(self, *args: Any, **kwargs: Any) -> LLMCall:
        """Convert native args/kwargs into a universal LLMCall."""
        ...

    def to_llm_response(self, response: Any) -> LLMResponse:
        """Convert a native SDK response object into a universal LLMResponse."""
        ...

    async def generate(
        self, call: LLMCall, response_format: Optional[Any] = None
    ) -> LLMResponse:
        """Execute a generation request using this provider natively (used for internal tracker logic)."""
        ...

    async def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for the text using this provider natively."""
        ...

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using this provider natively."""
        ...

    def inject_context(self, context_prompt: str, *args: Any, **kwargs: Any) -> Any:
        """Inject context into the LLM call arguments."""
        ...

    async def health_check(self) -> bool:
        """Check if the provider is accessible and responding correctly.

        Returns:
            True if provider is healthy, False otherwise.
        """
        ...
