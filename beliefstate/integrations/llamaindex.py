from typing import Any, List, Dict, Optional

try:
    from llama_index.core.callbacks import BaseCallbackHandler, CBEventType

    HAS_LLAMAINDEX = True
except ImportError:

    class BaseCallbackHandler:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    CBEventType: Any = None  # type: ignore[no-redef]
    HAS_LLAMAINDEX = False


class LlamaIndexBeliefTrackerCallback(BaseCallbackHandler):  # type: ignore[misc]
    def __init__(
        self,
        tracker: Any,
        event_starts_to_ignore: Optional[List[Any]] = None,
        event_ends_to_ignore: Optional[List[Any]] = None,
    ) -> None:
        self.tracker = tracker
        super().__init__(
            event_starts_to_ignore=event_starts_to_ignore or [],
            event_ends_to_ignore=event_ends_to_ignore or [],
        )

    def on_event_start(
        self,
        event_type: Any,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> str:
        return event_id

    def on_event_end(
        self,
        event_type: Any,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        if not HAS_LLAMAINDEX:
            raise ImportError(
                "llama-index-core is not installed. "
                "Install it via `pip install beliefstate[llamaindex]` to use LlamaIndex callbacks."
            )

        if event_type == CBEventType.LLM and payload and "response" in payload:
            response = payload["response"]
            if hasattr(response, "message") and hasattr(response.message, "content"):
                text = response.message.content
            elif hasattr(response, "text"):
                text = response.text
            else:
                text = str(response)

            if text:
                session_id = self.tracker._active_session_id.get()

                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.tracker.process_response(text, session_id=session_id),
                        loop,
                    )
                else:
                    asyncio.run(
                        self.tracker.process_response(text, session_id=session_id)
                    )
