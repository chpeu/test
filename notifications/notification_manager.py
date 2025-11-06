"""
📢 NOTIFICATION MANAGER - Gestionnaire centralisé notifications
Agrège et envoie notifications via multiples canaux

Fonctionnalités :
- Multi-canaux (Telegram, SocketIO, Email, etc.)
- Agrégation intelligente (éviter spam)
- Priorités (info, warning, error, critical)
- Batching (grouper messages similaires)
- Historique
"""

import asyncio
import logging
from typing import Optional, Dict, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time

from notifications.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Gestionnaire centralisé notifications
    
    Envoie via multiples canaux avec agrégation
    """
    
    def __init__(
        self,
        telegram_notifier: Optional[TelegramNotifier] = None,
        socketio_callback: Optional[Callable] = None,
        enable_batching: bool = True,
        batch_interval: int = 5
    ):
        """
        Initialiser Notification Manager
        
        Args:
            telegram_notifier: Instance TelegramNotifier
            socketio_callback: Callback SocketIO (async func)
            enable_batching: Activer batching
            batch_interval: Intervalle batch (secondes)
        """
        self.telegram_notifier = telegram_notifier
        self.socketio_callback = socketio_callback
        self.enable_batching = enable_batching
        self.batch_interval = batch_interval
        
        # Historique
        self.notification_history: deque = deque(maxlen=1000)
        
        # Batching
        self.pending_batches: Dict[str, List[Dict]] = defaultdict(list)
        self.last_batch_send: Dict[str, float] = defaultdict(float)
        
        # Stats
        self.stats = {
            'total_sent': 0,
            'telegram_sent': 0,
            'socketio_sent': 0,
            'batched': 0
        }
        
        logger.info(f"📢 Notification Manager initialisé | Batching: {enable_batching}")
    
    async def notify(
        self,
        event_type: str,
        data: Dict,
        priority: str = 'info',
        channels: Optional[List[str]] = None
    ):
        """
        Envoyer notification
        
        Args:
            event_type: Type événement ('position_opened', 'position_closed', etc.)
            data: Données événement
            priority: 'info', 'warning', 'error', 'critical'
            channels: Canaux spécifiques (['telegram', 'socketio']) ou None=tous
        """
        # Enregistrer historique
        notification = {
            'event_type': event_type,
            'data': data,
            'priority': priority,
            'timestamp': time.time()
        }
        self.notification_history.append(notification)
        
        # Déterminer canaux
        if channels is None:
            channels = ['telegram', 'socketio']
        
        # Batching si activé et priorité basse
        if self.enable_batching and priority == 'info' and event_type in ['setup_rejected']:
            await self._add_to_batch(event_type, data, channels)
            return
        
        # Envoi immédiat
        await self._send_notification(event_type, data, priority, channels)
    
    async def _send_notification(
        self,
        event_type: str,
        data: Dict,
        priority: str,
        channels: List[str]
    ):
        """Envoyer notification vers canaux"""
        
        # Telegram
        if 'telegram' in channels and self.telegram_notifier:
            await self._send_telegram(event_type, data, priority)
        
        # SocketIO
        if 'socketio' in channels and self.socketio_callback:
            await self._send_socketio(event_type, data)
        
        self.stats['total_sent'] += 1
    
    async def _send_telegram(self, event_type: str, data: Dict, priority: str):
        """Envoyer vers Telegram"""
        try:
            if event_type == 'position_opened':
                await self.telegram_notifier.notify_position_opened(data)
            
            elif event_type == 'position_closed':
                result = data.get('result', {})
                await self.telegram_notifier.notify_position_closed(data, result)
            
            elif event_type == 'tp_escalier_level':
                await self.telegram_notifier.notify_tp_escalier_level(data)
            
            elif event_type == 'early_invalidation':
                await self.telegram_notifier.notify_early_invalidation(data)
            
            elif event_type == 'error':
                error_type = data.get('error_type', 'Unknown')
                details = data.get('details', 'No details')
                await self.telegram_notifier.notify_error(error_type, details)
            
            elif event_type == 'reconnection':
                service = data.get('service', 'Unknown')
                await self.telegram_notifier.notify_reconnection(service)
            
            elif event_type == 'daily_summary':
                stats = data.get('stats', {})
                await self.telegram_notifier.notify_daily_summary(stats)
            
            elif event_type == 'recovery_mode':
                level = data.get('level', 1)
                pause_duration = data.get('pause_duration', 0)
                await self.telegram_notifier.notify_recovery_mode(level, pause_duration)
            
            else:
                # Message générique
                await self.telegram_notifier.send_message(
                    f"📢 **{event_type}**\n\n{data}"
                )
            
            self.stats['telegram_sent'] += 1
        
        except Exception as e:
            logger.error(f"❌ Erreur envoi Telegram: {e}")
    
    async def _send_socketio(self, event_type: str, data: Dict):
        """Envoyer vers SocketIO"""
        try:
            if self.socketio_callback:
                await self.socketio_callback(event_type, data)
            
            self.stats['socketio_sent'] += 1
        
        except Exception as e:
            logger.error(f"❌ Erreur envoi SocketIO: {e}")
    
    async def _add_to_batch(self, event_type: str, data: Dict, channels: List[str]):
        """Ajouter notification au batch"""
        self.pending_batches[event_type].append({
            'data': data,
            'channels': channels,
            'timestamp': time.time()
        })
        
        # Vérifier si batch doit être envoyé
        elapsed = time.time() - self.last_batch_send[event_type]
        if elapsed >= self.batch_interval:
            await self._flush_batch(event_type)
    
    async def _flush_batch(self, event_type: str):
        """Envoyer batch groupé"""
        if event_type not in self.pending_batches or not self.pending_batches[event_type]:
            return
        
        batch = self.pending_batches[event_type]
        count = len(batch)
        
        # Créer message agrégé
        if event_type == 'setup_rejected':
            # Compter raisons rejet
            rejection_counts = defaultdict(int)
            symbols = set()
            
            for item in batch:
                data = item['data']
                rejection_reason = data.get('rejection_reason', 'Unknown')
                rejection_counts[rejection_reason] += 1
                symbols.add(data.get('symbol', '?'))
            
            # Message Telegram groupé
            if self.telegram_notifier:
                message = f"""
📊 **SETUPS REJETÉS** ({count})

"""
                for reason, count_reason in rejection_counts.items():
                    message += f"• {reason}: {count_reason}\n"
                
                message += f"\n📈 **Symboles**: {', '.join(list(symbols)[:5])}"
                if len(symbols) > 5:
                    message += f" +{len(symbols)-5} autres"
                
                message += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
                
                await self.telegram_notifier.send_message(message.strip())
                self.stats['telegram_sent'] += 1
        
        # Clear batch
        self.pending_batches[event_type] = []
        self.last_batch_send[event_type] = time.time()
        self.stats['batched'] += count
        
        logger.info(f"📦 Batch envoyé: {event_type} ({count} items)")
    
    async def flush_all_batches(self):
        """Envoyer tous les batchs en attente"""
        for event_type in list(self.pending_batches.keys()):
            await self._flush_batch(event_type)
    
    def get_stats(self) -> Dict:
        """
        Obtenir statistiques
        
        Returns:
            Dict avec stats notifications
        """
        return {
            **self.stats,
            'history_size': len(self.notification_history),
            'pending_batches': {
                event_type: len(batch)
                for event_type, batch in self.pending_batches.items()
            }
        }
    
    def get_recent_notifications(self, limit: int = 100) -> List[Dict]:
        """
        Obtenir notifications récentes
        
        Args:
            limit: Nombre max
        
        Returns:
            Liste notifications
        """
        return list(self.notification_history)[-limit:]


# ==================== HELPER ====================

def create_notification_manager(
    telegram_bot_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    socketio_callback: Optional[Callable] = None,
    enable_batching: bool = True
) -> NotificationManager:
    """
    Factory pour créer Notification Manager
    
    Args:
        telegram_bot_token: Token bot Telegram
        telegram_chat_id: ID chat Telegram
        socketio_callback: Callback SocketIO
        enable_batching: Activer batching
    
    Returns:
        Instance NotificationManager
    """
    # Créer Telegram Notifier si credentials fournis
    telegram_notifier = None
    if telegram_bot_token and telegram_chat_id:
        from notifications.telegram_notifier import create_telegram_notifier
        # 🔥 FIX: TelegramNotifier accepte maintenant str ou int directement
        telegram_notifier = create_telegram_notifier(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,  # Peut être str ou int, TelegramNotifier gère les deux
            enabled=True
        )
    
    return NotificationManager(
        telegram_notifier=telegram_notifier,
        socketio_callback=socketio_callback,
        enable_batching=enable_batching
    )

