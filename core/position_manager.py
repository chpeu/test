#!/usr/bin/env python3
"""
Position Manager - Trade Cursor v7.0
Gestion des positions: TP/SL, Break-even, Trailing Stop
REFACTORISÉ avec architecture modulaire
"""

import asyncio
import json
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
    
    # Price precision from API (for accurate price formatting)
    price_precision: Optional[int] = None
    tick_size: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertir position en dictionnaire JSON"""
        from datetime import datetime
        # 🔥 FIX: Convertir start_time en opened_at (ISO string) pour le frontend
        opened_at = datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None
        
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
            'opened_at': opened_at,  # 🔥 NOUVEAU: Ajouté pour le frontend (compte à rebours)
            'break_even_set': self.break_even_set,
            'partial_tp_sold': self.partial_tp_sold,
            'dynamic_sl': self.dynamic_sl,
            'size_remaining': self.size_remaining,
            'partial_profit_usdt': self.partial_profit_usdt,
            'capital': self.capital,
            'tp_escalier_enabled': self.tp_escalier_enabled,
            'tp_escalier_current_level': self.tp_escalier_current_level,
            'tp_escalier_size_remaining': self.tp_escalier_size_remaining,
            'tp_escalier_profits': self.tp_escalier_profits,
            'tp_escalier_levels': json.dumps(self.tp_escalier_levels) if hasattr(self, 'tp_escalier_levels') and self.tp_escalier_levels else None,  # 🔥 FIX: Ajouter niveaux TP escalier (JSON string)
            'current_price': getattr(self, 'current_price', None),  # 🔥 FIX: Ajouter prix actuel si disponible
            'price_precision': self.price_precision,  # 🔥 FIX: Précision prix depuis API
            'tickSize': self.tick_size  # 🔥 FIX: Tick size depuis API (alternative à price_precision)
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
        self.market_info_cache: Dict[str, Dict] = {}  # 🔥 FIX: Cache pour informations de marché (précision)

        # Initialiser modules spécialisés
        self._init_modules(analytics_db)

    def _get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        Récupérer les informations de marché (précision, tickSize) depuis l'API
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dictionnaire avec les informations de marché ou None
        """
        # Vérifier le cache d'abord
        if symbol in self.market_info_cache:
            return self.market_info_cache[symbol]
        
        try:
            from api.mexc import get_mexc_client
            import asyncio
            
            # Récupérer le client MEXC
            client = get_mexc_client()
            
            # Charger les marchés si pas déjà fait
            if not hasattr(client, '_markets_loaded'):
                # Utiliser load_markets pour obtenir toutes les infos de marché
                try:
                    # Essayer de récupérer la boucle d'événements actuelle
                    try:
                        loop = asyncio.get_running_loop()
                        # Si une boucle est en cours, créer une tâche
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                lambda: asyncio.run(client.exchange.load_markets())
                            )
                            markets = future.result(timeout=10)
                    except RuntimeError:
                        # Pas de boucle en cours, utiliser asyncio.run
                        markets = asyncio.run(client.exchange.load_markets())
                    
                    client._markets_loaded = True
                    client._markets = markets
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de charger les marchés: {e}")
                    return None
            
            # Récupérer les informations du marché pour ce symbole
            if hasattr(client, '_markets') and symbol in client._markets:
                market_info = client._markets[symbol]
                # Mettre en cache
                self.market_info_cache[symbol] = market_info
                return market_info
                    
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération market info pour {symbol}: {e}")
        
        return None

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
        # 🔥 FIX: Mettre à jour paramètres FIXE depuis TRADING_CONFIG (au lieu de self.config qui n'est pas mis à jour dynamiquement)
        self.tpsl_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
        self.tpsl_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
        # ✅ Mettre à jour paramètres ATR depuis TRADING_CONFIG
        self.tpsl_config.atr_mult_tp = TRADING_CONFIG.get('atr_mult_tp', 1.5)
        self.tpsl_config.atr_mult_sl = TRADING_CONFIG.get('atr_mult_sl', 1.0)
        self.tpsl_config.atr_min = TRADING_CONFIG.get('atr_min', 0.15)
        self.tpsl_config.atr_max = TRADING_CONFIG.get('atr_max', 1.5)
        
        # 🔥 FIX: Mettre à jour use_atr depuis TRADING_CONFIG (au lieu de self.config qui n'est pas mis à jour dynamiquement)
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        # 🔥 FIX: Accepter aussi 'ESCALIER' comme mode valide (identique à TP_MULTI)
        use_atr = (tp_sl_mode == 'ATR' or tp_sl_mode == 'TP_MULTI' or tp_sl_mode == 'ESCALIER')

        # Calculer TP/SL selon le mode
        if use_atr and atr:
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

        # 🔥 FIX: Récupérer la précision depuis l'API pour formater correctement les prix
        price_precision = None
        tick_size = None
        try:
            market_info = self._get_market_info(symbol)
            if market_info:
                # Essayer de récupérer pricePrecision (nombre de décimales)
                price_precision = market_info.get('precision', {}).get('price')
                if price_precision is None:
                    # Essayer de récupérer depuis info
                    price_precision = market_info.get('info', {}).get('pricePrecision')
                
                # Essayer de récupérer tickSize
                tick_size = market_info.get('precision', {}).get('amount')
                if tick_size is None:
                    tick_size = market_info.get('info', {}).get('tickSize')
                if tick_size is None:
                    # Calculer depuis pricePrecision si disponible
                    if price_precision is not None:
                        tick_size = 10 ** (-price_precision)
        except Exception as e:
            logger.warning(f"⚠️ Impossible de récupérer la précision pour {symbol}: {e}")

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
            condition_types=condition_types or [],
            price_precision=price_precision,
            tick_size=tick_size
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

        # ========================================
        # ✅ POINT C : CAPTURE INDICATEURS D'ENTRÉE (pour PostgreSQL)
        # ========================================
        # 🔥 FIX: Capturer les indicateurs TOUJOURS, pas seulement si data_logger.is_running
        # Récupérer scan_uuid, opportunity_id et setup depuis les attributs stockés
        scan_uuid = getattr(self, '_last_setup_scan_uuid', None)
        opportunity_id = getattr(self, '_last_setup_opportunity_id', None)
        last_setup = getattr(self, '_last_setup', None)
        
        # 🔥 DEBUG: Log pour vérifier si _last_setup est disponible
        if not last_setup:
            logger.warning(f"⚠️ _last_setup est None pour {symbol} - les indicateurs d'entrée ne seront pas disponibles")
        else:
            logger.info(f"✅ _last_setup disponible pour {symbol}, keys: {list(last_setup.keys())[:10]}")
            if 'indicators_1m' not in last_setup and 'indicators_5m' not in last_setup:
                logger.warning(f"⚠️ _last_setup ne contient pas 'indicators_1m' ou 'indicators_5m' pour {symbol}")
        
        # Préparer entry_indicators (snapshot au moment de l'entrée)
        # Récupérer depuis setup si disponible
        indicators_1m = last_setup.get('indicators_1m', {}) if last_setup else {}
        indicators_5m = last_setup.get('indicators_5m', {}) if last_setup else {}
        
        # 🔥 DEBUG: Log pour vérifier le contenu des indicateurs
        if indicators_1m or indicators_5m:
            indicators_1m_non_null = len([v for v in indicators_1m.values() if v is not None]) if indicators_1m else 0
            indicators_5m_non_null = len([v for v in indicators_5m.values() if v is not None]) if indicators_5m else 0
            logger.info(f"✅ Indicateurs trouvés: indicators_1m keys: {list(indicators_1m.keys())[:5]}, indicators_5m keys: {list(indicators_5m.keys())[:5]}")
            logger.info(f"✅ Indicateurs non-null: indicators_1m: {indicators_1m_non_null}/{len(indicators_1m) if indicators_1m else 0}, indicators_5m: {indicators_5m_non_null}/{len(indicators_5m) if indicators_5m else 0}")
            # 🔥 DEBUG: Vérifier les valeurs spécifiques
            if indicators_1m:
                logger.info(f"🔍 DEBUG indicators_1m valeurs: rsi={indicators_1m.get('rsi')}, macd_hist={indicators_1m.get('macd_hist')}, adx={indicators_1m.get('adx')}, ema9={indicators_1m.get('ema9')}, ema21={indicators_1m.get('ema21')}")
        else:
            logger.warning(f"⚠️ Aucun indicateur trouvé dans indicators_1m ou indicators_5m pour {symbol}")
        
        # 🔥 DEBUG: Vérifier si last_setup contient directement les indicateurs (fallback)
        if last_setup:
            logger.info(f"🔍 DEBUG last_setup contient directement: rsi={last_setup.get('rsi')}, macd={last_setup.get('macd')}, adx={last_setup.get('adx')}, ema9={last_setup.get('ema9')}, ema21={last_setup.get('ema21')}")
        
        # 🔥 FIX: Utiliser last_setup comme fallback pour tous les indicateurs manquants
        # Helper function pour obtenir une valeur avec fallback
        def get_indicator(key_1m=None, key_5m=None, key_setup=None, default=None):
            """Récupère un indicateur depuis indicators_1m, indicators_5m ou last_setup"""
            if key_1m and indicators_1m and indicators_1m.get(key_1m) is not None:
                return indicators_1m.get(key_1m)
            if key_5m and indicators_5m and indicators_5m.get(key_5m) is not None:
                return indicators_5m.get(key_5m)
            if key_setup and last_setup and last_setup.get(key_setup) is not None:
                return last_setup.get(key_setup)
            return default
        
        entry_indicators = {
                    # RSI
                    'rsi_1m': get_indicator('rsi', None, 'rsi'),
                    'rsi_5m': get_indicator(None, 'rsi', None),
                    'rsi_prev_1m': get_indicator('rsi_prev', None, 'rsi_prev'),
                    'rsi_prev_5m': get_indicator(None, 'rsi_prev', None),
                    # MACD
                    'macd_1m': get_indicator('macd', None, 'macd'),
                    'macd_signal_1m': get_indicator('macd_signal', None, 'macd_signal'),
                    'macd_hist_1m': get_indicator('macd_hist', None, 'macd_hist'),
                    'macd_hist_prev_1m': get_indicator('macd_hist_prev', None, 'macd_hist_prev'),
                    'macd_5m': get_indicator(None, 'macd', None),
                    'macd_signal_5m': get_indicator(None, 'macd_signal', None),
                    'macd_hist_5m': get_indicator(None, 'macd_hist', None),
                    'macd_hist_prev_5m': get_indicator(None, 'macd_hist_prev', None),
                    # ADX
                    'adx_1m': get_indicator('adx', None, 'adx'),
                    'adx_5m': get_indicator(None, 'adx', None),
                    'di_plus_1m': get_indicator('di_plus', None, 'di_plus'),
                    'di_minus_1m': get_indicator('di_minus', None, 'di_minus'),
                    'di_gap_1m': get_indicator('di_gap', None, 'di_gap'),
                    'di_plus_5m': get_indicator(None, 'di_plus', None),
                    'di_minus_5m': get_indicator(None, 'di_minus', None),
                    'di_gap_5m': get_indicator(None, 'di_gap', None),
                    # EMA
                    'ema9_1m': get_indicator('ema9', None, 'ema9'),
                    'ema21_1m': get_indicator('ema21', None, 'ema21'),
                    'ema_diff_pct_1m': get_indicator('ema_diff_pct', None, 'ema_diff_pct'),
                    'ema9_5m': get_indicator(None, 'ema9', None),
                    'ema21_5m': get_indicator(None, 'ema21', None),
                    'ema_diff_pct_5m': get_indicator(None, 'ema_diff_pct', None),
                    # ATR
                    'atr_1m': get_indicator('atr', None, 'atr'),
                    'atr_pct_1m': (atr / entry * 100) if atr and entry else get_indicator('atr_pct', None, 'atr_pct'),
                    'atr_5m': get_indicator(None, 'atr', None),
                    'atr_pct_5m': (atr5m / entry * 100) if atr5m and entry else get_indicator(None, 'atr_pct', None),
                    # Bollinger Bands
                    'bb_upper_1m': get_indicator('bb_upper', None, 'bb_upper'),
                    'bb_middle_1m': get_indicator('bb_middle', None, 'bb_middle'),
                    'bb_lower_1m': get_indicator('bb_lower', None, 'bb_lower'),
                    'bb_width_1m': get_indicator('bb_width', None, 'bb_width'),
                    'bb_distance_to_lower_1m': get_indicator('bb_distance_to_lower', None, 'bb_distance_to_lower'),
                    'bb_distance_to_upper_1m': get_indicator('bb_distance_to_upper', None, 'bb_distance_to_upper'),
                    'bb_upper_5m': get_indicator(None, 'bb_upper', None),
                    'bb_middle_5m': get_indicator(None, 'bb_middle', None),
                    'bb_lower_5m': get_indicator(None, 'bb_lower', None),
                    'bb_width_5m': get_indicator(None, 'bb_width', None),
                    'bb_distance_to_lower_5m': get_indicator(None, 'bb_distance_to_lower', None),
                    'bb_distance_to_upper_5m': get_indicator(None, 'bb_distance_to_upper', None),
                    # Volume
                    'volume_1m': get_indicator('volume', None, 'volume'),
                    'volume_avg_1m': get_indicator('volume_avg', None, 'volume_avg'),
                    'volume_ratio_1m': get_indicator('volume_ratio', None, 'volumeSpike'),
                    'volume_spike_1m': get_indicator('volume_spike', None, 'volumeSpike'),
                    'volume_5m': get_indicator(None, 'volume', None),
                    'volume_avg_5m': get_indicator(None, 'volume_avg', None),
                    'volume_ratio_5m': get_indicator(None, 'volume_ratio', None),
                    'volume_spike_5m': get_indicator(None, 'volume_spike', None),
                    # Score
                    'score': last_setup.get('totalScore') if last_setup else None,
                }
                
        # Conditions matched
        entry_conditions = condition_types or []
        
        # Scalability au moment de l'entrée
        entry_scalability = scalability_data or {}
        
        # 🔥 FIX: TOUJOURS stocker les indicateurs dans la position (pour PostgreSQL)
        self.active_position._scan_log_id = scan_uuid
        self.active_position._entry_indicators = entry_indicators
        self.active_position._entry_conditions = entry_conditions
        self.active_position._entry_scalability = entry_scalability
        
        # 🔥 DEBUG: Compter les indicateurs récupérés
        entry_indicators_non_null = len([v for v in entry_indicators.values() if v is not None])
        logger.info(f"✅ Indicateurs d'entrée stockés pour {symbol}: {entry_indicators_non_null}/{len(entry_indicators)} indicateurs non-null")
        
        # 🔥 DEBUG: Log quelques indicateurs clés pour vérification
        if entry_indicators_non_null > 0:
            logger.info(f"🔍 DEBUG entry_indicators exemples: rsi_1m={entry_indicators.get('rsi_1m')}, macd_hist_1m={entry_indicators.get('macd_hist_1m')}, adx_1m={entry_indicators.get('adx_1m')}, ema9_1m={entry_indicators.get('ema9_1m')}, ema21_1m={entry_indicators.get('ema21_1m')}")
        
        # ========================================
        # ✅ LOG TRADE ENTRY (backend.ml.data_logger - optionnel)
        # ========================================
        try:
            from backend.ml.data_logger import DataLogger
            data_logger = DataLogger()
            
            if data_logger and data_logger.is_running:
                # Logger l'entrée (non-blocking avec create_task)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Créer une task non-bloquante
                        async def log_entry():
                            trade_id = await data_logger.log_trade_entry(
                                opportunity_id=opportunity_id,
                                scan_log_id=scan_uuid,
                                symbol=symbol,
                                direction=direction,
                                entry_price=entry,
                                size_usdt=size,
                                tp_price=tp,
                                sl_price=sl,
                                tp_sl_mode=TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                                entry_indicators=entry_indicators,
                                entry_conditions=entry_conditions,
                                entry_scalability=entry_scalability
                            )
                            # Stocker trade_id dans position
                            if trade_id:
                                self.active_position._trade_id = trade_id
                        loop.create_task(log_entry())
                    else:
                        # Pas de loop, créer un nouveau
                        trade_id = loop.run_until_complete(data_logger.log_trade_entry(
                            opportunity_id=opportunity_id,
                            scan_log_id=scan_uuid,
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry,
                            size_usdt=size,
                            tp_price=tp,
                            sl_price=sl,
                            tp_sl_mode=TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                            entry_indicators=entry_indicators,
                            entry_conditions=entry_conditions,
                            entry_scalability=entry_scalability
                        ))
                        # Stocker trade_id dans position
                        if trade_id:
                            self.active_position._trade_id = trade_id
                except RuntimeError:
                    # Pas de loop disponible, ignorer
                    pass
        except Exception as e:
            logger.debug(f"Erreur log_trade_entry (non-bloquant): {e}")
        # ========================================
        # FIN POINT C
        # ========================================

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
        # 🔥 INFO: Log pour vérifier les paramètres (changer de debug à info pour visibilité)
        logger.info(f"💹 _estimate_slippage: order_size={order_size}, spread_pct={spread_pct}, depth={depth}, balance_score={balance_score}")
        
        if spread_pct <= 0 or depth <= 0:
            logger.warning(f"💹 _estimate_slippage: Retourne 0.0 car spread_pct={spread_pct} ou depth={depth} <= 0")
            return 0.0

        # Imbalance factor
        imbalance_factor = 1 / balance_score if balance_score > 0 else 1.0

        # 🔥 FIX BUG #2: Depth factor - Vérifier que bid_vol et ask_vol ne sont pas None (pas juste truthy)
        # Car bid_vol=0 est falsy mais valide
        if bid_vol is not None and ask_vol is not None:
            total_vol = bid_vol + ask_vol
            depth_factor = order_size / total_vol if total_vol > 0 else 0
        else:
            depth_factor = order_size / depth if depth > 0 else 0

        # Slippage estimé
        slippage_pct = spread_pct * (1 + depth_factor * imbalance_factor)

        # Limiter à 1% maximum
        slippage_pct = min(slippage_pct, 1.0)

        # 🔥 FIX: Retourner en % (pas en décimales) pour cohérence avec l'affichage
        return round(slippage_pct, 2)  # Déjà en %, pas besoin de multiplier

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

        # 🔥 FIX: Importer TRADING_CONFIG pour lecture dynamique
        from config import TRADING_CONFIG

        # Calculer temps écoulé et PnL
        elapsed = time.time() - self.active_position.start_time
        pnl = self.pnl_calculator.calculate_pnl_percent(
            self.active_position.entry,
            current_price,
            self.active_position.direction
        )

        # 1. Early Invalidation (10-30s)
        early_invalidation_data = None
        if self.early_invalidation.should_check(elapsed):
            invalidation = self.early_invalidation.check_invalidation(
                position=self.active_position.to_dict(),
                current_price=current_price,
                pnl_percent=pnl
            )
            if invalidation:
                # Stocker les détails de l'invalidation pour le logging
                entry = self.active_position.entry
                atr = self.active_position.atr
                atr_pct = (atr / entry * 100) if entry > 0 and atr > 0 else None
                # Calculer le seuil adaptatif utilisé
                invalidation_threshold = self.early_invalidation.get_adaptive_threshold(
                    elapsed, atr_pct or 0.5
                )
                early_invalidation_data = {
                    'triggered': True,
                    'triggered_at': datetime.now().isoformat(),
                    'threshold': invalidation_threshold,
                    'elapsed': elapsed,
                    'atr_pct': atr_pct,
                    'pnl_pct': pnl
                }
                # Stocker dans la position pour le logging
                self.active_position._early_invalidation_data = early_invalidation_data
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

        # 3. TP Partiel (si pas TP Escalier) - utiliser break_even_trigger comme seuil du 1er TP
        if not self.active_position.tp_escalier_enabled:
            # 🔥 FIX: En mode FIXE, utiliser break_even_trigger comme seuil du 1er TP partiel
            # break_even_trigger détermine le % de profit pour déclencher le 1er TP
            break_even_trigger = TRADING_CONFIG.get('break_even_trigger', 0.3)
            if self.partial_tp.check_trigger(
                position=self.active_position.to_dict(),
                current_price=current_price,
                trigger_pct=break_even_trigger  # Utiliser break_even_trigger au lieu de partial_tp_trigger
            ):
                partial_result = self.partial_tp.execute_partial_tp(
                    position=self.active_position.to_dict(),
                    current_price=current_price
                )
                # Mettre à jour position
                self.active_position.partial_tp_sold = True
                self.active_position.size_remaining = partial_result['size_remaining']
                self.active_position.partial_profit_usdt = partial_result['profit_usdt']

                # Déplacer SL à break-even après le 1er TP
                new_sl = self.partial_tp.update_sl_after_partial_tp(
                    self.active_position.to_dict()
                )
                self.active_position.sl = new_sl
                self.active_position.break_even_set = True
                
                logger.info(
                    f"💰 1er TP partiel déclenché à {break_even_trigger:.2f}% | "
                    f"Break-even activé | Trailing stop activé"
                )

        # 4. Trailing Stop (activé après le 1er TP partiel ou si PnL > break_even_trigger)
        # 🔥 FIX: Le trailing stop est activé après le 1er TP (déclenché par break_even_trigger)
        # Le trailing stop commence à fonctionner une fois que le PnL dépasse break_even_trigger
        if self.active_position.partial_tp_sold or pnl >= TRADING_CONFIG.get('break_even_trigger', 0.3):
            if self.trailing_stop.should_trigger(pnl):
                # 🔥 FIX: En mode FIXE, utiliser trailing_distance directement depuis TRADING_CONFIG
                tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                if tp_sl_mode == 'FIXE':
                    # Mode FIXE : utiliser trailing_distance directement
                    trailing_distance = TRADING_CONFIG.get('trailing_distance', 0.15)
                    new_sl = self._update_trailing_stop_fixe(
                        current_price=current_price,
                        trailing_distance=trailing_distance
                    )
                    if new_sl:
                        self.active_position.sl = new_sl
                        self.active_position.dynamic_sl = new_sl
                else:
                    # Mode ATR : utiliser distance adaptative
                    new_sl = self.trailing_stop.update_trailing_stop(
                        position=self.active_position.to_dict(),
                        current_price=current_price,
                        pnl_percent=pnl
                    )
                    if new_sl:
                        self.active_position.sl = new_sl
                        self.active_position.dynamic_sl = new_sl

        # 6. Vérifier TP/SL
        return self._check_levels(current_price)

    def _update_trailing_stop_fixe(
        self,
        current_price: float,
        trailing_distance: float
    ) -> Optional[float]:
        """
        Mettre à jour trailing stop en mode FIXE avec distance fixe

        Args:
            current_price: Prix actuel
            trailing_distance: Distance trailing en % (depuis TRADING_CONFIG)

        Returns:
            Nouveau SL si mis à jour, None sinon
        """
        if not self.active_position:
            return None

        direction = self.active_position.direction
        current_sl = self.active_position.sl

        if direction == 'LONG':
            new_sl = current_price * (1 - trailing_distance / 100)
            # Monter SL uniquement (jamais descendre)
            if new_sl > current_sl:
                new_sl = round(new_sl, 8)
                logger.info(
                    f"🔄 Trailing SL LONG {self.active_position.symbol} (FIXE): "
                    f"{current_sl:.8f} → {new_sl:.8f} (-{trailing_distance:.2f}%)"
                )
                return new_sl
        else:  # SHORT
            new_sl = current_price * (1 + trailing_distance / 100)
            # Descendre SL uniquement (jamais monter)
            if new_sl < current_sl:
                new_sl = round(new_sl, 8)
                logger.info(
                    f"🔄 Trailing SL SHORT {self.active_position.symbol} (FIXE): "
                    f"{current_sl:.8f} → {new_sl:.8f} (+{trailing_distance:.2f}%)"
                )
                return new_sl

        return None

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
        # 🔥 FIX: _estimate_slippage retourne un pourcentage (%)
        slippage_pct = 0.0
        # 🔥 INFO: Log pour vérifier les conditions (changer de debug à info pour visibilité)
        logger.info(f"💹 Calcul slippage: use_slippage_calculation={self.config.use_slippage_calculation}, "
                   f"scalability_data={'présent' if self.active_position.scalability_data else 'absent'}")
        
        if self.config.use_slippage_calculation and self.active_position.scalability_data:
            spread_pct = self.active_position.scalability_data.get('spread_pct', 0.0)
            depth = self.active_position.scalability_data.get('depth', 0.0)
            balance = self.active_position.scalability_data.get('balance', 1.0)
            
            logger.info(f"💹 Données scalabilité: spread_pct={spread_pct}, depth={depth}, balance={balance}, size={self.active_position.size}")
            
            slippage_pct = self._estimate_slippage(
                order_size=self.active_position.size,
                spread_pct=spread_pct,
                depth=depth,
                balance_score=balance,
                bid_vol=self.active_position.scalability_data.get('bid_vol'),
                ask_vol=self.active_position.scalability_data.get('ask_vol')
            )
            logger.info(f"💹 Slippage calculé: {slippage_pct}%")
        else:
            if not self.config.use_slippage_calculation:
                logger.warning("💹 Slippage non calculé: use_slippage_calculation est False")
            if not self.active_position.scalability_data:
                logger.warning("💹 Slippage non calculé: scalability_data est absent")
        
        # 🔥 FIX: Convertir slippage_pct en USDT pour les calculs
        slippage_usdt = (slippage_pct / 100) * self.active_position.size if self.active_position.size > 0 else 0.0

        # Calculer coûts totaux (fees en USDT + slippage en USDT)
        total_costs = pnl_data['fees'] + slippage_usdt

        # PnL net
        # 🔥 FIX: Calculer net_pnl_pct en tenant compte des coûts (fees + slippage)
        # Le PnL net en % doit être ajusté pour refléter les coûts réels
        gross_pnl_pct = pnl_data['pnl_pct']
        total_costs_pct = (total_costs / self.active_position.size) * 100 if self.active_position.size > 0 else 0
        net_pnl_pct = gross_pnl_pct - total_costs_pct
        
        # 🔥 FIX: net_pnl_usdt doit être calculé après déduction du slippage USDT
        net_pnl_usdt = pnl_data['net_pnl'] - slippage_usdt

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
            'slippage': round(slippage_pct, 4),  # 🔥 FIX: Slippage en pourcentage
            'slippage_pct': round(slippage_pct, 4),  # Alias
            'slippage_usdt': round(slippage_usdt, 4),  # 🔥 FIX: Slippage en USDT
            'gross_pnl_usdt': round(pnl_data['pnl_usdt_gross'], 4),
            'fees': round(pnl_data['fees'], 4),  # 🔥 FIX: Plus de précision pour les fees (devrait être 0.0000 pour paires 0% fee)
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

        # ========================================
        # ✅ POINT D : LOG TRADE EXIT
        # ========================================
        
        # 🔥 PHASE 2: Logger dans PostgreSQL si activé
        try:
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            if pg_datalogger and pg_datalogger.enabled:
                try:
                    # Préparer les données du trade pour PostgreSQL
                    # Récupérer pnl_history pour métriques de position
                    pnl_history = []
                    if hasattr(self.active_position, 'pnl_history') and self.active_position.pnl_history:
                        pnl_history = self.active_position.pnl_history
                    
                    # Récupérer entry_indicators, entry_conditions, entry_scalability
                    entry_indicators = getattr(self.active_position, '_entry_indicators', {})
                    entry_conditions = getattr(self.active_position, '_entry_conditions', [])
                    entry_scalability = getattr(self.active_position, '_entry_scalability', {})
                    
                    # 🔥 FIX: Si entry_indicators est vide, essayer de récupérer depuis scan_log_id
                    if not entry_indicators or all(v is None for v in entry_indicators.values()):
                        scan_log_id = getattr(self.active_position, '_scan_log_id', None)
                        if scan_log_id:
                            logger.warning(f"⚠️ entry_indicators vide pour {self.active_position.symbol}, tentative de récupération depuis scan_log_id={scan_log_id}")
                            # Essayer de récupérer depuis PostgreSQL si disponible
                            try:
                                from core.callbacks.scanner_loop import get_pg_datalogger
                                pg_datalogger = get_pg_datalogger()
                                if pg_datalogger and pg_datalogger.enabled:
                                    # Récupérer les indicateurs depuis scan_logs (colonnes individuelles, pas JSONB)
                                    query = """
                                        SELECT 
                                            rsi_1m, rsi_5m, rsi_prev_1m, rsi_prev_5m,
                                            macd_1m, macd_signal_1m, macd_hist_1m, macd_hist_prev_1m,
                                            macd_5m, macd_signal_5m, macd_hist_5m, macd_hist_prev_5m,
                                            adx_1m, adx_5m,
                                            di_plus_1m, di_minus_1m, di_gap_1m,
                                            di_plus_5m, di_minus_5m, di_gap_5m,
                                            ema9_1m, ema21_1m, ema_diff_pct_1m,
                                            ema9_5m, ema21_5m, ema_diff_pct_5m,
                                            atr_1m, atr_pct_1m, atr_5m, atr_pct_5m,
                                            bb_upper_1m, bb_middle_1m, bb_lower_1m,
                                            bb_width_1m, bb_distance_to_lower_1m, bb_distance_to_upper_1m,
                                            bb_upper_5m, bb_middle_5m, bb_lower_5m,
                                            bb_width_5m, bb_distance_to_lower_5m, bb_distance_to_upper_5m,
                                            volume_1m, volume_avg_1m, volume_ratio_1m, volume_spike_1m,
                                            volume_5m, volume_avg_5m, volume_ratio_5m, volume_spike_5m,
                                            score_total
                                        FROM scan_logs
                                        WHERE id = %s
                                        LIMIT 1
                                    """
                                    result = pg_datalogger._execute_query(query, (scan_log_id,), fetch=True)
                                    if result and result[0]:
                                        row = result[0]
                                        # Reconstruire entry_indicators depuis les colonnes individuelles
                                        entry_indicators = {
                                            'rsi_1m': row[0], 'rsi_5m': row[1], 'rsi_prev_1m': row[2], 'rsi_prev_5m': row[3],
                                            'macd_1m': row[4], 'macd_signal_1m': row[5], 'macd_hist_1m': row[6], 'macd_hist_prev_1m': row[7],
                                            'macd_5m': row[8], 'macd_signal_5m': row[9], 'macd_hist_5m': row[10], 'macd_hist_prev_5m': row[11],
                                            'adx_1m': row[12], 'adx_5m': row[13],
                                            'di_plus_1m': row[14], 'di_minus_1m': row[15], 'di_gap_1m': row[16],
                                            'di_plus_5m': row[17], 'di_minus_5m': row[18], 'di_gap_5m': row[19],
                                            'ema9_1m': row[20], 'ema21_1m': row[21], 'ema_diff_pct_1m': row[22],
                                            'ema9_5m': row[23], 'ema21_5m': row[24], 'ema_diff_pct_5m': row[25],
                                            'atr_1m': row[26], 'atr_pct_1m': row[27], 'atr_5m': row[28], 'atr_pct_5m': row[29],
                                            'bb_upper_1m': row[30], 'bb_middle_1m': row[31], 'bb_lower_1m': row[32],
                                            'bb_width_1m': row[33], 'bb_distance_to_lower_1m': row[34], 'bb_distance_to_upper_1m': row[35],
                                            'bb_upper_5m': row[36], 'bb_middle_5m': row[37], 'bb_lower_5m': row[38],
                                            'bb_width_5m': row[39], 'bb_distance_to_lower_5m': row[40], 'bb_distance_to_upper_5m': row[41],
                                            'volume_1m': row[42], 'volume_avg_1m': row[43], 'volume_ratio_1m': row[44], 'volume_spike_1m': row[45],
                                            'volume_5m': row[46], 'volume_avg_5m': row[47], 'volume_ratio_5m': row[48], 'volume_spike_5m': row[49],
                                            'score': row[50] if len(row) > 50 else None,
                                        }
                                        logger.info(f"✅ Indicateurs récupérés depuis PostgreSQL pour {self.active_position.symbol}")
                            except Exception as e:
                                logger.debug(f"Erreur récupération indicateurs depuis PostgreSQL: {e}")
                    
                    # Récupérer timestamps
                    from config import TRADING_CONFIG
                    timestamp_entry = None
                    if hasattr(self.active_position, 'start_time'):
                        timestamp_entry = datetime.fromtimestamp(self.active_position.start_time).isoformat()
                    elif hasattr(self.active_position, 'timestamp'):
                        timestamp_entry = self.active_position.timestamp
                    else:
                        timestamp_entry = datetime.now().isoformat()
                    
                    timestamp_exit = datetime.now().isoformat()
                    
                    # Préparer config_snapshot complet (toutes les variables de configuration)
                    from config import (
                        TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS,
                        TREND_BONUS_CONFIG, RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG,
                        WEBSOCKET_CONFIG
                    )
                    config_snapshot = {}
                    # Copier TRADING_CONFIG
                    if TRADING_CONFIG:
                        config_snapshot.update(TRADING_CONFIG.copy())
                    # Ajouter les variables définies séparément (elles ne sont pas dans TRADING_CONFIG)
                    config_snapshot['RISK_CONFIG'] = RISK_CONFIG
                    config_snapshot['CONDITION_WEIGHTS'] = CONDITION_WEIGHTS
                    config_snapshot['TREND_BONUS_CONFIG'] = TREND_BONUS_CONFIG
                    config_snapshot['RETRY_CONFIG'] = RETRY_CONFIG
                    config_snapshot['CIRCUIT_BREAKER_CONFIG'] = CIRCUIT_BREAKER_CONFIG
                    config_snapshot['WEBSOCKET_CONFIG'] = WEBSOCKET_CONFIG
                    
                    # Préparer indicateurs de sortie (vide pour l'instant, sera rempli plus tard si nécessaire)
                    # TODO: Faire un scan rapide au moment de la fermeture pour récupérer les indicateurs de sortie
                    exit_indicators = {}
                    
                    trade_data = {
                        'symbol': self.active_position.symbol,
                        'direction': self.active_position.direction,
                        'entry_price': self.active_position.entry,
                        'exit_price': exit_price,
                        'tp_price': self.active_position.tp,
                        'sl_price': self.active_position.sl,
                        'size_usdt': self.active_position.size,
                        'timestamp_entry': timestamp_entry,
                        'timestamp_exit': timestamp_exit,
                        'gross_pnl_usdt': result['gross_pnl_usdt'],
                        'gross_pnl_pct': result['gross_pnl_pct'],
                        'net_pnl_usdt': result['net_pnl_usdt'],
                        'net_pnl_pct': result['net_pnl_pct'],
                        'fees': result['fees'],
                        'slippage': result['slippage_pct'],
                        'total_costs': result['total_costs'],
                        'reason': reason,
                        'duration_seconds': duration,
                        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                        'break_even_triggered': self.active_position.break_even_set,
                        'trailing_stop_triggered': (reason == 'TS'),
                        'partial_tp_triggered': self.active_position.partial_tp_sold,
                        # Early Invalidation
                        'early_invalidation_triggered': (reason == 'EARLY_INVALIDATION'),
                        'early_invalidation_triggered_at': getattr(self.active_position, '_early_invalidation_data', {}).get('triggered_at') if reason == 'EARLY_INVALIDATION' else None,
                        'early_invalidation_threshold': getattr(self.active_position, '_early_invalidation_data', {}).get('threshold') if reason == 'EARLY_INVALIDATION' else None,
                        'early_invalidation_elapsed': getattr(self.active_position, '_early_invalidation_data', {}).get('elapsed') if reason == 'EARLY_INVALIDATION' else None,
                        'early_invalidation_atr_pct': getattr(self.active_position, '_early_invalidation_data', {}).get('atr_pct') if reason == 'EARLY_INVALIDATION' else None,
                        'early_invalidation_pnl_pct': getattr(self.active_position, '_early_invalidation_data', {}).get('pnl_pct') if reason == 'EARLY_INVALIDATION' else None,
                        'tp_escalier_enabled': self.active_position.tp_escalier_enabled,
                        'tp_escalier_levels_hit': [
                            {'level': i+1, 'profit': p.get('profit', 0)}
                            for i, p in enumerate(self.active_position.tp_escalier_profits)
                        ] if hasattr(self.active_position, 'tp_escalier_profits') and self.active_position.tp_escalier_profits else [],
                        'max_pnl_reached': max([p.get('pnl_pct', 0) for p in pnl_history], default=None) if pnl_history else None,
                        'min_pnl_reached': min([p.get('pnl_pct', 0) for p in pnl_history], default=None) if pnl_history else None,
                        'pnl_history': pnl_history,  # Pour calculer max_favorable_excursion
                        'entry_indicators': entry_indicators,
                        'entry_conditions': entry_conditions,
                        'entry_scalability': entry_scalability,
                        'exit_indicators': exit_indicators,  # Vide pour l'instant, sera rempli plus tard
                        'config_snapshot': config_snapshot,  # Toutes les variables de configuration
                        'is_backtest': False
                    }
                    
                    # Récupérer opportunity_id et scan_log_id si disponibles
                    opportunity_id = getattr(self.active_position, '_opportunity_id', None)
                    scan_log_id = getattr(self.active_position, '_scan_log_id', None)
                    
                    # Logger le trade
                    trade_id = pg_datalogger.log_trade(
                        trade_data=trade_data,
                        opportunity_id=opportunity_id,
                        scan_log_id=scan_log_id,
                        session_id=getattr(self, 'session_id', None)
                    )
                    
                    if trade_id:
                        logger.debug(f"📊 Trade loggé dans PostgreSQL: {self.active_position.symbol} (ID: {trade_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Erreur logging PostgreSQL trade: {e}")
        except Exception as e:
            logger.debug(f"Erreur initialisation PostgreSQL datalogger (non-bloquant): {e}")
        
        # Logging existant (backend.ml.data_logger)
        try:
            from backend.ml.data_logger import DataLogger
            data_logger = DataLogger()
            
            if data_logger and data_logger.is_running:
                trade_id = getattr(self.active_position, '_trade_id', None)
                
                if trade_id:
                    # Logger la sortie (non-blocking avec create_task)
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Créer une task non-bloquante
                            async def log_exit():
                                await data_logger.log_trade_exit(
                                    trade_id=trade_id,
                                    exit_price=exit_price,
                                    exit_reason=reason,
                                    duration_seconds=float(duration),
                                    pnl_pct=result['pnl_pct'],
                                    pnl_usdt=result['pnl_usdt'],
                                    gross_pnl_usdt=result['gross_pnl_usdt'],
                                    slippage_pct=result['slippage_pct'],
                                    slippage_usdt=result['slippage_usdt'],
                                    fees_usdt=result['fees'],
                                    net_pnl_usdt=result['net_pnl_usdt'],
                                    net_pnl_pct=result['net_pnl_pct'],
                                    win=net_pnl_pct > 0,
                                    break_even_set=self.active_position.break_even_set,
                                    partial_tp_executed=self.active_position.partial_tp_sold,
                                    partial_tp_profit=self.active_position.partial_profit_usdt if self.active_position.partial_tp_sold else None,
                                    partial_tp_percent=0.5 if self.active_position.partial_tp_sold else None,
                                    tp_escalier_levels_executed=len(self.active_position.tp_escalier_profits) if hasattr(self.active_position, 'tp_escalier_profits') and self.active_position.tp_escalier_profits else 0,
                                    tp_escalier_profits=sum(p.get('profit', 0) for p in self.active_position.tp_escalier_profits) if hasattr(self.active_position, 'tp_escalier_profits') and self.active_position.tp_escalier_profits else 0,
                                    trailing_stop_activated=(reason == 'TS'),
                                    max_favorable_excursion=None,
                                    max_adverse_excursion=None
                                )
                            loop.create_task(log_exit())
                        else:
                            # Pas de loop, créer un nouveau (ne devrait pas arriver car close_position est appelé depuis un contexte async)
                            # On ignore silencieusement car c'est un cas rare
                            pass
                    except RuntimeError:
                        # Pas de loop disponible, ignorer
                        pass
        except Exception as e:
            logger.debug(f"Erreur log_trade_exit (non-bloquant): {e}")
        # ========================================
        # FIN POINT D
        # ========================================

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
        # 🔥 DEBUG: Log pour vérifier les valeurs avant enregistrement
        logger.debug(f"💾 Enregistrement trade: net_pnl_pct={net_pnl_pct:.4f}%, net_pnl_usdt={net_pnl_usdt:.4f} USDT, slippage_pct={slippage_pct:.4f}%")
        
        self.analytics_logger.log_trade(
            position=position.to_dict(),
            exit_price=exit_price,
            reason=reason,
            pnl_data={
                'pnl_pct': pnl_data['pnl_pct'],
                'net_pnl': net_pnl_usdt,  # 🔥 FIX: net_pnl doit être en USDT
                'net_pnl_pct': net_pnl_pct,  # 🔥 FIX: net_pnl_pct en pourcentage (après déduction des coûts)
                'fees': pnl_data['fees'],
                'slippage': slippage_pct,  # 🔥 FIX: Ajouter slippage en pourcentage
                'slippage_pct': slippage_pct,  # Alias
                'slippage_usdt': slippage_usdt,  # Slippage en USDT
                'gross_pnl': pnl_data['pnl_usdt_gross']  # PnL brut en USDT
            },
            mode='LIVE'
        )

        # Réinitialiser position
        self.active_position = None

        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl_pct:.2f}% ({net_pnl_usdt:.4f} USDT) | "
            f"Slippage: {slippage_pct:.4f}% ({slippage_usdt:.4f} USDT)"
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
