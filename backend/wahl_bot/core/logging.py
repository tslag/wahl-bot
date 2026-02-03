import logging
import os
import sys

from loguru import logger

# Centralized logging configuration using Loguru and intercepting stdlib logging
# Level can be controlled via the LOG_LEVEL environment variable (defaults to INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Remove any previously configured handlers to avoid duplicate logs
logger.remove()

# Configure Loguru sink (stdout) with a compact, structured format
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name} | {message}",
    backtrace=True,
    diagnose=False,
)


class InterceptHandler(logging.Handler):
    """Default handler to route stdlib logging to Loguru."""

    def emit(
        self, record: logging.LogRecord
    ) -> None:  # pragma: no cover - simple routing
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        # Find caller frame to preserve correct module/line in logs
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Install the intercept handler as the root logger handler
logging.basicConfig(handlers=[InterceptHandler()], level=LOG_LEVEL)

# Optionally adjust noisy third-party loggers
for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncio"):
    logging.getLogger(name).handlers = [InterceptHandler()]
    logging.getLogger(name).setLevel(LOG_LEVEL)

# Export the configured Loguru logger for application modules to import
# Usage: from core.logging import logger
