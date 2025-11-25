#!/usr/bin/env python3
"""
API Endpoints pour Live Trading Configuration
Gestion de la configuration live trading (mode, dry-run, API keys, alertes)
"""

import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Router FastAPI
router = APIRouter(prefix="/api/live", tags=["live"])

# Fichier de configuration live
LIVE_CONFIG_FILE = Path("config_live_persistent.json")


def load_live_config() -> Dict[str, Any]:
    """Charger la configuration live depuis le fichier"""
    default_config = {
        'trading_mode': 'PAPER',
        'dry_run': True,
        'api_key_mexc': '',
        'api_secret_mexc': '',
        'max_slippage_pct': 0.15,
        'max_latency_ms': 1000,
        'max_pnl_discrepancy_pct': 20
    }

    if not LIVE_CONFIG_FILE.exists():
        return default_config

    try:
        with open(LIVE_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Merger avec defaults pour ajouter les clés manquantes
            return {**default_config, **config}
    except Exception as e:
        logger.error(f"Erreur lecture config live: {e}")
        return default_config


def save_live_config(config: Dict[str, Any]) -> bool:
    """Sauvegarder la configuration live dans le fichier"""
    try:
        with open(LIVE_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde config live: {e}")
        return False


@router.get("/stats")
async def get_live_stats():
    """
    Récupérer les statistiques live trading

    Returns:
        JSONResponse avec mode, stats ordres, latences, health check
    """
    try:
        # Charger config
        config = load_live_config()

        # Récupérer stats depuis LiveOrderManager si actif
        from main import live_order_manager

        if live_order_manager:
            stats = live_order_manager.get_stats()

            return JSONResponse({
                'mode': 'LIVE' if not live_order_manager.dry_run else 'DRY_RUN',
                'live_enabled': True,
                'dry_run': live_order_manager.dry_run,
                'orders_placed': stats['orders_placed'],
                'orders_filled': stats['orders_filled'],
                'orders_failed': stats['orders_failed'],
                'success_rate': stats['success_rate'],
                'avg_latency_ms': stats['avg_latency_ms'],
                'api_healthy': stats['avg_latency_ms'] < config.get('max_latency_ms', 1000),
                'warnings': []
            })
        else:
            # Mode PAPER
            return JSONResponse({
                'mode': 'PAPER',
                'live_enabled': False,
                'dry_run': None,
                'orders_placed': 0,
                'orders_filled': 0,
                'orders_failed': 0,
                'success_rate': 0,
                'avg_latency_ms': 0,
                'api_healthy': True,
                'warnings': []
            })

    except Exception as e:
        logger.error(f"Erreur récupération stats live: {e}")
        return JSONResponse({
            'mode': 'PAPER',
            'live_enabled': False,
            'error': str(e)
        })


@router.get("/config")
async def get_live_config():
    """
    Récupérer la configuration live actuelle

    Returns:
        JSONResponse avec trading_mode, dry_run, alertes
    """
    try:
        config = load_live_config()

        # Ne pas renvoyer les API keys en clair (sécurité)
        config_safe = config.copy()
        if config_safe.get('api_key_mexc'):
            config_safe['api_key_mexc'] = '***' + config_safe['api_key_mexc'][-4:] if len(config_safe['api_key_mexc']) > 4 else '***'
        if config_safe.get('api_secret_mexc'):
            config_safe['api_secret_mexc'] = '***'

        return JSONResponse({
            'success': True,
            **config_safe
        })

    except Exception as e:
        logger.error(f"Erreur récupération config live: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_live_config(data: Dict[str, Any]):
    """
    Mettre à jour la configuration live

    Args:
        data: Dict avec trading_mode, dry_run, api_key_mexc, etc.

    Returns:
        JSONResponse avec success, updated
    """
    try:
        # Charger config actuelle
        config = load_live_config()

        # Mettre à jour les champs fournis
        if 'trading_mode' in data:
            config['trading_mode'] = data['trading_mode']
        if 'dry_run' in data:
            config['dry_run'] = bool(data['dry_run'])
        if 'api_key_mexc' in data and data['api_key_mexc']:
            config['api_key_mexc'] = data['api_key_mexc']
        if 'api_secret_mexc' in data and data['api_secret_mexc']:
            config['api_secret_mexc'] = data['api_secret_mexc']
        if 'max_slippage_pct' in data:
            config['max_slippage_pct'] = float(data['max_slippage_pct'])
        if 'max_latency_ms' in data:
            config['max_latency_ms'] = int(data['max_latency_ms'])
        if 'max_pnl_discrepancy_pct' in data:
            config['max_pnl_discrepancy_pct'] = float(data['max_pnl_discrepancy_pct'])

        # Sauvegarder
        if not save_live_config(config):
            raise HTTPException(status_code=500, detail="Erreur sauvegarde config")

        # Si mode LIVE, réinitialiser LiveOrderManager
        if config['trading_mode'] == 'LIVE':
            from main import live_order_manager
            from trading.live_order_manager import LiveOrderManager

            # Créer nouveau LiveOrderManager avec nouvelle config
            if config.get('api_key_mexc') and config.get('api_secret_mexc'):
                import main
                main.live_order_manager = LiveOrderManager(
                    api_key=config['api_key_mexc'],
                    api_secret=config['api_secret_mexc'],
                    dry_run=config['dry_run']
                )
                logger.info(
                    f"✅ LiveOrderManager réinitialisé | "
                    f"Mode: {'DRY_RUN' if config['dry_run'] else 'LIVE RÉEL'}"
                )

        return JSONResponse({
            'success': True,
            'updated': config,
            'message': 'Configuration sauvegardée avec succès'
        })

    except Exception as e:
        logger.error(f"Erreur mise à jour config live: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-connection")
async def test_mexc_connection(data: Dict[str, Any]):
    """
    Tester la connexion API MEXC

    Args:
        data: Dict avec api_key, api_secret

    Returns:
        JSONResponse avec success, latency_ms, error
    """
    try:
        import time
        import ccxt

        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API key et secret requis")

        # Initialiser exchange
        exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True
        })

        # Tester connexion
        start = time.time()
        balance = exchange.fetch_balance()
        latency_ms = (time.time() - start) * 1000

        return JSONResponse({
            'success': True,
            'latency_ms': latency_ms,
            'balance_usdt': balance.get('USDT', {}).get('free', 0),
            'message': f'Connexion réussie | Latence: {latency_ms:.0f}ms'
        })

    except Exception as e:
        logger.error(f"Erreur test connexion MEXC: {e}")
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=400)


@router.post("/emergency-stop")
async def emergency_stop():
    """
    Arrêt d'urgence du trading live

    Returns:
        JSONResponse avec success
    """
    try:
        from main import live_order_manager, app_state

        # Arrêter scanner
        app_state['is_scanning'] = False

        # Fermer position active si existe (en mode dry-run pour sécurité)
        from main import position_manager
        if position_manager and position_manager.active_position:
            logger.warning("🛑 ARRÊT D'URGENCE: Fermeture position active")
            # TODO: Implémenter fermeture d'urgence position

        logger.warning("🛑 ARRÊT D'URGENCE activé")

        return JSONResponse({
            'success': True,
            'message': 'Arrêt d\'urgence activé | Trading stoppé'
        })

    except Exception as e:
        logger.error(f"Erreur arrêt d'urgence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Commands Handlers
# ============================================================================

def register_websocket_commands(ws_manager):
    """
    Enregistrer les commandes WebSocket pour live trading

    Args:
        ws_manager: Instance du WebSocketManager
    """

    @ws_manager.command('get_live_config')
    async def handle_get_live_config(data: Dict, websocket):
        """Récupérer config live via WebSocket"""
        try:
            config = load_live_config()

            # Ne pas renvoyer les API keys en clair
            config_safe = config.copy()
            if config_safe.get('api_key_mexc'):
                config_safe['api_key_mexc'] = '***' + config_safe['api_key_mexc'][-4:] if len(config_safe['api_key_mexc']) > 4 else '***'
            if config_safe.get('api_secret_mexc'):
                config_safe['api_secret_mexc'] = '***'

            return {
                'success': True,
                **config_safe
            }
        except Exception as e:
            logger.error(f"Erreur WS get_live_config: {e}")
            return {'success': False, 'error': str(e)}

    @ws_manager.command('update_live_config')
    async def handle_update_live_config(data: Dict, websocket):
        """Mettre à jour config live via WebSocket"""
        try:
            # Appeler l'endpoint update directement
            result = await update_live_config(data)
            return result
        except Exception as e:
            logger.error(f"Erreur WS update_live_config: {e}")
            return {'success': False, 'error': str(e)}

    @ws_manager.command('test_mexc_connection')
    async def handle_test_connection(data: Dict, websocket):
        """Tester connexion MEXC via WebSocket"""
        try:
            result = await test_mexc_connection(data)
            return result
        except Exception as e:
            logger.error(f"Erreur WS test_mexc_connection: {e}")
            return {'success': False, 'error': str(e)}

    @ws_manager.command('emergency_stop')
    async def handle_emergency_stop(data: Dict, websocket):
        """Arrêt d'urgence via WebSocket"""
        try:
            result = await emergency_stop()
            return result
        except Exception as e:
            logger.error(f"Erreur WS emergency_stop: {e}")
            return {'success': False, 'error': str(e)}

    logger.info("✅ Commandes WebSocket live trading enregistrées")
