"""
Callbacks pour rafraîchissement de scalabilité
🔥 OPT #8: Intervalle adaptatif basé sur volatilité globale
"""

import asyncio
import logging
import time
from typing import Optional

from config import TRADING_CONFIG

logger = logging.getLogger(__name__)

# Variables globales injectées par init_instances()
_scanner = None
_position_manager = None
_price_provider = None
_app_state = None
_sio = None  # 🔥 MIGRATION: Gardé pour compatibilité, mais utiliser _ws_manager
_ws_manager = None  # 🔥 FIX BUG #14: Ajouter variable globale pour WebSocket natif

# 🔥 OPT #8: Variables pour intervalle adaptatif
_last_refresh_time = 0
_current_interval = 90  # Intervalle par défaut
_avg_volatility = 0.0


def set_scanner(scanner):
    """Injecter l'instance scanner"""
    global _scanner
    _scanner = scanner


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
    """🔥 FIX BUG #14: Injecter l'instance WebSocketManager"""
    global _ws_manager
    _ws_manager = ws_manager


def calculate_adaptive_interval(top_pairs: list) -> int:
    """
    🔥 OPT #8: Calculer l'intervalle adaptatif basé sur la volatilité moyenne
    
    - Haute volatilité (>0.5%) → intervalle court (60s)
    - Basse volatilité (<0.2%) → intervalle long (180s)
    - Moyenne → interpolation linéaire
    
    Args:
        top_pairs: Liste des top pairs avec leurs métriques
        
    Returns:
        Intervalle en secondes
    """
    global _avg_volatility
    
    interval_min = TRADING_CONFIG.get('scalability_interval_min', 60)
    interval_max = TRADING_CONFIG.get('scalability_interval_max', 180)
    
    if not top_pairs:
        return (interval_min + interval_max) // 2
    
    # Calculer volatilité moyenne (vol5)
    volatilities = [p.get('vol5', 0) for p in top_pairs if p.get('vol5', 0) > 0]
    if not volatilities:
        return (interval_min + interval_max) // 2
    
    avg_vol = sum(volatilities) / len(volatilities)
    _avg_volatility = avg_vol
    
    # Seuils de volatilité
    vol_low = 0.2   # Basse volatilité
    vol_high = 0.5  # Haute volatilité
    
    if avg_vol >= vol_high:
        # Haute volatilité → refresh rapide
        return interval_min
    elif avg_vol <= vol_low:
        # Basse volatilité → refresh lent
        return interval_max
    else:
        # Interpolation linéaire
        ratio = (avg_vol - vol_low) / (vol_high - vol_low)
        interval = interval_max - (ratio * (interval_max - interval_min))
        return int(interval)


def get_current_interval() -> int:
    """Récupérer l'intervalle actuel (pour le scheduler)"""
    return _current_interval


def should_refresh() -> bool:
    """
    🔥 OPT #8: Vérifier si on doit rafraîchir (basé sur intervalle adaptatif)
    
    Returns:
        True si le temps écoulé >= intervalle actuel
    """
    global _last_refresh_time
    
    now = time.time()
    elapsed = now - _last_refresh_time
    
    return elapsed >= _current_interval


async def scalability_refresh_loop_callback():
    """
    🔥 OPT #8: Callback avec intervalle adaptatif
    
    Procédure:
    1. Vérifier que le scanner est actif
    2. Vérifier intervalle adaptatif (skip si pas encore le moment)
    3. Vérifier qu'aucune position n'est active
    4. Scanner les nouvelles top pairs
    5. Calculer nouvel intervalle basé sur volatilité
    6. Mettre à jour WebSocket avec les nouvelles paires

    Note: Ne procède pas si une position est active pour éviter interruption
    du TP partiel ou autres opérations sensibles
    """
    global _last_refresh_time, _current_interval
    
    if not _app_state or not _app_state.get('is_scanning'):
        logger.debug("⏸️ Scalability refresh: scanner inactif")
        return

    if not _scanner:
        logger.debug("⚠️ Scanner non disponible pour scalability_refresh")
        return

    # 🔥 OPT #8: Vérifier intervalle adaptatif
    if not should_refresh():
        remaining = _current_interval - (time.time() - _last_refresh_time)
        logger.debug(f"⏳ Scalability refresh: {remaining:.0f}s restantes (intervalle={_current_interval}s)")
        return

    try:
        # Vérifier qu'aucune position n'est active
        if _app_state.get('active_position') or (
            _position_manager and _position_manager.active_position
        ):
            logger.info("⏸️ Scalability refresh ignoré - Position active")
            return

        # Mettre à jour le timestamp AVANT le refresh (évite double refresh)
        _last_refresh_time = time.time()
        
        top_pairs = await _refresh_top_pairs()
        
        # 🔥 OPT #8: Calculer nouvel intervalle basé sur volatilité
        if top_pairs:
            new_interval = calculate_adaptive_interval(top_pairs)
            if new_interval != _current_interval:
                logger.info(
                    f"📊 Intervalle adaptatif: {_current_interval}s → {new_interval}s "
                    f"(volatilité moyenne: {_avg_volatility:.2f}%)"
                )
                _current_interval = new_interval

    except Exception as e:
        logger.error(f"❌ Erreur scalability_refresh_loop_callback: {e}")


async def _refresh_top_pairs() -> list:
    """
    Rafraîchir la liste des top pairs

    Procédure:
    1. Scanner les 20 meilleures paires actuellement
    2. Mettre à jour le cache app_state['top_pairs']
    3. Mettre à jour WebSocket avec les nouvelles paires
    4. Émettre événement SocketIO
    
    Returns:
        Liste des top pairs (pour calcul intervalle adaptatif)
    """
    if not _scanner or not _app_state:
        return []

    try:
        logger.info("🔄 Rafraîchissement des top pairs (scalability)...")

        # 🔥 OPT #10: Utiliser la limite configurable
        limit = TRADING_CONFIG.get('top_pairs_limit', 20)
        
        # Scanner les nouvelles top pairs
        top_pairs = await _scanner.scan_top_pairs(limit)

        if not top_pairs:
            logger.warning("⚠️ Aucune paire retournée par scanner")
            return []

        # Mettre à jour le cache
        _app_state['top_pairs'] = top_pairs

        logger.info(f"✅ Top pairs rafraîchies: {len(top_pairs)} paires")

        # 🔥 MIGRATION COMPLÈTE: Utiliser WebSocket natif uniquement
        if _ws_manager:
            await _ws_manager.emit('top_pairs_update', {'pairs': top_pairs})
            logger.debug(f"📡 top_pairs_update émis: {len(top_pairs)} paires")

        # Mettre à jour WebSocket si price_provider disponible
        await _update_websocket(top_pairs)
        
        return top_pairs

    except Exception as e:
        logger.error(f"❌ Erreur rafraîchissement top pairs: {e}")
        return []


async def _update_websocket(top_pairs: list):
    """
    Mettre à jour WebSocket avec les nouvelles paires

    Procédure:
    1. Vérifier qu'aucune position n'est active (🔥 FIX: Ne pas changer WebSocket pendant position)
    2. Arrêter ancien WebSocket
    3. Démarrer nouveau WebSocket avec les nouvelles paires
    4. Logger les changements

    Args:
        top_pairs: Liste des nouvelles top pairs
    """
    if not _price_provider:
        logger.debug("⚠️ Price provider non disponible")
        return

    try:
        # 🔥 FIX: Vérifier qu'aucune position n'est active AVANT de changer le WebSocket
        # Ceci empêche le prix de se figer pendant une position active
        if _app_state and (_app_state.get('active_position') or (
            _position_manager and _position_manager.active_position
        )):
            logger.info("⏸️ Mise à jour WebSocket ignorée - Position active en cours (current_price protection)")
            return

        logger.debug("🔌 Mise à jour WebSocket...")

        # Arrêter ancien WebSocket
        if hasattr(_price_provider, 'stop_websocket'):
            try:
                await _price_provider.stop_websocket()
                logger.debug("✅ Ancien WebSocket arrêté")
            except Exception as e:
                logger.warning(f"⚠️ Erreur arrêt WebSocket: {e}")

        # Extraire les symboles
        symbols = [
            p.get('symbol', '')
            for p in top_pairs[:30]
            if p.get('symbol')
        ]

        if not symbols:
            logger.warning("⚠️ Aucun symbole à monitorer")
            return

        # Démarrer nouveau WebSocket
        if hasattr(_price_provider, 'start_websocket'):
            try:
                await _price_provider.start_websocket(symbols)
                logger.info(f"✅ WebSocket démarré: {len(symbols)} symboles monitorés")
            except Exception as e:
                logger.error(f"❌ Erreur démarrage WebSocket: {e}")

    except Exception as e:
        logger.error(f"❌ Erreur mise à jour WebSocket: {e}")
