"""
Analyseur technique pour détecter les setups de trading
Analyse multi-timeframe (1m, 5m) avec indicateurs avancés
"""
import asyncio
from typing import List, Dict, Optional
import math

from api.mexc import get_mexc_client
from core.indicators import Indicators
from config import TRADING_CONFIG, DEBUG_ENABLED
from utils.logger import get_logger


logger = get_logger()


class TechnicalAnalyzer:
    """Analyseur technique pour détecter les setups LONG/SHORT"""
    
    def __init__(self):
        self.client = get_mexc_client()
        self.indicators = Indicators()
    
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
        volume_multiplier: float = 1.0
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
            # Récupérer OHLCV
            ohlcv = await self.client.fetch_ohlcv(symbol, timeframe, limit=100)
            
            if not ohlcv or len(ohlcv) < 20:
                return None
            
            # Extraire données
            closes = [k[4] for k in ohlcv]  # Close
            highs = [k[2] for k in ohlcv]  # High
            lows = [k[3] for k in ohlcv]  # Low
            volumes = [k[5] for k in ohlcv]  # Volume
            
            current_candle = ohlcv[-1]
            price = closes[-1]
            
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
            if atr_percent > 1.0:
                min_vol_ratio = 1.0
            elif atr_percent < 0.3:
                min_vol_ratio = 0.6
            else:
                min_vol_ratio = 0.8
            
            min_vol_ratio = min_vol_ratio * volume_multiplier
            min_vol_ratio = max(0.4, min(1.5, min_vol_ratio))
            
            # Filtrer volume
            if vol_spike < min_vol_ratio:
                if DEBUG_ENABLED:
                    logger.debug(f"Volume insuffisant {symbol} {timeframe}: {vol_spike:.2f}x < {min_vol_ratio:.2f}x")
                return None
            
            # Filtrer micro-range
            min_range = atr_percent * 0.2
            min_range = max(0.0003, min(0.003, min_range))
            candle_range = ((current_candle[2] - current_candle[3]) / price) * 100  # high - low
            
            if candle_range < min_range:
                if DEBUG_ENABLED:
                    logger.debug(f"Bougie plate {symbol} {timeframe}: range={candle_range:.4f}% < {min_range:.4f}%")
                return None
            
            # Filtre ATR optimal
            if timeframe == '1m':
                optimal_atr_min = TRADING_CONFIG['optimal_atr_min_1m']
                optimal_atr_max = TRADING_CONFIG['optimal_atr_max_1m']
            else:
                optimal_atr_min = TRADING_CONFIG['optimal_atr_min_5m']
                optimal_atr_max = TRADING_CONFIG['optimal_atr_max_5m']
            
            if atr_percent < optimal_atr_min or atr_percent > optimal_atr_max:
                if DEBUG_ENABLED:
                    atr_status = 'trop bas' if atr_percent < optimal_atr_min else 'trop élevé'
                    logger.debug(f"ATR sous-optimal {symbol} {timeframe}: {atr_percent:.3f}% ({atr_status})")
                return None
            
            # === PHASE 1 + 2: NOUVEAUX FILTRES ===
            
            # 1. SNR Filter (Signal-to-Noise Ratio)
            snr = abs(price - ema21) / atr if atr > 0 else 0
            snr_threshold = TRADING_CONFIG.get('snr_threshold', 0.3)
            if snr < snr_threshold:
                if DEBUG_ENABLED:
                    logger.debug(f"SNR trop faible {symbol} {timeframe}: {snr:.3f} < {snr_threshold} (signal plat)")
                return None
            
            # 2. Breakout Filter
            breakout_mult = TRADING_CONFIG.get('breakout_threshold', 0.3)
            breakout_threshold = atr * breakout_mult
            if price < ema21 + breakout_threshold and price > ema21 - breakout_threshold:
                if DEBUG_ENABLED:
                    logger.debug(f"Pas de breakout {symbol} {timeframe}: prix dans range ±ATR*{breakout_mult}")
                return None
            
            # 3. Wick Ratio Filter (manipulation)
            body = abs(current_candle[1] - current_candle[4])  # open - close
            if body == 0:
                body = 0.0001  # Éviter division par 0
            wick_ratio = (current_candle[2] - current_candle[3]) / body  # high - low
            wick_max = TRADING_CONFIG.get('wick_ratio_max', 2.5)
            if wick_ratio > wick_max:
                if DEBUG_ENABLED:
                    logger.debug(f"Wicks suspects {symbol} {timeframe}: ratio={wick_ratio:.2f} > {wick_max}")
                return None
            
            # Conditions LONG
            long_conditions = []
            
            # 1. EMAs
            ema_diff_percent = ((ema9 - ema21) / ema21) * 100
            if ema9 > ema21 and ema_diff_percent > 0.05:
                long_conditions.append(f"EMAs Up ({ema_diff_percent:.3f}%)")
            
            # 2. RSI
            rsi_rebound = rsi >= 30 and rsi <= 40 and adx['adx'] < 20 and rsi > rsi_prev
            rsi_pullback = rsi >= 45 and rsi <= 55 and macd['histogram'] > 0 and adx['adx'] > 25 and rsi > rsi_prev
            
            if rsi_rebound:
                long_conditions.append(f"RSI Rebound↑ (ADX<{adx['adx']:.1f})")
            elif rsi_pullback:
                long_conditions.append(f"RSI Pullback↑ (ADX>{adx['adx']:.1f})")
            
            # 3. Volume
            if vol_spike > 1.5:
                long_conditions.append(f"Vol >>{vol_spike:.1f}x")
            else:
                long_conditions.append(f"Vol >{min_vol_ratio:.1f}x")
            
            # 4. MACD
            macd_bullish = macd['macd'] > macd['signal'] or macd['histogram'] > 0
            macd_momentum = macd['histogram'] > macd_prev['histogram']
            
            if macd_bullish and macd_momentum:
                long_conditions.append("MACD+↑ (momentum)")
            elif macd_bullish:
                long_conditions.append("MACD+")
            
            # 5. Bollinger
            dist_to_lower = ((price - bb['lower']) / bb['lower']) * 100 if bb['upper'] > 0 else 999
            bb_threshold = max(0.3, atr_percent * 0.5)
            if dist_to_lower < bb_threshold:
                long_conditions.append("BB Lower")
            
            # 6. ADX + DI Gap (remplace ADX >30 seul)
            di_gap = adx['diPlus'] - adx['diMinus']
            di_gap_min = TRADING_CONFIG.get('di_gap_min', 5)
            di_gap_adx_threshold = TRADING_CONFIG.get('di_gap_adx_threshold', 25)
            if adx['adx'] > di_gap_adx_threshold and adx['diPlus'] > adx['diMinus'] and abs(di_gap) > di_gap_min:
                long_conditions.append("ADX+ + DI Gap>" + str(abs(di_gap)))
            elif adx['adx'] > 30 and adx['diPlus'] > adx['diMinus']:
                long_conditions.append("ADX+ (>30)")
            
            # 7. Pattern
            long_patterns = [
                'ENGULFING_BULLISH', 'HAMMER',
                'DOJI_DRAGONFLY', 'MARUBOZU_BULLISH',
                'MORNING_STAR', 'DOJI'
            ]
            if pattern in long_patterns:
                long_conditions.append(f"Pattern: {pattern}")
            
            # Conditions SHORT
            short_conditions = []
            
            # 1. EMAs
            ema_diff_percent_short = ((ema21 - ema9) / ema21) * 100
            if ema9 < ema21 and ema_diff_percent_short > 0.05:
                short_conditions.append(f"EMAs Down ({ema_diff_percent_short:.3f}%)")
            
            # 2. RSI
            rsi_overbought = rsi >= 60 and rsi <= 70 and adx['adx'] < 20 and rsi < rsi_prev
            rsi_rejection = rsi >= 45 and rsi <= 55 and macd['histogram'] < 0 and adx['adx'] > 25 and rsi < rsi_prev
            
            if rsi_overbought:
                short_conditions.append(f"RSI Overbought↓ (ADX<{adx['adx']:.1f})")
            elif rsi_rejection:
                short_conditions.append(f"RSI Rejection↓ (ADX>{adx['adx']:.1f})")
            
            # 3. Volume
            if vol_spike > 1.5:
                short_conditions.append(f"Vol >>{vol_spike:.1f}x")
            else:
                short_conditions.append(f"Vol >{min_vol_ratio:.1f}x")
            
            # 4. MACD
            macd_bearish = macd['macd'] < macd['signal'] or macd['histogram'] < 0
            macd_momentum_down = macd['histogram'] < macd_prev['histogram']
            
            if macd_bearish and macd_momentum_down:
                short_conditions.append("MACD-↓ (momentum)")
            elif macd_bearish:
                short_conditions.append("MACD-")
            
            # 5. Bollinger
            dist_to_upper = ((bb['upper'] - price) / price) * 100 if bb['upper'] > 0 else 999
            if dist_to_upper < bb_threshold:
                short_conditions.append("BB Upper")
            
            # 6. ADX + DI Gap (remplace ADX >30 seul)
            di_gap_short = adx['diMinus'] - adx['diPlus']
            if adx['adx'] > di_gap_adx_threshold and adx['diMinus'] > adx['diPlus'] and abs(di_gap_short) > di_gap_min:
                short_conditions.append("ADX- + DI Gap>" + str(abs(di_gap_short)))
            elif adx['adx'] > 30 and adx['diMinus'] > adx['diPlus']:
                short_conditions.append("ADX- (>30)")
            
            # 7. Pattern
            short_patterns = [
                'ENGULFING_BEARISH', 'SHOOTING_STAR',
                'DOJI_GRAVESTONE', 'MARUBOZU_BEARISH',
                'EVENING_STAR'
            ]
            if pattern in short_patterns:
                short_conditions.append(f"Pattern: {pattern}")
            
            # Tolérance dynamique ADX
            min_conditions = 6
            if adx['adx'] > 30:
                min_conditions = 5
            elif adx['adx'] >= 25:
                min_conditions = 5.5
            
            # Direction temporaire
            temp_direction = 'NEUTRAL'
            if len(long_conditions) >= min_conditions:
                temp_direction = 'LONG'
            elif len(short_conditions) >= min_conditions:
                temp_direction = 'SHORT'
            
            # Trend bonus
            trend_bonus = 0
            if trend_data and temp_direction != 'NEUTRAL':
                if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
                    trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
                elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
                    trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
            
            # PHASE 2: Divergence RSI/MACD (calcul avant direction)
            divergence_bonus = 0
            if temp_direction == 'LONG':
                if rsi < rsi_prev and macd['histogram'] > macd_prev['histogram']:
                    divergence_bonus = 1
                    long_conditions.append("Divergence+ ↑")
            elif temp_direction == 'SHORT':
                if rsi > rsi_prev and macd['histogram'] < macd_prev['histogram']:
                    divergence_bonus = 1
                    short_conditions.append("Divergence- ↓")
            
            # Vérifier avec bonus
            long_with_bonus = len(long_conditions) + (trend_bonus if temp_direction == 'LONG' else 0)
            short_with_bonus = len(short_conditions) + (trend_bonus if temp_direction == 'SHORT' else 0)
            
            direction = 'NEUTRAL'
            if long_with_bonus >= min_conditions:
                direction = 'LONG'
            elif short_with_bonus >= min_conditions:
                direction = 'SHORT'
            else:
                if DEBUG_ENABLED:
                    logger.debug(f"Conditions insuffisantes {symbol} {timeframe}: Long={len(long_conditions)}+{trend_bonus} Short={len(short_conditions)} (min={min_conditions})")
                return None
            
            # Cohérence EMA/MACD
            if direction == 'LONG' and ema9 > ema21 and macd['histogram'] <= -0.001:
                if DEBUG_ENABLED:
                    logger.debug(f"Incohérence EMA/MACD {symbol} {timeframe}: MACD très négatif")
                return None
            
            if direction == 'SHORT' and ema9 < ema21 and macd['histogram'] >= 0.001:
                if DEBUG_ENABLED:
                    logger.debug(f"Incohérence EMA/MACD {symbol} {timeframe}: MACD très positif")
                return None
            
            # Volume quality check BLOQUANT
            vol_quality = self.check_volume_quality(vol_spike, atr, price, 0)  # volume24h non utilisé pour l'instant
            if not vol_quality['shouldTrade'] or vol_quality['quality'] < 75:
                if DEBUG_ENABLED:
                    logger.debug(f"Volume quality rejeté {symbol} {timeframe}: {vol_quality['quality']}% < 75%")
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
                    if DEBUG_ENABLED:
                        logger.debug(f"Pas de structure swing {symbol} {timeframe}: {direction}")
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
            
            return {
                'symbol': symbol,
                'direction': direction,
                'entry': round(entry, 6),
                'sl': round(sl, 6),
                'tp': round(tp, 6),
                'rsi': round(rsi, 1),
                'volumeSpike': round(vol_spike, 1),
                'signals': conditions,
                'timeframe': timeframe,
                'volatility': atr / price if price > 0 else 0,
                'atr': atr,
                'price': price
            }
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur analyse {symbol} {timeframe}: {e}")
            return None
    
    async def analyze_pair(
        self,
        symbol: str,
        trend_data: Optional[Dict] = None,
        volume_multiplier: float = 1.0,
        use_confluence: bool = False
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
            # Analyser 1m
            analysis_1m = await self.analyze_timeframe(symbol, '1m', trend_data, volume_multiplier)
            analysis_5m = await self.analyze_timeframe(symbol, '5m', trend_data, volume_multiplier)
            
            if DEBUG_ENABLED:
                if analysis_1m:
                    logger.info(f"1m VALIDE: {analysis_1m['direction']} - {len(analysis_1m['signals'])} conditions")
                if analysis_5m:
                    logger.info(f"5m VALIDE: {analysis_5m['direction']} - {len(analysis_5m['signals'])} conditions")
            
            # Confluence ou mode permissif
            if use_confluence and analysis_1m and analysis_5m:
                # MODE CONFLUENCE STRICTE
                if analysis_1m['direction'] != analysis_5m['direction']:
                    if DEBUG_ENABLED:
                        logger.debug(f"Confluence: directions opposées")
                    return None
                
                strength_1m = len(analysis_1m['signals'])
                strength_5m = len(analysis_5m['signals'])
                
                if strength_5m < strength_1m * 0.8:
                    if DEBUG_ENABLED:
                        logger.debug(f"Confluence: 5m trop faible")
                    return None
                
                # Retourner le meilleur
                best = analysis_1m if strength_1m >= strength_5m else analysis_5m
                best['confirmedBy'] = '1m + 5m confluence'
                if analysis_1m and analysis_5m:
                    best['atr5m'] = analysis_5m['atr']
                return best
            else:
                # MODE PERMISSIF avec priorité par force
                strength_1m = len(analysis_1m['signals']) if analysis_1m else 0
                strength_5m = len(analysis_5m['signals']) if analysis_5m else 0
                
                if strength_1m > 0 or strength_5m > 0:
                    best = analysis_1m if strength_1m > strength_5m else analysis_5m
                    best['confirmedBy'] = f"{best['timeframe']} only ({len(best['signals'])} conds)"
                    if analysis_1m and analysis_5m:
                        best['atr5m'] = analysis_5m['atr']
                    return best
            
            return None
            
        except Exception as e:
            if DEBUG_ENABLED:
                logger.error(f"Erreur analyse pair {symbol}: {e}")
            return None
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()

