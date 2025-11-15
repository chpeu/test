"""Shared Pydantic schemas for API responses."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    winrate: float = 0.0
    profit_total: float = Field(0.0, description="Total net profit in USDT")
    profit_today: float = Field(0.0, description="Net profit for current day in USDT")
    drawdown: float = 0.0
    drawdown_max: float = 0.0
    drawdown_max_date: Optional[str] = None
    current_peak: float = 0.0
    win_streak: int = 0
    loss_streak: int = 0
    recovery_mode_active: bool = False
    equity_curve: List[float] = Field(default_factory=list)


class TradeHistoryItem(BaseModel):
    timestamp: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    entry: Optional[float] = None
    exit: Optional[float] = None
    gross_pnl_pct: Optional[float] = None
    gross_pnl_usdt: Optional[float] = None
    net_pnl_pct: Optional[float] = None
    net_pnl_usdt: Optional[float] = None
    fees: Optional[float] = None
    slippage: Optional[float] = None
    total_costs: Optional[float] = None
    reason: Optional[str] = None
    duration: Optional[float] = None


class DataloggerResetResponse(BaseModel):
    success: bool
    message: str
    deleted: Dict[str, int]
    total_deleted: int


__all__ = [
    "DashboardSummary",
    "TradeHistoryItem",
    "DataloggerResetResponse",
]
