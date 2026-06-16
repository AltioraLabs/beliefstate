from typing import Any
import uuid


class FlaskBeliefMiddleware:
    def __init__(
        self, app: Any, tracker: Any, session_id_header: str = "x-session-id"
    ) -> None:
        self.app = app
        self.tracker = tracker
        self.session_id_header = session_id_header

    def __call__(self, environ: Any, start_response: Any) -> Any:
        header_key = "HTTP_" + self.session_id_header.upper().replace("-", "_")
        session_id = environ.get(header_key, "")
        if not session_id:
            session_id = str(uuid.uuid4())

        token = self.tracker._active_session_id.set(session_id)
        try:
            return self.app(environ, start_response)
        finally:
            self.tracker._active_session_id.reset(token)
