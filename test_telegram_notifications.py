#!/usr/bin/env python3
"""
Test de vérification des notifications Telegram
Vérifie que les paramètres sont bien chargés et que notification_manager est configuré
"""
import os
import sys

def test_telegram_config():
    """Vérifier la configuration Telegram depuis .env"""
    print("=" * 70)
    print("TEST CONFIGURATION TELEGRAM")
    print("=" * 70)

    # Charger les variables d'environnement depuis .env
    from dotenv import load_dotenv
    load_dotenv()

    # Vérifier les credentials
    print("\n1. CREDENTIALS TELEGRAM:")
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
    telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'

    print(f"   - TELEGRAM_BOT_TOKEN: {'OK Configure' if telegram_token else 'XX Manquant'}")
    print(f"   - TELEGRAM_CHAT_ID: {'OK Configure' if telegram_chat_id else 'XX Manquant'}")
    print(f"   - TELEGRAM_ENABLED: {'OK Active' if telegram_enabled else 'XX Desactive'}")

    # Vérifier les types de notifications
    print("\n2. TYPES DE NOTIFICATIONS (depuis .env):")
    notification_types = {
        'Position Ouverte': 'TELEGRAM_NOTIFY_POSITION_OPENED',
        'Position Fermée': 'TELEGRAM_NOTIFY_POSITION_CLOSED',
        'TP Escalier': 'TELEGRAM_NOTIFY_TP_ESCALIER',
        'Invalidation Précoce': 'TELEGRAM_NOTIFY_EARLY_INVALIDATION',
        'Erreurs': 'TELEGRAM_NOTIFY_ERROR',
        'Reconnexion': 'TELEGRAM_NOTIFY_RECONNECTION',
        'Résumé Quotidien': 'TELEGRAM_NOTIFY_DAILY_SUMMARY',
        'Mode Recovery': 'TELEGRAM_NOTIFY_RECOVERY_MODE',
        'Setup Rejeté': 'TELEGRAM_NOTIFY_SETUP_REJECTED'
    }

    for label, env_key in notification_types.items():
        value = os.getenv(env_key, 'true').lower() == 'true'
        status = 'OK Active' if value else 'XX Desactive'
        print(f"   - {label:25s}: {status}")

    # Charger config.py pour vérifier
    print("\n3. VERIFICATION CONFIG.PY:")
    try:
        from config import (
            TELEGRAM_ENABLED as cfg_enabled,
            TELEGRAM_NOTIFY_POSITION_OPENED,
            TELEGRAM_NOTIFY_POSITION_CLOSED,
            TELEGRAM_NOTIFY_TP_ESCALIER
        )
        print(f"   - config.TELEGRAM_ENABLED: {cfg_enabled}")
        print(f"   - config.TELEGRAM_NOTIFY_POSITION_OPENED: {TELEGRAM_NOTIFY_POSITION_OPENED}")
        print(f"   - config.TELEGRAM_NOTIFY_POSITION_CLOSED: {TELEGRAM_NOTIFY_POSITION_CLOSED}")
        print(f"   - config.TELEGRAM_NOTIFY_TP_ESCALIER: {TELEGRAM_NOTIFY_TP_ESCALIER}")
    except Exception as e:
        print(f"   ❌ Erreur import config: {e}")

    # Vérifier NotificationManager
    print("\n4. VERIFICATION NOTIFICATION_MANAGER:")
    try:
        from notifications.notification_manager import create_notification_manager
        from config import (
            TELEGRAM_BOT_TOKEN as cfg_token,
            TELEGRAM_CHAT_ID as cfg_chat_id,
            TELEGRAM_NOTIFY_POSITION_OPENED,
            TELEGRAM_NOTIFY_POSITION_CLOSED,
            TELEGRAM_NOTIFY_TP_ESCALIER,
            TELEGRAM_NOTIFY_EARLY_INVALIDATION,
            TELEGRAM_NOTIFY_ERROR,
            TELEGRAM_NOTIFY_RECONNECTION,
            TELEGRAM_NOTIFY_DAILY_SUMMARY,
            TELEGRAM_NOTIFY_RECOVERY_MODE,
            TELEGRAM_NOTIFY_SETUP_REJECTED
        )

        telegram_notify_settings = {
            'position_opened': TELEGRAM_NOTIFY_POSITION_OPENED,
            'position_closed': TELEGRAM_NOTIFY_POSITION_CLOSED,
            'tp_escalier_level': TELEGRAM_NOTIFY_TP_ESCALIER,
            'early_invalidation': TELEGRAM_NOTIFY_EARLY_INVALIDATION,
            'error': TELEGRAM_NOTIFY_ERROR,
            'reconnection': TELEGRAM_NOTIFY_RECONNECTION,
            'daily_summary': TELEGRAM_NOTIFY_DAILY_SUMMARY,
            'recovery_mode': TELEGRAM_NOTIFY_RECOVERY_MODE,
            'setup_rejected': TELEGRAM_NOTIFY_SETUP_REJECTED
        }

        notification_manager = create_notification_manager(
            telegram_bot_token=cfg_token if telegram_enabled else None,
            telegram_chat_id=cfg_chat_id if telegram_enabled else None,
            telegram_notify_settings=telegram_notify_settings
        )

        print(f"   - NotificationManager cree: OK")
        print(f"   - TelegramNotifier: {'OK Active' if notification_manager.telegram_notifier else 'XX Desactive'}")
        print(f"   - Settings: {notification_manager.telegram_notify_settings}")

    except Exception as e:
        print(f"   XX Erreur creation NotificationManager: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("RÉSULTAT:")
    print("=" * 70)

    if telegram_enabled and telegram_token and telegram_chat_id:
        print("OK Configuration Telegram VALIDE")
        print("   Les notifications seront envoyees selon les types actives")
    elif telegram_token and telegram_chat_id:
        print("!! Telegram configure mais DESACTIVE")
        print("   Activez TELEGRAM_ENABLED=true dans .env pour recevoir les notifications")
    else:
        print("XX Configuration Telegram INCOMPLETE")
        print("   Ajoutez TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans .env")

    print("=" * 70)

if __name__ == "__main__":
    test_telegram_config()
