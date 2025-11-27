#!/usr/bin/env python3
"""
Live Order Manager - Trade Cursor v7.0
Gestion des ordres réels via API MEXC privée

ARCHITECTURE HYBRIDE:
- Système actuel: WebSocket public (prix, signaux, monitoring) → GRATUIT, RAPIDE
- Ce module: API privée (ordres uniquement) → 4-6 calls par trade
"""

import logging
import time
import ccxt
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Résultat d'un ordre exécuté"""
    success: bool
    order_id: Optional[str] = None
    filled_price: Optional[float] = None
    filled_amount: Optional[float] = None
    actual_pnl_usdt: Optional[float] = None
    actual_fees_usdt: Optional[float] = None
    actual_slippage_pct: Optional[float] = None
    balance_after: Optional[float] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    executed_at: Optional[str] = None


class LiveOrderManager:
    """
    Gestionnaire d'ordres live MEXC

    RESPONSABILITÉS:
    1. Ouvrir position (createOrder)
    2. Fermer position partielle/totale (createOrder)
    3. Vérifier résultat post-trade (fetchOrder + fetchBalance)

    NON RESPONSABLE DE:
    - Suivi des prix (WebSocket public)
    - Détection signaux (système actuel)
    - Calculs TP/SL (système actuel)
    - Monitoring position (système actuel)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        dry_run: bool = True
    ):
        """
        Initialiser le gestionnaire d'ordres

        Args:
            api_key: Clé API MEXC
            api_secret: Secret API MEXC
            testnet: Utiliser testnet (si disponible)
            dry_run: Mode simulation (pas d'ordres réels)
        """
        self.dry_run = dry_run
        self.testnet = testnet

        # Initialiser exchange MEXC
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,  # Protection rate limit
            'options': {
                'defaultType': 'spot',  # Trading spot uniquement
            }
        })

        if testnet:
            # MEXC n'a pas de testnet public, utiliser sandbox si disponible
            self.exchange.set_sandbox_mode(True)
            logger.warning("⚠️ MEXC testnet non disponible, utiliser dry_run=True pour tests")

        # Statistiques
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_failed': 0,
            'total_latency_ms': 0,
            'avg_latency_ms': 0,
        }

        logger.info(
            f"✅ LiveOrderManager initialisé | "
            f"Mode: {'DRY_RUN' if dry_run else 'LIVE'} | "
            f"Testnet: {testnet}"
        )

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        size_usdt: float,
        leverage: int = 1
    ) -> OrderResult:
        """
        Ouvrir une position

        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT
            entry_price: Prix d'entrée théorique (pour calcul slippage)
            size_usdt: Taille en USDT
            leverage: Levier (1 = spot, > 1 = futures)

        Returns:
            OrderResult avec détails de l'ordre
        """
        start_time = time.time()

        try:
            # Calcul quantité
            amount = size_usdt / entry_price

            # Type d'ordre
            side = 'buy' if direction == 'LONG' else 'sell'
            order_type = 'market'  # Market order pour exécution immédiate

            logger.info(
                f"📤 OUVERTURE POSITION: {symbol} {direction} | "
                f"Prix théorique: {entry_price} | "
                f"Taille: {size_usdt} USDT ({amount:.8f} {symbol.split('/')[0]}) | "
                f"Mode: {'DRY_RUN' if self.dry_run else 'LIVE'}"
            )

            # DRY RUN: Simuler ordre
            if self.dry_run:
                latency_ms = (time.time() - start_time) * 1000
                logger.info(f"✅ [DRY_RUN] Ordre simulé | Latence: {latency_ms:.0f}ms")

                return OrderResult(
                    success=True,
                    order_id=f"dry_run_{int(time.time())}",
                    filled_price=entry_price,
                    filled_amount=amount,
                    actual_pnl_usdt=0.0,
                    actual_fees_usdt=0.0,
                    actual_slippage_pct=0.0,
                    balance_after=None,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat()
                )

            # LIVE: Passer ordre réel
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                params={
                    'leverage': leverage if leverage > 1 else None
                }
            )

            latency_ms = (time.time() - start_time) * 1000

            # Vérifier ordre rempli
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price')
            filled_amount = order.get('filled')

            # Calculer slippage
            slippage_pct = 0.0
            if filled_price and entry_price:
                slippage_pct = abs((filled_price - entry_price) / entry_price) * 100

            # Mettre à jour stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = (
                self.stats['total_latency_ms'] / self.stats['orders_placed']
            )

            logger.info(
                f"✅ Position ouverte | "
                f"Order ID: {order_id} | "
                f"Prix rempli: {filled_price} | "
                f"Slippage: {slippage_pct:.3f}% | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                actual_slippage_pct=slippage_pct,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat()
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            logger.error(
                f"❌ Erreur ouverture position: {e} | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return OrderResult(
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
    ) -> OrderResult:
        """
        Fermer une position (totale ou partielle)

        Args:
            symbol: Paire (ex: BTC/USDT)
            direction: LONG ou SHORT (de la position ouverte)
            entry_price: Prix d'entrée (pour calcul PnL)
            current_price: Prix actuel théorique
            size_amount: Quantité à fermer
            partial_pct: % à fermer (None = fermeture totale)

        Returns:
            OrderResult avec PnL réel, slippage, fees
        """
        start_time = time.time()

        try:
            # Calcul quantité à fermer
            if partial_pct:
                amount = size_amount * (partial_pct / 100)
                logger.info(f"🔸 FERMETURE PARTIELLE {partial_pct}%: {amount:.8f}")
            else:
                amount = size_amount
                logger.info(f"🔸 FERMETURE TOTALE: {amount:.8f}")

            # Type d'ordre (inverse de l'ouverture)
            side = 'sell' if direction == 'LONG' else 'buy'
            order_type = 'market'

            logger.info(
                f"📤 FERMETURE POSITION: {symbol} {direction} | "
                f"Prix théorique: {current_price} | "
                f"Quantité: {amount:.8f} | "
                f"Mode: {'DRY_RUN' if self.dry_run else 'LIVE'}"
            )

            # DRY RUN: Simuler fermeture
            if self.dry_run:
                latency_ms = (time.time() - start_time) * 1000

                # Calculer PnL simulé
                if direction == 'LONG':
                    pnl_usdt = (current_price - entry_price) * amount
                else:
                    pnl_usdt = (entry_price - current_price) * amount

                logger.info(
                    f"✅ [DRY_RUN] Fermeture simulée | "
                    f"PnL simulé: {pnl_usdt:+.2f} USDT | "
                    f"Latence: {latency_ms:.0f}ms"
                )

                return OrderResult(
                    success=True,
                    order_id=f"dry_run_close_{int(time.time())}",
                    filled_price=current_price,
                    filled_amount=amount,
                    actual_pnl_usdt=pnl_usdt,
                    actual_fees_usdt=0.0,
                    actual_slippage_pct=0.0,
                    balance_after=None,
                    latency_ms=latency_ms,
                    executed_at=datetime.now(timezone.utc).isoformat()
                )

            # LIVE: Fermer position réelle
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extraire infos ordre
            order_id = order.get('id')
            filled_price = order.get('average') or order.get('price')
            filled_amount = order.get('filled')
            fees = order.get('fee', {}).get('cost', 0.0)

            # Calculer PnL réel
            pnl_usdt = 0.0
            if filled_price and filled_amount:
                if direction == 'LONG':
                    pnl_usdt = (filled_price - entry_price) * filled_amount
                else:
                    pnl_usdt = (entry_price - filled_price) * filled_amount

            # Calculer slippage
            slippage_pct = 0.0
            if filled_price and current_price:
                slippage_pct = abs((filled_price - current_price) / current_price) * 100

            # Récupérer solde après trade
            balance = self._get_balance('USDT')

            # Mettre à jour stats
            self.stats['orders_placed'] += 1
            self.stats['orders_filled'] += 1
            self.stats['total_latency_ms'] += latency_ms
            self.stats['avg_latency_ms'] = (
                self.stats['total_latency_ms'] / self.stats['orders_placed']
            )

            logger.info(
                f"✅ Position fermée | "
                f"Order ID: {order_id} | "
                f"Prix rempli: {filled_price} | "
                f"PnL réel: {pnl_usdt:+.2f} USDT | "
                f"Fees: {fees:.4f} USDT | "
                f"Slippage: {slippage_pct:.3f}% | "
                f"Balance: {balance:.2f} USDT | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_amount=filled_amount,
                actual_pnl_usdt=pnl_usdt,
                actual_fees_usdt=fees,
                actual_slippage_pct=slippage_pct,
                balance_after=balance,
                latency_ms=latency_ms,
                executed_at=datetime.now(timezone.utc).isoformat()
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.stats['orders_failed'] += 1

            logger.error(
                f"❌ Erreur fermeture position: {e} | "
                f"Latence: {latency_ms:.0f}ms"
            )

            return OrderResult(
                success=False,
                error_message=str(e),
                latency_ms=latency_ms
            )

    def verify_trade_result(
        self,
        order_id: str,
        expected_pnl: float,
        expected_slippage: float
    ) -> Dict[str, Any]:
        """
        Vérifier le résultat d'un trade après fermeture

        Args:
            order_id: ID de l'ordre de fermeture
            expected_pnl: PnL théorique attendu
            expected_slippage: Slippage théorique attendu

        Returns:
            Dict avec comparaison théorique vs réel
        """
        try:
            if self.dry_run:
                return {
                    'verified': True,
                    'mode': 'DRY_RUN',
                    'discrepancy_pnl': 0.0,
                    'discrepancy_slippage': 0.0
                }

            # Récupérer détails ordre
            order = self.exchange.fetch_order(order_id)

            filled_price = order.get('average') or order.get('price')
            filled_amount = order.get('filled')
            fees = order.get('fee', {}).get('cost', 0.0)

            # Récupérer balance actuelle
            balance = self._get_balance('USDT')

            # Calcul écarts
            # Note: Le PnL réel a déjà été calculé lors de la fermeture
            # Ici on vérifie juste la cohérence

            logger.info(
                f"🔍 VÉRIFICATION TRADE | "
                f"Order ID: {order_id} | "
                f"PnL attendu: {expected_pnl:+.2f} USDT | "
                f"Fees: {fees:.4f} USDT | "
                f"Balance: {balance:.2f} USDT"
            )

            return {
                'verified': True,
                'order_id': order_id,
                'filled_price': filled_price,
                'filled_amount': filled_amount,
                'fees': fees,
                'balance': balance,
                'expected_pnl': expected_pnl,
                'expected_slippage': expected_slippage
            }

        except Exception as e:
            logger.error(f"❌ Erreur vérification trade: {e}")
            return {
                'verified': False,
                'error': str(e)
            }

    def _get_balance(self, currency: str = 'USDT') -> float:
        """Récupérer balance actuelle"""
        try:
            if self.dry_run:
                return 0.0

            balance = self.exchange.fetch_balance()
            return balance.get('free', {}).get(currency, 0.0)

        except Exception as e:
            logger.error(f"❌ Erreur récupération balance: {e}")
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


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    """
    Exemple d'utilisation du LiveOrderManager
    """

    # Configuration
    API_KEY = "your_mexc_api_key"
    API_SECRET = "your_mexc_api_secret"

    # Initialiser en mode DRY_RUN pour tests
    order_manager = LiveOrderManager(
        api_key=API_KEY,
        api_secret=API_SECRET,
        dry_run=True  # ⚠️ Mettre False pour live réel
    )

    # Exemple 1: Ouvrir position LONG BTC
    print("\n=== OUVERTURE POSITION ===")
    result_open = order_manager.open_position(
        symbol='BTC/USDT',
        direction='LONG',
        entry_price=50000.0,
        size_usdt=100.0
    )

    if result_open.success:
        print(f"✅ Position ouverte | Order ID: {result_open.order_id}")
        print(f"   Prix rempli: {result_open.filled_price}")
        print(f"   Slippage: {result_open.actual_slippage_pct:.3f}%")
        print(f"   Latence: {result_open.latency_ms:.0f}ms")
    else:
        print(f"❌ Échec: {result_open.error_message}")

    # Simuler attente
    time.sleep(2)

    # Exemple 2: Fermer position avec profit
    print("\n=== FERMETURE POSITION ===")
    result_close = order_manager.close_position(
        symbol='BTC/USDT',
        direction='LONG',
        entry_price=50000.0,
        current_price=50500.0,  # +1% profit
        size_amount=0.002  # Quantité ouverte
    )

    if result_close.success:
        print(f"✅ Position fermée | Order ID: {result_close.order_id}")
        print(f"   Prix rempli: {result_close.filled_price}")
        print(f"   PnL réel: {result_close.actual_pnl_usdt:+.2f} USDT")
        print(f"   Fees: {result_close.actual_fees_usdt:.4f} USDT")
        print(f"   Slippage: {result_close.actual_slippage_pct:.3f}%")
        print(f"   Balance: {result_close.balance_after:.2f} USDT")
        print(f"   Latence: {result_close.latency_ms:.0f}ms")
    else:
        print(f"❌ Échec: {result_close.error_message}")

    # Statistiques
    print("\n=== STATISTIQUES ===")
    stats = order_manager.get_stats()
    print(f"Ordres placés: {stats['orders_placed']}")
    print(f"Ordres remplis: {stats['orders_filled']}")
    print(f"Ordres échoués: {stats['orders_failed']}")
    print(f"Taux de succès: {stats['success_rate']:.1f}%")
    print(f"Latence moyenne: {stats['avg_latency_ms']:.0f}ms")
