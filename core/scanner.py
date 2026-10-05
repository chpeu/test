"""
Scanner de scalabilité pour les paires MEXC
Identifie les meilleures paires pour le scalping basé sur:
- Volatilité optimale
- Spread faible
- Volume élevé
- Profondeur du carnet d'ordres
- Balance bid/ask
- 🔥 OPT: Trend strength (ADX)
- 🔥 OPT: Funding rate filter
- 🔥 OPT: Direction bias (bid/ask imbalance)
"""
import asyncio
from typing import List, Dict, Optional, Tuple
import math
import time

from api.mexc import get_mexc_client
from config import TRADING_CONFIG, DEBUG_ENABLED
from utils.logger import get_logger
from utils.effective_config import get_effective_value

# 🔥 SPRINT 1.2: Exception Handling System
try:
    from core.exceptions import (
        NetworkError, APIError, RateLimitError, MarketDataError,
        PriceDataError, InsufficientDataError,
        TradeCursorError
    )
except ImportError:
    # Fallback si exceptions custom non disponibles
    NetworkError = APIError = RateLimitError = MarketDataError = Exception
    PriceDataError = InsufficientDataError = TradeCursorError = Exception

logger = get_logger()


class ScalabilityScanner:
    """Scanner de scalabilité pour identifier les meilleures paires"""
    
    def __init__(self):
        from core.state_manager import get_state_manager
        state = get_state_manager()
        self.client = get_mexc_client()
        self.price_provider = state.get_price_provider()
        if not self.price_provider:
            from api.price_provider import get_price_provider
            self.price_provider = get_price_provider()
        self.is_scanning = False
        # 🔥 OPT #7: caches par instance (évite contamination tests)
        self._orderbook_cache: Dict[str, Dict] = {}
        self._orderbook_cache_timestamps: Dict[str, float] = {}
        # 🔥 OPT #5: dernière raison de rejet (pour debug)
        self._last_reject_reason: Optional[str] = None
        # 🔥 ORDER FLOW: Historique des spreads pour volatilité
        self._spread_history: Dict[str, List[float]] = {}
        # 🔥 ORDER FLOW: Historique des volumes pour accélération
        self._volume_history: Dict[str, List[float]] = {}
    
    def calculate_volatility(self, data, period: int) -> float:
        """
        Calcul volatilité (écart-type normalisé)
        
        Args:
            data: Liste des prix de clôture ou klines [[timestamp, open, high, low, close, volume]]
            period: Période de calcul
            
        Returns:
            Volatilité en %
        """
        # Extraire les closes si data est une liste de klines
        if data and isinstance(data[0], (list, tuple)) and len(data[0]) >= 5:
            closes = [kline[4] for kline in data]  # Close price is at index 4
        else:
            closes = data
        
        if len(closes) < period:
            return 0.0
        
        recent_closes = closes[-period:]
        mean = sum(recent_closes) / len(recent_closes)
        variance = sum((v - mean) ** 2 for v in recent_closes) / len(recent_closes)
        std = math.sqrt(variance)
        
        return (std / mean) * 100 if mean > 0 else 0.0
    
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        Calcul Average True Range (ATR)
        
        Args:
            highs: Liste des prix high
            lows: Liste des prix low
            closes: Liste des prix de clôture
            period: Période de calcul (défaut: 14)
            
        Returns:
            ATR en valeur absolue
        """
        if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
            # Fallback: utiliser high - low moyen
            if len(highs) >= 5:
                return sum(highs[-5:][i] - lows[-5:][i] for i in range(5)) / 5
            return 0.0
        
        true_ranges = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 1]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Utiliser les dernières 'period' valeurs
        recent_tr = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
        
        return sum(recent_tr) / len(recent_tr) if recent_tr else 0.0
    
    async def fetch_spread_data(self, symbol: str) -> Dict:
        """
        🔥 OPT #7: Récupère spread et profondeur avec CACHE
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dict avec spread, bookDepth, balanceScore, directionBias
        """
        cache_ttl = TRADING_CONFIG.get('scalability_orderbook_cache_ttl', 30)
        now = time.time()
        cache_entry = self._orderbook_cache.get(symbol)
        cache_age = now - self._orderbook_cache_timestamps.get(symbol, 0)
        
        try:
            orderbook = await self.client.fetch_order_book(symbol, limit=5)
            
            default_result = {
                'spread': float('nan'),
                'bookDepth': 0,
                'balanceScore': 0,
                'bidVol': 0,
                'askVol': 0,
                'directionBias': 'NEUTRAL',
                'bidAskRatio': 0.5
            }
            
            if not orderbook or 'bids' not in orderbook or 'asks' not in orderbook:
                return default_result
            
            asks = orderbook['asks']
            bids = orderbook['bids']
            
            if not asks or not bids:
                return default_result
            
            best_ask = float(asks[0][0])
            best_bid = float(bids[0][0])
            
            if not best_ask or not best_bid or best_ask <= 0 or best_bid <= 0:
                return default_result
            
            # Calcul spread
            mid_price = (best_ask + best_bid) / 2
            spread = ((best_ask - best_bid) / mid_price) * 100
            
            # Calcul profondeur
            ask_vol = sum(float(ask[1]) for ask in asks[:5])
            bid_vol = sum(float(bid[1]) for bid in bids[:5])
            total_vol = ask_vol + bid_vol
            
            # Balance score (0-1): 1 = équilibré, 0 = déséquilibré
            bid_ask_ratio = bid_vol / total_vol if total_vol > 0 else 0.5
            balance_score = 1 - (abs(bid_ask_ratio - 0.5) * 2)
            
            # 🔥 OPT #6: Direction bias basé sur déséquilibre bid/ask
            # > 0.6 = pression acheteuse (LONG), < 0.4 = pression vendeuse (SHORT)
            if bid_ask_ratio > 0.6:
                direction_bias = 'LONG'
            elif bid_ask_ratio < 0.4:
                direction_bias = 'SHORT'
            else:
                direction_bias = 'NEUTRAL'
            
            result = {
                'spread': spread,
                'bookDepth': total_vol,
                'balanceScore': balance_score,
                'bidVol': bid_vol,
                'askVol': ask_vol,
                'directionBias': direction_bias,
                'bidAskRatio': bid_ask_ratio
            }

            # 🔥 OPT #7: Mettre en cache
            self._orderbook_cache[symbol] = result
            self._orderbook_cache_timestamps[symbol] = now

            return result

        # 🔥 SPRINT 1.2: Spread calculation - Distinguer erreurs réseau, API, données
        except NetworkError as e:
            # Erreur réseau - fallback sur cache si disponible
            if DEBUG_ENABLED:
                logger.warning(f"⚠️ Erreur réseau spread {symbol}: {e}")
            if cache_entry and cache_age < cache_ttl:
                return cache_entry
            return {
                'spread': float('nan'),
                'bookDepth': 0,
                'balanceScore': 0,
                'bidVol': 0,
                'askVol': 0,
                'directionBias': 'NEUTRAL',
                'note': 'Erreur réseau'
            }
        except APIError as e:
            # Erreur API (symbole invalide, rate limit)
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur API spread {symbol}: {e}")
            # Pas de fallback cache pour erreurs API
            return {
                'spread': float('nan'),
                'bookDepth': 0,
                'balanceScore': 0,
                'bidVol': 0,
                'askVol': 0,
                'directionBias': 'NEUTRAL',
                'note': 'Erreur API'
            }
        except MarketDataError as e:
            # Données marché invalides
            logger.error(f"❌ Données marché invalides spread {symbol}: {e}")
            # 🔥 OPT #7: fallback sur cache si disponible
            if cache_entry and cache_age < cache_ttl:
                return cache_entry
            return {
                'spread': float('nan'),
                'bookDepth': 0,
                'balanceScore': 0,
                'bidVol': 0,
                'askVol': 0,
                'directionBias': 'NEUTRAL',
                'note': 'Données invalides'
            }
        except Exception as e:
            # Erreur inattendue
            logger.error(f"❌ Erreur inattendue spread {symbol}: {type(e).__name__}: {e}")
            # 🔥 OPT #7: fallback sur cache si disponible
            if cache_entry and cache_age < cache_ttl:
                return cache_entry
            return {
                'spread': float('nan'),
                'bookDepth': 0,
                'balanceScore': 0,
                'bidVol': 0,
                'askVol': 0,
                'directionBias': 'NEUTRAL',
                'bidAskRatio': 0.5
            }
    
    def calculate_score(self, pair: Dict, max_volume: float, max_depth: float) -> float:
        """
        🔥 OPT #1/#4/#5: Calcule le score de scalabilité avec paramètres dynamiques (régime)
        
        Formula: (volSpreadRatio × log10(volume) × normFactor × balanceBonus × adxBonus)
        
        Args:
            pair: Données de la paire
            max_volume: Volume max normalisé
            max_depth: Profondeur max normalisée
            
        Returns:
            Score final (0.0 si rejeté)
        """
        symbol = pair.get('symbol', '?')
        self._last_reject_reason = None
        spread = pair.get('spread', float('nan'))
        vol5 = pair.get('vol5', 0.0)
        recent_volume = pair.get('recentVolume', 0)
        book_depth = pair.get('bookDepth', 0)
        balance_score = pair.get('balanceScore', 0)
        funding_rate = pair.get('fundingRate', 0)
        adx = pair.get('adx', 0)
        
        # 🔥 UTILISATION DE GET_EFFECTIVE_VALUE POUR LE RÉGIME DYNAMIQUE
        spread_min = get_effective_value('scalability_spread_min') or 0.001
        tp_sl_mode = get_effective_value('tp_sl_mode') or 'FIXE'
        
        # spread_max dynamique
        spread_max = get_effective_value('scalability_spread_max')
        max_spread_trading = get_effective_value('max_spread_pct') or 0.05
        
        if tp_sl_mode == 'FIXE':
            max_spread_trading = get_effective_value('max_spread_pct_fixe') or max_spread_trading
        else:
            max_spread_trading = get_effective_value('max_spread_pct_atr') or max_spread_trading

        if spread_max is None:
            spread_max = max_spread_trading
        else:
            spread_max = min(spread_max, max_spread_trading)

        volume_min = get_effective_value('scalability_volume_min') or 100000
        funding_max = get_effective_value('scalability_funding_rate_max') or 0.05
        balance_min = get_effective_value('balance_score_min') or 0.7
        log_rejected = get_effective_value('scalability_log_rejected')
        if log_rejected is None: log_rejected = True

        # 🔥 OPT #5: Filtres avec logging des rejets
        reject_reason = None
        
        # Log détaillé pour debug (si activé)
        if DEBUG_ENABLED and symbol in ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']:
            logger.info(f"🔍 [SCORE-DEBUG] {symbol}: spread={spread:.4f}%, vol5={vol5:.4f}%, vol_min={volume_min}, funding={funding_rate:.4f}%")
        
        if math.isnan(spread):
            reject_reason = f"spread=NaN"
        elif spread <= spread_min:
            reject_reason = f"spread={spread:.4f}% < min={spread_min}%"
        elif spread > spread_max:
            reject_reason = f"spread={spread:.4f}% > max={spread_max}%"
        elif book_depth <= 0:
            reject_reason = f"bookDepth={book_depth} <= 0"
        elif recent_volume < volume_min:
            reject_reason = f"volume={recent_volume:.0f} < min={volume_min}"
        elif balance_score < balance_min:
            reject_reason = f"balance={balance_score:.2f} < min={balance_min}"
        elif abs(funding_rate) > funding_max:
            reject_reason = f"fundingRate={funding_rate:.3f}% > max={funding_max}%"
        
        if reject_reason:
            if log_rejected:
                logger.info(f"⏭️ {symbol} rejeté: {reject_reason}")
            self._last_reject_reason = reject_reason
            return 0.0
        
        # Ratio volatilité/spread (plus élevé = mieux)
        vol_spread_ratio = (vol5 / spread) if (spread > 0 and not math.isnan(spread) and vol5 > 0) else 0.0
        
        # Facteur de normalisation (volume + depth)
        norm_factor = 0.5 * (recent_volume / max_volume) + 0.5 * (book_depth / max_depth)
        
        # Bonus balance
        balance_bonus = balance_score
        
        # 🔥 OPT #4: Bonus ADX si trend fort
        adx_threshold = get_effective_value('scalability_adx_bonus_threshold') or 25
        adx_multiplier = get_effective_value('scalability_adx_bonus_multiplier') or 1.2
        adx_bonus = adx_multiplier if adx > adx_threshold else 1.0
        
        # Score brut avec bonus ADX
        raw_score = vol_spread_ratio * math.log10(recent_volume + 1) * norm_factor * balance_bonus * adx_bonus
        
        # Retourner score limité
        final_score = round(raw_score, 2) if (math.isfinite(raw_score) and raw_score >= 0) else 0.0
        self._last_reject_reason = None
        return final_score
    
    def calculate_adx(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """
        🔥 OPT #4: Calcul simplifié ADX pour trend strength
        
        Args:
            highs: Liste des prix high
            lows: Liste des prix low
            closes: Liste des prix close
            period: Période ADX (défaut 14)
            
        Returns:
            ADX value (0-100)
        """
        if len(closes) < period + 1:
            return 0.0
        
        try:
            # Calcul TR, +DM, -DM
            tr_list = []
            plus_dm_list = []
            minus_dm_list = []
            
            for i in range(1, len(closes)):
                high = highs[i]
                low = lows[i]
                prev_high = highs[i-1]
                prev_low = lows[i-1]
                prev_close = closes[i-1]
                
                # True Range
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_list.append(tr)
                
                # +DM, -DM
                plus_dm = max(0, high - prev_high) if high - prev_high > prev_low - low else 0
                minus_dm = max(0, prev_low - low) if prev_low - low > high - prev_high else 0
                plus_dm_list.append(plus_dm)
                minus_dm_list.append(minus_dm)
            
            if len(tr_list) < period:
                return 0.0
            
            # Moyennes lissées
            atr = sum(tr_list[-period:]) / period
            plus_di = (sum(plus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0
            minus_di = (sum(minus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0
            
            # DX et ADX
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0

            return round(dx, 2)

        # 🔥 SPRINT 1.2: DX calculation - Failsafe, return 0.0 sur toute erreur
        except (ValueError, ZeroDivisionError, IndexError) as e:
            # Erreur calcul (données insuffisantes, division par zéro)
            if DEBUG_ENABLED:
                logger.debug(f"Erreur calcul DX: {type(e).__name__}: {e}")
            return 0.0
        except Exception as e:
            # Erreur inattendue
            if DEBUG_ENABLED:
                logger.warning(f"⚠️ Erreur inattendue calcul DX: {type(e).__name__}: {e}")
            return 0.0

    def calculate_orderflow_metrics(
        self,
        symbol: str,
        bid_vol: float,
        ask_vol: float,
        spread: float,
        closes: List[float],
        volumes: List[float]
    ) -> Dict[str, float]:
        """
        🔥 ORDER FLOW: Calcul des métriques avancées pour ML
        
        Args:
            symbol: Symbole de la paire
            bid_vol: Volume bid (acheteurs)
            ask_vol: Volume ask (vendeurs)
            spread: Spread actuel en %
            closes: Liste des prix de clôture
            volumes: Liste des volumes
            
        Returns:
            Dict avec les 6 métriques order flow
        """
        # 1. Delta Volume: pression nette (+ = acheteurs dominent)
        delta_volume = bid_vol - ask_vol
        
        # 2. Imbalance Normalized: ratio [-1, +1]
        total_vol = bid_vol + ask_vol
        imbalance_normalized = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0
        
        # 3. Spread Volatility (écart-type sur les 5 derniers spreads)
        if symbol not in self._spread_history:
            self._spread_history[symbol] = []
        
        # Ajouter le spread actuel à l'historique (max 10 valeurs)
        if not math.isnan(spread) and spread > 0:
            self._spread_history[symbol].append(spread)
            if len(self._spread_history[symbol]) > 10:
                self._spread_history[symbol] = self._spread_history[symbol][-10:]
        
        # Calculer écart-type sur les 5 derniers
        spread_history = self._spread_history.get(symbol, [])
        if len(spread_history) >= 5:
            recent_spreads = spread_history[-5:]
            mean_spread = sum(recent_spreads) / len(recent_spreads)
            variance = sum((s - mean_spread) ** 2 for s in recent_spreads) / len(recent_spreads)
            spread_volatility_5 = math.sqrt(variance)
        else:
            spread_volatility_5 = 0.0
        
        # 4. Book Depth Ratio: bid_vol / ask_vol (> 1 = plus d'acheteurs)
        book_depth_ratio = bid_vol / ask_vol if ask_vol > 0 else 1.0
        
        # 5. Volume Acceleration: dérivée du volume (changement récent)
        if len(volumes) >= 5:
            vol_recent = sum(volumes[-3:]) / 3  # Moyenne 3 dernières
            vol_previous = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else vol_recent  # Moyenne précédentes
            volume_acceleration = (vol_recent - vol_previous) / vol_previous if vol_previous > 0 else 0.0
        else:
            volume_acceleration = 0.0
        
        # 6. Price Momentum 5: % change sur 5 bougies
        if len(closes) >= 5:
            price_momentum_5 = ((closes[-1] - closes[-5]) / closes[-5]) * 100 if closes[-5] > 0 else 0.0
        else:
            price_momentum_5 = 0.0
        
        return {
            'delta_volume': round(delta_volume, 4),
            'imbalance_normalized': round(imbalance_normalized, 4),
            'spread_volatility_5': round(spread_volatility_5, 6),
            'book_depth_ratio': round(book_depth_ratio, 4),
            'volume_acceleration': round(volume_acceleration, 4),
            'price_momentum_5': round(price_momentum_5, 4)
        }

    async def scan_pair(self, symbol: str) -> Optional[Dict]:
        """
        🔥 OPT #4/#9: Scanne une paire avec ADX et klines optimisées
        
        Args:
            symbol: Symbole de la paire
            
        Returns:
            Dict avec les métriques ou None si erreur
        """
        try:
            # 🔥 OPT #9: Nombre de klines configurable (défaut 30 au lieu de 60)
            klines_limit = TRADING_CONFIG.get('scalability_klines_limit', 30)
            
            # Récupérer klines 1m
            klines = await self.client.fetch_ohlcv(symbol, '1m', limit=klines_limit)
            
            if not klines or len(klines) < 15:
                return None
            
            # Parser klines
            highs = [k[2] for k in klines]   # High
            lows = [k[3] for k in klines]    # Low
            closes = [k[4] for k in klines]  # Close
            volumes = [k[5] for k in klines]  # Volume
            
            # Calculer volatilités
            vol5_recent = sum(volumes[-5:])
            vol5_volatility = self.calculate_volatility(closes, 5)
            vol15_recent = sum(volumes[-15:]) if len(volumes) >= 15 else sum(volumes)
            vol15_volatility = self.calculate_volatility(closes, min(15, len(closes)))
            
            # 🔥 OPT #4: Calculer ADX pour trend strength
            adx = self.calculate_adx(highs, lows, closes)
            
            # 🔥 FIX: Calculer ATR pour Market Regime Selector
            atr = self.calculate_atr(highs, lows, closes)
            current_price = closes[-1] if closes else 1
            atr_percent = (atr / current_price) * 100 if current_price > 0 else 0.25

            # 🔥 PHASE 1B: Calculer ATR 5m (approximation depuis klines 1m)
            highs_5m = []
            lows_5m = []
            closes_5m = []
            if len(closes) >= 5:
                for i in range(0, len(closes), 5):
                    chunk_highs = highs[i:i + 5]
                    chunk_lows = lows[i:i + 5]
                    chunk_closes = closes[i:i + 5]
                    if len(chunk_closes) < 5:
                        continue
                    highs_5m.append(max(chunk_highs))
                    lows_5m.append(min(chunk_lows))
                    closes_5m.append(chunk_closes[-1])

            atr_5m = None
            atr_percent_5m = None
            if closes_5m and len(closes_5m) >= 5:
                atr_5m = self.calculate_atr(highs_5m, lows_5m, closes_5m)
                atr_percent_5m = (atr_5m / current_price) * 100 if current_price > 0 else None
            
            # Récupérer spread & depth (avec cache)
            spread_data = await self.fetch_spread_data(symbol)
            
            # 🔥 ORDER FLOW: Calculer les métriques avancées
            orderflow_metrics = self.calculate_orderflow_metrics(
                symbol=symbol,
                bid_vol=spread_data['bidVol'],
                ask_vol=spread_data['askVol'],
                spread=spread_data['spread'],
                closes=closes,
                volumes=volumes
            )
            
            # Construire objet paire
            pair = {
                'symbol': symbol,
                'price': closes[-1] if closes else 0,
                'recentVolume': vol5_recent,
                'vol5': vol5_volatility,
                'vol15': vol15_volatility,
                'spread': spread_data['spread'],
                'bookDepth': spread_data['bookDepth'],
                'balanceScore': spread_data['balanceScore'],
                'bidVol': spread_data['bidVol'],
                'askVol': spread_data['askVol'],
                'directionBias': spread_data.get('directionBias', 'NEUTRAL'),
                'bidAskRatio': spread_data.get('bidAskRatio', 0.5),
                'adx': adx,  # 🔥 OPT #4: ADX pour trend strength
                'atr': atr,  # 🔥 FIX: ATR valeur absolue pour Market Regime
                'atr_percent': atr_percent,  # 🔥 FIX: ATR en % pour Market Regime
                'atr_5m': atr_5m,
                'atr_percent_5m': atr_percent_5m,
                # 🔥 ORDER FLOW: 6 nouvelles métriques pour ML
                'delta_volume': orderflow_metrics['delta_volume'],
                'imbalance_normalized': orderflow_metrics['imbalance_normalized'],
                'spread_volatility_5': orderflow_metrics['spread_volatility_5'],
                'book_depth_ratio': orderflow_metrics['book_depth_ratio'],
                'volume_acceleration': orderflow_metrics['volume_acceleration'],
                'price_momentum_5': orderflow_metrics['price_momentum_5']
            }
            
            return pair

        # 🔥 SPRINT 1.2: Scan pair - Distinguer erreurs données, réseau, calcul
        except NetworkError as e:
            # Erreur réseau (timeout fetch ticker/ohlcv)
            if DEBUG_ENABLED:
                logger.warning(f"⚠️ Erreur réseau scan pair {symbol}: {e}")
            return None
        except APIError as e:
            # Erreur API (symbole invalide, rate limit)
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur API scan pair {symbol}: {e}")
            return None
        except MarketDataError as e:
            # Données marché invalides
            logger.error(f"❌ Données marché invalides scan pair {symbol}: {e}")
            return None
        except InsufficientDataError as e:
            # Données insuffisantes (pas assez de bougies)
            if DEBUG_ENABLED:
                logger.debug(f"Données insuffisantes scan pair {symbol}: {e}")
            return None
        except (ValueError, ZeroDivisionError, KeyError) as e:
            # Erreur calcul métriques
            if DEBUG_ENABLED:
                logger.error(f"❌ Erreur calcul scan pair {symbol}: {type(e).__name__}: {e}")
            return None
        except Exception as e:
            # Erreur inattendue
            logger.error(f"❌ Erreur inattendue scan pair {symbol}: {type(e).__name__}: {e}", exc_info=True)
            return None
    
    async def fetch_funding_rate(self, symbol: str) -> float:
        """
        🔥 OPT #2: Récupérer le funding rate d'une paire
        
        Args:
            symbol: Symbole futures (ex: BTC/USDT:USDT)
            
        Returns:
            Funding rate en % (ex: 0.01 = 0.01%)
        """
        try:
            # MEXC retourne le funding rate via fetch_funding_rate
            funding = await self.client.exchange.fetch_funding_rate(symbol)
            if funding and 'fundingRate' in funding:
                # Convertir en pourcentage
                return float(funding['fundingRate']) * 100
            return 0.0
        # 🔥 SPRINT 1.2: Funding rate - Failsafe, return 0.0 sur toute erreur
        except NetworkError as e:
            # Erreur réseau - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur réseau funding rate: {e}")
            return 0.0
        except APIError as e:
            # Erreur API - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur API funding rate: {e}")
            return 0.0
        except Exception as e:
            # Erreur inattendue - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur inattendue funding rate: {type(e).__name__}: {e}")
            return 0.0

    async def fetch_ticker_volume_24h(self, symbol: str) -> float:
        """
        🔥 OPT #3: Récupérer le volume 24h d'une paire
        
        Args:
            symbol: Symbole
            
        Returns:
            Volume 24h en USDT
        """
        try:
            ticker = await self.client.exchange.fetch_ticker(symbol)
            if ticker and 'quoteVolume' in ticker:
                return float(ticker['quoteVolume'] or 0)
            return 0.0
        # 🔥 SPRINT 1.2: Volume 24h - Failsafe, return 0.0 sur toute erreur
        except NetworkError as e:
            # Erreur réseau - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur réseau volume 24h: {e}")
            return 0.0
        except APIError as e:
            # Erreur API - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur API volume 24h: {e}")
            return 0.0
        except Exception as e:
            # Erreur inattendue - failsafe
            if DEBUG_ENABLED:
                logger.debug(f"Erreur inattendue volume 24h: {type(e).__name__}: {e}")
            return 0.0

    async def scan_top_pairs(self, n: int = 20) -> List[Dict]:
        """
        🔥 OPT #2/#3/#5: Scanne avec pré-filtrage volume 24h et funding rate
        
        Args:
            n: Nombre de paires à retourner
            
        Returns:
            Liste des paires triée par score décroissant
        """
        # 🔥 SPRINT 1: Suppression du flag is_scanning interne (géré par verrou externe StateManager)
        
        # 🔥 OPT #5: Stats des rejets
        reject_stats = {
            'excluded': 0,
            'low_volume_24h': 0,
            'high_funding': 0,
            'scan_failed': 0,
            'score_zero': 0
        }
        
        try:
            # 🔥 OPT #11: Utiliser get_effective_value pour les filtres du scanner
            volume_24h_min = get_effective_value('scalability_volume_24h_min')
            funding_max = get_effective_value('scalability_funding_rate_max')
            # volume_min est utilisé plus loin dans calculate_score via TRADING_CONFIG
            
            logger.info("🔍 Recuperation details futures...")
            
            # Récupérer toutes les paires futures USDT
            markets = await self.client.exchange.load_markets()
            futures_pairs = []
            
            # 🔥 OPT #12: Log de départ
            logger.info(f"📡 {len(markets)} marchés chargés au total")
            
            for symbol, market in markets.items():
                if market.get('type') == 'swap' and market.get('quote') == 'USDT' and market.get('active'):
                    maker_fee = market.get('maker', 0)
                    taker_fee = market.get('taker', 0)
                    major_pairs = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
                    is_major = symbol in major_pairs
                    
                    # 🔥 SPRINT 3: STRICT 0-FEE FILTER
                    # On ne sélectionne QUE les paires à 0 frais (taker == 0)
                    if taker_fee == 0 or is_major:
                        futures_pairs.append({
                            'symbol': symbol,
                            'maker': maker_fee,
                            'taker': taker_fee,
                            'is_major': is_major
                        })
                    else:
                        if DEBUG_ENABLED:
                            logger.debug(f"⏭️ {symbol} ignoré: taker_fee={taker_fee*100:.4f}% > 0%")
            
            logger.info(f"📊 {len(futures_pairs)} paires après filtrage des frais (incluant majeures)")
            
            # Exclure paires manuellement blacklistées
            excluded = set(TRADING_CONFIG.get("excluded_symbols", []))
            if excluded:
                before_len = len(futures_pairs)
                futures_pairs = [p for p in futures_pairs if p['symbol'] not in excluded]
                reject_stats['excluded'] = before_len - len(futures_pairs)
                if reject_stats['excluded'] > 0:
                    logger.info(f"⏭️ {reject_stats['excluded']} paires exclues manuellement")
            
            logger.info(f"📈 Pré-filtrage: volume_24h >= {volume_24h_min:,.0f} USDT, funding <= {funding_max}%")
            
            # 🔥 OPTIMISATION: Utiliser fetch_tickers() pour récupérer TOUS les volumes d'un coup
            # C'est beaucoup plus rapide que fetch_ticker par symbole
            logger.info("📡 Récupération de tous les tickers MEXC...")
            all_tickers = {}
            try:
                all_tickers = await self.client.exchange.fetch_tickers()
                logger.info(f"✅ {len(all_tickers)} tickers récupérés")
            except Exception as e:
                logger.warning(f"⚠️ Erreur fetch_tickers: {e}, repli sur appels individuels")

            # 🔥 DEBUG: Log config values
            # Utiliser get_effective_value pour être raccord avec le filtrage
            eff_spread_max = get_effective_value('scalability_spread_max')
            eff_volume_min = get_effective_value('scalability_volume_min')
            logger.info(f"🔍 Config Effective Scan: spread_max={eff_spread_max}, volume_min={eff_volume_min}, funding_max={funding_max}")
            
            # Récupérer volume 24h et funding rate en batch
            prefilter_batch_size = 20 # Augmenté car on a déjà les volumes
            filtered_pairs = []
            
            for i in range(0, len(futures_pairs), prefilter_batch_size):
                batch = futures_pairs[i:i + prefilter_batch_size]
                
                # Les volumes sont déjà dans all_tickers
                # On ne fetch en parallèle que les funding rates (plus lent)
                funding_tasks = [self.fetch_funding_rate(p['symbol']) for p in batch]
                funding_rates = await asyncio.gather(*funding_tasks, return_exceptions=True)
                
                for j, pair in enumerate(batch):
                    # Récupérer volume depuis all_tickers ou fetch individuel si manquant
                    ticker = all_tickers.get(pair['symbol'], {})
                    vol_24h = ticker.get('quoteVolume') or ticker.get('baseVolume', 0)
                    
                    if vol_24h == 0:
                        # Fallback si ticker manquant
                        vol_24h = await self.fetch_ticker_volume_24h(pair['symbol'])
                    
                    funding = funding_rates[j] if isinstance(funding_rates[j], (int, float)) else 0
                    
                    pair['volume24h'] = vol_24h
                    pair['fundingRate'] = funding
                    
                    # 🔥 DEBUG: Log rejections for specific symbols
                    if pair['symbol'] in ['BTC/USDT:USDT', 'ETH/USDT:USDT']:
                        logger.info(f"🔍 DEBUG {pair['symbol']}: vol_24h={vol_24h:,.0f}, funding={funding:.4f}%")

                    # 🔥 OPT #3: Filtrer par volume 24h
                    if vol_24h < volume_24h_min:
                        reject_stats['low_volume_24h'] += 1
                        continue
                    
                    # 🔥 OPT #2: Filtrer par funding rate
                    if abs(funding) > funding_max:
                        reject_stats['high_funding'] += 1
                        continue
                    
                    filtered_pairs.append(pair)
                
                # Petite pause pour ne pas saturer l'API
                await asyncio.sleep(0.05)
            
            logger.info(
                f"✅ Pré-filtrage: {len(filtered_pairs)}/{len(futures_pairs)} paires retenues | "
                f"Rejetées: vol24h={reject_stats['low_volume_24h']}, funding={reject_stats['high_funding']}"
            )
            
            # Scanner les paires filtrées par batch
            BATCH_SIZE = 5
            total_batches = math.ceil(len(filtered_pairs) / BATCH_SIZE)
            
            for i in range(0, len(filtered_pairs), BATCH_SIZE):
                # 🔥 FIX: Yield control to event loop to prevent WebSocket blocking
                await asyncio.sleep(0)
                
                batch = filtered_pairs[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                progress = f"{i + 1}-{min(i + BATCH_SIZE, len(filtered_pairs))}"
                
                logger.info(f"📊 Batch {batch_num}/{total_batches} ({progress}/{len(filtered_pairs)})")
                
                # Scanner en parallèle
                results = await asyncio.gather(*[self.scan_pair(p['symbol']) for p in batch], return_exceptions=True)
                
                # Intégrer résultats
                for j, result in enumerate(results):
                    if isinstance(result, dict) and result:
                        filtered_pairs[i + j].update(result)
                    else:
                        reject_stats['scan_failed'] += 1
                        # Valeurs par défaut
                        filtered_pairs[i + j].update({
                            'recentVolume': 0,
                            'vol5': 0,
                            'vol15': 0,
                            'spread': float('nan'),
                            'bookDepth': 0,
                            'balanceScore': 0,
                            'bidVol': 0,
                            'askVol': 0,
                            'price': 0,
                            'adx': 0,
                            'atr': 0,
                            'atr_percent': 0,
                            'directionBias': 'NEUTRAL'
                        })
                
                # Pause plus longue entre batches pour laisser le WS respirer
                if i + BATCH_SIZE < len(filtered_pairs):
                    await asyncio.sleep(0.1)
            
            # 🔥 FIX: Yield avant calculs lourds finaux
            await asyncio.sleep(0)
            
            # Calculer normalisations
            valid_pairs = [p for p in filtered_pairs if p.get('recentVolume', 0) > 0]
            max_volume = max([p['recentVolume'] for p in valid_pairs], default=1)
            max_depth = max([p['bookDepth'] for p in valid_pairs], default=1)
            
            # 🔥 OPT #5: Calculer scores avec logging rejets
            for pair in filtered_pairs:
                score = self.calculate_score(pair, max_volume, max_depth)
                pair['score'] = score
                pair['rejectReason'] = self._last_reject_reason
                if score == 0:
                    reject_stats['score_zero'] += 1
            
            # Trier par score décroissant
            filtered_pairs.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # Paires pour le régime (celles qui ont un ATR valide, même si score 0)
            regime_pairs = [p for p in filtered_pairs if p.get('atr_percent') is not None and p.get('atr_percent') > 0]
            
            # Paires pour le trading (score > 0)
            scored_pairs = [p for p in filtered_pairs if p.get('score', 0) > 0]
            top_pairs = scored_pairs[:n]
            
            # 🔥 OPT #5: Log résumé des rejets
            logger.info(
                f"✅ {len(top_pairs)} paires scalables (score>0) | {len(regime_pairs)} paires pour régime | "
                f"Rejets: excluded={reject_stats['excluded']}, vol24h={reject_stats['low_volume_24h']}, "
                f"funding={reject_stats['high_funding']}, scan={reject_stats['scan_failed']}, "
                f"score0={reject_stats['score_zero']}"
            )
            
            # Si on n'a pas de paires avec score > 0, on retourne quand même les paires filtrées pour le régime
            # afin que le MarketRegimeSelector puisse travailler
            if not top_pairs and regime_pairs:
                logger.info(f"⚠️ Aucune paire avec score > 0, retour de {len(regime_pairs)} paires pour détection régime")
                return regime_pairs[:n] # Retourner les meilleures paires par volume/funding même si score 0
                
            return top_pairs

        # 🔥 SPRINT 1.2: Scan scalability top-level - Distinguer toutes erreurs
        except NetworkError as e:
            # Erreur réseau (timeout fetch tickers/ohlcv)
            logger.error(f"❌ Erreur réseau scanner scalabilite: {e}")
            return []
        except APIError as e:
            # Erreur API MEXC (rate limit, endpoint error)
            logger.error(f"❌ Erreur API scanner scalabilite: {e}")
            return []
        except MarketDataError as e:
            # Données marché invalides
            logger.error(f"❌ Données marché invalides scanner scalabilite: {e}")
            return []
        except (ValueError, ZeroDivisionError, KeyError) as e:
            # Erreur calcul métriques
            import traceback
            logger.error(f"❌ Erreur calcul scanner scalabilite: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            return []
        except Exception as e:
            # Erreur totalement inattendue
            import traceback
            logger.error(f"❌ Erreur inattendue scanner scalabilite: {type(e).__name__}: {e}", exc_info=True)
            logger.error(traceback.format_exc())
            return []
        finally:
            self.is_scanning = False
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()

