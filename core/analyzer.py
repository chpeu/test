"""
Analyseur technique pour détecter les setups de trading
Analyse multi-timeframe (1m, 5m) avec indicateurs avancés
"""
import asyncio
import time
from typing import List, Dict, Optional
import math

from api.mexc import get_mexc_client
from api.price_provider import get_price_provider
from core.indicators import Indicators
from config import TRADING_CONFIG, DEBUG_ENABLED, CONDITION_WEIGHTS, TREND_BONUS_CONFIG
from utils.logger import get_logger


logger = get_logger()


class TechnicalAnalyzer:
    """Analyseur technique pour détecter les setups LONG/SHORT"""
    
    def __init__(self):
        self.client = get_mexc_client()
        self.indicators = Indicators()
        self.price_provider = get_price_provider()  # 🔥 JOUR 2: Prix WebSocket
        # 🔥 PHASE 3: Cache spread (5 secondes)
        self._spread_cache: Dict[str, Dict] = {}
        # 🔥 PHASE 2: Cache orderbook (2 secondes)
        self._orderbook_cache: Dict[str, Dict] = {}
    
    async def calculate_trend_data(self, symbol: str, timeframe: str = '15m') -> Optional[Dict]:
        """
        Calculer les données de tendance pour un timeframe donné
        
        Args:
            symbol: Symbole de la paire
            timeframe: Timeframe (5m, 15m, 30m, 1h)
            
        Returns:
            Dict avec trend (BULLISH/BEARISH/NEUTRAL), strength, bonus
        """
        try:
            # Mapper le timeframe vers le format ccxt
            timeframe_map = {
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '1h': '1h'
            }
            ccxt_tf = timeframe_map.get(timeframe, '15m')
            
            # Récupérer OHLCV pour le timeframe
            ohlcv = await self.client.fetch_ohlcv(symbol, ccxt_tf, limit=100)
            
            if not ohlcv or len(ohlcv) < 100:
                return None
            
            # Extraire closes
            closes = [candle[4] for candle in ohlcv]  # Close price
            
            # Calculer EMAs
            ema20 = self.indicators.calculate_ema(closes, 20)
            ema50 = self.indicators.calculate_ema(closes, 50)
            ema100 = self.indicators.calculate_ema(closes, 100)
            
            # Prix actuel
            price = closes[-1]
            
            # Déterminer la tendance
            trend = 'NEUTRAL'
            strength = 'NONE'
            bonus = 0
            
            if ema20 > ema50 and ema50 > ema100 and price > ema20:
                trend = 'BULLISH'
                strength = 'STRONG'
                bonus = 25
            elif ema20 > ema50 and price > ema20:
                trend = 'BULLISH'
                strength = 'MODERATE'
                bonus = 15
            elif ema20 < ema50 and ema50 < ema100 and price < ema20:
                trend = 'BEARISH'
                strength = 'STRONG'
                bonus = 25
            elif ema20 < ema50 and price < ema20:
                trend = 'BEARISH'
                strength = 'MODERATE'
                bonus = 15
            
            return {
                'trend': trend,
                'strength': strength,
                'bonus': bonus
            }
        except Exception as e:
            logger.warning(f"⚠️ Erreur calcul trend_data pour {symbol} ({timeframe}): {e}")
            return None
    
    def check_volume_quality(self, vol_spike: float, atr: float, price: float, volume24h: float) -> Dict:
        """
        Vérifie la qualité du volume
        
        Args:
            vol_spike: Ratio volume spike
            atr: ATR
            price: Prix actuel
            volume24h: Volume 24h
            
        Returns:
            Dict avec quality, warnings, shouldTrade
        """
        warnings = []
        quality = 100
        
        # Cohérence Volume/ATR
        atr_percent = (atr / price) * 100 if price > 0 else 0
        volume_atr_ratio = vol_spike / max(atr_percent * 0.1, 0.1) if atr_percent > 0 else 0
        
        if volume_atr_ratio > 3.0:
            warnings.append('Volume élevé sans mouvement')
            quality -= 20
        
        # Liquidité
        if volume24h < 1000000 and volume24h > 0:
            warnings.append('Liquidité faible')
            quality -= 15
        
        return {
            'quality': quality,
            'warnings': warnings,
            'shouldTrade': quality >= 70
        }
    
    def calculate_position_size(self, setup: Dict, account_size: float = 10000.0) -> Dict:
        """
        Calcule la taille de position optimale
        
        Args:
            setup: Setup de trading
            account_size: Taille du compte
            
        Returns:
            Dict avec size, risk, reason
        """
        base_risk = 0.02  # 2%
        
        # Ajustement selon nombre de conditions
        condition_count = len(setup.get('signals', []))
        
        if condition_count >= 7:
            quality_multiplier = 1.5
        elif condition_count >= 6:
            quality_multiplier = 1.2
        elif condition_count >= 5:
            quality_multiplier = 0.8
        else:
            quality_multiplier = 0.5
        
        # Ajustement selon volatilité
        atr = setup.get('atr', 0)
        price = setup.get('price', setup.get('entry', 1))
        atr_percent = (atr / price) * 100 if price > 0 else 0
        
        if atr_percent > 2.0:
            vol_multiplier = 0.7
        elif atr_percent < 0.5:
            vol_multiplier = 1.3
        else:
            vol_multiplier = 1.0
        
        final_risk = base_risk * quality_multiplier * vol_multiplier
        final_risk = max(0.005, min(final_risk, 0.05))
        
        # Calcul taille
        entry = float(setup.get('entry', 1))
        sl = float(setup.get('sl', 1))
        stop_loss_percent = abs((sl - entry) / entry * 100)
        
        position_size = (account_size * final_risk) / (stop_loss_percent / 100) if stop_loss_percent > 0 else 0
        
        return {
            'size': round(position_size, 2),
            'risk': f"{final_risk * 100:.2f}%",
            'reason': f"Conditions: {condition_count} | Quality: {quality_multiplier:.2f}x | Vol: {vol_multiplier:.2f}x"
        }
    
    async def analyze_timeframe(
        self,
        symbol: str,
        timeframe: str,
        trend_data: Optional[Dict] = None,
        volume_multiplier: float = 1.0,
        return_reason: bool = False
    ) -> Optional[Dict]:
        """
        Analyse un timeframe pour détecter un setup
        
        Args:
            symbol: Symbole de la paire
            timeframe: '1m' ou '5m'
            trend_data: Données de tendance (optionnel)
            volume_multiplier: Multiplicateur de volume (0.1-2.0)
            
        Returns:
            Dict avec setup ou None
        """
        try:
            # 🔥 JOUR 2: Récupérer prix via WebSocket (prioritaire) ou REST
            ticker_data = await self.price_provider.get_price(symbol)
            if not ticker_data:
                reason = f"Prix non disponible (WebSocket ou REST) pour {symbol}"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # 🔥 FIX: Vérifier que ticker_data est un dict, pas une liste
            if not isinstance(ticker_data, dict):
                reason = f"Format de données prix invalide (attendu dict, reçu {type(ticker_data).__name__}) pour {symbol}"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                logger.error(f"{symbol} {timeframe}: {reason}")
                return None
            
            current_price = float(ticker_data.get('lastPrice', 0))
            if current_price == 0:
                reason = f"Prix invalide (0) pour {symbol}"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # Récupérer OHLCV pour indicateurs
            # 🔥 FIX: Vérifier que le symbole est au bon format pour ccxt
            # ccxt utilise le format standardisé SOL/USDT:USDT, pas besoin de conversion
            try:
                ohlcv = await self.client.fetch_ohlcv(symbol, timeframe, limit=100)
            except Exception as e:
                reason = f"Erreur fetch OHLCV: {str(e)} (symbole: {symbol})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.error(f"{symbol} {timeframe}: {reason}")
                return None
            
            if not ohlcv or len(ohlcv) < 20:
                reason = f"Données OHLCV insuffisantes: {len(ohlcv) if ohlcv else 0} bougies (min 20)"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                return None
            
            # Extraire données
            closes = [k[4] for k in ohlcv]  # Close
            highs = [k[2] for k in ohlcv]  # High
            lows = [k[3] for k in ohlcv]  # Low
            volumes = [k[5] for k in ohlcv]  # Volume
            
            current_candle = ohlcv[-1]
            # 🔥 JOUR 2: Utiliser prix WebSocket (plus récent) au lieu de closes[-1]
            price = current_price
            
            # Calculer indicateurs
            rsi = self.indicators.calculate_rsi(closes, 14)
            rsi_prev = self.indicators.calculate_rsi_previous(closes, 14)
            atr = self.indicators.calculate_atr(highs, lows, closes, 14)
            ema9 = self.indicators.calculate_ema(closes, 9)
            ema21 = self.indicators.calculate_ema(closes, 21)
            macd = self.indicators.calculate_macd(closes, 3, 10, 16)
            macd_prev = self.indicators.calculate_macd_previous(closes, 3, 10, 16)
            bb = self.indicators.calculate_bollinger_bands(closes, 20, 2)
            adx = self.indicators.calculate_adx(highs, lows, closes, 14)
            
            # Patterns (simple + multi-bougies)
            pattern = self.indicators.detect_pattern(current_candle)
            # Si pattern simple non trouvé, essayer multi-bougies
            if pattern == 'NONE':
                pattern = self.indicators.detect_pattern_multi(ohlcv[-3:])
            
            # Volume spike
            avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
            recent_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 1
            vol_spike = recent_vol / avg_vol if avg_vol > 0 else 1
            
            # ATR percent
            atr_percent = (atr / price) * 100 if price > 0 else 0
            
            # Min volume ratio adaptatif
            base_min_vol = 1.0 if atr_percent > 1.0 else (0.6 if atr_percent < 0.3 else 0.8)
            min_vol_ratio = base_min_vol * volume_multiplier
            min_vol_ratio = max(0.4, min(1.5, min_vol_ratio))
            
            # 🔥 FIX: Log détaillé pour comprendre le calcul du volume
            logger.debug(
                f"📊 {symbol} {timeframe}: Volume | "
                f"ATR%: {atr_percent:.3f} | "
                f"Base min_vol: {base_min_vol:.2f}x | "
                f"Volume multiplier: {volume_multiplier:.2f} | "
                f"Min requis: {min_vol_ratio:.2f}x | "
                f"Vol actuel: {vol_spike:.2f}x"
            )
            
            # Filtrer volume
            if vol_spike < min_vol_ratio:
                reason = f"Volume insuffisant: {vol_spike:.2f}x < {min_vol_ratio:.2f}x requis (base: {base_min_vol:.2f}x × mult: {volume_multiplier:.2f})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # Filtrer micro-range
            min_range = atr_percent * 0.2
            min_range = max(0.0003, min(0.003, min_range))
            candle_range = ((current_candle[2] - current_candle[3]) / price) * 100  # high - low
            
            if candle_range < min_range:
                reason = f"Bougie plate: range={candle_range:.4f}% < {min_range:.4f}% requis"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # Filtre ATR optimal
            if timeframe == '1m':
                optimal_atr_min = TRADING_CONFIG['optimal_atr_min_1m']
                optimal_atr_max = TRADING_CONFIG['optimal_atr_max_1m']
            else:
                optimal_atr_min = TRADING_CONFIG['optimal_atr_min_5m']
                optimal_atr_max = TRADING_CONFIG['optimal_atr_max_5m']
            
            if atr_percent < optimal_atr_min or atr_percent > optimal_atr_max:
                atr_status = 'trop bas' if atr_percent < optimal_atr_min else 'trop élevé'
                reason = f"ATR sous-optimal: {atr_percent:.3f}% ({atr_status}, optimal: {optimal_atr_min}-{optimal_atr_max}%)"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # === PHASE 1 + 2: NOUVEAUX FILTRES ===
            
            # 1. SNR Filter (Signal-to-Noise Ratio)
            snr = abs(price - ema21) / atr if atr > 0 else 0
            snr_threshold = TRADING_CONFIG.get('snr_threshold', 0.3)
            
            # 🔥 FIX: Log détaillé pour comprendre le calcul du SNR
            logger.debug(
                f"📊 {symbol} {timeframe}: SNR | "
                f"Price: {price:.6f} | EMA21: {ema21:.6f} | Diff: {abs(price - ema21):.6f} | "
                f"ATR: {atr:.6f} | SNR: {snr:.3f} | Seuil: {snr_threshold}"
            )
            
            if snr < snr_threshold:
                reason = f"SNR trop faible: {snr:.3f} < {snr_threshold} (signal plat)"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # 2. Breakout Filter
            breakout_mult = TRADING_CONFIG.get('breakout_threshold', 0.3)
            breakout_threshold = atr * breakout_mult
            if price < ema21 + breakout_threshold and price > ema21 - breakout_threshold:
                reason = f"Pas de breakout: prix dans range ±ATR*{breakout_mult} autour de EMA21"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # 3. Wick Ratio Filter (manipulation)
            body = abs(current_candle[1] - current_candle[4])  # open - close
            if body == 0:
                body = 0.0001  # Éviter division par 0
            wick_ratio = (current_candle[2] - current_candle[3]) / body  # high - low
            wick_max = TRADING_CONFIG.get('wick_ratio_max', 2.5)
            if wick_ratio > wick_max:
                reason = f"Wicks suspects: ratio={wick_ratio:.2f} > {wick_max} (possible manipulation)"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # 🔥 PHASE 3: Conditions LONG avec tracking des types pour score pondéré
            long_conditions = []
            long_condition_types = []  # Types de conditions pour calculer le score pondéré
            
            # 1. EMAs
            ema_diff_percent = ((ema9 - ema21) / ema21) * 100
            if ema9 > ema21 and ema_diff_percent > 0.05:
                long_conditions.append(f"EMAs Up ({ema_diff_percent:.3f}%)")
                long_condition_types.append('EMAs')
            
            # 2. RSI
            rsi_rebound = rsi >= 30 and rsi <= 40 and adx['adx'] < 20 and rsi > rsi_prev
            rsi_pullback = rsi >= 45 and rsi <= 55 and macd['histogram'] > 0 and adx['adx'] > 25 and rsi > rsi_prev
            
            if rsi_rebound:
                long_conditions.append(f"RSI Rebound↑ (ADX<{adx['adx']:.1f})")
                long_condition_types.append('RSI')
            elif rsi_pullback:
                long_conditions.append(f"RSI Pullback↑ (ADX>{adx['adx']:.1f})")
                long_condition_types.append('RSI')
            
            # 3. Volume
            if vol_spike > 1.5:
                long_conditions.append(f"Vol >>{vol_spike:.1f}x")
            else:
                long_conditions.append(f"Vol >{min_vol_ratio:.1f}x")
            long_condition_types.append('Volume')  # Volume toujours présent
            
            # 4. MACD
            macd_bullish = macd['macd'] > macd['signal'] or macd['histogram'] > 0
            macd_momentum = macd['histogram'] > macd_prev['histogram']
            
            if macd_bullish and macd_momentum:
                long_conditions.append("MACD+↑ (momentum)")
                long_condition_types.append('MACD')
            elif macd_bullish:
                long_conditions.append("MACD+")
                long_condition_types.append('MACD')
            
            # 5. Bollinger
            dist_to_lower = ((price - bb['lower']) / bb['lower']) * 100 if bb['upper'] > 0 else 999
            bb_threshold = max(0.3, atr_percent * 0.5)
            if dist_to_lower < bb_threshold:
                long_conditions.append("BB Lower")
                long_condition_types.append('Bollinger')
            
            # 6. ADX + DI Gap (remplace ADX >30 seul)
            di_gap = adx['diPlus'] - adx['diMinus']
            di_gap_min = TRADING_CONFIG.get('di_gap_min', 5)
            di_gap_adx_threshold = TRADING_CONFIG.get('di_gap_adx_threshold', 25)
            if adx['adx'] > di_gap_adx_threshold and adx['diPlus'] > adx['diMinus'] and abs(di_gap) > di_gap_min:
                long_conditions.append("ADX+ + DI Gap>" + str(abs(di_gap)))
                long_condition_types.append('ADX_DI')
            elif adx['adx'] > 30 and adx['diPlus'] > adx['diMinus']:
                long_conditions.append("ADX+ (>30)")
                long_condition_types.append('ADX_DI')
            
            # 7. Pattern
            long_patterns = [
                'ENGULFING_BULLISH', 'HAMMER',
                'DOJI_DRAGONFLY', 'MARUBOZU_BULLISH',
                'MORNING_STAR', 'DOJI'
            ]
            if pattern in long_patterns:
                long_conditions.append(f"Pattern: {pattern}")
                long_condition_types.append('Pattern')
            
            # 🔥 PHASE 3: Conditions SHORT avec tracking des types pour score pondéré
            short_conditions = []
            short_condition_types = []  # Types de conditions pour calculer le score pondéré
            
            # 1. EMAs
            ema_diff_percent_short = ((ema21 - ema9) / ema21) * 100
            if ema9 < ema21 and ema_diff_percent_short > 0.05:
                short_conditions.append(f"EMAs Down ({ema_diff_percent_short:.3f}%)")
                short_condition_types.append('EMAs')
            
            # 2. RSI
            rsi_overbought = rsi >= 60 and rsi <= 70 and adx['adx'] < 20 and rsi < rsi_prev
            rsi_rejection = rsi >= 45 and rsi <= 55 and macd['histogram'] < 0 and adx['adx'] > 25 and rsi < rsi_prev
            
            if rsi_overbought:
                short_conditions.append(f"RSI Overbought↓ (ADX<{adx['adx']:.1f})")
                short_condition_types.append('RSI')
            elif rsi_rejection:
                short_conditions.append(f"RSI Rejection↓ (ADX>{adx['adx']:.1f})")
                short_condition_types.append('RSI')
            
            # 3. Volume
            if vol_spike > 1.5:
                short_conditions.append(f"Vol >>{vol_spike:.1f}x")
            else:
                short_conditions.append(f"Vol >{min_vol_ratio:.1f}x")
            short_condition_types.append('Volume')  # Volume toujours présent
            
            # 4. MACD
            macd_bearish = macd['macd'] < macd['signal'] or macd['histogram'] < 0
            macd_momentum_down = macd['histogram'] < macd_prev['histogram']
            
            if macd_bearish and macd_momentum_down:
                short_conditions.append("MACD-↓ (momentum)")
                short_condition_types.append('MACD')
            elif macd_bearish:
                short_conditions.append("MACD-")
                short_condition_types.append('MACD')
            
            # 5. Bollinger
            dist_to_upper = ((bb['upper'] - price) / price) * 100 if bb['upper'] > 0 else 999
            if dist_to_upper < bb_threshold:
                short_conditions.append("BB Upper")
                short_condition_types.append('Bollinger')
            
            # 6. ADX + DI Gap (remplace ADX >30 seul)
            di_gap_short = adx['diMinus'] - adx['diPlus']
            if adx['adx'] > di_gap_adx_threshold and adx['diMinus'] > adx['diPlus'] and abs(di_gap_short) > di_gap_min:
                short_conditions.append("ADX- + DI Gap>" + str(abs(di_gap_short)))
                short_condition_types.append('ADX_DI')
            elif adx['adx'] > 30 and adx['diMinus'] > adx['diPlus']:
                short_conditions.append("ADX- (>30)")
                short_condition_types.append('ADX_DI')
            
            # 7. Pattern
            short_patterns = [
                'ENGULFING_BEARISH', 'SHOOTING_STAR',
                'DOJI_GRAVESTONE', 'MARUBOZU_BEARISH',
                'EVENING_STAR'
            ]
            if pattern in short_patterns:
                short_conditions.append(f"Pattern: {pattern}")
                short_condition_types.append('Pattern')
            
            # 🔥 PHASE 3: Calculer scores pondérés
            use_weighted = TRADING_CONFIG.get('use_weighted_scoring', True)
            
            def calculate_weighted_score(condition_types: List[str]) -> float:
                """Calcule le score pondéré basé sur les types de conditions"""
                score = 0.0
                for cond_type in condition_types:
                    score += CONDITION_WEIGHTS.get(cond_type, 1.0)  # Par défaut 1.0 si type inconnu
                return score
            
            # Calculer scores LONG et SHORT
            long_score = calculate_weighted_score(long_condition_types) if use_weighted else len(long_conditions)
            short_score = calculate_weighted_score(short_condition_types) if use_weighted else len(short_conditions)
            
            # Tolérance dynamique ADX (scores minimums)
            min_conditions = 6  # Par défaut pour compatibilité
            if use_weighted:
                min_score_required = TRADING_CONFIG.get('min_score_required', 7.5)
                if adx['adx'] > 30:
                    min_score_required = TRADING_CONFIG.get('min_score_adx_high', 7.0)
                elif adx['adx'] < 25:
                    min_score_required = TRADING_CONFIG.get('min_score_adx_low', 8.0)
            else:
                # Système ancien (comptage simple)
                if adx['adx'] > 30:
                    min_conditions = 5
                elif adx['adx'] >= 25:
                    min_conditions = 5.5
                min_score_required = min_conditions  # Pour compatibilité
            
            # Direction temporaire (basée sur score ou comptage)
            temp_direction = 'NEUTRAL'
            if use_weighted:
                if long_score >= min_score_required:
                    temp_direction = 'LONG'
                elif short_score >= min_score_required:
                    temp_direction = 'SHORT'
            else:
                if len(long_conditions) >= min_conditions:
                    temp_direction = 'LONG'
                elif len(short_conditions) >= min_conditions:
                    temp_direction = 'SHORT'
            
            # 🔥 PHASE 2: Trend bonus (corrigé)
            trend_score_bonus = 0.0
            if trend_data and temp_direction != 'NEUTRAL':
                if isinstance(trend_data, dict):
                    bonus_value = trend_data.get('bonus', 0)
                    divisor = TREND_BONUS_CONFIG.get('bonus_divisor', 5)
                    if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
                        trend_score_bonus = bonus_value / divisor  # 25 → 5.0 au lieu de 2.5
                    elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
                        trend_score_bonus = bonus_value / divisor
                else:
                    logger.warning(f"⚠️ trend_data invalide (attendu dict, reçu {type(trend_data).__name__}) pour {symbol}")
            
            # PHASE 2: Divergence RSI/MACD (calcul avant direction)
            divergence_bonus = 0
            if temp_direction == 'LONG':
                if rsi < rsi_prev and macd['histogram'] > macd_prev['histogram']:
                    divergence_bonus = 1
                    long_conditions.append("Divergence+ ↑")
                    long_condition_types.append('Divergence')
            elif temp_direction == 'SHORT':
                if rsi > rsi_prev and macd['histogram'] < macd_prev['histogram']:
                    divergence_bonus = 1
                    short_conditions.append("Divergence- ↓")
                    short_condition_types.append('Divergence')
            
            # 🔥 PHASE 2: Ajouter trend_bonus au score (si use_direct_score)
            if use_weighted and TREND_BONUS_CONFIG.get('use_direct_score', True):
                long_score += trend_score_bonus if temp_direction == 'LONG' else 0
                short_score += trend_score_bonus if temp_direction == 'SHORT' else 0
                # Recalculer si divergence ajoutée
                if divergence_bonus > 0:
                    if temp_direction == 'LONG':
                        long_score = calculate_weighted_score(long_condition_types) + trend_score_bonus
                    else:
                        short_score = calculate_weighted_score(short_condition_types) + trend_score_bonus
            else:
                # Système ancien (bonus conditionnel)
                trend_bonus = int(trend_score_bonus)  # Arrondir pour compatibilité
                long_with_bonus = len(long_conditions) + (trend_bonus if temp_direction == 'LONG' else 0)
                short_with_bonus = len(short_conditions) + (trend_bonus if temp_direction == 'SHORT' else 0)
            
            # Vérifier avec score pondéré ou comptage
            direction = 'NEUTRAL'
            if use_weighted:
                if long_score >= min_score_required:
                    direction = 'LONG'
                elif short_score >= min_score_required:
                    direction = 'SHORT'
            else:
                if long_with_bonus >= min_conditions:
                    direction = 'LONG'
                elif short_with_bonus >= min_conditions:
                    direction = 'SHORT'
            
            # 🔥 PHASE 1: Logs détaillés avec scores
            if direction == 'NEUTRAL':
                if use_weighted:
                    reason = (
                        f"Score insuffisant: Long={len(long_conditions)}+{trend_score_bonus:.1f} "
                        f"[{', '.join(long_condition_types[:5])}] → Score: {long_score:.1f}/{min_score_required:.1f} ❌ | "
                        f"Short={len(short_conditions)} [{', '.join(short_condition_types[:5])}] → Score: {short_score:.1f}/{min_score_required:.1f} ❌"
                    )
                else:
                    reason = f"Conditions insuffisantes: Long={len(long_conditions)}+{trend_bonus} Short={len(short_conditions)} (min={min_conditions} requis)"
                
                if return_reason:
                    return {
                        'reason': reason, 'symbol': symbol, 'timeframe': timeframe,
                        'long_conditions': len(long_conditions), 'short_conditions': len(short_conditions),
                        'min_required': min_score_required if use_weighted else min_conditions,
                        'long_score': long_score if use_weighted else None,
                        'short_score': short_score if use_weighted else None
                    }
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # Cohérence EMA/MACD
            if direction == 'LONG' and ema9 > ema21 and macd['histogram'] <= -0.001:
                reason = f"Incohérence EMA/MACD: EMA9>EMA21 mais MACD très négatif (histogram={macd['histogram']:.4f})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            if direction == 'SHORT' and ema9 < ema21 and macd['histogram'] >= 0.001:
                reason = f"Incohérence EMA/MACD: EMA9<EMA21 mais MACD très positif (histogram={macd['histogram']:.4f})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # Volume quality check BLOQUANT
            vol_quality = self.check_volume_quality(vol_spike, atr, price, 0)  # volume24h non utilisé pour l'instant
            if not vol_quality['shouldTrade'] or vol_quality['quality'] < 75:
                warnings_str = ", ".join(vol_quality.get('warnings', [])) if vol_quality.get('warnings') else "Aucun"
                reason = f"Volume quality rejeté: {vol_quality['quality']}% < 75% (warnings: {warnings_str})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe, 'quality': vol_quality['quality']}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None
            
            # PHASE 2: Structure swing HH/HL (blocking)
            if len(highs) >= 5 and len(lows) >= 5:
                recent_highs = highs[-5:]
                recent_lows = lows[-5:]
                
                if direction == 'LONG':
                    hh = recent_highs[-1] > recent_highs[-2]
                    hl = recent_lows[-1] > recent_lows[-2]
                    has_swing = hh or hl
                else:  # SHORT
                    lh = recent_highs[-1] < recent_highs[-2]
                    ll = recent_lows[-1] < recent_lows[-2]
                    has_swing = lh or ll
                
                if not has_swing:
                    reason = f"Pas de structure swing: {direction} requis (HH/HL pour LONG, LH/LL pour SHORT)"
                    if return_reason:
                        return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe, 'direction': direction}
                    if DEBUG_ENABLED:
                        logger.debug(f"{symbol} {timeframe}: {reason}")
                    return None
            
            # Sélectionner conditions finales
            conditions = long_conditions if direction == 'LONG' else short_conditions
            
            # TP/SL pour monitoring
            if direction == 'LONG':
                entry = price
                sl = entry * 0.9975  # -0.25%
                tp = entry * 1.0025  # +0.25%
            else:
                entry = price
                sl = entry * 1.0025  # +0.25%
                tp = entry * 0.9975  # -0.25%
            
            # 🔥 PHASE 1: LOG DÉTAILLÉ avec score pondéré
            if use_weighted:
                condition_types = long_condition_types if direction == 'LONG' else short_condition_types
                final_score = long_score if direction == 'LONG' else short_score
                score_info = f"Score: {final_score:.1f}/{min_score_required:.1f} | Conditions: {len(conditions)}"
            else:
                score_info = f"Conditions: {len(conditions)}/{min_conditions}"
            
            logger.info(
                f"✅ {symbol} {timeframe}: SETUP TROUVÉ - {direction} | "
                f"{score_info} | "
                f"RSI: {rsi:.1f} | Vol: {vol_spike:.2f}x | ATR: {atr_percent:.3f}% | "
                f"Entry: {entry:.6f} | SL: {sl:.6f} | TP: {tp:.6f} | "
                f"EMA9/21: {ema9:.6f}/{ema21:.6f} | MACD: {macd['histogram']:.6f} | "
                f"ADX: {adx['adx']:.1f} (DI+:{adx['diPlus']:.1f}/DI-:{adx['diMinus']:.1f}) | "
                f"Pattern: {pattern} | "
                f"Signals: {', '.join(conditions[:5])}" + (f" (+{len(conditions)-5} autres)" if len(conditions) > 5 else "")
            )
            
            # 🔥 PHASE 5: Ajouter condition_types pour métriques
            condition_types = long_condition_types if direction == 'LONG' else short_condition_types
            
            # 🔥 PHASE 2: Calculer score total pour position sizing
            use_weighted = TRADING_CONFIG.get('use_weighted_scoring', True)
            if use_weighted:
                final_score = long_score if direction == 'LONG' else short_score
            else:
                final_score = len(conditions) + (trend_score_bonus if trend_score_bonus else 0)
            
            return {
                'symbol': symbol,
                'direction': direction,
                'entry': round(entry, 6),
                'sl': round(sl, 6),
                'tp': round(tp, 6),
                'rsi': round(rsi, 1),
                'volumeSpike': round(vol_spike, 1),
                'signals': conditions,
                'condition_types': condition_types,  # 🔥 PHASE 5: Types de conditions pour métriques
                'totalScore': final_score,  # 🔥 PHASE 2: Score total pour position sizing
                'min_score_required': min_score_required,  # 🔥 PHASE 6: Score minimum requis (pour Recovery Mode)
                'timeframe': timeframe,
                'volatility': atr / price if price > 0 else 0,
                'atr': atr,
                'atr_percent': (atr / price * 100) if price > 0 else 0,  # 🔥 PHASE 2: ATR % pour position sizing
                'price': price,
                'ohlcv': ohlcv  # 🔥 PHASE 2: OHLCV pour détection pump & dump
            }
            
        except Exception as e:
            import traceback
            error_msg = f"Exception lors de l'analyse {timeframe}: {str(e)}"
            # 🔥 DEBUG: Log traceback complet pour identifier l'emplacement exact
            logger.error(f"❌ Erreur analyse {symbol} {timeframe}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if return_reason:
                return {'reason': error_msg, 'symbol': symbol, 'timeframe': timeframe, 'error': True}
            if DEBUG_ENABLED:
                logger.error(f"Erreur analyse {symbol} {timeframe}: {e}")
            return None
    
    async def analyze_pair(
        self,
        symbol: str,
        trend_data: Optional[Dict] = None,
        volume_multiplier: float = 1.0,
        use_confluence: bool = False,
        return_reason: bool = False,
        active_positions: Optional[List[str]] = None,
        position_manager = None
    ) -> Optional[Dict]:
        """
        Analyse une paire sur 1m et 5m
        
        Args:
            symbol: Symbole de la paire
            trend_data: Données de tendance
            volume_multiplier: Multiplicateur de volume
            use_confluence: True = 1m ET 5m, False = 1m OU 5m
            
        Returns:
            Meilleur setup ou None
        """
        try:
            # 🔥 PHASE 2: Toujours calculer trend_data (au lieu d'optionnel)
            if trend_data is None:
                trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
                trend_data = await self.calculate_trend_data(symbol, trend_timeframe)
                if trend_data:
                    logger.debug(f"📊 {symbol}: Trend {trend_data.get('trend', 'NEUTRAL')} ({trend_timeframe}) - Bonus: {trend_data.get('bonus', 0)}")
            
            # Analyser 1m
            analysis_1m = await self.analyze_timeframe(symbol, '1m', trend_data, volume_multiplier, return_reason=return_reason)
            analysis_5m = await self.analyze_timeframe(symbol, '5m', trend_data, volume_multiplier, return_reason=return_reason)
            
            # 🔥 FIX: Ne pas retourner immédiatement une raison si l'autre timeframe est valide
            # En mode permissif, on peut utiliser un timeframe même si l'autre est rejeté
            
            # 🔥 LOG DÉTAILLÉ: Résumé des analyses 1m et 5m
            if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                logger.info(
                    f"📊 {symbol} 1m: VALIDE - {analysis_1m['direction']} | "
                    f"Conditions: {len(analysis_1m['signals'])} | "
                    f"RSI: {analysis_1m.get('rsi', 0):.1f} | Vol: {analysis_1m.get('volumeSpike', 0):.2f}x | "
                    f"ATR: {(analysis_1m.get('atr', 0) / analysis_1m.get('price', 1) * 100):.3f}%"
                )
            elif analysis_1m and isinstance(analysis_1m, dict) and 'reason' in analysis_1m:
                logger.info(f"❌ {symbol} 1m: REJETÉ - {analysis_1m.get('reason', 'Raison inconnue')}")
            
            if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                logger.info(
                    f"📊 {symbol} 5m: VALIDE - {analysis_5m['direction']} | "
                    f"Conditions: {len(analysis_5m['signals'])} | "
                    f"RSI: {analysis_5m.get('rsi', 0):.1f} | Vol: {analysis_5m.get('volumeSpike', 0):.2f}x | "
                    f"ATR: {(analysis_5m.get('atr', 0) / analysis_5m.get('price', 1) * 100):.3f}%"
                )
            elif analysis_5m and isinstance(analysis_5m, dict) and 'reason' in analysis_5m:
                logger.info(f"❌ {symbol} 5m: REJETÉ - {analysis_5m.get('reason', 'Raison inconnue')}")
            
            # 🔥 PHASE 3: Vérifier spread avant validation finale
            best_setup = None
            if use_confluence and analysis_1m and analysis_5m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                # Confluence: 1m ET 5m valides
                # Prendre le meilleur (score le plus élevé ou conditions les plus nombreuses)
                best_setup = analysis_1m if len(analysis_1m.get('signals', [])) >= len(analysis_5m.get('signals', [])) else analysis_5m
            elif not use_confluence:
                # Mode permissif: 1m OU 5m
                if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                    best_setup = analysis_1m
                elif analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                    best_setup = analysis_5m
            
            if best_setup:
                # 🔥 PHASE 3: Vérifier spread avant validation finale
                spread_check = await self._check_spread(symbol)
                
                if not spread_check['valid']:
                    logger.warning(
                        f"⚠️ {symbol} - Setup rejeté : Spread trop élevé "
                        f"({spread_check['spread_pct']:.3f}% > {spread_check['max_allowed']:.3f}%)"
                    )
                    return None
                
                # Ajouter info spread au setup
                best_setup['spread_pct'] = spread_check['spread_pct']
                best_setup['spread_quality'] = spread_check['quality']
                
                # 🔥 PHASE 2: Vérifier orderbook imbalance avant validation finale
                orderbook_check = await self._check_orderbook_imbalance(
                    symbol=symbol,
                    direction=best_setup['direction']
                )
                
                if not orderbook_check['valid']:
                    # 🔥 Afficher le seuil correct selon la direction
                    required_str = '≥1.1' if best_setup['direction'] == 'LONG' else '≤0.95'
                    logger.warning(
                        f"⚠️ {symbol} - Setup {best_setup['direction']} rejeté : "
                        f"Orderbook défavorable (ratio={orderbook_check['ratio']:.2f}, required={required_str})"
                    )
                    return None
                
                # Bonus si orderbook très favorable
                if orderbook_check['quality'] == 'EXCELLENT':
                    # Ajouter au score total si disponible
                    if 'totalScore' in best_setup:
                        best_setup['totalScore'] += 1.0
                
                best_setup['orderbook_ratio'] = orderbook_check['ratio']
                best_setup['orderbook_quality'] = orderbook_check['quality']
                
                # 🔥 PHASE 2: Vérifier manipulation pump & dump
                # Récupérer OHLCV depuis l'analyse si disponible
                ohlcv_data = None
                if best_setup.get('timeframe') == '1m' and analysis_1m:
                    ohlcv_data = analysis_1m.get('ohlcv')
                elif best_setup.get('timeframe') == '5m' and analysis_5m:
                    ohlcv_data = analysis_5m.get('ohlcv')
                # Fallback : utiliser celui qui est disponible
                if not ohlcv_data and analysis_1m:
                    ohlcv_data = analysis_1m.get('ohlcv')
                elif not ohlcv_data and analysis_5m:
                    ohlcv_data = analysis_5m.get('ohlcv')
                
                manipulation_check = self._detect_manipulation(
                    symbol=symbol,
                    timeframe=best_setup.get('timeframe', '1m'),
                    ohlcv=ohlcv_data,
                    volume=best_setup.get('volumeSpike', 0),
                    vol_spike=best_setup.get('volumeSpike', 0)
                )
                
                if manipulation_check['suspicious']:
                    logger.warning(
                        f"⚠️ {symbol} - Setup {best_setup['direction']} rejeté : "
                        f"Manipulation suspectée ({manipulation_check['reason']})"
                    )
                    return None
                
                # 🔥 PHASE 6: Vérifier corrélation avec positions actives
                if active_positions:
                    correlation_check = await self._check_correlation(symbol, active_positions)
                    
                    if not correlation_check['valid']:
                        # HARD mode: Rejeter
                        logger.warning(f"⚠️ {symbol} - Setup rejeté: {correlation_check['reason']}")
                        if return_reason:
                            return {'reason': correlation_check['reason'], 'symbol': symbol}
                        return None
                    elif correlation_check.get('penalty', 0) != 0:
                        # SOFT mode: Appliquer pénalité au score
                        penalty = correlation_check['penalty']
                        if 'totalScore' in best_setup:
                            best_setup['totalScore'] += penalty
                            logger.info(f"⚠️ {symbol} - Corrélation (SOFT): Score {best_setup['totalScore']:.1f} après pénalité {penalty}")
                
                # 🔥 PHASE 6: Recovery Mode - Ajuster score minimum et confluence
                recovery_config = TRADING_CONFIG.get('recovery_mode', {})
                min_score_required = best_setup.get('min_score_required', TRADING_CONFIG.get('min_score_required', 7.5))
                
                if recovery_config.get('enabled', False) and position_manager:
                    recovery_mode_active = position_manager.config.recovery_mode_active if hasattr(position_manager, 'config') else False
                    
                    if recovery_mode_active:
                        recovery_boost = recovery_config.get('min_score_boost', 1.5)
                        adjusted_min_score = min_score_required + recovery_boost
                        
                        # Forcer confluence si configuré
                        if recovery_config.get('confluence_forced', False):
                            use_confluence = True
                            # Vérifier que confluence est respectée
                            if not (analysis_1m and analysis_5m and 
                                    not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) and 
                                    not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m)):
                                logger.warning(f"⚠️ {symbol} - Setup rejeté (Recovery Mode): Confluence requise")
                                if return_reason:
                                    return {'reason': 'Recovery Mode: Confluence requise', 'symbol': symbol}
                                return None
                        
                        # Vérifier score avec boost
                        setup_score = best_setup.get('totalScore', 0)
                        if setup_score < adjusted_min_score:
                            logger.warning(
                                f"⚠️ {symbol} - Setup rejeté (Recovery Mode): "
                                f"Score {setup_score:.1f} < {adjusted_min_score:.1f} (min: {min_score_required:.1f} + boost: {recovery_boost:.1f})"
                            )
                            if return_reason:
                                return {
                                    'reason': f'Recovery Mode: Score insuffisant ({setup_score:.1f} < {adjusted_min_score:.1f})',
                                    'symbol': symbol
                                }
                            return None
                        
                        logger.info(
                            f"✅ {symbol} - Setup validé (Recovery Mode): "
                            f"Score {setup_score:.1f} >= {adjusted_min_score:.1f}"
                        )
                
                # Mettre à jour min_score_required dans le setup
                best_setup['min_score_required'] = min_score_required
                
                return best_setup
            
            # Confluence ou mode permissif (ancien code pour compatibilité)
            if use_confluence and analysis_1m and analysis_5m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                # MODE CONFLUENCE STRICTE
                if analysis_1m['direction'] != analysis_5m['direction']:
                    reason = f"Confluence: directions opposées (1m={analysis_1m['direction']}, 5m={analysis_5m['direction']})"
                    if return_reason:
                        return {'reason': reason, 'symbol': symbol, 'timeframe': '1m+5m'}
                    if DEBUG_ENABLED:
                        logger.debug(reason)
                    return None
                
                strength_1m = len(analysis_1m['signals'])
                strength_5m = len(analysis_5m['signals'])
                
                if strength_5m < strength_1m * 0.8:
                    reason = f"Confluence: 5m trop faible (1m={strength_1m} conds, 5m={strength_5m} conds, besoin ≥{strength_1m*0.8:.1f})"
                    if return_reason:
                        return {'reason': reason, 'symbol': symbol, 'timeframe': '1m+5m'}
                    if DEBUG_ENABLED:
                        logger.debug(reason)
                    return None
                
                # Retourner le meilleur
                best = analysis_1m if strength_1m >= strength_5m else analysis_5m
                best['confirmedBy'] = '1m + 5m confluence'
                best['symbol'] = symbol  # 🔥 FIX: Ajouter symbol au setup
                if analysis_1m and analysis_5m:
                    best['atr5m'] = analysis_5m['atr']
                
                # 🔥 LOG DÉTAILLÉ: Confluence réussie
                logger.info(
                    f"✅ {symbol}: CONFLUENCE RÉUSSIE - {best['direction']} | "
                    f"1m: {strength_1m} conditions | 5m: {strength_5m} conditions | "
                    f"Meilleur: {best['timeframe']} | "
                    f"Entry: {best['entry']:.6f} | SL: {best['sl']:.6f} | TP: {best['tp']:.6f}"
                )
                
                return best
            else:
                # MODE PERMISSIF avec priorité par force
                # Filtrer les raisons (ne pas les compter comme des analyses valides)
                valid_1m = analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m)
                valid_5m = analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m)
                
                strength_1m = len(analysis_1m['signals']) if valid_1m else 0
                strength_5m = len(analysis_5m['signals']) if valid_5m else 0
                
                if strength_1m > 0 or strength_5m > 0:
                    best = analysis_1m if strength_1m > strength_5m else analysis_5m
                    best['confirmedBy'] = f"{best['timeframe']} only ({len(best['signals'])} conds)"
                    best['symbol'] = symbol  # 🔥 FIX: Ajouter symbol au setup
                    if analysis_1m and analysis_5m and valid_1m and valid_5m:
                        best['atr5m'] = analysis_5m['atr']
                    
                    # 🔥 LOG DÉTAILLÉ: Mode permissif - setup trouvé
                    logger.info(
                        f"✅ {symbol}: SETUP (Mode permissif) - {best['direction']} | "
                        f"Timeframe: {best['timeframe']} | Conditions: {len(best['signals'])} | "
                        f"1m: {strength_1m} | 5m: {strength_5m} | "
                        f"Entry: {best['entry']:.6f} | SL: {best['sl']:.6f} | TP: {best['tp']:.6f}"
                    )
                    
                    return best
            
            # Aucun timeframe valide
            reasons = []
            if analysis_1m and isinstance(analysis_1m, dict) and 'reason' in analysis_1m:
                reasons.append(f"1m: {analysis_1m['reason']}")
            elif not analysis_1m:
                reasons.append("1m: None (pas de setup)")
                
            if analysis_5m and isinstance(analysis_5m, dict) and 'reason' in analysis_5m:
                reasons.append(f"5m: {analysis_5m['reason']}")
            elif not analysis_5m:
                reasons.append("5m: None (pas de setup)")
            
            # 🔥 FIX: Si return_reason=True, retourner une raison combinée
            if return_reason:
                reason = f"Aucun timeframe valide. " + " | ".join(reasons) if reasons else "Aucune raison spécifique"
                return {'reason': reason, 'symbol': symbol, 'timeframe': '1m+5m'}
            
            return None
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur analyse pair {symbol}: {e}")
            return None
    
    async def _check_spread(self, symbol: str) -> Dict:
        """
        Vérifier spread en temps réel avec cache
        
        Returns:
            Dict avec valid, spread_pct, max_allowed, quality
        """
        # 🔥 PHASE 3: Utiliser cache (5 secondes)
        cache_key = symbol
        if cache_key in self._spread_cache:
            cached = self._spread_cache[cache_key]
            if time.time() - cached['timestamp'] < 5:  # Cache valide 5 secondes
                return cached['data']
        
        try:
            # Récupérer orderbook
            orderbook = await self.client.fetch_order_book(symbol, limit=5)
            
            best_bid = orderbook['bids'][0][0] if orderbook['bids'] else 0
            best_ask = orderbook['asks'][0][0] if orderbook['asks'] else 0
            
            if best_bid == 0 or best_ask == 0:
                return {'valid': False, 'spread_pct': 999, 'max_allowed': 0.03, 'quality': 'UNKNOWN'}
            
            mid_price = (best_bid + best_ask) / 2
            spread_pct = ((best_ask - best_bid) / mid_price) * 100
            
            # Seuil dynamique selon mode TP/SL
            tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
            
            if tp_sl_mode == 'FIXE':
                max_spread = 0.03  # 0.03% pour TP +0.25% (plus réaliste que 0.02%)
            else:
                max_spread = 0.06  # 0.06% pour TP ATR (plus large)
            
            valid = spread_pct <= max_spread
            
            # Quality scoring
            if spread_pct < 0.01:
                quality = 'EXCELLENT'
            elif spread_pct < 0.015:
                quality = 'GOOD'
            elif spread_pct < max_spread:
                quality = 'ACCEPTABLE'
            else:
                quality = 'POOR'
            
            result = {
                'valid': valid,
                'spread_pct': spread_pct,
                'max_allowed': max_spread,
                'quality': quality
            }
            
            # Mettre en cache
            self._spread_cache[cache_key] = {
                'timestamp': time.time(),
                'data': result
            }
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Erreur check spread {symbol}: {e}")
            return {'valid': False, 'spread_pct': 999, 'max_allowed': 0.03, 'quality': 'ERROR'}
    
    def _check_price_action_coherence(
        self,
        direction: str,
        current_candle: list,
        previous_candle: Optional[list],
        ema9: float,
        ema21: float
    ) -> Dict:
        """
        Vérifier cohérence price action avec direction
        
        Returns:
            Dict avec coherent, reason, quality
        """
        if not previous_candle:
            return {'coherent': True, 'reason': 'Pas de bougie précédente', 'quality': 'UNKNOWN'}
        
        open_price, high, low, close = current_candle[1:5]
        prev_open, prev_high, prev_low, prev_close = previous_candle[1:5]
        
        body = abs(close - open_price)
        candle_range = high - low
        
        if candle_range == 0:
            return {'coherent': False, 'reason': 'Range nul', 'quality': 'POOR'}
        
        body_ratio = body / candle_range if candle_range > 0 else 0
        
        if direction == 'LONG':
            # LONG : Vérifier que bougie actuelle est haussière
            is_bullish = close > open_price
            
            # Vérifier momentum
            momentum_ok = close > prev_close
            
            # Vérifier position vs EMAs
            above_ema9 = close > ema9
            
            # Vérifier wicks
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            wick_imbalance = upper_wick > lower_wick * 2 if lower_wick > 0 else False  # Upper wick trop grand
            
            # Plus tolérant pour doji/indécision
            if body_ratio < 0.2:  # Doji (très petit corps)
                # Ne pas rejeter automatiquement, mais qualité réduite
                quality = 'ACCEPTABLE'
                return {'coherent': True, 'reason': 'Doji/indécision', 'quality': quality}
            
            # Si bougie actuelle bearish MAIS précédente très bullish
            if not is_bullish and prev_close > prev_open and (prev_close - prev_open) > body * 2:
                # Momentum précédent fort → accepter
                quality = 'ACCEPTABLE'
                return {'coherent': True, 'reason': 'Momentum précédent fort', 'quality': quality}
            
            # Validation stricte seulement si contradiction majeure
            if not is_bullish and body_ratio > 0.5:  # Bearish avec corps significatif
                return {
                    'coherent': False,
                    'reason': 'Bougie baissière (close < open)',
                    'quality': 'POOR'
                }
            
            if wick_imbalance and body_ratio < 0.5:  # Upper wick suspect
                return {
                    'coherent': False,
                    'reason': 'Upper wick suspect (rejection)',
                    'quality': 'POOR'
                }
            
            # Quality scoring
            if is_bullish and momentum_ok and above_ema9 and body_ratio > 0.6:
                quality = 'EXCELLENT'
            elif is_bullish and momentum_ok:
                quality = 'GOOD'
            else:
                quality = 'ACCEPTABLE'
            
            return {'coherent': True, 'reason': 'Cohérente', 'quality': quality}
        
        else:  # SHORT
            is_bearish = close < open_price
            momentum_ok = close < prev_close
            below_ema9 = close < ema9
            
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            wick_imbalance = lower_wick > upper_wick * 2 if upper_wick > 0 else False
            
            # Plus tolérant pour doji/indécision
            if body_ratio < 0.2:
                quality = 'ACCEPTABLE'
                return {'coherent': True, 'reason': 'Doji/indécision', 'quality': quality}
            
            # Si bougie actuelle bullish MAIS précédente très bearish
            if not is_bearish and prev_close < prev_open and (prev_open - prev_close) > body * 2:
                quality = 'ACCEPTABLE'
                return {'coherent': True, 'reason': 'Momentum précédent fort', 'quality': quality}
            
            # Validation stricte seulement si contradiction majeure
            if not is_bearish and body_ratio > 0.5:
                return {
                    'coherent': False,
                    'reason': 'Bougie haussière (close > open)',
                    'quality': 'POOR'
                }
            
            if wick_imbalance and body_ratio < 0.5:
                return {
                    'coherent': False,
                    'reason': 'Lower wick suspect (rejection)',
                    'quality': 'POOR'
                }
            
            if is_bearish and momentum_ok and below_ema9 and body_ratio > 0.6:
                quality = 'EXCELLENT'
            elif is_bearish and momentum_ok:
                quality = 'GOOD'
            else:
                quality = 'ACCEPTABLE'
            
            return {'coherent': True, 'reason': 'Cohérente', 'quality': quality}
    
    async def _check_correlation(self, symbol: str, active_positions: Optional[List[str]]) -> Dict:
        """
        🔥 PHASE 6: Vérifier si le symbole est corrélé avec des positions actives
        
        Args:
            symbol: Symbole de la paire (ex: BTC/USDT:USDT)
            active_positions: Liste des symboles de positions actives
            
        Returns:
            Dict avec valid (bool), reason (str si rejeté), group (str si trouvé), penalty (float si SOFT)
        """
        from config import TRADING_CONFIG
        
        correlation_config = TRADING_CONFIG.get('correlation_filter', {})
        if not correlation_config.get('enabled', False):
            return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}
        
        if not active_positions:
            return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}
        
        # Extraire le symbole de base (ex: BTC/USDT:USDT → BTC)
        base_symbol = symbol.split('/')[0].split(':')[0].upper()
        
        # Identifier le groupe de corrélation
        groups = correlation_config.get('groups', {})
        symbol_group = None
        
        for group_name, group_symbols in groups.items():
            for group_symbol in group_symbols:
                if group_symbol.upper() in base_symbol or base_symbol in group_symbol.upper():
                    symbol_group = group_name
                    break
            if symbol_group:
                break
        
        if not symbol_group:
            # Pas de groupe = OK
            return {'valid': True, 'reason': None, 'group': None, 'penalty': 0.0}
        
        # Compter les positions actives dans le même groupe
        count_in_group = 0
        correlated_symbols = []
        
        for active_symbol in active_positions:
            active_base = active_symbol.split('/')[0].split(':')[0].upper()
            group_symbols = groups.get(symbol_group, [])
            
            for group_symbol in group_symbols:
                if group_symbol.upper() in active_base or active_base in group_symbol.upper():
                    count_in_group += 1
                    correlated_symbols.append(active_symbol)
                    break
        
        max_positions = correlation_config.get('max_positions_per_group', 1)
        mode = correlation_config.get('mode', 'HARD')
        
        if mode == 'SOFT':
            # SOFT mode: Appliquer pénalité au score
            if count_in_group >= max_positions:
                penalty = correlation_config.get('penalty_score', -1.5)
                reason = f"Corrélation avec {', '.join(correlated_symbols[:2])} (groupe: {symbol_group})"
                logger.warning(f"⚠️ {symbol} - Corrélation détectée (SOFT mode): {reason} - Pénalité: {penalty}")
                return {
                    'valid': True,  # Toujours valide en SOFT mode
                    'reason': reason,
                    'group': symbol_group,
                    'penalty': penalty,
                    'correlated_count': count_in_group
                }
            else:
                return {'valid': True, 'reason': None, 'group': symbol_group, 'penalty': 0.0}
        else:
            # HARD mode: Rejeter si max atteint
            if count_in_group >= max_positions:
                reason = f"Corrélation avec {', '.join(correlated_symbols[:2])} (groupe: {symbol_group}, max: {max_positions})"
                logger.warning(f"⚠️ {symbol} - Setup rejeté (HARD mode): {reason}")
                return {
                    'valid': False,
                    'reason': reason,
                    'group': symbol_group,
                    'penalty': 0.0,
                    'correlated_count': count_in_group
                }
            else:
                return {'valid': True, 'reason': None, 'group': symbol_group, 'penalty': 0.0}
    
    async def _check_orderbook_imbalance(self, symbol: str, direction: str) -> Dict:
        """
        Vérifier imbalance orderbook (bid/ask ratio)
        
        Returns:
            Dict avec valid, ratio, quality, bid_value, ask_value
        """
        # 🔥 PHASE 2: Utiliser cache (2 secondes)
        cache_key = f"{symbol}_{direction}"
        if cache_key in self._orderbook_cache:
            cached = self._orderbook_cache[cache_key]
            if time.time() - cached['timestamp'] < 2:  # Cache valide 2 secondes
                return cached['data']
        
        try:
            # Récupérer orderbook (top 10)
            orderbook = await self.client.fetch_order_book(symbol, limit=10)
            
            bids = orderbook.get('bids', [])[:10] if orderbook.get('bids') else []
            asks = orderbook.get('asks', [])[:10] if orderbook.get('asks') else []
            
            if not bids or not asks:
                return {'valid': True, 'ratio': 1.0, 'quality': 'UNKNOWN', 'bid_value': 0, 'ask_value': 0}
            
            # 🔥 FIX: ccxt retourne des listes [price, size] ou tuples (price, size)
            # Normaliser en listes pour garantir le format
            def normalize_order(order):
                """Normaliser un ordre en [price, size]"""
                if isinstance(order, (list, tuple)) and len(order) >= 2:
                    return [float(order[0]), float(order[1])]
                elif isinstance(order, dict):
                    return [float(order.get('price', 0)), float(order.get('size', 0))]
                else:
                    return [0.0, 0.0]
            
            bids_normalized = [normalize_order(bid) for bid in bids]
            asks_normalized = [normalize_order(ask) for ask in asks]
            
            # Calculer valeur totale (price × size)
            bid_value = sum([price * size for price, size in bids_normalized])
            ask_value = sum([price * size for price, size in asks_normalized])
            
            if bid_value == 0 or ask_value == 0:
                return {'valid': True, 'ratio': 1.0, 'quality': 'UNKNOWN', 'bid_value': bid_value, 'ask_value': ask_value}
            
            # Ratio bid/ask
            ratio = bid_value / ask_value
            
            # Validation selon direction (seuils plus permissifs)
            if direction == 'LONG':
                # LONG : besoin de pression acheteuse (ratio ≥ 1.1)
                required_ratio = 1.1  # Plus permissif que 1.2
                valid = ratio >= required_ratio
                
                # Quality scoring
                if ratio >= 1.5:
                    quality = 'EXCELLENT'
                elif ratio >= 1.3:
                    quality = 'GOOD'
                elif ratio >= required_ratio:
                    quality = 'ACCEPTABLE'
                else:
                    quality = 'POOR'
            
            else:  # SHORT
                # SHORT : besoin de pression vendeuse (ratio ≤ 0.95) - 🔥 Ajusté de 0.9 à 0.95
                required_ratio = 0.95  # Plus strict que 0.9 pour meilleure qualité
                valid = ratio <= required_ratio
                
                if ratio <= 0.6:
                    quality = 'EXCELLENT'
                elif ratio <= 0.7:
                    quality = 'GOOD'
                elif ratio <= required_ratio:
                    quality = 'ACCEPTABLE'
                else:
                    quality = 'POOR'
            
            logger.debug(
                f"📊 {symbol} Orderbook: Ratio={ratio:.2f} "
                f"({'✅' if valid else '❌'} for {direction}), Quality={quality}"
            )
            
            result = {
                'valid': valid,
                'ratio': ratio,
                'quality': quality,
                'bid_value': bid_value,
                'ask_value': ask_value
            }
            
            # Mettre en cache
            self._orderbook_cache[cache_key] = {
                'timestamp': time.time(),
                'data': result
            }
            
            return result
        
        except Exception as e:
            logger.error(f"❌ Erreur check orderbook {symbol}: {e}")
            # En cas d'erreur, accepter (éviter rejets systématiques)
            return {'valid': True, 'ratio': 1.0, 'quality': 'UNKNOWN', 'bid_value': 0, 'ask_value': 0}
    
    def _detect_manipulation(
        self,
        symbol: str,
        timeframe: str,
        ohlcv: Optional[List],
        volume: float,
        vol_spike: float
    ) -> Dict:
        """
        Détecter pump & dump / manipulation (version permissive)
        
        Returns:
            Dict avec suspicious, reason, severity
        """
        # Si pas de données OHLCV, on ne peut pas détecter
        if not ohlcv or len(ohlcv) < 3:
            return {'suspicious': False, 'reason': 'Pas de données OHLCV', 'severity': 'NONE'}
        
        suspicion_score = 0
        
        # 1. Volume spike extrême (>8x) sans news (plus permissif que 5x)
        if vol_spike > 8.0:
            suspicion_score += 2
        
        # 2. Wicks extrêmes (manipulation visible)
        current_candle = ohlcv[-1]
        if len(current_candle) >= 5:
            open_price, high, low, close = current_candle[1:5]
            
            body = abs(close - open_price)
            upper_wick = high - max(open_price, close)
            lower_wick = min(open_price, close) - low
            candle_range = high - low
            
            if candle_range > 0:
                wick_ratio = (upper_wick + lower_wick) / candle_range
                
                # Wicks > 90% du range = manipulation (plus permissif que 80%)
                if wick_ratio > 0.9:
                    suspicion_score += 1
        
        # 3. Prix en dehors de 4 écarts-types (plus permissif que 3)
        try:
            closes = [c[4] for c in ohlcv[-20:] if len(c) >= 5]
            if len(closes) >= 10:
                mean_price = sum(closes) / len(closes)
                variance = sum((c - mean_price) ** 2 for c in closes) / len(closes)
                std_price = variance ** 0.5 if variance > 0 else 0
                
                if std_price > 0 and len(current_candle) >= 5:
                    z_score = abs(current_candle[4] - mean_price) / std_price
                    
                    if z_score > 4:  # Plus permissif que 3
                        suspicion_score += 2
        except:
            pass
        
        # 4. Mouvement > 5% en 1 minute (trop rapide)
        if timeframe == '1m' and len(current_candle) >= 5:
            open_price = current_candle[1]
            close = current_candle[4]
            price_change = abs(close - open_price) / open_price * 100 if open_price > 0 else 0
            
            if price_change > 5:
                suspicion_score += 2
        
        # 5. Pattern pump & dump classique
        if len(ohlcv) >= 3:
            candle_1 = ohlcv[-3]
            candle_2 = ohlcv[-2]
            candle_3 = ohlcv[-1]
            
            if len(candle_1) >= 5 and len(candle_2) >= 5 and len(candle_3) >= 5:
                close_1 = candle_1[4]
                close_2 = candle_2[4]
                close_3 = candle_3[4]
                
                # Pump : +3% en 1 bougie
                pump = (close_2 - close_1) / close_1 * 100 if close_1 > 0 else 0
                # Dump : -2% en 1 bougie après pump
                dump = (close_3 - close_2) / close_2 * 100 if close_2 > 0 else 0
                
                if pump > 3 and dump < -2:
                    suspicion_score += 3
        
        # Rejeter seulement si score élevé (≥4)
        if suspicion_score >= 4:
            reasons = []
            if vol_spike > 8.0:
                reasons.append(f'Volume spike extrême ({vol_spike:.1f}x)')
            if suspicion_score >= 3:
                reasons.append('Pattern pump & dump')
            reason = ' | '.join(reasons) if reasons else 'Manipulation suspectée'
            
            return {
                'suspicious': True,
                'reason': reason,
                'severity': 'HIGH' if suspicion_score >= 5 else 'MEDIUM'
            }
        
        # Pas de manipulation détectée
        return {'suspicious': False, 'reason': 'Clean', 'severity': 'NONE'}
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()



