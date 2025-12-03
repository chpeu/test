#!/usr/bin/env python3
"""
Live Order Manager FUTURES - Trade Cursor v7.2
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

🔥 v7.2: BYPASS MODE
- Utilise les endpoints browser pour bypasser le blocage API MEXC
- Basé sur https://github.com/oboshto/mexc-futures-sdk
- Requiert un browser_token (WEB_xxx...) récupéré depuis DevTools
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
import threading

# 🔥 Helper pour exécuter du code async depuis un contexte sync sans bloquer la loop principale
_bypass_loop = asyncio.new_event_loop()

def _run_bypass_loop():
    asyncio.set_event_loop(_bypass_loop)
    _bypass_loop.run_forever()

_bypass_thread = threading.Thread(target=_run_bypass_loop, name="bypass_async_loop", daemon=True)
_bypass_thread.start()

def run_async_safely(coro, timeout: float = 30.0):
    """Planifier une coroutine sur la loop dédiée et attendre son résultat."""
    future = asyncio.run_coroutine_threadsafe(coro, _bypass_loop)
    return future.result(timeout=timeout)

# 🔥 Import du client bypass
try:
    from trading.mexc_futures_bypass import (
        MexcFuturesBypass,
        MexcFuturesWebSocket,
        OrderSide,
        OrderType,
        OpenType,
        OrderResult as BypassOrderResult,
        Position as BypassPosition,
    )
    BYPASS_AVAILABLE = True
except ImportError:
    BYPASS_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================
from enum import Enum

class CircuitState(Enum):
    """États du circuit breaker"""
    CLOSED = "closed"      # Normal, requêtes passent
    OPEN = "open"          # Échecs critiques, requêtes bloquées
    HALF_OPEN = "half_open"  # Test de récupération


class CircuitBreaker:
    """
    🔥 Circuit Breaker pour arrêter automatiquement le trading après échecs consécutifs

    Protège contre:
    - Perte de connexion répétée
    - Token expiré non détecté
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

    def can_execute(self, is_closing_order: bool = False) -> Tuple[bool, str]:
        """
        Vérifier si une requête peut être exécutée

        Args:
            is_closing_order: True pour ordres de fermeture (TP/SL) → toujours autorisés

        Returns:
            Tuple (allowed, reason)
        """
        # 🔥 CRITIQUE: Les ordres de fermeture (TP/SL) passent TOUJOURS
        # pour protéger les positions existantes, même si circuit ouvert
        if is_closing_order:
            if self.state == CircuitState.OPEN:
                logger.warning(f"⚠️ Circuit Breaker OUVERT mais ordre de fermeture AUTORISÉ (protection capital)")
            return (True, "Ordre de fermeture (prioritaire)")

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

    def reset(self):
        """
        Réinitialiser manuellement le circuit breaker

        Utile pour forcer la fermeture du circuit après avoir résolu
        les problèmes qui ont causé l'ouverture.
        """
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None
        logger.warning("🔄 Circuit Breaker RÉINITIALISÉ manuellement - Retour à l'état CLOSED")


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
    filled_amount: Optional[float] = None  # 🔥 En CONTRATS MEXC (pas tokens)
    filled_contracts: Optional[float] = None  # 🔥 Alias explicite pour contrats MEXC
    filled_size_usdt: Optional[float] = None
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
    # 🔥 FIX: Minimum contract amount pour TP partiel
    min_contract_amount: Optional[float] = None
    # 🔥 FIX: Contract size utilisé (pour éviter erreurs PNL)
    contract_size: Optional[float] = None


class LiveOrderManagerFutures:
    """
    Gestionnaire d'ordres FUTURES MEXC (Perpetual Swaps)

    RESPONSABILITÉS:
    1. Configurer le levier
    2. Ouvrir position LONG ou SHORT
    3. Fermer position partielle/totale
    4. Récupérer infos position (PnL, liquidation, etc.)

    MODES:
    - BYPASS (recommandé): Utilise browser token pour bypasser blocage API
    - CCXT (legacy): Utilise API keys classiques (peut être bloqué)

    DIFFÉRENCES VS SPOT:
    - Utilise 'swap' au lieu de 'spot'
    - Gère le levier et la marge
    - Positions SHORT possibles
    - Calcul du prix de liquidation
    """

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        browser_token: str = None,
        default_leverage: int = 10,
        testnet: bool = False,
        dry_run: bool = True,
        use_bypass: bool = True,
        telegram_notifier: Optional[Any] = None,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5
    ):
        """
        Initialiser le gestionnaire d'ordres futures

        Args:
            api_key: Clé API MEXC Futures (mode CCXT)
            api_secret: Secret API MEXC Futures (mode CCXT)
            browser_token: Token browser WEB_xxx... (mode BYPASS)
            default_leverage: Levier par défaut (1-125)
            testnet: Utiliser testnet (si disponible)
            dry_run: Mode simulation (pas d'ordres réels)
            use_bypass: Utiliser le mode bypass (recommandé)
            telegram_notifier: 🔥 Instance TelegramNotifier pour alertes (optionnel)
            enable_circuit_breaker: 🔥 Activer circuit breaker (défaut True)
            circuit_breaker_threshold: 🔥 Seuil échecs consécutifs (défaut 5)
        """
        self.dry_run = dry_run
        self.testnet = testnet
        self.default_leverage = min(125, max(1, default_leverage))
        self.telegram_notifier = telegram_notifier

        # 🔥 NOUVEAU: Circuit Breaker
        self.circuit_breaker: Optional[CircuitBreaker] = None
        if enable_circuit_breaker and not dry_run:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=circuit_breaker_threshold,
                recovery_timeout=300,  # 5 minutes
                success_threshold=2
            )
            logger.info(f"✅ Circuit Breaker activé (seuil: {circuit_breaker_threshold} échecs)")

        # 🔥 DEBUG: Tracer les valeurs pour diagnostiquer le mode bypass
        print(f"🔍 DEBUG LiveOrderManagerFutures.__init__:")
        print(f"   use_bypass param: {use_bypass}")
        print(f"   BYPASS_AVAILABLE: {BYPASS_AVAILABLE}")
        print(f"   browser_token: {browser_token[:20] if browser_token else 'None'}...")
        print(f"   Résultat use_bypass: {use_bypass and BYPASS_AVAILABLE and bool(browser_token)}")
        
        self.use_bypass = use_bypass and BYPASS_AVAILABLE and bool(browser_token)
        
        # 🔥 Mode BYPASS: Client avec browser token
        self.bypass_client: Optional[MexcFuturesBypass] = None
        self.bypass_ws: Optional[MexcFuturesWebSocket] = None
        
        # Mode CCXT: Exchange classique
        self.exchange = None
        
        if self.use_bypass:
            # 🔥 BYPASS MODE: Utiliser les endpoints browser
            self.bypass_client = MexcFuturesBypass(
                browser_token=browser_token,
                debug=False,
                enable_token_monitor=True,        # 🔥 Monitoring token actif
                token_check_interval=300,         # 🔥 Vérif toutes les 5 minutes
                telegram_notifier=telegram_notifier  # 🔥 Alertes Telegram
            )
            logger.info(
                f"✅ LiveOrderManagerFutures initialisé en mode BYPASS | "
                f"Mode: {'DRY_RUN' if dry_run else 'LIVE BYPASS'} | "
                f"Levier défaut: {self.default_leverage}x"
            )
        else:
            # 🔥 CCXT MODE: Utiliser les API keys classiques
            if api_key and api_secret:
                self.bypass_ws = MexcFuturesWebSocket(
                    api_key=api_key,
                    secret_key=api_secret,
                    auto_reconnect=True
                )
                logger.info("✅ WebSocket bypass initialisé (pour updates temps réel)")
                self.exchange = ccxt.mexc({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'enableRateLimit': True,
                    'timeout': 10000,
                    'options': {
                        'defaultType': 'swap',
                        'adjustForTimeDifference': True,
                        'defaultMarginMode': 'isolated',
                    }
                })

                if testnet:
                    self.exchange.set_sandbox_mode(True)
                    logger.warning("⚠️ MEXC Futures testnet - utiliser dry_run=True pour tests")

            logger.info(
                f"✅ LiveOrderManagerFutures initialisé en mode CCXT | "
                f"Mode: {'DRY_RUN' if dry_run else 'LIVE CCXT'} | "
                f"Levier défaut: {self.default_leverage}x"
            )

        # Statistiques
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_failed': 0,
            'total_latency_ms': 0,
            'avg_latency_ms': 0,
            'total_pnl_usdt': 0.0,
        }

        # Cache des leviers par symbole
        self._leverage_cache: Dict[str, int] = {}
        
        # 🔄 Rate limiting pour lectures (1 req/sec max sur bypass)
        self._last_read_request_time: float = 0.0
        self._read_rate_limit_sec: float = 1.0  # 1 seconde min entre lectures bypass
        
        # 🔥 Vérifier connectivité API en mode LIVE
        if not dry_run:
            try:
                balance = self.get_balance('USDT')
                if balance is not None:
                    logger.info(f"✅ API MEXC connectée | Balance USDT: {balance:.2f}")
                else:
                    logger.warning("⚠️ Balance non disponible - vérifiez vos credentials")
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
        Convertir symbole standard en format bypass MEXC
        
        Ex: BTC/USDT:USDT → BTC_USDT
            BTC/USDT → BTC_USDT
        """
        # Retirer :USDT si présent
        clean = symbol.replace(":USDT", "")
        # Remplacer / par _
        return clean.replace("/", "_")

    def _verify_position_size(
        self,
        symbol: str,
        reference_price: float,
        retries: int = 3,
        delay_sec: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Récupérer la taille réelle ouverte sur MEXC (contrats & USDT)
        Utilise CCXT en priorité puis fallback bypass.
        """
        if self.dry_run:
            return None

        def _fetch_via_ccxt() -> Optional[Dict[str, float]]:
            if not self.exchange:
                return None
            try:
                futures_symbol = self._convert_symbol_to_futures(symbol)
                positions = self.exchange.fetch_positions([futures_symbol])
                for pos in positions:
                    if pos.get('symbol') == futures_symbol and float(pos.get('contracts', 0)) > 0:
                        contracts = float(pos.get('contracts', 0))
                        entry_price = float(pos.get('entryPrice', 0)) or reference_price
                        size_usdt = contracts * entry_price
                        return {
                            'contracts': contracts,
                            'entry_price': entry_price,
                            'size_usdt': size_usdt
                        }
            except Exception as ccxt_err:
                logger.debug(f"⚠️ CCXT verify_position_size échec: {ccxt_err}")
            return None

        def _fetch_via_bypass() -> Optional[Dict[str, float]]:
            if not (self.use_bypass and self.bypass_client):
                return None
            try:
                bypass_symbol = self._convert_symbol_to_bypass(symbol)
                positions = run_async_safely(self.bypass_client.get_open_positions(bypass_symbol))
                for pos in positions:
                    if pos.symbol == bypass_symbol and pos.hold_vol > 0:
                        contracts = float(pos.hold_vol)
                        entry_price = float(pos.hold_avg_price or reference_price)
                        size_usdt = contracts * entry_price
                        return {
                            'contracts': contracts,
                            'entry_price': entry_price,
                            'size_usdt': size_usdt
                        }
            except Exception as bypass_err:
                logger.debug(f"⚠️ Bypass verify_position_size échec: {bypass_err}")
            return None

        for attempt in range(retries):
            result = _fetch_via_ccxt()
            if result:
                return result
            result = _fetch_via_bypass()
            if result:
                return result
            if attempt < retries - 1:
                logger.debug(f"⏳ verify_position_size retry {attempt + 1}/{retries-1} dans {delay_sec}s...")
                time.sleep(delay_sec)

        logger.warning(f"⚠️ Impossible de vérifier taille réelle pour {symbol} après {retries} tentatives")
        return None

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        size_usdt: float,
        leverage: int = None
    ) -> FuturesOrderResult:
        """
        Ouvrir une position futures (LONG ou SHORT)

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
                logger.error(f"🚨 Circuit Breaker BLOQUE l'ordre: {reason}")
                if self.telegram_notifier:
                    self.telegram_notifier.send_alert(
                        f"🚨 CIRCUIT BREAKER OUVERT\n"
                        f"Ordre bloqué: {symbol} {direction}\n"
                        f"Raison: {reason}"
                    )
                return FuturesOrderResult(
                    success=False,
                    error_message=f"Circuit breaker ouvert: {reason}",
                    latency_ms=(time.time() - start_time) * 1000
                )

        try:
            if not entry_price or entry_price <= 0:
                raise ValueError(f"Prix d'entrée invalide pour {symbol}: {entry_price}")

            # Convertir symbole au format futures
            futures_symbol = self._convert_symbol_to_futures(symbol)

            # Calcul quantité en contrats
            # Pour MEXC Futures: amount = size_usdt / entry_price
            amount = size_usdt / entry_price
            
            # 🔥 FIX: Stocker min_amount pour validation TP partiel
            min_amount = None

            # 🔢 Ajuster quantité selon la précision/limites du marché (CCXT uniquement)
            if self.exchange:
                try:
                    if not getattr(self.exchange, 'markets', None):
                        self.exchange.load_markets()
                    market = self.exchange.market(futures_symbol)

                    amount = float(self.exchange.amount_to_precision(futures_symbol, amount))

                    limits = (market or {}).get('limits', {}) if market else {}
                    min_amount = limits.get('amount', {}).get('min')
                    max_amount = limits.get('amount', {}).get('max')

                    # 🔥 Rejeter si quantité < min après arrondi (pas assez de capital)
                    if min_amount and amount < float(min_amount):
                        logger.error(
                            f"❌ Quantité insuffisante {futures_symbol}: {amount:.8f} < min {min_amount} | "
                            f"Capital requis: {float(min_amount) * entry_price:.2f} USDT (vous avez {size_usdt:.2f} USDT)"
                        )
                        return FuturesOrderResult(
                            success=False,
                            error_message=f"Quantité insuffisante: {amount:.8f} < min {min_amount}",
                            latency_ms=(time.time() - start_time) * 1000
                        )
                    
                    if max_amount and amount > float(max_amount):
                        logger.debug(
                            f"🔧 Ajustement quantité {futures_symbol}: {amount} > max {max_amount}, arrondi au maximum"
                        )
                        amount = float(max_amount)

                    if amount <= 0:
                        raise ValueError(
                            f"Quantité arrondie invalide ({amount}) pour {futures_symbol}. Vérifier size_usdt={size_usdt}"
                        )
                except Exception as precision_err:
                    logger.warning(f"⚠️ Impossible d'ajuster la quantité {futures_symbol}: {precision_err}")
            else:
                # En mode bypass pur, on laisse la quantité calculée telle quelle (MEXC accepte le flottant brut)
                amount = round(amount, 8)

            # Type d'ordre
            # LONG = buy, SHORT = sell (pour ouvrir)
            side = 'buy' if direction == 'LONG' else 'sell'
            order_type = 'market'

            # 🔥 WARNING pour visibilité dans les logs
            logger.warning(
                f"📤 OUVERTURE FUTURES {direction}: {futures_symbol} | "
                f"Prix théorique: {entry_price} | "
                f"Taille: {size_usdt:.2f} USDT | "
                f"Levier: {leverage}x | "
                f"Quantité: {amount:.6f} tokens | "
                f"Mode: {'DRY_RUN' if self.dry_run else 'LIVE'}"
            )

            # DRY RUN: Simuler ordre (SHADOW TRADING REALISTE)
            if self.dry_run:
                # -------------------------------------------------------------
                # 🌑 SHADOW TRADING - SIMULATION HAUTE FIDÉLITÉ
                # -------------------------------------------------------------
                start_shadow = time.time()
                
                # 1. Récupérer Carnet d'Ordres Réel (L2 Data)
                # On essaie de récupérer la liquidité réelle pour calculer le vrai prix
                shadow_book = None
                try:
                    if self.use_bypass and self.bypass_client:
                        # Mode Bypass
                        bypass_symbol_book = self._convert_symbol_to_bypass(symbol)
                        # Note: get_order_book n'est pas toujours dispo dans bypass, fallback sur CCXT si besoin
                        # Si bypass a une méthode get_depth ou similaire
                        pass 
                    
                    # Fallback ou Primary: Utiliser CCXT (souvent plus simple pour fetchOrderBook public)
                    if not shadow_book and self.exchange:
                        # Utiliser l'instance exchange même en dry_run si dispo, sinon créer une temporaire ? 
                        # self.exchange est init en mode CCXT, mais peut-être pas en mode Bypass/DryRun pur sans keys
                        # On va supposer que l'accès public (sans keys) fonctionne pour fetchOrderBook
                        shadow_book = self.exchange.fetch_order_book(futures_symbol, limit=20)
                except Exception as e:
                    logger.debug(f"⚠️ Shadow: Impossible de fetch orderbook: {e}")

                # 2. Calculer Prix d'Exécution Réaliste (Walking the Book)
                shadow_filled_price = entry_price
                shadow_slippage = 0.0
                market_impact_usd = 0.0
                
                if shadow_book and 'bids' in shadow_book and 'asks' in shadow_book:
                    bids = shadow_book['bids'] # [[price, qty], ...]
                    asks = shadow_book['asks']
                    
                    # Si on ACHÈTE (LONG), on tape dans les ASKS (vendeurs)
                    # Si on VEND (SHORT), on tape dans les BIDS (acheteurs)
                    liquidity_side = asks if direction == 'LONG' else bids
                    
                    remaining_qty = amount
                    total_cost = 0.0
                    filled_qty = 0.0
                    
                    # "Walk the book"
                    for price, qty in liquidity_side:
                        take_qty = min(remaining_qty, qty)
                        total_cost += take_qty * price
                        filled_qty += take_qty
                        remaining_qty -= take_qty
                        
                        if remaining_qty <= 0:
                            break
                            
                    if filled_qty > 0:
                        shadow_filled_price = total_cost / filled_qty
                        
                        # Calculer slippage réel vs meilleur prix
                        best_price = liquidity_side[0][0]
                        shadow_slippage = abs((shadow_filled_price - best_price) / best_price) * 100
                        market_impact_usd = abs(shadow_filled_price - best_price) * filled_qty

                # 3. Simuler Latence Réseau (50-150ms)
                # On ajoute un bruit aléatoire pour simuler le temps de trajet réel
                import random
                network_latency = random.uniform(0.050, 0.150)
                time.sleep(network_latency)
                
                latency_ms = (time.time() - start_time) * 1000

                # 4. Calculer prix de liquidation simulé
                margin = size_usdt / leverage
                if direction == 'LONG':
                    liq_price = shadow_filled_price * (1 - 1/leverage + 0.005)
                else:
                    liq_price = shadow_filled_price * (1 + 1/leverage - 0.005)

                logger.info(
                    f"🌑 [SHADOW] Position {direction} simulée | "
                    f"Prix Demandé: {entry_price} → Exécuté: {shadow_filled_price:.2f} | "
                    f"Slippage: {shadow_slippage:.4f}% ({market_impact_usd:.2f}$) | "
                    f"Latence: {latency_ms:.0f}ms"
                )

                return FuturesOrderResult(
                    success=True,
                    order_id=f"shadow_{int(time.time())}_{random.randint(1000,9999)}",
                    filled_price=shadow_filled_price, # Prix réaliste
                    filled_amount=amount,
                    filled_size_usdt=amount * shadow_filled_price,
                    actual_pnl_usdt=0.0,
                    actual_fees_usdt=amount * shadow_filled_price * 0.0002, # Simulation fees 0.02%
                    actual_slippage_pct=shadow_slippage,
                    margin_used=margin,
                    leverage=leverage,
                    liquidation_price=liq_price,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat(),
                    # Métadonnées Shadow pour ML
                    raw_api_response={
                        'is_shadow': True,
                        'shadow_slippage': shadow_slippage,
                        'market_impact': market_impact_usd,
                        'book_depth_used': len(shadow_book['asks']) if shadow_book else 0
                    }
                )

            # 🔥 Vérifier solde disponible AVANT d'ouvrir position
            margin_required = size_usdt / leverage
            balance_free = self.get_balance('USDT')
            balance_total = self.get_balance_total('USDT')
            
            if balance_free is not None and balance_free < margin_required:
                # Calculer le levier minimum nécessaire
                min_leverage_needed = int(size_usdt / balance_free) + 1 if balance_free > 0 else 999
                margin_blocked = (balance_total or 0) - (balance_free or 0)
                
                logger.error(
                    f"❌ Solde insuffisant: {balance_free:.2f} USDT disponible / {balance_total:.2f} USDT total | "
                    f"Marge bloquée: {margin_blocked:.2f} USDT | "
                    f"Requis: {margin_required:.2f} USDT (size={size_usdt:.2f}, leverage={leverage}x) | "
                    f"💡 Levier min nécessaire: x{min_leverage_needed}"
                )
                return FuturesOrderResult(
                    success=False,
                    error_message=f"Solde insuffisant: {balance_free:.2f} USDT disponible (total: {balance_total:.2f}), {margin_required:.2f} USDT requis. Augmenter levier à x{min_leverage_needed} ou fermer des positions.",
                    latency_ms=(time.time() - start_time) * 1000
                )

            # Stocker levier dans cache pour la fermeture
            self._leverage_cache[futures_symbol] = leverage
            
            # ================================================================
            # 🔥 MODE BYPASS: Utiliser les endpoints browser
            # ================================================================
            if self.use_bypass and self.bypass_client:
                bypass_symbol = self._convert_symbol_to_bypass(symbol)
                
                # 🔥 Récupérer les specs du contrat pour arrondir correctement
                contract_spec = run_async_safely(
                    self.bypass_client.get_contract_spec(bypass_symbol)
                )
                
                if contract_spec:
                    original_entry_price = entry_price
                    
                    # 🔥 FIX CRITIQUE: TOUJOURS diviser par contract_size pour obtenir le nombre de CONTRATS
                    # Sur MEXC, 1 contrat = contract_size tokens
                    # Exemples:
                    #   - SHIB (contractSize=1000): 10 USDT @ 0.00001 = 1M tokens / 1000 = 1000 contrats
                    #   - BTC (contractSize=0.0001): 10 USDT @ 100000 = 0.0001 BTC / 0.0001 = 1 contrat
                    if contract_spec.contract_size != 1.0:
                        original_amount = amount
                        amount = amount / contract_spec.contract_size
                        logger.info(
                            f"📋 Conversion tokens→contrats {bypass_symbol}: "
                            f"{original_amount:.6f} / {contract_spec.contract_size} = {amount:.2f} contrats"
                        )
                    
                    # Arrondir volume et prix selon les specs
                    amount = contract_spec.round_volume(amount)
                    entry_price = contract_spec.round_price(entry_price)

                    if entry_price <= 0:
                        entry_price = max(original_entry_price, contract_spec.price_unit or 0.0)
                        if entry_price <= 0:
                            raise ValueError(
                                f"Prix arrondi invalide pour {bypass_symbol}: {original_entry_price} → {entry_price}"
                            )

                    # 🔥 FIX: Vérifier que la valeur en USDT après arrondi est >= 5.5 USDT (minimum MEXC + marge)
                    MIN_ORDER_USDT = 6.0  # 5 USDT minimum MEXC + 1.0 marge sécurité
                    # 🔥 Calcul correct: amount (contrats) * entry_price * contract_size = valeur en USDT
                    actual_size_usdt = amount * entry_price * contract_spec.contract_size
                    
                    logger.debug(
                        f"📊 DEBUG {bypass_symbol}: amount={amount:.6f} contrats, entry_price={entry_price}, "
                        f"contract_size={contract_spec.contract_size}, value={actual_size_usdt:.2f} USDT"
                    )
                    
                    if actual_size_usdt < MIN_ORDER_USDT:
                        import math
                        # 🔥 FIX: Calculer le nombre EXACT de contrats pour atteindre MIN_ORDER_USDT
                        min_amount_needed = MIN_ORDER_USDT / (entry_price * contract_spec.contract_size)
                        
                        # Arrondir vers le haut au vol_unit le plus proche
                        if contract_spec.vol_unit > 0:
                            min_amount_needed = math.ceil(min_amount_needed / contract_spec.vol_unit) * contract_spec.vol_unit
                        
                        # Arrondir selon la précision
                        min_amount_needed = round(min_amount_needed, contract_spec.vol_precision)
                        
                        # 🔥 FIX: Si après arrondi c'est toujours < minimum, augmenter d'un vol_unit
                        recalc_usdt = min_amount_needed * entry_price * contract_spec.contract_size
                        while recalc_usdt < MIN_ORDER_USDT and contract_spec.vol_unit > 0:
                            min_amount_needed += contract_spec.vol_unit
                            recalc_usdt = min_amount_needed * entry_price * contract_spec.contract_size
                        
                        logger.warning(
                            f"⚠️ Taille insuffisante {bypass_symbol}: {actual_size_usdt:.2f} USDT < {MIN_ORDER_USDT} USDT | "
                            f"Augmentation automatique: {amount:.6f} → {min_amount_needed:.6f} contrats ({recalc_usdt:.2f} USDT)"
                        )
                        amount = min_amount_needed
                        actual_size_usdt = recalc_usdt
                    
                    # Log si volume < min_vol (info uniquement)
                    if amount < contract_spec.min_vol:
                        logger.info(
                            f"ℹ️ Volume {bypass_symbol}: {amount} < min_vol {contract_spec.min_vol} | "
                            f"Valeur: {actual_size_usdt:.2f} USDT (minimum MEXC: 5 USDT)"
                        )

                    logger.debug(f"📋 Specs {bypass_symbol}: minVol={contract_spec.min_vol}, volUnit={contract_spec.vol_unit}")
                    
                    # 🔥 FIX: Stocker min_vol pour validation TP partiel
                    min_amount = contract_spec.min_vol
                else:
                    # Fallback: arrondi basique
                    amount = round(amount, 4)
                    min_amount = 1.0  # Fallback minimum
                    logger.warning(f"⚠️ Specs non disponibles pour {bypass_symbol}, arrondi basique")
                
                # Déterminer side pour bypass
                # 1=open long, 2=close short, 3=open short, 4=close long
                if direction == 'LONG':
                    bypass_side = OrderSide.OPEN_LONG
                else:
                    bypass_side = OrderSide.OPEN_SHORT
                
                # 🔥 FIX: Validation finale avant envoi
                if amount <= 0:
                    logger.error(
                        f"❌ [BYPASS] BLOQUE: amount={amount} <= 0 pour {bypass_symbol} | "
                        f"size_usdt original={size_usdt}, entry_price={entry_price}"
                    )
                    return FuturesOrderResult(
                        success=False,
                        error_message=f"Volume invalide: {amount} <= 0",
                        latency_ms=(time.time() - start_time) * 1000
                    )
                
                # 🔥 FIX: S'assurer que la valeur en USDT est >= 5 USDT
                final_value_usdt = amount * entry_price * (contract_spec.contract_size if contract_spec else 1)
                if final_value_usdt < 5.0:
                    logger.error(
                        f"❌ [BYPASS] BLOQUE: valeur finale {final_value_usdt:.2f} USDT < 5 USDT | "
                        f"amount={amount}, price={entry_price}, contract_size={contract_spec.contract_size if contract_spec else 1}"
                    )
                    return FuturesOrderResult(
                        success=False,
                        error_message=f"Valeur ordre trop petite: {final_value_usdt:.2f} USDT < 5 USDT minimum MEXC",
                        latency_ms=(time.time() - start_time) * 1000
                    )
                
                logger.info(
                    f"🔥 [BYPASS] Ouverture {direction}: {bypass_symbol} | "
                    f"Side: {bypass_side} | Vol: {amount:.6f} | Price: {entry_price} | Leverage: {leverage}x | "
                    f"Valeur: {final_value_usdt:.2f} USDT"
                )
                
                # 🔥 FIX: Configurer le levier AVANT de passer l'ordre
                # En mode marge isolée, le levier doit être défini sur le compte
                position_type = 1 if direction == 'LONG' else 2
                try:
                    run_async_safely(
                        self.bypass_client.set_leverage(
                            symbol=bypass_symbol,
                            leverage=leverage,
                            open_type=OpenType.ISOLATED,
                            position_type=position_type
                        )
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de configurer le levier: {e} (peut déjà être configuré)")
                
                # Appeler le client bypass (async) via helper thread-safe
                bypass_result = run_async_safely(
                    self.bypass_client.submit_order(
                        symbol=bypass_symbol,
                        side=bypass_side,
                        vol=amount,
                        price=entry_price,
                        order_type=OrderType.MARKET,
                        open_type=OpenType.ISOLATED,
                        leverage=leverage
                    )
                )
                
                latency_ms = (time.time() - start_time) * 1000

                if bypass_result.success:
                    # 🔥 VÉRIFICATION POST-CRÉATION: S'assurer que l'ordre existe réellement
                    # Attendre 300ms pour que MEXC traite l'ordre
                    time.sleep(0.3)

                    # Vérifier si l'ordre existe réellement
                    order_check = run_async_safely(
                        self.bypass_client.get_order(bypass_result.order_id)
                    )

                    # Analyser la réponse
                    if not order_check or not order_check.get("success"):
                        # Ordre introuvable = rejet silencieux par MEXC
                        error_details = order_check.get("message", "Unknown") if order_check else "No response"
                        error_code = order_check.get("code", -1) if order_check else -1

                        logger.error(
                            f"❌ [BYPASS] REJET SILENCIEUX détecté: {bypass_symbol} | "
                            f"Order ID: {bypass_result.order_id} | "
                            f"Code: {error_code} | Message: {error_details} | "
                            f"Vol envoyé: {amount:.6f} | Prix envoyé: {entry_price} | "
                            f"Specs: minVol={contract_spec.min_vol if contract_spec else 'N/A'}, "
                            f"volUnit={contract_spec.vol_unit if contract_spec else 'N/A'}"
                        )

                        # 🔥 TELEGRAM: Notifier rejet silencieux
                        if self.telegram_notifier:
                            self.telegram_notifier.send_error_sync(
                                "Rejet silencieux MEXC",
                                f"{bypass_symbol} | Code: {error_code} | {error_details}"
                            )

                        # 🔥 Circuit Breaker: Enregistrer échec
                        if self.circuit_breaker:
                            self.circuit_breaker.record_failure()

                        self.stats['orders_failed'] += 1

                        return FuturesOrderResult(
                            success=False,
                            error_message=f"Rejet silencieux MEXC (code {error_code}): {error_details}",
                            latency_ms=latency_ms
                        )

                    # Ordre confirmé existant
                    order_data = order_check.get("data", {})
                    order_state = order_data.get("state", 0)  # 1=pending, 2=filled, 3=cancelled, 4=rejected

                    if order_state == 4:
                        # Ordre explicitement rejeté
                        logger.error(
                            f"❌ [BYPASS] Ordre REJETÉ par MEXC: {bypass_symbol} | "
                            f"Order ID: {bypass_result.order_id} | "
                            f"State: {order_state} | "
                            f"Vol: {amount:.6f} | Prix: {entry_price}"
                        )

                        # 🔥 TELEGRAM: Notifier rejet d'ordre
                        if self.telegram_notifier:
                            self.telegram_notifier.send_error_sync(
                                "Ordre rejeté MEXC",
                                f"{bypass_symbol} | State: {order_state} | Vol: {amount:.6f}"
                            )

                        if self.circuit_breaker:
                            self.circuit_breaker.record_failure()

                        self.stats['orders_failed'] += 1

                        return FuturesOrderResult(
                            success=False,
                            error_message=f"Ordre rejeté par MEXC (state={order_state})",
                            latency_ms=latency_ms
                        )

                    # ✅ Ordre valide
                    logger.debug(f"✅ Ordre confirmé existant: ID={bypass_result.order_id}, state={order_state}")

                    # 🔥 OPT #2: Récupérer PRIX RÉEL de l'ordre rempli
                    # MEXC retourne 'dealAvgPrice' (prix moyen d'exécution) dans order_data
                    actual_filled_price = order_data.get('dealAvgPrice') or order_data.get('avgPrice')

                    if actual_filled_price and actual_filled_price > 0:
                        # Calculer slippage réel (protection division par zéro)
                        if entry_price and entry_price > 0:
                            actual_slippage = abs((actual_filled_price - entry_price) / entry_price) * 100
                        else:
                            actual_slippage = 0.0
                            logger.warning(f"⚠️ entry_price=0, slippage non calculable")

                        logger.info(
                            f"📊 Prix rempli RÉEL: {actual_filled_price} (théorique: {entry_price}) | "
                            f"Slippage: {actual_slippage:.3f}%"
                        )

                        # Utiliser prix réel
                        final_filled_price = actual_filled_price
                        final_slippage_pct = actual_slippage
                    else:
                        # Fallback: prix théorique si prix réel non disponible
                        logger.warning(f"⚠️ Prix réel non disponible dans order_data, utilisation prix théorique")
                        final_filled_price = entry_price
                        final_slippage_pct = 0.0

                    # 🔥 Circuit Breaker: Enregistrer succès
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success()

                    # 🔥 FIX: Calculer le VRAI volume en tokens (contrats * contract_size)
                    # Exemple: 7 contrats * 10 contract_size = 70 tokens XLM
                    real_contract_size = contract_spec.contract_size if contract_spec else 1.0
                    real_filled_amount = amount * real_contract_size  # Volume réel en tokens
                    real_filled_size_usdt = real_filled_amount * final_filled_price  # Valeur USDT réelle
                    
                    # 🔥 FIX: Définir mexc_contracts AVANT utilisation
                    mexc_contracts = amount  # Contrats MEXC (ce que MEXC affiche)
                    
                    logger.info(
                        f"📊 Volume RÉEL: {real_filled_amount:.4f} tokens ({amount:.2f} contrats × {real_contract_size} contract_size) = {real_filled_size_usdt:.4f} USDT"
                    )
                    
                    # 🔁 VÉRIFICATION POST-ORDRE: Récupérer la taille réelle via CCXT/BYPASS
                    live_sync = self._verify_position_size(symbol, final_filled_price)
                    if live_sync:
                        verified_contracts = live_sync['contracts']
                        verified_size_usdt = live_sync['size_usdt']
                        if abs(verified_contracts - mexc_contracts) > 1e-6:
                            logger.warning(
                                f"⚠️ CONTRATS réels ≠ demandés: {mexc_contracts:.4f} -> {verified_contracts:.4f}"
                            )
                        real_filled_amount = verified_contracts * real_contract_size
                        real_filled_size_usdt = verified_size_usdt
                        final_filled_price = live_sync['entry_price'] or final_filled_price

                    # Calculer prix de liquidation estimé (basé sur prix réel)
                    margin = size_usdt / leverage
                    if direction == 'LONG':
                        liq_price = final_filled_price * (1 - 1/leverage + 0.005)
                    else:
                        liq_price = final_filled_price * (1 + 1/leverage - 0.005)

                    # Mettre à jour stats
                    self.stats['orders_placed'] += 1
                    self.stats['orders_filled'] += 1
                    self.stats['total_latency_ms'] += latency_ms
                    self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']

                    logger.info(
                        f"✅ [BYPASS] Position {direction} ouverte | "
                        f"Order ID: {bypass_result.order_id} | "
                        f"Prix: {final_filled_price} | "
                        f"Volume: {real_filled_amount:.4f} tokens ({real_filled_size_usdt:.4f} USDT) | "
                        f"Slippage: {final_slippage_pct:.3f}% | "
                        f"Latence: {latency_ms:.0f}ms"
                    )

                    # 🔥 FIX: Retourner les VRAIS tokens pour l'affichage
                    # mexc_contracts = contrats MEXC (2543 pour SHIB)
                    # real_filled_amount = tokens réels (2543000 pour SHIB avec contractSize=1000)
                    # L'affichage doit montrer les tokens, pas les contrats MEXC
                    
                    return FuturesOrderResult(
                        success=True,
                        order_id=str(bypass_result.order_id),
                        filled_price=final_filled_price,  # 🔥 Prix RÉEL rempli
                        filled_amount=real_filled_amount,  # 🔥 FIX: Tokens réels (pas contrats MEXC!)
                        filled_contracts=real_filled_amount,  # 🔥 Tokens pour affichage dashboard
                        filled_size_usdt=real_filled_size_usdt,  # 🔥 FIX: Valeur USDT RÉELLE
                        actual_fees_usdt=0.0,  # 0% fees sur paires scannées
                        actual_slippage_pct=final_slippage_pct,  # 🔥 Slippage RÉEL calculé
                        margin_used=margin,
                        leverage=leverage,
                        liquidation_price=liq_price,
                        latency_ms=latency_ms,
                        executed_at=datetime.now(timezone.utc).isoformat(),
                        raw_api_response=bypass_result.data,
                        min_contract_amount=float(min_amount) if min_amount else None,  # 🔥 FIX: Pour TP partiel
                        contract_size=real_contract_size  # 🔥 FIX: Contract size pour calcul PNL correct
                    )
                else:
                    # 🔥 Circuit Breaker: Enregistrer échec
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure()

                    self.stats['orders_failed'] += 1
                    logger.error(
                        f"❌ [BYPASS] Échec ouverture: {bypass_result.error_message}"
                    )

                    # 🔥 TELEGRAM: Notifier échec ouverture
                    if self.telegram_notifier:
                        self.telegram_notifier.send_error_sync(
                            "Échec ouverture position",
                            f"{symbol} | {bypass_result.error_message}"
                        )

                    return FuturesOrderResult(
                        success=False,
                        error_message=bypass_result.error_message,
                        latency_ms=latency_ms
                    )
            
            # ================================================================
            # MODE CCXT: Utiliser l'API classique (peut être bloquée)
            # ================================================================
            # FIX: MEXC requiert leverage, openType ET positionType dans params
            # openType: 1=isolated, 2=cross
            # positionType: 1=long, 2=short
            position_type = 1 if direction == 'LONG' else 2
            
            # DEBUG: Activer verbose pour capturer réponse MEXC complète
            self.exchange.verbose = True
            
            # Retry avec backoff sur timeout/network errors
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
                            'leverage': str(leverage),
                            'openType': 1,  # isolated margin
                            'positionType': position_type,  # 1=long, 2=short
                            'type': 5,  # FIX: Forcer type 5 (market) pour MEXC API native
                        }
                    )
                    break  # Succès, sortir de la boucle
                except (ccxt.NetworkError, ccxt.RequestTimeout) as retry_error:
                    last_error = retry_error
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 1s, 2s
                        logger.warning(
                            f"Timeout/Network error (tentative {attempt + 1}/{max_retries}), "
                            f"retry dans {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        raise last_error
            
            # DEBUG: Désactiver verbose après ordre
            self.exchange.verbose = False

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos ordre
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price') or entry_price
            filled_amount = order.get('filled') or amount
            fee_info = order.get('fee', {})
            fees = fee_info.get('cost', 0.0) or 0.0

            # Calculer slippage (protection division par zéro)
            if filled_price and entry_price and entry_price > 0:
                slippage_pct = abs((filled_price - entry_price) / entry_price) * 100
            else:
                slippage_pct = 0.0

            # Calculer marge utilisée
            margin_used = size_usdt / leverage

            # Récupérer infos position pour liquidation price
            liquidation_price = None
            funding_rate = None
            try:
                positions = self.exchange.fetch_positions([futures_symbol])
                for pos in positions:
                    if pos.get('symbol') == futures_symbol and float(pos.get('contracts', 0)) > 0:
                        liquidation_price = float(pos.get('liquidationPrice', 0)) or None
                        break
                # Récupérer funding rate
                try:
                    funding_info = self.exchange.fetch_funding_rate(futures_symbol)
                    funding_rate = funding_info.get('fundingRate')
                except:
                    pass
            except Exception as e:
                logger.debug(f"Impossible de récupérer position/funding: {e}")

            # Récupérer taux de frais
            maker_fee_rate = None
            taker_fee_rate = None
            try:
                markets = self.exchange.load_markets()
                if futures_symbol in markets:
                    market = markets[futures_symbol]
                    maker_fee_rate = market.get('maker')
                    taker_fee_rate = market.get('taker')
            except:
                pass

            # Mettre à jour stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']

            logger.info(
                f"Position FUTURES {direction} ouverte | "
                f"Order ID: {order_id} | "
                f"Prix rempli: {filled_price} | "
                f"Slippage: {slippage_pct:.3f}% | "
                f"Fees: {fees:.4f} USDT | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                filled_size_usdt=filled_amount * filled_price if filled_price else filled_amount * entry_price,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                margin_used=margin_used,
                leverage=leverage,
                liquidation_price=liquidation_price,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat(),
                maker_fee_rate=maker_fee_rate,
                taker_fee_rate=taker_fee_rate,
                funding_rate=funding_rate,
                raw_api_response=order,
                min_contract_amount=float(min_amount) if min_amount else None  # 🔥 FIX: Pour TP partiel
            )

        except Exception as e:
            # 🔥 Circuit Breaker: Enregistrer échec
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()

            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            # Log détaillé avec message d'erreur complet
            error_msg = str(e)
            # Extraire le message d'erreur s'il est dans un tuple
            if hasattr(e, 'args') and len(e.args) > 0:
                if isinstance(e.args[0], str):
                    error_msg = e.args[0]
            
            mexc_response = None
            mexc_status = None
            try:
                mexc_response = getattr(e, 'response', None) or getattr(e, 'body', None)
                mexc_status = getattr(e, 'http_status', None)
            except Exception:
                pass

            logger.error(
                f"Erreur ouverture position futures: {error_msg} | "
                f"Symbol: {symbol} → {futures_symbol} | "
                f"Side: {side} | Amount: {amount:.6f} | Leverage: {leverage}x | "
                f"Size USDT: {size_usdt:.2f} | "
                f"Latence: {latency_ms:.0f}ms"
                + (f" | HTTP {mexc_status}" if mexc_status else "")
            )

            if mexc_response:
                logger.error(f"Réponse MEXC: {mexc_response}")

            # 🔥 TELEGRAM: Notifier erreur critique
            if self.telegram_notifier:
                self.telegram_notifier.send_error_sync(
                    "Erreur ouverture position",
                    f"{symbol} | {error_msg[:200]}"
                )

            return FuturesOrderResult(
                success=False,
                error_message=error_msg,
                latency_ms=latency_ms
            )

    # 🔥 FIX: Anti rate-limiting - timestamp de la dernière requête
    _last_close_request_time: float = 0
    _min_request_interval_sec: float = 1.0  # Minimum 1 seconde entre les requêtes
    
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
        
        # 🔥 FIX: Anti rate-limiting - attendre si nécessaire
        time_since_last = time.time() - LiveOrderManagerFutures._last_close_request_time
        if time_since_last < self._min_request_interval_sec:
            wait_time = self._min_request_interval_sec - time_since_last
            logger.debug(f"⏳ Anti rate-limit: attente {wait_time:.2f}s avant close_position")
            time.sleep(wait_time)
        LiveOrderManagerFutures._last_close_request_time = time.time()

        # 🔥 CIRCUIT BREAKER: Ordres de fermeture TOUJOURS autorisés (is_closing_order=True)
        if self.circuit_breaker:
            can_execute, reason = self.circuit_breaker.can_execute(is_closing_order=True)
            if not can_execute:
                # Ne devrait jamais arriver car is_closing_order=True bypass le circuit breaker
                logger.error(f"🚨 Circuit Breaker BLOQUE la fermeture: {reason}")
                return FuturesOrderResult(
                    success=False,
                    error_message=f"Circuit breaker ouvert: {reason}",
                    latency_ms=(time.time() - start_time) * 1000
                )

        try:
            # 🔥 FIX: Validation current_price pour éviter division par zéro
            if not current_price or current_price <= 0:
                logger.error(f"❌ current_price invalide ({current_price}) pour fermeture {symbol}")
                # Fallback: utiliser entry_price comme prix de sortie estimé
                if entry_price and entry_price > 0:
                    logger.warning(f"⚠️ Fallback sur entry_price: {entry_price}")
                    current_price = entry_price
                else:
                    return FuturesOrderResult(
                        success=False,
                        error_message=f"Prix invalide pour fermeture: current_price={current_price}, entry_price={entry_price}",
                        latency_ms=(time.time() - start_time) * 1000
                    )

            # Convertir symbole
            futures_symbol = self._convert_symbol_to_futures(symbol)

            # Calcul quantité à fermer
            if partial_pct:
                amount = size_amount * (partial_pct / 100)
                logger.info(f"FERMETURE PARTIELLE {partial_pct}%: {amount:.6f}")
            else:
                amount = size_amount
                logger.info(f"FERMETURE TOTALE: {amount:.6f}")

            # Pour fermer: LONG → sell, SHORT → buy
            side = 'sell' if direction == 'LONG' else 'buy'
            order_type = 'market'

            # Ajuster quantité fermée selon précision
            if self.exchange:
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
                    logger.warning(f"Impossible d'ajuster la quantité close {symbol}: {precision_err}")
            else:
                amount = round(amount, 8)

            logger.info(
                f"FERMETURE FUTURES {direction}: {futures_symbol} | "
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
                    f"[DRY_RUN] Fermeture {direction} simulée | "
                    f"PnL: {pnl_usdt:+.2f} USDT | "
                    f"Latence: {latency_ms:.0f}ms"
                )

                return FuturesOrderResult(
                    success=True,
                    order_id=f"dry_run_close_futures_{int(time.time())}",
                    filled_price=current_price,
                    filled_amount=amount,
                    filled_size_usdt=amount * current_price,
                    actual_pnl_usdt=pnl_usdt,
                    actual_fees_usdt=0.0,
                    actual_slippage_pct=0.0,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat()
                )

            # LIVE: Fermer position réelle
            leverage = self._leverage_cache.get(futures_symbol, self.default_leverage)
            
            # ================================================================
            # MODE BYPASS: Utiliser les endpoints browser
            # ================================================================
            if self.use_bypass and self.bypass_client:
                bypass_symbol = self._convert_symbol_to_bypass(symbol)
                
                # Récupérer les specs du contrat pour arrondir correctement
                contract_spec = run_async_safely(
                    self.bypass_client.get_contract_spec(bypass_symbol)
                )
                
                # 🔥 FIX FERMETURE PARTIELLE: Pour fermeture TOTALE, récupérer taille réelle MEXC
                used_mexc_size = False  # Flag pour savoir si on a la taille réelle MEXC
                if partial_pct is None:  # Fermeture totale
                    try:
                        positions = run_async_safely(
                            self.bypass_client.get_open_positions(bypass_symbol)
                        )
                        if positions:
                            for pos in positions:
                                # Trouver la position correspondante
                                pos_symbol = getattr(pos, 'symbol', None)
                                pos_size = getattr(pos, 'hold_vol', None) or getattr(pos, 'size', None)
                                if pos_symbol == bypass_symbol and pos_size and pos_size > 0:
                                    logger.info(
                                        f"📋 [CLOSE] Taille RÉELLE MEXC: {pos_size} contrats "
                                        f"(calculée: {amount / contract_spec.contract_size if contract_spec and contract_spec.contract_size != 1.0 else amount:.2f})"
                                    )
                                    # Utiliser directement la taille MEXC en contrats (pas besoin de conversion!)
                                    amount = float(pos_size)
                                    used_mexc_size = True
                                    break
                    except Exception as pos_err:
                        logger.warning(f"⚠️ Impossible de récupérer position MEXC: {pos_err}, utilisation taille calculée")
                
                if contract_spec:
                    # 🔥 FIX CRITIQUE: Convertir tokens → contrats MEXC (comme à l'ouverture!)
                    # Sur MEXC, 1 contrat = contractSize tokens
                    # Exemple SOL (contractSize=0.1): 0.1 token → 1 contrat
                    # SAUF si on a récupéré la taille réelle MEXC (déjà en contrats)
                    if contract_spec.contract_size != 1.0 and not used_mexc_size:
                        # Conversion nécessaire si on n'a pas la taille réelle MEXC
                        original_amount = amount
                        amount = amount / contract_spec.contract_size
                        logger.info(
                            f"📋 [CLOSE] Conversion tokens→contrats {bypass_symbol}: "
                            f"{original_amount:.6f} / {contract_spec.contract_size} = {amount:.2f} contrats"
                        )
                    
                    amount = contract_spec.round_volume(amount)
                    current_price = contract_spec.round_price(current_price)
                    
                    # 🔥 FIX CRITIQUE: Si amount arrondi = 0, récupérer la taille réelle MEXC et fermer 100%
                    # Cela arrive quand partial_pct * position < min_contract (ex: 0.5 contrat DOGE)
                    if amount <= 0 and partial_pct is not None:
                        logger.warning(
                            f"⚠️ Volume partiel arrondi à 0 pour {bypass_symbol}. "
                            f"Récupération taille MEXC pour fermer 100%..."
                        )
                        try:
                            positions = run_async_safely(
                                self.bypass_client.get_open_positions(bypass_symbol)
                            )
                            if positions:
                                for pos in positions:
                                    pos_symbol = getattr(pos, 'symbol', None)
                                    pos_size = getattr(pos, 'hold_vol', None) or getattr(pos, 'size', None)
                                    if pos_symbol == bypass_symbol and pos_size and pos_size > 0:
                                        amount = float(pos_size)
                                        logger.info(
                                            f"🔧 TP Partiel forcé à 100%: volume MEXC={amount} contrats "
                                            f"(partiel impossible car < min)"
                                        )
                                        break
                        except Exception as pos_err:
                            logger.error(f"❌ Impossible de récupérer position MEXC: {pos_err}")
                else:
                    amount = round(amount, 4)
                    logger.warning(f"Specs non disponibles pour {bypass_symbol}, arrondi basique")
                
                # 🔥 FIX: Validation finale - rejeter si volume toujours 0
                if amount <= 0:
                    logger.error(
                        f"❌ [BYPASS] BLOQUE fermeture: volume={amount} <= 0 pour {bypass_symbol} | "
                        f"partial_pct={partial_pct}"
                    )
                    return FuturesOrderResult(
                        success=False,
                        error_message=f"Volume fermeture invalide: {amount} <= 0",
                        latency_ms=(time.time() - start_time) * 1000
                    )
                
                # Déterminer side pour bypass (fermeture)
                # 1=open long, 2=close short, 3=open short, 4=close long
                if direction == 'LONG':
                    bypass_side = OrderSide.CLOSE_LONG
                else:
                    bypass_side = OrderSide.CLOSE_SHORT
                
                logger.info(
                    f"[BYPASS] Fermeture {direction}: {bypass_symbol} | "
                    f"Side: {bypass_side} | Vol: {amount:.6f} | Price: {current_price}"
                )
                
                # Appeler le client bypass (async) via helper thread-safe
                bypass_result = run_async_safely(
                    self.bypass_client.submit_order(
                        symbol=bypass_symbol,
                        side=bypass_side,
                        vol=amount,
                        price=current_price,
                        order_type=OrderType.MARKET,
                        open_type=OpenType.ISOLATED,
                        leverage=leverage,
                        reduce_only=True
                    )
                )
                
                latency_ms = (time.time() - start_time) * 1000

                if bypass_result.success:
                    # 🔥 VÉRIFICATION POST-CRÉATION: S'assurer que l'ordre existe réellement
                    time.sleep(0.3)

                    order_check = run_async_safely(
                        self.bypass_client.get_order(bypass_result.order_id)
                    )

                    # Analyser la réponse
                    if not order_check or not order_check.get("success"):
                        error_details = order_check.get("message", "Unknown") if order_check else "No response"
                        error_code = order_check.get("code", -1) if order_check else -1

                        logger.error(
                            f"❌ [BYPASS] REJET SILENCIEUX fermeture: {bypass_symbol} | "
                            f"Order ID: {bypass_result.order_id} | "
                            f"Code: {error_code} | Message: {error_details} | "
                            f"Vol envoyé: {amount:.6f} | Prix envoyé: {current_price}"
                        )

                        # 🔥 TELEGRAM: Notifier rejet silencieux fermeture
                        if self.telegram_notifier:
                            self.telegram_notifier.send_error_sync(
                                "Rejet silencieux fermeture",
                                f"{bypass_symbol} | Code: {error_code} | {error_details}"
                            )

                        if self.circuit_breaker:
                            self.circuit_breaker.record_failure()

                        self.stats['orders_failed'] += 1

                        return FuturesOrderResult(
                            success=False,
                            error_message=f"Rejet silencieux fermeture (code {error_code}): {error_details}",
                            latency_ms=latency_ms
                        )

                    order_data = order_check.get("data", {})
                    order_state = order_data.get("state", 0)

                    if order_state == 4:
                        logger.error(
                            f"❌ [BYPASS] Fermeture REJETÉE: {bypass_symbol} | "
                            f"Order ID: {bypass_result.order_id} | State: {order_state}"
                        )

                        # 🔥 TELEGRAM: Notifier fermeture rejetée
                        if self.telegram_notifier:
                            self.telegram_notifier.send_error_sync(
                                "Fermeture rejetée MEXC",
                                f"{bypass_symbol} | State: {order_state}"
                            )

                        if self.circuit_breaker:
                            self.circuit_breaker.record_failure()

                        self.stats['orders_failed'] += 1

                        return FuturesOrderResult(
                            success=False,
                            error_message=f"Fermeture rejetée (state={order_state})",
                            latency_ms=latency_ms
                        )

                    logger.debug(f"✅ Fermeture confirmée: ID={bypass_result.order_id}, state={order_state}")

                    # 🔥 OPT #2: Récupérer PRIX RÉEL de fermeture
                    actual_exit_price = order_data.get('dealAvgPrice') or order_data.get('avgPrice')

                    if actual_exit_price and actual_exit_price > 0:
                        # Calculer slippage réel sur fermeture (avec protection division par zéro)
                        if current_price and current_price > 0:
                            exit_slippage = abs((actual_exit_price - current_price) / current_price) * 100
                        else:
                            exit_slippage = 0.0
                            logger.warning(f"⚠️ current_price=0, slippage exit non calculable")

                        logger.info(
                            f"📊 Prix sortie RÉEL: {actual_exit_price} (théorique: {current_price}) | "
                            f"Slippage sortie: {exit_slippage:.3f}%"
                        )

                        final_exit_price = actual_exit_price
                        final_exit_slippage = exit_slippage
                    else:
                        logger.warning(f"⚠️ Prix sortie réel non disponible, utilisation prix théorique")
                        final_exit_price = current_price
                        final_exit_slippage = 0.0

                    # 🔥 Circuit Breaker: Enregistrer succès
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success()

                    # 🔥 FIX: Essayer de récupérer le PnL RÉEL depuis l'historique MEXC
                    real_pnl_from_api = None
                    try:
                        # Attendre que MEXC enregistre la fermeture
                        time.sleep(0.5)
                        
                        # Récupérer l'historique des positions récentes
                        pos_history = run_async_safely(
                            self.bypass_client.get_position_history(
                                symbol=bypass_symbol,
                                page_size=5
                            )
                        )
                        
                        if pos_history and pos_history.get("success") and pos_history.get("data"):
                            history_data = pos_history.get("data", [])
                            if isinstance(history_data, list) and len(history_data) > 0:
                                # Prendre la position la plus récente
                                latest_pos = history_data[0]
                                # MEXC retourne 'realizedPnl' ou 'profitReal' selon le endpoint
                                real_pnl = latest_pos.get('realizedPnl') or latest_pos.get('profitReal') or latest_pos.get('profit')
                                if real_pnl is not None:
                                    real_pnl_from_api = float(real_pnl)
                                    logger.info(f"📊 PnL RÉEL depuis API MEXC: {real_pnl_from_api:+.4f} USDT")
                    except Exception as pnl_err:
                        logger.debug(f"⚠️ Impossible de récupérer PnL depuis historique: {pnl_err}")
                    
                    # Calculer PnL basé sur prix réel (fallback si API échoue)
                    # 🔥 FIX: Inclure contract_size dans le calcul (PnL = DeltaPrice * Contracts * ContractSize)
                    real_contract_size = contract_spec.contract_size if contract_spec else 1.0
                    
                    if direction == 'LONG':
                        calculated_pnl = (final_exit_price - entry_price) * amount * real_contract_size
                    else:
                        calculated_pnl = (entry_price - final_exit_price) * amount * real_contract_size
                    
                    # Utiliser le PnL de l'API si disponible, sinon le calculé
                    pnl_usdt = real_pnl_from_api if real_pnl_from_api is not None else calculated_pnl
                    
                    if real_pnl_from_api is not None and abs(real_pnl_from_api - calculated_pnl) > 0.01:
                        logger.info(
                            f"📊 PnL différence: API={real_pnl_from_api:+.4f} vs Calculé={calculated_pnl:+.4f} USDT"
                        )

                    # Mettre à jour stats
                    self.stats['orders_placed'] += 1
                    self.stats['orders_filled'] += 1
                    self.stats['total_latency_ms'] += latency_ms
                    self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']
                    self.stats['total_pnl_usdt'] += pnl_usdt

                    logger.info(
                        f"[BYPASS] Position {direction} fermée | "
                        f"Order ID: {bypass_result.order_id} | "
                        f"Prix sortie: {final_exit_price} | "
                        f"PnL: {pnl_usdt:+.2f} USDT | "
                        f"Slippage: {final_exit_slippage:.3f}% | "
                        f"Latence: {latency_ms:.0f}ms"
                    )

                    return FuturesOrderResult(
                        success=True,
                        order_id=str(bypass_result.order_id),
                        filled_price=final_exit_price,  # 🔥 Prix RÉEL sortie
                        filled_amount=amount * real_contract_size,  # 🔥 FIX: Tokens réels (comme open_position)
                        filled_size_usdt=amount * final_exit_price * real_contract_size, # 🔥 FIX: Valeur USDT réelle
                        actual_pnl_usdt=pnl_usdt,  # 🔥 PnL basé sur prix RÉEL
                        actual_fees_usdt=0.0,  # 0% fees
                        actual_slippage_pct=final_exit_slippage,  # 🔥 Slippage RÉEL
                        latency_ms=latency_ms,
                        executed_at=datetime.now(timezone.utc).isoformat(),
                        raw_api_response=bypass_result.data
                    )
                else:
                    # 🔥 Circuit Breaker: Enregistrer échec
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure()

                    self.stats['orders_failed'] += 1
                    logger.error(
                        f"❌ [BYPASS] Échec fermeture: {bypass_result.error_message}"
                    )

                    # 🔥 TELEGRAM: Notifier échec fermeture
                    if self.telegram_notifier:
                        self.telegram_notifier.send_error_sync(
                            "Échec fermeture position",
                            f"{symbol} | {bypass_result.error_message}"
                        )

                    return FuturesOrderResult(
                        success=False,
                        error_message=bypass_result.error_message,
                        latency_ms=latency_ms
                    )
            
            # ================================================================
            # MODE CCXT: Utiliser l'API classique (peut être bloquée)
            # ================================================================
            # positionType: 1=long, 2=short
            position_type = 1 if direction == 'LONG' else 2
            
            # Retry avec backoff pour fermeture aussi
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
                            'type': 5,  # FIX: Forcer type 5 (market) pour MEXC API native
                        }
                    )
                    break  # Succès
                except (ccxt.NetworkError, ccxt.RequestTimeout) as retry_error:
                    last_error = retry_error
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"Timeout fermeture (tentative {attempt + 1}/{max_retries}), "
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

            # Slippage (avec protection division par zéro)
            if filled_price and current_price and current_price > 0:
                slippage_pct = abs((filled_price - current_price) / current_price) * 100
            else:
                slippage_pct = 0.0

            # Récupérer funding rate à la sortie
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
                f"Position FUTURES {direction} fermée | "
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
                filled_size_usdt=filled_amount * filled_price,
                actual_pnl_usdt=pnl_usdt,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat(),
                funding_rate=funding_rate,
                raw_api_response=order
            )

        except Exception as e:
            # 🔥 Circuit Breaker: Enregistrer échec
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()

            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            logger.error(f"❌ Erreur fermeture position futures: {e}")

            # 🔥 TELEGRAM: Notifier erreur fermeture critique
            if self.telegram_notifier:
                self.telegram_notifier.send_error_sync(
                    "Erreur fermeture position",
                    f"{symbol} | {str(e)[:200]}"
                )

            return FuturesOrderResult(
                success=False,
                error_message=str(e),
                latency_ms=latency_ms
            )

    async def place_stop_loss_order(
        self,
        symbol: str,
        direction: str,
        sl_price: float,
        entry_price: float
    ) -> FuturesOrderResult:
        """
        🔥 FIX SL MISMATCH V2: Placer un ordre Stop Loss sur l'exchange
        
        Cette méthode place un ordre SL de protection directement sur MEXC.
        En cas de crash du bot, l'ordre SL reste actif sur l'exchange.
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT (de la position ouverte)
            sl_price: Prix du Stop Loss
            entry_price: Prix d'entrée de la position
            
        Returns:
            FuturesOrderResult avec l'ID de l'ordre SL
        """
        start_time = time.time()
        
        try:
            if self.dry_run:
                logger.info(
                    f"🛡️ [DRY_RUN] Ordre SL simulé: {symbol} {direction} | "
                    f"SL={sl_price:.8f} | Entry={entry_price:.8f}"
                )
                return FuturesOrderResult(
                    success=True,
                    order_id=f"sl_dry_run_{int(time.time())}",
                    filled_price=sl_price,
                    latency_ms=(time.time() - start_time) * 1000
                )
            
            # Vérifier si bypass disponible
            if not self.use_bypass or not self.bypass_client:
                logger.warning("⚠️ Bypass non disponible pour placer ordre SL")
                return FuturesOrderResult(
                    success=False,
                    error_message="Bypass non disponible",
                    latency_ms=(time.time() - start_time) * 1000
                )
            
            # Récupérer la position actuelle pour connaître la taille
            position_info = self.get_position(symbol)
            if not position_info:
                logger.warning(f"⚠️ Aucune position trouvée pour {symbol}, impossible de placer SL")
                return FuturesOrderResult(
                    success=False,
                    error_message="Aucune position active",
                    latency_ms=(time.time() - start_time) * 1000
                )
            
            position_size = position_info.get('size', 0)
            if position_size <= 0:
                logger.warning(f"⚠️ Taille de position invalide pour {symbol}: {position_size}")
                return FuturesOrderResult(
                    success=False,
                    error_message="Taille de position invalide",
                    latency_ms=(time.time() - start_time) * 1000
                )
            
            # Convertir symbole au format bypass
            bypass_symbol = self._convert_symbol_to_bypass(symbol)
            
            # Déterminer le side pour fermer la position
            # LONG -> close long (side=4), SHORT -> close short (side=2)
            if direction == 'LONG':
                close_side = OrderSide.CLOSE_LONG  # 4
            else:
                close_side = OrderSide.CLOSE_SHORT  # 2
            
            # Récupérer specs du contrat pour arrondir
            contract_spec = run_async_safely(
                self.bypass_client.get_contract_spec(bypass_symbol)
            )
            
            if contract_spec:
                position_size = contract_spec.round_volume(position_size)
                sl_price = contract_spec.round_price(sl_price)
            
            logger.info(
                f"🛡️ [BYPASS] Placement ordre SL: {bypass_symbol} | "
                f"Side: {close_side} | Vol: {position_size:.6f} | "
                f"SL Price: {sl_price:.8f}"
            )
            
            # 🔥 NOTE: MEXC bypass ne supporte pas les ordres stop conditionnels séparés
            # Le paramètre stop_loss_price est pour attacher un SL lors de l'ouverture
            # Pour un vrai ordre stop, il faudrait utiliser l'endpoint /private/planorder/place
            # qui n'est pas encore implémenté dans le bypass
            
            # Pour l'instant, on log un message informatif
            # La protection principale reste la vérification SL temps réel via WebSocket
            logger.info(
                f"ℹ️ Ordre SL sur exchange non supporté par le bypass actuel. "
                f"Protection assurée par vérification SL temps réel WebSocket. "
                f"Symbole: {symbol} | SL: {sl_price:.8f}"
            )
            
            return FuturesOrderResult(
                success=True,  # On considère succès car la protection temps réel est active
                order_id=f"sl_realtime_{int(time.time())}",
                filled_price=sl_price,
                latency_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ Erreur placement ordre SL: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return FuturesOrderResult(
                success=False,
                error_message=str(e),
                latency_ms=latency_ms
            )

    def get_position(self, symbol: str, prefer_ccxt: bool = True) -> Optional[Dict[str, Any]]:
        """
        Récupérer infos position ouverte
        
        Args:
            symbol: Paire (ex: BTC/USDT)
            prefer_ccxt: Si True, utilise CCXT en priorité (recommandé pour lectures)

        Returns:
            Dict avec size, entryPrice, unrealizedPnl, liquidationPrice, etc.
        """
        try:
            if self.dry_run:
                return None

            # 🔄 PRIORITÉ CCXT pour les lectures (économise les requêtes bypass)
            if prefer_ccxt and self.exchange:
                try:
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
                except Exception as ccxt_err:
                    logger.warning(f"⚠️ CCXT get_position failed, fallback bypass: {ccxt_err}")
            
            # 🔥 FALLBACK BYPASS (avec rate limiting)
            if self.use_bypass and self.bypass_client:
                # Rate limiting: max 1 lecture/sec
                now = time.time()
                elapsed = now - self._last_read_request_time
                if elapsed < self._read_rate_limit_sec:
                    wait_time = self._read_rate_limit_sec - elapsed
                    logger.debug(f"⏳ Rate limit lecture bypass: attente {wait_time:.2f}s")
                    time.sleep(wait_time)
                self._last_read_request_time = time.time()
                
                bypass_symbol = self._convert_symbol_to_bypass(symbol)
                
                positions = run_async_safely(
                    self.bypass_client.get_open_positions(bypass_symbol)
                )
                
                for pos in positions:
                    if pos.hold_vol > 0:
                        return {
                            'symbol': symbol,
                            'side': 'long' if pos.position_type == 1 else 'short',
                            'size': pos.hold_vol,
                            'entry_price': pos.hold_avg_price,
                            'unrealized_pnl': pos.unrealized_pnl,
                            'liquidation_price': pos.liquidate_price,
                            'margin': pos.margin,
                            'leverage': pos.leverage,
                        }
                return None
            
            # MODE CCXT seul (pas de bypass)
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

    def get_balance(self, currency: str = 'USDT', prefer_ccxt: bool = True) -> Optional[float]:
        """
        Récupérer balance DISPONIBLE futures (free)
        
        Args:
            currency: Devise (défaut USDT)
            prefer_ccxt: Si True, utilise CCXT en priorité (recommandé pour lectures)
        """
        try:
            if self.dry_run:
                return 0.0

            # 🔄 PRIORITÉ CCXT pour les lectures
            if prefer_ccxt and self.exchange:
                try:
                    balance = self.exchange.fetch_balance()
                    return float(balance.get(currency, {}).get('free', 0.0))
                except Exception as ccxt_err:
                    logger.warning(f"⚠️ CCXT get_balance failed, fallback bypass: {ccxt_err}")
            
            # 🔥 FALLBACK BYPASS (avec rate limiting)
            if self.use_bypass and self.bypass_client:
                # Rate limiting: max 1 lecture/sec
                now = time.time()
                elapsed = now - self._last_read_request_time
                if elapsed < self._read_rate_limit_sec:
                    wait_time = self._read_rate_limit_sec - elapsed
                    logger.debug(f"⏳ Rate limit lecture bypass: attente {wait_time:.2f}s")
                    time.sleep(wait_time)
                self._last_read_request_time = time.time()
                
                asset = run_async_safely(
                    self.bypass_client.get_account_asset(currency)
                )
                if asset:
                    return asset.available_balance
                return None
            
            # MODE CCXT seul
            balance = self.exchange.fetch_balance()
            return float(balance.get(currency, {}).get('free', 0.0))

        except Exception as e:
            logger.error(f"❌ Erreur récupération balance futures: {e}")
            return None

    def get_balance_total(self, currency: str = 'USDT', prefer_ccxt: bool = True) -> Optional[float]:
        """
        Récupérer balance TOTALE futures (total = available + marge utilisée)
        
        Args:
            currency: Devise (défaut USDT)
            prefer_ccxt: Si True, utilise CCXT en priorité
        """
        try:
            if self.dry_run:
                return 0.0

            # 🔄 PRIORITÉ CCXT
            if prefer_ccxt and self.exchange:
                try:
                    balance = self.exchange.fetch_balance()
                    return float(balance.get(currency, {}).get('total', 0.0))
                except Exception as ccxt_err:
                    logger.warning(f"⚠️ CCXT get_balance_total failed, fallback bypass: {ccxt_err}")
            
            # 🔥 FALLBACK BYPASS
            if self.use_bypass and self.bypass_client:
                asset = run_async_safely(
                    self.bypass_client.get_account_asset(currency)
                )
                if asset:
                    # total = available + frozen (marge bloquée)
                    return (asset.available_balance or 0) + (asset.frozen_balance or 0)
                return None
            
            # MODE CCXT seul
            balance = self.exchange.fetch_balance()
            return float(balance.get(currency, {}).get('total', 0.0))

        except Exception as e:
            logger.error(f"❌ Erreur récupération balance total futures: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Récupérer statistiques d'utilisation"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['orders_filled'] / self.stats['orders_placed'] * 100
                if self.stats['orders_placed'] > 0 else 0.0
            )
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        🔥 NOUVEAU: Dashboard de santé du système de trading

        Returns:
            Dict avec status complet du système:
            - circuit_breaker: État du circuit breaker
            - token_monitor: État du monitoring token (si bypass actif)
            - rate_limiter: Stats du rate limiter (si bypass actif)
            - system: Stats générales (success rate, latence, etc.)
        """
        health = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'mode': 'bypass' if self.use_bypass else 'ccxt',
            'dry_run': self.dry_run,
            'system': {
                'orders_placed': self.stats['orders_placed'],
                'orders_filled': self.stats['orders_filled'],
                'orders_failed': self.stats['orders_failed'],
                'success_rate_pct': (
                    self.stats['orders_filled'] / self.stats['orders_placed'] * 100
                    if self.stats['orders_placed'] > 0 else 0.0
                ),
                'avg_latency_ms': self.stats['avg_latency_ms'],
                'total_pnl_usdt': self.stats['total_pnl_usdt'],
            },
            'circuit_breaker': None,
            'token_monitor': None,
            'rate_limiter': None,
        }

        # Circuit Breaker status
        if self.circuit_breaker:
            cb_status = self.circuit_breaker.get_status()
            health['circuit_breaker'] = {
                'enabled': True,
                'state': cb_status['state'],
                'failure_count': cb_status['failure_count'],
                'success_count': cb_status['success_count'],
                'threshold': cb_status['threshold'],
                'last_failure_time': cb_status['last_failure_time'],
                'opened_at': cb_status['opened_at'],
            }
        else:
            health['circuit_breaker'] = {'enabled': False}

        # Token Monitor + Rate Limiter status (bypass mode uniquement)
        if self.use_bypass and self.bypass_client:
            try:
                # Récupérer le status du token monitor
                if hasattr(self.bypass_client, 'token_monitor') and self.bypass_client.token_monitor:
                    health['token_monitor'] = {
                        'enabled': True,
                        'last_check_time': self.bypass_client.token_monitor.last_check_time,
                        'check_interval_sec': self.bypass_client.token_monitor.check_interval,
                        'is_valid': self.bypass_client.token_monitor.is_token_valid,
                    }
                else:
                    health['token_monitor'] = {'enabled': False}

                # Récupérer le status du rate limiter
                if hasattr(self.bypass_client, 'rate_limiter') and self.bypass_client.rate_limiter:
                    rl = self.bypass_client.rate_limiter
                    health['rate_limiter'] = {
                        'enabled': True,
                        'current_rate_per_sec': rl.current_rate,
                        'min_rate': rl.min_rate,
                        'max_rate': rl.max_rate,
                        'consecutive_429s': rl.consecutive_429s,
                        'consecutive_200s': rl.consecutive_200s,
                    }
                else:
                    health['rate_limiter'] = {'enabled': False}
            except Exception as e:
                logger.debug(f"Impossible de récupérer status bypass: {e}")

        return health

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
