import asyncio
from typing import Any, Optional


async def process_openai_assistant_message(
    tracker: Any, message_content: str, session_id: Optional[str] = None
) -> None:
    """Processes a raw assistant text response and updates the belief tracker."""
    await tracker.process_response(message_content, session_id=session_id)


async def observe_run(
    tracker: Any,
    client: Any,
    thread_id: str,
    run_id: str,
    poll_interval: float = 1.0,
    session_id: Optional[str] = None,
) -> Any:
    """
    Polls an OpenAI Assistant Run until complete.
    Once completed, retrieves the latest assistant message, updates belief store, and returns the Run status.
    """
    while True:
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread_id, run_id=run_id
        )
        if run.status in ["completed", "failed", "cancelled", "expired"]:
            break
        await asyncio.sleep(poll_interval)

    if run.status == "completed":
        # Fetch messages in thread
        messages = await client.beta.threads.messages.list(thread_id=thread_id)
        # Filter for assistant messages (messages list is typically reverse-chronological)
        assistant_messages = [m for m in messages.data if m.role == "assistant"]
        if assistant_messages:
            latest_msg = assistant_messages[0]
            # Accumulate text content
            text_blocks = []
            for block in latest_msg.content:
                # Content block can be text or image_file
                if hasattr(block, "text") and hasattr(block.text, "value"):
                    text_blocks.append(block.text.value)
            full_text = "\n".join(text_blocks)
            if full_text:
                await process_openai_assistant_message(
                    tracker, full_text, session_id=session_id
                )

    return run
