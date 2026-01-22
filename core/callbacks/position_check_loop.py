"""
Callbacks pour la boucle de vérification de position
Exécuté toutes les 2 secondes pour vérifier la position active
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

from utils.pricing import get_preferred_price

logger = logging.getLogger(__name__)

# Variables globales injectées par init_instances()
_position_manager = None
_price_provider = None
_app_state = None
_sio = None  # 🔥 MIGRATION: Gardé pour compatibilité, mais utiliser _ws_manager
_ws_manager = None  # 🔥 FIX BUG #13: Ajouter variable globale pour WebSocket natif
_position_lock = None
_analytics_db = None
_notification_manager = None


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
    """Injecter l'instance SocketIO (legacy - gardé pour compatibilité)"""
    global _sio
    _sio = sio


def set_websocket_manager(ws_manager):
    """🔥 FIX BUG #13: Injecter l'instance WebSocketManager"""
    global _ws_manager
    _ws_manager = ws_manager


def set_position_lock(lock):
    """Injecter le lock de position"""
    global _position_lock
    _position_lock = lock


def set_analytics_db(analytics_db):
    """Injecter la base de données analytics"""
    global _analytics_db
    _analytics_db = analytics_db


def set_notification_manager(notification_manager):
    """Injecter NotificationManager pour les alertes Telegram"""
    global _notification_manager
    _notification_manager = notification_manager


async def _notify_error(error_type: str, details: str):
    """Notifier Telegram en cas d'erreur critique"""
    if not _notification_manager:
        return

    try:
        snippet = (details or "Unknown")
        if len(snippet) > 500:
            snippet = snippet[:500] + "..."

        await _notification_manager.notify(
            'error',
            {
                'error_type': error_type,
                'details': snippet
            },
            priority='error',
            channels=['telegram']
        )
    except Exception as notify_err:
        logger.error(f"❌ Erreur notification Telegram (error_type={error_type}): {notify_err}")


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

        fallback_price = getattr(position, 'entry', 0)
        current_price = get_preferred_price(current_price_data, fallback_price)

        if not current_price or current_price <= 0:
            logger.debug(f"⚠️ Prix non exploitable pour {symbol}: {current_price}")
            return

        # 🔥 POST-EXIT: Envoyer prix aux trackers actifs (si le symbole est en tracking)
        try:
            from core.post_exit import get_post_exit_manager
            post_exit_mgr = get_post_exit_manager()
            if post_exit_mgr.is_tracking(symbol):
                post_exit_mgr.on_price_update_sync(symbol, current_price)
        except Exception:
            pass  # Non-bloquant

        # Vérifier la position (retourne None ou raison de fermeture)
        # Stocker le SL avant pour détecter les changements
        sl_before = position.sl if hasattr(position, 'sl') else None
        
        close_reason = await _position_manager.check_position(current_price)

        # Si position toujours active, émettre mise à jour
        if not close_reason:
            # 🔥 FIX SL MISMATCH: Mettre à jour SL temps réel si changé (trailing stop)
            sl_after = position.sl if hasattr(position, 'sl') else None
            if sl_before != sl_after and sl_after and _price_provider:
                if hasattr(_price_provider, 'update_sl_level'):
                    _price_provider.update_sl_level(sl_after)
            
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
                    # 🔥 FIX: Utiliser add_trade pour upsert sécurisé et éviter doublons
                    from core.state_manager import get_state_manager
                    state = get_state_manager()
                    state.add_trade(result)

                    # FIX: Mettre à jour les stats de session
                    _update_session_stats(result)

                # Désactiver WebSocket monitoring si price_provider
                if _price_provider and hasattr(_price_provider, 'stop_websocket'):
                    try:
                        await _price_provider.stop_websocket()
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur arrêt WebSocket: {e}")
                        await _notify_error('stop_websocket_position', str(e))
                
                # 🔥 FIX SL MISMATCH: Désactiver callback SL temps réel
                if _price_provider and hasattr(_price_provider, 'set_sl_check_callback'):
                    _price_provider.set_sl_check_callback(None)
                
                # 🔥 FIX SL MISMATCH V2: Annuler tâche SL en attente
                try:
                    from main import cancel_pending_sl_task
                    closed_symbol = result.get('symbol') if result else None
                    if closed_symbol:
                        cancel_pending_sl_task(closed_symbol)
                except ImportError:
                    pass

                # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
                if _ws_manager:
                    await _ws_manager.emit('position_closed', result)
                    # 🔥 FIX: Émettre stats_update après fermeture de position
                    await _emit_stats_update()

    except Exception as e:
        logger.error(f"❌ Erreur position_check_loop_callback: {e}")
        await _notify_error('position_check_loop', str(e))


async def _emit_position_update(position, current_price: float):
    """
    Émettre mise à jour de position au frontend

    Args:
        position: Objet position active
        current_price: Prix actuel du marché
    """
    logger.info(f"🔄 _emit_position_update appelé pour {position.symbol} @ {current_price}")

    try:
        # Calculer PnL (BUG #1 FIX: utiliser pnl_calculator au lieu de _calculate_pnl)
        pnl = 0.0
        try:
            pnl_calculator = getattr(_position_manager, 'pnl_calculator', None) if _position_manager else None
            if pnl_calculator:
                pnl = pnl_calculator.calculate_pnl_percent(
                    entry=position.entry,
                    current_price=current_price,
                    direction=position.direction
                )
            else:
                entry_price = getattr(position, 'entry', 0) or 0
                if entry_price > 0:
                    pnl = ((current_price - entry_price) / entry_price) * 100
                    if getattr(position, 'direction', 'LONG') == 'SHORT':
                        pnl = -pnl
        except Exception:
            pnl = 0.0
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
        # Import différé pour éviter les problèmes de chargement
        TRADING_CONFIG = {}
        try:
            import sys
            import importlib
            if 'config' not in sys.modules:
                config_module = importlib.import_module('config')
            else:
                config_module = sys.modules['config']
            TRADING_CONFIG = getattr(config_module, 'TRADING_CONFIG', {})
        except Exception as e:
            logger.warning(f"⚠️ Erreur import TRADING_CONFIG: {e}")
            TRADING_CONFIG = {}

        # 🔥 FIX: Émettre mise à jour au frontend avec toutes les infos
        import json
        from datetime import datetime

        def _to_iso(ts_value):
            if ts_value is None:
                return None
            if isinstance(ts_value, str):
                return ts_value
            if isinstance(ts_value, datetime):
                return ts_value.isoformat()
            if isinstance(ts_value, (int, float)):
                return datetime.fromtimestamp(ts_value).isoformat()
            try:
                return datetime.fromtimestamp(float(ts_value)).isoformat()
            except Exception:
                return None

        # 🔥 NOUVEAU: Ajouter opened_at pour le compte à rebours
        opened_at = None
        if hasattr(position, 'start_time') and position.start_time:
            opened_at = datetime.fromtimestamp(position.start_time).isoformat()
        elif hasattr(position, 'timestamp') and position.timestamp:
            # Fallback: utiliser timestamp si start_time n'est pas disponible
            if isinstance(position.timestamp, (int, float)):
                opened_at = datetime.fromtimestamp(position.timestamp).isoformat()
            else:
                opened_at = position.timestamp
        
        effective_config = getattr(position, 'effective_config', {}) or {}

        atr_percent = getattr(position, 'atr_pct_used', None)
        if atr_percent is None:
            atr_percent = getattr(position, 'atr_percent', None)

        tp_sl_mode = getattr(position, 'tp_sl_mode', None) or (TRADING_CONFIG.get('tp_sl_mode', 'FIXE') if TRADING_CONFIG else 'FIXE')
        use_atr_mode = (tp_sl_mode == 'ATR')
        break_even_use_atr = use_atr_mode
        trailing_config = TRADING_CONFIG.get('trailing_stop', {}) if TRADING_CONFIG else {}
        trailing_use_atr_trigger = use_atr_mode

        be_atr_mult_effective = effective_config.get('break_even_atr_mult') or (TRADING_CONFIG.get('break_even_atr_mult', 0.5) if TRADING_CONFIG else 0.5)
        trailing_trigger_atr_mult_effective = effective_config.get('trailing_trigger_atr_mult') or (TRADING_CONFIG.get('trailing_trigger_atr_mult', 1.5) if TRADING_CONFIG else 1.5)
        trailing_distance_mult_effective = (
            effective_config.get('trailing_distance_mult')
            or (TRADING_CONFIG.get('trailing_distance_atr_mult') if TRADING_CONFIG else None)
            or (TRADING_CONFIG.get('trailing_atr_multiplier') if TRADING_CONFIG else None)
            or (TRADING_CONFIG.get('trailing_distance_mult') if TRADING_CONFIG else None)
            or 1.0
        )

        break_even_trigger_pct = None
        if break_even_use_atr and atr_percent is not None:
            break_even_trigger_pct = atr_percent * be_atr_mult_effective
        else:
            break_even_trigger_pct = TRADING_CONFIG.get('break_even_trigger', None) if TRADING_CONFIG else None

        trailing_trigger_pct = None
        trailing_distance_pct = None
        if trailing_use_atr_trigger and atr_percent is not None:
            trailing_trigger_pct = atr_percent * trailing_trigger_atr_mult_effective
            trailing_distance_pct = atr_percent * trailing_distance_mult_effective
        else:
            trailing_trigger_pct = (
                trailing_config.get('trigger_pnl')
                or (TRADING_CONFIG.get('trailing_trigger_pnl', None) if TRADING_CONFIG else None)
            )
            trailing_distance_pct = TRADING_CONFIG.get('trailing_distance', None) if TRADING_CONFIG else None

        stagnation_config = TRADING_CONFIG.get('stagnation_exit', {}) if TRADING_CONFIG else {}
        stagnation_enabled = use_atr_mode and (TRADING_CONFIG.get('stagnation_exit_enabled', stagnation_config.get('enabled', False)) if TRADING_CONFIG else False)
        stagnation_timeout = effective_config.get('stagnation_exit_timeout_seconds')
        if stagnation_timeout is None:
            stagnation_timeout = TRADING_CONFIG.get('stagnation_exit_timeout_seconds', stagnation_config.get('timeout_seconds', None)) if TRADING_CONFIG else None

        stagnation_positive_timeout = effective_config.get('stagnation_positive_timeout_seconds')
        if stagnation_positive_timeout is None:
            stagnation_positive_timeout = TRADING_CONFIG.get('stagnation_positive_timeout_seconds', None) if TRADING_CONFIG else None

        stagnation_min_pnl_to_stay = effective_config.get('stagnation_exit_min_pnl_to_stay')
        if stagnation_min_pnl_to_stay is None:
            stagnation_min_pnl_to_stay = TRADING_CONFIG.get('stagnation_exit_min_pnl_to_stay', None) if TRADING_CONFIG else None

        stagnation_positive_threshold = TRADING_CONFIG.get('stagnation_positive_threshold', None) if TRADING_CONFIG else None
        stagnation_mfe_pullback_pct = TRADING_CONFIG.get('stagnation_mfe_pullback_pct', None) if TRADING_CONFIG else None

        # 🔥 NOUVEAU: Calculer les prochains événements (TP et SL séparés)
        next_events = _calculate_next_event(position, current_price, pnl_pct, atr_percent, 
                                          break_even_trigger_pct, trailing_trigger_pct, 
                                          effective_config, TRADING_CONFIG if TRADING_CONFIG else {})
        
        # 🔥 DEBUG: Log next_events
        if next_events:
            if next_events.get('next_tp'):
                logger.info(f"🎯 Next TP: {next_events['next_tp'].get('type')} - {next_events['next_tp'].get('description')} - distance: {next_events['next_tp'].get('distance_pct', 0):.2f}%")
            if next_events.get('next_sl'):
                logger.info(f"🛑 Next SL: {next_events['next_sl'].get('type')} - {next_events['next_sl'].get('description')} - distance: {next_events['next_sl'].get('distance_pct', 0):.2f}%")
        else:
            logger.warning("⚠️ Next events = None")

        try:
            position.current_price = current_price
            position.pnl = round(pnl, 4)
            position.pnl_pct = round(pnl_pct, 4)
            position.pnl_usdt = round(pnl_usdt, 4)
            # 🔥 FIX: Stocker next_tp et next_sl séparément + next_event pour compatibilité
            position.next_event = next_events.get('next_event') if next_events else None
            position.next_tp = next_events.get('next_tp') if next_events else None
            position.next_sl = next_events.get('next_sl') if next_events else None
        except Exception:
            pass

        update_data = {
            'symbol': position.symbol,
            'direction': position.direction,
            'entry': position.entry,
            'size': position.size,
            'current_price': current_price,
            'pnl': round(pnl, 4),
            'pnl_pct': round(pnl_pct, 4),
            'pnl_usdt': round(pnl_usdt, 4),
            'tp_pct': getattr(position, 'tp_pct', None),
            'sl_pct': getattr(position, 'sl_pct', None),
            'tp_mode': getattr(position, 'tp_mode', None),
            'sl_mode': getattr(position, 'sl_mode', None),
            'tp_atr_mult': getattr(position, 'tp_atr_mult', None),
            'sl_atr_mult': getattr(position, 'sl_atr_mult', None),
            'tp_price': getattr(position, 'tp_price', getattr(position, 'tp', None)),
            'sl_price': getattr(position, 'sl_price', getattr(position, 'sl', None)),
            'next_tp_pct': getattr(position, 'next_tp_pct', None),
            'trailing_stop': getattr(position, 'trailing_stop', None),
            'trailing_activated': getattr(position, 'trailing_activated', False),
            'partial_tp_taken': getattr(position, 'partial_tp_taken', False),
            'partial_tp_sold': getattr(position, 'partial_tp_sold', False),
            'partial_tp_percent': getattr(position, 'partial_tp_percent', None),
            'tp_escalier_levels': getattr(position, 'tp_escalier_levels', []),
            'current_tp_level': getattr(position, 'current_tp_level', None),
            'partial_profit_usdt': getattr(position, 'partial_profit_usdt', 0.0),
            'partial_profit_pct': getattr(position, 'partial_profit_pct', None),
            'force_full_tp_for_partial': getattr(position, 'force_full_tp_for_partial', False),
            'last_update_at': datetime.now().isoformat(),
            'opened_at': opened_at,
            # 🔥 NOUVEAU: Ajouter next_tp et next_sl séparément + next_event pour compatibilité
            'next_event': next_events.get('next_event') if next_events else None,
            'next_tp': next_events.get('next_tp') if next_events else None,
            'next_sl': next_events.get('next_sl') if next_events else None,
            'position_events': getattr(position, 'position_events', []),
            'position_size_contracts': getattr(position, 'position_size_contracts', None),
            'size_initial_contracts': getattr(position, 'size_initial_contracts', None),
            'size_remaining_contracts': getattr(position, 'size_remaining_contracts', None),
            'tp_escalier_enabled': getattr(position, 'tp_escalier_enabled', False),
            'tp_escalier_current_level': getattr(position, 'tp_escalier_current_level', None),
            'tp_escalier_profits': getattr(position, 'tp_escalier_profits', None),
            'tp_escalier_levels': json.dumps(getattr(position, 'tp_escalier_levels', [])) if hasattr(position, 'tp_escalier_levels') and getattr(position, 'tp_escalier_levels') else None,  # 🔥 FIX: Niveaux TP escalier
            # 🔥 FIX: Ajouter levier utilisé pour affichage correct (levier auto adapté)
            'leverage_used': getattr(position, 'leverage_used', None),
            # 🔥 FIX: Ajouter force_full_tp_for_partial pour affichage message TP
            'force_full_tp_for_partial': getattr(position, 'force_full_tp_for_partial', False),
            # 🔥 FIX: Ajouter multiplicateur sizing adaptatif
            'adaptive_sizing_multiplier': getattr(position, 'adaptive_sizing_multiplier', None),
            # 🔥 FIX: Ajouter ML confidence et calibrated winrate pour affichage badge
            'ml_confidence': getattr(position, 'ml_confidence', None),
            'ml_calibrated_winrate': getattr(position, 'ml_calibrated_winrate', None),
            'atr_pct_used': getattr(position, 'atr_pct_used', None),
            'atr_percent': atr_percent,
            'atr_blended': getattr(position, 'atr_blended', None),
            'effective_config': effective_config,
            'break_even_use_atr': break_even_use_atr,
            'break_even_atr_mult_effective': be_atr_mult_effective,
            'break_even_trigger_pct': break_even_trigger_pct,
            'break_even_triggered_at': _to_iso(getattr(position, 'break_even_triggered_at', None)),
            'break_even_price': getattr(position, 'be_price_at_trigger', None),
            'break_even_pnl_pct': getattr(position, 'be_pnl_at_trigger', None),
            'trailing_use_atr_trigger': trailing_use_atr_trigger,
            'trailing_trigger_atr_mult_effective': trailing_trigger_atr_mult_effective,
            'trailing_distance_mult_effective': trailing_distance_mult_effective,
            'trailing_trigger_pct': trailing_trigger_pct,
            'trailing_distance_pct_effective': trailing_distance_pct,
            'trailing_activated': getattr(position, 'trailing_activated', False),
            'trailing_activated_at': _to_iso(getattr(position, 'trailing_activated_at', None)),
            'trailing_final_sl': getattr(position, 'trailing_final_sl', None),
            'trailing_distance_pct': getattr(position, 'trailing_distance_pct', None),
            'trailing_mfe_enabled': (TRADING_CONFIG.get('trailing_mfe_enabled', False) if TRADING_CONFIG else False) if use_atr_mode else False,
            'trailing_mfe_trigger_pct': (TRADING_CONFIG.get('trailing_mfe_trigger_pct', None) if TRADING_CONFIG else None) if use_atr_mode else None,
            'trailing_mfe_triggered': getattr(position, 'trailing_mfe_triggered', False),
            'trailing_mfe_triggered_at': _to_iso(getattr(position, 'trailing_mfe_triggered_at', None)),
            'trailing_mfe_trigger_pnl_pct': getattr(position, 'trailing_mfe_trigger_pnl_pct', None),
            'trailing_mfe_trigger_price': getattr(position, 'trailing_mfe_trigger_price', None),
            'max_price_reached': getattr(position, 'max_price_reached', None),
            'min_price_reached': getattr(position, 'min_price_reached', None),
            'max_pnl_reached': getattr(position, 'max_pnl_reached', None),
            'min_pnl_reached': getattr(position, 'min_pnl_reached', None),
            'max_pnl_timestamp': _to_iso(getattr(position, 'max_pnl_timestamp', None)),
            'min_pnl_timestamp': _to_iso(getattr(position, 'min_pnl_timestamp', None)),
            'stagnation_enabled': stagnation_enabled,
            'stagnation_timeout_seconds_effective': stagnation_timeout,
            'stagnation_positive_timeout_seconds_effective': stagnation_positive_timeout,
            'stagnation_exit_min_pnl_to_stay_effective': stagnation_min_pnl_to_stay,
            'stagnation_positive_threshold': stagnation_positive_threshold,
            'stagnation_mfe_pullback_pct': stagnation_mfe_pullback_pct,
            'stagnation_detected_at': _to_iso(getattr(position, 'stagnation_detected_at', None)),
            'stagnation_pnl_at_detection': getattr(position, 'stagnation_pnl_at_detection', None),
            'stagnation_positive_triggered': getattr(position, 'stagnation_positive_triggered', False),
            'stagnation_mfe_at_exit': getattr(position, 'stagnation_mfe_at_exit', None),
            'stagnation_pullback_at_exit': getattr(position, 'stagnation_pullback_at_exit', None)
        }

        # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
        if _ws_manager:
            await _ws_manager.emit('position_update', update_data)
        # 🔥 FIX: Émettre aussi status pour synchronisation temps réel complète
        if _app_state and _ws_manager:
            status_data = {
                'is_scanning': _app_state.get('is_scanning', False),
                'active_position': update_data,
                'stats': _app_state.get('stats', {}),
                'top_pairs': _app_state.get('top_pairs', [])
            }
            await _ws_manager.emit('status', status_data)

        logger.debug(
            f"📡 position_update émis: {position.symbol} | "
            f"Prix: {current_price:.6f} | PnL: {pnl:.2f}%"
        )

    except Exception as e:
        logger.error(f"❌ Erreur émission position_update: {e}")
        await _notify_error('emit_position_update', str(e))


async def _emit_stats_update():
    """
    Calculer et émettre les stats au frontend via WebSocket
    
    Cette fonction calcule les stats depuis analytics_db ou app_state
    et les émet via WebSocket pour synchronisation temps réel
    """
    if not _ws_manager or not _app_state:
        return
    
    try:
        import time
        stats_dict = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl_usdt': 0.0,
            'total_pnl_pct': 0.0,
            'best_trade': None,
            'worst_trade': None,
            'avg_trade_duration': 0.0
        }
        
        # Récupérer stats depuis analytics_db si disponible
        if _analytics_db:
            try:
                trades = _analytics_db.get_trades(limit=10000)
                if trades:
                    total = len(trades)
                    # 🔥 FIX: Utiliser net_pnl_usdt au lieu de pnl_usdt
                    wins = sum(1 for t in trades if t.get('net_pnl_usdt', t.get('pnl_usdt', 0)) > 0)
                    losses = total - wins
                    
                    # 🔥 FIX: Calculer PnL total avec net_pnl_usdt et net_pnl_pct
                    total_pnl_usdt = sum(t.get('net_pnl_usdt', t.get('pnl_usdt', 0)) for t in trades)
                    total_pnl_pct = sum(t.get('net_pnl_pct', t.get('pnl_pct', 0)) for t in trades)
                    
                    # 🔥 DEBUG: Log pour vérifier les valeurs
                    if total > 0:
                        logger.debug(f"📊 Stats calculées: {total} trades, PnL USDT={total_pnl_usdt:.2f}, PnL %={total_pnl_pct:.2f}")
                        # Afficher les 3 premiers trades pour debug
                        for i, t in enumerate(trades[:3]):
                            logger.debug(f"  Trade {i+1}: net_pnl_usdt={t.get('net_pnl_usdt', 'N/A')}, net_pnl_pct={t.get('net_pnl_pct', 'N/A')}")
                    
                    # 🔥 FIX: Trouver best/worst trade avec net_pnl_usdt
                    best_trade = max(trades, key=lambda t: t.get('net_pnl_usdt', t.get('pnl_usdt', 0)), default=None)
                    worst_trade = min(trades, key=lambda t: t.get('net_pnl_usdt', t.get('pnl_usdt', 0)), default=None)
                    
                    # Calculer durée moyenne
                    durations = [t.get('duration_seconds', 0) for t in trades if t.get('duration_seconds')]
                    avg_duration = sum(durations) / len(durations) if durations else 0.0
                    
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        # 🔥 FIX: Arrondir à 4 décimales pour éviter de perdre les petites valeurs (0.00)
                        'total_pnl_usdt': round(total_pnl_usdt, 4),
                        'total_pnl_pct': round(total_pnl_pct, 4),
                        'best_trade': best_trade,
                        'worst_trade': worst_trade,
                        'avg_trade_duration': round(avg_duration, 2)
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats analytics_db: {e}")
        
        # Fallback: utiliser app_state['trade_history']
        if stats_dict['total_trades'] == 0 and _app_state.get('trade_history'):
            try:
                trades = _app_state['trade_history']
                if trades:
                    total = len(trades)
                    wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0 or t.get('pnl_usdt', 0) > 0)
                    losses = total - wins
                    
                    # Calculer PnL total
                    total_pnl_usdt = sum(t.get('net_pnl_usdt', t.get('pnl_usdt', 0)) for t in trades)
                    total_pnl_pct = sum(t.get('net_pnl_pct', t.get('pnl_pct', 0)) for t in trades)
                    
                    # Trouver best/worst trade
                    best_trade = max(trades, key=lambda t: t.get('net_pnl_usdt', t.get('pnl_usdt', 0)), default=None)
                    worst_trade = min(trades, key=lambda t: t.get('net_pnl_usdt', t.get('pnl_usdt', 0)), default=None)
                    
                    stats_dict = {
                        'total_trades': total,
                        'wins': wins,
                        'losses': losses,
                        'total_pnl_usdt': round(total_pnl_usdt, 2),
                        'total_pnl_pct': round(total_pnl_pct, 2),
                        'best_trade': best_trade,
                        'worst_trade': worst_trade,
                        'avg_trade_duration': 0.0  # Pas disponible dans app_state
                    }
            except Exception as e:
                logger.error(f"❌ Erreur récupération stats app_state: {e}")
        
        # Émettre stats_update via WebSocket
        await _ws_manager.emit('stats_update', stats_dict)
        logger.debug(f"📊 stats_update émis: {stats_dict['wins']}W/{stats_dict['losses']}L - Total: {stats_dict['total_trades']}")
        
    except Exception as e:
        logger.error(f"❌ Erreur émission stats_update: {e}")


def _calculate_next_event(position, current_price, pnl_pct, atr_percent, 
                         break_even_trigger_pct, trailing_trigger_pct,
                         effective_config, trading_config):
    """
    Calculer les prochains événements pour la position active.
    Retourne un dictionnaire avec 'next_tp' et 'next_sl' séparés pour affichage distinct.
    """
    try:
        direction = position.direction
        entry = position.entry
        current_level = pnl_pct * 100  # Convertir en %
        
        # Récupérer TP/SL
        tp_price = position.tp
        sl_price = position.sl
        
        # 🔥 FIX: Construire les événements TP et SL séparément
        result = {
            'next_tp': None,
            'next_sl': None,
            'next_event': None,  # Événement le plus proche (pour compatibilité)
            'current_level_pct': current_level,
            'symbol': position.symbol,
            'direction': direction,
            'atr_percent': atr_percent
        }
        
        # 1. Stop Loss (toujours affiché)
        if sl_price:
            if direction == 'LONG':
                sl_distance = ((sl_price - current_price) / current_price) * 100
            else:
                sl_distance = ((current_price - sl_price) / current_price) * 100
            
            result['next_sl'] = {
                'type': 'SL',
                'price': sl_price,
                'distance_pct': sl_distance,
                'distance_atr': sl_distance / atr_percent if atr_percent else None,
                'color': '#ef4444',  # rouge
                'description': 'Stop Loss'
            }
        
        # 2. Prochain TP (toujours affiché)
        tp_escalier_levels = getattr(position, 'tp_escalier_levels', [])
        current_tp_level = getattr(position, 'current_tp_level', 0)
        tp_sl_mode = getattr(position, 'tp_sl_mode', None) or trading_config.get('tp_sl_mode', 'FIXE')
        partial_tp_sold = getattr(position, 'partial_tp_sold', False)
        disable_final_tp = trading_config.get('partial_tp_disable_final_tp', False)
        use_partial_tp_as_next = (
            tp_sl_mode == 'FIXE'
            and not partial_tp_sold
            and break_even_trigger_pct is not None
        )

        if use_partial_tp_as_next:
            tp_pct = break_even_trigger_pct
            tp_distance = tp_pct - current_level
            tp_price_calc = entry * (1 + tp_pct / 100) if direction == 'LONG' else entry * (1 - tp_pct / 100)

            result['next_tp'] = {
                'type': 'TP_PARTIAL',
                'price': tp_price_calc,
                'distance_pct': tp_distance,
                'distance_atr': tp_distance / atr_percent if atr_percent else None,
                'color': '#10b981',  # vert
                'description': 'TP Partiel'
            }
        elif tp_escalier_levels and current_tp_level < len(tp_escalier_levels):
            # Mode escalier
            next_level = tp_escalier_levels[current_tp_level]
            tp_pct = next_level.get('pct', 0)
            tp_distance = tp_pct - current_level
            tp_price_calc = entry * (1 + tp_pct / 100) if direction == 'LONG' else entry * (1 - tp_pct / 100)
            
            result['next_tp'] = {
                'type': f'TP{current_tp_level + 1}',
                'price': tp_price_calc,
                'distance_pct': tp_distance,
                'distance_atr': tp_distance / atr_percent if atr_percent else None,
                'color': '#10b981',  # vert
                'description': f'TP {current_tp_level + 1}/{len(tp_escalier_levels)}'
            }
        elif tp_price and not (disable_final_tp and partial_tp_sold):
            # TP normal
            if direction == 'LONG':
                tp_distance = ((tp_price - current_price) / current_price) * 100
            else:
                tp_distance = ((current_price - tp_price) / current_price) * 100
            
            result['next_tp'] = {
                'type': 'TP',
                'price': tp_price,
                'distance_pct': tp_distance,
                'distance_atr': tp_distance / atr_percent if atr_percent else None,
                'color': '#10b981',  # vert
                'description': 'Take Profit'
            }
        
        # 3. Calculer l'événement le plus proche (pour compatibilité et logique interne)
        events = []
        
        if result['next_sl']:
            events.append({**result['next_sl'], 'priority': 0})
        
        # Break-even
        be_triggered = getattr(position, 'break_even_triggered', False)
        if not be_triggered and break_even_trigger_pct is not None:
            be_distance = break_even_trigger_pct - current_level
            if be_distance > 0:
                be_price = entry * (1 + break_even_trigger_pct / 100) if direction == 'LONG' else entry * (1 - break_even_trigger_pct / 100)
                events.append({
                    'type': 'BE',
                    'price': be_price,
                    'distance_pct': be_distance,
                    'distance_atr': be_distance / atr_percent if atr_percent else None,
                    'priority': 1,
                    'color': '#3b82f6',  # bleu
                    'description': 'Break-even'
                })
        
        # Trailing activation
        trailing_activated = getattr(position, 'trailing_activated', False)
        if not trailing_activated and trailing_trigger_pct is not None:
            trailing_distance = trailing_trigger_pct - current_level
            if trailing_distance > 0:
                events.append({
                    'type': 'TRAILING',
                    'price': None,
                    'distance_pct': trailing_distance,
                    'distance_atr': trailing_distance / atr_percent if atr_percent else None,
                    'priority': 2,
                    'color': '#8b5cf6',  # violet
                    'description': 'Trailing stop'
                })
        
        if result['next_tp']:
            events.append({**result['next_tp'], 'priority': 3})
        
        # Trier par priorité puis par valeur absolue de distance
        if events:
            events.sort(key=lambda x: (x['priority'], abs(x['distance_pct'])))
            result['next_event'] = events[0]
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur calcul next_event: {e}")
        return None
