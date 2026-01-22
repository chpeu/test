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
from collections.abc import MutableMapping, MutableSequence

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
        self._pg_datalogger = None
        self._simple_logger = None
        self._ws_manager = None  # Sprint 2.1
        
        # Files & Paths
        self._trade_history_file = None  # Sprint 2.1

        # Locks for synchronization (Lazy initialization to avoid event loop issues)
        self._locks: Dict[str, asyncio.Lock] = {}

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

    def set_is_scanning(self, value: bool) -> None:
        with self._thread_lock:
            self._app_state.is_scanning = value
            logger.debug(f"Scanning status: {value}")

    @property
    def active_position(self) -> Optional[Any]:
        """Get active position (thread-safe)"""
        with self._thread_lock:
            return self._app_state.active_position

    def set_active_position(self, position: Optional[Any]) -> None:
        """Set active position (thread-safe)"""
        with self._thread_lock:
            self._app_state.active_position = position
            if position:
                symbol = None
                if isinstance(position, dict):
                    symbol = position.get("symbol")
                elif hasattr(position, "symbol"):
                    try:
                        symbol = getattr(position, "symbol")
                    except Exception:
                        symbol = None
                elif hasattr(position, "get"):
                    try:
                        symbol = position.get("symbol")
                    except Exception:
                        symbol = None
                logger.debug(f"Active position set: {symbol}")
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

    def set_logs(self, logs: List[Dict[str, Any]]) -> None:
        with self._thread_lock:
            self._app_state.logs = logs.copy()

    @property
    def trade_history(self) -> List[Dict[str, Any]]:
        """Get trade history (thread-safe)"""
        with self._thread_lock:
            return self._app_state.trade_history.copy()

    def add_trade(self, trade: Dict[str, Any]) -> None:
        """Add or update trade in history (thread-safe upsert)"""
        with self._thread_lock:
            if not trade or not isinstance(trade, dict):
                return
            
            # Validation minimale : ignorer les trades vides ou sans symbole
            if not trade.get('symbol'):
                return

            # 🔥 FIX: Ignorer les trades qui semblent "ouverts" ou incomplets (N/A dans UI)
            # Un trade historique doit avoir une raison de sortie ou un PnL finalisé
            has_reason = bool(trade.get('reason') or trade.get('exit_reason') or trade.get('close_reason'))
            has_pnl = trade.get('pnl_usdt') is not None or trade.get('net_pnl_usdt') is not None
            
            if not has_reason and not has_pnl:
                # logger.debug(f"⚠️ Trade ignoré dans l'historique (incomplet/ouvert): {trade.get('symbol')}")
                return

            # Récupérer l'ID pour l'upsert
            trade_id = trade.get('id') or trade.get('trade_id') or trade.get('closure_id')
            
            target_idx = -1
            
            # 1. Essayer de trouver par ID explicite
            if trade_id:
                for i, t in enumerate(self._app_state.trade_history):
                    t_id = t.get('id') or t.get('trade_id') or t.get('closure_id')
                    if t_id == trade_id:
                        target_idx = i
                        break
            
            # 2. Si pas trouvé et ID manquant, essayer détection heuristique (Symbol + Timestamp précis)
            # Risqué, donc on ne le fait que si on a des timestamps précis
            if target_idx == -1 and not trade_id:
                ts = trade.get('timestamp') or trade.get('closed_at')
                if ts:
                    for i, t in enumerate(self._app_state.trade_history):
                        if t.get('symbol') == trade['symbol']:
                            t_ts = t.get('timestamp') or t.get('closed_at')
                            if t_ts == ts:
                                target_idx = i
                                break

            if target_idx >= 0:
                # UPDATE
                self._app_state.trade_history[target_idx].update(trade)
                logger.debug(f"Trade updated in history: {trade.get('symbol')} (ID: {trade_id})")
            else:
                # INSERT
                self._app_state.trade_history.append(trade)
                logger.debug(f"Trade added to history: {trade.get('symbol')} (ID: {trade_id})")

    def set_trade_history(self, history: List[Dict[str, Any]]) -> None:
        """Set trade history (thread-safe)"""
        with self._thread_lock:
            self._app_state.trade_history = history.copy()

    @property
    def close_failure_count(self) -> int:
        """Get close failure count"""
        with self._thread_lock:
            return self._app_state.close_failure_count

    @property
    def close_failure_symbol(self) -> Optional[str]:
        with self._thread_lock:
            return self._app_state.close_failure_symbol

    def set_close_failure_count(self, value: int) -> None:
        with self._thread_lock:
            self._app_state.close_failure_count = int(value)

    def set_close_failure_symbol(self, symbol: Optional[str]) -> None:
        with self._thread_lock:
            self._app_state.close_failure_symbol = symbol

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

    def get_pg_datalogger(self):
        """Get PostgreSQL DataLogger instance"""
        with self._thread_lock:
            return self._pg_datalogger

    def set_pg_datalogger(self, datalogger) -> None:
        """Set PostgreSQL DataLogger instance"""
        with self._thread_lock:
            self._pg_datalogger = datalogger

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

    def get_legacy_proxy(self) -> 'LegacyAppStateProxy':
        """
        Get a LegacyAppStateProxy for backward compatibility.
        
        Returns:
            LegacyAppStateProxy instance
        """
        return LegacyAppStateProxy(self)

    # ==================== Locks ====================

    def lock(self, name: str) -> asyncio.Lock:
        """
        Get async lock by name for synchronized operations
        (Lazy initialization ensures the lock is created in the current event loop)

        Args:
            name: Lock name ("position", "scanner", "state")

        Returns:
            asyncio.Lock
        """
        valid_locks = ["position", "scanner", "state"]
        if name not in valid_locks:
            raise ValueError(f"Unknown lock: {name}. Available: {valid_locks}")
        
        with self._thread_lock:
            if name not in self._locks:
                self._locks[name] = asyncio.Lock()
            return self._locks[name]

    # ==================== Serialization ====================

    def to_dict(self) -> Dict[str, Any]:
        """
        Export state as dict (for compatibility with legacy app_state)

        Returns:
            Dict compatible avec ancien app_state
        """
        with self._thread_lock:
            active_position: Any = self._app_state.active_position
            if active_position is not None and hasattr(active_position, "to_dict"):
                try:
                    active_position = active_position.to_dict()
                except Exception:
                    pass
            return {
                "is_scanning": self._app_state.is_scanning,
                "active_position": active_position,
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
                "session_id": self._app_state.session_id,
            }

    # ==================== Cleanup ====================

    def cleanup(self) -> None:
        """Cleanup state (reset to defaults)"""
        with self._thread_lock:
            self._app_state = ApplicationState()
            logger.info("🧹 StateManager cleaned up")


class _LegacyStatsProxy(dict):
    def __init__(self, state: "StateManager"):
        self._state = state
        super().__init__()
        self._refresh()

    def _refresh(self) -> None:
        stats = self._state.stats
        super().clear()
        super().update({
            "total_trades": stats.total_trades,
            "wins": stats.wins,
            "losses": stats.losses,
            "winrate": stats.winrate,
        })

    def __getitem__(self, key):
        self._refresh()
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._refresh()
        return super().get(key, default)

    def items(self):
        self._refresh()
        return super().items()

    def keys(self):
        self._refresh()
        return super().keys()

    def values(self):
        self._refresh()
        return super().values()

    def __iter__(self):
        self._refresh()
        return super().__iter__()

    def __len__(self):
        self._refresh()
        return super().__len__()

    def __setitem__(self, key, value):
        if key == "total_trades":
            self._state.update_stats(total_trades=int(value))
        elif key == "wins":
            self._state.update_stats(wins=int(value))
        elif key == "losses":
            self._state.update_stats(losses=int(value))
        elif key == "winrate":
            return
        else:
            raise KeyError(key)
        self._refresh()

    def update(self, *args, **kwargs):
        data = dict(*args, **kwargs)
        for k, v in data.items():
            self.__setitem__(k, v)

    def to_dict(self) -> Dict[str, Any]:
        self._refresh()
        return dict(self)


class _LegacyListProxy(list):
    def __init__(self, getter, setter, append_item=None):
        self._getter = getter
        self._setter = setter
        self._append_item = append_item
        super().__init__()
        self._refresh()

    def _refresh(self) -> None:
        data = self._getter() or []
        super().clear()
        super().extend(list(data))

    def _commit(self) -> None:
        self._setter(list(self))

    def __len__(self):
        self._refresh()
        return super().__len__()

    def __getitem__(self, index):
        self._refresh()
        return super().__getitem__(index)

    def __iter__(self):
        self._refresh()
        return super().__iter__()

    def __setitem__(self, index, value):
        self._refresh()
        super().__setitem__(index, value)
        self._commit()

    def __delitem__(self, index):
        self._refresh()
        super().__delitem__(index)
        self._commit()

    def insert(self, index, value):
        self._refresh()
        super().insert(index, value)
        self._commit()

    def append(self, value):
        if self._append_item is not None:
            self._append_item(value)
            self._refresh()
            return
        self._refresh()
        super().append(value)
        self._commit()

    def extend(self, iterable):
        self._refresh()
        super().extend(iterable)
        self._commit()

    def clear(self):
        self._refresh()
        super().clear()
        self._commit()

    def pop(self, index: int = -1):
        self._refresh()
        value = super().pop(index)
        self._commit()
        return value

    def remove(self, value):
        self._refresh()
        super().remove(value)
        self._commit()

    def to_list(self) -> List[Any]:
        self._refresh()
        return list(self)


class LegacyAppStateProxy(MutableMapping):
    def __init__(self, state: "StateManager"):
        self._state = state
        self._extras: Dict[str, Any] = {}
        self._stats = _LegacyStatsProxy(state)
        self._top_pairs = _LegacyListProxy(lambda: state.top_pairs, state.set_top_pairs)
        self._logs = _LegacyListProxy(lambda: state.logs, state.set_logs, append_item=state.add_log)
        self._trade_history = _LegacyListProxy(lambda: state.trade_history, state.set_trade_history, append_item=state.add_trade)

    def __getitem__(self, key):
        if key == "is_scanning":
            return self._state.is_scanning
        if key == "active_position":
            return self._state.active_position
        if key == "stats":
            return self._stats
        if key == "top_pairs":
            return self._top_pairs
        if key == "logs":
            return self._logs
        if key == "trade_history":
            return self._trade_history
        if key == "close_failure_count":
            return self._state.close_failure_count
        if key == "close_failure_symbol":
            return self._state.close_failure_symbol
        if key == "backend_reboot_in_progress":
            return self._state.backend_reboot_in_progress
        if key == "session_id":
            return self._state.session_id
        
        # 🔥 FIX: Rechercher dans TRADING_CONFIG si la clé n'est pas dans l'état de l'app
        if key in self._extras:
            return self._extras[key]
            
        from config import TRADING_CONFIG
        if key in TRADING_CONFIG:
            return TRADING_CONFIG[key]
            
        raise KeyError(key)

    def __setitem__(self, key, value):
        if key == "is_scanning":
            self._state.set_scanning(bool(value))
            return
        if key == "active_position":
            self._state.set_active_position(value)
            return
        if key == "stats":
            if isinstance(value, dict):
                if "total_trades" in value:
                    self._state.update_stats(total_trades=int(value["total_trades"]))
                if "wins" in value:
                    self._state.update_stats(wins=int(value["wins"]))
                if "losses" in value:
                    self._state.update_stats(losses=int(value["losses"]))
            return
        if key == "top_pairs":
            self._state.set_top_pairs(list(value) if value else [])
            return
        if key == "logs":
            self._state.set_logs(list(value) if value else [])
            return
        if key == "trade_history":
            self._state.set_trade_history(list(value) if value else [])
            return
        if key == "close_failure_count":
            self._state.set_close_failure_count(int(value))
            return
        if key == "close_failure_symbol":
            self._state.set_close_failure_symbol(value)
            return
        if key == "backend_reboot_in_progress":
            self._state.set_backend_reboot(bool(value))
            return
        if key == "session_id":
            self._extras[key] = value
            return
        self._extras[key] = value

    def __delitem__(self, key):
        del self._extras[key]

    def __iter__(self):
        keys = [
            "is_scanning",
            "active_position",
            "stats",
            "top_pairs",
            "logs",
            "trade_history",
            "close_failure_count",
            "close_failure_symbol",
            "backend_reboot_in_progress",
            "session_id",
        ]
        seen = set(keys)
        for k in keys:
            yield k
        for k in self._extras.keys():
            if k not in seen:
                yield k

    def __len__(self):
        return len(list(iter(self)))

    def copy(self) -> Dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        active_position = self._state.active_position
        if active_position is not None and hasattr(active_position, "to_dict"):
            try:
                active_position = active_position.to_dict()
            except Exception:
                pass

        data: Dict[str, Any] = {
            "is_scanning": self._state.is_scanning,
            "active_position": active_position,
            "stats": self._stats.to_dict(),
            "top_pairs": self._top_pairs.to_list(),
            "logs": self._logs.to_list(),
            "trade_history": self._trade_history.to_list(),
            "close_failure_count": self._state.close_failure_count,
            "close_failure_symbol": self._state.close_failure_symbol,
            "backend_reboot_in_progress": self._state.backend_reboot_in_progress,
            "session_id": self._state.session_id,
        }
        for k, v in self._extras.items():
            if k not in data:
                data[k] = v
        return data


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
