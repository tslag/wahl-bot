"""Centralized logging configuration using Loguru for the application.

This module configures Loguru and installs an intercept handler so code
that uses the standard library ``logging`` is routed through Loguru. The
log level can be adjusted via the ``LOG_LEVEL`` environment variable.
"""

import logging
import os
import sys

from loguru import logger

# NOTE: Allow overriding of log level via environment for runtime control
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
    """Handler to route stdlib logging records into Loguru.

    This preserves caller information so Loguru logs reflect the originating
    module/line rather than the interception point.
    """

    def emit(
        self, record: logging.LogRecord
    ) -> None:  # pragma: no cover - simple routing
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        # NOTE: Walk frames to skip logging internals and find original caller
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Install the intercept handler as the root logger handler
logging.basicConfig(handlers=[InterceptHandler()], level=LOG_LEVEL)

# NOTE: Reduce verbosity of noisy third-party loggers by routing them too
for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncio"):
    logging.getLogger(name).handlers = [InterceptHandler()]
    logging.getLogger(name).setLevel(LOG_LEVEL)

# Export the configured Loguru logger for application modules to import
# Usage: from core.logging import logger
