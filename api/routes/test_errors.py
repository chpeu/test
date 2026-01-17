"""
Route de test pour générer des erreurs fictives
Utile pour tester le système d'historique des erreurs
"""
from fastapi import APIRouter, Query
import logging
import random
from datetime import datetime

logger = logging.getLogger(__name__)
test_errors_router = APIRouter()

# Messages d'erreur fictifs pour les tests
FAKE_ERROR_MESSAGES = [
    "🚨 Connexion MEXC échouée: TimeoutError",
    "❌ Erreur calcul position: Division par zéro",
    "⚠️ Prix WebSocket invalide pour BTC/USDT",
    "🔴 Échec ouverture position: Fonds insuffisants", 
    "💥 Erreur ML prédiction: Model non chargé",
    "🚫 API rate limit dépassé: 429 Too Many Requests",
    "⛔ Erreur parsing JSON: Malformed response",
    "🔥 Exception non gérée dans scanner_loop",
    "❗ PostgreSQL connexion perdue: Connection refused",
    "🚨 Stop Loss non exécuté: Order rejected"
]

FAKE_CRITICAL_MESSAGES = [
    "💀 CRITIQUE: Perte totale du capital détectée",
    "🔴 CRITIQUE: Multiple positions ouvertes simultanément", 
    "💥 CRITIQUE: Système de trading arrêté d'urgence",
    "⚠️ CRITIQUE: Base de données corrompue détectée"
]

@test_errors_router.post("/generate")
def generate_test_errors(
    count: int = Query(5, description="Nombre d'erreurs à générer", ge=1, le=20),
    include_critical: bool = Query(True, description="Inclure des erreurs CRITICAL")
):
    """Générer des erreurs fictives pour tester l'historique"""
    try:
        generated_errors = []
        
        for i in range(count):
            # 20% de chance d'avoir une erreur CRITICAL si activé
            if include_critical and random.random() < 0.2:
                level = logging.CRITICAL
                message = random.choice(FAKE_CRITICAL_MESSAGES)
                level_name = "CRITICAL"
            else:
                level = logging.ERROR
                message = random.choice(FAKE_ERROR_MESSAGES)
                level_name = "ERROR"
            
            # Ajouter numéro et timestamp pour éviter la duplication
            timestamp = datetime.now().strftime('%H:%M:%S')
            full_message = f"{message} (Test #{i+1} - {timestamp})"
            
            # Logger l'erreur (sera automatiquement capturée par WebSocketLogHandler)
            if level == logging.CRITICAL:
                logger.critical(full_message)
            else:
                logger.error(full_message)
            
            generated_errors.append({
                'level': level_name,
                'message': full_message,
                'timestamp': timestamp
            })
        
        return {
            'success': True,
            'message': f'{count} erreurs de test générées',
            'generated_errors': generated_errors
        }
        
    except Exception as e:
        logger.error(f"Erreur génération erreurs de test: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@test_errors_router.post("/stress-test")  
def stress_test_errors(
    batches: int = Query(3, description="Nombre de lots d'erreurs", ge=1, le=10),
    batch_size: int = Query(10, description="Taille de chaque lot", ge=5, le=50)
):
    """Test de charge avec beaucoup d'erreurs pour tester le scroll infini"""
    try:
        total_generated = 0
        
        for batch in range(batches):
            for i in range(batch_size):
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Millisecondes
                message = f"🚨 Erreur stress test - Lot {batch+1}/{batches} - #{i+1}/{batch_size} ({timestamp})"
                
                # Alterner ERROR et CRITICAL
                if i % 4 == 0:
                    logger.critical(f"💀 CRITICAL: {message}")
                else:
                    logger.error(f"❌ ERROR: {message}")
                
                total_generated += 1
        
        return {
            'success': True,
            'message': f'Test de charge terminé: {total_generated} erreurs générées',
            'batches': batches,
            'batch_size': batch_size,
            'total_errors': total_generated
        }
        
    except Exception as e:
        logger.error(f"Erreur stress test: {e}")
        return {
            'success': False,
            'error': str(e)
        }
