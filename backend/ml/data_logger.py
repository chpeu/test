"""Minimal stub for the legacy backend ML DataLogger.

This no-op implementation keeps backward compatibility with the previous
`backend.ml.data_logger` module that was removed when switching to the
PostgreSQL DataLogger.  The current codebase still imports `DataLogger`
from this path as an optional logger, so we provide a lightweight
singleton that silently ignores all logging requests while keeping the
same async API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DataLogger:
    """No-op singleton used to avoid import errors for the legacy logger."""

    _instance: Optional["DataLogger"] = None

    def __new__(cls) -> "DataLogger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance.is_running = False
        return cls._instance

    async def initialize(self) -> None:
        """Simulate async initialization."""
        if not self._initialized:
            self._initialized = True
            self.is_running = True
            logger.info("Legacy DataLogger stub initialized (no-op).")

    async def shutdown(self) -> None:
        if self.is_running:
            self.is_running = False
            logger.info("Legacy DataLogger stub shutdown (no-op).")

    async def log_scan(self, *_, **__) -> Optional[int]:
        return None

    async def log_opportunity(self, *_, **__) -> Optional[int]:
        return None

    async def log_trade_entry(self, *_, **__) -> Optional[int]:
        return None

    async def log_trade_exit(self, *_, **__) -> None:
        return None


# Backward compatible helper for synchronous contexts
async def _ensure_initialized() -> DataLogger:
    logger_instance = DataLogger()
    if not logger_instance.is_running:
        await logger_instance.initialize()
    return logger_instance


def ensure_running_sync() -> None:
    """Allow synchronous code to ensure the stub is initialized."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_ensure_initialized())
    else:
        loop.create_task(_ensure_initialized())
