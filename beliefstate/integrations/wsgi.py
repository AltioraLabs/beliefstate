import logging
from typing import Any
from beliefstate.tracker import session_context
from beliefstate.integrations.common import IntegrationLogger, validate_session_id

logger = logging.getLogger(__name__)


class BeliefTrackerWSGIMiddleware:
    """
    WSGI Middleware (works with Flask, Django, etc.)
    to automatically extract a session ID from a request header and set it in the tracker's context.
    
    Features:
    - Automatic session ID extraction from configurable header
    - Request-scoped context propagation
    - Structured logging
    - Error handling with graceful degradation
    
    Usage:
        app = Flask(__name__)
        app.wsgi_app = BeliefTrackerWSGIMiddleware(app.wsgi_app)
    """

    def __init__(self, app: Any, header_name: str = "X-Session-ID") -> None:
        self.app = app
        self.header_name = header_name if isinstance(header_name, str) else header_name.decode("latin1")
        self.log = IntegrationLogger(__name__, "WSGI")

    def __call__(self, environ: Any, start_response: Any) -> Any:
        # WSGI standardizes headers to HTTP_UPPER_CASE_WITH_UNDERSCORES
        wsgi_header = "HTTP_" + self.header_name.upper().replace("-", "_")
        session_id = environ.get(wsgi_header)

        if session_id:
            try:
                # Validate session ID
                session_id = validate_session_id(session_id)
                token = session_context.set(session_id)
                self.log.debug("Session context set", session_id=session_id)
                try:
                    return self.app(environ, start_response)
                finally:
                    session_context.reset(token)
                    self.log.debug("Session context reset", session_id=session_id)
            except ValueError as e:
                self.log.warning("Invalid session ID in header", error=str(e))
                return self.app(environ, start_response)
            except Exception as e:
                self.log.error("Error in middleware", error=str(e))
                raise
        else:
            self.log.debug("No session ID found in request")
            return self.app(environ, start_response)
