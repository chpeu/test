"""
TestableMarketDataCollector - Trade Cursor v7.0 Phase 3
Collecteur de données de marché découplé et testable
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import math

from ..interfaces.scanner_interfaces import (
    IMarketDataCollector, OrderbookData, TickerData, OHLCVData, MarketData,
    DataSource, ScannerValidationUtils
)

logger = logging.getLogger(__name__)


class TestableMarketDataCollector(IMarketDataCollector):
    """
    Collecteur de données de marché découplé et testable
    
    Responsabilités:
    - Collecte orderbook avec cache intelligent
    - Collecte ticker data (prix, volume 24h)
    - Collecte OHLCV multi-timeframe
    - Collecte funding rates
    - Gestion erreurs robuste (Network/API/Data)
    - Cache configurable avec TTL
    """
    
    def __init__(self, client=None, cache_ttl_seconds: int = 30, max_cache_size: int = 1000):
        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_cache_size = max_cache_size
        
        # Cache par type de données
        self._orderbook_cache: Dict[str, Dict[str, Any]] = {}
        self._ticker_cache: Dict[str, Dict[str, Any]] = {}
        self._ohlcv_cache: Dict[str, Dict[str, Any]] = {}
        self._funding_cache: Dict[str, Dict[str, Any]] = {}
        
        # Métriques de performance
        self.collection_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.error_count = 0
        self.total_collection_time_ms = 0.0
        
        # Configuration retry
        self.max_retries = 2
        self.retry_delay_ms = 500
        
        logger.info(f"✅ TestableMarketDataCollector initialisé (cache TTL: {cache_ttl_seconds}s)")
    
    async def collect_orderbook(self, symbol: str, limit: int = 5) -> Optional[OrderbookData]:
        """Collecte les données orderbook pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.collection_count += 1
            
            # Vérifier cache d'abord
            cached_data = self._get_from_cache(self._orderbook_cache, symbol)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"📋 Cache hit orderbook for {symbol}")
                return cached_data['data']
            
            self.cache_misses += 1
            
            # Valider symbole
            if not ScannerValidationUtils.is_valid_symbol(symbol):
                logger.warning(f"Invalid symbol for orderbook: {symbol}")
                return None
            
            # Collecte avec retry
            orderbook_raw = await self._collect_with_retry(
                self._fetch_orderbook_raw, symbol, limit
            )
            
            if not orderbook_raw:
                return None
            
            # Construire OrderbookData
            orderbook_data = self._build_orderbook_data(symbol, orderbook_raw)
            
            # Mettre en cache
            self._put_in_cache(self._orderbook_cache, symbol, orderbook_data)
            
            # Métriques
            collection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_collection_time_ms += collection_time
            
            logger.debug(f"✅ Orderbook collected for {symbol}: spread={orderbook_data.spread_pct:.4f}%, "
                        f"depth={orderbook_data.book_depth:.0f}")
            
            return orderbook_data
            
        except Exception as e:
            logger.error(f"❌ Failed to collect orderbook for {symbol}: {e}")
            self.error_count += 1
            return None
    
    async def collect_ticker(self, symbol: str) -> Optional[TickerData]:
        """Collecte les données ticker pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.collection_count += 1
            
            # Vérifier cache
            cached_data = self._get_from_cache(self._ticker_cache, symbol)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"📋 Cache hit ticker for {symbol}")
                return cached_data['data']
            
            self.cache_misses += 1
            
            # Valider symbole
            if not ScannerValidationUtils.is_valid_symbol(symbol):
                logger.warning(f"Invalid symbol for ticker: {symbol}")
                return None
            
            # Collecte avec retry
            ticker_raw = await self._collect_with_retry(
                self._fetch_ticker_raw, symbol
            )
            
            if not ticker_raw:
                return None
            
            # Construire TickerData
            ticker_data = self._build_ticker_data(symbol, ticker_raw)
            
            # Mettre en cache
            self._put_in_cache(self._ticker_cache, symbol, ticker_data)
            
            # Métriques
            collection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_collection_time_ms += collection_time
            
            logger.debug(f"✅ Ticker collected for {symbol}: price={ticker_data.price:.6f}, "
                        f"vol24h={ticker_data.volume_24h:,.0f}")
            
            return ticker_data
            
        except Exception as e:
            logger.error(f"❌ Failed to collect ticker for {symbol}: {e}")
            self.error_count += 1
            return None
    
    async def collect_ohlcv(self, symbol: str, timeframe: str, limit: int = 30) -> Optional[OHLCVData]:
        """Collecte les données OHLCV pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.collection_count += 1
            
            # Cache key avec timeframe
            cache_key = f"{symbol}_{timeframe}"
            
            # Vérifier cache
            cached_data = self._get_from_cache(self._ohlcv_cache, cache_key)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"📋 Cache hit OHLCV for {symbol} {timeframe}")
                return cached_data['data']
            
            self.cache_misses += 1
            
            # Valider inputs
            if not ScannerValidationUtils.is_valid_symbol(symbol):
                logger.warning(f"Invalid symbol for OHLCV: {symbol}")
                return None
            
            if timeframe not in ['1m', '5m', '15m', '1h', '4h', '1d']:
                logger.warning(f"Invalid timeframe for OHLCV: {timeframe}")
                return None
            
            # Collecte avec retry
            ohlcv_raw = await self._collect_with_retry(
                self._fetch_ohlcv_raw, symbol, timeframe, limit
            )
            
            if not ohlcv_raw:
                return None
            
            # Construire OHLCVData
            ohlcv_data = self._build_ohlcv_data(symbol, timeframe, ohlcv_raw)
            
            # Mettre en cache
            self._put_in_cache(self._ohlcv_cache, cache_key, ohlcv_data)
            
            # Métriques
            collection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_collection_time_ms += collection_time
            
            logger.debug(f"✅ OHLCV collected for {symbol} {timeframe}: {len(ohlcv_data.klines)} candles")
            
            return ohlcv_data
            
        except Exception as e:
            logger.error(f"❌ Failed to collect OHLCV for {symbol} {timeframe}: {e}")
            self.error_count += 1
            return None
    
    async def collect_funding_rate(self, symbol: str) -> Optional[float]:
        """Collecte le taux de funding pour une paire"""
        try:
            start_time = datetime.utcnow()
            self.collection_count += 1
            
            # Vérifier cache
            cached_data = self._get_from_cache(self._funding_cache, symbol)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"📋 Cache hit funding for {symbol}")
                return cached_data['data']
            
            self.cache_misses += 1
            
            # Valider symbole
            if not ScannerValidationUtils.is_valid_symbol(symbol):
                logger.warning(f"Invalid symbol for funding: {symbol}")
                return None
            
            # Collecte avec retry
            funding_raw = await self._collect_with_retry(
                self._fetch_funding_rate_raw, symbol
            )
            
            if funding_raw is None:
                return None
            
            # Convertir en pourcentage si nécessaire
            funding_rate = float(funding_raw) * 100 if abs(funding_raw) <= 1 else float(funding_raw)
            
            # Mettre en cache
            self._put_in_cache(self._funding_cache, symbol, funding_rate)
            
            # Métriques
            collection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_collection_time_ms += collection_time
            
            logger.debug(f"✅ Funding collected for {symbol}: {funding_rate:.4f}%")
            
            return funding_rate
            
        except Exception as e:
            logger.error(f"❌ Failed to collect funding for {symbol}: {e}")
            self.error_count += 1
            return None
    
    async def collect_complete_market_data(self, symbol: str, timeframes: List[str]) -> MarketData:
        """Collecte toutes les données nécessaires pour une paire"""
        try:
            start_time = datetime.utcnow()
            
            # Collecte en parallèle pour optimiser performance
            tasks = []
            
            # Orderbook et ticker (essentiels)
            tasks.append(self.collect_orderbook(symbol))
            tasks.append(self.collect_ticker(symbol))
            
            # OHLCV pour chaque timeframe
            for tf in timeframes:
                tasks.append(self.collect_ohlcv(symbol, tf))
            
            # Funding rate (optionnel)
            tasks.append(self.collect_funding_rate(symbol))
            
            # Exécuter toutes les tâches en parallèle
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Parser résultats
            orderbook = results[0] if not isinstance(results[0], Exception) else None
            ticker = results[1] if not isinstance(results[1], Exception) else None
            
            ohlcv_data = {}
            for i, tf in enumerate(timeframes):
                result_idx = 2 + i
                if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                    ohlcv_data[tf] = results[result_idx]
            
            funding_rate_idx = 2 + len(timeframes)
            funding_rate = (
                results[funding_rate_idx] 
                if funding_rate_idx < len(results) and not isinstance(results[funding_rate_idx], Exception) 
                else None
            )
            
            # Construire MarketData
            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                orderbook=orderbook,
                ticker=ticker,
                source=DataSource.MEXC
            )
            
            # Ajouter OHLCV par timeframe
            for tf, data in ohlcv_data.items():
                if tf == '1m':
                    market_data.ohlcv_1m = data
                elif tf == '5m':
                    market_data.ohlcv_5m = data
                elif tf == '15m':
                    market_data.ohlcv_15m = data
            
            # Ajouter funding rate au ticker si disponible
            if funding_rate is not None and market_data.ticker:
                market_data.ticker.funding_rate = funding_rate
            
            # Calculer qualité des données
            market_data.data_quality = self._calculate_data_quality(market_data)
            
            collection_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            logger.debug(f"✅ Complete market data for {symbol}: quality={market_data.data_quality:.2f}, "
                        f"time={collection_time:.1f}ms")
            
            return market_data
            
        except Exception as e:
            logger.error(f"❌ Failed to collect complete market data for {symbol}: {e}")
            self.error_count += 1
            
            # Retourner MarketData minimal en cas d'erreur
            return MarketData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                data_quality=0.0,
                source=DataSource.MEXC
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0
        
        avg_collection_time = (
            self.total_collection_time_ms / self.collection_count 
            if self.collection_count > 0 else 0.0
        )
        
        return {
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': hit_rate,
                'total_requests': total_requests
            },
            'cache_sizes': {
                'orderbook': len(self._orderbook_cache),
                'ticker': len(self._ticker_cache),
                'ohlcv': len(self._ohlcv_cache),
                'funding': len(self._funding_cache),
                'total': len(self._orderbook_cache) + len(self._ticker_cache) + 
                        len(self._ohlcv_cache) + len(self._funding_cache)
            },
            'performance': {
                'total_collections': self.collection_count,
                'total_errors': self.error_count,
                'error_rate': self.error_count / self.collection_count if self.collection_count > 0 else 0.0,
                'average_collection_time_ms': avg_collection_time
            },
            'configuration': {
                'cache_ttl_seconds': self.cache_ttl_seconds,
                'max_cache_size': self.max_cache_size,
                'max_retries': self.max_retries
            }
        }
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Vide le cache complètement ou pour un symbole"""
        if symbol:
            # Vider cache pour symbole spécifique
            self._orderbook_cache.pop(symbol, None)
            self._ticker_cache.pop(symbol, None)
            self._funding_cache.pop(symbol, None)
            
            # Pour OHLCV, chercher toutes les clés contenant le symbole
            ohlcv_keys_to_remove = [k for k in self._ohlcv_cache.keys() if k.startswith(f"{symbol}_")]
            for key in ohlcv_keys_to_remove:
                self._ohlcv_cache.pop(key, None)
            
            logger.debug(f"Cache cleared for {symbol}")
        else:
            # Vider tout le cache
            self._orderbook_cache.clear()
            self._ticker_cache.clear()
            self._ohlcv_cache.clear()
            self._funding_cache.clear()
            logger.info("All caches cleared")
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Collecte Raw Data
    # =============================================================================
    
    async def _fetch_orderbook_raw(self, symbol: str, limit: int) -> Optional[Dict]:
        """Fetch raw orderbook data"""
        if not self.client:
            logger.warning("No client configured for orderbook fetch")
            return None
        
        try:
            # Normaliser symbole pour MEXC
            mexc_symbol = ScannerValidationUtils.normalize_symbol(symbol)
            
            orderbook = await self.client.fetch_order_book(mexc_symbol, limit=limit)
            
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                logger.debug(f"Invalid orderbook response for {symbol}")
                return None
            
            return orderbook
            
        except Exception as e:
            logger.debug(f"Orderbook fetch error for {symbol}: {e}")
            raise
    
    async def _fetch_ticker_raw(self, symbol: str) -> Optional[Dict]:
        """Fetch raw ticker data"""
        if not self.client:
            logger.warning("No client configured for ticker fetch")
            return None
        
        try:
            # Normaliser symbole pour MEXC
            mexc_symbol = ScannerValidationUtils.normalize_symbol(symbol)
            
            ticker = await self.client.exchange.fetch_ticker(mexc_symbol)
            
            if not ticker:
                logger.debug(f"Invalid ticker response for {symbol}")
                return None
            
            return ticker
            
        except Exception as e:
            logger.debug(f"Ticker fetch error for {symbol}: {e}")
            raise
    
    async def _fetch_ohlcv_raw(self, symbol: str, timeframe: str, limit: int) -> Optional[List]:
        """Fetch raw OHLCV data"""
        if not self.client:
            logger.warning("No client configured for OHLCV fetch")
            return None
        
        try:
            # Normaliser symbole pour MEXC
            mexc_symbol = ScannerValidationUtils.normalize_symbol(symbol)
            
            klines = await self.client.fetch_ohlcv(mexc_symbol, timeframe, limit=limit)
            
            if not klines or len(klines) < 10:
                logger.debug(f"Insufficient OHLCV data for {symbol} {timeframe}: {len(klines) if klines else 0} candles")
                return None
            
            return klines
            
        except Exception as e:
            logger.debug(f"OHLCV fetch error for {symbol} {timeframe}: {e}")
            raise
    
    async def _fetch_funding_rate_raw(self, symbol: str) -> Optional[float]:
        """Fetch raw funding rate data"""
        if not self.client:
            logger.warning("No client configured for funding fetch")
            return None
        
        try:
            # Normaliser symbole pour MEXC
            mexc_symbol = ScannerValidationUtils.normalize_symbol(symbol)
            
            funding = await self.client.exchange.fetch_funding_rate(mexc_symbol)
            
            if not funding or 'fundingRate' not in funding:
                logger.debug(f"Invalid funding response for {symbol}")
                return None
            
            return float(funding['fundingRate'])
            
        except Exception as e:
            logger.debug(f"Funding fetch error for {symbol}: {e}")
            raise
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Construction des Objets
    # =============================================================================
    
    def _build_orderbook_data(self, symbol: str, orderbook_raw: Dict) -> OrderbookData:
        """Construit OrderbookData depuis les données raw"""
        try:
            bids = [(float(bid[0]), float(bid[1])) for bid in orderbook_raw['bids'][:5]]
            asks = [(float(ask[0]), float(ask[1])) for ask in orderbook_raw['asks'][:5]]
            
            orderbook_data = OrderbookData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bids=bids,
                asks=asks
            )
            
            return orderbook_data
            
        except Exception as e:
            logger.error(f"Error building orderbook data for {symbol}: {e}")
            return OrderbookData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bids=[],
                asks=[]
            )
    
    def _build_ticker_data(self, symbol: str, ticker_raw: Dict) -> TickerData:
        """Construit TickerData depuis les données raw"""
        try:
            ticker_data = TickerData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                price=float(ticker_raw.get('last', 0) or ticker_raw.get('close', 0)),
                volume_24h=float(ticker_raw.get('quoteVolume', 0) or ticker_raw.get('baseVolume', 0)),
                price_change_24h=float(ticker_raw.get('change', 0) or 0),
                price_change_24h_pct=float(ticker_raw.get('percentage', 0) or 0),
                high_24h=float(ticker_raw.get('high', 0)) if ticker_raw.get('high') else None,
                low_24h=float(ticker_raw.get('low', 0)) if ticker_raw.get('low') else None
            )
            
            return ticker_data
            
        except Exception as e:
            logger.error(f"Error building ticker data for {symbol}: {e}")
            return TickerData(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                price=0.0,
                volume_24h=0.0
            )
    
    def _build_ohlcv_data(self, symbol: str, timeframe: str, ohlcv_raw: List) -> OHLCVData:
        """Construit OHLCVData depuis les données raw"""
        try:
            # Convertir en format standardisé
            klines = []
            for candle in ohlcv_raw:
                if len(candle) >= 6:
                    klines.append([
                        float(candle[0]),  # timestamp
                        float(candle[1]),  # open
                        float(candle[2]),  # high
                        float(candle[3]),  # low
                        float(candle[4]),  # close
                        float(candle[5])   # volume
                    ])
            
            ohlcv_data = OHLCVData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.utcnow(),
                klines=klines
            )
            
            return ohlcv_data
            
        except Exception as e:
            logger.error(f"Error building OHLCV data for {symbol} {timeframe}: {e}")
            return OHLCVData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.utcnow(),
                klines=[]
            )
    
    # =============================================================================
    # MÉTHODES PRIVÉES - Cache et Utils
    # =============================================================================
    
    def _get_from_cache(self, cache: Dict, key: str) -> Optional[Dict[str, Any]]:
        """Récupère depuis le cache avec vérification TTL"""
        if key not in cache:
            return None
        
        cache_entry = cache[key]
        age_seconds = (datetime.utcnow() - cache_entry['timestamp']).total_seconds()
        
        if age_seconds > self.cache_ttl_seconds:
            # Cache expiré
            del cache[key]
            return None
        
        return cache_entry
    
    def _put_in_cache(self, cache: Dict, key: str, data: Any) -> None:
        """Met en cache avec gestion de la taille max"""
        # Nettoyage si cache trop grand
        if len(cache) >= self.max_cache_size:
            self._cleanup_cache(cache)
        
        cache[key] = {
            'data': data,
            'timestamp': datetime.utcnow()
        }
    
    def _cleanup_cache(self, cache: Dict) -> None:
        """Nettoie le cache en supprimant les entrées les plus anciennes"""
        try:
            # Trier par timestamp et garder les 80% les plus récentes
            sorted_items = sorted(
                cache.items(),
                key=lambda x: x[1]['timestamp'],
                reverse=True
            )
            
            keep_count = int(len(sorted_items) * 0.8)
            cache.clear()
            
            for key, value in sorted_items[:keep_count]:
                cache[key] = value
            
            logger.debug(f"Cache cleanup: kept {keep_count}/{len(sorted_items)} entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
    
    async def _collect_with_retry(self, func, *args, **kwargs) -> Any:
        """Exécute une fonction avec retry automatique"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay_ms = self.retry_delay_ms * (2 ** attempt)  # Backoff exponentiel
                    logger.debug(f"Retry {attempt + 1}/{self.max_retries} after {delay_ms}ms: {e}")
                    await asyncio.sleep(delay_ms / 1000)
                else:
                    logger.debug(f"All retries exhausted for {func.__name__}: {e}")
        
        # Toutes les tentatives ont échoué
        if last_exception:
            raise last_exception
        
        return None
    
    def _calculate_data_quality(self, market_data: MarketData) -> float:
        """Calcule un score de qualité des données (0.0 - 1.0)"""
        try:
            quality_score = 0.0
            max_score = 5.0
            
            # 1. Presence orderbook (20%)
            if market_data.orderbook and market_data.orderbook.bids and market_data.orderbook.asks:
                quality_score += 1.0
            
            # 2. Presence ticker (20%)
            if market_data.ticker and ScannerValidationUtils.is_valid_price(market_data.ticker.price):
                quality_score += 1.0
            
            # 3. OHLCV 1m data (20%)
            if market_data.ohlcv_1m and len(market_data.ohlcv_1m.klines) >= 20:
                quality_score += 1.0
            elif market_data.ohlcv_1m and len(market_data.ohlcv_1m.klines) >= 10:
                quality_score += 0.5
            
            # 4. OHLCV 5m data (20%)
            if market_data.ohlcv_5m and len(market_data.ohlcv_5m.klines) >= 10:
                quality_score += 1.0
            elif market_data.ohlcv_5m and len(market_data.ohlcv_5m.klines) >= 5:
                quality_score += 0.5
            
            # 5. Data freshness (20%)
            data_age = (datetime.utcnow() - market_data.timestamp).total_seconds()
            if data_age <= 30:  # Very fresh
                quality_score += 1.0
            elif data_age <= 120:  # Acceptable
                quality_score += 0.7
            elif data_age <= 300:  # Old but usable
                quality_score += 0.3
            
            return min(1.0, quality_score / max_score)
            
        except Exception as e:
            logger.error(f"Error calculating data quality: {e}")
            return 0.5  # Score neutre en cas d'erreur
