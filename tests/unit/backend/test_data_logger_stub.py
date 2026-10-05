"""Tests pour le stub data_logger de backend/ml."""

import pytest
import asyncio
from unittest.mock import MagicMock, patch


class TestDataLoggerStub:
    """Tests pour le stub DataLogger no-op."""

    def test_stub_singleton(self):
        """Test que le stub est un singleton."""
        from backend.ml.data_logger import DataLogger

        logger1 = DataLogger()
        logger2 = DataLogger()
        assert logger1 is logger2

    def test_stub_init(self):
        """Test que le stub s'initialise sans erreur."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        assert logger is not None
        assert hasattr(logger, "is_running")

    @pytest.mark.asyncio
    async def test_stub_initialize(self):
        """Test que initialize est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        await logger.initialize()
        assert logger.is_running is True

    @pytest.mark.asyncio
    async def test_stub_shutdown(self):
        """Test que shutdown est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        await logger.initialize()
        assert logger.is_running is True
        await logger.shutdown()
        assert logger.is_running is False

    @pytest.mark.asyncio
    async def test_stub_log_scan(self):
        """Test que log_scan est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        result = await logger.log_scan("BTC_USDT", {"open": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_stub_log_opportunity(self):
        """Test que log_opportunity est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        result = await logger.log_opportunity("BTC_USDT", {"score": 0.85})
        assert result is None

    @pytest.mark.asyncio
    async def test_stub_log_trade_entry(self):
        """Test que log_trade_entry est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        result = await logger.log_trade_entry("BTC_USDT", "LONG", 100.0, 0.5)
        assert result is None

    @pytest.mark.asyncio
    async def test_stub_log_trade_exit(self):
        """Test que log_trade_exit est un no-op asynchrone."""
        from backend.ml.data_logger import DataLogger

        logger = DataLogger()
        # Ne doit pas lever d'exception
        await logger.log_trade_exit("BTC_USDT", "LONG", 100.0, 101.0, 0.5)

    def test_ensure_running_sync_no_loop(self):
        """Test ensure_running_sync sans loop courante."""
        from backend.ml.data_logger import ensure_running_sync

        # Ne doit pas lever d'exception
        ensure_running_sync()

    @pytest.mark.asyncio
    async def test_ensure_running_sync_with_loop(self):
        """Test ensure_running_sync avec loop courante."""
        from backend.ml.data_logger import _ensure_initialized

        # Ne doit pas lever d'exception
        await _ensure_initialized()
