#!/usr/bin/env python3
"""
Position Manager - Trade Cursor v7.0
Gestion des positions: TP/SL, Break-even, Trailing Stop
REFACTORISÉ avec architecture modulaire
"""

import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
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

MIN_LIVE_TRADE_DURATION_SEC = 10


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
    actual_slippage_pct: Optional[float] = None

    # 🔥 LIVE TRADING METADATA (ordres & exécution)
    live_execution_mode: Optional[str] = None
    entry_order_id: Optional[str] = None
    entry_order_type: Optional[str] = None
    entry_requested_price: Optional[float] = None
    entry_fill_price: Optional[float] = None
    entry_slippage_pct: Optional[float] = None
    entry_latency_ms: Optional[float] = None
    entry_timestamp: Optional[str] = None
    entry_api_response: Optional[Any] = None
    exit_order_id: Optional[str] = None
    exit_order_type: Optional[str] = None
    exit_requested_price: Optional[float] = None
    exit_fill_price: Optional[float] = None
    exit_slippage_pct: Optional[float] = None
    exit_latency_ms: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_api_response: Optional[Any] = None
    leverage_used: Optional[int] = None
    margin_mode: Optional[str] = None
    contract_size_used: Optional[float] = None  # 🔥 FIX: Stocker contract_size pour éviter erreurs de calcul
    position_size_usdt: Optional[float] = None
    position_size_contracts: Optional[float] = None
    size_initial_contracts: Optional[float] = None
    size_initial_usdt: Optional[float] = None  # 🔥 FIX: Taille initiale USDT (demandée) pour historique
    size_executed_usdt: Optional[float] = None  # 🔥 FIX: Taille réellement exécutée (après lot size)
    size_remaining_contracts: Optional[float] = None
    liquidation_price: Optional[float] = None
    margin_used: Optional[float] = None
    maker_fee_rate: Optional[float] = None
    taker_fee_rate: Optional[float] = None
    entry_fee_usdt: Optional[float] = None
    exit_fee_usdt: Optional[float] = None
    total_fees_usdt: Optional[float] = None
    funding_rate_at_entry: Optional[float] = None
    funding_rate_at_exit: Optional[float] = None
    funding_paid_usdt: Optional[float] = None
    
    # 🔥 ML & Sizing Adaptatif (pour affichage frontend)
    ml_confidence: Optional[float] = None  # Confiance ML au moment de l'ouverture (%)
    ml_calibrated_winrate: Optional[float] = None  # 🔥 WR Réel calibré (si disponible)
    adaptive_sizing_multiplier: Optional[float] = None  # Multiplicateur sizing adaptatif (0.5-1.5)
    
    # 🔥 FIX: Min contract amount pour validation TP partiel
    min_contract_amount: Optional[float] = None  # Minimum du contrat en tokens
    force_full_tp_for_partial: bool = False  # Si True, le TP partiel fermera 100% car qty < min
    
    time_to_fill_entry_ms: Optional[float] = None
    time_to_fill_exit_ms: Optional[float] = None
    price_at_signal: Optional[float] = None
    price_at_order_sent: Optional[float] = None
    signal_to_fill_slippage_pct: Optional[float] = None
    api_errors: Optional[Any] = None
    retry_count: int = 0
    exchange_latency_ms: Optional[float] = None
    ws_latency_ms: Optional[float] = None

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
            'tp_escalier_levels': self.tp_escalier_levels if hasattr(self, 'tp_escalier_levels') and self.tp_escalier_levels else [],  # 🔥 FIX: Retourner la liste native pour éviter erreurs de type
            'current_price': getattr(self, 'current_price', None),  # 🔥 FIX: Ajouter prix actuel si disponible
            'price_precision': self.price_precision,  # 🔥 FIX: Précision prix depuis API
            'tick_size': self.tick_size,  # 🔥 FIX: Tick size depuis API (alternative à price_precision)
            # Live meta
            'live_execution_mode': self.live_execution_mode,
            'entry_order_id': self.entry_order_id,
            'entry_order_type': self.entry_order_type,
            'entry_requested_price': self.entry_requested_price,
            'entry_fill_price': self.entry_fill_price,
            'entry_slippage_pct': self.entry_slippage_pct,
            'entry_latency_ms': self.entry_latency_ms,
            'entry_timestamp': self.entry_timestamp,
            'exit_order_id': self.exit_order_id,
            'exit_order_type': self.exit_order_type,
            'exit_requested_price': self.exit_requested_price,
            'exit_fill_price': self.exit_fill_price,
            'exit_slippage_pct': self.exit_slippage_pct,
            'exit_latency_ms': self.exit_latency_ms,
            'exit_timestamp': self.exit_timestamp,
            'leverage_used': self.leverage_used,
            'margin_mode': self.margin_mode,
            'contract_size_used': self.contract_size_used,
            'position_size_usdt': self.position_size_usdt,
            'position_size_contracts': self.position_size_contracts,
            'size_initial_contracts': self.size_initial_contracts,
            'size_initial_usdt': self.size_initial_usdt,
            'size_remaining_contracts': self.size_remaining_contracts,
            'liquidation_price': self.liquidation_price,
            'margin_used': self.margin_used,
            'entry_fee_usdt': self.entry_fee_usdt,
            'exit_fee_usdt': self.exit_fee_usdt,
            'total_fees_usdt': self.total_fees_usdt,
            'funding_rate_at_entry': self.funding_rate_at_entry,
            'funding_rate_at_exit': self.funding_rate_at_exit,
            'funding_paid_usdt': self.funding_paid_usdt,
            'time_to_fill_entry_ms': self.time_to_fill_entry_ms,
            'time_to_fill_exit_ms': self.time_to_fill_exit_ms,
            # 🔥 ML & Sizing Adaptatif
            'ml_confidence': self.ml_confidence,
            'ml_calibrated_winrate': self.ml_calibrated_winrate,
            'adaptive_sizing_multiplier': self.adaptive_sizing_multiplier,
            # 🔥 FIX: Info TP partiel forcé à 100%
            'min_contract_amount': self.min_contract_amount,
            'force_full_tp_for_partial': self.force_full_tp_for_partial,
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

    def __init__(self, config: PositionConfig, analytics_db=None, live_order_manager=None):
        """
        Initialiser PositionManager avec modules

        Args:
            config: Configuration position
            analytics_db: Base de données Analytics (optionnel)
            live_order_manager: Gestionnaire ordres live (None = paper trading)
        """
        self.config = config
        self.active_position: Optional[Position] = None
        self.price_cache: Dict[str, Dict] = {}
        self.api_alert_shown = False
        self.last_price = 0.0
        self.last_price_update = datetime.now().timestamp() * 1000
        self.market_info_cache: Dict[str, Dict] = {}  # 🔥 FIX: Cache pour informations de marché (précision)

        # 🔥 LIVE TRADING: Gestionnaire ordres live (None = paper trading)
        self.live_order_manager = live_order_manager

        # Initialiser modules spécialisés
        self._init_modules(analytics_db)

    def _schedule_position_sync(self, symbol: str, delay: Optional[float] = None) -> None:
        if not self.live_order_manager:
            return

        dry_run = False
        try:
            dry_run = getattr(self.live_order_manager, 'dry_run', False)
        except Exception:
            dry_run = False

        if dry_run:
            return

        from config import TRADING_CONFIG

        if delay is None:
            delay = float(TRADING_CONFIG.get('live_resync_delay_sec', 3))

        def _worker():
            try:
                if delay and delay > 0:
                    logger.debug(f"⏳ Resynchronisation position LIVE programmée dans {delay}s pour {symbol}...")
                    time.sleep(delay)

                live_position = self.live_order_manager.get_position(symbol, prefer_ccxt=True)
                if not live_position:
                    logger.warning(f"⚠️ Aucune position LIVE trouvée pour {symbol} lors de la resynchronisation différée")
                    return

                current_position = self.active_position
                if not current_position or current_position.symbol != symbol:
                    return

                live_entry_price = float(live_position.get('entry_price') or 0)
                # 🔥 FIX: Utiliser 'tokens' directement (déjà calculé = contracts × contract_size)
                real_tokens = float(live_position.get('tokens') or 0)

                if live_entry_price > 0:
                    previous_entry = current_position.entry
                    if previous_entry and abs(live_entry_price - previous_entry) > 1e-8:
                        price_diff = live_entry_price - previous_entry
                        if current_position.direction == 'LONG':
                            current_position.tp += price_diff
                            current_position.sl += price_diff
                        else:
                            current_position.tp -= price_diff
                            current_position.sl -= price_diff
                        logger.info(
                            f"🔁 [LIVE] Prix d'entrée resynchronisé: {previous_entry:.8f} -> {live_entry_price:.8f}"
                        )
                    current_position.entry = live_entry_price
                    current_position.entry_fill_price = live_entry_price

                if real_tokens > 0 and live_entry_price > 0:
                    # 🔥 FIX: Calculer USDT directement depuis tokens × entry
                    live_size_usdt = real_tokens * live_entry_price

                    # 🔥 FIX: Mettre à jour size_initial_contracts si pas encore synchro LIVE
                    # ou si aucun TP partiel n'a eu lieu (size_initial == size_remaining)
                    old_initial = current_position.size_initial_contracts or 0
                    old_remaining = current_position.size_remaining_contracts or 0
                    if not old_initial or abs(old_initial - old_remaining) < 0.0001:
                        # Première synchro LIVE ou pas de TP partiel → mettre à jour initial
                        current_position.size_initial_contracts = real_tokens

                    # Mettre à jour la taille actuelle (TOUJOURS, même après TP partiel)
                    current_position.size = live_size_usdt
                    current_position.position_size_usdt = live_size_usdt
                    current_position.position_size_contracts = real_tokens
                    current_position.size_remaining = live_size_usdt
                    current_position.size_remaining_contracts = real_tokens

                    logger.info(
                        f"🔁 [LIVE] Taille resynchronisée: {real_tokens:.6f} tokens × {live_entry_price:.4f} = {live_size_usdt:.4f} USDT"
                    )
            except Exception as e:
                logger.error(f"❌ Erreur resynchronisation différée position LIVE pour {symbol}: {e}")

        thread = threading.Thread(target=_worker, name=f"position_sync_{symbol}", daemon=True)
        try:
            thread.start()
        except RuntimeError as e:
            logger.error(f"❌ Impossible de démarrer le thread de resynchronisation pour {symbol}: {e}")

    def _get_contract_size(self, symbol: str) -> float:
        """
        🔥 FIX: Obtenir le contractSize pour un symbole
        
        Pour SHIB avec contractSize=1000, MEXC retourne 2524 contrats mais
        le vrai montant en tokens est 2524 * 1000 = 2,524,000
        
        Args:
            symbol: Symbole de la paire (ex: SHIB/USDT:USDT)
            
        Returns:
            contractSize (ex: 1000 pour SHIB, 0.0001 pour BTC)
        """
        try:
            if self.live_order_manager and hasattr(self.live_order_manager, 'bypass_client'):
                bypass_client = self.live_order_manager.bypass_client
                if bypass_client:
                    # Convertir le symbole au format bypass (SHIB/USDT:USDT -> SHIB_USDT)
                    bypass_symbol = symbol.replace('/USDT:USDT', '_USDT').replace('/', '_')
                    
                    # Essayer de récupérer depuis le cache du bypass_client
                    if hasattr(bypass_client, '_contract_specs') and bypass_symbol in bypass_client._contract_specs:
                        spec = bypass_client._contract_specs[bypass_symbol]
                        return spec.contract_size
                    
                    # Sinon, essayer de récupérer via l'API (synchrone)
                    try:
                        from trading.live_order_manager_futures import run_async_safely
                        spec = run_async_safely(bypass_client.get_contract_spec(bypass_symbol))
                        if spec:
                            logger.info(f"📋 ContractSize récupéré pour {symbol}: {spec.contract_size}")
                            return spec.contract_size
                    except Exception as e:
                        logger.debug(f"⚠️ Impossible de récupérer contract_spec pour {bypass_symbol}: {e}")
        except Exception as e:
            logger.debug(f"⚠️ Erreur _get_contract_size pour {symbol}: {e}")
        
        return 1.0  # Défaut: pas de conversion

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
        condition_types: Optional[List[str]] = None,
        ml_confidence: Optional[float] = None,  # 🔥 FIX: Ajouter ml_confidence
        adaptive_sizing_multiplier: Optional[float] = None  # 🔥 Multiplicateur sizing adaptatif
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
        # 🔥 FIX: Log critique pour diagnostiquer size=0
        logger.info(
            f"📋 OPEN_POSITION reçu: {symbol} {direction} | "
            f"entry={entry} | size={size} USDT"
        )
        
        # 🔥 FIX: Validation size minimum AVANT de créer la position
        MIN_SIZE_USDT = 7.0
        if size < MIN_SIZE_USDT:
            logger.warning(
                f"⚠️ Position size trop petite: {size:.2f} USDT < {MIN_SIZE_USDT} USDT | "
                f"Augmentation automatique à {MIN_SIZE_USDT} USDT"
            )
            size = MIN_SIZE_USDT
        
        # Validation
        if not entry or entry <= 0:
            raise ValueError(f"Entry invalide: {entry}")

        if self.config.fixed_sl_pct <= 0 or self.config.fixed_tp_pct <= 0:
            raise ValueError(
                f"Config invalide: fixed_sl_pct={self.config.fixed_sl_pct}%, "
                f"fixed_tp_pct={self.config.fixed_tp_pct}%"
            )

        # 🔥 ML AUTO-CALIBRATION: Vérifier si le trade doit être pris
        calibrated_wr = None
        logger.info(f"🔍 Calibration check: {symbol} {direction} | ml_confidence={ml_confidence}")
        try:
            from ml.calibration import get_calibration_manager
            calib_manager = get_calibration_manager()
            should_take, calibrated_wr, calib_reason = calib_manager.should_take_trade(
                direction=direction,
                ml_confidence=ml_confidence
            )
            
            if not should_take:
                logger.warning(
                    f"🚫 Trade rejeté par ML Calibration: {symbol} {direction} | "
                    f"ML Conf={ml_confidence:.1f}% → WR Réel={calibrated_wr:.1f}% | "
                    f"Raison: {calib_reason}"
                )
                return None  # Rejeter le trade
            
            if calibrated_wr is not None:
                logger.info(
                    f"✅ Trade accepté (calibration): {symbol} {direction} | "
                    f"ML Conf={ml_confidence:.1f}% → WR Réel={calibrated_wr:.1f}%"
                )
            else:
                logger.info(f"⏭️ Calibration: {symbol} {direction} | Phase apprentissage (calibrated_wr=None)")
        except Exception as e:
            logger.warning(f"⚠️ Calibration check erreur (non-bloquant): {e}")

        from config import TRADING_CONFIG
        excluded_symbols = set(TRADING_CONFIG.get('excluded_symbols', []))
        if symbol in excluded_symbols:
            raise ValueError(f"Symbol {symbol} est exclu du trading (excluded_symbols)")

        # Mettre à jour config TP/SL avec valeurs depuis TRADING_CONFIG (dynamique)
        self.tpsl_config.win_streak = self.config.win_streak
        self.tpsl_config.loss_streak = self.config.loss_streak
        # FIX: Mettre à jour paramètres FIXE depuis TRADING_CONFIG (au lieu de self.config qui n'est pas mis à jour dynamiquement)
        self.tpsl_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.6)
        self.tpsl_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
        # 🔥 FIX: Mettre à jour paramètres ATR depuis valeurs EFFECTIVES (régime dynamique)
        from utils.effective_config import get_effective_value
        self.tpsl_config.atr_mult_tp = get_effective_value('atr_mult_tp', 1.5)
        self.tpsl_config.atr_mult_sl = get_effective_value('atr_mult_sl', 1.0)
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

        # ✅ Initialiser les tailles en contrats même en mode paper/dry-run
        try:
            contracts = size / entry if entry else 0.0
        except Exception:
            contracts = 0.0

        self.active_position.position_size_contracts = contracts
        self.active_position.size_initial_contracts = contracts
        self.active_position.size_remaining_contracts = contracts
        self.active_position.size_remaining = size
        
        # 🔥 FIX CRITIQUE: Initialiser size_initial_usdt dès l'ouverture avec la taille demandée
        # Cette valeur NE DOIT PAS être écrasée par une valeur incorrecte de synchronisation
        self.active_position.size_initial_usdt = size  # size = taille en USDT demandée
        # 🔥 FIX: Initialiser size_executed_usdt (sera écrasée après exécution ordre live)
        self.active_position.size_executed_usdt = size  # Par défaut = demandée, mise à jour après ordre
        
        # 🔥 FIX: Stocker ml_confidence sur la position pour le logging
        self.active_position.ml_confidence = ml_confidence
        self.active_position.ml_calibrated_winrate = calibrated_wr
        
        # 🔥 Stocker le multiplicateur sizing adaptatif
        self.active_position.adaptive_sizing_multiplier = adaptive_sizing_multiplier
        
        # 🔥 FIX: Initialiser leverage_used dès la création (sera mis à jour après l'ordre)
        configured_leverage = TRADING_CONFIG.get('default_leverage', 10)
        self.active_position.leverage_used = configured_leverage

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

        # 🔥 LIVE TRADING: Passer ordre réel si LiveOrderManager actif
        executed_size_usdt = size

        if self.live_order_manager:
            try:
                # Calculer la taille en tokens (amount) depuis la taille en USDT
                size_amount = size / entry

                # 🔥 FIX: Récupérer le levier depuis TRADING_CONFIG (pas celui de l'init)
                configured_leverage = TRADING_CONFIG.get('default_leverage', 10)
                
                # 🔍 VÉRIFICATION LEVIER: Logger pour debug
                logger.info(
                    f"🔍 LEVIER CHECK: config={configured_leverage}x | "
                    f"live_manager_default={self.live_order_manager.default_leverage}x | "
                    f"Utilisation: {configured_leverage}x"
                )

                order_result = self.live_order_manager.open_position(
                    symbol=symbol,
                    direction=direction,
                    entry_price=entry,
                    size_usdt=size,
                    leverage=configured_leverage
                )

                if order_result.success:
                    # Mettre à jour position avec données réelles
                    self.active_position.live_execution_mode = 'LIVE'
                    self.active_position.entry_order_id = order_result.order_id
                    
                    # FIX: Stocker le levier utilisé pour l'affichage frontend
                    self.active_position.leverage_used = order_result.leverage
                    
                    # 🔥 FIX: Stocker contract_size pour éviter erreurs de calcul PNL
                    if hasattr(order_result, 'contract_size') and order_result.contract_size:
                        self.active_position.contract_size_used = order_result.contract_size
                        logger.info(f"📋 Contract size stocké: {order_result.contract_size}")
                    
                    # FIX: Mettre à jour la taille avec la taille réellement exécutée
                    if order_result.filled_size_usdt and order_result.filled_size_usdt > 0:
                        executed_size_usdt = order_result.filled_size_usdt
                        # 🔥 DEBUG: Log pour tracer le calcul
                        logger.warning(
                            f"🔍 DEBUG SIZE (1): filled_size_usdt={order_result.filled_size_usdt:.4f}, "
                            f"filled_amount={order_result.filled_amount}, filled_price={order_result.filled_price}"
                        )
                        self.active_position.size = executed_size_usdt
                        self.active_position.position_size_usdt = executed_size_usdt
                        self.active_position.size_remaining = executed_size_usdt
                        # 🔥 FIX: Stocker la taille exécutée pour calcul PnL précis
                        self.active_position.size_executed_usdt = executed_size_usdt
                        logger.info(f"✅ Taille position ajustée au réel: {size:.2f} -> {executed_size_usdt:.2f} USDT")
                    
                    if order_result.filled_amount:
                        # 🔥 FIX CRITIQUE: Utiliser les valeurs de order_result correctement
                        # order_result.filled_amount est DÉJÀ en tokens réels (conversion faite dans bypass)
                        # order_result.contract_size contient le contract_size utilisé
                        
                        # Stocker le contract_size pour les calculs futurs
                        if order_result.contract_size and order_result.contract_size > 0:
                            self.active_position.contract_size_used = order_result.contract_size
                            logger.info(f"📋 Contract size depuis ordre: {order_result.contract_size} pour {symbol}")
                        elif not self.active_position.contract_size_used or self.active_position.contract_size_used <= 0:
                            self.active_position.contract_size_used = self._get_contract_size(symbol)
                            logger.info(f"📋 Contract size récupéré: {self.active_position.contract_size_used} pour {symbol}")
                        
                        # 🔥 FIX: filled_amount est DÉJÀ en tokens réels, pas besoin de conversion
                        real_tokens = order_result.filled_amount
                        logger.info(f"📊 Position ouverte: {real_tokens:.6f} tokens réels ({real_tokens / self.active_position.contract_size_used if self.active_position.contract_size_used else real_tokens:.2f} contrats MEXC)")
                        
                        self.active_position.position_size_contracts = real_tokens
                        self.active_position.size_initial_contracts = real_tokens
                        self.active_position.size_remaining_contracts = real_tokens
                        
                    # Mettre à jour prix d'entrée si différent
                    if order_result.filled_price and order_result.filled_price > 0:
                        # Ajuster TP/SL pour maintenir la distance relative
                        price_diff = order_result.filled_price - entry
                        if direction == 'LONG':
                            self.active_position.tp += price_diff
                            self.active_position.sl += price_diff
                        else:
                            self.active_position.tp -= price_diff
                            self.active_position.sl -= price_diff
                            
                        self.active_position.entry = order_result.filled_price
                        self.active_position.entry_fill_price = order_result.filled_price
                        
                    self.active_position.entry_slippage_pct = order_result.actual_slippage_pct
                    self.active_position.entry_latency_ms = order_result.latency_ms
                    self.active_position.liquidation_price = order_result.liquidation_price
                    self.active_position.entry_fee_usdt = order_result.actual_fees_usdt
                    self.active_position.margin_used = order_result.margin_used
                    
                    # 🔥 FIX: Utiliser order_result.min_contract_amount
                    self.active_position.min_contract_amount = order_result.min_contract_amount
                    
                    # 🔥 FIX CRITIQUE: Calculer si TP partiel doit fermer 100% au lieu de X%
                    # ATTENTION: filled_amount est en TOKENS, min_contract_amount est en CONTRATS
                    # Il faut convertir en contrats pour comparer correctement !
                    if order_result.min_contract_amount and order_result.filled_amount:
                        partial_tp_percent = TRADING_CONFIG.get('partial_tp_percent', 50.0)
                        
                        # 🔥 FIX: Convertir tokens → contrats pour comparaison
                        contract_size = order_result.contract_size or self.active_position.contract_size_used or 1.0
                        filled_contracts = order_result.filled_amount / contract_size if contract_size > 0 else order_result.filled_amount
                        partial_contracts = filled_contracts * (partial_tp_percent / 100.0)
                        
                        logger.info(
                            f"📊 Vérification TP Partiel: {filled_contracts:.2f} contrats × {partial_tp_percent}% = "
                            f"{partial_contracts:.2f} contrats | Min: {order_result.min_contract_amount} contrats"
                        )
                        
                        if partial_contracts < order_result.min_contract_amount:
                            self.active_position.force_full_tp_for_partial = True
                            logger.info(
                                f"🔧 TP Partiel forcé à 100%: {partial_contracts:.2f} contrats < min {order_result.min_contract_amount} | "
                                f"Position: {filled_contracts:.2f} contrats ({order_result.filled_amount:.6f} tokens)"
                            )
                        else:
                            self.active_position.force_full_tp_for_partial = False

                    # 🔄 Synchroniser avec la position réelle retournée par l'API MEXC (prix d'entrée & taille)
                    if not self.live_order_manager.dry_run:
                        # Attendre le délai configuré avant lecture (laisse le temps à MEXC d'enregistrer)
                        sync_delay = TRADING_CONFIG.get('live_entry_sync_delay_sec', 2)
                        if sync_delay > 0:
                            logger.debug(f"⏳ Attente {sync_delay}s avant synchro position MEXC...")
                            time.sleep(sync_delay)
                        
                        # prefer_ccxt=True pour utiliser CCXT en priorité (économise bypass)
                        live_position = self.live_order_manager.get_position(symbol, prefer_ccxt=True)
                        if live_position:
                            live_entry_price = float(live_position.get('entry_price') or 0)
                            # 🔥 FIX: Utiliser 'tokens' directement (déjà calculé = contracts × contract_size)
                            real_tokens = float(live_position.get('tokens') or 0)
                            live_contracts = float(live_position.get('contracts') or 0)
                            
                            logger.info(
                                f"🔁 [LIVE] get_position: tokens={real_tokens:.6f}, contracts={live_contracts}, "
                                f"contract_size={live_position.get('contract_size')}, entry={live_entry_price}"
                            )

                            if live_entry_price > 0:
                                previous_entry = self.active_position.entry
                                if abs(live_entry_price - previous_entry) > 1e-8:
                                    price_diff = live_entry_price - previous_entry
                                    if direction == 'LONG':
                                        self.active_position.tp += price_diff
                                        self.active_position.sl += price_diff
                                    else:
                                        self.active_position.tp -= price_diff
                                        self.active_position.sl -= price_diff
                                    logger.info(
                                        f"🔁 [LIVE] Prix d'entrée synchronisé avec MEXC: {previous_entry:.8f} -> {live_entry_price:.8f}"
                                    )
                                self.active_position.entry = live_entry_price
                                self.active_position.entry_fill_price = live_entry_price

                            if real_tokens > 0 and live_entry_price > 0:
                                # 🔥 FIX: Utiliser tokens déjà calculé par get_position
                                live_size_usdt = real_tokens * live_entry_price
                                
                                logger.info(
                                    f"🔁 [LIVE] Sync: {real_tokens:.6f} tokens × {live_entry_price:.4f} = {live_size_usdt:.4f} USDT"
                                )

                                self.active_position.size = live_size_usdt
                                self.active_position.position_size_usdt = live_size_usdt
                                self.active_position.position_size_contracts = real_tokens
                                self.active_position.size_remaining = live_size_usdt
                                self.active_position.size_initial_contracts = real_tokens
                                self.active_position.size_remaining_contracts = real_tokens
                                self.active_position.size_executed_usdt = live_size_usdt
                                if not self.active_position.size_initial_usdt:
                                    self.active_position.size_initial_usdt = live_size_usdt
                            else:
                                logger.warning(
                                    f"🔍 DEBUG SIZE (2b): live_contracts={live_contracts}, live_entry_price={live_entry_price} - SYNC SKIPPED!"
                                )
                        # Programmer une resynchronisation non bloquante
                        self._schedule_position_sync(symbol)

                    # Recalculer TP/SL avec nouveau prix d'entrée si slippage significatif
                    if order_result.actual_slippage_pct and abs(order_result.actual_slippage_pct) > 0.01:  # > 0.01%
                        price_diff = order_result.filled_price - entry
                        self.active_position.tp += price_diff if direction == 'LONG' else -price_diff
                        self.active_position.sl += price_diff if direction == 'LONG' else -price_diff

                    logger.info(
                        f"✅ Ordre LIVE placé: {symbol} | "
                        f"Prix rempli: {order_result.filled_price:.8f} | "
                        f"Slippage: {order_result.actual_slippage_pct or 0:.4f}% | "
                        f"Taille réelle: {executed_size_usdt:.2f} USDT ({order_result.filled_amount:.4f} contrats)"
                    )
                    # 🔥 FIX: Marquer la position comme ouverte sur l'exchange
                    self.active_position.is_live_open = True
                else:
                    logger.error(
                        f"❌ Ordre LIVE échoué: {symbol} | "
                        f"Erreur: {order_result.error_message} | "
                        f"Revert to paper trading"
                    )
                    # 🔥 FIX: Position non ouverte sur exchange - empêcher TP partiels live
                    self.active_position.is_live_open = False
            except Exception as e:
                logger.error(f"❌ Erreur passage ordre LIVE: {e}")

        logger.info(
            f"🟢 POSITION OUVERTE: {direction} {symbol} | "
            f"Entry: {self._format_price(entry)} | "
            f"SL: {self._format_price(sl)} | TP: {self._format_price(tp)} | "
            f"Size: {executed_size_usdt:.2f} USDT | Mode: {'ATR' if self.config.use_atr else 'FIXE'}"
            + (f" | TP Escalier: {len(levels_config)} niveaux" if levels_config else "")
            + (f" | LIVE: {self.live_order_manager.dry_run and 'DRY-RUN' or 'RÉEL'}" if self.live_order_manager else " | PAPER")
        )

        # ========================================
        # ✅ POINT C : CAPTURE INDICATEURS D'ENTRÉE (pour PostgreSQL)
        # ========================================
        # 🔥 FIX: Capturer les indicateurs TOUJOURS, pas seulement si data_logger.is_running
        # Récupérer scan_uuid, opportunity_id et setup depuis les attributs stockés
        scan_uuid = getattr(self, '_last_setup_scan_uuid', None)
        opportunity_id = getattr(self, '_last_setup_opportunity_id', None)
        last_setup = getattr(self, '_last_setup', None)
        
        # 🔥 FIX BUG #4: Monitoring amélioré - Log d'alerte si _last_setup est None
        if not last_setup:
            logger.error(
                f"❌ BUG #4: _last_setup est None pour {symbol} - "
                f"Les indicateurs d'entrée ne seront PAS disponibles dans PostgreSQL. "
                f"Vérifier que scanner_loop.py stocke correctement _last_setup dans position_manager."
            )
        else:
            logger.info(f"✅ _last_setup disponible pour {symbol}, keys: {list(last_setup.keys())[:10]}")
            if 'indicators_1m' not in last_setup and 'indicators_5m' not in last_setup:
                logger.warning(
                    f"⚠️ BUG #4: _last_setup ne contient pas 'indicators_1m' ou 'indicators_5m' pour {symbol}. "
                    f"Vérifier que analyzer.py ajoute ces indicateurs au setup retourné."
                )
        
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
        self.active_position._opportunity_id = opportunity_id  # 🔥 FIX: Stocker opportunity_id
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

        # 📢 NOTIFICATION: Position ouverte
        if hasattr(self, 'notification_manager') and self.notification_manager:
            try:
                import asyncio
                position_data = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_price': entry,
                    'size_usdt': executed_size_usdt,
                    'sl': sl,
                    'tp': tp,
                    'atr': atr,
                    'leverage': getattr(self.live_order_manager, 'leverage', 1) if self.live_order_manager else 1,
                    'tp_escalier_levels': len(levels_config) if levels_config else 0
                }
                # Appel async non-bloquant
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(
                            self.notification_manager.notify('position_opened', position_data, priority='info')
                        )
                    else:
                        asyncio.run(self.notification_manager.notify('position_opened', position_data, priority='info'))
                except RuntimeError:
                    # Pas de loop, ignorer notification
                    pass
            except Exception as e:
                logger.debug(f"Erreur envoi notification position_opened: {e}")

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
        # ✅ Lire risk_per_trade et bornes depuis TRADING_CONFIG
        from config import TRADING_CONFIG
        risk_per_trade_pct = float(TRADING_CONFIG.get('risk_per_trade', 2.0))
        risk_per_trade = risk_per_trade_pct / 100.0  # Convertir % en décimal
        base_risk = risk_per_trade  # Utiliser risk_per_trade au lieu de base_risk par défaut

        # Bornes dynamiques (overridable via config)
        min_risk_pct_cfg = TRADING_CONFIG.get('min_risk_per_trade')
        max_risk_pct_cfg = TRADING_CONFIG.get('max_risk_per_trade')

        min_risk = (
            max(0.001, float(min_risk_pct_cfg) / 100.0)
            if min_risk_pct_cfg is not None else
            max(0.001, base_risk * 0.5)
        )
        max_risk = (
            max(min_risk, float(max_risk_pct_cfg) / 100.0)
            if max_risk_pct_cfg is not None else
            max(base_risk, base_risk * 2.0)
        )

        score = setup.get('score', 5.0)

        # Taille de base
        base_size = capital * base_risk

        # 🔥 SIMPLIFIÉ: Pas de multiplicateur basé sur le score
        # Le score sert uniquement à filtrer les setups (min_score_required)
        # La taille reste constante = account_size × risk_per_trade
        multiplier = 1.0

        # Multiplicateur selon streaks (Séries)
        streak_mult = 1.0
        
        # 🟢 BOOST GAINS : Si on est sur une série de victoires, on augmente
        if self.config.win_streak >= 3:
            streak_mult = 1.1  # +10%
            
        # 🔴 PROTECTION PERTES : Gérée par le Recovery Mode
        # On n'applique pas de réduction simple ici pour éviter le double emploi
        
        # Recovery Mode - Réduction de taille progressive
        recovery_mult = self.recovery_mode.get_position_size_multiplier(self.config.loss_streak)
        
        if recovery_mult < 1.0:
            # Si le Recovery Mode est actif, il dicte la réduction
            # Cela remplace tout multiplicateur de streak précédent
            streak_mult = recovery_mult
            logger.debug(
                f"🔄 Recovery Mode Actif: Taille réduite à {recovery_mult:.0%} (Streak de {self.config.loss_streak} pertes)"
            )

        # 🔥 PHASE 8: Sizing Adaptatif par Paire/Session
        adaptive_mult = 1.0
        symbol = setup.get('symbol', '')
        if symbol and TRADING_CONFIG.get('adaptive_sizing_enabled', True):
            try:
                from core.position.adaptive_sizing import get_adaptive_sizing_manager
                adaptive_manager = get_adaptive_sizing_manager()
                adaptive_mult = adaptive_manager.get_size_multiplier(symbol)
                if adaptive_mult != 1.0:
                    logger.info(
                        f"📊 Sizing adaptatif {symbol}: x{adaptive_mult:.2f} "
                        f"(basé sur WR session)"
                    )
            except Exception as e:
                logger.debug(f"Sizing adaptatif non disponible: {e}")

        # Calculer taille finale
        final_size = base_size * multiplier * streak_mult * adaptive_mult

        # Bornes
        min_size = capital * min_risk if min_risk else 0.0
        max_size = capital * max_risk if max_risk else final_size
        final_size = max(min_size, min(max_size, final_size))
        
        # 🔥 FIX: Garantir une taille minimum de 7 USDT pour éviter les rejets MEXC (min 5 USDT)
        MIN_POSITION_USDT = 7.0
        if final_size < MIN_POSITION_USDT:
            logger.warning(
                f"⚠️ Taille position trop petite ({final_size:.2f} USDT), augmentation au minimum {MIN_POSITION_USDT} USDT"
            )
            final_size = MIN_POSITION_USDT

        # 🔥 DEBUG: Log WARNING pour visibilité
        logger.warning(
            f"📊 POSITION SIZING DEBUG: {setup.get('symbol', 'N/A')} | "
            f"Score={score:.1f} | Capital={capital:.2f} | Risk={base_risk*100:.2f}% | "
            f"Base={base_size:.2f} | Multiplier={multiplier:.2f} | "
            f"Streak={streak_mult:.2f} | Adaptive={adaptive_mult:.2f} | "
            f"Final={final_size:.2f} USDT"
        )

        return round(final_size, 2)

    def record_trade_for_adaptive_sizing(self, symbol: str, pnl_pct: float, is_win: bool):
        """
        Enregistre un trade dans le manager de sizing adaptatif.
        Appelé après la fermeture d'une position.
        
        Args:
            symbol: Symbole de la paire
            pnl_pct: PnL en pourcentage
            is_win: True si trade gagnant
        """
        from config import TRADING_CONFIG
        if not TRADING_CONFIG.get('adaptive_sizing_enabled', True):
            return
        
        try:
            from core.position.adaptive_sizing import get_adaptive_sizing_manager
            manager = get_adaptive_sizing_manager()
            manager.record_trade(symbol, pnl_pct, is_win)
        except Exception as e:
            logger.debug(f"Erreur enregistrement trade adaptatif: {e}")

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

        # Depth factor
        if bid_vol and ask_vol:
            depth_factor = order_size / (bid_vol + ask_vol)
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
        
        # 🔥 BOUCLE DE VÉRIFICATION: Assurer cohérence entre size, tokens et entry
        # Source de vérité = size_initial_contracts (tokens MEXC à l'ouverture)
        # Si pas de TP partiel: size_remaining_contracts doit = size_initial_contracts
        # size USDT doit être = tokens × entry_price
        if self.active_position.entry and self.active_position.entry > 0:
            
            # 🔥 FIX CRITIQUE: Si pas de TP partiel, synchroniser remaining avec initial
            if not self.active_position.partial_tp_sold and self.active_position.size_initial_contracts:
                if self.active_position.size_remaining_contracts != self.active_position.size_initial_contracts:
                    logger.warning(
                        f"⚠️ SYNC: size_remaining_contracts ({self.active_position.size_remaining_contracts:.6f}) "
                        f"!= size_initial_contracts ({self.active_position.size_initial_contracts:.6f}) sans TP partiel. Correction..."
                    )
                    self.active_position.size_remaining_contracts = self.active_position.size_initial_contracts
                    self.active_position.position_size_contracts = self.active_position.size_initial_contracts
            
            # Utiliser size_initial_contracts comme source de vérité
            tokens_source = self.active_position.size_remaining_contracts or self.active_position.size_initial_contracts
            
            if tokens_source and tokens_source > 0:
                expected_size_usdt = tokens_source * self.active_position.entry
                current_size = self.active_position.size or 0
                
                # Vérifier si size est incohérent (plus de 5% d'écart)
                if current_size > 0:
                    ratio = current_size / expected_size_usdt
                    if ratio > 1.05 or ratio < 0.95:
                        logger.warning(
                            f"⚠️ CORRECTION SIZE: {current_size:.4f} USDT → {expected_size_usdt:.4f} USDT "
                            f"({tokens_source:.6f} tokens × {self.active_position.entry:.4f})"
                        )
                        self.active_position.size = expected_size_usdt
                        self.active_position.position_size_usdt = expected_size_usdt
                        self.active_position.size_remaining = expected_size_usdt
                else:
                    # size manquant, initialiser
                    self.active_position.size = expected_size_usdt
                    self.active_position.position_size_usdt = expected_size_usdt
                    self.active_position.size_remaining = expected_size_usdt
                    
            # Cas 2: Pas de tokens mais size existe → calculer tokens depuis size
            elif self.active_position.size and self.active_position.size > 0:
                expected_tokens = self.active_position.size / self.active_position.entry
                if not self.active_position.size_initial_contracts:
                    self.active_position.size_initial_contracts = expected_tokens
                if not self.active_position.size_remaining_contracts:
                    self.active_position.size_remaining_contracts = expected_tokens
                if not self.active_position.position_size_contracts:
                    self.active_position.position_size_contracts = expected_tokens
                logger.debug(f"📋 Tokens calculés depuis size: {expected_tokens:.6f}")

        # 🔥 FIX: Initialiser size_initial_usdt si manquant (pour historique)
        if not self.active_position.size_initial_usdt:
             if self.active_position.partial_tp_sold:
                  # Estimation rétroactive si on a déjà vendu
                  partial_pct = TRADING_CONFIG.get('partial_tp_percent', 50.0) / 100.0
                  try:
                      # Si size actuel est 10.40 et partial 50%, initial ~ 20.80.
                      self.active_position.size_initial_usdt = self.active_position.size / (1 - partial_pct)
                  except:
                      self.active_position.size_initial_usdt = self.active_position.size
             else:
                  self.active_position.size_initial_usdt = self.active_position.size
        
        # 🔥 FIX: Initialiser start_time si manquant (pour duration)
        if not self.active_position.start_time:
             self.active_position.start_time = time.time()

        # Calculer temps écoulé et PnL
        elapsed = time.time() - self.active_position.start_time

        # 🔥 SANITY CHECK LOOP: Resynchroniser toutes les 15 secondes
        # Cela répond à la demande de "boucles de verifs" pour assurer la cohérence exchange/local
        if elapsed > 10 and int(elapsed) % 15 == 0 and int(elapsed) != getattr(self, '_last_sync_check', 0):
             self._last_sync_check = int(elapsed)
             # Ne pas spammer les logs si tout va bien
             self._schedule_position_sync(self.active_position.symbol, delay=0)

        # 🔥 OPT #3: Utiliser prix RÉEL rempli pour calcul PnL (early invalidation)
        # Si entry_fill_price est disponible (ordre réel exécuté), l'utiliser
        # Sinon fallback sur entry (prix théorique, pour paper trading)
        effective_entry = self.active_position.entry_fill_price or self.active_position.entry

        pnl = self.pnl_calculator.calculate_pnl_percent(
            effective_entry,  # 🔥 Prix RÉEL au lieu de théorique
            current_price,
            self.active_position.direction
        )
        
        # 🔥 FIX: Enregistrer le PnL dans l'historique pour calculer max_drawdown
        pnl_usdt = (pnl / 100) * self.active_position.size if self.active_position.size else 0
        self.active_position.pnl_history.append({
            'timestamp': time.time(),
            'price': current_price,
            'pnl_pct': pnl,
            'pnl_usdt': pnl_usdt
        })

        # 1. Early Invalidation (10-30s)
        early_invalidation_data = None
        if self.early_invalidation.should_check(elapsed):
            invalidation = self.early_invalidation.check_invalidation(
                position=self.active_position.to_dict(),
                current_price=current_price,
                pnl_percent=pnl  # 🔥 PnL basé sur prix RÉEL
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
                # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
                early_invalidation_data = {
                    'triggered': True,
                    'triggered_at': datetime.now(timezone.utc).isoformat(),
                    'threshold': invalidation_threshold,
                    'elapsed': elapsed,
                    'atr_pct': atr_pct,
                    'pnl_pct': pnl
                }
                # Stocker dans la position pour le logging
                self.active_position._early_invalidation_data = early_invalidation_data
                return invalidation

        # 🔥 OPT #13: Time-Based Exit - Fermer si position flat après 20min
        if elapsed > 1200:  # 20 minutes = 1200 secondes
            # Position considérée "flat" si PnL entre -0.1% et +0.1%
            if -0.1 <= pnl <= 0.1:
                logger.warning(
                    f"⏱️ Time-Based Exit: Position {self.active_position.symbol} {self.active_position.direction} "
                    f"ouverte depuis {elapsed/60:.1f}min avec PnL {pnl:+.2f}% (flat) → Fermeture"
                )
                return 'TIME_BASED_EXIT'

        # 2. TP Escalier - Vérifier niveaux
        if self.active_position.tp_escalier_enabled:
            level_result = self.tp_escalier.check_and_execute_levels(
                position=self.active_position.to_dict(),
                current_price=current_price
            )
            if level_result:
                # 🔥 LIVE TRADING: Exécuter l'ordre TP Escalier réel sur MEXC
                if self.live_order_manager and not self.live_order_manager.dry_run:
                    try:
                        size_contracts = self.active_position.position_size_contracts
                        if not size_contracts:
                            entry_price = self.active_position.entry or 1
                            size_contracts = self.active_position.size / entry_price
                        
                        # Calculer le % à vendre pour ce niveau
                        level_pct = level_result['size_pct'] * 100  # Convertir en %
                        
                        escalier_order_result = self.live_order_manager.close_position(
                            symbol=self.active_position.symbol,
                            direction=self.active_position.direction,
                            entry_price=self.active_position.entry,
                            current_price=current_price,
                            size_amount=size_contracts,
                            partial_pct=level_pct
                        )
                        
                        if escalier_order_result.success:
                            filled_amount = escalier_order_result.filled_amount or (size_contracts * level_pct / 100)
                            
                            # Mettre à jour les contrats restants
                            remaining_contracts = size_contracts - filled_amount
                            self.active_position.position_size_contracts = remaining_contracts
                            
                            level_result['profit_usdt'] = escalier_order_result.actual_pnl_usdt or level_result['profit_usdt']
                            
                            logger.info(
                                f"💰 [LIVE] TP Escalier niveau {level_result.get('level', '?')} exécuté: "
                                f"{self.active_position.symbol} | "
                                f"Vendu: {filled_amount:.4f} contrats | "
                                f"PnL: {level_result['profit_usdt']:.2f} USDT"
                            )
                        else:
                            logger.error(
                                f"❌ [LIVE] Échec TP Escalier: {escalier_order_result.error_message}"
                            )
                    except Exception as e:
                        logger.error(f"❌ Erreur TP Escalier LIVE: {e}")
                
                # Mettre à jour position avec résultats TP Escalier
                self.active_position.tp_escalier_current_level = self.active_position.to_dict()['tp_escalier_current_level'] + 1
                self.active_position.tp_escalier_size_remaining = self.active_position.to_dict()['tp_escalier_size_remaining'] - level_result['size_pct']
                self.active_position.tp_escalier_profits.append(level_result)
                self.active_position.partial_profit_usdt += level_result['profit_usdt']

        # 3. TP Partiel (si pas TP Escalier) - utiliser break_even_trigger comme seuil du 1er TP
        if not self.active_position.tp_escalier_enabled:
            # 🔥 HYBRID: Break-even basé sur ATR ou % fixe
            break_even_use_atr = TRADING_CONFIG.get('break_even_use_atr', False)
            if break_even_use_atr:
                # 🔥 Mode ATR: BE dès PnL >= X × ATR%
                atr_pct = self._get_position_atr_percent()
                be_atr_mult = TRADING_CONFIG.get('break_even_atr_mult', 0.5)
                break_even_trigger = atr_pct * be_atr_mult
                logger.debug(f"🎯 BE ATR: trigger={break_even_trigger:.3f}% (ATR={atr_pct:.3f}% × {be_atr_mult})")
            else:
                # Mode FIXE: utiliser break_even_trigger directement
                break_even_trigger = TRADING_CONFIG.get('break_even_trigger', 0.3)
            if self.partial_tp.check_trigger(
                position=self.active_position.to_dict(),
                current_price=current_price,
                trigger_pct=break_even_trigger  # Utiliser break_even_trigger au lieu de partial_tp_trigger
            ):
                # Calculer le pourcentage à vendre
                partial_tp_percent = TRADING_CONFIG.get('partial_tp_percent', 50.0)
                
                # 🔥 FIX: Vérifier si on doit forcer 100% (position trop petite pour TP partiel)
                force_full_tp = getattr(self.active_position, 'force_full_tp_for_partial', False)
                if force_full_tp:
                    logger.info(
                        f"🔧 Force TP 100% au lieu de {partial_tp_percent}% (position au minimum du contrat)"
                    )
                    partial_tp_percent = 100.0
                
                # 🔥 LIVE TRADING: Exécuter l'ordre partiel réel sur MEXC
                # 🔥 FIX: Vérifier que la position existe réellement sur l'exchange
                is_live_open = getattr(self.active_position, 'is_live_open', False)
                if self.live_order_manager and not self.live_order_manager.dry_run and is_live_open:
                    try:
                        # Calculer la taille en contrats à vendre
                        size_contracts = self.active_position.position_size_contracts
                        if not size_contracts:
                            entry_price = self.active_position.entry or 1
                            size_contracts = self.active_position.size / entry_price
                        
                        # 🔥 FIX: Vérifier que size_contracts est valide
                        if size_contracts <= 0:
                            logger.warning(f"⚠️ TP Partiel ignoré: size_contracts={size_contracts} invalide")
                            return None
                        
                        partial_order_result = self.live_order_manager.close_position(
                            symbol=self.active_position.symbol,
                            direction=self.active_position.direction,
                            entry_price=self.active_position.entry,
                            current_price=current_price,
                            size_amount=size_contracts,
                            partial_pct=partial_tp_percent  # 🔥 Peut être 100% si force_full_tp
                        )
                        
                        if partial_order_result.success:
                            # Utiliser les valeurs réelles de l'exécution
                            filled_amount = partial_order_result.filled_amount or (size_contracts * partial_tp_percent / 100)
                            filled_size_usdt = partial_order_result.filled_size_usdt or (filled_amount * current_price)
                            
                            # 🔥 FIX: Si forcé à 100%, la position a été entièrement fermée par MEXC
                            # On marque la position comme vide, la prochaine vérification TP/SL 
                            # détectera que size_remaining = 0 et fermera proprement le trade
                            if getattr(partial_order_result, 'forced_full_close', False):
                                logger.info(
                                    f"🔧 [LIVE] TP forcé à 100% (position trop petite): {self.active_position.symbol} | "
                                    f"PnL: {partial_order_result.actual_pnl_usdt or 0:.2f} USDT | "
                                    f"Position fermée entièrement sur MEXC - clôture du trade..."
                                )
                                # Marquer position comme fermée
                                self.active_position.partial_tp_sold = True
                                self.active_position.size_remaining = 0
                                self.active_position.size_remaining_contracts = 0
                                self.active_position.position_size_contracts = 0
                                self.active_position.partial_profit_usdt = partial_order_result.actual_pnl_usdt or 0.0
                                # Retourner 'TP' pour que le scanner_loop ferme le trade
                                return 'TP'
                            
                            # Mettre à jour les contrats restants
                            remaining_contracts = max(size_contracts - filled_amount, 0)
                            remaining_usdt = max(self.active_position.size - filled_size_usdt, 0)

                            self.active_position.partial_tp_sold = True
                            self.active_position.size_remaining = remaining_usdt
                            self.active_position.position_size_contracts = remaining_contracts
                            self.active_position.size_remaining_contracts = remaining_contracts
                            if not self.active_position.size_initial_contracts:
                                self.active_position.size_initial_contracts = size_contracts
                            self.active_position.partial_profit_usdt = partial_order_result.actual_pnl_usdt or 0.0
                            
                            logger.info(
                                f"💰 [LIVE] TP Partiel exécuté: {self.active_position.symbol} | "
                                f"Vendu: {filled_amount:.4f} contrats ({filled_size_usdt:.2f} USDT) | "
                                f"Restant: {remaining_contracts:.4f} contrats ({remaining_usdt:.2f} USDT) | "
                                f"PnL: {partial_order_result.actual_pnl_usdt or 0:.2f} USDT"
                            )

                            # 📢 NOTIFICATION: TP Escalier level hit
                            if hasattr(self, 'notification_manager') and self.notification_manager:
                                try:
                                    import asyncio
                                    tp_data = {
                                        'symbol': self.active_position.symbol,
                                        'direction': self.active_position.direction,
                                        'level': 1,  # First TP partial
                                        'entry_price': self.active_position.entry,
                                        'exit_price': current_price,
                                        'sold_usdt': filled_size_usdt,
                                        'remaining_usdt': remaining_usdt,
                                        'pnl_usdt': partial_order_result.actual_pnl_usdt or 0.0,
                                        'pnl_pct': pnl
                                    }
                                    # Appel async non-bloquant
                                    try:
                                        loop = asyncio.get_event_loop()
                                        if loop.is_running():
                                            loop.create_task(
                                                self.notification_manager.notify('tp_escalier_level', tp_data, priority='info')
                                            )
                                        else:
                                            asyncio.run(self.notification_manager.notify('tp_escalier_level', tp_data, priority='info'))
                                    except RuntimeError:
                                        pass
                                except Exception as e:
                                    logger.debug(f"Erreur envoi notification tp_escalier_level: {e}")
                        else:
                            logger.error(
                                f"❌ [LIVE] Échec TP Partiel: {partial_order_result.error_message}"
                            )
                            # Ne pas marquer comme vendu si l'ordre a échoué
                            return None
                    except Exception as e:
                        logger.error(f"❌ Erreur TP Partiel LIVE: {e}")
                        return None
                else:
                    # Mode paper/dry-run: calcul local
                    partial_result = self.partial_tp.execute_partial_tp(
                        position=self.active_position.to_dict(),
                        current_price=current_price
                    )
                    self.active_position.partial_tp_sold = True
                    self.active_position.size_remaining = partial_result['size_remaining']
                    self.active_position.partial_profit_usdt = partial_result['profit_usdt']
                    entry_price = self.active_position.entry or current_price or 1
                    remaining_contracts = self.active_position.size_remaining / entry_price
                    initial_contracts = self.active_position.position_size_contracts or (self.active_position.size / entry_price)
                    
                    # 🔥 FIX: Mettre à jour size_initial_contracts si non défini OU si incohérent (tant que pas de TP partiel)
                    # Cela corrige le bug où size_initial était fixé à une mauvaise valeur (ex: 2452 au lieu de 2.45M)
                    if not self.active_position.size_initial_contracts or (not self.active_position.partial_tp_sold and abs(self.active_position.size_initial_contracts - initial_contracts) > initial_contracts * 0.1):
                        self.active_position.size_initial_contracts = initial_contracts
                        
                    self.active_position.position_size_contracts = remaining_contracts
                    self.active_position.size_remaining_contracts = remaining_contracts

                # Déplacer SL à break-even après le 1er TP
                new_sl = self.partial_tp.update_sl_after_partial_tp(
                    self.active_position.to_dict()
                )
                self.active_position.sl = new_sl
                self.active_position.break_even_set = True
                self._schedule_position_sync(self.active_position.symbol)
                
                logger.info(
                    f"💰 1er TP partiel déclenché à {break_even_trigger:.2f}% | "
                    f"Break-even activé | Trailing stop activé"
                )

        # 4. Trailing Stop (activé après le 1er TP partiel ou si PnL > trigger ATR)
        # 🔥 HYBRID: Trailing trigger basé sur ATR ou % fixe
        # Support both nested (trailing_stop.use_atr_trigger) and flat (trailing_use_atr_trigger) config keys
        trailing_config = TRADING_CONFIG.get('trailing_stop', {})
        use_atr_trigger = (
            trailing_config.get('use_atr_trigger', False) or 
            TRADING_CONFIG.get('trailing_use_atr_trigger', False)
        )
        
        if use_atr_trigger:
            # 🔥 Mode ATR: trigger dès PnL >= X × ATR%
            atr_pct = self._get_position_atr_percent()
            trigger_atr_mult = (
                trailing_config.get('trigger_atr_mult', 1.0) or
                TRADING_CONFIG.get('trailing_trigger_atr_mult', 1.0)
            )
            trailing_trigger = atr_pct * trigger_atr_mult
        else:
            # Mode FIXE
            trailing_trigger = (
                trailing_config.get('trigger_pnl') or
                TRADING_CONFIG.get('trailing_trigger_pnl', 0.15)
            )
        
        trailing_should_activate = self.active_position.partial_tp_sold or pnl >= trailing_trigger
        
        if trailing_should_activate:
            if pnl >= trailing_trigger:  # Remplace should_trigger()
                # 🔥 FIX: En mode FIXE, utiliser trailing_distance directement depuis TRADING_CONFIG
                tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
                if tp_sl_mode == 'FIXE':
                    # Mode FIXE : utiliser trailing_distance directement
                    trailing_distance = TRADING_CONFIG.get('trailing_distance', 0.15)
                    new_sl = self._update_trailing_stop_fixe(current_price, trailing_distance)
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

        # 5. 🔥 HYBRID: Stagnation Exit (Time Decay)
        stagnation_reason = self._check_stagnation_exit(pnl)
        if stagnation_reason:
            return stagnation_reason

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

    def _get_position_atr_percent(self) -> float:
        """
        🔥 HYBRID: Obtenir ATR% pour la position active
        
        Returns:
            ATR en pourcentage du prix d'entrée (ex: 0.35 pour 0.35%)
        """
        from config import TRADING_CONFIG  # 🔥 FIX: Import manquant
        
        if not self.active_position:
            return 0.5  # Fallback
        
        entry = self.active_position.entry
        atr = getattr(self.active_position, 'atr', None)
        
        if entry and entry > 0 and atr and atr > 0:
            atr_pct = (atr / entry) * 100
            # Clamp entre atr_min et atr_max
            atr_min = TRADING_CONFIG.get('atr_min', 0.10)
            atr_max = TRADING_CONFIG.get('atr_max', 1.0)
            atr_pct = max(atr_min, min(atr_max, atr_pct))
            return atr_pct
        else:
            # Fallback: moyenne raisonnable pour scalping
            return 0.35

    def _check_stagnation_exit(self, pnl: float) -> Optional[str]:
        """
        🔥 HYBRID: Vérifier si le trade doit être fermé pour stagnation (Time Decay)
        
        Args:
            pnl: PnL actuel en %
            
        Returns:
            'STAGNATION' si doit être fermé, None sinon
        """
        from config import TRADING_CONFIG  # 🔥 FIX: Import manquant
        from utils.effective_config import get_effective_value  # 🔥 NOUVEAU
        
        # 🔥 FIX: Prioriser les FLAT KEYS (mises à jour via frontend) sur le dict imbriqué
        stagnation_config = TRADING_CONFIG.get('stagnation_exit', {})
        
        # Enabled: flat key prioritaire
        enabled = TRADING_CONFIG.get('stagnation_exit_enabled', stagnation_config.get('enabled', False))
        if not enabled:
            return None
        
        if not self.active_position or not self.active_position.start_time:
            return None
        
        import time
        elapsed = time.time() - self.active_position.start_time
        
        # 🔥 Utiliser timeout dynamique du régime (position_timeout) si dispo, sinon config
        effective_timeout = get_effective_value('position_timeout')
        default_timeout = TRADING_CONFIG.get('stagnation_exit_timeout_seconds', stagnation_config.get('timeout_seconds', 120))
        
        timeout = effective_timeout if effective_timeout is not None else default_timeout
        
        # Pas encore timeout
        if elapsed < timeout:
            return None
        
        # 🔥 FIX: Flat keys prioritaires pour seuils
        min_pnl_to_stay = TRADING_CONFIG.get('stagnation_exit_min_pnl_to_stay', stagnation_config.get('min_pnl_to_stay', 0.10))
        max_loss_to_exit = TRADING_CONFIG.get('stagnation_exit_max_loss_to_exit', stagnation_config.get('max_loss_to_exit', -0.05))
        
        # Rester si PnL suffisant
        if pnl >= min_pnl_to_stay:
            return None
        
        # Sortir si perte ou stagnation après timeout
        if pnl < max_loss_to_exit or (pnl >= max_loss_to_exit and pnl < min_pnl_to_stay):
            logger.warning(
                f"⏰ STAGNATION EXIT {self.active_position.symbol}: "
                f"PnL={pnl:.2f}% après {elapsed:.0f}s (timeout={timeout}s)"
            )
            return 'STAGNATION'
        
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

    def close_position(self, exit_price: float, reason: str, skip_order: bool = False) -> Dict[str, Any]:
        """
        Fermer la position active

        Args:
            exit_price: Prix de sortie
            reason: Raison de fermeture (TP, SL, TS, EARLY_INVALIDATION, etc.)
            skip_order: Si True, ne pas envoyer d'ordre (position déjà fermée sur MEXC)

        Returns:
            Dict avec résultats du trade
        """
        # 🔥 FIX: Import TRADING_CONFIG au début pour éviter UnboundLocalError
        from config import TRADING_CONFIG
        
        if not self.active_position:
            raise ValueError("Aucune position active à fermer")
        
        # 🔥 FIX: Détecter si la position a déjà été fermée sur MEXC (TP forcé à 100%)
        # Dans ce cas, size_remaining_contracts = 0 et on ne doit pas envoyer d'ordre
        if (self.active_position.size_remaining_contracts == 0 and 
            self.active_position.partial_tp_sold and 
            reason == 'TP'):
            logger.info(
                f"📋 Position déjà fermée sur MEXC (TP forcé 100%): {self.active_position.symbol} | "
                f"Finalisation du trade sans envoyer d'ordre..."
            )
            skip_order = True

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

        if duration < MIN_LIVE_TRADE_DURATION_SEC and reason != 'SL':
            wait_time = MIN_LIVE_TRADE_DURATION_SEC - duration
            if wait_time > 0:
                logger.info(
                    f"⏳ Durée position {duration}s < {MIN_LIVE_TRADE_DURATION_SEC}s (raison={reason}). "
                    f"Attente {wait_time:.1f}s avant fermeture."
                )
                time.sleep(wait_time)
                duration = int(time.time() - self.active_position.start_time)

        # 🔥 FIX CRITIQUE: Limiter exit_price au SL + slippage maximum (éviter pertes > SL configuré)
        # Problème: Un trade a perdu -2.10% alors que SL = 0.20% (facteur x10 inacceptable)
        # Cause: Latence entre vérification et execution, prix peut dépasser largement le SL
        if reason in ['SL', 'EARLY_INVALIDATION']:
            from config import TRADING_CONFIG
            max_slippage_on_sl = TRADING_CONFIG.get('max_slippage_pct', 0.03)  # 0.03% max par défaut
            sl = self.active_position.sl
            entry = self.active_position.entry
            direction = self.active_position.direction
            
            if direction == 'LONG':
                # SL est en dessous de entry
                # Accepter max 0.03% de slippage sous le SL
                min_exit = sl * (1 - max_slippage_on_sl / 100)
                if exit_price < min_exit:
                    original_exit = exit_price
                    exit_price = min_exit  # Plafonner à SL - slippage max
                    exit_pnl = ((exit_price - entry) / entry) * 100
                    original_pnl = ((original_exit - entry) / entry) * 100
                    logger.warning(
                        f"🔴 SLIPPAGE EXTRÊME détecté sur SL: "
                        f"{self.active_position.symbol} | "
                        f"Prix original={original_exit:.8f} ({original_pnl:.2f}%) < "
                        f"SL={sl:.8f} ({((sl-entry)/entry)*100:.2f}%) | "
                        f"Prix plafonné={exit_price:.8f} ({exit_pnl:.2f}%) | "
                        f"Slippage max autorisé: {max_slippage_on_sl}%"
                    )
            else:  # SHORT
                # SL est au-dessus de entry
                max_exit = sl * (1 + max_slippage_on_sl / 100)
                if exit_price > max_exit:
                    original_exit = exit_price
                    exit_price = max_exit
                    exit_pnl = ((entry - exit_price) / entry) * 100
                    original_pnl = ((entry - original_exit) / entry) * 100
                    logger.warning(
                        f"🔴 SLIPPAGE EXTRÊME détecté sur SL: "
                        f"{self.active_position.symbol} | "
                        f"Prix original={original_exit:.8f} ({original_pnl:.2f}%) > "
                        f"SL={sl:.8f} ({((entry-sl)/entry)*100:.2f}%) | "
                        f"Prix plafonné={exit_price:.8f} ({exit_pnl:.2f}%) | "
                        f"Slippage max autorisé: {max_slippage_on_sl}%"
                    )

        # 🔥 LIVE TRADING: Fermer ordre réel si LiveOrderManager actif
        actual_exit_price = exit_price  # Prix par défaut (paper trading)
        actual_slippage_pct = 0.0
        requested_exit_price = exit_price

        if self.live_order_manager and not skip_order:
            try:
                # Calculer la taille en tokens (amount) depuis la taille en USDT
                size_amount = self.active_position.position_size_contracts
                if not size_amount:
                    entry_price = self.active_position.entry or 1
                    size_amount = (self.active_position.size / entry_price) if entry_price else 0

                order_result = self.live_order_manager.close_position(
                    symbol=self.active_position.symbol,
                    direction=self.active_position.direction,
                    entry_price=self.active_position.entry,
                    current_price=exit_price,
                    size_amount=size_amount,
                    partial_pct=None  # Full close
                )

                if order_result.success:
                    # Utiliser le prix réel et slippage réel
                    actual_exit_price = order_result.filled_price
                    actual_slippage_pct = order_result.actual_slippage_pct or 0.0
                    # 💾 Stocker métadonnées ordre de sortie
                    self.active_position.exit_order_id = order_result.order_id
                    self.active_position.exit_order_type = 'market'
                    self.active_position.exit_requested_price = requested_exit_price
                    self.active_position.exit_fill_price = order_result.filled_price
                    self.active_position.exit_slippage_pct = actual_slippage_pct
                    self.active_position.exit_latency_ms = order_result.latency_ms
                    self.active_position.exit_timestamp = order_result.executed_at
                    self.active_position.exit_fee_usdt = getattr(order_result, 'actual_fees_usdt', None)
                    self.active_position.time_to_fill_exit_ms = order_result.latency_ms
                    self.active_position.funding_rate_at_exit = getattr(order_result, 'funding_rate', None)
                    self.active_position.exit_api_response = getattr(order_result, 'raw_api_response', None)
                    entry_fees = self.active_position.entry_fee_usdt or 0.0
                    exit_fees = getattr(order_result, 'actual_fees_usdt', None) or 0.0
                    self.active_position.total_fees_usdt = entry_fees + exit_fees

                    # Calculer PnL réalisé depuis order_result
                    realized_pnl_usdt = order_result.actual_pnl_usdt or 0.0
                    realized_pnl_pct = (realized_pnl_usdt / self.active_position.size * 100) if self.active_position.size > 0 else 0.0

                    logger.info(
                        f"✅ Ordre LIVE fermé: {self.active_position.symbol} | "
                        f"Prix rempli: {order_result.filled_price:.8f} | "
                        f"Slippage: {actual_slippage_pct:.4f}% | "
                        f"PnL réalisé: {realized_pnl_usdt:.2f} USDT ({realized_pnl_pct:.2f}%)"
                    )
                else:
                    # 🔥 FIX: Détecter si position inexistante sur MEXC (code 2009)
                    # Cela signifie que la position a été fermée autrement (manuellement, liquidation, etc.)
                    error_msg = order_result.error_message or ""
                    # Note: FuturesOrderResult n'a pas error_code, seulement error_message
                    if "2009" in error_msg or "nonexistent" in error_msg.lower() or "closed" in error_msg.lower():
                        logger.warning(
                            f"⚠️ Position DÉJÀ FERMÉE sur MEXC: {self.active_position.symbol} | "
                            f"Message: {error_msg} | "
                            f"Fermeture locale (paper close) avec prix actuel"
                        )
                        # Marquer comme succès pour éviter boucle infinie
                        # La position est DÉJÀ fermée sur l'exchange
                        skip_order = True  # Ne plus réessayer
                    else:
                        logger.error(
                            f"❌ Ordre LIVE fermeture échoué: {self.active_position.symbol} | "
                            f"Erreur: {order_result.error_message} | "
                            f"Using paper trading exit price"
                        )
            except Exception as e:
                logger.error(f"❌ Erreur fermeture ordre LIVE: {e}")

        # Utiliser le prix de sortie réel (paper ou live)
        exit_price = actual_exit_price

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
        # 🔥 FIX Option B: Utiliser size_executed_usdt (taille réellement exécutée) pour précision
        # Si TP partiel, reconstruire la taille totale exécutée
        if self.active_position.partial_tp_sold:
            # Si TP partiel fait, size actuelle = reste, donc taille totale = size / (1 - partial_pct)
            partial_pct = TRADING_CONFIG.get('partial_tp_percent', 50.0) / 100.0
            size_for_pct = self.active_position.size / (1 - partial_pct) if partial_pct < 1 else self.active_position.size
        else:
            # Priorité: size_executed_usdt > size (taille actuelle)
            size_for_pct = getattr(self.active_position, 'size_executed_usdt', None) or self.active_position.size
        
        gross_pnl_pct = pnl_data['pnl_pct']
        
        # 🔥 FIX: Gestion robuste de la division par zéro
        if size_for_pct > 0:
            total_costs_pct = (total_costs / size_for_pct) * 100
        else:
            total_costs_pct = 0
            logger.warning(f"⚠️ Position size est zéro lors du calcul des coûts")
        
        # 🔥 FIX: net_pnl_usdt doit être calculé après déduction du slippage USDT
        net_pnl_usdt = pnl_data['net_pnl'] - slippage_usdt
        
        # 🔥 FIX CRITIQUE: Calculer net_pnl_pct directement depuis net_pnl_usdt / size_initial
        # Cela garantit cohérence parfaite: PnL % = PnL USDT / Size * 100
        if size_for_pct > 0:
            net_pnl_pct = (net_pnl_usdt / size_for_pct) * 100
        else:
            net_pnl_pct = gross_pnl_pct - total_costs_pct

        # Taille fermée
        if self.active_position.partial_tp_sold:
            size_closed = self.active_position.size_remaining or (self.active_position.size * 0.5)
        else:
            size_closed = self.active_position.size

        # Générer ID unique pour éviter doublons
        closure_id = str(uuid.uuid4())

        # Construire résultat
        # 🔥 FIX: Ajouter opened_at et closed_at pour l'affichage frontend
        # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
        opened_at = datetime.fromtimestamp(self.active_position.start_time).isoformat() if hasattr(self.active_position, 'start_time') else self.active_position.timestamp
        closed_at = datetime.now(timezone.utc).isoformat()
        
        result = {
            'symbol': self.active_position.symbol,
            'direction': self.active_position.direction,
            'entry': self.active_position.entry,
            'entry_price': self.active_position.entry,  # 🔥 FIX: Ajouté pour PostgreSQL log_trade
            'exit': exit_price,
            'exit_price': exit_price,  # 🔥 FIX: Alias pour compatibilité frontend
            # 🔥 FIX PRECISION: Conserver 6 décimales pour les pourcentages (éviter arrondi trop agressif)
            # Les petits trades gagnants (+0.05%) étaient affichés comme 0.00% après arrondi à 2 décimales
            'pnl_pct': round(pnl_data['pnl_pct'], 6),
            'pnl_usdt': round(net_pnl_usdt, 4),
            'gross_pnl_pct': round(pnl_data['pnl_pct'], 6),
            'slippage': round(slippage_pct, 6),  # 6 décimales pour précision
            'slippage_pct': round(slippage_pct, 6),  # Alias
            'slippage_usdt': round(slippage_usdt, 4),
            'gross_pnl_usdt': round(pnl_data['pnl_usdt_gross'], 4),
            'fees': round(pnl_data['fees'], 4),
            'total_costs': round(total_costs, 4),  # 4 décimales au lieu de 2
            'total_costs_usdt': round(total_costs, 4),
            'net_pnl': round(net_pnl_pct, 6),  # 6 décimales pour précision
            'net_pnl_pct': round(net_pnl_pct, 6),  # 6 décimales pour précision
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
            # 🔥 FIX Option B: Utiliser la taille exécutée (réelle) pour cohérence avec PnL
            'size': round(size_for_pct, 4),  # Taille utilisée pour calcul PnL
            'size_initial_usdt': getattr(self.active_position, 'size_initial_usdt', None),
            'size_executed_usdt': getattr(self.active_position, 'size_executed_usdt', None),  # 🔥 NEW
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
                        # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
                        timestamp_entry = datetime.now(timezone.utc).isoformat()
                    
                    # 🔥 FIX BUG #3: Utiliser timezone.utc pour PostgreSQL TIMESTAMPTZ
                    timestamp_exit = datetime.now(timezone.utc).isoformat()
                    
                    # Préparer config_snapshot complet (toutes les variables de configuration)
                    # 🔥 FIX BUG #1: Utiliser serialize_config_safe() pour éviter les erreurs de sérialisation
                    from config import (
                        TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS,
                        TREND_BONUS_CONFIG, RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG,
                        WEBSOCKET_CONFIG
                    )
                    from core.postgresql_datalogger import serialize_config_safe
                    config_snapshot = {}
                    # Copier TRADING_CONFIG avec sérialisation safe
                    if TRADING_CONFIG:
                        config_snapshot.update(serialize_config_safe(TRADING_CONFIG))
                    # Ajouter les variables définies séparément avec sérialisation safe
                    config_snapshot['RISK_CONFIG'] = serialize_config_safe(RISK_CONFIG) if RISK_CONFIG else {}
                    config_snapshot['CONDITION_WEIGHTS'] = serialize_config_safe(CONDITION_WEIGHTS) if CONDITION_WEIGHTS else {}
                    config_snapshot['TREND_BONUS_CONFIG'] = serialize_config_safe(TREND_BONUS_CONFIG) if TREND_BONUS_CONFIG else {}
                    config_snapshot['RETRY_CONFIG'] = serialize_config_safe(RETRY_CONFIG) if RETRY_CONFIG else {}
                    config_snapshot['CIRCUIT_BREAKER_CONFIG'] = serialize_config_safe(CIRCUIT_BREAKER_CONFIG) if CIRCUIT_BREAKER_CONFIG else {}
                    config_snapshot['WEBSOCKET_CONFIG'] = serialize_config_safe(WEBSOCKET_CONFIG) if WEBSOCKET_CONFIG else {}
                    
                    # Préparer indicateurs de sortie
                    # 🔥 FIX: Récupérer les indicateurs depuis pnl_history (dernier point)
                    # Note: analyze_timeframe est async, on utilise les indicateurs déjà collectés
                    exit_indicators = {}
                    try:
                        # Utiliser les derniers indicateurs du pnl_history si disponibles
                        if hasattr(self.active_position, 'pnl_history') and self.active_position.pnl_history:
                            last_entry = self.active_position.pnl_history[-1]
                            # Les indicateurs peuvent être stockés dans _last_indicators
                            last_indicators = getattr(self.active_position, '_last_indicators', {})
                            if last_indicators:
                                exit_indicators = last_indicators
                                logger.debug(f"📊 Exit indicators depuis _last_indicators: {exit_indicators}")
                        
                        # Si toujours vide, on laisse vide (évite RuntimeWarning en essayant d'appeler async depuis sync)
                        if not exit_indicators:
                            logger.debug("⚠️ Pas d'indicateurs de sortie disponibles (async call skipped)")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de récupérer exit_indicators: {e}")
                        exit_indicators = {}
                    
                    # 🔥 Déterminer le mode de trading (Live/Paper et Dry-Run)
                    is_live_trade = self.live_order_manager is not None
                    is_dry_run = getattr(self.live_order_manager, 'dry_run', True) if self.live_order_manager else False
                    live_execution_mode = 'DRY_RUN' if is_dry_run else ('LIVE_REAL' if is_live_trade else 'PAPER')
                    
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
                        # 🔥 LIVE TRADING MODE
                        'is_live_trade': is_live_trade,
                        'is_dry_run': is_dry_run,
                        'live_execution_mode': live_execution_mode,
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
                        'is_backtest': False,
                        # Métadonnées LIVE (si disponibles)
                        'entry_order_id': getattr(self.active_position, 'entry_order_id', None),
                        'entry_order_type': getattr(self.active_position, 'entry_order_type', None),
                        'entry_requested_price': getattr(self.active_position, 'entry_requested_price', None),
                        'entry_fill_price': getattr(self.active_position, 'entry_fill_price', None),
                        'entry_slippage_pct': getattr(self.active_position, 'entry_slippage_pct', None),
                        'entry_latency_ms': getattr(self.active_position, 'entry_latency_ms', None),
                        'entry_timestamp': getattr(self.active_position, 'entry_timestamp', None),
                        'exit_order_id': getattr(self.active_position, 'exit_order_id', None),
                        'exit_order_type': getattr(self.active_position, 'exit_order_type', None),
                        'exit_requested_price': getattr(self.active_position, 'exit_requested_price', None),
                        'exit_fill_price': getattr(self.active_position, 'exit_fill_price', None),
                        'exit_slippage_pct': getattr(self.active_position, 'exit_slippage_pct', None),
                        'exit_latency_ms': getattr(self.active_position, 'exit_latency_ms', None),
                        'exit_timestamp': getattr(self.active_position, 'exit_timestamp', None),
                        'entry_fee_usdt': getattr(self.active_position, 'entry_fee_usdt', None),
                        'exit_fee_usdt': getattr(self.active_position, 'exit_fee_usdt', None),
                        'total_fees_usdt': getattr(self.active_position, 'total_fees_usdt', None),
                        'position_size_usdt': getattr(self.active_position, 'position_size_usdt', None),
                        'position_size_contracts': getattr(self.active_position, 'position_size_contracts', None),
                        'margin_mode': getattr(self.active_position, 'margin_mode', None),
                        'margin_used': getattr(self.active_position, 'margin_used', None),
                        'leverage_used': getattr(self.active_position, 'leverage_used', None),
                        'liquidation_price': getattr(self.active_position, 'liquidation_price', None),
                        'time_to_fill_entry_ms': getattr(self.active_position, 'time_to_fill_entry_ms', None),
                        'time_to_fill_exit_ms': getattr(self.active_position, 'time_to_fill_exit_ms', None),
                        # Nouvelles métadonnées LIVE
                        'maker_fee_rate': getattr(self.active_position, 'maker_fee_rate', None),
                        'taker_fee_rate': getattr(self.active_position, 'taker_fee_rate', None),
                        'funding_rate_at_entry': getattr(self.active_position, 'funding_rate_at_entry', None),
                        'funding_rate_at_exit': getattr(self.active_position, 'funding_rate_at_exit', None),
                        'entry_api_response': getattr(self.active_position, 'entry_api_response', None),
                        'exit_api_response': getattr(self.active_position, 'exit_api_response', None),
                        # 🔥 FIX: Ajouter ml_confidence au trade (même valeur que dans scan_logs)
                        'ml_confidence': getattr(self.active_position, 'ml_confidence', None)
                    }
                    
                    # 🔥 SPRINT 1: Ajouter contexte Market Regime et Circuit Breaker
                    try:
                        from core.market_regime_selector import get_regime_selector
                        from utils.effective_config import get_effective_value
                        regime_selector = get_regime_selector()
                        regime_status = regime_selector.get_status()
                        trade_data['entry_market_regime'] = regime_status.get('current_regime', 'UNKNOWN')
                        trade_data['entry_market_regime_avg_atr'] = regime_status.get('avg_atr', 0)
                        trade_data['entry_market_regime_avg_adx'] = regime_status.get('avg_adx', 0)
                        # 🔥 FIX: Utiliser valeurs EFFECTIVES (régime) pas valeurs base
                        trade_data['entry_min_score_required'] = get_effective_value('min_score_required')
                        trade_data['entry_atr_mult_sl'] = get_effective_value('atr_mult_sl')
                        trade_data['entry_atr_mult_tp'] = get_effective_value('atr_mult_tp')
                        # 🔥 NOUVEAU: Paramètres dynamiques additionnels
                        trade_data['entry_volume_multiplier'] = get_effective_value('volume_multiplier')
                        trade_data['entry_rsi_filter_mode'] = get_effective_value('rsi_filter_mode')
                        trade_data['entry_position_timeout'] = get_effective_value('position_timeout')
                        trade_data['entry_optimal_atr_max_1m'] = get_effective_value('optimal_atr_max_1m')
                    except Exception as e:
                        logger.debug(f"⚠️ Impossible de récupérer régime: {e}")
                    
                    try:
                        from core.trading_circuit_breaker import get_trading_circuit_breaker
                        trading_cb = get_trading_circuit_breaker()
                        cb_status = trading_cb.get_status()
                        trade_data['entry_cb_state'] = cb_status.get('state', 'ACTIVE')
                        trade_data['entry_consecutive_losses'] = cb_status.get('consecutive_losses', 0)
                        trade_data['entry_daily_pnl_pct'] = cb_status.get('daily_pnl_pct', 0)
                        trade_data['entry_cb_score_boost'] = cb_status.get('score_boost', 0)
                    except Exception as e:
                        logger.debug(f"⚠️ Impossible de récupérer CB: {e}")
                    
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
                        
                        # 🔥 ML AUTO-CALIBRATION: Mettre à jour les stats après chaque trade
                        try:
                            from ml.calibration import get_calibration_manager
                            calib_manager = get_calibration_manager()
                            
                            # Récupérer les infos nécessaires
                            ml_conf = getattr(self.active_position, 'ml_confidence', None)
                            is_live = getattr(self.active_position, 'live_execution_mode', None) == 'LIVE'
                            is_dry = self.live_order_manager.dry_run if self.live_order_manager else True
                            trade_ts = datetime.fromtimestamp(
                                self.active_position.start_time,
                                tz=timezone.utc
                            ) if self.active_position.start_time else datetime.now(timezone.utc)
                            
                            if ml_conf and ml_conf >= 30:
                                calib_manager.update_calibration(
                                    direction=self.active_position.direction,
                                    ml_confidence=float(ml_conf),
                                    win=net_pnl_pct > 0,
                                    pnl_pct=net_pnl_pct,
                                    pnl_usdt=net_pnl_usdt,
                                    is_live=is_live,
                                    is_dry_run=is_dry,
                                    trade_timestamp=trade_ts
                                )
                                logger.debug(f"📊 Calibration ML mise à jour: {self.active_position.symbol}")
                        except Exception as calib_err:
                            logger.debug(f"Calibration update ignoré (non-bloquant): {calib_err}")
                            
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
                                    max_favorable_excursion=trade_data.get('max_pnl_reached'),
                                    max_adverse_excursion=trade_data.get('min_pnl_reached')
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
        is_win = net_pnl_pct > 0
        if is_win:
            self.config.win_streak += 1
            self.config.loss_streak = 0
        else:
            self.config.win_streak = 0
            self.config.loss_streak += 1

        # 🔥 PHASE 8: Enregistrer trade pour sizing adaptatif
        self.record_trade_for_adaptive_sizing(
            symbol=self.active_position.symbol,
            pnl_pct=net_pnl_pct,
            is_win=is_win
        )

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
        
        # 🔥 FIX: Déterminer is_dry_run depuis live_order_manager si actif
        is_dry_run_mode = None
        if self.live_order_manager:
            is_dry_run_mode = self.live_order_manager.dry_run
        
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
            mode='LIVE' if self.live_order_manager else 'PAPER',
            is_dry_run=is_dry_run_mode
        )

        # Réinitialiser position
        self.active_position = None

        logger.info(
            f"🔴 POSITION FERMÉE: {result['symbol']} | "
            f"Raison: {reason} | PnL net: {net_pnl_pct:.2f}% ({net_pnl_usdt:.4f} USDT) | "
            f"Slippage: {slippage_pct:.4f}% ({slippage_usdt:.4f} USDT)"
        )

        # 📢 NOTIFICATION: Position fermée
        if hasattr(self, 'notification_manager') and self.notification_manager:
            try:
                import asyncio
                notification_data = {
                    'symbol': result['symbol'],
                    'direction': result['direction'],
                    'entry_price': result['entry'],
                    'exit_price': result['exit'],
                    'size_usdt': result['size'],
                    'duration': result['duration'],
                    'result': result  # Include full result for notification_manager
                }
                # Appel async non-bloquant
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(
                            self.notification_manager.notify('position_closed', notification_data, priority='info')
                        )
                    else:
                        asyncio.run(self.notification_manager.notify('position_closed', notification_data, priority='info'))
                except RuntimeError:
                    # Pas de loop, ignorer notification
                    pass
            except Exception as e:
                logger.debug(f"Erreur envoi notification position_closed: {e}")

        # 📢 NOTIFICATION: Early invalidation (si applicable)
        if reason == 'EARLY_INVALIDATION' and hasattr(self, 'notification_manager') and self.notification_manager:
            try:
                import asyncio
                early_invalidation_data = {
                    'symbol': result['symbol'],
                    'direction': result['direction'],
                    'entry_price': result['entry'],
                    'exit_price': result['exit'],
                    'pnl_pct': pnl_data['pnl_pct'],
                    'duration': result['duration'],
                    'reason': 'Invalidation précoce'
                }
                # Appel async non-bloquant
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(
                            self.notification_manager.notify('early_invalidation', early_invalidation_data, priority='warning')
                        )
                    else:
                        asyncio.run(self.notification_manager.notify('early_invalidation', early_invalidation_data, priority='warning'))
                except RuntimeError:
                    pass
            except Exception as e:
                logger.debug(f"Erreur envoi notification early_invalidation: {e}")

        # 🔥 OPT #17: Enregistrer cooldown post-trade
        try:
            from core.analyzer.advanced_filters import get_cooldown_manager
            cooldown_mgr = get_cooldown_manager()
            cooldown_mgr.record_trade_close(result['symbol'], result['direction'])
            logger.debug(f"⏱️ Cooldown enregistré pour {result['symbol']} {result['direction']}")
        except Exception as e:
            logger.debug(f"Erreur enregistrement cooldown: {e}")

        # 🔥 SPRINT 1: Enregistrer trade dans Trading Circuit Breaker
        try:
            from core.trading_circuit_breaker import get_trading_circuit_breaker
            trading_cb = get_trading_circuit_breaker()
            can_continue = trading_cb.record_trade(
                symbol=result['symbol'],
                pnl_pct=net_pnl_pct,
                pnl_usdt=net_pnl_usdt
            )
            if not can_continue:
                logger.warning(
                    f"🛑 Trading Circuit Breaker activé après trade {result['symbol']} | "
                    f"État: {trading_cb.state.value} | Raison: {trading_cb.pause_reason}"
                )
        except Exception as e:
            logger.debug(f"Erreur enregistrement Trading Circuit Breaker: {e}")

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
