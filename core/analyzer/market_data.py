"""
Vérifications des données de marché en temps réel
Spread, orderbook imbalance, liquidité
"""

import time
from typing import Dict
from config import TRADING_CONFIG
from utils.logger import get_logger


logger = get_logger()

ORDERBOOK_LONG_MIN_RATIO = 1.1
ORDERBOOK_SHORT_MAX_RATIO = 0.95


async def check_spread(client, symbol: str, spread_cache: Dict) -> Dict:
    """
    Vérifier spread en temps réel avec cache

    Args:
        client: Client MEXC (ccxt)
        symbol: Symbole de la paire
        spread_cache: Cache de spread (dict modifié in-place)

    Returns:
        Dict avec valid, spread_pct, max_allowed, quality
    """
    # Utiliser cache (5 secondes)
    cache_key = symbol
    if cache_key in spread_cache:
        cached = spread_cache[cache_key]
        if time.time() - cached['timestamp'] < 5:  # Cache valide 5 secondes
            return cached['data']

    try:
        # Récupérer orderbook
        orderbook = await client.fetch_order_book(symbol, limit=5)

        # 🔥 FIX: Vérifier que orderbook n'est pas None et contient bids/asks
        if orderbook is None:
            # 🔥 FIX: Ne pas logger ici car WebSocketLogHandler capture déjà logger.error et envoie au frontend
            # Le log sera envoyé automatiquement via WebSocketLogHandler
            return {'valid': False, 'spread_pct': 999, 'max_allowed': 0.03, 'quality': 'ERROR'}
        
        bids = orderbook.get('bids', []) if orderbook else []
        asks = orderbook.get('asks', []) if orderbook else []
        
        best_bid = bids[0][0] if bids and len(bids) > 0 and len(bids[0]) > 0 else 0
        best_ask = asks[0][0] if asks and len(asks) > 0 and len(asks[0]) > 0 else 0

        if best_bid == 0 or best_ask == 0:
            return {'valid': False, 'spread_pct': 999, 'max_allowed': 0.03, 'quality': 'UNKNOWN'}

        mid_price = (best_bid + best_ask) / 2
        spread_pct = ((best_ask - best_bid) / mid_price) * 100

        # Seuil dynamique selon mode TP/SL
        tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')

        if tp_sl_mode == 'FIXE':
            max_spread = 0.03  # 0.03% pour TP +0.25%
        else:
            max_spread = 0.06  # 0.06% pour TP ATR

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
        spread_cache[cache_key] = {
            'timestamp': time.time(),
            'data': result
        }

        return result

    except Exception as e:
        error_msg = f"❌ Erreur check spread {symbol}: {e}"
        # 🔥 FIX: logger.error est capturé par WebSocketLogHandler et envoyé au frontend automatiquement
        # Pas besoin d'envoyer manuellement via websocket_manager.emit (cela créerait un doublon)
        logger.error(error_msg)
        return {'valid': False, 'spread_pct': 999, 'max_allowed': 0.03, 'quality': 'ERROR'}


async def check_orderbook_imbalance(
    client,
    symbol: str,
    direction: str,
    orderbook_cache: Dict
) -> Dict:
    """
    Vérifier imbalance orderbook (bid/ask ratio)

    Args:
        client: Client MEXC (ccxt)
        symbol: Symbole de la paire
        direction: 'LONG' ou 'SHORT'
        orderbook_cache: Cache orderbook (dict modifié in-place)

    Returns:
        Dict avec valid, ratio, quality, bid_value, ask_value
    """
    # Utiliser cache (2 secondes)
    cache_key = f"{symbol}_{direction}"
    if cache_key in orderbook_cache:
        cached = orderbook_cache[cache_key]
        if time.time() - cached['timestamp'] < 2:  # Cache valide 2 secondes
            return cached['data']

    try:
        # Récupérer orderbook (top 10)
        orderbook = await client.fetch_order_book(symbol, limit=10)

        if orderbook is None:
            logger.warning(f"⚠️ Orderbook None pour {symbol}, retour valeur par défaut")
            return {'valid': True, 'ratio': None, 'quality': 'UNKNOWN', 'bid_value': 0, 'ask_value': 0}  # 🔥 FIX: ratio=None au lieu de 1.0 (1.0 = vraie valeur, pas absence de données)

        bids = orderbook.get('bids', [])[:10] if orderbook.get('bids') else []
        asks = orderbook.get('asks', [])[:10] if orderbook.get('asks') else []

        if not bids or not asks:
            return {'valid': True, 'ratio': None, 'quality': 'UNKNOWN', 'bid_value': 0, 'ask_value': 0}  # 🔥 FIX: ratio=None au lieu de 1.0

        # Normaliser ordres en [price, size]
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

        # Validation selon direction
        if direction == 'LONG':
            required_ratio = ORDERBOOK_LONG_MIN_RATIO
            valid = ratio >= required_ratio

            # Quality scoring
            if ratio >= 1.5:
                quality = 'EXCELLENT'
            elif ratio >= 1.3:
                quality = 'GOOD'
            elif ratio >= 1.1:
                quality = 'ACCEPTABLE'
            elif ratio >= required_ratio:
                quality = 'FAIR'
            else:
                quality = 'POOR'

        else:  # SHORT
            required_ratio = ORDERBOOK_SHORT_MAX_RATIO
            valid = ratio <= required_ratio

            if ratio <= 0.6:
                quality = 'EXCELLENT'
            elif ratio <= 0.7:
                quality = 'GOOD'
            elif ratio <= 0.95:
                quality = 'ACCEPTABLE'
            elif ratio <= required_ratio:
                quality = 'FAIR'
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
            'ask_value': ask_value,
            'required_ratio': required_ratio
        }

        # Mettre en cache
        orderbook_cache[cache_key] = {
            'timestamp': time.time(),
            'data': result
        }

        return result

    except Exception as e:
        logger.error(f"❌ Erreur check orderbook {symbol}: {e}")
        # En cas d'erreur, accepter (éviter rejets systématiques)
        return {'valid': True, 'ratio': 1.0, 'quality': 'UNKNOWN', 'bid_value': 0, 'ask_value': 0}
