#!/usr/bin/env python3
"""
Recovery Mode - Trade Cursor v7.0
Gestion du mode récupération progressif après pertes
"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RecoveryModeConfig:
    """Configuration Recovery Mode"""
    enabled: bool = True
    mode: str = 'PROGRESSIVE'  # 'SIMPLE' ou 'PROGRESSIVE'

    # Mode SIMPLE
    trigger_loss_streak: int = 3
    min_score_boost: float = 1.5
    position_size_reduction: float = 0.7
    confluence_forced: bool = False
    duration_trades: int = 5

    # Mode PROGRESSIVE
    levels: List[Dict] = field(default_factory=lambda: [
        {'trigger_loss_streak': 2, 'min_score_boost': 0.5, 'position_size_reduction': 0.85, 'duration_trades': 3},
        {'trigger_loss_streak': 3, 'min_score_boost': 1.5, 'position_size_reduction': 0.7, 'duration_trades': 5},
        {'trigger_loss_streak': 5, 'min_score_boost': 2.5, 'position_size_reduction': 0.5, 'confluence_forced': True, 'duration_trades': 10}
    ])


@dataclass
class RecoveryState:
    """Snapshot structuré de l'état Recovery (usage shadow / refactor)."""
    active: bool
    level: Optional[int]
    loss_streak: int
    min_score_boost: float
    position_size_mult: float
    confluence_forced: bool
    remaining_trades: int


class RecoveryModeManager:
    """Gestionnaire Recovery Mode"""

    def __init__(self, config: Optional[RecoveryModeConfig] = None):
        self.config = config or RecoveryModeConfig()
        self.active = False
        self.remaining_trades = 0

    def get_recovery_level(self, loss_streak: int) -> Optional[Dict]:
        """
        Obtenir niveau recovery selon loss streak

        Args:
            loss_streak: Nombre de pertes consécutives

        Returns:
            Dict avec config niveau recovery ou None
        """
        if not self.config.enabled:
            return None

        if self.config.mode == 'SIMPLE':
            if loss_streak >= self.config.trigger_loss_streak:
                return {
                    'level': 1,
                    'min_score_boost': self.config.min_score_boost,
                    'position_size_reduction': self.config.position_size_reduction,
                    'confluence_forced': self.config.confluence_forced,
                    'duration_trades': self.config.duration_trades
                }
            return None

        # Mode PROGRESSIVE
        applicable_level = None
        for i, level in enumerate(self.config.levels):
            if loss_streak >= level['trigger_loss_streak']:
                applicable_level = {**level, 'level': i + 1}

        return applicable_level

    def get_state(self, loss_streak: int, use_active_flag: bool = True) -> RecoveryState:
        """
        Construire un snapshot RecoveryState sans modifier la logique existante.

        Args:
            loss_streak: Nombre de pertes consécutives
            use_active_flag: True = active basé sur self.active (comportement actuel)
        """
        level = self.get_recovery_level(loss_streak)
        active = self.active if use_active_flag else bool(level)
        min_score_boost = level.get('min_score_boost', 0.0) if level else 0.0
        position_size_mult = level.get('position_size_reduction', 1.0) if level else 1.0
        confluence_forced = level.get('confluence_forced', False) if level else False
        remaining_trades = self.remaining_trades if active else 0

        return RecoveryState(
            active=active,
            level=level.get('level') if level else None,
            loss_streak=loss_streak,
            min_score_boost=min_score_boost,
            position_size_mult=position_size_mult,
            confluence_forced=confluence_forced,
            remaining_trades=remaining_trades
        )

    def activate(self, loss_streak: int) -> Optional[Dict]:
        """
        Activer Recovery Mode

        Args:
            loss_streak: Nombre de pertes actuelles

        Returns:
            Config niveau activé ou None
        """
        level = self.get_recovery_level(loss_streak)

        if level and not self.active:
            self.active = True
            self.remaining_trades = level.get('duration_trades', 5)

            logger.warning(
                f"🔄 RECOVERY MODE Niveau {level['level']} ACTIVÉ "
                f"après {loss_streak} losses "
                f"(durée: {self.remaining_trades} trades, "
                f"boost: +{level.get('min_score_boost', 0):.1f}, "
                f"réduction: {((1-level.get('position_size_reduction', 1))*100):.0f}%)"
            )

            return level

        return None

    def update_after_trade(self, is_win: bool) -> None:
        """
        Mettre à jour après un trade

        Args:
            is_win: True si trade gagnant
        """
        if not self.active:
            return

        self.remaining_trades -= 1

        if is_win or self.remaining_trades <= 0:
            logger.info(
                f"✅ RECOVERY MODE DÉSACTIVÉ "
                f"({'win streak' if is_win else 'durée écoulée'})"
            )
            self.deactivate()

    def deactivate(self) -> None:
        """Désactiver Recovery Mode"""
        self.active = False
        self.remaining_trades = 0

    def get_position_size_multiplier(self, loss_streak: int) -> float:
        """
        Obtenir multiplicateur taille position

        Args:
            loss_streak: Nombre de pertes

        Returns:
            Multiplicateur (ex: 0.7 = -30%)
        """
        level = self.get_recovery_level(loss_streak)
        if level:
            return level.get('position_size_reduction', 1.0)
        return 1.0

    def get_min_score_boost(self, loss_streak: int) -> float:
        """
        Obtenir boost score minimum

        Args:
            loss_streak: Nombre de pertes

        Returns:
            Boost score (ex: 1.5 points)
        """
        level = self.get_recovery_level(loss_streak)
        if level:
            return level.get('min_score_boost', 0.0)
        return 0.0
