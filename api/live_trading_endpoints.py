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
        'default_leverage': 1   # 🔥 FUTURES: Levier par défaut (1-125x)
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


@router.post("/reconcile-mexc")
async def run_mexc_reconciliation():
    """
    Exécute le script de réconciliation MEXC vs DB
    """
    import subprocess
    import sys
    from pathlib import Path
    
    script_path = Path("verification/reconcile_exchange_export_vs_db.py")
    excel_path = Path("export mexc.xlsx")
    output_csv = Path("verification/reconcile_mexc_vs_db_agg.csv")
    
    if not excel_path.exists():
        return JSONResponse({
            "success": False,
            "error": "Fichier 'export mexc.xlsx' introuvable à la racine."
        }, status_code=404)
        
    try:
        # Exécuter la commande
        cmd = [
            sys.executable, str(script_path),
            "--file", str(excel_path),
            "--mexc-fr-orders",
            "--output-csv", str(output_csv),
            "--sheet", "Feuil3",
            "--auto-time-offset",
            "--time-tolerance-seconds", "3600"
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if process.returncode != 0:
            logger.error(f"Erreur réconciliation: {process.stderr}")
            return JSONResponse({
                "success": False,
                "error": f"Erreur lors de l'exécution du script: {process.stderr}"
            }, status_code=500)
            
        # Lire le résultat du CSV pour le renvoyer
        import pandas as pd
        if output_csv.exists():
            df = pd.read_csv(output_csv)
            # On ne renvoie que les colonnes intéressantes
            results = df.to_dict(orient="records")
            return JSONResponse({
                "success": True,
                "output": process.stdout,
                "results": results,
                "summary": {
                    "total_mismatches": len(df),
                    "mean_pnl_diff": float(df["pnl_diff_usdt"].mean()) if not df.empty else 0,
                    "max_size_diff": float(df["size_diff_ratio"].max()) if not df.empty else 0
                }
            })
        else:
            return JSONResponse({
                "success": True,
                "output": process.stdout,
                "results": [],
                "message": "Aucun écart détecté."
            })
            
    except Exception as e:
        logger.error(f"Exception pendant réconciliation: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


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
        from core.state_manager import get_state_manager

        state = get_state_manager()
        live_order_manager = state.get_live_order_manager()
        if not live_order_manager:
            from main import live_order_manager as legacy_live_order_manager

            live_order_manager = legacy_live_order_manager

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


@router.get("/health")
async def get_health_dashboard():
    """
    🔥 NOUVEAU: Dashboard de santé complet du système de trading

    Retourne:
    - État du Circuit Breaker
    - État du Token Monitor (si bypass actif)
    - Stats du Rate Limiter adaptatif (si bypass actif)
    - Métriques système (success rate, latence, PnL)

    Returns:
        JSONResponse avec health status complet
    """
    try:
        from main import live_order_manager

        if not live_order_manager:
            return JSONResponse({
                'success': True,
                'mode': 'PAPER',
                'message': 'Live trading non actif (mode PAPER)',
                'health': {
                    'timestamp': None,
                    'mode': 'paper',
                    'dry_run': True,
                    'circuit_breaker': {'enabled': False},
                    'token_monitor': {'enabled': False},
                    'rate_limiter': {'enabled': False},
                    'system': {
                        'orders_placed': 0,
                        'orders_filled': 0,
                        'orders_failed': 0,
                        'success_rate_pct': 0.0,
                        'avg_latency_ms': 0.0,
                        'total_pnl_usdt': 0.0,
                    }
                }
            })

        # Récupérer le health status complet
        if hasattr(live_order_manager, 'get_health_status'):
            health_status = live_order_manager.get_health_status()

            return JSONResponse({
                'success': True,
                'health': health_status,
                'message': 'Health status récupéré avec succès'
            })
        else:
            # Fallback si méthode non disponible
            return JSONResponse({
                'success': False,
                'error': 'Méthode get_health_status() non disponible sur LiveOrderManager',
                'message': 'Veuillez mettre à jour LiveOrderManager avec la v7.3'
            }, status_code=501)

    except Exception as e:
        logger.error(f"Erreur récupération health status: {e}")
        return JSONResponse({
            'success': False,
            'error': str(e),
            'message': f'Erreur: {str(e)}'
        }, status_code=500)


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
                default_leverage = config.get('default_leverage', TRADING_CONFIG.get('default_leverage', 1))
                browser_token = TRADING_CONFIG.get('mexc_browser_token') or os.getenv('MEXC_BROWSER_TOKEN', '').strip()
                use_bypass_mode = TRADING_CONFIG.get('use_bypass_mode', True)

                if use_bypass_mode and not browser_token:
                    logger.warning("⚠️ Mode BYPASS activé mais aucun browser token fourni (MEXC_BROWSER_TOKEN). Retour en mode CCXT.")

                # 🔥 v7.3: Récupérer telegram_notifier depuis notification_manager
                telegram_notif = None
                if hasattr(main, 'notification_manager') and main.notification_manager:
                    if hasattr(main.notification_manager, 'telegram_notifier'):
                        telegram_notif = main.notification_manager.telegram_notifier

                lom = LiveOrderManagerFutures(
                    api_key=config['api_key_mexc'],
                    api_secret=config['api_secret_mexc'],
                    browser_token=browser_token if browser_token else None,
                    default_leverage=default_leverage,
                    dry_run=config['dry_run'],
                    use_bypass=use_bypass_mode and bool(browser_token),
                    telegram_notifier=telegram_notif,  # 🔥 v7.3: Alertes Telegram
                    enable_circuit_breaker=True,       # 🔥 v7.3: Circuit Breaker actif
                    circuit_breaker_threshold=5        # 🔥 v7.3: 5 échecs → ouverture circuit
                )
                
                # 🔥 SYNC: Update both StateManager and main module
                from core.state_manager import get_state_manager
                get_state_manager().set_live_order_manager(lom)
                main.live_order_manager = lom
                
                logger.info(
                    f"✅ LiveOrderManagerFutures réinitialisé | "
                    f"Mode: {'DRY_RUN' if config['dry_run'] else 'LIVE RÉEL'} | "
                    f"Levier: {default_leverage}x | "
                    f"Bypass: {'ON' if use_bypass_mode and browser_token else 'OFF'}"
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
        data: Dict avec api_key, api_secret (optionnels si déjà configurés)

    Returns:
        JSONResponse avec success, latency_ms, balance, error
    """
    try:
        import time
        import ccxt

        api_key = data.get('api_key', '')
        api_secret = data.get('api_secret', '')

        # 🔥 FIX: Si aucune clé passée, utiliser les clés configurées
        if not api_key or not api_secret:
            config = load_live_config()
            if not api_key:
                api_key = config.get('api_key_mexc', '')
            if not api_secret:
                api_secret = config.get('api_secret_mexc', '')
        
        if not api_key or not api_secret:
            raise HTTPException(status_code=400, detail="API key et secret requis (non configurés)")

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


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker():
    """
    Réinitialiser manuellement le Circuit Breaker

    Utilisé pour débloquer le trading après que le Circuit Breaker
    se soit ouvert suite à des erreurs consécutives.
    """
    try:
        from main import live_order_manager

        if not live_order_manager:
            raise HTTPException(status_code=400, detail="Live Order Manager non disponible")

        if not hasattr(live_order_manager, 'circuit_breaker') or not live_order_manager.circuit_breaker:
            return JSONResponse({
                'success': False,
                'message': 'Circuit Breaker non activé'
            })

        # Récupérer l'état avant reset
        status_before = live_order_manager.circuit_breaker.get_status()

        # Réinitialiser le circuit breaker
        live_order_manager.circuit_breaker.reset()

        # Récupérer l'état après reset
        status_after = live_order_manager.circuit_breaker.get_status()

        logger.warning(
            f"🔄 Circuit Breaker réinitialisé manuellement | "
            f"État avant: {status_before['state']} ({status_before['failure_count']} échecs) | "
            f"État après: {status_after['state']}"
        )

        return JSONResponse({
            'success': True,
            'message': 'Circuit Breaker réinitialisé avec succès',
            'status_before': status_before,
            'status_after': status_after
        })

    except Exception as e:
        logger.error(f"Erreur réinitialisation Circuit Breaker: {e}")
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


@router.get('/token/status')
async def get_token_status():
    """
    🔥 NOUVEAU: Récupérer le statut du token MEXC
    
    Returns:
        - token_healthy: Token valide
        - token_age_hours: Âge du token en heures
        - estimated_expiry_hours: Temps restant estimé avant expiration
        - proactive_alert_sent: Alerte proactive envoyée
    """
    try:
        from main import live_order_manager
        
        if not live_order_manager:
            return JSONResponse({
                'success': False,
                'message': 'Live trading non initialisé'
            })
        
        # Récupérer le client MEXC bypass
        if hasattr(live_order_manager, 'client') and live_order_manager.client:
            client = live_order_manager.client
            
            # Récupérer le token monitor
            if hasattr(client, '_token_monitor') and client._token_monitor:
                status = client._token_monitor.get_status()
                return JSONResponse({
                    'success': True,
                    **status
                })
        
        return JSONResponse({
            'success': False,
            'message': 'Token monitor non disponible'
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération statut token: {e}")
        return JSONResponse({'success': False, 'error': str(e)})


@router.post('/token/reset-timer')
async def reset_token_timer():
    """
    🔥 NOUVEAU: Réinitialiser le timer du token après renouvellement manuel
    
    Appeler cette API après avoir:
    1. Mis à jour MEXC_BROWSER_TOKEN dans .env
    2. Redémarré le bot
    
    Cela réinitialise le compteur d'âge du token pour les alertes proactives.
    """
    try:
        from main import live_order_manager
        
        if not live_order_manager:
            return JSONResponse({
                'success': False,
                'message': 'Live trading non initialisé'
            })
        
        # Récupérer le client MEXC bypass
        if hasattr(live_order_manager, 'client') and live_order_manager.client:
            client = live_order_manager.client
            
            # Récupérer le token monitor
            if hasattr(client, '_token_monitor') and client._token_monitor:
                client._token_monitor.reset_token_timer()
                status = client._token_monitor.get_status()
                
                logger.info("✅ Timer token MEXC réinitialisé via API")
                
                return JSONResponse({
                    'success': True,
                    'message': 'Timer token réinitialisé',
                    **status
                })
        
        return JSONResponse({
            'success': False,
            'message': 'Token monitor non disponible'
        })
        
    except Exception as e:
        logger.error(f"Erreur reset timer token: {e}")
        return JSONResponse({'success': False, 'error': str(e)})


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


# ========== DIAGNOSTIC LEVIER ==========

@router.get("/leverage/diagnostic")
async def diagnostic_leverage():
    """
    🔍 Diagnostic complet du levier - Vérifie toutes les sources de config
    
    Returns:
        Dict avec le levier depuis chaque source et celui effectivement utilisé
    """
    try:
        from config import TRADING_CONFIG
        import main
        
        # 1. TRADING_CONFIG (config.py + config_overrides.json)
        trading_config_leverage = TRADING_CONFIG.get('default_leverage', 'NON_DEFINI')
        
        # 2. live_config (config_live_persistent.json)
        live_config = load_live_config()
        live_config_leverage = live_config.get('default_leverage', 'NON_DEFINI')
        
        # 3. config_overrides.json directement
        overrides_leverage = 'NON_DEFINI'
        try:
            from utils.config_persistence import load_config_overrides
            overrides = load_config_overrides()
            overrides_leverage = overrides.get('default_leverage', 'NON_DEFINI')
        except:
            pass
        
        # 4. LiveOrderManager actuel
        live_manager_leverage = 'NON_INITIALISE'
        if hasattr(main, 'live_order_manager') and main.live_order_manager:
            live_manager_leverage = getattr(main.live_order_manager, 'default_leverage', 'NON_DEFINI')
        
        # 5. PositionManager
        position_manager_leverage = 'NON_INITIALISE'
        if hasattr(main, 'position_manager') and main.position_manager:
            if hasattr(main.position_manager, 'live_order_manager') and main.position_manager.live_order_manager:
                position_manager_leverage = getattr(main.position_manager.live_order_manager, 'default_leverage', 'NON_DEFINI')
        
        # Déterminer le levier effectif (celui qui sera réellement utilisé)
        # Ordre de priorité: TRADING_CONFIG (car passé explicitement dans position_manager)
        effective_leverage = trading_config_leverage if trading_config_leverage != 'NON_DEFINI' else 10
        
        # Vérifier la cohérence
        inconsistencies = []
        if trading_config_leverage != live_config_leverage:
            inconsistencies.append(f"TRADING_CONFIG ({trading_config_leverage}) != live_config ({live_config_leverage})")
        if live_manager_leverage != 'NON_INITIALISE' and live_manager_leverage != effective_leverage:
            inconsistencies.append(f"LiveOrderManager ({live_manager_leverage}x) != effective ({effective_leverage}x)")
        
        return {
            'success': True,
            'sources': {
                'TRADING_CONFIG': trading_config_leverage,
                'config_overrides.json': overrides_leverage,
                'config_live_persistent.json': live_config_leverage,
                'LiveOrderManager.default_leverage': live_manager_leverage,
                'PositionManager→LiveOrderManager': position_manager_leverage,
            },
            'effective_leverage': effective_leverage,
            'inconsistencies': inconsistencies,
            'is_consistent': len(inconsistencies) == 0,
            'recommendation': (
                "✅ Cohérent" if len(inconsistencies) == 0 
                else f"⚠️ Incohérence détectée: {'; '.join(inconsistencies)}"
            )
        }
        
    except Exception as e:
        logger.error(f"Erreur diagnostic levier: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@router.post("/leverage/sync")
async def sync_leverage(leverage: int = 1):
    """
    🔄 Synchroniser le levier dans TOUTES les sources de config
    
    Args:
        leverage: Levier souhaité (1-125)
        
    Returns:
        Dict avec le résultat de la synchronisation
    """
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import save_config_overrides, load_config_overrides
        import main
        
        # Borner le levier
        leverage = max(1, min(125, leverage))
        
        updates = []
        
        # 1. Mettre à jour TRADING_CONFIG en mémoire
        TRADING_CONFIG['default_leverage'] = leverage
        updates.append(f"TRADING_CONFIG: {leverage}x")
        
        # 2. Persister dans config_overrides.json
        overrides = load_config_overrides()
        overrides['default_leverage'] = leverage
        save_config_overrides(overrides)
        updates.append(f"config_overrides.json: {leverage}x")
        
        # 3. Mettre à jour config_live_persistent.json
        live_config = load_live_config()
        live_config['default_leverage'] = leverage
        save_live_config(live_config)
        updates.append(f"config_live_persistent.json: {leverage}x")
        
        # 4. Mettre à jour LiveOrderManager si actif
        if hasattr(main, 'live_order_manager') and main.live_order_manager:
            main.live_order_manager.default_leverage = leverage
            updates.append(f"LiveOrderManager.default_leverage: {leverage}x")
        
        logger.info(f"✅ Levier synchronisé à {leverage}x dans toutes les sources")
        
        return {
            'success': True,
            'leverage': leverage,
            'updates': updates,
            'message': f"Levier synchronisé à {leverage}x dans {len(updates)} sources"
        }
        
    except Exception as e:
        logger.error(f"Erreur sync levier: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
