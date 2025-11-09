#!/usr/bin/env python3
"""
Position Manager - Trade Cursor v7.0
Gestion des positions: TP/SL, Break-even, Trailing Stop
REFACTORISÉ avec architecture modulaire
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Import modules refactorisés
from core.position.tp_sl_calculator import (
    calculate_fixed_levels,
    calculate_atr_levels,
    TPSLConfig
)
from core.position.early_invalidation import (
    EarlyInvalidationChecker,
    EarlyInvalidationConfig
)
from core.position.trailing_stop import (
    TrailingStopManager,
    TrailingStopConfig
)
from core.position.pnl_calculator import PnLCalculator
from core.position.recovery_mode import (
    RecoveryModeManager,
    RecoveryModeConfig
)
from core.position.partial_tp_manager import PartialTPManager
from core.position.tp_escalier_manager import TPEscalierManager
from core.position.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Représente une position active"""
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    entry: float
    size: float
    sl: float
    tp: float
    atr: Optional[float] = None
    atr5m: Optional[float] = None
    confirmed_by: str = ""
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    start_time: float = field(default_factory=lambda: datetime.now().timestamp())

    # Scalability data for slippage calculation
    scalability_data: Optional[Dict] = None

    # State flags
    break_even_set: bool = False
    partial_tp_sold: bool = False

    # Dynamic SL (for trailing)
    dynamic_sl: Optional[float] = None

    # Position partielle physique
    size_remaining: Optional[float] = None
    partial_profit_usdt: float = 0.0
    capital: Optional[float] = None

    # Métriques conditions
    condition_types: List[str] = field(default_factory=list)

    # TP Escalier (Multi-Level TP)
    tp_escalier_enabled: bool = False
    tp_escalier_levels: List[Dict] = field(default_factory=list)
    tp_escalier_current_level: int = 0
    tp_escalier_size_remaining: float = 1.0
    tp_escalier_profits: List[Dict] = field(default_factory=list)

    pnl_history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convertir position en dictionnaire JSON"""
        return {
            'symbol': self.symbol,
            'direction': self.direction,
            'entry': self.entry,
            'size': self.size,
            'sl': self.sl,
            'tp': self.tp,
            'atr': self.atr,
            'atr5m': self.atr5m,
            'confirmed_by': self.confirmed_by,
            'timestamp': self.timestamp,
            'start_time': self.start_time,
            'break_even_set': self.break_even_set,
            'partial_tp_sold': self.partial_tp_sold,
            'dynamic_sl': self.dynamic_sl,
            'size_remaining': self.size_remaining,
            'partial_profit_usdt': self.partial_profit_usdt,
            'capital': self.capital,
            'tp_escalier_enabled': self.tp_escalier_enabled,
            'tp_escalier_current_level': self.tp_escalier_current_level,
            'tp_escalier_size_remaining': self.tp_escalier_size_remaining,
            'tp_escalier_profits': self.tp_escalier_profits
        }


@dataclass
class PositionConfig:
    """Configuration pour la gestion de position"""
    # Mode
    use_atr: bool = False

    # TP/SL FIXE
    fixed_tp_pct: float = 0.6
    fixed_sl_pct: float = 0.25

    # TP/SL ATR multipliers
    atr_mult_tp: float = 1.5
    atr_mult_sl: float = 1.0
    atr_min: float = 0.15
    atr_max: float = 1.5

    # Break-even & Trailing (FIXE mode)
    use_break_even: bool = True
    break_even_trigger: float = 0.3  # %
    use_trailing_stop: bool = True
    trailing_distance: float = 0.15  # %
    use_partial_tp: bool = True
    partial_tp_trigger: float = 0.25  # %

    # Break-even progressif (ATR mode)
    be_atr_factor: float = 1.5

    # Fees
    taker_fee: float = 0.0

    # Recovery Mode
    recovery_mode_active: bool = False
    recovery_mode_remaining_trades: int = 0
    use_fee_calculation: bool = True

    # Slippage estimation
    use_slippage_calculation: bool = True

    # Win/Loss streaks
    win_streak: int = 0
    loss_streak: int = 0


class PositionManager:
    """Gestionnaire de positions - Architecture modulaire v7.0"""

    @staticmethod
    def _format_price(price: float, min_decimals: int = 6, max_decimals: int = 10) -> str:
        """
        Formater un prix avec le bon nombre de décimales selon sa valeur

        Args:
            price: Prix à formater
            min_decimals: Nombre minimum de décimales (défaut: 6)
            max_decimals: Nombre maximum de décimales (défaut: 10)

        Returns:
            String formatée du prix
        """
        if price == 0:
            return "0.0"

        if price < 0.01:
            price_str = f"{price:.{max_decimals}f}"
            price_str = price_str.rstrip('0').rstrip('.')
            if '.' in price_str:
                decimals = len(price_str.split('.')[1])
                if decimals < min_decimals:
                    return f"{price:.{min_decimals}f}".rstrip('0').rstrip('.')
            return price_str
        else:
            return f"{price:.{min_decimals}f}"

    def __init__(self, config: PositionConfig, analytics_db=None):
        """
        Initialiser PositionManager avec modules

        Args:
            config: Configuration position
            analytics_db: Base de données Analytics (optionnel)
        """
        self.config = config
        self.active_position: Optional[Position] = None
        self.price_cache: Dict[str, Dict] = {}
        self.api_alert_shown = False
        self.last_price = 0.0
        self.last_price_update = datetime.now().timestamp() * 1000

        # Initialiser modules spécialisés
        self._init_modules(analytics_db)

    def _init_modules(self, analytics_db):
        """Initialiser tous les modules de gestion"""
        # Configuration TP/SL
        self.tpsl_config = TPSLConfig(
            fixed_tp_pct=self.config.fixed_tp_pct,
            fixed_sl_pct=self.config.fixed_sl_pct,
            atr_mult_tp=self.config.atr_mult_tp,
            atr_mult_sl=self.config.atr_mult_sl,
            atr_min=self.config.atr_min,
            atr_max=self.config.atr_max,
            win_streak=self.config.win_streak,
            loss_streak=self.config.loss_streak
        )

        # Early Invalidation
        from config import TRADING_CONFIG
        early_config_dict = TRADING_CONFIG.get('early_invalidation', {})
        self.early_invalidation = EarlyInvalidationChecker(
            EarlyInvalidationConfig(
                enabled=early_config_dict.get('enabled', True),
                threshold_15s=early_config_dict.get('threshold_15s', -0.12),
                threshold_30s=early_config_dict.get('threshold_30s', -0.08),
                adaptive_enabled=early_config_dict.get('adaptive_enabled', True),
                low_vol_multiplier=early_config_dict.get('low_vol_multiplier', 0.7),
                high_vol_multiplier=early_config_dict.get('high_vol_multiplier', 1.3)
            )
        )

        # Trailing Stop - ✅ Lire depuis TRADING_CONFIG directement
        self.trailing_stop = TrailingStopManager(
            TrailingStopConfig(
                enabled=TRADING_CONFIG.get('trailing_enabled', True),
                trigger_pnl=TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
                atr_multiplier=TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
                min_distance=TRADING_CONFIG.get('trailing_min_distance', 0.08),
                max_distance=TRADING_CONFIG.get('trailing_max_distance', 0.25)
            )
        )

        # PnL Calculator
        self.pnl_calculator = PnLCalculator()

        # Recovery Mode
        recovery_config_dict = TRADING_CONFIG.get('recovery_mode', {})
        self.recovery_mode = RecoveryModeManager(
            RecoveryModeConfig(
                enabled=recovery_config_dict.get('enabled', True),
                mode=recovery_config_dict.get('mode', 'PROGRESSIVE'),
                trigger_loss_streak=recovery_config_dict.get('trigger_loss_streak', 3),
                min_score_boost=recovery_config_dict.get('min_score_boost', 1.5),
                position_size_reduction=recovery_config_dict.get('position_size_reduction', 0.7),
                confluence_forced=recovery_config_dict.get('confluence_forced', False),
                duration_trades=recovery_config_dict.get('duration_trades', 5),
                levels=recovery_config_dict.get('levels', [])
            )
        )

        # Partial TP Manager
        self.partial_tp = PartialTPManager()

        # TP Escalier Manager
        self.tp_escalier = TPEscalierManager()

        # Analytics Logger
        self.analytics_logger = AnalyticsLogger(analytics_db)
        self.analytics_db = analytics_db

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry: float,
        size: float,
        atr: Optional[float] = None,
        atr5m: Optional[float] = None,
        confirmed_by: str = "",
        scalability_data: Optional[Dict] = None,
        condition_types: Optional[List[str]] = None
    ) -> Position:
        """
        Ouvrir une nouvelle position

        Args:
            symbol: Symbole trading
            direction: 'LONG' ou 'SHORT'
            entry: Prix d'entrée
            size: Taille position en USDT
            atr: ATR 1m (optionnel)
            atr5m: ATR 5m (optionnel)
            confirmed_by: Conditions de confirmation
            scalability_data: Données scalabilité (optionnel)
            condition_types: Types de conditions détectées

        Returns:
            Position créée
        """
        # Validation
        if not entry or entry <= 0:
            raise ValueError(f"Entry invalide: {entry}")

        if self.config.fixed_sl_pct <= 0 or self.config.fixed_tp_pct <= 0:
            raise ValueError(
                f"Config invalide: fixed_sl_pct={self.config.fixed_sl_pct}%, "
                f"fixed_tp_pct={self.config.fixed_tp_pct}%"
            )

        # ✅ Mettre à jour config TP/SL avec valeurs depuis TRADING_CONFIG (dynamique)
        from config import TRADING_CONFIG
        self.tpsl_config.win_streak = self.config.win_streak
        self.tpsl_config.loss_streak = self.config.loss_streak
        # ✅ Mettre à jour paramètres ATR depuis TRADING_CONFIG
        self.tpsl_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
        self.tpsl_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
        self.tpsl_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
        self.tpsl_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)

        # Calculer TP/SL selon le mode
        if self.config.use_atr and atr:
            sl, tp = calculate_atr_levels(
                entry=entry,
                atr=atr,
                atr5m=atr5m,
                direction=direction,
                config=self.tpsl_config
            )
        else:
            sl, tp = calculate_fixed_levels(
                entry=entry,
                direction=direction,
                config=self.tpsl_config
            )

        # Créer position
        self.active_position = Position(
            symbol=symbol,
            direction=direction,
            entry=entry,
            size=size,
            sl=sl,
            tp=tp,
            atr=atr,
            atr5m=atr5m,
            confirmed_by=confirmed_by,
            scalability_data=scalability_data,
            condition_types=condition_types or []
        )

        # ✅ Initialiser TP Escalier si mode TP_MULTI
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        levels_config = None
        if tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER':
            # Construire config niveaux depuis TRADING_CONFIG
            levels_config = []
            for level in [1, 2, 3, 4]:
                pnl = TRADING_CONFIG.get(f'escalier_level{level}_pnl', 0.2)
                size_pct = TRADING_CONFIG.get(f'escalier_level{level}_size', 25.0) / 100.0
                levels_config.append({
                    'pnl': pnl,
                    'size_pct': size_pct
                })
            
            # Initialiser TP Escalier
            self.tp_escalier.initialize_levels(
                position=self.active_position.to_dict(),
                levels_config=levels_config
            )
            # Mettre à jour position avec tp_escalier_enabled
            self.active_position.tp_escalier_enabled = True
            self.active_position.tp_escalier_levels = levels_config

        logger.info(
            f"🟢 POSITION OUVERTE: {direction} {symbol} | "
            f"Entry: {self._format_price(entry)} | "
            f"SL: {self._format_price(sl)} | TP: {self._format_price(tp)} | "
            f"Size: {size:.2f} USDT | Mode: {'ATR' if self.config.use_atr else 'FIXE'}"
            + (f" | TP Escalier: {len(levels_config)} niveaux" if levels_config else "")
        )

        return self.active_position

    def calculate_position_size(
        self,
        setup: Dict[str, Any],
        capital: float,
        base_risk: float = 0.01,
        min_risk: float = 0.005,
        max_risk: float = 0.03
    ) -> float:
        """
        Calculer taille position selon score setup et Recovery Mode

        Args:
            setup: Dictionnaire setup avec score, ATR, etc.
            capital: Capital total USDT
            base_risk: Risque de base (1%)
            min_risk: Risque minimum (0.5%)
            max_risk: Risque maximum (3%)

        Returns:
            Taille position en USDT
        """
        # ✅ Lire risk_per_trade depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        risk_per_trade = TRADING_CONFIG.get('risk_per_trade', 2.0) / 100.0  # Convertir % en décimal
        base_risk = risk_per_trade  # Utiliser risk_per_trade au lieu de base_risk par défaut
        
        score = setup.get('score', 5.0)

        # Taille de base
        base_size = capital * base_risk

        # Multiplicateur selon score (5-10 points)
        score_multipliers = {
            5.0: 1.0,
            6.0: 1.15,
            7.0: 1.3,
            8.0: 1.5,
            9.0: 1.75,
            10.0: 2.0
        }
        multiplier = score_multipliers.get(score, 1.0)

        # Multiplicateur selon streaks
        streak_mult = 1.0
        if self.config.win_streak >= 3:
            streak_mult = 1.1  # +10%
        elif self.config.loss_streak >= 2:
            streak_mult = 0.85  # -15%

        # Recovery Mode - Réduction de taille
        recovery_mult = self.recovery_mode.get_position_size_multiplier(self.config.loss_streak)
        if recovery_mult < 1.0:
            streak_mult = streak_mult * recovery_mult
            logger.debug(
                f"🔄 Recovery Mode: Taille réduite "
                f"(mult: {recovery_mult:.2f}, final: {streak_mult:.2f})"
            )

        # Calculer taille finale
        final_size = base_size * multiplier * streak_mult

        # Bornes
        min_size = capital * min_risk
        max_size = capital * max_risk
        final_size = max(min_size, min(max_size, final_size))

        logger.debug(
            f"📊 Position sizing: {setup.get('symbol', 'N/A')} | "
            f"Score={score:.1f} | Base={base_size:.0f} | "
            f"Multiplier={multiplier:.2f} | Streak={streak_mult:.2f} | "
            f"Final={final_size:.2f} USDT"
        )

        return round(final_size, 2)

    def get_recovery_level(self, loss_streak: int) -> Optional[Dict]:
        """
        Obtenir niveau recovery selon loss streak

        Args:
            loss_streak: Nombre de pertes consécutives

        Returns:
            Dict avec niveau recovery ou None
        """
        return self.recovery_mode.get_recovery_level(loss_streak)

    def _estimate_slippage(
        self,
        order_size: float,
        spread_pct: float,
        depth: float,
        balance_score: float,
        bid_vol: Optional[float] = None,
        ask_vol: Optional[float] = None
    ) -> float:
        """
        Estime le slippage réaliste pour un ordre

        Args:
            order_size: Taille de l'ordre en USDT
            spread_pct: Spread moyen en %
            depth: Profondeur totale du carnet
            balance_score: Équilibre bid/ask (0-1)
            bid_vol: Volume bid total (optionnel)
            ask_vol: Volume ask total (optionnel)

        Returns:
            Slippage estimé en %
        """
        if spread_pct <= 0 or depth <= 0:
            return 0.0

        # Imbalance factor
        imbalance_factor = 1 / balance_score if balance_score > 0 else 1.0

        # Depth factor
        if bid_vol and ask_vol:
            depth_factor = order_size / (bid_vol + ask_vol)
        else:
            depth_factor = order_size / depth if depth > 0 else 0

        # Slippage estimé
        slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)

        # Limiter à 1% maximum
        slippage_pct = min(slippage_pct, 1.0)

        return round(slippage_pct, 4)

    async def check_position(self, current_price: float) -> Optional[str]:
        """
        Vérifier position et mettre à jour selon conditions du marché

        Args:
            current_price: Prix actuel

        Returns:
            Raison de fermeture si position doit être fermée, None sinon
        """
        if not self.active_position:
            return None

        # Calculer temps écoulé et PnL
        elapsed = time.time() - self.active_position.start_time
        pnl = self.pnl_calculator.calculate_pnl_percent(
            self.active_position.entry,
            current_price,
            self.active_position.direction
        )

        # 1. Early Invalidation (10-30s)
        if self.early_invalidation.should_check(elapsed):
            invalidation = self.early_invalidation.check_invalidation(
                position=self.active_position.to_dict(),
                current_price=current_price,
                pnl_percent=pnl
            )
            if invalidation:
                return invalidation

        # 2. TP Escalier - Vérifier niveaux
        if self.active_position.tp_escalier_enabled:
            level_result = self.tp_escalier.check_and_execute_levels(
                position=self.active_position.to_dict(),
                current_price=current_price
            )
            if level_result:
                # Mettre à jour position avec résultats TP Escalier
                self.active_position.tp_escalier_current_level = self.active_position.to_dict()['tp_escalier_current_level'] + 1
                self.active_position.tp_escalier_size_remaining = self.active_position.to_dict()['tp_escalier_size_remaining'] - level_result['size_pct']
                self.active_position.tp_escalier_profits.append(level_result)
                self.active_position.partial_profit_usdt += level_result['profit_usdt']

        # 3. TP Partiel (si pas TP Escalier)
        if not self.active_position.tp_escalier_enabled:
            if self.partial_tp.check_trigger(
                position=self.active_position.to_dict(),
                current_price=current_price,
                trigger_pct=self.config.partial_tp_trigger
            ):
                partial_result = self.partial_tp.execute_partial_tp(
                    position=self.active_position.to_dict(),
                    current_price=current_price
                )
                # Mettre à jour position
                self.active_position.partial_tp_sold = True
                self.active_position.size_remaining = partial_result['size_remaining']
                self.active_position.partial_profit_usdt = partial_result['profit_usdt']

                # Déplacer SL à break-even
                new_sl = self.partial_tp.update_sl_after_partial_tp(
                    self.active_position.to_dict()
                )
                self.active_position.sl = new_sl
                self.active_position.break_even_set = True

        # 4. Trailing Stop (si PnL > trigger)
        if self.trailing_stop.should_trigger(pnl):
            new_sl = self.trailing_stop.update_trailing_stop(
                position=self.active_position.to_dict(),
                current_price=current_price,
                pnl_percent=pnl
            )
            if new_sl:
                self.active_position.sl = new_sl

        # 5. Vérifier TP/SL
        return self._check_levels(current_price)

    def _check_levels(self, current_price: float) -> Optional[str]:
        """Vérifier si TP ou SL est touché"""
        direction = self.active_position.direction
        sl = self.active_position.sl
        tp = self.active_position.tp

        # Calculer PnL
        pnl = self.pnl_calculator.calculate_pnl_percent(
            self.active_position.entry,
            current_price,
            direction
        )

        # TP Escalier - Gestion spéciale
        if self.active_position.tp_escalier_enabled:
            if self.active_position.tp_escalier_current_level >= len(self.active_position.tp_escalier_levels):
                # Tous niveaux passés, vérifier seulement SL (trailing)
                if direction == 'LONG':
                    if current_price <= sl:
                        return 'TS'
                else:
                    if current_price >= sl:
                        return 'TS'
                return None
            else:
                # Niveaux restants, vérifier seulement SL
                has_tp_escalier_profits = len(self.active_position.tp_escalier_profits) > 0
                if direction == 'LONG':
                    if current_price <= sl:
                        return 'TS' if (has_tp_escalier_profits or pnl >= 0) else 'SL'
                else:
                    if current_price >= sl:
                        return 'TS' if (has_tp_escalier_profits or pnl >= 0) else 'SL'
                return None

        # Mode standard avec TP partiel
        if self.config.use_partial_tp and self.active_position.partial_tp_sold:
            # Après TP partiel, ignorer TP final en mode FIXE
            if not self.config.use_atr:
                if direction == 'LONG':
                    if current_price <= sl:
                        return 'TS'
                else:
                    if current_price >= sl:
                        return 'TS'
                return None

        # Vérification standard TP/SL
        if direction == 'LONG':
            if current_price <= sl:
                return 'TS' if pnl >= 0 else 'SL'
            if current_price >= tp:
                return 'TP'
        else:  # SHORT
            if current_price >= sl:
                return 'TS' if pnl >= 0 else 'SL'
            if current_price <= tp:
                return 'TP'

        return None

    def close_position(self, exit_price: float, reason: str) -> Dict[str, Any]:
        """
        Fermer la position active

        Args:
            exit_price: Prix de sortie
            reason: Raison de fermeture (TP, SL, TS, EARLY_INVALIDATION, etc.)

        Returns:
            Dict avec résultats du trade
        """
        if not self.active_position:
            raise ValueError("Aucune position active à fermer")

        # ✅ FIX: Validation exit_price avec fallback multi-niveaux
        exit_price_source = "api"  # Pour tracking

        if exit_price is None or exit_price <= 0:
            logger.warning(
                f"⚠️ Exit price invalide ({exit_price}) pour {self.active_position.symbol}"
            )

            # Fallback 1: Essayer le cache de prix
            cached_price = self.get_cached_price(
                self.active_position.symbol,
                max_age_ms=30000  # 30 secondes max
            )

            if cached_price and cached_price > 0:
                exit_price = cached_price
                exit_price_source = "cache"
                logger.info(
                    f"✅ Utilisation prix en cache: {exit_price} "
                    f"(âge < 30s)"
                )
            else:
                # Fallback 2: Utiliser le prix d'entrée
                exit_price = self.active_position.entry
                exit_price_source = "entry_fallback"
                logger.warning(
                    f"⚠️ Pas de prix valide disponible, "
                    f"utilisation prix d'entrée: {exit_price}"
                )

        # Calculer durée
        duration = int(time.time() - self.active_position.start_time)

        # 🔥 FIX: Calculer PnL réalisé avec fees à 0% (scan scalabilité uniquement sur paires 0% fee)
        pnl_data = self.pnl_calculator.calculate_realized_pnl(
            position=self.active_position.to_dict(),
            exit_price=exit_price,
            fees_percent=0.0  # 🔥 FIX: 0% fees (paires scalabilité uniquement)
        )

        # Calculer slippage si applicable
        slippage = 0.0
        if self.config.use_slippage_calculation and self.active_position.scalability_data:
            slippage = self._estimate_slippage(
                order_size=self.active_position.size,
                spread_pct=self.active_position.scalability_data.get('spread_pct', 0.0),
                depth=self.active_position.scalability_data.get('depth', 0.0),
                balance_score=self.active_position.scalability_data.get('balance', 1.0),
                bid_vol=self.active_position.scalability_data.get('bid_vol'),
                ask_vol=self.active_position.scalability_data.get('ask_vol')
            )

        # Calculer coûts totaux
        total_costs = pnl_data['fees'] + slippage

        # PnL net
        net_pnl_pct = pnl_data['pnl_pct']
        net_pnl_usdt = pnl_data['net_pnl'] - slippage

        # Taille fermée
        if self.active_position.partial_tp_sold:
            size_closed = self.active_position.size_remaining or (self.active_position.size * 0.5)
        else:
            size_closed = self.active_position.size

        # Générer ID unique pour éviter doublons
        closure_id = str(uuid.uuid4())

        # Construire résultat
        # 🔥 FIX: Ajouter opened_at et closed_at pour l'affichage frontend
        opened_at = datetime.fromtimestamp(self.active_position.start_time).isoformat() if hasattr(self.active_position, 'start_time') else self.active_position.timestamp
        closed_at = datetime.now().isoformat()
        
        result = {
            'symbol': self.active_position.symbol,
            'direction': self.active_position.direction,
            'entry': self.active_position.entry,
            'exit': exit_price,
            'exit_price': exit_price,  # 🔥 FIX: Alias pour compatibilité frontend
            'pnl_pct': round(pnl_data['pnl_pct'], 2),
            'pnl_usdt': round(net_pnl_usdt, 4),
            'gross_pnl_pct': round(pnl_data['pnl_pct'], 2),
            'gross_pnl_usdt': round(pnl_data['pnl_usdt_gross'], 4),
            'fees': round(pnl_data['fees'], 4),  # 🔥 FIX: Plus de précision pour les fees (devrait être 0.0000 pour paires 0% fee)
            'slippage': round(slippage, 6),  # 🔥 FIX: Plus de précision pour le slippage (6 décimales pour éviter confusion avec fees)
            'total_costs': round(total_costs, 2),
            'total_costs_usdt': round(total_costs, 4),
            'net_pnl': round(net_pnl_pct, 2),
            'net_pnl_pct': round(net_pnl_pct, 2),  # 🔥 FIX: Alias pour compatibilité frontend
            'net_pnl_usdt': round(net_pnl_usdt, 4),
            'duration': duration,
            'reason': reason,
            'close_reason': reason,
            'timestamp': self.active_position.timestamp,
            'opened_at': opened_at,  # 🔥 FIX: Ajouté pour l'affichage frontend
            'closed_at': closed_at,  # 🔥 FIX: Ajouté pour l'affichage frontend
            'closure_id': closure_id,
            'has_partial_tp': self.active_position.partial_tp_sold,
            'size_closed': round(size_closed, 4),
            'size': self.active_position.size,
            'confirmed_by': getattr(self.active_position, 'confirmed_by', ''),  # 🔥 FIX: Ajouté pour l'affichage signals
            # ✅ FIX: Tracking source du exit_price
            'exit_price_source': exit_price_source,
            'exit_price_from_fallback': exit_price_source != "api"
        }

        # Mettre à jour streaks
        if net_pnl_pct > 0:
            self.config.win_streak += 1
            self.config.loss_streak = 0
        else:
            self.config.win_streak = 0
            self.config.loss_streak += 1

        # Recovery Mode - Mettre à jour
        self.recovery_mode.update_after_trade(is_win=net_pnl_pct > 0)
        if self.recovery_mode.active:
            self.config.recovery_mode_active = True
            self.config.recovery_mode_remaining_trades = self.recovery_mode.remaining_trades
        else:
            self.config.recovery_mode_active = False
            self.config.recovery_mode_remaining_trades = 0

        # Sauvegarder position avant de réinitialiser
        position = self.active_position

        # Logger dans Analytics DB
        self.analytics_logger.log_trade(
            position=position.to_dict(),
            exit_price=exit_price,
            reason=reason,
            pnl_data={
                'pnl_pct': pnl_data['pnl_pct'],
                'net_pnl': net_pnl_usdt,
                'fees': pnl_data['fees']
            },
            mode='LIVE'
        )

        # Réinitialiser position
        self.active_position = None

        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl_pct:.2f}% ({net_pnl_usdt:.4f} USDT)"
        )

        return result

    def update_price_cache(self, symbol: str, price: float, data: Any = None):
        """Mettre à jour le cache de prix"""
        self.price_cache[symbol] = {
            'price': price,
            'timestamp': datetime.now().timestamp() * 1000,
            'data': data
        }

    def get_cached_price(self, symbol: str, max_age_ms: int = 20000) -> Optional[float]:
        """Récupérer le prix en cache s'il est frais"""
        if symbol not in self.price_cache:
            return None

        cache = self.price_cache[symbol]
        age = datetime.now().timestamp() * 1000 - cache['timestamp']

        if age <= max_age_ms:
            return cache['price']

        return None
