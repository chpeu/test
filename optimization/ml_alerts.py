"""
ML Alerts - Système d'alertes pour prédictions ML à haute confiance
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MLAlertManager:
    """Gestionnaire d'alertes pour prédictions ML"""
    
    def __init__(self):
        self.alert_history = []
        
    def should_alert(
        self,
        prediction: Dict,
        min_confidence: float = 0.7,
        prediction_type: str = 'win'
    ) -> bool:
        """
        Déterminer si une alerte doit être envoyée
        
        Args:
            prediction: Résultat de prédiction
            min_confidence: Confiance minimale
            prediction_type: Type de prédiction à alerter ('win' ou 'all')
            
        Returns:
            True si alerte doit être envoyée
        """
        confidence = prediction.get('confidence', 0)
        pred_type = prediction.get('prediction')
        
        # Vérifier confiance
        if confidence < min_confidence:
            return False
        
        # Vérifier type
        if prediction_type == 'win' and pred_type != 'win':
            return False
        
        return True
    
    def format_alert_message(
        self,
        prediction: Dict,
        symbol: str,
        scan_id: Optional[int] = None
    ) -> str:
        """
        Formater message d'alerte
        
        Args:
            prediction: Résultat de prédiction
            symbol: Symbole
            scan_id: ID du scan
            
        Returns:
            Message formaté
        """
        pred_type = prediction.get('prediction', 'unknown')
        confidence = prediction.get('confidence', 0)
        win_prob = prediction.get('win_probability', 0)
        model = prediction.get('model_name', 'unknown')
        
        # Emoji selon prédiction
        emoji = "🚀" if pred_type == 'win' else "⚠️"
        
        # Top features
        top_features = prediction.get('top_features', [])
        features_str = ""
        if top_features and len(top_features) > 0:
            features_str = "\n📊 Top Features:\n"
            for i, feat in enumerate(top_features[:3], 1):
                features_str += f"  {i}. {feat['feature']}\n"
        
        message = f"""
{emoji} **Alerte ML - {pred_type.upper()}**

📈 **Symbole**: {symbol}
🎯 **Prédiction**: {pred_type.upper()}
💯 **Confiance**: {confidence:.1%}
📊 **Probabilité Win**: {win_prob:.1%}
🤖 **Modèle**: {model}
{features_str}
⏰ **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        if scan_id:
            message += f"🔍 **Scan ID**: {scan_id}\n"
        
        return message.strip()
    
    def send_alert(
        self,
        prediction: Dict,
        symbol: str,
        scan_id: Optional[int] = None,
        channels: list = None
    ) -> Dict:
        """
        Envoyer alerte sur les canaux configurés
        
        Args:
            prediction: Résultat de prédiction
            symbol: Symbole
            scan_id: ID du scan
            channels: Liste des canaux ('console', 'webhook', 'notification_service')
            
        Returns:
            Dict avec résultats d'envoi
        """
        if channels is None:
            channels = ['console']  # Par défaut, juste console
        
        message = self.format_alert_message(prediction, symbol, scan_id)
        
        results = {}
        
        # Console
        if 'console' in channels:
            logger.info(f"\n{'='*60}\n{message}\n{'='*60}")
            results['console'] = {'status': 'success'}
        
        # Webhook (pour Discord, Telegram, etc.)
        if 'webhook' in channels:
            webhook_result = self._send_webhook(message, prediction, symbol)
            results['webhook'] = webhook_result
        
        # Service de notifications interne
        if 'notification_service' in channels:
            notif_result = self._send_notification(message, prediction, symbol, scan_id)
            results['notification_service'] = notif_result
        
        # Historique
        self.alert_history.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'prediction': prediction.get('prediction'),
            'confidence': prediction.get('confidence'),
            'channels': channels,
            'results': results
        })
        
        return {
            'status': 'success',
            'message': 'Alerte envoyée',
            'channels': results
        }
    
    def _send_webhook(self, message: str, prediction: Dict, symbol: str) -> Dict:
        """
        Envoyer via webhook (Discord, Telegram, etc.)
        
        Note: À implémenter selon vos besoins
        """
        try:
            import os
            webhook_url = os.getenv('ML_ALERT_WEBHOOK_URL')
            
            if not webhook_url:
                logger.warning("⚠️ ML_ALERT_WEBHOOK_URL non configuré")
                return {'status': 'skipped', 'reason': 'no_webhook_url'}
            
            # TODO: Implémenter envoi webhook selon votre service
            # Exemple pour Discord:
            # import requests
            # requests.post(webhook_url, json={'content': message})
            
            logger.info(f"📤 Webhook alerte envoyée (simulé)")
            return {'status': 'success', 'message': 'Webhook envoyé'}
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi webhook: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _send_notification(
        self,
        message: str,
        prediction: Dict,
        symbol: str,
        scan_id: Optional[int]
    ) -> Dict:
        """
        Envoyer via le service de notifications interne
        """
        try:
            from services.notification_service import NotificationService
            
            notif_service = NotificationService()
            
            # Créer notification
            notif_service.create_notification(
                type='ml_alert',
                title=f"Alerte ML - {prediction.get('prediction', '').upper()}",
                message=message,
                priority='high' if prediction.get('confidence', 0) >= 0.8 else 'medium',
                metadata={
                    'symbol': symbol,
                    'prediction': prediction.get('prediction'),
                    'confidence': prediction.get('confidence'),
                    'win_probability': prediction.get('win_probability'),
                    'scan_id': scan_id,
                    'prediction_id': prediction.get('prediction_id')
                }
            )
            
            logger.info(f"🔔 Notification interne créée pour {symbol}")
            return {'status': 'success', 'message': 'Notification créée'}
            
        except ImportError:
            logger.warning("⚠️ NotificationService non disponible")
            return {'status': 'skipped', 'reason': 'service_not_available'}
        except Exception as e:
            logger.error(f"❌ Erreur envoi notification: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_alert_history(self, limit: int = 20) -> list:
        """Récupérer historique des alertes"""
        return self.alert_history[-limit:]
    
    def clear_history(self):
        """Vider l'historique"""
        self.alert_history = []


# Singleton
_alert_manager: Optional[MLAlertManager] = None


def get_alert_manager() -> MLAlertManager:
    """Récupérer instance singleton du gestionnaire d'alertes"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = MLAlertManager()
    return _alert_manager


def send_ml_alert(
    prediction: Dict,
    symbol: str,
    scan_id: Optional[int] = None,
    min_confidence: float = 0.7,
    channels: list = None
) -> Optional[Dict]:
    """
    Helper pour envoyer une alerte ML si critères remplis
    
    Args:
        prediction: Résultat de prédiction
        symbol: Symbole
        scan_id: ID du scan
        min_confidence: Confiance minimale
        channels: Canaux d'envoi
        
    Returns:
        Résultat d'envoi ou None si pas d'alerte
    """
    manager = get_alert_manager()
    
    # Vérifier si alerte nécessaire
    if not manager.should_alert(prediction, min_confidence):
        return None
    
    # Envoyer alerte
    return manager.send_alert(prediction, symbol, scan_id, channels)
