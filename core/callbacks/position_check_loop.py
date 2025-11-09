"""
Callbacks pour la boucle de vérification de position
Exécuté toutes les 2 secondes pour vérifier la position active
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Variables globales injectées par init_instances()
_position_manager = None
_price_provider = None
_app_state = None
_sio = None
_position_lock = None
_analytics_db = None


def set_position_manager(position_manager):
    """Injecter l'instance position_manager"""
    global _position_manager
    _position_manager = position_manager


def set_price_provider(price_provider):
    """Injecter l'instance price_provider"""
    global _price_provider
    _price_provider = price_provider


def set_app_state(app_state):
    """Injecter l'état de l'application"""
    global _app_state
    _app_state = app_state


def set_socketio(sio):
    """Injecter l'instance SocketIO"""
    global _sio
    _sio = sio


def set_position_lock(lock):
    """Injecter le lock de position"""
    global _position_lock
    _position_lock = lock


def set_analytics_db(analytics_db):
    """Injecter la base de données analytics"""
    global _analytics_db
    _analytics_db = analytics_db


def _update_session_stats(result: dict):
    """
    Mettre à jour les statistiques de session après fermeture d'une position

    Args:
        result: Dictionnaire retourné par position_manager.close_position()
    """
    if not result or not _app_state:
        return

    # Incrémenter total trades
    _app_state['stats']['total_trades'] += 1

    # Déterminer si win ou loss basé sur net_pnl_usdt
    net_pnl = result.get('net_pnl_usdt', result.get('pnl_usdt', 0))

    if net_pnl > 0:
        _app_state['stats']['wins'] += 1
    else:
        _app_state['stats']['losses'] += 1

    # Calculer winrate
    total = _app_state['stats']['total_trades']
    wins = _app_state['stats']['wins']
    _app_state['stats']['winrate'] = round((wins / total * 100), 2) if total > 0 else 0.0

    logger.info(
        f"📊 Stats session mises à jour: "
        f"{wins}W/{_app_state['stats']['losses']}L "
        f"({_app_state['stats']['winrate']:.1f}% WR) "
        f"- Total: {total}"
    )


async def position_check_loop_callback():
    """
    Callback appelé toutes les 2 secondes pour vérifier la position

    Procédure:
    1. Vérifier qu'une position est active
    2. Récupérer le prix actuel
    3. Effectuer check_position (TP/SL/Break-even/etc.)
    4. Émettre position_update pour le frontend
    5. Si position fermée: archiver et nettoyer
    """
    if not _position_manager or not _price_provider or not _app_state:
        return

    try:
        # Vérifier qu'une position est active
        if not _position_manager.active_position:
            return

        # Récupérer la position
        position = _position_manager.active_position
        symbol = position.symbol

        # Récupérer prix actuel
        current_price_data = await _price_provider.get_price(symbol)
        if not current_price_data:
            # 🔥 FIX: Ne pas logger en WARNING si c'est juste temporaire (peut être normal)
            # Le prix peut être indisponible temporairement sans être une erreur critique
            logger.debug(f"⚠️ Prix indisponible pour {symbol} (tentative suivante dans {_app_state.get('check_interval', 0.1)}s)")
            return

        current_price = (
            current_price_data.get('lastPrice', 0)
            if isinstance(current_price_data, dict)
            else current_price_data
        )

        # Vérifier la position (retourne None ou raison de fermeture)
        close_reason = await _position_manager.check_position(current_price)

        # Si position toujours active, émettre mise à jour
        if not close_reason:
            await _emit_position_update(position, current_price)
            return

        # Position fermée - Acquérir le lock
        if _position_lock:
            async with _position_lock:
                # BUG #2 FIX: Ordre correct des paramètres (exit_price, reason)
                result = _position_manager.close_position(exit_price=current_price, reason=close_reason)

                if _app_state:
                    _app_state['active_position'] = None

                # Archiver dans l'historique
                if result:
                    result['timestamp'] = datetime.now().isoformat()
                    if 'trade_history' not in _app_state:
                        _app_state['trade_history'] = []
                    _app_state['trade_history'].append(result)

                    # Limiter l'historique à 1000 trades
                    if len(_app_state['trade_history']) > 1000:
                        _app_state['trade_history'] = _app_state['trade_history'][-1000:]

                    # FIX: Mettre à jour les stats de session
                    _update_session_stats(result)

                # Désactiver WebSocket monitoring si price_provider
                if _price_provider and hasattr(_price_provider, 'stop_websocket'):
                    try:
                        await _price_provider.stop_websocket()
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur arrêt WebSocket: {e}")

                # FIX: Émettre événement de fermeture avec result directement (compatible frontend)
                if _sio:
                    await _sio.emit('position_closed', result)

    except Exception as e:
        logger.error(f"❌ Erreur position_check_loop_callback: {e}")


async def _emit_position_update(position, current_price: float):
    """
    Émettre mise à jour de position au frontend

    Args:
        position: Objet position active
        current_price: Prix actuel du marché
    """
    if not _position_manager or not _sio:
        return

    try:
        # Calculer PnL (BUG #1 FIX: utiliser pnl_calculator au lieu de _calculate_pnl)
        pnl = _position_manager.pnl_calculator.calculate_pnl_percent(
            entry=position.entry,
            current_price=current_price,
            direction=position.direction
        )
        pnl_pct = pnl / 100  # Convertir % en décimal

        # Calculer taille à considérer (incluant TP partiel)
        size_to_consider = position.size
        partial_profit_usdt = 0.0

        if hasattr(position, 'partial_tp_sold') and position.partial_tp_sold:
            size_to_consider = getattr(position, 'size_remaining', position.size * 0.5)
            partial_profit_usdt = getattr(position, 'partial_profit_usdt', 0.0)

        # Calculer PnL USDT selon direction
        if position.direction == 'LONG':
            price_diff = current_price - position.entry
            pnl_usdt = size_to_consider * (price_diff / position.entry)
        else:  # SHORT
            price_diff = position.entry - current_price
            pnl_usdt = size_to_consider * (price_diff / position.entry)

        # Ajouter profit du TP partiel
        pnl_usdt += partial_profit_usdt

        logger.debug(
            f"📊 Position check: {position.symbol} {position.direction} | "
            f"Entry={position.entry:.6f} | Prix={current_price:.6f} | "
            f"PnL={pnl:.2f}% | PnL USDT={pnl_usdt:.4f}"
        )

        # Importer config pour récupérer le mode TP/SL
        from config import TRADING_CONFIG

        # Émettre mise à jour au frontend
        update_data = {
            'symbol': position.symbol,
            'direction': position.direction,
            'entry': position.entry,
            'current_price': current_price,
            'sl': position.sl,
            'tp': position.tp,
            'pnl': pnl,
            'pnl_usdt': pnl_usdt,
            'size': position.size,
            'break_even_set': getattr(position, 'break_even_set', False),
            'partial_tp_sold': getattr(position, 'partial_tp_sold', False),
            'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        }

        await _sio.emit('position_update', update_data)
        # 🔥 FIX: Émettre aussi status pour synchronisation temps réel complète
        if _app_state:
            status_data = {
                'is_scanning': _app_state.get('is_scanning', False),
                'active_position': update_data,
                'stats': _app_state.get('stats', {}),
                'top_pairs': _app_state.get('top_pairs', [])
            }
            await _sio.emit('status', status_data)

        logger.debug(
            f"📡 position_update émis: {position.symbol} | "
            f"Prix: {current_price:.6f} | PnL: {pnl:.2f}%"
        )

    except Exception as e:
        logger.error(f"❌ Erreur émission position_update: {e}")
