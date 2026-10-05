"""
Routes API pour les notifications (Telegram, etc.)
"""
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def send_notification(message: str, level: str = "info"):
    """Compatibilité tests: envoi simplifié (sync)."""
    if not message:
        return False
    return {
        "success": True,
        "level": level,
        "message": message,
    }

@router.post("/telegram/config")
async def api_update_telegram_config(request: Request):
    """Mettre à jour la configuration Telegram"""
    try:
        params = await request.json()
        updated = await perform_telegram_config_update(params)
        return JSONResponse({'updated': updated, 'success': True})
    except Exception as e:
        logger.error(f"Erreur mise à jour Telegram: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

@router.post("/telegram/test")
async def api_test_telegram():
    """Envoyer un message de test Telegram"""
    try:
        result = await perform_telegram_test()
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Erreur test Telegram: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)

async def perform_telegram_config_update(params: dict) -> dict:
    """Logique centrale pour mettre à jour Telegram"""
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    notify_types = {
        'TELEGRAM_NOTIFY_POSITION_OPENED': 'TELEGRAM_NOTIFY_POSITION_OPENED',
        'TELEGRAM_NOTIFY_POSITION_CLOSED': 'TELEGRAM_NOTIFY_POSITION_CLOSED',
        'TELEGRAM_NOTIFY_TP_ESCALIER': 'TELEGRAM_NOTIFY_TP_ESCALIER',
        'TELEGRAM_NOTIFY_EARLY_INVALIDATION': 'TELEGRAM_NOTIFY_EARLY_INVALIDATION',
        'TELEGRAM_NOTIFY_ERROR': 'TELEGRAM_NOTIFY_ERROR',
        'TELEGRAM_NOTIFY_RECONNECTION': 'TELEGRAM_NOTIFY_RECONNECTION',
        'TELEGRAM_NOTIFY_DAILY_SUMMARY': 'TELEGRAM_NOTIFY_DAILY_SUMMARY',
        'TELEGRAM_NOTIFY_RECOVERY_MODE': 'TELEGRAM_NOTIFY_RECOVERY_MODE',
        'TELEGRAM_NOTIFY_SETUP_REJECTED': 'TELEGRAM_NOTIFY_SETUP_REJECTED'
    }
    
    updated = {}
    for key, env_key in notify_types.items():
        if key in params:
            value = bool(params[key])
            os.environ[env_key] = 'true' if value else 'false'
            updated[key] = value

    notif_mgr = state.get_notification_manager()
    if notif_mgr:
        notif_mgr.telegram_notify_settings.update({
            'position_opened': bool(params.get('TELEGRAM_NOTIFY_POSITION_OPENED', True)),
            'position_closed': bool(params.get('TELEGRAM_NOTIFY_POSITION_CLOSED', True)),
            'tp_escalier_level': bool(params.get('TELEGRAM_NOTIFY_TP_ESCALIER', True)),
            'early_invalidation': bool(params.get('TELEGRAM_NOTIFY_EARLY_INVALIDATION', True)),
            'error': bool(params.get('TELEGRAM_NOTIFY_ERROR', True)),
            'reconnection': bool(params.get('TELEGRAM_NOTIFY_RECONNECTION', True)),
            'daily_summary': bool(params.get('TELEGRAM_NOTIFY_DAILY_SUMMARY', False)),
            'recovery_mode': bool(params.get('TELEGRAM_NOTIFY_RECOVERY_MODE', True)),
            'setup_rejected': bool(params.get('TELEGRAM_NOTIFY_SETUP_REJECTED', False))
        })

    # Persistance .env
    try:
        env_file = Path('.env')
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            updated_lines = []
            env_keys_updated = set()
            for line in lines:
                line_stripped = line.strip()
                updated_line = False
                for key, env_key in notify_types.items():
                    if line_stripped.startswith(f'{env_key}='):
                        if key in params:
                            value = bool(params[key])
                            updated_lines.append(f'{env_key}={"true" if value else "false"}\n')
                            env_keys_updated.add(env_key)
                            updated_line = True
                            break
                if not updated_line:
                    updated_lines.append(line)

            for key, env_key in notify_types.items():
                if env_key not in env_keys_updated and key in params:
                    value = bool(params[key])
                    updated_lines.append(f'{env_key}={"true" if value else "false"}\n')

            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
    except Exception as e:
        logger.error(f"Erreur sauvegarde .env: {e}")

    return updated

async def perform_telegram_test() -> dict:
    """Logique centrale pour tester Telegram"""
    from core.state_manager import get_state_manager
    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED
    
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {'success': False, 'error': 'Telegram non configuré (vérifiez .env)'}
    
    state = get_state_manager()
    notif_mgr = state.get_notification_manager()
    if notif_mgr and notif_mgr.telegram_notifier:
        test_message = "🧪 **Test de notification Telegram**\n\nCe message confirme que votre configuration Telegram fonctionne correctement ! ✅"
        success = await notif_mgr.telegram_notifier.send_message(test_message)
        if success:
            return {'success': True, 'message': 'Message de test envoyé avec succès'}
        return {'success': False, 'error': "Erreur lors de l'envoi du message"}
    return {'success': False, 'error': 'Notification manager non disponible'}
