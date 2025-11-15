"""Application state helpers for FastAPI dependencies."""
from __future__ import annotations

from collections import UserDict
from copy import deepcopy
from typing import Any, Dict


class ApplicationState(UserDict):
    """Centralized mutable state shared across routes and services."""

    _DEFAULT_STATE: Dict[str, Any] = {
        "top_pairs": [],
        "scanner_running": False,
        "is_scanning": False,
        "active_position": None,
        "logs": [],
        "trade_history": [],
        "stats": {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": 0.0,
        },
    }

    def __init__(self, initial: Dict[str, Any] | None = None):
        super().__init__(deepcopy(self._DEFAULT_STATE))
        if initial:
            self.update(initial)

    def reset(self) -> None:
        """Reset state to default values."""
        self.clear()
        self.update(deepcopy(self._DEFAULT_STATE))

    def as_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation (useful for responses)."""
        return deepcopy(self.data)


__all__ = ["ApplicationState"]
