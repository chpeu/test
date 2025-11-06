"""
📱 TELEGRAM NOTIFIER - Notifications Telegram
Envoi alertes temps réel via bot Telegram

Fonctionnalités :
- Messages formatés (Markdown)
- Alertes position (ouverture, fermeture, TP partiel)
- Alertes système (erreurs, reconnexion)
- Throttling (éviter spam)
- Emojis pour visibilité
"""

import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import time
from collections import deque

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Notificateur Telegram
    
    Envoie messages via bot Telegram
    """
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: bool = True,
        throttle_seconds: int = 2
    ):
        """
        Initialiser Telegram Notifier
        
        Args:
            bot_token: Token bot Telegram (ex: '123456:ABC-DEF...')
            chat_id: ID chat/channel Telegram
            enabled: Activer notifications
            throttle_seconds: Délai min entre messages (anti-spam)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bot_token and chat_id
        self.throttle_seconds = throttle_seconds
        
        # Throttling
        self.last_message_time = 0
        self.message_queue: deque = deque(maxlen=100)
        
        if self.enabled:
            logger.info(f"📱 Telegram Notifier activé | Chat ID: {chat_id}")
        else:
            logger.warning("⚠️ Telegram Notifier désactivé (token/chat_id manquants)")
    
    async def send_message(
        self,
        message: str,
        parse_mode: str = 'Markdown',
        bypass_throttle: bool = False
    ) -> bool:
        """
        Envoyer message Telegram
        
        Args:
            message: Texte message
            parse_mode: 'Markdown' ou 'HTML'
            bypass_throttle: Ignorer throttling (urgence)
        
        Returns:
            True si envoyé, False sinon
        """
        if not self.enabled:
            logger.debug(f"📱 [TELEGRAM DISABLED] {message}")
            return False
        
        # Throttling
        if not bypass_throttle:
            elapsed = time.time() - self.last_message_time
            if elapsed < self.throttle_seconds:
                logger.debug(f"⏱️ Throttled: attente {self.throttle_seconds - elapsed:.1f}s")
                await asyncio.sleep(self.throttle_seconds - elapsed)
        
        try:
            # Import ici pour éviter dépendance obligatoire
            import aiohttp
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        self.last_message_time = time.time()
                        self.message_queue.append({
                            'message': message,
                            'timestamp': time.time(),
                            'success': True
                        })
                        logger.debug(f"✅ Message Telegram envoyé")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Erreur Telegram API: {response.status} - {error_text}")
                        return False
        
        except ImportError:
            logger.error("❌ aiohttp non installé (requis pour Telegram)")
            self.enabled = False
            return False
        
        except Exception as e:
            logger.error(f"❌ Erreur envoi Telegram: {e}")
            return False
    
    # ==================== ALERTES SPÉCIFIQUES ====================
    
    async def notify_position_opened(self, position_data: Dict):
        """
        Notifier ouverture position
        
        Args:
            position_data: Dict avec symbol, direction, entry, size, tp, sl, etc.
        """
        symbol = position_data.get('symbol', '?')
        direction = position_data.get('direction', '?')
        entry = position_data.get('entry', 0)
        size = position_data.get('size', 0)
        tp = position_data.get('tp', 0)
        sl = position_data.get('sl', 0)
        condition_types = position_data.get('condition_types', [])
        
        # Emoji direction
        emoji = "🟢" if direction == 'LONG' else "🔴"
        
        # Formatage conditions
        conditions_str = ', '.join(condition_types) if condition_types else 'N/A'
        
        message = f"""
{emoji} **POSITION OUVERTE** {emoji}

📊 **Symbole**: `{symbol}`
📈 **Direction**: **{direction}**
💰 **Entry**: `{entry:.6f}`
💵 **Size**: `{size:.2f} USDT`

🎯 **TP**: `{tp:.6f}` (+{((tp - entry) / entry * 100 if direction == 'LONG' else (entry - tp) / entry * 100):.2f}%)
🛡️ **SL**: `{sl:.6f}` ({((sl - entry) / entry * 100 if direction == 'LONG' else (entry - sl) / entry * 100):.2f}%)

🔍 **Conditions**: {conditions_str}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_position_closed(self, position_data: Dict, result: Dict):
        """
        Notifier fermeture position
        
        Args:
            position_data: Données position
            result: Résultat fermeture (exit_reason, pnl_pct, etc.)
        """
        symbol = position_data.get('symbol', '?')
        direction = position_data.get('direction', '?')
        exit_reason = result.get('exit_reason', '?')
        pnl_pct = result.get('pnl_pct', 0)
        pnl_usdt = result.get('pnl_usdt', 0)
        duration = result.get('duration_seconds', 0)
        
        # Emoji résultat
        if pnl_usdt > 0:
            emoji = "✅"
            color = "🟢"
        elif pnl_usdt < 0:
            emoji = "❌"
            color = "🔴"
        else:
            emoji = "➖"
            color = "⚪"
        
        # Formatage durée
        if duration < 60:
            duration_str = f"{int(duration)}s"
        elif duration < 3600:
            duration_str = f"{int(duration/60)}m {int(duration%60)}s"
        else:
            duration_str = f"{int(duration/3600)}h {int((duration%3600)/60)}m"
        
        message = f"""
{emoji} **POSITION FERMÉE** {emoji}

📊 **Symbole**: `{symbol}`
📈 **Direction**: {direction}
🚪 **Raison**: **{exit_reason}**

{color} **PnL**: **{pnl_usdt:+.2f} USDT** ({pnl_pct:+.2f}%)

⏱️ **Durée**: {duration_str}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_tp_escalier_level(self, level_data: Dict):
        """
        Notifier TP Escalier niveau atteint
        
        Args:
            level_data: Données niveau (symbol, level, profit_usdt, etc.)
        """
        symbol = level_data.get('symbol', '?')
        level = level_data.get('level', 0)
        total_levels = level_data.get('total_levels', 0)
        profit_usdt = level_data.get('profit_usdt', 0)
        profit_pct = level_data.get('profit_pct', 0)
        size_remaining_pct = level_data.get('size_remaining_pct', 0)
        
        message = f"""
🎯 **TP ESCALIER Niveau {level}/{total_levels}** 🎯

📊 **Symbole**: `{symbol}`
💰 **Profit Partiel**: **+{profit_usdt:.2f} USDT** (+{profit_pct:.2f}%)
📉 **Restant**: {size_remaining_pct:.0f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_early_invalidation(self, position_data: Dict):
        """
        Notifier early invalidation
        
        Args:
            position_data: Données position
        """
        symbol = position_data.get('symbol', '?')
        direction = position_data.get('direction', '?')
        pnl_pct = position_data.get('pnl_pct', 0)
        
        message = f"""
⚡ **EARLY INVALIDATION** ⚡

📊 **Symbole**: `{symbol}`
📈 **Direction**: {direction}
📉 **PnL**: {pnl_pct:.2f}%

⚠️ Position fermée rapidement (pas de réaction attendue)

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_error(self, error_type: str, details: str):
        """
        Notifier erreur système
        
        Args:
            error_type: Type erreur
            details: Détails
        """
        message = f"""
🚨 **ERREUR SYSTÈME** 🚨

❌ **Type**: {error_type}
📝 **Détails**: {details}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip(), bypass_throttle=True)
    
    async def notify_reconnection(self, service: str):
        """
        Notifier reconnexion service
        
        Args:
            service: Nom service (ex: 'WebSocket', 'MEXC API')
        """
        message = f"""
🔄 **RECONNEXION** 🔄

🔌 **Service**: {service}
✅ **Statut**: Reconnecté avec succès

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_daily_summary(self, stats: Dict):
        """
        Notifier résumé journalier
        
        Args:
            stats: Statistiques journée (total_trades, winrate, pnl_total, etc.)
        """
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        winrate = stats.get('winrate', 0)
        pnl_total = stats.get('pnl_total', 0)
        best_trade = stats.get('best_trade', 0)
        worst_trade = stats.get('worst_trade', 0)
        
        emoji = "📊"
        
        message = f"""
{emoji} **RÉSUMÉ JOURNALIER** {emoji}

📈 **Trades**: {total_trades} ({wins}W / {losses}L)
🎯 **Winrate**: {winrate:.1f}%
💰 **PnL Total**: **{pnl_total:+.2f} USDT**

🏆 **Meilleur**: +{best_trade:.2f} USDT
💔 **Pire**: {worst_trade:.2f} USDT

📅 {datetime.now().strftime('%Y-%m-%d')}
"""
        
        await self.send_message(message.strip())
    
    async def notify_recovery_mode(self, level: int, pause_duration: int):
        """
        Notifier activation recovery mode
        
        Args:
            level: Niveau recovery (1, 2, 3)
            pause_duration: Durée pause (secondes)
        """
        message = f"""
🛡️ **RECOVERY MODE NIVEAU {level}** 🛡️

⏸️ **Pause**: {pause_duration // 60} minutes
⚠️ Trading temporairement suspendu

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message.strip())
    
    def get_stats(self) -> Dict:
        """
        Obtenir statistiques notifications
        
        Returns:
            Dict avec nombre messages envoyés, erreurs, etc.
        """
        successful = sum(1 for msg in self.message_queue if msg['success'])
        
        return {
            'total_messages': len(self.message_queue),
            'successful': successful,
            'failed': len(self.message_queue) - successful,
            'enabled': self.enabled
        }


# ==================== HELPER ====================

def create_telegram_notifier(
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    enabled: bool = True
) -> TelegramNotifier:
    """
    Factory pour créer Telegram Notifier
    
    Args:
        bot_token: Token bot
        chat_id: ID chat
        enabled: Activer
    
    Returns:
        Instance TelegramNotifier
    """
    return TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        enabled=enabled
    )

