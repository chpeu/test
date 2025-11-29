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


logger = get_logger()


class ScalabilityScanner:
    """Scanner de scalabilité pour identifier les meilleures paires"""
    
    def __init__(self):
        self.client = get_mexc_client()
        self.is_scanning = False
        # 🔥 OPT #7: caches par instance (évite contamination tests)
        self._orderbook_cache: Dict[str, Dict] = {}
        self._orderbook_cache_timestamps: Dict[str, float] = {}
        # 🔥 OPT #5: dernière raison de rejet (pour debug)
        self._last_reject_reason: Optional[str] = None
    
    def calculate_volatility(self, closes: List[float], period: int) -> float:
        """
        Calcul volatilité (écart-type normalisé)
        
        Args:
            closes: Liste des prix de clôture
            period: Période de calcul
            
        Returns:
            Volatilité en %
        """
        if len(closes) < period:
            return 0.0
        
        recent_closes = closes[-period:]
        mean = sum(recent_closes) / len(recent_closes)
        variance = sum((v - mean) ** 2 for v in recent_closes) / len(recent_closes)
        std = math.sqrt(variance)
        
        return (std / mean) * 100 if mean > 0 else 0.0
    
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

        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur spread pour {symbol}: {e}")
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
        🔥 OPT #1/#4/#5: Calcule le score de scalabilité avec paramètres configurables
        
        Formula: (volSpreadRatio × log10(volume) × normFactor × balanceBonus × adxBonus)
        
        Args:
            pair: Données de la paire
            max_volume: Volume max normalisé
            max_depth: Profondeur max normalisée
            
        Returns:
            Tuple (score, reject_reason) - reject_reason=None si accepté
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
        
        # 🔥 OPT #1: Paramètres configurables (plus hardcodés)
        spread_min = TRADING_CONFIG.get('scalability_spread_min', 0.001)
        spread_max = TRADING_CONFIG.get('scalability_spread_max', 0.02)
        volume_min = TRADING_CONFIG.get('scalability_volume_min', 100000)
        funding_max = TRADING_CONFIG.get('scalability_funding_rate_max', 0.05)
        balance_min = TRADING_CONFIG.get('balance_score_min', 0.7)
        log_rejected = TRADING_CONFIG.get('scalability_log_rejected', True)

        # 🔥 OPT #5: Filtres avec logging des rejets
        reject_reason = None
        
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
            if log_rejected and DEBUG_ENABLED:
                logger.debug(f"⏭️ {symbol} rejeté: {reject_reason}")
            self._last_reject_reason = reject_reason
            return 0.0
        
        # Ratio volatilité/spread (plus élevé = mieux)
        vol_spread_ratio = (vol5 / spread) if (spread > 0 and not math.isnan(spread) and vol5 > 0) else 0.0
        
        # Facteur de normalisation (volume + depth)
        norm_factor = 0.5 * (recent_volume / max_volume) + 0.5 * (book_depth / max_depth)
        
        # Bonus balance
        balance_bonus = balance_score
        
        # 🔥 OPT #4: Bonus ADX si trend fort
        adx_threshold = TRADING_CONFIG.get('scalability_adx_bonus_threshold', 25)
        adx_multiplier = TRADING_CONFIG.get('scalability_adx_bonus_multiplier', 1.2)
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
            
        except Exception:
            return 0.0

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
            
            # Récupérer spread & depth (avec cache)
            spread_data = await self.fetch_spread_data(symbol)
            
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
                'adx': adx  # 🔥 OPT #4: ADX pour trend strength
            }
            
            return pair
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur scan pair {symbol}: {e}")
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
        except Exception:
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
        except Exception:
            return 0.0

    async def scan_top_pairs(self, n: int = 20) -> List[Dict]:
        """
        🔥 OPT #2/#3/#5: Scanne avec pré-filtrage volume 24h et funding rate
        
        Args:
            n: Nombre de paires à retourner
            
        Returns:
            Liste des paires triée par score décroissant
        """
        if self.is_scanning:
            logger.warning("Scanner déjà en cours")
            return []
        
        self.is_scanning = True
        
        # 🔥 OPT #5: Stats des rejets
        reject_stats = {
            'excluded': 0,
            'low_volume_24h': 0,
            'high_funding': 0,
            'scan_failed': 0,
            'score_zero': 0
        }
        
        try:
            logger.info("🔍 Recuperation details futures...")
            
            # Récupérer toutes les paires futures USDT
            markets = await self.client.exchange.load_markets()
            futures_pairs = []
            
            for symbol, market in markets.items():
                if market['type'] == 'swap' and market['quote'] == 'USDT':
                    # Vérifier 0% fees
                    maker_fee = market.get('maker', 0)
                    taker_fee = market.get('taker', 0)
                    if maker_fee == 0 and taker_fee == 0:
                        futures_pairs.append({
                            'symbol': symbol,
                            'maker': maker_fee,
                            'taker': taker_fee
                        })
            
            logger.info(f"📊 {len(futures_pairs)} paires 0% fees retrouvees")
            
            # Exclure paires manuellement blacklistées
            excluded = set(TRADING_CONFIG.get("excluded_symbols", []))
            if excluded:
                before_len = len(futures_pairs)
                futures_pairs = [p for p in futures_pairs if p['symbol'] not in excluded]
                reject_stats['excluded'] = before_len - len(futures_pairs)
                if reject_stats['excluded'] > 0:
                    logger.info(f"⏭️ {reject_stats['excluded']} paires exclues manuellement")
            
            # 🔥 OPT #3: Pré-filtrage par volume 24h (évite scan inutile)
            volume_24h_min = TRADING_CONFIG.get('scalability_volume_24h_min', 500000)
            funding_max = TRADING_CONFIG.get('scalability_funding_rate_max', 0.05)
            
            logger.info(f"📈 Pré-filtrage: volume_24h >= {volume_24h_min:,.0f} USDT, funding <= {funding_max}%")
            
            # Récupérer volume 24h et funding rate en batch
            prefilter_batch_size = 10
            filtered_pairs = []
            
            for i in range(0, len(futures_pairs), prefilter_batch_size):
                batch = futures_pairs[i:i + prefilter_batch_size]
                
                # Récupérer volumes et funding rates en parallèle
                volume_tasks = [self.fetch_ticker_volume_24h(p['symbol']) for p in batch]
                funding_tasks = [self.fetch_funding_rate(p['symbol']) for p in batch]
                
                volumes = await asyncio.gather(*volume_tasks, return_exceptions=True)
                funding_rates = await asyncio.gather(*funding_tasks, return_exceptions=True)
                
                for j, pair in enumerate(batch):
                    vol_24h = volumes[j] if isinstance(volumes[j], (int, float)) else 0
                    funding = funding_rates[j] if isinstance(funding_rates[j], (int, float)) else 0
                    
                    pair['volume24h'] = vol_24h
                    pair['fundingRate'] = funding
                    
                    # 🔥 OPT #3: Filtrer par volume 24h
                    if vol_24h < volume_24h_min:
                        reject_stats['low_volume_24h'] += 1
                        continue
                    
                    # 🔥 OPT #2: Filtrer par funding rate
                    if abs(funding) > funding_max:
                        reject_stats['high_funding'] += 1
                        continue
                    
                    filtered_pairs.append(pair)
                
                # Petite pause
                if i + prefilter_batch_size < len(futures_pairs):
                    await asyncio.sleep(0.02)
            
            logger.info(
                f"✅ Pré-filtrage: {len(filtered_pairs)}/{len(futures_pairs)} paires retenues | "
                f"Rejetées: vol24h={reject_stats['low_volume_24h']}, funding={reject_stats['high_funding']}"
            )
            
            # Scanner les paires filtrées par batch
            BATCH_SIZE = 5
            total_batches = math.ceil(len(filtered_pairs) / BATCH_SIZE)
            
            for i in range(0, len(filtered_pairs), BATCH_SIZE):
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
                            'directionBias': 'NEUTRAL'
                        })
                
                # Petite pause entre batches
                if i + BATCH_SIZE < len(filtered_pairs):
                    await asyncio.sleep(0.05)
            
            # Calculer normalisations
            valid_pairs = [p for p in filtered_pairs if p.get('recentVolume', 0) > 0]
            max_volume = max([p['recentVolume'] for p in valid_pairs], default=1)
            max_depth = max([p['bookDepth'] for p in valid_pairs], default=1)
            
            # 🔥 OPT #5: Calculer scores avec logging rejets
            for pair in filtered_pairs:
                score, reject_reason = self.calculate_score(pair, max_volume, max_depth)
                pair['score'] = score
                pair['rejectReason'] = reject_reason
                if score == 0:
                    reject_stats['score_zero'] += 1
            
            # Filtrer et trier
            scored_pairs = [p for p in filtered_pairs if p.get('score', 0) > 0]
            scored_pairs.sort(key=lambda x: x['score'], reverse=True)
            top_pairs = scored_pairs[:n]
            
            # 🔥 OPT #5: Log résumé des rejets
            logger.info(
                f"✅ {len(top_pairs)} paires scalables classées | "
                f"Rejets: excluded={reject_stats['excluded']}, vol24h={reject_stats['low_volume_24h']}, "
                f"funding={reject_stats['high_funding']}, scan={reject_stats['scan_failed']}, "
                f"score0={reject_stats['score_zero']}"
            )
            
            # Log top 5 pour debug
            if top_pairs and DEBUG_ENABLED:
                top5_info = ", ".join([
                    f"{p['symbol'].split('/')[0]}({p['score']:.1f})"
                    for p in top_pairs[:5]
                ])
                logger.debug(f"🏆 Top 5: {top5_info}")
            
            return top_pairs
            
        except Exception as e:
            logger.error(f"❌ Erreur scanner scalabilite: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
        finally:
            self.is_scanning = False
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()

