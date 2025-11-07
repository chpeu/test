"""
Callbacks pour rafraîchissement de scalabilité
Exécuté toutes les 90 secondes pour rafraîchir la liste des top pairs
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Variables globales injectées par init_instances()
_scanner = None
_position_manager = None
_price_provider = None
_app_state = None
_sio = None


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
    """Injecter l'instance SocketIO"""
    global _sio
    _sio = sio


async def scalability_refresh_loop_callback():
    """
    Callback appelé toutes les 90 secondes pour rafraîchir la liste des top pairs

    Procédure:
    1. Vérifier que le scanner est actif
    2. Vérifier qu'aucune position n'est active (pour éviter interruption)
    3. Scanner les nouvelles top pairs
    4. Mettre à jour WebSocket avec les nouvelles paires
    5. Émettre événement SocketIO

    Note: Ne procède pas si une position est active pour éviter interruption
    du TP partiel ou autres opérations sensibles
    """
    if not _app_state or not _app_state.get('is_scanning'):
        logger.debug("⏸️ Scalability refresh: scanner inactif")
        return

    if not _scanner:
        logger.debug("⚠️ Scanner non disponible pour scalability_refresh")
        return

    try:
        # Vérifier qu'aucune position n'est active
        if _app_state.get('active_position') or (
            _position_manager and _position_manager.active_position
        ):
            logger.info("⏸️ Scalability refresh ignoré - Position active")
            return

        await _refresh_top_pairs()

    except Exception as e:
        logger.error(f"❌ Erreur scalability_refresh_loop_callback: {e}")


async def _refresh_top_pairs():
    """
    Rafraîchir la liste des top pairs

    Procédure:
    1. Scanner les 20 meilleures paires actuellement
    2. Mettre à jour le cache app_state['top_pairs']
    3. Mettre à jour WebSocket avec les nouvelles paires
    4. Émettre événement SocketIO
    """
    if not _scanner or not _app_state:
        return

    try:
        logger.info("🔄 Rafraîchissement des top pairs (scalability)...")

        # Scanner les nouvelles top pairs
        top_pairs = await _scanner.scan_top_pairs(20)

        if not top_pairs:
            logger.warning("⚠️ Aucune paire retournée par scanner")
            return

        # Mettre à jour le cache
        _app_state['top_pairs'] = top_pairs

        logger.info(f"✅ Top pairs rafraîchies: {len(top_pairs)} paires")

        # Émettre événement SocketIO
        if _sio:
            await _sio.emit('top_pairs_update', {'pairs': top_pairs})
            logger.debug(f"📡 top_pairs_update émis: {len(top_pairs)} paires")

        # Mettre à jour WebSocket si price_provider disponible
        await _update_websocket(top_pairs)

    except Exception as e:
        logger.error(f"❌ Erreur rafraîchissement top pairs: {e}")


async def _update_websocket(top_pairs: list):
    """
    Mettre à jour WebSocket avec les nouvelles paires

    Procédure:
    1. Arrêter ancien WebSocket
    2. Démarrer nouveau WebSocket avec les nouvelles paires
    3. Logger les changements

    Args:
        top_pairs: Liste des nouvelles top pairs
    """
    if not _price_provider:
        logger.debug("⚠️ Price provider non disponible")
        return

    try:
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
