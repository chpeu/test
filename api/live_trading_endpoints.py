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
        'max_pnl_discrepancy_pct': 20,
        'default_leverage': 10  # 🔥 FUTURES: Levier par défaut (1-125x)
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
        if 'default_leverage' in data:
            # Borner le levier entre 1 et 125
            config['default_leverage'] = max(1, min(125, int(data['default_leverage'])))

        # Sauvegarder
        if not save_live_config(config):
            raise HTTPException(status_code=500, detail="Erreur sauvegarde config")

        # Si mode LIVE, réinitialiser LiveOrderManager
        if config['trading_mode'] == 'LIVE':
            from main import live_order_manager
            from trading.live_order_manager_futures import LiveOrderManagerFutures

            # Créer nouveau LiveOrderManagerFutures avec nouvelle config
            if config.get('api_key_mexc') and config.get('api_secret_mexc'):
                import main
                from config import TRADING_CONFIG
                default_leverage = config.get('default_leverage', TRADING_CONFIG.get('default_leverage', 10))
                
                main.live_order_manager = LiveOrderManagerFutures(
                    api_key=config['api_key_mexc'],
                    api_secret=config['api_secret_mexc'],
                    default_leverage=default_leverage,
                    dry_run=config['dry_run']
                )
                logger.info(
                    f"✅ LiveOrderManagerFutures réinitialisé | "
                    f"Mode: {'DRY_RUN' if config['dry_run'] else 'LIVE RÉEL'} | "
                    f"Levier: {default_leverage}x"
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
    Tester la connexion API MEXC FUTURES

    Args:
        data: Dict avec api_key, api_secret

    Returns:
        JSONResponse avec success, latency_ms, balance, error
    """
    try:
        import time
        import ccxt

        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')

        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API key et secret requis")

        # 🔥 FUTURES: Initialiser exchange avec defaultType: swap
        exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 🔥 FUTURES/Perpetual Swaps
                'adjustForTimeDifference': True,
            }
        })

        # Tester connexion FUTURES
        start = time.time()
        balance = exchange.fetch_balance()
        latency_ms = (time.time() - start) * 1000

        # Récupérer balance USDT futures
        usdt_balance = balance.get('USDT', {})
        free_balance = usdt_balance.get('free', 0) if isinstance(usdt_balance, dict) else 0

        # Tester aussi les positions ouvertes
        positions = []
        try:
            positions = exchange.fetch_positions()
            open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
        except Exception:
            open_positions = []

        return JSONResponse({
            'success': True,
            'mode': 'FUTURES',
            'latency_ms': latency_ms,
            'balance_usdt': free_balance,
            'open_positions': len(open_positions),
            'message': f'✅ Connexion FUTURES réussie | Balance: {free_balance:.2f} USDT | Latence: {latency_ms:.0f}ms'
        })

    except Exception as e:
        logger.error(f"Erreur test connexion MEXC FUTURES: {e}")
        return JSONResponse({
            'success': False,
            'mode': 'FUTURES',
            'error': str(e),
            'message': f'❌ Erreur: {str(e)}'
        }, status_code=400)


@router.post("/emergency-stop")
async def emergency_stop():
    """Arrêt d'urgence du trading live"""
    try:
        from main import live_order_manager, app_state

        app_state['is_scanning'] = False
        closed_positions = []

        # Fermer TOUTES les positions via API si disponible
        if live_order_manager and hasattr(live_order_manager, 'emergency_close_all'):
            results = live_order_manager.emergency_close_all()
            closed_positions = [r.order_id for r in results if r.success]

        logger.warning(f"🛑 ARRÊT D'URGENCE | Positions fermées: {len(closed_positions)}")

        return JSONResponse({
            'success': True,
            'closed_positions': len(closed_positions),
            'message': f'Arrêt d\'urgence activé | {len(closed_positions)} positions fermées'
        })

    except Exception as e:
        logger.error(f"Erreur arrêt d'urgence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    """Récupérer toutes les positions ouvertes"""
    try:
        from main import live_order_manager
        
        if not live_order_manager:
            return JSONResponse({'success': True, 'positions': [], 'count': 0})
        
        if hasattr(live_order_manager, 'get_all_positions'):
            positions = live_order_manager.get_all_positions()
            return JSONResponse({
                'success': True,
                'positions': positions,
                'count': len(positions)
            })
        
        return JSONResponse({'success': True, 'positions': [], 'count': 0})
        
    except Exception as e:
        logger.error(f"Erreur récupération positions: {e}")
        return JSONResponse({'success': False, 'error': str(e), 'positions': []})


@router.get("/balance")
async def get_balance():
    """Récupérer la balance USDT Futures"""
    try:
        from main import live_order_manager
        
        if not live_order_manager:
            return JSONResponse({'success': True, 'balance': 0, 'currency': 'USDT'})
        
        if hasattr(live_order_manager, 'get_balance'):
            balance = live_order_manager.get_balance('USDT')
            return JSONResponse({
                'success': True,
                'balance': balance,
                'currency': 'USDT'
            })
        
        return JSONResponse({'success': True, 'balance': 0, 'currency': 'USDT'})
        
    except Exception as e:
        logger.error(f"Erreur récupération balance: {e}")
        return JSONResponse({'success': False, 'error': str(e), 'balance': 0})


@router.post("/trailing-stop")
async def set_trailing_stop(data: Dict[str, Any]):
    """
    Configurer un trailing stop pour une position
    
    Args:
        symbol: Paire (ex: BTC/USDT)
        callback_rate: Pourcentage de callback (1-5%)
        activation_price: Prix d'activation (optionnel)
    """
    try:
        from main import live_order_manager
        
        symbol = data.get('symbol')
        callback_rate = data.get('callback_rate', 1.0)  # 1% par défaut
        activation_price = data.get('activation_price')
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol requis")
        
        if not live_order_manager:
            raise HTTPException(status_code=400, detail="Live trading non actif")
        
        # Vérifier si position existe
        position = live_order_manager.get_position(symbol) if hasattr(live_order_manager, 'get_position') else None
        if not position:
            raise HTTPException(status_code=400, detail=f"Pas de position ouverte sur {symbol}")
        
        # Pour l'instant, stocker la config trailing stop localement
        # TODO: Implémenter via API MEXC quand supporté
        trailing_config = {
            'symbol': symbol,
            'callback_rate': callback_rate,
            'activation_price': activation_price or position.get('entry_price'),
            'active': True
        }
        
        logger.info(f"✅ Trailing Stop configuré: {symbol} @ {callback_rate}%")
        
        return JSONResponse({
            'success': True,
            'trailing_stop': trailing_config,
            'message': f'Trailing stop activé: {callback_rate}%'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur configuration trailing stop: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-tp-sl")
async def set_tp_sl(data: Dict[str, Any]):
    """
    Configurer TP/SL via API pour une position
    
    Args:
        symbol: Paire (ex: BTC/USDT)
        direction: LONG ou SHORT
        stop_loss: Prix stop loss
        take_profit: Prix take profit
    """
    try:
        from main import live_order_manager
        
        symbol = data.get('symbol')
        direction = data.get('direction', 'LONG')
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol requis")
        
        if not live_order_manager:
            raise HTTPException(status_code=400, detail="Live trading non actif")
        
        if hasattr(live_order_manager, 'set_stop_loss_take_profit'):
            success = live_order_manager.set_stop_loss_take_profit(
                symbol=symbol,
                direction=direction,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit
            )
            
            if success:
                return JSONResponse({
                    'success': True,
                    'message': f'TP/SL configuré pour {symbol}'
                })
            else:
                raise HTTPException(status_code=400, detail="Échec configuration TP/SL")
        
        raise HTTPException(status_code=400, detail="Fonction non disponible")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur configuration TP/SL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funding-rate/{symbol}")
async def get_funding_rate(symbol: str):
    """Récupérer le funding rate pour un symbole"""
    try:
        from main import live_order_manager
        
        if not live_order_manager:
            return JSONResponse({'success': True, 'rate': 0, 'symbol': symbol})
        
        if hasattr(live_order_manager, 'get_funding_rate'):
            rate = live_order_manager.get_funding_rate(symbol)
            return JSONResponse({
                'success': True,
                'rate': rate or 0,
                'symbol': symbol
            })
        
        return JSONResponse({'success': True, 'rate': 0, 'symbol': symbol})
        
    except Exception as e:
        logger.error(f"Erreur récupération funding rate: {e}")
        return JSONResponse({'success': False, 'error': str(e), 'rate': 0})


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

    @ws_manager.command('get_positions')
    async def handle_get_positions(data: Dict, websocket):
        """Récupérer positions via WebSocket"""
        try:
            result = await get_positions()
            return result
        except Exception as e:
            logger.error(f"Erreur WS get_positions: {e}")
            return {'success': False, 'error': str(e), 'positions': []}

    @ws_manager.command('get_balance')
    async def handle_get_balance(data: Dict, websocket):
        """Récupérer balance via WebSocket"""
        try:
            result = await get_balance()
            return result
        except Exception as e:
            logger.error(f"Erreur WS get_balance: {e}")
            return {'success': False, 'error': str(e), 'balance': 0}

    @ws_manager.command('set_trailing_stop')
    async def handle_set_trailing_stop(data: Dict, websocket):
        """Configurer trailing stop via WebSocket"""
        try:
            result = await set_trailing_stop(data)
            return result
        except Exception as e:
            logger.error(f"Erreur WS set_trailing_stop: {e}")
            return {'success': False, 'error': str(e)}

    @ws_manager.command('set_tp_sl')
    async def handle_set_tp_sl(data: Dict, websocket):
        """Configurer TP/SL via WebSocket"""
        try:
            result = await set_tp_sl(data)
            return result
        except Exception as e:
            logger.error(f"Erreur WS set_tp_sl: {e}")
            return {'success': False, 'error': str(e)}

    logger.info("✅ Commandes WebSocket live trading enregistrées")
