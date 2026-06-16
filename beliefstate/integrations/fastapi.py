from typing import Any
import uuid


class BeliefMiddleware:
    def __init__(
        self, app: Any, tracker: Any, session_id_header: str = "x-session-id"
    ) -> None:
        self.app = app
        self.tracker = tracker
        self.session_id_header = session_id_header.lower()

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            header_bytes = self.session_id_header.encode("utf-8")
            session_id = headers.get(header_bytes, b"").decode("utf-8")

            if not session_id:
                session_id = str(uuid.uuid4())

            async with self.tracker.session(session_id):
                await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)
