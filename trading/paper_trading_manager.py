"""
📝 PAPER TRADING MANAGER - Mode simulation temps réel
Hérite AbstractTradingManager

Simule trading avec :
- Données réelles (prix live)
- Fees simulés
- Slippage simulé
- Latence simulée (optionnel)
- Aucun appel API réel (pas de risque)

Parfait pour :
- Tester stratégies sans risque
- Valider modifications avant Live
- Former utilisateurs
"""

from trading.abstract_trading_manager import AbstractTradingManager, TradingPosition
from typing import Dict, Optional
import logging
import time
import asyncio

logger = logging.getLogger(__name__)


class PaperTradingManager(AbstractTradingManager):
    """
    Gestionnaire Paper Trading (simulation temps réel)
    
    Utilise :
    - Prix réels (via price_provider)
    - Simulation fees/slippage
    - Pas d'appels API réels
    """
    
    def __init__(
        self,
        initial_capital: float = 1000.0,
        price_provider=None,
        analytics_db=None,
        simulate_latency: bool = False,
        latency_ms: int = 100
    ):
        """
        Initialiser Paper Trading
        
        Args:
            initial_capital: Capital initial USDT
            price_provider: Provider pour prix réels
            analytics_db: Analytics DB pour logging
            simulate_latency: Simuler latence exécution
            latency_ms: Latence en ms
        """
        super().__init__(initial_capital)
        
        self.price_provider = price_provider
        self.analytics_db = analytics_db
        self.simulate_latency = simulate_latency
        self.latency_ms = latency_ms
        
        # Calibration (ajuster après 100 trades live)
        self.config.update({
            'taker_fee': 0.0004,  # 0.04% (fees MEXC)
            'slippage_pct': 0.05,  # 0.05% (mesuré en live)
        })
        
        # Cache prix
        self.price_cache: Dict[str, float] = {}
        
        logger.info(f"📝 Paper Trading initialisé | Capital: {initial_capital} USDT | Latence: {latency_ms}ms")
    
    # ==================== IMPLÉMENTATION ABSTRAITE ====================
    
    async def execute_order(self, order: Dict) -> Dict:
        """
        Exécuter ordre (SIMULATION - pas d'API réelle)

        Args:
            order: {
                'type': 'BUY' ou 'SELL',
                'symbol': 'BTC/USDT:USDT',
                'size': 100.0
            }

        Returns:
            {
                'executed': True,
                'price': 45000.0,
                'timestamp': 1234567890,
                'simulated': True
            }
        """
        symbol = order['symbol']
        order_type = order['type']
        size = order['size']

        # Simuler latence si activé
        if self.simulate_latency:
            await asyncio.sleep(self.latency_ms / 1000)

        # Obtenir prix actuel
        price = await self.get_current_price(symbol)

        # Appliquer slippage
        adjusted_price = self.apply_fees_slippage(price, order_type)

        logger.info(
            f"📝 PAPER ORDER: {order_type} {symbol} | "
            f"Size: {size:.2f} USDT | "
            f"Prix: {price:.6f} → {adjusted_price:.6f} (slippage: {self.config['slippage_pct']:.2f}%)"
        )

        return {
            'executed': True,
            'price': adjusted_price,
            'timestamp': time.time(),
            'simulated': True,
            'latency_ms': self.latency_ms if self.simulate_latency else 0
        }
    
    async def get_current_price(self, symbol: str) -> float:
        """
        Obtenir prix actuel (depuis price_provider ou cache)

        Args:
            symbol: Symbole

        Returns:
            Prix actuel
        """
        # Si price_provider disponible, l'utiliser
        if self.price_provider:
            try:
                price_data = await self.price_provider.get_price(symbol)
                if price_data:
                    price = price_data.get('lastPrice', 0) if isinstance(price_data, dict) else price_data
                    if price and price > 0:
                        self.price_cache[symbol] = price
                        return price
            except Exception as e:
                logger.warning(f"⚠️ Erreur get_price: {e}")

        # Fallback: cache
        if symbol in self.price_cache:
            return self.price_cache[symbol]

        # Fallback: 0
        logger.error(f"❌ Aucun prix disponible pour {symbol}")
        return 0.0
    
    def update_price_cache(self, symbol: str, price: float):
        """
        Mettre à jour cache prix (appelé externalement)
        
        Args:
            symbol: Symbole
            price: Prix
        """
        self.price_cache[symbol] = price
    
    # ==================== HOOKS OVERRIDÉS ====================
    
    def on_position_opened(self, position: TradingPosition):
        """Hook après ouverture (log + analytics DB)"""
        super().on_position_opened(position)
        
        # Logger dans Analytics DB si disponible
        if self.analytics_db:
            try:
                setup_data = {
                    'timestamp': position.timestamp,
                    'symbol': position.symbol,
                    'direction': position.direction,
                    'price': position.entry,
                    'entry': position.entry,
                    'sl': position.sl,
                    'tp': position.tp,
                    'position_size': position.size,
                    'capital': position.capital,
                    'condition_types': position.condition_types,
                    'tp_escalier_enabled': position.tp_escalier_enabled,
                    'tp_escalier_levels': position.tp_escalier_levels,
                    'metadata': {'trading_mode': 'PAPER'}
                }
                setup_id = self.analytics_db.insert_validated_setup(setup_data)
                position.setup_id = setup_id
                logger.debug(f"✅ Setup validé loggé (ID: {setup_id})")
            except Exception as e:
                logger.error(f"❌ Erreur log setup validé: {e}")
    
    def on_position_closed(self, position: TradingPosition, result: Dict):
        """Hook après fermeture (log + analytics DB)"""
        super().on_position_closed(position, result)
        
        # Logger trade dans Analytics DB
        if self.analytics_db:
            try:
                trade_data = {
                    **result,
                    'trading_mode': 'PAPER',
                    'setup_id': position.setup_id,
                    'is_backtest': False
                }
                trade_id = self.analytics_db.insert_trade(trade_data)
                logger.debug(f"✅ Trade loggé (ID: {trade_id})")
            except Exception as e:
                logger.error(f"❌ Erreur log trade: {e}")
    
    # ==================== MÉTHODES PUBLIQUES ====================
    
    async def check_active_position(self):
        """
        Vérifier position active (appelé périodiquement)
        
        À appeler depuis une boucle externe (ex: scheduler)
        """
        if not self.active_position:
            return
        
        position = self.active_position

        # Obtenir prix actuel
        current_price = await self.get_current_price(position.symbol)
        if current_price <= 0:
            logger.warning(f"⚠️ Prix invalide pour {position.symbol}")
            return
        
        # Early invalidation (30 premières secondes)
        elapsed = time.time() - position.start_time
        if elapsed <= 30:
            if self.check_early_invalidation(position, current_price):
                self.close_position('EARLY_INVALIDATION', current_price)
                return
        
        # Break-even
        self.update_break_even(position, current_price)
        
        # Trailing stop
        pnl_pct = self.calculate_pnl_pct(position, current_price)
        if pnl_pct > 0.25:  # Activer trailing à +0.25%
            self.update_trailing_stop(position, current_price)
        
        # Vérifier TP/SL
        reason = self.check_tp_sl(position, current_price)
        if reason:
            self.close_position(reason, current_price)
    
    def get_portfolio_summary(self) -> Dict:
        """
        Résumé portefeuille Paper Trading
        
        Returns:
            Dict avec capital, stats, position active, etc.
        """
        stats = self.get_stats()
        
        return {
            'mode': 'PAPER',
            'capital': self.capital,
            'roi': stats['roi'],
            'total_trades': stats['total_trades'],
            'winrate': stats['winrate'],
            'profit_factor': stats['profit_factor'],
            'active_position': self.active_position.to_dict() if self.active_position else None,
            'recent_trades': self.closed_trades[-10:] if self.closed_trades else []
        }


# ==================== HELPER ====================

def create_paper_trading_manager(
    initial_capital: float = 1000.0,
    price_provider=None,
    analytics_db=None
) -> PaperTradingManager:
    """
    Factory pour créer Paper Trading Manager
    
    Args:
        initial_capital: Capital initial
        price_provider: Provider prix réels
        analytics_db: Analytics DB
    
    Returns:
        Instance PaperTradingManager
    """
    return PaperTradingManager(
        initial_capital=initial_capital,
        price_provider=price_provider,
        analytics_db=analytics_db
    )

