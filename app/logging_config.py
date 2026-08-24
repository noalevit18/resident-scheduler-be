"""Central logging configuration for the app.

Called once, as early as possible, from app.main. Every module that does
`logger = logging.getLogger(__name__)` inherits this configuration since
they all propagate up to the root logger.

Behavior is controlled via env vars so production (Cloud Run, which
captures container stdout/stderr into Cloud Logging) and local dev can
diverge without code changes:

- LOG_LEVEL: root logger level, default "INFO".
- LOG_TO_FILE: "true"/"1"/"yes" to additionally write logs to a local file.
  Default off (console/stdout only, matching the Cloud Run deploy path).
- LOG_FILE_PATH: where to write the file when LOG_TO_FILE is enabled.
  Default "logs/app.log".
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def configure_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter(_LOG_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if _is_truthy(os.getenv("LOG_TO_FILE", "false")):
        log_file_path = os.getenv("LOG_FILE_PATH", "logs/app.log")
        os.makedirs(os.path.dirname(log_file_path) or ".", exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
