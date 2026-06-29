"""Tests for beliefstate.integrations.wsgi (WSGI middleware)."""

from unittest.mock import MagicMock

from beliefstate.integrations.wsgi import BeliefTrackerWSGIMiddleware
from beliefstate.tracker import session_context


class MockWSGIApp:
    def __call__(self, environ, start_response):
        self.last_session = session_context.get()
        start_response("200 OK", [])
        return [b"ok"]


class TestWSGIMiddleware:
    def test_session_id_from_header(self):
        app = MockWSGIApp()
        middleware = BeliefTrackerWSGIMiddleware(app)
        environ = {"HTTP_X_SESSION_ID": "user-42"}
        start_response = MagicMock()

        middleware(environ, start_response)
        assert app.last_session == "user-42"
        assert session_context.get() == "default"

    def test_no_session_header(self):
        app = MockWSGIApp()
        middleware = BeliefTrackerWSGIMiddleware(app)
        environ = {}
        start_response = MagicMock()

        middleware(environ, start_response)
        assert app.last_session == "default"

    def test_invalid_session_header(self):
        app = MockWSGIApp()
        middleware = BeliefTrackerWSGIMiddleware(app)
        environ = {"HTTP_X_SESSION_ID": ""}
        start_response = MagicMock()

        middleware(environ, start_response)
        assert app.last_session == "default"

    def test_custom_header_name(self):
        app = MockWSGIApp()
        middleware = BeliefTrackerWSGIMiddleware(app, header_name="X-Custom")
        environ = {"HTTP_X_CUSTOM": "custom-id"}
        start_response = MagicMock()

        middleware(environ, start_response)
        assert app.last_session == "custom-id"

    def test_non_string_header_name(self):
        app = MockWSGIApp()
        middleware = BeliefTrackerWSGIMiddleware(app, header_name=123)
        environ = {"HTTP_123": "value"}
        start_response = MagicMock()

        middleware(environ, start_response)
        assert app.last_session == "value"
