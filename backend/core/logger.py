import json
import logging
import sys
from datetime import datetime, timezone

from config import LOG_LEVEL, LOG_FORMAT


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "time":    datetime.now(timezone.utc).isoformat(),
            "level":   record.levelname,
            "logger":  record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)
        for field in ("request_id", "model", "latency"):
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        return json.dumps(entry, default=str)


class _PlainFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def setup_logging() -> None:
    root    = logging.getLogger()
    level   = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    fmt     = _JSONFormatter() if LOG_FORMAT.lower() == "json" else _PlainFormatter()
    handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(fmt)
    root.setLevel(level)

    if root.hasHandlers():
        root.handlers.clear()

    root.addHandler(handler)

    # silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
