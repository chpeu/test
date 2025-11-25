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
from datetime import datetime, timezone
from functools import wraps

logger = logging.getLogger(__name__)


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


class LiveOrderManagerFutures:
    """
    Gestionnaire d'ordres FUTURES MEXC (Perpetual Swaps)

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
        dry_run: bool = True
    ):
        """
        Initialiser le gestionnaire d'ordres futures

        Args:
            api_key: Clé API MEXC Futures
            api_secret: Secret API MEXC Futures
            default_leverage: Levier par défaut (1-125)
            testnet: Utiliser testnet (si disponible)
            dry_run: Mode simulation (pas d'ordres réels)
        """
        self.dry_run = dry_run
        self.testnet = testnet
        self.default_leverage = min(125, max(1, default_leverage))

        # Initialiser exchange MEXC Futures
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 🔥 FUTURES/Perpetual Swaps
                'adjustForTimeDifference': True,
                'defaultMarginMode': 'isolated',  # 🔥 Mode marge ISOLÉE (jamais croisé)
            }
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)
            logger.warning("⚠️ MEXC Futures testnet - utiliser dry_run=True pour tests")

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

        logger.info(
            f"✅ LiveOrderManagerFutures initialisé | "
            f"Mode: {'DRY_RUN' if dry_run else 'LIVE FUTURES'} | "
            f"Levier défaut: {self.default_leverage}x"
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

        try:
            # Convertir symbole au format futures
            futures_symbol = self._convert_symbol_to_futures(symbol)

            # Calcul quantité en contrats
            # Pour MEXC Futures: amount = size_usdt / entry_price
            amount = size_usdt / entry_price

            # Type d'ordre
            # LONG = buy, SHORT = sell (pour ouvrir)
            side = 'buy' if direction == 'LONG' else 'sell'
            order_type = 'market'

            logger.info(
                f"📤 OUVERTURE FUTURES {direction}: {futures_symbol} | "
                f"Prix théorique: {entry_price} | "
                f"Taille: {size_usdt} USDT | "
                f"Levier: {leverage}x | "
                f"Quantité: {amount:.6f} | "
                f"Mode: {'DRY_RUN' if self.dry_run else 'LIVE'}"
            )

            # DRY RUN: Simuler ordre
            if self.dry_run:
                latency_ms = (time.time() - start_time) * 1000

                # Calculer prix de liquidation simulé
                margin = size_usdt / leverage
                if direction == 'LONG':
                    liq_price = entry_price * (1 - 1/leverage + 0.005)  # ~0.5% buffer
                else:
                    liq_price = entry_price * (1 + 1/leverage - 0.005)

                logger.info(
                    f"✅ [DRY_RUN] Position {direction} simulée | "
                    f"Latence: {latency_ms:.0f}ms | "
                    f"Liq. price: {liq_price:.2f}"
                )

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

            # LIVE: Configurer marge isolée + levier
            if futures_symbol not in self._leverage_cache or self._leverage_cache[futures_symbol] != leverage:
                try:
                    # 🔥 Mode marge ISOLÉE (pas croisé)
                    self.exchange.set_margin_mode('isolated', futures_symbol)
                    self.exchange.set_leverage(leverage, futures_symbol)
                    self._leverage_cache[futures_symbol] = leverage
                    logger.info(f"✅ {futures_symbol}: Marge ISOLÉE + Levier {leverage}x configurés")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible de configurer marge/levier: {e}")

            # LIVE: Passer ordre MARKET (pas de limit, pas de hedge)
            order = self.exchange.create_order(
                symbol=futures_symbol,
                type=order_type,  # 'market'
                side=side,
                amount=amount
                # 🔥 Pas de positionSide = mode one-way (pas hedge)
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos ordre
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price') or entry_price
            filled_amount = order.get('filled') or amount
            fees = order.get('fee', {}).get('cost', 0.0)

            # Calculer slippage
            slippage_pct = abs((filled_price - entry_price) / entry_price) * 100 if filled_price else 0

            # Mettre à jour stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = self.stats['total_latency_ms'] / self.stats['orders_placed']

            logger.info(
                f"✅ Position FUTURES {direction} ouverte | "
                f"Order ID: {order_id} | "
                f"Prix rempli: {filled_price} | "
                f"Slippage: {slippage_pct:.3f}% | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                leverage=leverage,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat()
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            logger.error(
                f"❌ Erreur ouverture position futures: {e} | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return FuturesOrderResult(
                success=False,
                error_message=str(e),
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
            order = self.exchange.create_order(
                symbol=futures_symbol,
                type=order_type,  # 'market'
                side=side,
                amount=amount,
                params={
                    'reduceOnly': True,  # Important: fermeture uniquement
                }
                # 🔥 Pas de positionSide = mode one-way (pas hedge)
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price') or current_price
            filled_amount = order.get('filled') or amount
            fees = order.get('fee', {}).get('cost', 0.0)

            # Calculer PnL réel
            if direction == 'LONG':
                pnl_usdt = (filled_price - entry_price) * filled_amount
            else:
                pnl_usdt = (entry_price - filled_price) * filled_amount

            pnl_usdt -= fees  # Soustraire fees

            # Slippage
            slippage_pct = abs((filled_price - current_price) / current_price) * 100 if filled_price else 0

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
                executed_at=datetime.now(timezone.utc).isoformat()
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
                        'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'
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
                        'positionSide': 'LONG' if direction == 'LONG' else 'SHORT'
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
                            'positionSide': 'LONG' if side == 'long' else 'SHORT'
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
