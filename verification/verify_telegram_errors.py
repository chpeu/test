#!/usr/bin/env python3
"""
🔥 Script de vérification - Notifications Telegram pour erreurs

Vérifie :
1. Configuration TELEGRAM_NOTIFY_ERROR dans .env
2. NotificationManager charge correctement les settings
3. Les erreurs sont bien notifiées via Telegram
4. Les colonnes scan_logs sont correctement remplies

Usage:
    python verify_telegram_errors.py
"""
import os
import sys
import asyncio
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_env_config():
    """Vérifier la configuration .env"""
    logger.info("=" * 60)
    logger.info("📋 CHECK 1: Configuration .env")
    logger.info("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    checks = {
        'TELEGRAM_ENABLED': os.getenv('TELEGRAM_ENABLED', 'false'),
        'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN', '')[:20] + '...' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NON CONFIGURÉ',
        'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID', 'NON CONFIGURÉ'),
        'TELEGRAM_NOTIFY_ERROR': os.getenv('TELEGRAM_NOTIFY_ERROR', 'true'),
    }
    
    for key, value in checks.items():
        status = "✅" if value and value not in ['NON CONFIGURÉ', 'false'] else "⚠️"
        logger.info(f"  {status} {key}: {value}")
    
    notify_error = os.getenv('TELEGRAM_NOTIFY_ERROR', 'true').lower() == 'true'
    
    if not notify_error:
        logger.warning("⚠️ TELEGRAM_NOTIFY_ERROR est désactivé! Activez-le dans .env")
        return False
    
    return True


def check_notification_manager():
    """Vérifier NotificationManager"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 CHECK 2: NotificationManager")
    logger.info("=" * 60)
    
    try:
        from config import (
            TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED,
            TELEGRAM_NOTIFY_ERROR
        )
        from notifications import create_notification_manager
        
        logger.info(f"  📱 TELEGRAM_ENABLED: {TELEGRAM_ENABLED}")
        logger.info(f"  🚨 TELEGRAM_NOTIFY_ERROR: {TELEGRAM_NOTIFY_ERROR}")
        
        # Créer notification_manager
        notification_manager = create_notification_manager(
            telegram_bot_token=TELEGRAM_BOT_TOKEN if TELEGRAM_ENABLED else None,
            telegram_chat_id=TELEGRAM_CHAT_ID if TELEGRAM_ENABLED else None
        )
        
        # Vérifier settings
        error_enabled = notification_manager.telegram_notify_settings.get('error', False)
        logger.info(f"  🔧 notification_manager.telegram_notify_settings['error']: {error_enabled}")
        
        if not error_enabled:
            logger.error("❌ Les notifications d'erreur sont désactivées dans NotificationManager!")
            return False, None
        
        logger.info("  ✅ NotificationManager configuré correctement")
        return True, notification_manager
        
    except Exception as e:
        logger.error(f"❌ Erreur création NotificationManager: {e}")
        return False, None


async def test_error_notification(notification_manager):
    """Tester l'envoi d'une notification d'erreur"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 CHECK 3: Test envoi notification erreur")
    logger.info("=" * 60)
    
    if not notification_manager:
        logger.error("❌ NotificationManager non disponible")
        return False
    
    if not notification_manager.telegram_notifier:
        logger.warning("⚠️ TelegramNotifier désactivé (token/chat_id manquants)")
        return False
    
    try:
        # Envoyer notification de test
        test_error_type = "Test Validation"
        test_details = f"Ceci est un test de notification d'erreur automatique - {datetime.now().strftime('%H:%M:%S')}"
        
        logger.info(f"  📤 Envoi notification test: {test_error_type}")
        
        await notification_manager.notify('error', {
            'error_type': test_error_type,
            'details': test_details
        }, priority='high')
        
        logger.info("  ✅ Notification envoyée avec succès!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi notification: {e}")
        return False


def check_scan_logs_columns():
    """Vérifier les colonnes vides dans scan_logs"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 CHECK 4: Colonnes scan_logs")
    logger.info("=" * 60)
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        pg_logger = PostgreSQLDataLogger()
        
        if not pg_logger.cursor:
            logger.error("❌ Connexion PostgreSQL impossible")
            return False
        
        # Vérifier les colonnes souvent vides
        query = """
        SELECT 
            COUNT(*) as total,
            COUNT(spread_pct) as spread_pct_filled,
            COUNT(book_depth) as book_depth_filled,
            COUNT(balance_score) as balance_score_filled,
            COUNT(bid_vol) as bid_vol_filled,
            COUNT(ask_vol) as ask_vol_filled,
            COUNT(orderbook_imbalance_ratio) as imbalance_filled
        FROM scan_logs
        WHERE created_at > NOW() - INTERVAL '1 hour'
        """
        
        pg_logger.cursor.execute(query)
        result = pg_logger.cursor.fetchone()
        
        if result:
            total = result[0]
            logger.info(f"  📊 Scans dernière heure: {total}")
            
            if total > 0:
                columns = ['spread_pct', 'book_depth', 'balance_score', 'bid_vol', 'ask_vol', 'orderbook_imbalance_ratio']
                for i, col in enumerate(columns):
                    filled = result[i + 1]
                    pct = (filled / total * 100) if total > 0 else 0
                    status = "✅" if pct > 80 else "⚠️" if pct > 50 else "❌"
                    logger.info(f"  {status} {col}: {filled}/{total} ({pct:.1f}%)")
            else:
                logger.warning("  ⚠️ Aucun scan dans la dernière heure")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification scan_logs: {e}")
        return False


def check_telegram_notify_functions():
    """Vérifier que les fonctions notify_error_telegram existent"""
    logger.info("\n" + "=" * 60)
    logger.info("📋 CHECK 5: Fonctions notify_error_telegram")
    logger.info("=" * 60)
    
    errors = []
    
    # Check main.py
    try:
        # Import dynamique pour vérifier
        import importlib.util
        spec = importlib.util.spec_from_file_location("main_check", "main.py")
        # On ne peut pas exécuter main.py directement, vérifions le code
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
            if "async def notify_error_telegram" in content:
                logger.info("  ✅ main.py: notify_error_telegram définie")
            else:
                logger.error("  ❌ main.py: notify_error_telegram MANQUANTE")
                errors.append("main.py")
            
            if "await notify_error_telegram" in content:
                logger.info("  ✅ main.py: notify_error_telegram appelée")
            else:
                logger.warning("  ⚠️ main.py: notify_error_telegram pas appelée")
    except Exception as e:
        logger.error(f"  ❌ Erreur vérification main.py: {e}")
        errors.append("main.py")
    
    # Check scanner_loop.py
    try:
        with open("core/callbacks/scanner_loop.py", "r", encoding="utf-8") as f:
            content = f.read()
            if "async def notify_error_telegram" in content:
                logger.info("  ✅ scanner_loop.py: notify_error_telegram définie")
            else:
                logger.error("  ❌ scanner_loop.py: notify_error_telegram MANQUANTE")
                errors.append("scanner_loop.py")
            
            if "await notify_error_telegram" in content:
                logger.info("  ✅ scanner_loop.py: notify_error_telegram appelée")
            else:
                logger.warning("  ⚠️ scanner_loop.py: notify_error_telegram pas appelée")
    except Exception as e:
        logger.error(f"  ❌ Erreur vérification scanner_loop.py: {e}")
        errors.append("scanner_loop.py")
    
    return len(errors) == 0


async def main():
    """Exécuter toutes les vérifications"""
    logger.info("🔥 VÉRIFICATION NOTIFICATIONS TELEGRAM POUR ERREURS")
    logger.info("=" * 60)
    
    results = {}
    
    # Check 1: Configuration .env
    results['env_config'] = check_env_config()
    
    # Check 2: NotificationManager
    nm_ok, notification_manager = check_notification_manager()
    results['notification_manager'] = nm_ok
    
    # Check 3: Test envoi (seulement si NM ok)
    if nm_ok and notification_manager:
        results['test_send'] = await test_error_notification(notification_manager)
    else:
        results['test_send'] = False
        logger.warning("⏭️ Test envoi skippé (NotificationManager non disponible)")
    
    # Check 4: Colonnes scan_logs
    results['scan_logs'] = check_scan_logs_columns()
    
    # Check 5: Fonctions notify_error_telegram
    results['functions'] = check_telegram_notify_functions()
    
    # Résumé
    logger.info("\n" + "=" * 60)
    logger.info("📊 RÉSUMÉ")
    logger.info("=" * 60)
    
    all_passed = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {status}: {check}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("✅ TOUTES LES VÉRIFICATIONS PASSÉES!")
    else:
        logger.warning("⚠️ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
