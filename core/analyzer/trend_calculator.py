"""
Calcul des tendances multi-timeframe
Analyse EMA pour déterminer tendance BULLISH/BEARISH/NEUTRAL
"""

from typing import Optional, Dict
from utils.logger import get_logger


logger = get_logger()


async def calculate_trend_data(
    client,
    indicators,
    symbol: str,
    timeframe: str = '15m'
) -> Optional[Dict]:
    """
    Calculer les données de tendance pour un timeframe donné

    Args:
        client: Client MEXC (ccxt)
        indicators: Instance Indicators
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
        ohlcv = await client.fetch_ohlcv(symbol, ccxt_tf, limit=100)

        if not ohlcv or len(ohlcv) < 100:
            return None

        # Extraire closes
        closes = [candle[4] for candle in ohlcv]  # Close price

        # Calculer EMAs
        ema20 = indicators.calculate_ema(closes, 20)
        ema50 = indicators.calculate_ema(closes, 50)
        ema100 = indicators.calculate_ema(closes, 100)

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
