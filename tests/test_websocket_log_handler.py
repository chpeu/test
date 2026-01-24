import asyncio
import logging

import pytest

from core.shutdown import GracefulShutdown, set_shutdown_manager
from utils.logger import WebSocketLogHandler, drain_websocket_log_handlers


class DummyWsManager:
    def __init__(self):
        self.calls = []

    async def emit(self, event, data):
        self.calls.append((event, data))
        await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_websocket_log_handler_drain_cancels_pending_tasks():
    set_shutdown_manager(None)

    ws_mgr = DummyWsManager()
    handler = WebSocketLogHandler()
    handler.set_ws_manager(ws_mgr)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger("test_ws_log_handler_drain")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("hello")
    assert len(handler._tasks) >= 1

    await handler.drain(timeout=0)
    assert len(handler._tasks) == 0

    logger.info("after_drain")
    await asyncio.sleep(0)
    assert len(handler._tasks) == 0


@pytest.mark.asyncio
async def test_websocket_log_handler_skips_when_shutdown_in_progress():
    ws_mgr = DummyWsManager()
    handler = WebSocketLogHandler()
    handler.set_ws_manager(ws_mgr)

    logger = logging.getLogger("test_ws_log_handler_shutdown")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    shutdown = GracefulShutdown(timeout=1.0)
    set_shutdown_manager(shutdown)
    shutdown.is_shutting_down = True

    try:
        logger.info("hello")
        await asyncio.sleep(0)
        assert len(handler._tasks) == 0
    finally:
        set_shutdown_manager(None)


@pytest.mark.asyncio
async def test_drain_websocket_log_handlers_drains_all_instances():
    set_shutdown_manager(None)

    ws_mgr = DummyWsManager()
    handler = WebSocketLogHandler()
    handler.set_ws_manager(ws_mgr)

    logger = logging.getLogger("test_drain_ws_handlers")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("hello")
    assert len(handler._tasks) >= 1

    await drain_websocket_log_handlers(timeout=0)
    assert len(handler._tasks) == 0
