import threading
import socket
import time
import logging
from typing import Optional
import uvicorn

logger = logging.getLogger(__name__)


_server_thread: Optional[threading.Thread] = None
_server_config: Optional[uvicorn.Config] = None


def find_free_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No free port found in range {start_port}-{start_port + max_attempts}"
    )


def start_dashboard(
    tracker,
    host: str = "127.0.0.1",
    port: int = 8000,
    auto_port: bool = True,
) -> str:
    global _server_thread, _server_config

    if _server_thread and _server_thread.is_alive():
        logger.warning("Dashboard already running")
        return f"http://{host}:{port}"

    from dashboard.backend.server import set_tracker, push_tracker_event, app

    set_tracker(tracker)
    tracker.register_dashboard_callback(push_tracker_event)

    if auto_port:
        port = find_free_port(port)

    _server_config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(_server_config)

    def run_server():
        server.run()

    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()

    time.sleep(0.5)
    url = f"http://{host}:{port}"
    print(f"\n{'=' * 60}")
    print(f"  BeliefState Dashboard running at: {url}")
    print(f"{'=' * 60}\n")
    return url


def stop_dashboard():
    global _server_thread, _server_config
    if _server_config and _server_config.loaded_app:
        _server_config.loaded_app.state.should_exit = True
    _server_thread = None
    _server_config = None
