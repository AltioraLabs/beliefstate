from beliefstate.integrations.asgi import BeliefTrackerASGIMiddleware
from beliefstate.integrations.langchain import BeliefTrackerLangchainCallback
from beliefstate.integrations.wsgi import BeliefTrackerWSGIMiddleware

try:
    from beliefstate.integrations.fastapi import (
        FastAPIBeliefTrackerMiddleware,
        get_session_id,
    )
except ImportError:
    FastAPIBeliefTrackerMiddleware = None  # type: ignore[assignment,misc]
    get_session_id = None  # type: ignore[assignment]

try:
    from beliefstate.integrations.flask import (
        FlaskBeliefTrackerMiddleware,
        register_flask_hooks,
    )
except ImportError:
    FlaskBeliefTrackerMiddleware = None  # type: ignore[assignment,misc]
    register_flask_hooks = None  # type: ignore[assignment]

try:
    from beliefstate.integrations.llamaindex import LlamaIndexBeliefTrackerCallback
except ImportError:
    LlamaIndexBeliefTrackerCallback = None  # type: ignore[assignment,misc]

try:
    from beliefstate.integrations.openai import (
        observe_run,
        process_openai_assistant_message,
    )
except ImportError:
    process_openai_assistant_message = None  # type: ignore[assignment]
    observe_run = None  # type: ignore[assignment]

__all__ = [
    "BeliefTrackerASGIMiddleware",
    "BeliefTrackerLangchainCallback",
    "BeliefTrackerWSGIMiddleware",
    "FastAPIBeliefTrackerMiddleware",
    "FlaskBeliefTrackerMiddleware",
    "LlamaIndexBeliefTrackerCallback",
    "get_session_id",
    "observe_run",
    "process_openai_assistant_message",
    "register_flask_hooks",
]
