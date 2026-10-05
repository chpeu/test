"""
BTC Indicator - Phase 1D
Récupère et analyse la volatilité/tendance BTC pour confirmer le régime de marché.
Source: MEXC API (déjà connecté au projet)

Auteur: Cascade AI
Date: 11/12/2025
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BTCTrend(Enum):
    """Tendances BTC possibles"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"


@dataclass
class BTCStatus:
    """Status BTC actuel"""
    price: float
    pct_change_1h: float
    pct_change_24h: float
    is_volatile: bool
    trend: BTCTrend
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'pct_change_1h': self.pct_change_1h,
            'pct_change_24h': self.pct_change_24h,
            'is_volatile': self.is_volatile,
            'trend': self.trend.value,
            'timestamp': self.timestamp.isoformat()
        }


class BTCIndicator:
    """
    Indicateur BTC pour confirmation du régime de marché.
    
    Utilise MEXC API pour récupérer:
    - Prix actuel BTC
    - Variation 1h et 24h
    - Tendance (BULLISH/BEARISH/RANGING)
    """
    
    def __init__(self):
        self.last_status: Optional[BTCStatus] = None
        self.last_fetch: Optional[datetime] = None
        self.cache_duration = timedelta(minutes=5)  # Cache 5 minutes
        self._exchange = None
        
    def _get_exchange(self):
        """Récupère l'instance MEXC exchange"""
        if self._exchange is None:
            try:
                from trading.live_order_manager_futures import get_bypass_client
                bypass = get_bypass_client()
                if bypass:
                    self._exchange = bypass
                    logger.debug("BTCIndicator: Utilisation du bypass client MEXC")
            except Exception as e:
                logger.debug(f"BTCIndicator: Bypass client non disponible: {e}")
            
            if self._exchange is None:
                try:
                    import ccxt
                    self._exchange = ccxt.mexc({
                        'enableRateLimit': True,
                        'options': {'defaultType': 'spot'}
                    })
                    logger.debug("BTCIndicator: Utilisation de ccxt MEXC spot")
                except Exception as e:
                    logger.warning(f"BTCIndicator: Impossible d'initialiser MEXC: {e}")
        
        return self._exchange
    
    async def get_btc_status(self, force_refresh: bool = False) -> Optional[BTCStatus]:
        """
        Récupère le status BTC actuel.
        
        Args:
            force_refresh: Ignorer le cache
            
        Returns:
            BTCStatus ou None si erreur
        """
        from utils.config_persistence import get_config_value
        
        # Vérifier si feature activée
        if not get_config_value('market_regime_btc_indicator_enabled', False):
            return None
        
        # Vérifier cache
        now = datetime.now()
        if not force_refresh and self.last_status and self.last_fetch:
            if now - self.last_fetch < self.cache_duration:
                return self.last_status
        
        try:
            status = await self._fetch_btc_data()
            if status:
                self.last_status = status
                self.last_fetch = now
            return status
        except Exception as e:
            logger.error(f"BTCIndicator: Erreur récupération BTC: {e}")
            return self.last_status  # Retourner cache si erreur
    
    async def _fetch_btc_data(self) -> Optional[BTCStatus]:
        """Récupère les données BTC depuis MEXC"""
        from utils.config_persistence import get_config_value
        
        exchange = self._get_exchange()
        if not exchange:
            return None
        
        try:
            # Récupérer ticker BTC
            ticker = None
            klines_1h = None
            klines_24h = None
            
            # Essayer avec le bypass client (futures)
            if hasattr(exchange, 'get_ticker'):
                try:
                    ticker_data = await self._run_sync(exchange.get_ticker, 'BTC_USDT')
                    if ticker_data:
                        ticker = {
                            'last': float(ticker_data.get('lastPrice', 0)),
                            'percentage': float(ticker_data.get('priceChangePercent', 0))
                        }
                except Exception:
                    pass
            
            # Fallback sur ccxt
            if not ticker and hasattr(exchange, 'fetch_ticker'):
                ticker = await self._run_sync(exchange.fetch_ticker, 'BTC/USDT')
            
            if not ticker:
                logger.warning("BTCIndicator: Impossible de récupérer ticker BTC")
                return None
            
            price = float(ticker.get('last', 0))
            pct_24h = float(ticker.get('percentage', 0))
            
            # Calculer variation 1h depuis klines si disponible
            pct_1h = 0.0
            try:
                if hasattr(exchange, 'fetch_ohlcv'):
                    klines = await self._run_sync(
                        exchange.fetch_ohlcv, 'BTC/USDT', '1h', None, 2
                    )
                    if klines and len(klines) >= 2:
                        price_1h_ago = float(klines[-2][4])  # Close price 1h ago
                        if price_1h_ago > 0:
                            pct_1h = ((price - price_1h_ago) / price_1h_ago) * 100
            except Exception as e:
                logger.debug(f"BTCIndicator: Klines 1h non disponibles: {e}")
                # Estimer 1h = 24h / 24 (approximation)
                pct_1h = pct_24h / 24
            
            # Déterminer volatilité et tendance
            volatile_threshold = get_config_value('market_regime_btc_volatile_threshold_1h', 2.0)
            trend_threshold = get_config_value('market_regime_btc_trend_threshold_24h', 5.0)
            
            is_volatile = abs(pct_1h) >= volatile_threshold
            
            if pct_24h >= trend_threshold:
                trend = BTCTrend.BULLISH
            elif pct_24h <= -trend_threshold:
                trend = BTCTrend.BEARISH
            else:
                trend = BTCTrend.RANGING
            
            status = BTCStatus(
                price=price,
                pct_change_1h=round(pct_1h, 2),
                pct_change_24h=round(pct_24h, 2),
                is_volatile=is_volatile,
                trend=trend,
                timestamp=datetime.now()
            )
            
            logger.info(
                f"📊 BTC Status: ${price:,.0f} | 1h: {pct_1h:+.2f}% | 24h: {pct_24h:+.2f}% | "
                f"Volatile: {is_volatile} | Trend: {trend.value}"
            )
            
            return status
            
        except Exception as e:
            logger.error(f"BTCIndicator: Erreur fetch BTC: {e}")
            return None
    
    async def _run_sync(self, func, *args):
        """Exécute une fonction sync dans un executor"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)
    
    def should_force_volatile(self, current_regime: str) -> bool:
        """
        Détermine si BTC volatil devrait forcer le régime VOLATILE.
        
        Args:
            current_regime: Régime actuel détecté par ATR
            
        Returns:
            True si on doit forcer VOLATILE
        """
        from utils.config_persistence import get_config_value
        
        if not get_config_value('market_regime_btc_force_volatile_enabled', True):
            return False
        
        if not self.last_status:
            return False
        
        # Si BTC est volatile et régime actuel n'est pas VOLATILE
        if self.last_status.is_volatile and current_regime != 'VOLATILE':
            logger.info(
                f"🔥 BTC volatile ({self.last_status.pct_change_1h:+.2f}% 1h) → "
                f"Force régime VOLATILE (était {current_regime})"
            )
            return True
        
        return False
    
    def get_regime_confidence_boost(self, regime: str) -> float:
        """
        Calcule un boost de confiance basé sur la cohérence BTC/régime.
        
        Args:
            regime: Régime détecté
            
        Returns:
            Boost de confiance [-0.2, +0.2]
        """
        if not self.last_status:
            return 0.0
        
        boost = 0.0
        
        # Cohérence volatilité
        if regime == 'VOLATILE' and self.last_status.is_volatile:
            boost += 0.1  # BTC confirme la volatilité
        elif regime == 'CALME' and not self.last_status.is_volatile and abs(self.last_status.pct_change_1h) < 0.5:
            boost += 0.1  # BTC confirme le calme
        
        # Incohérence = réduction confiance
        if regime == 'CALME' and self.last_status.is_volatile:
            boost -= 0.15  # Attention: BTC volatile mais régime calme
        
        return round(boost, 2)


# Singleton
_btc_indicator: Optional[BTCIndicator] = None

def get_btc_indicator() -> BTCIndicator:
    """Récupère l'instance singleton BTCIndicator"""
    global _btc_indicator
    if _btc_indicator is None:
        _btc_indicator = BTCIndicator()
    return _btc_indicator
