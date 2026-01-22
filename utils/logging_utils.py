"""
Logging Utilities - Centralized logging with WebSocket support
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Colors for terminal output
try:
    from colorama import Fore, Style
    COLOR_MAP = {
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'WARNING': Fore.YELLOW,
        'INFO': Fore.GREEN,
        'DEBUG': Fore.CYAN
    }
    RESET_CODE = Style.RESET_ALL
except ImportError:
    COLOR_MAP = {
        'ERROR': '\x1b[31m',
        'CRITICAL': '\x1b[31m\x1b[1m',
        'WARNING': '\x1b[33m',
        'INFO': '\x1b[32m',
        'DEBUG': '\x1b[36m'
    }
    RESET_CODE = '\x1b[0m'

async def add_log(level: str, message: str, detail: str = ''):
    """
    Add a log entry to the system and broadcast via WebSocket.
    
    Args:
        level: Log level (INFO, WARNING, ERROR, etc.)
        message: Primary log message
        detail: Optional detailed information
    """
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    color = COLOR_MAP.get(level, '')
    
    # Message with ANSI colors for UI
    colored_message = f"{color}{message}{RESET_CODE}"
    if detail:
        colored_message += f" {color}{detail}{RESET_CODE}"
        
    entry = {
        'timestamp': timestamp,
        'level': level,
        'message': colored_message,
        'detail': detail,
        'raw_message': message
    }
    
    # Add to StateManager (thread-safe)
    state.add_log(entry)
    
    # Prune logs if too many (StateManager doesn't currently do this, let's keep it here for now)
    # Actually, StateManager should handle its own pruning.
    
    # Broadcast via WebSocket
    ws_mgr = state.get_ws_manager()
    if ws_mgr:
        try:
            await ws_mgr.emit('log', entry)
        except Exception as e:
            logger.error(f"Error emitting log via WS: {e}")
            
    # Also log to console
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(f"[{timestamp}] {level}: {message} {detail}")
