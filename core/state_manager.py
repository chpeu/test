"""
🔥 SPRINT 1.4: State Management Centralisé

Gestionnaire d'état centralisé et thread-safe pour remplacer les variables globales dispersées.

Problèmes résolus:
- Variables globales dispersées (app_state, scanner, analyzer, etc.)
- Accès concurrent non-sûr
- Pas de validation de types
- Difficile à tester
- Pas de cleanup automatique

Utilisation:
```python
from core.state_manager import get_state_manager

state = get_state_manager()

# Application state
state.set_scanning(True)
is_scanning = state.is_scanning

# Component instances
state.set_scanner(scanner_instance)
scanner = state.get_scanner()

# Thread-safe operations
async with state.lock("position"):
    position = state.active_position
    # ... modify position
```
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from threading import Lock
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class TradingStats:
    """Statistiques de trading"""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0

    @property
    def winrate(self) -> float:
        """Calculer winrate"""
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100.0


@dataclass
class ApplicationState:
    """État de l'application de trading"""
    # Scanning state
    is_scanning: bool = False

    # Active position
    active_position: Optional[Dict[str, Any]] = None

    # Trading stats
    stats: TradingStats = field(default_factory=TradingStats)

    # Top pairs discovered
    top_pairs: List[Dict[str, Any]] = field(default_factory=list)

    # Logs buffer
    logs: List[Dict[str, Any]] = field(default_factory=list)

    # Trade history
    trade_history: List[Dict[str, Any]] = field(default_factory=list)

    # Position closing failures (pour éviter boucles infinies)
    close_failure_count: int = 0
    close_failure_symbol: Optional[str] = None

    # Backend reboot flag
    backend_reboot_in_progress: bool = False

    # Session ID unique
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class StateManager:
    """
    Gestionnaire d'état centralisé et thread-safe.

    Features:
    - État application (is_scanning, active_position, stats, etc.)
    - Instances des composants (scanner, analyzer, position_manager, etc.)
    - Locks pour synchronisation (position_lock, scanner_lock)
    - Thread-safe avec Lock interne
    - Validation de types
    - Cleanup automatique

    Exemple:
    ```python
    state = StateManager()

    # Application state
    state.set_scanning(True)
    state.set_active_position({"symbol": "BTC/USDT", "side": "LONG"})

    # Components
    state.set_scanner(scanner_instance)
    scanner = state.get_scanner()

    # Thread-safe operations
    async with state.lock("position"):
        # Operations sur position garanties atomiques
        position = state.active_position
        state.set_active_position(None)
    ```
    """

    def __init__(self):
        """Initialiser StateManager"""
        # Application state
        self._app_state = ApplicationState()

        # Component instances
        self._scanner = None
        self._analyzer = None
        self._position_config = None
        self._position_manager = None
        self._price_provider = None
        self._scheduler = None
        self._trade_db = None
        self._analytics_db = None
        self._notification_manager = None
        self._live_order_manager = None
        self._simple_logger = None
        self._ws_manager = None  # Sprint 2.1
        
        # Files & Paths
        self._trade_history_file = None  # Sprint 2.1

        # Locks for synchronization
        self._locks: Dict[str, asyncio.Lock] = {
            "position": asyncio.Lock(),
            "scanner": asyncio.Lock(),
            "state": asyncio.Lock(),  # Pour opérations atomiques sur state
        }

        # Thread lock for sync access
        self._thread_lock = Lock()

        logger.info("✅ StateManager initialisé")

    # ==================== Application State ====================

    @property
    def is_scanning(self) -> bool:
        """Get scanning status (thread-safe)"""
        with self._thread_lock:
            return self._app_state.is_scanning

    def set_scanning(self, value: bool) -> None:
        """Set scanning status (thread-safe)"""
        with self._thread_lock:
            self._app_state.is_scanning = value
            logger.debug(f"Scanning status: {value}")

    @property
    def active_position(self) -> Optional[Dict[str, Any]]:
        """Get active position (thread-safe)"""
        with self._thread_lock:
            return self._app_state.active_position

    def set_active_position(self, position: Optional[Dict[str, Any]]) -> None:
        """Set active position (thread-safe)"""
        with self._thread_lock:
            self._app_state.active_position = position
            if position:
                logger.debug(f"Active position set: {position.get('symbol')}")
            else:
                logger.debug("Active position cleared")

    @property
    def stats(self) -> TradingStats:
        """Get trading stats (thread-safe)"""
        with self._thread_lock:
            return self._app_state.stats

    def update_stats(self, **kwargs) -> None:
        """
        Update trading stats (thread-safe)

        Args:
            **kwargs: Stats to update (total_trades, wins, losses)
        """
        with self._thread_lock:
            if "total_trades" in kwargs:
                self._app_state.stats.total_trades = kwargs["total_trades"]
            if "wins" in kwargs:
                self._app_state.stats.wins = kwargs["wins"]
            if "losses" in kwargs:
                self._app_state.stats.losses = kwargs["losses"]

    @property
    def top_pairs(self) -> List[Dict[str, Any]]:
        """Get top pairs (thread-safe)"""
        with self._thread_lock:
            return self._app_state.top_pairs.copy()

    def set_top_pairs(self, pairs: List[Dict[str, Any]]) -> None:
        """Set top pairs (thread-safe)"""
        with self._thread_lock:
            self._app_state.top_pairs = pairs.copy()
            logger.debug(f"Top pairs updated: {len(pairs)} pairs")

    @property
    def logs(self) -> List[Dict[str, Any]]:
        """Get logs (thread-safe)"""
        with self._thread_lock:
            return self._app_state.logs.copy()

    def add_log(self, log: Dict[str, Any]) -> None:
        """Add log entry (thread-safe)"""
        with self._thread_lock:
            self._app_state.logs.append(log)

    def clear_logs(self) -> None:
        """Clear all logs (thread-safe)"""
        with self._thread_lock:
            self._app_state.logs.clear()

    @property
    def trade_history(self) -> List[Dict[str, Any]]:
        """Get trade history (thread-safe)"""
        with self._thread_lock:
            return self._app_state.trade_history.copy()

    def add_trade(self, trade: Dict[str, Any]) -> None:
        """Add trade to history (thread-safe)"""
        with self._thread_lock:
            self._app_state.trade_history.append(trade)
            logger.debug(f"Trade added: {trade.get('symbol')}")

    def set_trade_history(self, history: List[Dict[str, Any]]) -> None:
        """Set trade history (thread-safe)"""
        with self._thread_lock:
            self._app_state.trade_history = history.copy()

    @property
    def close_failure_count(self) -> int:
        """Get close failure count"""
        with self._thread_lock:
            return self._app_state.close_failure_count

    def increment_close_failure(self, symbol: Optional[str] = None) -> None:
        """Increment close failure count (thread-safe)"""
        with self._thread_lock:
            self._app_state.close_failure_count += 1
            if symbol:
                self._app_state.close_failure_symbol = symbol

    def reset_close_failure(self) -> None:
        """Reset close failure counters (thread-safe)"""
        with self._thread_lock:
            self._app_state.close_failure_count = 0
            self._app_state.close_failure_symbol = None

    @property
    def backend_reboot_in_progress(self) -> bool:
        """Get backend reboot flag"""
        with self._thread_lock:
            return self._app_state.backend_reboot_in_progress

    def set_backend_reboot(self, value: bool) -> None:
        """Set backend reboot flag (thread-safe)"""
        with self._thread_lock:
            self._app_state.backend_reboot_in_progress = value

    @property
    def session_id(self) -> str:
        """Get session ID"""
        with self._thread_lock:
            return self._app_state.session_id

    # ==================== Component Instances ====================

    def get_scanner(self):
        """Get scanner instance"""
        with self._thread_lock:
            return self._scanner

    def set_scanner(self, scanner) -> None:
        """Set scanner instance"""
        with self._thread_lock:
            self._scanner = scanner

    def get_analyzer(self):
        """Get analyzer instance"""
        with self._thread_lock:
            return self._analyzer

    def set_analyzer(self, analyzer) -> None:
        """Set analyzer instance"""
        with self._thread_lock:
            self._analyzer = analyzer

    def get_position_config(self):
        """Get position config"""
        with self._thread_lock:
            return self._position_config

    def set_position_config(self, config) -> None:
        """Set position config"""
        with self._thread_lock:
            self._position_config = config

    def get_position_manager(self):
        """Get position manager instance"""
        with self._thread_lock:
            return self._position_manager

    def set_position_manager(self, manager) -> None:
        """Set position manager instance"""
        with self._thread_lock:
            self._position_manager = manager

    def get_price_provider(self):
        """Get price provider instance"""
        with self._thread_lock:
            return self._price_provider

    def set_price_provider(self, provider) -> None:
        """Set price provider instance"""
        with self._thread_lock:
            self._price_provider = provider

    def get_scheduler(self):
        """Get scheduler instance"""
        with self._thread_lock:
            return self._scheduler

    def set_scheduler(self, scheduler) -> None:
        """Set scheduler instance"""
        with self._thread_lock:
            self._scheduler = scheduler

    def get_trade_db(self):
        """Get trade database instance"""
        with self._thread_lock:
            return self._trade_db

    def set_trade_db(self, db) -> None:
        """Set trade database instance"""
        with self._thread_lock:
            self._trade_db = db

    def get_analytics_db(self):
        """Get analytics database instance"""
        with self._thread_lock:
            return self._analytics_db

    def set_analytics_db(self, db) -> None:
        """Set analytics database instance"""
        with self._thread_lock:
            self._analytics_db = db

    def get_notification_manager(self):
        """Get notification manager instance"""
        with self._thread_lock:
            return self._notification_manager

    def set_notification_manager(self, manager) -> None:
        """Set notification manager instance"""
        with self._thread_lock:
            self._notification_manager = manager

    def get_live_order_manager(self):
        """Get live order manager instance"""
        with self._thread_lock:
            return self._live_order_manager

    def set_live_order_manager(self, manager) -> None:
        """Set live order manager instance"""
        with self._thread_lock:
            self._live_order_manager = manager

    def get_simple_logger(self):
        """Get simple logger instance"""
        with self._thread_lock:
            return self._simple_logger

    def set_simple_logger(self, logger) -> None:
        """Set simple logger instance"""
        with self._thread_lock:
            self._simple_logger = logger
    
    def get_ws_manager(self):
        """Get WebSocket manager instance (Sprint 2.1)"""
        with self._thread_lock:
            return self._ws_manager
    
    def set_ws_manager(self, manager) -> None:
        """Set WebSocket manager instance (Sprint 2.1)"""
        with self._thread_lock:
            self._ws_manager = manager
    
    @property
    def trade_history_file(self) -> Optional[str]:
        """Get trade history file path (Sprint 2.1)"""
        with self._thread_lock:
            return self._trade_history_file
    
    def set_trade_history_file(self, path: str) -> None:
        """Set trade history file path (Sprint 2.1)"""
        with self._thread_lock:
            self._trade_history_file = path

    # ==================== Locks ====================

    def lock(self, name: str) -> asyncio.Lock:
        """
        Get async lock by name for synchronized operations

        Args:
            name: Lock name ("position", "scanner", "state")

        Returns:
            asyncio.Lock

        Example:
            ```python
            async with state.lock("position"):
                # Atomic position operations
                pass
            ```
        """
        if name not in self._locks:
            raise ValueError(f"Unknown lock: {name}. Available: {list(self._locks.keys())}")
        return self._locks[name]

    # ==================== Serialization ====================

    def to_dict(self) -> Dict[str, Any]:
        """
        Export state as dict (for compatibility with legacy app_state)

        Returns:
            Dict compatible avec ancien app_state
        """
        with self._thread_lock:
            return {
                "is_scanning": self._app_state.is_scanning,
                "active_position": self._app_state.active_position,
                "stats": {
                    "total_trades": self._app_state.stats.total_trades,
                    "wins": self._app_state.stats.wins,
                    "losses": self._app_state.stats.losses,
                    "winrate": self._app_state.stats.winrate,
                },
                "top_pairs": self._app_state.top_pairs.copy(),
                "logs": self._app_state.logs.copy(),
                "trade_history": self._app_state.trade_history.copy(),
                "close_failure_count": self._app_state.close_failure_count,
                "close_failure_symbol": self._app_state.close_failure_symbol,
            }

    # ==================== Cleanup ====================

    def cleanup(self) -> None:
        """Cleanup state (reset to defaults)"""
        with self._thread_lock:
            self._app_state = ApplicationState()
            logger.info("🧹 StateManager cleaned up")


# Singleton instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """
    Get singleton StateManager instance

    Returns:
        StateManager singleton
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def reset_state_manager() -> None:
    """Reset singleton (for testing)"""
    global _state_manager
    _state_manager = None
