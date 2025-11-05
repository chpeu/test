"""
Analyseur technique pour détecter les setups de trading
Analyse multi-timeframe (1m, 5m) avec indicateurs avancés
"""
import asyncio
from typing import List, Dict, Optional
import math

from api.mexc import get_mexc_client
from api.price_provider import get_price_provider
from core.indicators import Indicators
from config import TRADING_CONFIG, DEBUG_ENABLED
from utils.logger import get_logger


logger = get_logger()


class TechnicalAnalyzer:
    """Analyseur technique pour détecter les setups LONG/SHORT"""
    
    def __init__(self):
        self.client = get_mexc_client()
        self.indicators = Indicators()
        self.price_provider = get_price_provider()  # 🔥 JOUR 2: Prix WebSocket
    
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
                # 🔥 FIX: Vérifier que trend_data est un dict
                if isinstance(trend_data, dict):
                    if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
                        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
                    elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
                        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
                else:
                    logger.warning(f"⚠️ trend_data invalide (attendu dict, reçu {type(trend_data).__name__}) pour {symbol}")
            
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
                reason = f"Conditions insuffisantes: Long={len(long_conditions)}+{trend_bonus} Short={len(short_conditions)} (min={min_conditions} requis)"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe, 'long_conditions': len(long_conditions), 'short_conditions': len(short_conditions), 'min_required': min_conditions}
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
            
            # 🔥 LOG DÉTAILLÉ: Setup trouvé avec tous les détails
            logger.info(
                f"✅ {symbol} {timeframe}: SETUP TROUVÉ - {direction} | "
                f"Conditions: {len(conditions)}/{min_conditions} | "
                f"RSI: {rsi:.1f} | Vol: {vol_spike:.2f}x | ATR: {atr_percent:.3f}% | "
                f"Entry: {entry:.6f} | SL: {sl:.6f} | TP: {tp:.6f} | "
                f"EMA9/21: {ema9:.6f}/{ema21:.6f} | MACD: {macd['histogram']:.6f} | "
                f"ADX: {adx['adx']:.1f} (DI+:{adx['diPlus']:.1f}/DI-:{adx['diMinus']:.1f}) | "
                f"Pattern: {pattern} | "
                f"Signals: {', '.join(conditions[:5])}" + (f" (+{len(conditions)-5} autres)" if len(conditions) > 5 else "")
            )
            
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
        return_reason: bool = False
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
            
            # Confluence ou mode permissif
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
    
    async def close(self):
        """Ferme les connexions"""
        await self.client.close()

