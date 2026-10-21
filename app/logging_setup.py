"""Asynchronous, non-blocking logging (Protocol 4).

Request-path cost is a single queue enqueue; a background QueueListener
thread performs file/console writes. Levels: DEBUG/INFO/WARNING/ERROR
controlled by LOG_LEVEL (default INFO).
"""
import atexit
import logging
import queue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_listener: QueueListener | None = None


def _shutdown() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


atexit.register(_shutdown)


def setup_logging(app) -> None:
    """Install the async pipeline on the root logger (idempotent)."""
    global _listener

    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    log_dir = Path(app.config["LOG_DIR"])
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    handlers: list[logging.Handler] = [file_handler]
    if not app.config.get("TESTING"):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(logging.Formatter(_FORMAT))
        handlers.append(console)

    # Keep third-party HTTP chatter out of the app log; we log AI calls ourselves.
    for noisy in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    log_queue: queue.Queue = queue.Queue(maxsize=1000)  # bounded => never blocks the request

    if _listener is not None:
        _listener.stop()
    _listener = QueueListener(log_queue, *handlers, respect_handler_level=True)
    _listener.start()

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if isinstance(handler, QueueHandler):  # remove only ours (idempotency in tests)
            root.removeHandler(handler)
    root.addHandler(QueueHandler(log_queue))

    # All application logs propagate to the root pipeline exactly once.
    app.logger.setLevel(level)
    app.logger.propagate = True
    for handler in list(app.logger.handlers):
        app.logger.removeHandler(handler)
