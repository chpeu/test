"""
🔥 SPRINT 1.5: MarketHelper

Patterns 9 & 14 - Scalability Data + Market Validation

Helper pour extraction données de scalabilité et validation market conditions.

Avant (main.py, lignes 666-697):
```python
spread_value = pair.get('spread', 0)
book_depth = pair.get('bookDepth', 0)
balance_score = pair.get('balanceScore', 1.0)

# Validation NaN
if isinstance(spread_value, float) and (spread_value != spread_value):
    spread_value = 0

scalability_data = {
    'spread_pct': spread_value,
    'depth': book_depth,
    # ... 10+ lignes
}
```

Après:
```python
scalability_data = MarketHelper.extract_scalability_data(pair, symbol)
```

Impact: -80 à -190 lignes de code dupliqué
"""

from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MarketHelper:
    """Helper pour données de marché et scalabilité"""

    @staticmethod
    def extract_scalability_data(
        source: Dict[str, Any],
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extraire et valider données de scalabilité depuis pair ou setup

        Args:
            source: Dict source (pair from scanner ou setup from analyzer)
            symbol: Symbole (optionnel, pour logging)

        Returns:
            Dict avec données de scalabilité standardisées

        Exemple:
        ```python
        scalability_data = MarketHelper.extract_scalability_data(pair, "BTC/USDT")
        ```
        """
        # Spread
        spread_value = source.get('spread', 0)

        # Validation NaN
        if isinstance(spread_value, float) and spread_value != spread_value:
            if symbol:
                logger.debug(f"Spread NaN détecté pour {symbol}, utilisation 0")
            spread_value = 0

        # Book depth
        book_depth = source.get('bookDepth', 0)

        # Si depth=0, calculer depuis volumes
        if book_depth == 0:
            bid_vol = source.get('bidVol', 0) or 0
            ask_vol = source.get('askVol', 0) or 0
            book_depth = bid_vol + ask_vol

        # Balance score
        balance_score = source.get('balanceScore', 1.0)
        if isinstance(balance_score, float) and balance_score != balance_score:
            balance_score = 1.0

        return {
            'spread_pct': float(spread_value),
            'depth': float(book_depth),
            'balance': float(balance_score),
            'bid_vol': float(source.get('bidVol', 0) or 0),
            'ask_vol': float(source.get('askVol', 0) or 0),
        }

    @staticmethod
    async def validate_market_conditions(
        client: Any,
        symbol: str,
        direction: str,
        spread_cache: Optional[Dict] = None,
        orderbook_cache: Optional[Dict] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Valider spread ET orderbook en un seul appel

        Args:
            client: Client API (avec méthodes check_spread, check_orderbook_imbalance)
            symbol: Symbole
            direction: Direction (LONG/SHORT)
            spread_cache: Cache pour spread (optionnel)
            orderbook_cache: Cache pour orderbook (optionnel)

        Returns:
            Tuple (valid, market_data, reason)
            - valid: True si conditions OK
            - market_data: Dict avec spread_pct, orderbook_ratio, etc.
            - reason: Raison rejet si not valid

        Exemple:
        ```python
        valid, data, reason = await MarketHelper.validate_market_conditions(
            client=self.client,
            symbol="BTC/USDT",
            direction="LONG",
            spread_cache=self._spread_cache
        )
        ```
        """
        try:
            # Check spread
            from utils.market_conditions import check_spread

            spread_check = await check_spread(
                client=client,
                symbol=symbol,
                spread_cache=spread_cache or {}
            )

            if not spread_check['valid']:
                reason = (
                    f"Spread trop élevé "
                    f"({spread_check['spread_pct']:.3f}% > {spread_check['max_allowed']:.3f}%)"
                )
                logger.warning(f"⚠️ {symbol} - {reason}")
                return False, None, reason

            # Check orderbook
            from utils.market_conditions import check_orderbook_imbalance

            orderbook_check = await check_orderbook_imbalance(
                client=client,
                symbol=symbol,
                direction=direction,
                orderbook_cache=orderbook_cache or {}
            )

            if not orderbook_check['valid']:
                reason = (
                    f"Orderbook défavorable "
                    f"(ratio={orderbook_check['ratio']:.2f}, "
                    f"quality={orderbook_check['quality']})"
                )
                logger.warning(f"⚠️ {symbol} - {reason}")
                return False, None, reason

            # Tout OK → retour market data
            market_data = {
                'spread_pct': spread_check['spread_pct'],
                'spread_max_allowed': spread_check['max_allowed'],
                'orderbook_ratio': orderbook_check['ratio'],
                'orderbook_quality': orderbook_check['quality'],
                'orderbook_bid_depth': orderbook_check.get('bid_depth', 0),
                'orderbook_ask_depth': orderbook_check.get('ask_depth', 0),
            }

            return True, market_data, None

        except Exception as e:
            reason = f"Erreur validation market: {e}"
            logger.error(f"❌ {symbol} - {reason}")
            return False, None, reason

    @staticmethod
    def validate_volume(
        volume_24h: Optional[float],
        min_volume: float = 1000000.0,
        symbol: Optional[str] = None
    ) -> bool:
        """
        Valider volume 24h

        Args:
            volume_24h: Volume 24h en USDT
            min_volume: Volume minimum requis
            symbol: Symbole (pour logging)

        Returns:
            True si volume suffisant
        """
        if volume_24h is None or volume_24h < min_volume:
            if symbol:
                logger.warning(
                    f"⚠️ {symbol} - Volume insuffisant: "
                    f"{volume_24h or 0:.0f} < {min_volume:.0f}"
                )
            return False

        return True

    @staticmethod
    def validate_liquidity_score(
        liquidity_score: Optional[float],
        min_score: float = 0.5,
        symbol: Optional[str] = None
    ) -> bool:
        """
        Valider score de liquidité

        Args:
            liquidity_score: Score de liquidité (0-1)
            min_score: Score minimum requis
            symbol: Symbole (pour logging)

        Returns:
            True si score suffisant
        """
        if liquidity_score is None or liquidity_score < min_score:
            if symbol:
                logger.warning(
                    f"⚠️ {symbol} - Liquidité insuffisante: "
                    f"{liquidity_score or 0:.2f} < {min_score:.2f}"
                )
            return False

        return True

    @staticmethod
    def calculate_liquidity_score(
        bid_vol: float,
        ask_vol: float,
        spread_pct: float,
        book_depth: float
    ) -> float:
        """
        Calculer score de liquidité composite

        Args:
            bid_vol: Volume bid
            ask_vol: Volume ask
            spread_pct: Spread en %
            book_depth: Profondeur orderbook

        Returns:
            Score 0-1 (1 = meilleure liquidité)

        Formule:
        - Balance bid/ask (30%)
        - Spread (40%)
        - Depth (30%)
        """
        # Balance bid/ask (0-1)
        total_vol = bid_vol + ask_vol
        if total_vol > 0:
            balance = 1.0 - abs(bid_vol - ask_vol) / total_vol
        else:
            balance = 0.0

        # Spread score (0-1) - spread plus bas = meilleur
        # 0.05% = 1.0, 0.5% = 0.0
        spread_score = max(0, 1.0 - (spread_pct / 0.5))

        # Depth score (0-1) - normalisé sur 1M
        depth_score = min(1.0, book_depth / 1000000.0)

        # Score composite
        liquidity_score = (
            0.3 * balance +
            0.4 * spread_score +
            0.3 * depth_score
        )

        return liquidity_score

    @staticmethod
    def format_volume(volume: float) -> str:
        """
        Formater volume pour affichage

        Args:
            volume: Volume en USDT

        Returns:
            Volume formaté (ex: "1.2M", "850K")
        """
        if volume >= 1000000:
            return f"{volume / 1000000:.1f}M"
        elif volume >= 1000:
            return f"{volume / 1000:.0f}K"
        else:
            return f"{volume:.0f}"

    @staticmethod
    def extract_ticker_data(
        ticker: Optional[Dict[str, Any]],
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extraire données essentielles d'un ticker

        Args:
            ticker: Ticker data
            symbol: Symbole (pour logging)

        Returns:
            Dict avec données ticker standardisées
        """
        if not ticker:
            return {
                'price': 0.0,
                'volume': 0.0,
                'high': 0.0,
                'low': 0.0,
                'change_pct': 0.0,
            }

        return {
            'price': float(ticker.get('lastPrice') or ticker.get('last') or ticker.get('close') or 0),
            'volume': float(ticker.get('quoteVolume') or ticker.get('volume') or 0),
            'high': float(ticker.get('high') or 0),
            'low': float(ticker.get('low') or 0),
            'change_pct': float(ticker.get('percentage') or ticker.get('change') or 0),
        }
