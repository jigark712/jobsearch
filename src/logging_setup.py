import json
import logging
import sys
from datetime import datetime, timezone

from src.paths import LOGS_DIR, ensure_data_dirs


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key in ("args", "msg", "levelname", "levelno", "pathname", "filename",
                       "module", "exc_info", "exc_text", "stack_info", "lineno",
                       "funcName", "created", "msecs", "relativeCreated", "thread",
                       "threadName", "processName", "process", "name", "message",
                       "taskName"):
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    ensure_data_dirs()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(LOGS_DIR / f"{today}.jsonl")
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(stream)

    return logger
