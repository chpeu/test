"""
Analyseur technique pour détecter les setups de trading
Analyse multi-timeframe (1m, 5m) avec indicateurs avancés
Version refactorisée - Délègue aux modules dans core/analyzer/
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

# Imports des modules refactorisés
from core.analyzer.filters import (
    check_volume_filter,
    check_snr_filter,
    check_breakout_filter,
    check_wick_filter,
    check_atr_filter
)
from core.analyzer.signal_generator import (
    generate_long_conditions,
    generate_short_conditions
)
from core.analyzer.scoring import (
    calculate_weighted_score,
    get_min_score_required,
    apply_trend_bonus,
    apply_divergence_bonus,
    evaluate_setup_score
)
from core.analyzer.market_data import (
    check_spread,
    check_orderbook_imbalance
)
from core.analyzer.risk_detector import (
    detect_manipulation,
    check_price_action_coherence
)
from core.analyzer.correlation import (
    check_static_correlation,
    check_dynamic_correlation
)
from core.analyzer.trend_calculator import calculate_trend_data


logger = get_logger()


class TechnicalAnalyzer:
    """Analyseur technique pour détecter les setups LONG/SHORT"""

    def __init__(self):
        self.client = get_mexc_client()
        self.indicators = Indicators()
        self.price_provider = get_price_provider()  # Prix WebSocket
        # Cache spread (5 secondes)
        self._spread_cache: Dict[str, Dict] = {}
        # Cache orderbook (2 secondes)
        self._orderbook_cache: Dict[str, Dict] = {}
        # Corrélation dynamique
        from core.correlation_dynamic import DynamicCorrelationFilter
        dynamic_corr_config = TRADING_CONFIG.get('dynamic_correlation', {})
        if dynamic_corr_config.get('enabled', False):
            self.correlation_filter = DynamicCorrelationFilter(
                period=dynamic_corr_config.get('period', 50),
                threshold=dynamic_corr_config.get('threshold', 0.7)
            )
        else:
            self.correlation_filter = None

    async def calculate_trend_data(self, symbol: str, timeframe: str = '15m') -> Optional[Dict]:
        """
        Calculer les données de tendance pour un timeframe donné

        Args:
            symbol: Symbole de la paire
            timeframe: Timeframe (5m, 15m, 30m, 1h)

        Returns:
            Dict avec trend (BULLISH/BEARISH/NEUTRAL), strength, bonus
        """
        return await calculate_trend_data(
            client=self.client,
            indicators=self.indicators,
            symbol=symbol,
            timeframe=timeframe
        )

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
            # Récupérer prix via WebSocket (prioritaire) ou REST
            ticker_data = await self.price_provider.get_price(symbol)
            if not ticker_data:
                reason = f"Prix non disponible (WebSocket ou REST) pour {symbol}"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None

            # Vérifier format données prix
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
            price = current_price  # Utiliser prix WebSocket (plus récent)

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
            if pattern == 'NONE':
                pattern = self.indicators.detect_pattern_multi(ohlcv[-3:])

            # Volume spike
            avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
            recent_vol = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else 1
            vol_spike = recent_vol / avg_vol if avg_vol > 0 else 1

            # ATR percent
            atr_percent = (atr / price) * 100 if price > 0 else 0

            # === FILTRES DE VALIDATION ===

            # Min volume ratio adaptatif
            base_min_vol = 1.0 if atr_percent > 1.0 else (0.6 if atr_percent < 0.3 else 0.8)
            min_vol_ratio = base_min_vol * volume_multiplier
            min_vol_ratio = max(0.4, min(1.5, min_vol_ratio))

            # 1. Filtre Volume
            volume_result = check_volume_filter(
                vol_spike=vol_spike,
                min_vol_ratio=min_vol_ratio,
                symbol=symbol,
                timeframe=timeframe,
                atr_percent=atr_percent,
                volume_multiplier=volume_multiplier,
                return_reason=return_reason
            )
            if volume_result:
                return volume_result if return_reason else None

            # 2. Filtrer micro-range
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

            # 3. Filtre ATR optimal
            atr_result = check_atr_filter(
                atr_percent=atr_percent,
                timeframe=timeframe,
                symbol=symbol,
                return_reason=return_reason
            )
            if atr_result:
                return atr_result if return_reason else None

            # 4. SNR Filter (Signal-to-Noise Ratio)
            snr_result = check_snr_filter(
                price=price,
                ema21=ema21,
                atr=atr,
                symbol=symbol,
                timeframe=timeframe,
                return_reason=return_reason
            )
            if snr_result:
                return snr_result if return_reason else None

            # 5. Breakout Filter
            breakout_result = check_breakout_filter(
                price=price,
                ema21=ema21,
                atr=atr,
                symbol=symbol,
                timeframe=timeframe,
                return_reason=return_reason
            )
            if breakout_result:
                return breakout_result if return_reason else None

            # 6. Wick Ratio Filter (manipulation)
            wick_result = check_wick_filter(
                current_candle=current_candle,
                symbol=symbol,
                timeframe=timeframe,
                return_reason=return_reason
            )
            if wick_result:
                return wick_result if return_reason else None

            # === GÉNÉRATION DES CONDITIONS LONG/SHORT ===

            long_conditions, long_condition_types = generate_long_conditions(
                ema9=ema9,
                ema21=ema21,
                rsi=rsi,
                rsi_prev=rsi_prev,
                vol_spike=vol_spike,
                min_vol_ratio=min_vol_ratio,
                macd=macd,
                macd_prev=macd_prev,
                price=price,
                bb=bb,
                atr_percent=atr_percent,
                adx=adx,
                pattern=pattern
            )

            short_conditions, short_condition_types = generate_short_conditions(
                ema9=ema9,
                ema21=ema21,
                rsi=rsi,
                rsi_prev=rsi_prev,
                vol_spike=vol_spike,
                min_vol_ratio=min_vol_ratio,
                macd=macd,
                macd_prev=macd_prev,
                price=price,
                bb=bb,
                atr_percent=atr_percent,
                adx=adx,
                pattern=pattern
            )

            # === ÉVALUATION DU SCORE ===

            evaluation = evaluate_setup_score(
                long_condition_types=long_condition_types,
                short_condition_types=short_condition_types,
                adx=adx,
                trend_data=trend_data
            )

            direction = evaluation['direction']
            temp_direction = evaluation['temp_direction']
            long_score = evaluation['long_score']
            short_score = evaluation['short_score']
            min_score_required = evaluation['min_required']
            trend_score_bonus = evaluation['trend_bonus']

            # Divergence RSI/MACD (calcul avant direction finale)
            divergence_bonus = apply_divergence_bonus(
                rsi=rsi,
                rsi_prev=rsi_prev,
                macd=macd,
                macd_prev=macd_prev,
                temp_direction=temp_direction,
                conditions=long_conditions if temp_direction == 'LONG' else short_conditions,
                condition_types=long_condition_types if temp_direction == 'LONG' else short_condition_types
            )

            # Recalculer score si divergence ajoutée
            use_weighted = TRADING_CONFIG.get('use_weighted_scoring', True)
            if divergence_bonus > 0 and use_weighted:
                if temp_direction == 'LONG':
                    long_score = calculate_weighted_score(long_condition_types) + trend_score_bonus
                else:
                    short_score = calculate_weighted_score(short_condition_types) + trend_score_bonus

            # Réévaluer direction après divergence
            direction = 'NEUTRAL'
            if long_score >= min_score_required:
                direction = 'LONG'
            elif short_score >= min_score_required:
                direction = 'SHORT'

            # Logs détaillés si score insuffisant
            if direction == 'NEUTRAL':
                if use_weighted:
                    reason = (
                        f"Score insuffisant: Long={len(long_conditions)}+{trend_score_bonus:.1f} "
                        f"[{', '.join(long_condition_types[:5])}] → Score: {long_score:.1f}/{min_score_required:.1f} ❌ | "
                        f"Short={len(short_conditions)} [{', '.join(short_condition_types[:5])}] → Score: {short_score:.1f}/{min_score_required:.1f} ❌"
                    )
                else:
                    reason = f"Conditions insuffisantes: Long={len(long_conditions)} Short={len(short_conditions)} (min={min_score_required} requis)"

                if return_reason:
                    return {
                        'reason': reason, 'symbol': symbol, 'timeframe': timeframe,
                        'long_conditions': len(long_conditions), 'short_conditions': len(short_conditions),
                        'min_required': min_score_required,
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
            vol_quality = self.check_volume_quality(vol_spike, atr, price, 0)
            if not vol_quality['shouldTrade'] or vol_quality['quality'] < 75:
                warnings_str = ", ".join(vol_quality.get('warnings', [])) if vol_quality.get('warnings') else "Aucun"
                reason = f"Volume quality rejeté: {vol_quality['quality']}% < 75% (warnings: {warnings_str})"
                if return_reason:
                    return {'reason': reason, 'symbol': symbol, 'timeframe': timeframe, 'quality': vol_quality['quality']}
                if DEBUG_ENABLED:
                    logger.debug(f"{symbol} {timeframe}: {reason}")
                return None

            # Structure swing HH/HL (blocking)
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

            # LOG DÉTAILLÉ avec score pondéré
            if use_weighted:
                condition_types = long_condition_types if direction == 'LONG' else short_condition_types
                final_score = long_score if direction == 'LONG' else short_score
                score_info = f"Score: {final_score:.1f}/{min_score_required:.1f} | Conditions: {len(conditions)}"
            else:
                score_info = f"Conditions: {len(conditions)}/{min_score_required}"

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

            # Ajouter condition_types pour métriques
            condition_types = long_condition_types if direction == 'LONG' else short_condition_types

            # Calculer score total pour position sizing
            if use_weighted:
                final_score = long_score if direction == 'LONG' else short_score
            else:
                final_score = len(conditions) + (trend_score_bonus if trend_score_bonus else 0)

            # 🔥 FIX: Ajouter tous les indicateurs au dictionnaire retourné pour qu'ils soient disponibles dans best_setup
            return {
                'symbol': symbol,
                'direction': direction,
                'entry': round(entry, 6),
                'sl': round(sl, 6),
                'tp': round(tp, 6),
                'rsi': round(rsi, 1),
                'rsi_prev': round(rsi_prev, 1) if rsi_prev is not None else None,
                'volumeSpike': round(vol_spike, 1),
                'signals': conditions,
                'condition_types': condition_types,
                'totalScore': final_score,
                'min_score_required': min_score_required,
                'timeframe': timeframe,
                'volatility': atr / price if price > 0 else 0,
                'atr': atr,
                'atr_pct': (atr / price * 100) if price > 0 else 0,
                'atr_percent': (atr / price * 100) if price > 0 else 0,  # Alias pour compatibilité
                'price': price,
                'ohlcv': ohlcv,
                # Indicateurs EMA
                'ema9': ema9 if ema9 is not None else None,
                'ema21': ema21 if ema21 is not None else None,
                # Indicateurs MACD
                'macd': macd.get('macd') if macd and isinstance(macd, dict) else None,
                'macd_signal': macd.get('signal') if macd and isinstance(macd, dict) else None,
                'macd_hist': macd.get('histogram') if macd and isinstance(macd, dict) else None,
                'macd_hist_prev': macd_prev.get('histogram') if macd_prev and isinstance(macd_prev, dict) else None,
                # Indicateurs ADX
                'adx': adx.get('adx') if adx and isinstance(adx, dict) else None,
                'di_plus': adx.get('diPlus') if adx and isinstance(adx, dict) else None,
                'di_minus': adx.get('diMinus') if adx and isinstance(adx, dict) else None,
                # Indicateurs Bollinger Bands
                'bb_upper': bb.get('upper') if bb and isinstance(bb, dict) else None,
                'bb_middle': bb.get('middle') if bb and isinstance(bb, dict) else None,
                'bb_lower': bb.get('lower') if bb and isinstance(bb, dict) else None,
                'bb_width': bb.get('width') if bb and isinstance(bb, dict) else None,
                'bb_distance_to_lower': ((price - bb.get('lower')) / bb.get('lower') * 100) if bb and isinstance(bb, dict) and bb.get('lower') and price else None,
                'bb_distance_to_upper': ((bb.get('upper') - price) / price * 100) if bb and isinstance(bb, dict) and bb.get('upper') and price else None,
                # Indicateurs Volume
                'volume': volumes[-1] if volumes else None,
                'volume_avg': avg_vol if avg_vol else None,
                'volume_ratio': vol_spike if vol_spike else None,
                'volume_spike': vol_spike if vol_spike else None,
                # Pattern
                'pattern': pattern if pattern else None
            }

        except Exception as e:
            import traceback
            error_msg = f"Exception lors de l'analyse {timeframe}: {str(e)}"
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
            start_time = time.time()  # Pour calculer scan_duration_ms
            
            # Toujours calculer trend_data (au lieu d'optionnel)
            if trend_data is None:
                trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
                trend_data = await self.calculate_trend_data(symbol, trend_timeframe)
                if trend_data:
                    logger.debug(f"📊 {symbol}: Trend {trend_data.get('trend', 'NEUTRAL')} ({trend_timeframe}) - Bonus: {trend_data.get('bonus', 0)}")

            # Analyser 1m et 5m
            analysis_1m = await self.analyze_timeframe(symbol, '1m', trend_data, volume_multiplier, return_reason=return_reason)
            analysis_5m = await self.analyze_timeframe(symbol, '5m', trend_data, volume_multiplier, return_reason=return_reason)

            # ========================================
            # ✅ POINT A : LOG SCAN (NON-BLOCKING)
            # ========================================
            scan_duration_ms = (time.time() - start_time) * 1000
            scan_uuid = None
            
            try:
                from backend.ml.data_logger import DataLogger
                data_logger = DataLogger()
                
                if data_logger and data_logger.is_running:
                    # Récupérer prix actuel
                    ticker_data = await self.price_provider.get_price(symbol)
                    current_price = float(ticker_data.get('lastPrice', 0)) if ticker_data else 0
                    
                    # Préparer indicateurs 1m
                    indicators_1m = {}
                    if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                        indicators_1m = {
                            'ema9': analysis_1m.get('ema9'),
                            'ema21': analysis_1m.get('ema21'),
                            'ema_diff_pct': (
                                ((analysis_1m.get('ema9', 0) - analysis_1m.get('ema21', 0)) 
                                 / analysis_1m.get('ema21', 1)) * 100
                                if analysis_1m.get('ema21') else None
                            ),
                            'rsi': analysis_1m.get('rsi'),
                            'rsi_prev': analysis_1m.get('rsi_prev'),
                            'macd': analysis_1m.get('macd'),
                            'macd_signal': analysis_1m.get('macd_signal'),
                            'macd_hist': analysis_1m.get('macd_hist'),
                            'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                            'adx': analysis_1m.get('adx'),
                            'di_plus': analysis_1m.get('di_plus'),
                            'di_minus': analysis_1m.get('di_minus'),
                            'di_gap': (
                                analysis_1m.get('di_plus', 0) - analysis_1m.get('di_minus', 0)
                                if analysis_1m.get('di_plus') and analysis_1m.get('di_minus') else None
                            ),
                            'atr': analysis_1m.get('atr'),
                            'atr_pct': analysis_1m.get('atr_pct'),
                            'bb_upper': analysis_1m.get('bb_upper'),
                            'bb_middle': analysis_1m.get('bb_middle'),
                            'bb_lower': analysis_1m.get('bb_lower'),
                            'bb_width': analysis_1m.get('bb_width'),
                            'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'),
                            'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                            'volume': analysis_1m.get('volume'),
                            'volume_avg': analysis_1m.get('volume_avg'),
                            'volume_ratio': analysis_1m.get('volumeSpike'),
                            'volume_spike': analysis_1m.get('volumeSpike'),
                            'pattern': analysis_1m.get('pattern'),
                            'pattern_multi': analysis_1m.get('pattern_multi')
                        }
                    
                    # Préparer indicateurs 5m
                    indicators_5m = {}
                    if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                        indicators_5m = {
                            'ema9': analysis_5m.get('ema9'),
                            'ema21': analysis_5m.get('ema21'),
                            'ema_diff_pct': (
                                ((analysis_5m.get('ema9', 0) - analysis_5m.get('ema21', 0)) 
                                 / analysis_5m.get('ema21', 1)) * 100
                                if analysis_5m.get('ema21') else None
                            ),
                            'rsi': analysis_5m.get('rsi'),
                            'rsi_prev': analysis_5m.get('rsi_prev'),
                            'macd': analysis_5m.get('macd'),
                            'macd_signal': analysis_5m.get('macd_signal'),
                            'macd_hist': analysis_5m.get('macd_hist'),
                            'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                            'adx': analysis_5m.get('adx'),
                            'di_plus': analysis_5m.get('di_plus'),
                            'di_minus': analysis_5m.get('di_minus'),
                            'di_gap': (
                                analysis_5m.get('di_plus', 0) - analysis_5m.get('di_minus', 0)
                                if analysis_5m.get('di_plus') and analysis_5m.get('di_minus') else None
                            ),
                            'atr': analysis_5m.get('atr'),
                            'atr_pct': analysis_5m.get('atr_pct'),
                            'bb_upper': analysis_5m.get('bb_upper'),
                            'bb_middle': analysis_5m.get('bb_middle'),
                            'bb_lower': analysis_5m.get('bb_lower'),
                            'bb_width': analysis_5m.get('bb_width'),
                            'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'),
                            'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                            'volume': analysis_5m.get('volume'),
                            'volume_avg': analysis_5m.get('volume_avg'),
                            'volume_ratio': analysis_5m.get('volumeSpike'),
                            'volume_spike': analysis_5m.get('volumeSpike'),
                            'pattern': analysis_5m.get('pattern'),
                            'pattern_multi': analysis_5m.get('pattern_multi')
                        }
                    
                    # Récupérer scalability data (sera mis à jour après spread_check)
                    scalability_data = {
                        'spread': None,
                        'bookDepth': None,
                        'balanceScore': None,
                        'bidVol': None,
                        'askVol': None
                    }
                    
                    # Préparer confluence
                    confluence = {
                        'use_confluence': use_confluence,
                        'confluence_met': False,
                        'score_1m': analysis_1m.get('totalScore') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'score_5m': analysis_5m.get('totalScore') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'score_total': None,
                        'score_long_1m': None,
                        'score_short_1m': None,
                        'score_long_5m': None,
                        'score_short_5m': None,
                        'timeframes_aligned': False,
                        'divergence_detected': False,
                        'divergence_type': None,
                        'divergence_bonus': 0
                    }
                    
                    # Préparer filters
                    filters = {
                        'snr_1m': analysis_1m.get('snr') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'snr_5m': analysis_5m.get('snr') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'snr_passed_1m': analysis_1m.get('snr_passed') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'snr_passed_5m': analysis_5m.get('snr_passed') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'breakout_distance_1m': analysis_1m.get('breakout_distance') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'breakout_distance_5m': analysis_5m.get('breakout_distance') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'breakout_passed_1m': analysis_1m.get('breakout_passed') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'breakout_passed_5m': analysis_5m.get('breakout_passed') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'wick_ratio_1m': analysis_1m.get('wick_ratio') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'wick_ratio_5m': analysis_5m.get('wick_ratio') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'wick_passed_1m': analysis_1m.get('wick_passed') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'wick_passed_5m': analysis_5m.get('wick_passed') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'atr_optimal_passed_1m': analysis_1m.get('atr_optimal_passed') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'atr_optimal_passed_5m': analysis_5m.get('atr_optimal_passed') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None,
                        'volume_filter_passed_1m': analysis_1m.get('volume_filter_passed') if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) else None,
                        'volume_filter_passed_5m': analysis_5m.get('volume_filter_passed') if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m) else None
                    }
                    
                    # Logger le scan
                    scan_uuid = await data_logger.log_scan(
                        symbol=symbol,
                        price=current_price,
                        indicators_1m=indicators_1m,
                        indicators_5m=indicators_5m,
                        confluence=confluence,
                        scalability_data=scalability_data,
                        trend_data={
                            'timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
                            'direction': trend_data.get('trend') if trend_data else None,
                            'strength': trend_data.get('strength') if trend_data else None,
                            'bonus': trend_data.get('bonus', 0) if trend_data else 0
                        },
                        filters=filters,
                        params_snapshot=TRADING_CONFIG.copy(),
                        is_opportunity=False,  # Pas encore décidé
                        opportunity_direction=None,
                        reject_reason=None,
                        reject_reason_category=None,
                        scan_duration_ms=scan_duration_ms
                    )
            except Exception as e:
                logger.debug(f"Erreur log_scan (non-bloquant): {e}")
                scan_uuid = None
            # ========================================
            # FIN POINT A
            # ========================================

            # LOG DÉTAILLÉ: Résumé des analyses 1m et 5m
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

            # Déterminer le meilleur setup
            best_setup = None
            if use_confluence and analysis_1m and analysis_5m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                # Confluence: 1m ET 5m valides
                best_setup = analysis_1m if len(analysis_1m.get('signals', [])) >= len(analysis_5m.get('signals', [])) else analysis_5m
            elif not use_confluence:
                # Mode permissif: 1m OU 5m
                if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                    best_setup = analysis_1m
                elif analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                    best_setup = analysis_5m

            if best_setup:
                # === VÉRIFICATIONS DE MARCHÉ ===

                # 1. Vérifier spread
                spread_check = await check_spread(
                    client=self.client,
                    symbol=symbol,
                    spread_cache=self._spread_cache
                )

                if not spread_check['valid']:
                    logger.warning(
                        f"⚠️ {symbol} - Setup rejeté : Spread trop élevé "
                        f"({spread_check['spread_pct']:.3f}% > {spread_check['max_allowed']:.3f}%)"
                    )
                    return None

                best_setup['spread_pct'] = spread_check['spread_pct']
                best_setup['spread_quality'] = spread_check['quality']
                
                # ✅ Mettre à jour scalability_data pour le scan logué
                if 'scalability_data' in locals():
                    scalability_data['spread'] = spread_check['spread_pct']

                # 2. Vérifier orderbook imbalance
                orderbook_check = await check_orderbook_imbalance(
                    client=self.client,
                    symbol=symbol,
                    direction=best_setup['direction'],
                    orderbook_cache=self._orderbook_cache
                )

                if not orderbook_check['valid']:
                    required_str = '≥1.1' if best_setup['direction'] == 'LONG' else '≤0.95'
                    info_msg = (
                        f"ℹ️ {symbol} - Setup {best_setup['direction']} rejeté : "
                        f"Orderbook défavorable (ratio={orderbook_check['ratio']:.2f}, required={required_str})"
                    )
                    logger.info(info_msg)
                    # 🔥 FIX: Envoyer le log au frontend via websocket_manager (INFO au lieu de WARNING)
                    try:
                        from core.websocket_manager import get_websocket_manager
                        from datetime import datetime
                        import asyncio
                        ws_mgr = get_websocket_manager()
                        if ws_mgr:
                            try:
                                loop = asyncio.get_running_loop()
                                async def send_log():
                                    # Format identique à add_log dans main.py
                                    entry = {
                                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                                        'level': 'INFO',  # 🔥 FIX: INFO au lieu de WARNING
                                        'message': f"ℹ️ Setup {best_setup['direction']} rejeté",
                                        'detail': f"{symbol}: Orderbook défavorable (ratio={orderbook_check['ratio']:.2f}, required={required_str})",
                                        'raw_message': f"Setup {best_setup['direction']} rejeté"
                                    }
                                    await ws_mgr.emit('log', entry)
                                loop.create_task(send_log())
                            except RuntimeError:
                                # Pas de loop en cours, ignorer (le log est déjà dans logger.info)
                                pass
                    except Exception as log_err:
                        logger.debug(f"Impossible d'envoyer log au frontend: {log_err}")
                    return None

                # Bonus si orderbook très favorable
                if orderbook_check['quality'] == 'EXCELLENT':
                    if 'totalScore' in best_setup:
                        best_setup['totalScore'] += 1.0

                best_setup['orderbook_ratio'] = orderbook_check['ratio']
                best_setup['orderbook_quality'] = orderbook_check['quality']
                # 🔥 FIX: Stocker aussi bid_value et ask_value pour calculer depth
                best_setup['orderbook_bid_value'] = orderbook_check.get('bid_value', 0)
                best_setup['orderbook_ask_value'] = orderbook_check.get('ask_value', 0)
                best_setup['orderbook_check'] = orderbook_check  # Stocker l'objet complet pour fallback
                
                # ✅ Mettre à jour scalability_data pour le scan logué
                if 'scalability_data' in locals():
                    scalability_data['bookDepth'] = orderbook_check.get('bid_value', 0) + orderbook_check.get('ask_value', 0)
                    scalability_data['bidVol'] = orderbook_check.get('bid_value', 0)
                    scalability_data['askVol'] = orderbook_check.get('ask_value', 0)
                    # Calculer balanceScore depuis ratio
                    ratio = orderbook_check.get('ratio', 1.0)
                    if ratio > 0:
                        bid_ask_ratio = ratio / (1 + ratio)  # Convertir ratio en pourcentage bid
                        scalability_data['balanceScore'] = 1 - (abs(bid_ask_ratio - 0.5) * 2)

                # 3. Vérifier manipulation pump & dump
                ohlcv_data = None
                if best_setup.get('timeframe') == '1m' and analysis_1m:
                    ohlcv_data = analysis_1m.get('ohlcv')
                elif best_setup.get('timeframe') == '5m' and analysis_5m:
                    ohlcv_data = analysis_5m.get('ohlcv')
                if not ohlcv_data and analysis_1m:
                    ohlcv_data = analysis_1m.get('ohlcv')
                elif not ohlcv_data and analysis_5m:
                    ohlcv_data = analysis_5m.get('ohlcv')

                manipulation_check = detect_manipulation(
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

                # === VÉRIFICATIONS DE CORRÉLATION ===

                # 4. Vérifier corrélation avec positions actives (filtre statique)
                if active_positions:
                    correlation_check = await check_static_correlation(symbol, active_positions)

                    if not correlation_check['valid']:
                        logger.warning(f"⚠️ {symbol} - Setup rejeté: {correlation_check['reason']}")
                        if return_reason:
                            return {'reason': correlation_check['reason'], 'symbol': symbol}
                        return None
                    elif correlation_check.get('penalty', 0) != 0:
                        penalty = correlation_check['penalty']
                        if 'totalScore' in best_setup:
                            best_setup['totalScore'] += penalty
                            logger.info(f"⚠️ {symbol} - Corrélation (SOFT): Score {best_setup['totalScore']:.1f} après pénalité {penalty}")

                # 5. Vérifier corrélation dynamique (basée sur prix réels)
                dynamic_corr_config = TRADING_CONFIG.get('dynamic_correlation', {})
                if dynamic_corr_config.get('enabled', False) and self.correlation_filter and active_positions:
                    current_price = best_setup.get('price', 0)

                    dynamic_corr_result = check_dynamic_correlation(
                        correlation_filter=self.correlation_filter,
                        symbol=symbol,
                        current_price=current_price,
                        active_positions=active_positions,
                        setup_score=best_setup.get('totalScore', 0)
                    )

                    if dynamic_corr_result['penalty'] < 0:
                        if 'totalScore' in best_setup:
                            best_setup['totalScore'] = dynamic_corr_result['adjusted_score']

                # === RECOVERY MODE PROGRESSIF ===

                recovery_config = TRADING_CONFIG.get('recovery_mode', {})
                min_score_required = best_setup.get('min_score_required', TRADING_CONFIG.get('min_score_required', 7.5))

                if recovery_config.get('enabled', False) and position_manager:
                    recovery_mode_active = position_manager.config.recovery_mode_active if hasattr(position_manager, 'config') else False

                    if recovery_mode_active:
                        loss_streak = position_manager.config.loss_streak if hasattr(position_manager, 'config') else 0
                        recovery_level = position_manager.get_recovery_level(loss_streak) if hasattr(position_manager, 'get_recovery_level') else None

                        if recovery_level:
                            recovery_boost = recovery_level.get('min_score_boost', recovery_config.get('min_score_boost', 1.5))
                            level_num = recovery_level.get('level', 1)
                        else:
                            recovery_boost = recovery_config.get('min_score_boost', 1.5)
                            level_num = 1

                        adjusted_min_score = min_score_required + recovery_boost

                        # Forcer confluence si configuré
                        confluence_forced = recovery_level.get('confluence_forced', False) if recovery_level else recovery_config.get('confluence_forced', False)

                        if confluence_forced:
                            use_confluence = True
                            if not (analysis_1m and analysis_5m and
                                    not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m) and
                                    not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m)):
                                logger.warning(f"⚠️ {symbol} - Setup rejeté (Recovery Mode Niveau {level_num}): Confluence requise")
                                if return_reason:
                                    return {'reason': f'Recovery Mode Niveau {level_num}: Confluence requise', 'symbol': symbol}
                                return None

                        # Vérifier score avec boost
                        setup_score = best_setup.get('totalScore', 0)
                        if setup_score < adjusted_min_score:
                            logger.warning(
                                f"⚠️ {symbol} - Setup rejeté (Recovery Mode Niveau {level_num}): "
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

                best_setup['min_score_required'] = min_score_required
                
                # 🔥 FIX: Ajouter indicators_1m et indicators_5m à best_setup pour qu'ils soient disponibles dans _last_setup
                # Construire indicators_1m depuis analysis_1m
                indicators_1m = {}
                if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                    indicators_1m = {
                        'rsi': analysis_1m.get('rsi'),
                        'rsi_prev': analysis_1m.get('rsi_prev'),
                        'macd': analysis_1m.get('macd'),
                        'macd_signal': analysis_1m.get('macd_signal'),
                        'macd_hist': analysis_1m.get('macd_hist'),
                        'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                        'adx': analysis_1m.get('adx'),
                        'di_plus': analysis_1m.get('di_plus'),
                        'di_minus': analysis_1m.get('di_minus'),
                        'di_gap': (
                            analysis_1m.get('di_plus', 0) - analysis_1m.get('di_minus', 0)
                            if analysis_1m.get('di_plus') and analysis_1m.get('di_minus') else None
                        ),
                        'ema9': analysis_1m.get('ema9'),
                        'ema21': analysis_1m.get('ema21'),
                        'ema_diff_pct': (
                            ((analysis_1m.get('ema9', 0) - analysis_1m.get('ema21', 0)) 
                             / analysis_1m.get('ema21', 1)) * 100
                            if analysis_1m.get('ema21') else None
                        ),
                        'atr': analysis_1m.get('atr'),
                        'atr_pct': analysis_1m.get('atr_pct'),
                        'bb_upper': analysis_1m.get('bb_upper'),
                        'bb_middle': analysis_1m.get('bb_middle'),
                        'bb_lower': analysis_1m.get('bb_lower'),
                        'bb_width': analysis_1m.get('bb_width'),
                        'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                        'volume': analysis_1m.get('volume'),
                        'volume_avg': analysis_1m.get('volume_avg'),
                        'volume_ratio': analysis_1m.get('volumeSpike'),
                        'volume_spike': analysis_1m.get('volumeSpike'),
                    }
                
                # Construire indicators_5m depuis analysis_5m
                indicators_5m = {}
                if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                    indicators_5m = {
                        'rsi': analysis_5m.get('rsi'),
                        'rsi_prev': analysis_5m.get('rsi_prev'),
                        'macd': analysis_5m.get('macd'),
                        'macd_signal': analysis_5m.get('macd_signal'),
                        'macd_hist': analysis_5m.get('macd_hist'),
                        'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                        'adx': analysis_5m.get('adx'),
                        'di_plus': analysis_5m.get('di_plus'),
                        'di_minus': analysis_5m.get('di_minus'),
                        'di_gap': (
                            analysis_5m.get('di_plus', 0) - analysis_5m.get('di_minus', 0)
                            if analysis_5m.get('di_plus') and analysis_5m.get('di_minus') else None
                        ),
                        'ema9': analysis_5m.get('ema9'),
                        'ema21': analysis_5m.get('ema21'),
                        'ema_diff_pct': (
                            ((analysis_5m.get('ema9', 0) - analysis_5m.get('ema21', 0)) 
                             / analysis_5m.get('ema21', 1)) * 100
                            if analysis_5m.get('ema21') else None
                        ),
                        'atr': analysis_5m.get('atr'),
                        'atr_pct': analysis_5m.get('atr_pct'),
                        'bb_upper': analysis_5m.get('bb_upper'),
                        'bb_middle': analysis_5m.get('bb_middle'),
                        'bb_lower': analysis_5m.get('bb_lower'),
                        'bb_width': analysis_5m.get('bb_width'),
                        'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'),
                        'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                        'volume': analysis_5m.get('volume'),
                        'volume_avg': analysis_5m.get('volume_avg'),
                        'volume_ratio': analysis_5m.get('volumeSpike'),
                        'volume_spike': analysis_5m.get('volumeSpike'),
                    }
                
                # Ajouter les indicateurs à best_setup
                best_setup['indicators_1m'] = indicators_1m
                best_setup['indicators_5m'] = indicators_5m
                
                # Stocker scan_uuid pour Point B et C
                if scan_uuid:
                    best_setup['_scan_uuid'] = scan_uuid

                # ========================================
                # ✅ POINT B : LOG OPPORTUNITY
                # ========================================
                try:
                    from backend.ml.data_logger import DataLogger
                    data_logger = DataLogger()
                    
                    if data_logger and data_logger.is_running and best_setup.get('_scan_uuid'):
                        # Récupérer scan_uuid
                        scan_uuid_opp = best_setup.get('_scan_uuid')
                        
                        # Préparer conditions matched
                        conditions_matched = []
                        if best_setup.get('signals'):
                            conditions_matched = [s.get('name', str(s)) if isinstance(s, dict) else str(s) for s in best_setup['signals']]
                        
                        # Calculer scores
                        score_long = None
                        score_short = None
                        if best_setup.get('direction') == 'LONG':
                            score_long = best_setup.get('totalScore')
                        elif best_setup.get('direction') == 'SHORT':
                            score_short = best_setup.get('totalScore')
                        
                        # Logger l'opportunité
                        opp_id = await data_logger.log_opportunity(
                            scan_log_id=scan_uuid_opp,
                            symbol=symbol,
                            direction=best_setup.get('direction'),
                            entry_suggested=best_setup.get('entry', best_setup.get('price', 0)),
                            tp_suggested=best_setup.get('tp', 0),
                            sl_suggested=best_setup.get('sl', 0),
                            tp_sl_mode=TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
                            setup_score=best_setup.get('totalScore', 0),
                            setup_reason=best_setup.get('confirmedBy', 'Setup détecté'),
                            conditions_matched=conditions_matched,
                            score_long=score_long,
                            score_short=score_short,
                            score_min_required=best_setup.get('min_score_required'),
                            trend_bonus=trend_data.get('bonus', 0) if trend_data else 0,
                            divergence_bonus=0  # À adapter si vous avez divergence
                        )
                        
                        # Stocker opp_id pour Point C
                        best_setup['_opportunity_id'] = opp_id
                except Exception as e:
                    logger.debug(f"Erreur log_opportunity (non-bloquant): {e}")
                # ========================================
                # FIN POINT B
                # ========================================

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
                best['symbol'] = symbol
                if analysis_1m and analysis_5m:
                    best['atr5m'] = analysis_5m['atr']
                
                # 🔥 FIX: Ajouter indicators_1m et indicators_5m à best pour qu'ils soient disponibles dans _last_setup
                indicators_1m = {}
                if analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m):
                    indicators_1m = {
                        'rsi': analysis_1m.get('rsi'), 'rsi_prev': analysis_1m.get('rsi_prev'),
                        'macd': analysis_1m.get('macd'), 'macd_signal': analysis_1m.get('macd_signal'),
                        'macd_hist': analysis_1m.get('macd_hist'), 'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                        'adx': analysis_1m.get('adx'), 'di_plus': analysis_1m.get('di_plus'),
                        'di_minus': analysis_1m.get('di_minus'),
                        'di_gap': (analysis_1m.get('di_plus', 0) - analysis_1m.get('di_minus', 0) if analysis_1m.get('di_plus') and analysis_1m.get('di_minus') else None),
                        'ema9': analysis_1m.get('ema9'), 'ema21': analysis_1m.get('ema21'),
                        'ema_diff_pct': (((analysis_1m.get('ema9', 0) - analysis_1m.get('ema21', 0)) / analysis_1m.get('ema21', 1)) * 100 if analysis_1m.get('ema21') else None),
                        'atr': analysis_1m.get('atr'), 'atr_pct': analysis_1m.get('atr_pct'),
                        'bb_upper': analysis_1m.get('bb_upper'), 'bb_middle': analysis_1m.get('bb_middle'), 'bb_lower': analysis_1m.get('bb_lower'),
                        'bb_width': analysis_1m.get('bb_width'), 'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'), 'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                        'volume': analysis_1m.get('volume'), 'volume_avg': analysis_1m.get('volume_avg'),
                        'volume_ratio': analysis_1m.get('volumeSpike'), 'volume_spike': analysis_1m.get('volumeSpike'),
                    }
                indicators_5m = {}
                if analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m):
                    indicators_5m = {
                        'rsi': analysis_5m.get('rsi'), 'rsi_prev': analysis_5m.get('rsi_prev'),
                        'macd': analysis_5m.get('macd'), 'macd_signal': analysis_5m.get('macd_signal'),
                        'macd_hist': analysis_5m.get('macd_hist'), 'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                        'adx': analysis_5m.get('adx'), 'di_plus': analysis_5m.get('di_plus'),
                        'di_minus': analysis_5m.get('di_minus'),
                        'di_gap': (analysis_5m.get('di_plus', 0) - analysis_5m.get('di_minus', 0) if analysis_5m.get('di_plus') and analysis_5m.get('di_minus') else None),
                        'ema9': analysis_5m.get('ema9'), 'ema21': analysis_5m.get('ema21'),
                        'ema_diff_pct': (((analysis_5m.get('ema9', 0) - analysis_5m.get('ema21', 0)) / analysis_5m.get('ema21', 1)) * 100 if analysis_5m.get('ema21') else None),
                        'atr': analysis_5m.get('atr'), 'atr_pct': analysis_5m.get('atr_pct'),
                        'bb_upper': analysis_5m.get('bb_upper'), 'bb_middle': analysis_5m.get('bb_middle'), 'bb_lower': analysis_5m.get('bb_lower'),
                        'bb_width': analysis_5m.get('bb_width'), 'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'), 'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                        'volume': analysis_5m.get('volume'), 'volume_avg': analysis_5m.get('volume_avg'),
                        'volume_ratio': analysis_5m.get('volumeSpike'), 'volume_spike': analysis_5m.get('volumeSpike'),
                    }
                best['indicators_1m'] = indicators_1m
                best['indicators_5m'] = indicators_5m

                logger.info(
                    f"✅ {symbol}: CONFLUENCE RÉUSSIE - {best['direction']} | "
                    f"1m: {strength_1m} conditions | 5m: {strength_5m} conditions | "
                    f"Meilleur: {best['timeframe']} | "
                    f"Entry: {best['entry']:.6f} | SL: {best['sl']:.6f} | TP: {best['tp']:.6f}"
                )

                return best
            else:
                # MODE PERMISSIF avec priorité par force
                valid_1m = analysis_1m and not (isinstance(analysis_1m, dict) and 'reason' in analysis_1m)
                valid_5m = analysis_5m and not (isinstance(analysis_5m, dict) and 'reason' in analysis_5m)

                strength_1m = len(analysis_1m['signals']) if valid_1m else 0
                strength_5m = len(analysis_5m['signals']) if valid_5m else 0

                if strength_1m > 0 or strength_5m > 0:
                    best = analysis_1m if strength_1m > strength_5m else analysis_5m
                    best['confirmedBy'] = f"{best['timeframe']} only ({len(best['signals'])} conds)"
                    best['symbol'] = symbol
                    if analysis_1m and analysis_5m and valid_1m and valid_5m:
                        best['atr5m'] = analysis_5m['atr']
                    
                    # 🔥 FIX: Ajouter indicators_1m et indicators_5m à best pour qu'ils soient disponibles dans _last_setup
                    indicators_1m = {}
                    if valid_1m:
                        indicators_1m = {
                            'rsi': analysis_1m.get('rsi'), 'rsi_prev': analysis_1m.get('rsi_prev'),
                            'macd': analysis_1m.get('macd'), 'macd_signal': analysis_1m.get('macd_signal'),
                            'macd_hist': analysis_1m.get('macd_hist'), 'macd_hist_prev': analysis_1m.get('macd_hist_prev'),
                            'adx': analysis_1m.get('adx'), 'di_plus': analysis_1m.get('di_plus'),
                            'di_minus': analysis_1m.get('di_minus'),
                            'di_gap': (analysis_1m.get('di_plus', 0) - analysis_1m.get('di_minus', 0) if analysis_1m.get('di_plus') and analysis_1m.get('di_minus') else None),
                            'ema9': analysis_1m.get('ema9'), 'ema21': analysis_1m.get('ema21'),
                            'ema_diff_pct': (((analysis_1m.get('ema9', 0) - analysis_1m.get('ema21', 0)) / analysis_1m.get('ema21', 1)) * 100 if analysis_1m.get('ema21') else None),
                            'atr': analysis_1m.get('atr'), 'atr_pct': analysis_1m.get('atr_pct'),
                            'bb_upper': analysis_1m.get('bb_upper'), 'bb_middle': analysis_1m.get('bb_middle'), 'bb_lower': analysis_1m.get('bb_lower'),
                            'bb_width': analysis_1m.get('bb_width'), 'bb_distance_to_lower': analysis_1m.get('bb_distance_to_lower'), 'bb_distance_to_upper': analysis_1m.get('bb_distance_to_upper'),
                            'volume': analysis_1m.get('volume'), 'volume_avg': analysis_1m.get('volume_avg'),
                            'volume_ratio': analysis_1m.get('volumeSpike'), 'volume_spike': analysis_1m.get('volumeSpike'),
                        }
                    indicators_5m = {}
                    if valid_5m:
                        indicators_5m = {
                            'rsi': analysis_5m.get('rsi'), 'rsi_prev': analysis_5m.get('rsi_prev'),
                            'macd': analysis_5m.get('macd'), 'macd_signal': analysis_5m.get('macd_signal'),
                            'macd_hist': analysis_5m.get('macd_hist'), 'macd_hist_prev': analysis_5m.get('macd_hist_prev'),
                            'adx': analysis_5m.get('adx'), 'di_plus': analysis_5m.get('di_plus'),
                            'di_minus': analysis_5m.get('di_minus'),
                            'di_gap': (analysis_5m.get('di_plus', 0) - analysis_5m.get('di_minus', 0) if analysis_5m.get('di_plus') and analysis_5m.get('di_minus') else None),
                            'ema9': analysis_5m.get('ema9'), 'ema21': analysis_5m.get('ema21'),
                            'ema_diff_pct': (((analysis_5m.get('ema9', 0) - analysis_5m.get('ema21', 0)) / analysis_5m.get('ema21', 1)) * 100 if analysis_5m.get('ema21') else None),
                            'atr': analysis_5m.get('atr'), 'atr_pct': analysis_5m.get('atr_pct'),
                            'bb_upper': analysis_5m.get('bb_upper'), 'bb_middle': analysis_5m.get('bb_middle'), 'bb_lower': analysis_5m.get('bb_lower'),
                            'bb_width': analysis_5m.get('bb_width'), 'bb_distance_to_lower': analysis_5m.get('bb_distance_to_lower'), 'bb_distance_to_upper': analysis_5m.get('bb_distance_to_upper'),
                            'volume': analysis_5m.get('volume'), 'volume_avg': analysis_5m.get('volume_avg'),
                            'volume_ratio': analysis_5m.get('volumeSpike'), 'volume_spike': analysis_5m.get('volumeSpike'),
                        }
                    best['indicators_1m'] = indicators_1m
                    best['indicators_5m'] = indicators_5m

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
