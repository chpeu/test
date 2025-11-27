#!/usr/bin/env python3
"""
Live Order Manager FUTURES - Trade Cursor v7.1
Gestion des ordres réels sur MEXC Futures (Perpetual Swaps)

SUPPORT:
- Positions LONG et SHORT
- Levier configurable (1x à 125x)
- Ordres Market et Limit
- Fermeture partielle/totale
- TP/SL via API (protection même si bot crash)
- Retry avec backoff exponentiel
- Synchronisation position réelle
- Emergency close
"""

import logging
import time
import asyncio
import ccxt
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
import json
from datetime import datetime, timezone
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================
class CircuitState(Enum):
    """États du circuit breaker"""
    CLOSED = "closed"      # Normal, requêtes passent
    OPEN = "open"          # Échecs critiques, requêtes bloquées
    HALF_OPEN = "half_open"  # Test de récupération


class CircuitBreaker:
    """
    Circuit Breaker pour arrêter automatiquement le trading après échecs consécutifs

    Protège contre:
    - Perte de connexion répétée
    - Token expiré
    - Problèmes d'API
    - Erreurs critiques en cascade

    États:
    - CLOSED: Normal (requêtes passent)
    - OPEN: Arrêt d'urgence (requêtes bloquées pendant recovery_timeout)
    - HALF_OPEN: Test si système est revenu (1 requête test)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        success_threshold: int = 2
    ):
        """
        Initialiser le circuit breaker

        Args:
            failure_threshold: Nombre d'échecs consécutifs avant ouverture (défaut 5)
            recovery_timeout: Temps d'attente avant test récupération en secondes (défaut 300s = 5min)
            success_threshold: Nombre de succès en HALF_OPEN pour fermer circuit (défaut 2)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.opened_at = 0

    def record_success(self):
        """Enregistrer un succès"""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("✅ Circuit Breaker FERMÉ - Système restauré")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def record_failure(self):
        """Enregistrer un échec"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0

        if self.state == CircuitState.HALF_OPEN:
            # Échec en test → réouvrir immédiatement
            logger.warning(f"❌ Circuit Breaker RÉOUVERT - Test échoué")
            self.state = CircuitState.OPEN
            self.opened_at = time.time()

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(
                    f"🚨 Circuit Breaker OUVERT - {self.failure_count} échecs consécutifs | "
                    f"Trading ARRÊTÉ pendant {self.recovery_timeout}s"
                )
                self.state = CircuitState.OPEN
                self.opened_at = time.time()

    def can_execute(self) -> Tuple[bool, str]:
        """
        Vérifier si une requête peut être exécutée

        Returns:
            Tuple (allowed, reason)
        """
        if self.state == CircuitState.CLOSED:
            return (True, "Circuit fermé")

        elif self.state == CircuitState.OPEN:
            # Vérifier si timeout expiré
            elapsed = time.time() - self.opened_at
            if elapsed >= self.recovery_timeout:
                logger.info(f"🔄 Circuit Breaker HALF-OPEN - Test de récupération (après {elapsed:.0f}s)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return (True, "Test de récupération")
            else:
                remaining = self.recovery_timeout - elapsed
                return (False, f"Circuit ouvert - attente {remaining:.0f}s avant test")

        elif self.state == CircuitState.HALF_OPEN:
            return (True, "Test en cours")

        return (False, "État inconnu")

    def get_status(self) -> Dict:
        """Récupérer le statut du circuit breaker"""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'opened_at': self.opened_at,
            'threshold': self.failure_threshold
        }


# ============================================================================
# RETRY DECORATOR avec Backoff Exponentiel
# ============================================================================
def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """
    Décorateur pour retry avec backoff exponentiel
    
    Args:
        max_retries: Nombre max de tentatives
        base_delay: Délai initial en secondes
        max_delay: Délai maximum en secondes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, 
                        ccxt.RequestTimeout, ccxt.DDoSProtection) as e:
                    last_exception = e
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"⚠️ Retry {attempt + 1}/{max_retries} après erreur: {e} | "
                        f"Attente: {delay:.1f}s"
                    )
                    time.sleep(delay)
                except Exception as e:
                    # Erreurs non-réseau: ne pas retry
                    raise e
            raise last_exception
        return wrapper
    return decorator


@dataclass
class FuturesOrderResult:
    """Résultat d'un ordre futures exécuté"""
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    filled_amount: Optional[float] = None
    actual_pnl_usdt: Optional[float] = None
    actual_fees_usdt: Optional[float] = None
    actual_slippage_pct: Optional[float] = None
    balance_after: Optional[float] = None
    margin_used: Optional[float] = None
    leverage: Optional[int] = None
    liquidation_price: Optional[float] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    executed_at: Optional[str] = None
    # 🔥 Nouvelles métadonnées LIVE
    maker_fee_rate: Optional[float] = None
    taker_fee_rate: Optional[float] = None
    funding_rate: Optional[float] = None
    raw_api_response: Optional[Dict[str, Any]] = None


class LiveOrderManagerFutures:
    """
    🔥 GESTIONNAIRE HYBRIDE: Bypass (primary) + CCXT (fallback)

    Gestionnaire d'ordres FUTURES MEXC (Perpetual Swaps)

    MODE HYBRIDE (si browser_token fourni):
    1. BYPASS en priorité (endpoints browser, pas de blocage API)
    2. CCXT en fallback automatique si bypass échoue
    3. Circuit Breaker: arrêt auto après 5 échecs consécutifs
    4. Token Health Monitor: check token toutes les 5min + alertes Telegram

    RESPONSABILITÉS:
    1. Configurer le levier
    2. Ouvrir position LONG ou SHORT
    3. Fermer position partielle/totale
    4. Récupérer infos position (PnL, liquidation, etc.)

    DIFFÉRENCES VS SPOT:
    - Utilise 'swap' au lieu de 'spot'
    - Gère le levier et la marge
    - Positions SHORT possibles
    - Calcul du prix de liquidation
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        default_leverage: int = 10,
        testnet: bool = False,
        dry_run: bool = True,
        browser_token: Optional[str] = None,
        telegram_notifier: Optional[Any] = None,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5
    ):
        """
        Initialiser le gestionnaire d'ordres futures

        Args:
            api_key: Clé API MEXC Futures
            api_secret: Secret API MEXC Futures
            default_leverage: Levier par défaut (1-125)
            testnet: Utiliser testnet (si disponible)
            dry_run: Mode simulation (pas d'ordres réels)
            browser_token: 🔥 Token browser pour bypass (optionnel)
            telegram_notifier: 🔥 Instance TelegramNotifier pour alertes (optionnel)
            enable_circuit_breaker: 🔥 Activer circuit breaker (défaut True)
            circuit_breaker_threshold: 🔥 Seuil échecs consécutifs (défaut 5)
        """
        self.dry_run = dry_run
        self.testnet = testnet
        self.default_leverage = min(125, max(1, default_leverage))
        self.telegram_notifier = telegram_notifier

        # 🔥 NOUVEAU: Mode hybride bypass + CCXT
        self.bypass_client = None
        self.bypass_enabled = False

        if browser_token and not dry_run:
            try:
                # Import dynamique pour éviter dépendance si pas utilisé
                from trading.mexc_futures_bypass import MexcFuturesBypass

                self.bypass_client = MexcFuturesBypass(
                    browser_token=browser_token,
                    timeout=10,
                    debug=False,
                    enable_token_monitor=True,
                    token_check_interval=300,  # 5 minutes
                    telegram_notifier=telegram_notifier
                )
                self.bypass_enabled = True
                logger.info("✅ Mode HYBRIDE activé: Bypass (primary) + CCXT (fallback)")

            except ImportError as e:
                logger.warning(f"⚠️ Bypass non disponible (import error): {e} | Mode CCXT seul")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation bypass: {e} | Mode CCXT seul")

        # Initialiser exchange MEXC Futures (toujours disponible en fallback)
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'timeout': 10000,  # 🔥 Timeout réduit à 10s (au lieu de défaut ~30s)
            'options': {
                'defaultType': 'swap',  # 🔥 FUTURES/Perpetual Swaps
                'adjustForTimeDifference': True,
                'defaultMarginMode': 'isolated',  # 🔥 Mode marge ISOLÉE (jamais croisé)
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.warning("⚠️ MEXC Futures testnet - utiliser dry_run=True pour tests")

        # 🔥 NOUVEAU: Circuit Breaker
        self.circuit_breaker = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_breaker_threshold,
                recovery_timeout=300,  # 5 minutes
                success_threshold=2
            )
            logger.info(f"✅ Circuit Breaker activé (seuil: {circuit_breaker_threshold} échecs)")

        # Statistiques étendues
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_failed': 0,
            'total_latency_ms': 0,
            'avg_latency_ms': 0,
            'total_pnl_usdt': 0.0,
            # 🔥 NOUVEAU: Stats bypass vs CCXT
            'bypass_success': 0,
            'bypass_failed': 0,
            'ccxt_fallback_used': 0,
            'circuit_breaker_blocks': 0,
        }

        # Cache des leviers par symbole
        self._leverage_cache: Dict[str, int] = {}

        logger.info(
            f"✅ LiveOrderManagerFutures initialisé | "
            f"Mode: {'DRY_RUN' if dry_run else ('HYBRID' if self.bypass_enabled else 'CCXT')} | "
            f"Levier défaut: {self.default_leverage}x"
        )

        # 🔥 Vérifier connectivité API en mode LIVE
        if not dry_run:
            try:
                balance = self.get_balance('USDT')
                logger.info(f"✅ API MEXC connectée | Balance USDT: {balance:.2f}")
            except Exception as api_error:
                logger.error(
                    f"❌ ERREUR API MEXC au démarrage: {api_error} | "
                    f"Vérifiez vos credentials et permissions Futures"
                )

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Configurer le levier pour un symbole

        Args:
            symbol: Paire (ex: BTC/USDT:USDT)
            leverage: Levier souhaité (1-125)

        Returns:
            True si succès
        """
        leverage = min(125, max(1, leverage))

        try:
            if self.dry_run:
                self._leverage_cache[symbol] = leverage
                logger.info(f"✅ [DRY_RUN] Levier {symbol} configuré à {leverage}x")
                return True

            # Appeler l'API pour configurer le levier
            # MEXC utilise setLeverage ou setMarginMode
            result = self.exchange.set_leverage(leverage, symbol)
            self._leverage_cache[symbol] = leverage

            logger.info(f"✅ Levier {symbol} configuré à {leverage}x")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur configuration levier {symbol}: {e}")
            return False

    def _convert_symbol_to_futures(self, symbol: str) -> str:
        """
        Convertir symbole standard en format futures MEXC

        Ex: BTC/USDT → BTC/USDT:USDT (perpetual)
        """
        if ':' not in symbol:
            # Ajouter le settlement currency
            base_quote = symbol.split('/')
            if len(base_quote) == 2:
                return f"{symbol}:{base_quote[1]}"
        return symbol

    def _convert_symbol_to_bypass(self, symbol: str) -> str:
        """
        Convertir symbole standard en format bypass

        Ex: BTC/USDT → BTC_USDT
        """
        # Retirer :USDT si présent
        symbol = symbol.replace(":USDT", "")
        # Remplacer / par _
        return symbol.replace("/", "_")

    async def start_monitoring(self):
        """🔥 Démarrer le monitoring token (si bypass activé)"""
        if self.bypass_client and hasattr(self.bypass_client, 'start_monitoring'):
            await self.bypass_client.start_monitoring()
            logger.info("✅ Token monitoring démarré")

    async def close_bypass(self):
        """🔥 Fermer le client bypass proprement"""
        if self.bypass_client and hasattr(self.bypass_client, 'close'):
            await self.bypass_client.close()
            logger.info("✅ Bypass client fermé")

    def get_health_status(self) -> Dict:
        """
        🔥 Récupérer le statut de santé complet du système

        Returns:
            Dict avec statuts circuit breaker, token monitor, rate limiter, etc.
        """
        health = {
            'mode': 'DRY_RUN' if self.dry_run else ('HYBRID' if self.bypass_enabled else 'CCXT'),
            'bypass_enabled': self.bypass_enabled,
            'stats': self.stats.copy()
        }

        # Circuit Breaker status
        if self.circuit_breaker:
            health['circuit_breaker'] = self.circuit_breaker.get_status()
        else:
            health['circuit_breaker'] = {'state': 'disabled'}

        # Token Monitor status (bypass)
        if self.bypass_client and hasattr(self.bypass_client, 'get_monitor_status'):
            health['token_monitor'] = self.bypass_client.get_monitor_status()
        else:
            health['token_monitor'] = {'running': False}

        # Rate Limiter stats (bypass)
        if self.bypass_client and hasattr(self.bypass_client, 'get_rate_limiter_stats'):
            health['rate_limiter'] = self.bypass_client.get_rate_limiter_stats()
        else:
            health['rate_limiter'] = {}

        return health

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        size_usdt: float,
        leverage: int = None
    ) -> FuturesOrderResult:
        """
        🔥 HYBRIDE: Ouvrir une position futures via Bypass (primary) ou CCXT (fallback)

        Logique:
        1. Vérifier Circuit Breaker
        2. Tenter BYPASS si activé
        3. Fallback CCXT si bypass échoue
        4. Enregistrer succès/échec dans Circuit Breaker

        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT
            entry_price: Prix d'entrée théorique
            size_usdt: Taille en USDT (marge × levier)
            leverage: Levier pour ce trade (défaut: self.default_leverage)

        Returns:
            FuturesOrderResult avec détails
        """
        start_time = time.time()
        leverage = leverage or self.default_leverage

        # 🔥 CIRCUIT BREAKER: Vérifier si trading autorisé
        if self.circuit_breaker:
            can_execute, reason = self.circuit_breaker.can_execute()
            if not can_execute:
                self.stats['circuit_breaker_blocks'] += 1
                logger.error(f"🚨 Circuit Breaker BLOQUE: {reason}")
                return FuturesOrderResult(
                    success=False,
                    error_message=f"Circuit breaker ouvert: {reason}",
                    latency_ms=(time.time() - start_time) * 1000
                )

        try:
            # Convertir symboles
            futures_symbol = self._convert_symbol_to_futures(symbol)
            bypass_symbol = self._convert_symbol_to_bypass(symbol)

            # Calcul quantité en contrats
            amount = size_usdt / entry_price

            # Ajuster quantité selon précision
            try:
                if not getattr(self.exchange, 'markets', None):
                    self.exchange.load_markets()
                market = self.exchange.market(futures_symbol)
                amount = float(self.exchange.amount_to_precision(futures_symbol, amount))

                limits = (market or {}).get('limits', {}) if market else {}
                min_amount = limits.get('amount', {}).get('min')
                max_amount = limits.get('amount', {}).get('max')

                if min_amount and amount < float(min_amount):
                    logger.error(
                        f"❌ Quantité insuffisante {futures_symbol}: {amount:.8f} < min {min_amount}"
                    )
                    return FuturesOrderResult(
                        success=False,
                        error_message=f"Quantité insuffisante: {amount:.8f} < min {min_amount}",
                        latency_ms=(time.time() - start_time) * 1000
                    )

                if max_amount and amount > float(max_amount):
                    amount = float(max_amount)

                if amount <= 0:
                    raise ValueError(f"Quantité invalide ({amount}) pour {futures_symbol}")
            except Exception as precision_err:
                logger.warning(f"⚠️ Impossible d'ajuster quantité {futures_symbol}: {precision_err}")

            side = 'buy' if direction == 'LONG' else 'sell'

            logger.info(
                f"📤 OUVERTURE {direction}: {symbol} | "
                f"Prix: {entry_price} | Size: {size_usdt} USDT | Leverage: {leverage}x | "
                f"Mode: {'DRY_RUN' if self.dry_run else ('HYBRID' if self.bypass_enabled else 'CCXT')}"
            )

            # DRY RUN: Simuler
            if self.dry_run:
                latency_ms = (time.time() - start_time) * 1000
                margin = size_usdt / leverage
                liq_price = entry_price * (1 - 1/leverage + 0.005) if direction == 'LONG' else entry_price * (1 + 1/leverage - 0.005)

                return FuturesOrderResult(
                    success=True,
                    order_id=f"dry_run_futures_{int(time.time())}",
                    filled_price=entry_price,
                    filled_amount=amount,
                    actual_pnl_usdt=0.0,
                    actual_fees_usdt=0.0,
                    actual_slippage_pct=0.0,
                    margin_used=margin,
                    leverage=leverage,
                    liquidation_price=liq_price,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat()
                )

            # 🔥 MODE HYBRIDE: Tenter BYPASS puis fallback CCXT
            bypass_tried = False
            bypass_error = None

            if self.bypass_enabled and self.bypass_client:
                bypass_tried = True
                try:
                    logger.info(f"🔄 Tentative BYPASS: {bypass_symbol}")

                    # Mapper direction → OrderSide
                    from trading.mexc_futures_bypass import OrderSide, OrderType, OpenType

                    order_side = OrderSide.OPEN_LONG if direction == 'LONG' else OrderSide.OPEN_SHORT

                    # Appel bypass (async)
                    result = asyncio.run(
                        self.bypass_client.submit_order(
                            symbol=bypass_symbol,
                            side=order_side,
                            vol=amount,
                            price=entry_price,
                            order_type=OrderType.MARKET,
                            open_type=OpenType.ISOLATED,
                            leverage=leverage
                        )
                    )

                    if result.success:
                        latency_ms = (time.time() - start_time) * 1000
                        self.stats['bypass_success'] += 1
                        self.stats['orders_placed'] += 1
                        self.stats['orders_filled'] += 1
                        self.stats['total_latency_ms'] += latency_ms
                        self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']

                        # 🔥 Circuit Breaker: enregistrer succès
                        if self.circuit_breaker:
                            self.circuit_breaker.record_success()

                        logger.info(
                            f"✅ BYPASS succès | Order ID: {result.order_id} | "
                            f"Latence: {latency_ms:.0f}ms"
                        )

                        return FuturesOrderResult(
                            success=True,
                            order_id=str(result.order_id),
                            filled_price=entry_price,
                            filled_amount=amount,
                            actual_fees_usdt=0.0,  # Bypass ne retourne pas fees directement
                            actual_slippage_pct=0.0,
                            margin_used=size_usdt / leverage,
                            leverage=leverage,
                            latency_ms=latency_ms,
                            executed_at=datetime.now(timezone.utc).isoformat()
                        )
                    else:
                        bypass_error = result.error_message
                        logger.warning(f"⚠️ BYPASS échec: {bypass_error} → Fallback CCXT")
                        self.stats['bypass_failed'] += 1

                except Exception as e:
                    bypass_error = str(e)
                    logger.warning(f"⚠️ BYPASS erreur: {e} → Fallback CCXT")
                    self.stats['bypass_failed'] += 1

            # 🔥 FALLBACK CCXT (toujours si bypass échoue ou désactivé)
            if bypass_tried:
                self.stats['ccxt_fallback_used'] += 1
                logger.info("🔄 Fallback CCXT activé")

            # Vérifier solde
            margin_required = size_usdt / leverage
            balance = self.get_balance('USDT')

            if balance < margin_required:
                return FuturesOrderResult(
                    success=False,
                    error_message=f"Solde insuffisant: {balance:.2f} USDT disponible, {margin_required:.2f} USDT requis",
                    latency_ms=(time.time() - start_time) * 1000
                )

            # Ordre CCXT
            position_type = 1 if direction == 'LONG' else 2
            self._leverage_cache[futures_symbol] = leverage

            # Retry avec backoff
            max_retries = 2
            last_error = None

            for attempt in range(max_retries):
                try:
                    order = self.exchange.create_order(
                        symbol=futures_symbol,
                        type='market',
                        side=side,
                        amount=amount,
                        params={
                            'leverage': str(leverage),
                            'openType': 1,
                            'positionType': position_type,
                            'type': 5,
                        }
                    )
                    break
                except (ccxt.NetworkError, ccxt.RequestTimeout) as retry_error:
                    last_error = retry_error
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Retry {attempt + 1}/{max_retries} dans {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        raise last_error

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price') or entry_price
            filled_amount = order.get('filled') or amount
            fee_info = order.get('fee', {})
            fees = fee_info.get('cost', 0.0) or 0.0
            slippage_pct = abs((filled_price - entry_price) / entry_price) * 100 if filled_price else 0
            margin_used = size_usdt / leverage

            # Stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']

            # 🔥 Circuit Breaker: enregistrer succès
            if self.circuit_breaker:
                self.circuit_breaker.record_success()

            logger.info(
                f"✅ CCXT succès | Order ID: {order_id} | "
                f"Prix: {filled_price} | Slippage: {slippage_pct:.3f}% | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                margin_used=margin_used,
                leverage=leverage,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat(),
                raw_api_response=order
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            # 🔥 Circuit Breaker: enregistrer échec
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()

            error_msg = str(e)
            if hasattr(e, 'args') and len(e.args) > 0 and isinstance(e.args[0], str):
                error_msg = e.args[0]

            logger.error(
                f"❌ Erreur ouverture position: {error_msg} | "
                f"Symbol: {symbol} | Direction: {direction} | "
                f"Leverage: {leverage}x | Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=False,
                error_message=error_msg,
                latency_ms=latency_ms
            )

    def close_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        current_price: float,
        size_amount: float,
        partial_pct: Optional[float] = None
    ) -> FuturesOrderResult:
        """
        Fermer une position futures (totale ou partielle)

        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT (de la position ouverte)
            entry_price: Prix d'entrée
            current_price: Prix actuel théorique
            size_amount: Quantité à fermer
            partial_pct: % à fermer (None = 100%)

        Returns:
            FuturesOrderResult avec PnL réel
        """
        start_time = time.time()

        try:
            # Convertir symbole
            futures_symbol = self._convert_symbol_to_futures(symbol)

            # Calcul quantité à fermer
            if partial_pct:
                amount = size_amount * (partial_pct / 100)
                logger.info(f"🔸 FERMETURE PARTIELLE {partial_pct}%: {amount:.6f}")
            else:
                amount = size_amount
                logger.info(f"🔸 FERMETURE TOTALE: {amount:.6f}")

            # Pour fermer: LONG → sell, SHORT → buy
            side = 'sell' if direction == 'LONG' else 'buy'
            order_type = 'market'

            # 🔢 Ajuster quantité fermée selon précision
            try:
                futures_symbol = self._convert_symbol_to_futures(symbol)
                if not getattr(self.exchange, 'markets', None):
                    self.exchange.load_markets()
                market = self.exchange.market(futures_symbol)
                amount = float(self.exchange.amount_to_precision(futures_symbol, amount))

                limits = (market or {}).get('limits', {}) if market else {}
                min_amount = limits.get('amount', {}).get('min')
                if min_amount and amount < float(min_amount):
                    amount = float(min_amount)
                if amount <= 0:
                    raise ValueError(
                        f"Quantité fermée invalide ({amount}) pour {futures_symbol}."
                    )
            except Exception as precision_err:
                logger.warning(f"⚠️ Impossible d'ajuster la quantité close {symbol}: {precision_err}")

            logger.info(
                f"📤 FERMETURE FUTURES {direction}: {futures_symbol} | "
                f"Prix théorique: {current_price} | "
                f"Quantité: {amount:.6f} | "
                f"Mode: {'DRY_RUN' if self.dry_run else 'LIVE'}"
            )

            # DRY RUN: Simuler fermeture
            if self.dry_run:
                latency_ms = (time.time() - start_time) * 1000

                # Calculer PnL
                if direction == 'LONG':
                    pnl_usdt = (current_price - entry_price) * amount
                else:  # SHORT
                    pnl_usdt = (entry_price - current_price) * amount

                self.stats['total_pnl_usdt'] += pnl_usdt

                logger.info(
                    f"✅ [DRY_RUN] Fermeture {direction} simulée | "
                    f"PnL: {pnl_usdt:+.2f} USDT | "
                    f"Latence: {latency_ms:.0f}ms"
                )

                return FuturesOrderResult(
                    success=True,
                    order_id=f"dry_run_close_futures_{int(time.time())}",
                    filled_price=current_price,
                    filled_amount=amount,
                    actual_pnl_usdt=pnl_usdt,
                    actual_fees_usdt=0.0,
                    actual_slippage_pct=0.0,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat()
                )

            # LIVE: Fermer position réelle (mode one-way, pas hedge)
            # 🔥 FIX: MEXC requiert leverage même pour fermeture en isolated margin
            leverage = self._leverage_cache.get(futures_symbol, self.default_leverage)
            # positionType: 1=long, 2=short (inverse de direction pour fermeture)
            position_type = 1 if direction == 'LONG' else 2
            
            # 🔥 Retry avec backoff pour fermeture aussi
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    order = self.exchange.create_order(
                        symbol=futures_symbol,
                        type=order_type,  # 'market'
                        side=side,
                        amount=amount,
                        params={
                            'reduceOnly': True,
                            'leverage': str(leverage),
                            'openType': 1,  # isolated margin
                            'positionType': position_type,  # même position_type que l'ouverture
                            'type': 5,  # 🔥 FIX: Forcer type 5 (market) pour MEXC API native
                        }
                    )
                    break  # Succès
                except (ccxt.NetworkError, ccxt.RequestTimeout) as retry_error:
                    last_error = retry_error
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"⚠️ Timeout fermeture (tentative {attempt + 1}/{max_retries}), "
                            f"retry dans {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        raise last_error

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price') or current_price
            filled_amount = order.get('filled') or amount
            fee_info = order.get('fee', {})
            fees = fee_info.get('cost', 0.0) or 0.0

            # Calculer PnL réel
            if direction == 'LONG':
                pnl_usdt = (filled_price - entry_price) * filled_amount
            else:
                pnl_usdt = (entry_price - filled_price) * filled_amount

            pnl_usdt -= fees  # Soustraire fees

            # Slippage
            slippage_pct = abs((filled_price - current_price) / current_price) * 100 if filled_price else 0

            # 🔥 Récupérer funding rate à la sortie
            funding_rate = None
            try:
                funding_info = self.exchange.fetch_funding_rate(futures_symbol)
                funding_rate = funding_info.get('fundingRate')
            except:
                pass

            # Mettre à jour stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']
            self.stats['total_pnl_usdt'] += pnl_usdt

            logger.info(
                f"✅ Position FUTURES {direction} fermée | "
                f"Order ID: {order_id} | "
                f"Prix rempli: {filled_price} | "
                f"PnL: {pnl_usdt:+.2f} USDT | "
                f"Fees: {fees:.4f} USDT | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                actual_pnl_usdt=pnl_usdt,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat(),
                funding_rate=funding_rate,
                raw_api_response=order
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            logger.error(f"❌ Erreur fermeture position futures: {e}")

            return FuturesOrderResult(
                success=False,
                error_message=str(e),
                latency_ms=latency_ms
            )

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupérer infos position ouverte

        Returns:
            Dict avec size, entryPrice, unrealizedPnl, liquidationPrice, etc.
        """
        try:
            if self.dry_run:
                return None

            futures_symbol = self._convert_symbol_to_futures(symbol)
            positions = self.exchange.fetch_positions([futures_symbol])

            for pos in positions:
                if pos.get('symbol') == futures_symbol and float(pos.get('contracts', 0)) > 0:
                    return {
                        'symbol': futures_symbol,
                        'side': pos.get('side'),
                        'size': float(pos.get('contracts', 0)),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                        'margin': float(pos.get('initialMargin', 0)),
                        'leverage': int(pos.get('leverage', 1)),
                    }

            return None

        except Exception as e:
            logger.error(f"❌ Erreur récupération position: {e}")
            return None

    def get_balance(self, currency: str = 'USDT') -> float:
        """Récupérer balance disponible futures"""
        try:
            if self.dry_run:
                return 0.0

            balance = self.exchange.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0.0))

        except Exception as e:
            logger.error(f"❌ Erreur récupération balance futures: {e}")
            return 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Récupérer statistiques d'utilisation"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['orders_filled'] / self.stats['orders_placed'] * 100
                if self.stats['orders_placed'] > 0 else 0.0
            )
        }

    # ========================================================================
    # 🔥 NOUVELLES FONCTIONNALITÉS v7.1
    # ========================================================================

    @retry_with_backoff(max_retries=3)
    def set_stop_loss_take_profit(
        self,
        symbol: str,
        direction: str,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ) -> bool:
        """
        Définir TP/SL via API MEXC (protection même si bot crash)
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT
            stop_loss_price: Prix stop loss
            take_profit_price: Prix take profit
            
        Returns:
            True si succès
        """
        try:
            if self.dry_run:
                logger.info(
                    f"✅ [DRY_RUN] TP/SL configuré: {symbol} | "
                    f"SL: {stop_loss_price} | TP: {take_profit_price}"
                )
                return True

            futures_symbol = self._convert_symbol_to_futures(symbol)
            
            # Récupérer position existante
            positions = self.exchange.fetch_positions([futures_symbol])
            position = None
            for pos in positions:
                if pos.get('symbol') == futures_symbol and float(pos.get('contracts', 0)) > 0:
                    position = pos
                    break
            
            if not position:
                logger.warning(f"⚠️ Pas de position ouverte pour {symbol}")
                return False

            # Créer ordres SL/TP via MEXC API
            params = {}
            if stop_loss_price:
                params['stopLossPrice'] = stop_loss_price
            if take_profit_price:
                params['takeProfitPrice'] = take_profit_price

            # Utiliser l'endpoint de modification de position
            # Note: MEXC utilise des ordres conditionnels pour TP/SL
            if stop_loss_price:
                sl_side = 'sell' if direction == 'LONG' else 'buy'
                self.exchange.create_order(
                    symbol=futures_symbol,
                    type='stop_market',
                    side=sl_side,
                    amount=float(position.get('contracts', 0)),
                    params={
                        'stopPrice': stop_loss_price,
                        'reduceOnly': True,
                        # 🔥 FIX: Pas de positionSide en mode one-way
                    }
                )
                logger.info(f"✅ Stop Loss configuré: {symbol} @ {stop_loss_price}")

            if take_profit_price:
                tp_side = 'sell' if direction == 'LONG' else 'buy'
                self.exchange.create_order(
                    symbol=futures_symbol,
                    type='take_profit_market',
                    side=tp_side,
                    amount=float(position.get('contracts', 0)),
                    params={
                        'stopPrice': take_profit_price,
                        'reduceOnly': True,
                        # 🔥 FIX: Pas de positionSide en mode one-way
                    }
                )
                logger.info(f"✅ Take Profit configuré: {symbol} @ {take_profit_price}")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur configuration TP/SL: {e}")
            return False

    def sync_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Synchroniser position locale avec position réelle sur MEXC
        
        Args:
            symbol: Paire à synchroniser
            
        Returns:
            Dict avec position réelle ou None si pas de position
        """
        try:
            if self.dry_run:
                return None

            real_position = self.get_position(symbol)
            
            if real_position:
                logger.info(
                    f"🔄 Position synchronisée: {symbol} | "
                    f"Size: {real_position['size']} | "
                    f"Entry: {real_position['entry_price']} | "
                    f"PnL: {real_position['unrealized_pnl']:+.2f} USDT"
                )
            else:
                logger.info(f"🔄 Aucune position ouverte sur {symbol}")
                
            return real_position

        except Exception as e:
            logger.error(f"❌ Erreur synchronisation: {e}")
            return None

    @retry_with_backoff(max_retries=5, base_delay=0.5)
    def emergency_close_all(self) -> List[FuturesOrderResult]:
        """
        🚨 FERMETURE D'URGENCE de toutes les positions
        
        Returns:
            Liste des résultats de fermeture
        """
        results = []
        
        try:
            if self.dry_run:
                logger.warning("🚨 [DRY_RUN] Emergency close simulé")
                return [FuturesOrderResult(success=True, order_id="emergency_dry_run")]

            # Récupérer toutes les positions ouvertes
            positions = self.exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]

            if not open_positions:
                logger.info("✅ Aucune position à fermer")
                return []

            logger.warning(f"🚨 EMERGENCY CLOSE: {len(open_positions)} positions à fermer")

            for pos in open_positions:
                symbol = pos.get('symbol')
                size = float(pos.get('contracts', 0))
                side = pos.get('side')  # 'long' ou 'short'
                entry_price = float(pos.get('entryPrice', 0))

                # Fermer avec ordre market
                close_side = 'sell' if side == 'long' else 'buy'
                
                try:
                    order = self.exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=close_side,
                        amount=size,
                        params={
                            'reduceOnly': True,
                            # 🔥 FIX: Pas de positionSide en mode one-way
                        }
                    )
                    
                    results.append(FuturesOrderResult(
                        success=True,
                        order_id=order.get('id'),
                        filled_price=order.get('average'),
                        filled_amount=size
                    ))
                    
                    logger.warning(
                        f"🚨 Position fermée: {symbol} | "
                        f"Size: {size} | Entry: {entry_price}"
                    )
                    
                except Exception as e:
                    logger.error(f"❌ Erreur fermeture {symbol}: {e}")
                    results.append(FuturesOrderResult(
                        success=False,
                        error_message=str(e)
                    ))

            return results

        except Exception as e:
            logger.error(f"❌ Erreur emergency close: {e}")
            return [FuturesOrderResult(success=False, error_message=str(e))]

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        Récupérer toutes les positions ouvertes
        
        Returns:
            Liste des positions avec détails
        """
        try:
            if self.dry_run:
                return []

            positions = self.exchange.fetch_positions()
            open_positions = []
            
            for pos in positions:
                if float(pos.get('contracts', 0)) > 0:
                    open_positions.append({
                        'symbol': pos.get('symbol'),
                        'side': pos.get('side'),
                        'size': float(pos.get('contracts', 0)),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                        'leverage': int(pos.get('leverage', 1)),
                        'margin': float(pos.get('initialMargin', 0)),
                        'margin_ratio': float(pos.get('marginRatio', 0)),
                    })

            return open_positions

        except Exception as e:
            logger.error(f"❌ Erreur récupération positions: {e}")
            return []

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Récupérer le funding rate actuel
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            
        Returns:
            Funding rate en % ou None
        """
        try:
            futures_symbol = self._convert_symbol_to_futures(symbol)
            funding = self.exchange.fetch_funding_rate(futures_symbol)
            rate = funding.get('fundingRate', 0) * 100  # Convertir en %
            
            logger.debug(f"📊 Funding rate {symbol}: {rate:+.4f}%")
            return rate

        except Exception as e:
            logger.error(f"❌ Erreur funding rate: {e}")
            return None

    def check_liquidation_risk(self, symbol: str, threshold_pct: float = 5.0) -> Tuple[bool, float]:
        """
        Vérifier le risque de liquidation
        
        Args:
            symbol: Paire
            threshold_pct: Seuil d'alerte en % (distance au prix de liquidation)
            
        Returns:
            (is_at_risk, distance_pct)
        """
        try:
            position = self.get_position(symbol)
            
            if not position:
                return (False, 100.0)

            entry_price = position['entry_price']
            liq_price = position['liquidation_price']
            mark_price = position.get('mark_price', entry_price)
            side = position['side']

            if side == 'long':
                distance_pct = ((mark_price - liq_price) / mark_price) * 100
            else:
                distance_pct = ((liq_price - mark_price) / mark_price) * 100

            is_at_risk = distance_pct < threshold_pct

            if is_at_risk:
                logger.warning(
                    f"⚠️ RISQUE LIQUIDATION: {symbol} | "
                    f"Distance: {distance_pct:.2f}% (seuil: {threshold_pct}%)"
                )

            return (is_at_risk, distance_pct)

        except Exception as e:
            logger.error(f"❌ Erreur vérification liquidation: {e}")
            return (False, 100.0)


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    """Exemple d'utilisation du LiveOrderManagerFutures"""

    # Configuration
    API_KEY = "your_mexc_futures_api_key"
    API_SECRET = "your_mexc_futures_api_secret"

    # Initialiser en mode DRY_RUN
    order_manager = LiveOrderManagerFutures(
        api_key=API_KEY,
        api_secret=API_SECRET,
        default_leverage=10,
        dry_run=True
    )

    # Exemple 1: Ouvrir position SHORT BTC avec levier 10x
    print("\n=== OUVERTURE SHORT ===")
    result_open = order_manager.open_position(
        symbol='BTC/USDT',
        direction='SHORT',
        entry_price=50000.0,
        size_usdt=100.0,  # 100 USDT de marge × 10x = 1000 USDT notionnel
        leverage=10
    )

    if result_open.success:
        print(f"✅ Position SHORT ouverte | Order ID: {result_open.order_id}")
        print(f"   Prix rempli: {result_open.filled_price}")
        print(f"   Levier: {result_open.leverage}x")
        print(f"   Prix liquidation: {result_open.liquidation_price}")
    else:
        print(f"❌ Échec: {result_open.error_message}")

    # Simuler attente
    time.sleep(1)

    # Exemple 2: Fermer position avec profit (prix a baissé)
    print("\n=== FERMETURE SHORT ===")
    result_close = order_manager.close_position(
        symbol='BTC/USDT',
        direction='SHORT',
        entry_price=50000.0,
        current_price=49000.0,  # -2% = profit pour SHORT
        size_amount=result_open.filled_amount
    )

    if result_close.success:
        print(f"✅ Position fermée | Order ID: {result_close.order_id}")
        print(f"   PnL réel: {result_close.actual_pnl_usdt:+.2f} USDT")
    else:
        print(f"❌ Échec: {result_close.error_message}")

    # Stats
    print("\n=== STATISTIQUES ===")
    stats = order_manager.get_stats()
    print(f"Ordres placés: {stats['orders_placed']}")
    print(f"PnL total: {stats['total_pnl_usdt']:+.2f} USDT")
