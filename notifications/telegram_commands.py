"""
📱 TELEGRAM COMMANDS - Gestionnaire de commandes Telegram
Gère les commandes reçues via webhook Telegram

Commandes disponibles :
- /stats : Statistiques de la session
- /report : Rapport détaillé (trades, winrate, PnL)
- /status : État actuel (position active, scanner)
- /trades : Derniers 10 trades
- /help : Liste des commandes disponibles
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TelegramCommandHandler:
    """
    Gestionnaire de commandes Telegram
    
    Parse et exécute les commandes reçues via webhook
    """
    
    def __init__(
        self,
        analytics_db=None,
        position_manager=None,
        notification_manager=None,
        instance_port: int = 5000
    ):
        """
        Initialiser gestionnaire de commandes
        
        Args:
            analytics_db: Instance AnalyticsDatabase
            position_manager: Instance PositionManager
            notification_manager: Instance NotificationManager
            instance_port: Port instance (pour identifier l'instance)
        """
        self.analytics_db = analytics_db
        self.position_manager = position_manager
        self.notification_manager = notification_manager
        self.instance_port = instance_port
        
        # Commandes disponibles
        self.commands = {
            '/stats': self.handle_stats,
            '/report': self.handle_report,
            '/status': self.handle_status,
            '/trades': self.handle_trades,
            '/help': self.handle_help,
            '/start': self.handle_help,  # Alias pour /help
        }
    
    async def handle_command(self, command: str, chat_id: int) -> str:
        """
        Gérer une commande reçue
        
        Args:
            command: Commande (ex: '/stats', '/report')
            chat_id: ID chat Telegram
        
        Returns:
            Message de réponse
        """
        # Nettoyer la commande (enlever @botname si présent)
        command = command.split('@')[0].strip().lower()
        
        # Trouver le handler
        handler = self.commands.get(command)
        if not handler:
            return f"❌ Commande inconnue : `{command}`\n\nUtilisez `/help` pour voir les commandes disponibles."
        
        try:
            # Exécuter le handler
            response = await handler(chat_id)
            return response
        except Exception as e:
            logger.error(f"❌ Erreur exécution commande {command}: {e}")
            return f"❌ Erreur lors de l'exécution de la commande : {str(e)}"
    
    async def handle_stats(self, chat_id: int) -> str:
        """
        Commande /stats : Statistiques de la session
        
        Returns:
            Message avec statistiques
        """
        if not self.analytics_db:
            return "❌ Analytics DB non disponible"
        
        try:
            # Récupérer tous les trades
            trades = self.analytics_db.get_trades(limit=10000)
            
            if not trades:
                return f"📊 **STATISTIQUES** [Instance {self.instance_port}]\n\nAucun trade pour le moment."
            
            # Calculer stats
            total_trades = len(trades)
            wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0)
            losses = total_trades - wins
            winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            total_pnl_usdt = sum(t.get('net_pnl_usdt', 0) for t in trades)
            total_pnl_pct = sum(t.get('net_pnl_pct', 0) for t in trades)
            
            # Meilleur/pire trade
            best_trade = max((t.get('net_pnl_usdt', 0) for t in trades), default=0)
            worst_trade = min((t.get('net_pnl_usdt', 0) for t in trades), default=0)
            
            # Trades aujourd'hui
            today = datetime.now().date()
            today_trades = [
                t for t in trades
                if t.get('date') == today.strftime('%Y-%m-%d')
            ]
            today_count = len(today_trades)
            today_pnl = sum(t.get('net_pnl_usdt', 0) for t in today_trades)
            
            message = f"""
📊 **STATISTIQUES** [Instance {self.instance_port}]

📈 **Total Trades**: {total_trades}
✅ **Wins**: {wins}
❌ **Losses**: {losses}
🎯 **Winrate**: {winrate:.1f}%

💰 **PnL Total**: {total_pnl_usdt:+.2f} USDT ({total_pnl_pct:+.2f}%)

🏆 **Meilleur Trade**: +{best_trade:.2f} USDT
💔 **Pire Trade**: {worst_trade:.2f} USDT

📅 **Aujourd'hui**: {today_count} trades | {today_pnl:+.2f} USDT

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            return message.strip()
        
        except Exception as e:
            logger.error(f"❌ Erreur calcul stats: {e}")
            return f"❌ Erreur calcul statistiques : {str(e)}"
    
    async def handle_report(self, chat_id: int) -> str:
        """
        Commande /report : Rapport détaillé
        
        Returns:
            Message avec rapport détaillé
        """
        if not self.analytics_db:
            return "❌ Analytics DB non disponible"
        
        try:
            # Récupérer tous les trades
            trades = self.analytics_db.get_trades(limit=10000)
            
            if not trades:
                return f"📊 **RAPPORT DÉTAILLÉ** [Instance {self.instance_port}]\n\nAucun trade pour le moment."
            
            # Calculer stats globales
            total_trades = len(trades)
            wins = sum(1 for t in trades if t.get('net_pnl_usdt', 0) > 0)
            losses = total_trades - wins
            winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            total_pnl_usdt = sum(t.get('net_pnl_usdt', 0) for t in trades)
            total_pnl_pct = sum(t.get('net_pnl_pct', 0) for t in trades)
            
            # Stats par direction
            long_trades = [t for t in trades if t.get('direction') == 'LONG']
            short_trades = [t for t in trades if t.get('direction') == 'SHORT']
            
            long_pnl = sum(t.get('net_pnl_usdt', 0) for t in long_trades)
            short_pnl = sum(t.get('net_pnl_usdt', 0) for t in short_trades)
            
            # Stats par raison de fermeture
            reasons = {}
            for t in trades:
                reason = t.get('reason', 'UNKNOWN')
                if reason not in reasons:
                    reasons[reason] = {'count': 0, 'pnl': 0}
                reasons[reason]['count'] += 1
                reasons[reason]['pnl'] += t.get('net_pnl_usdt', 0)
            
            # Top 5 raisons
            top_reasons = sorted(reasons.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
            
            # Durée moyenne
            durations = [t.get('duration_seconds', 0) for t in trades if t.get('duration_seconds')]
            avg_duration = sum(durations) / len(durations) if durations else 0
            avg_duration_str = f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s" if avg_duration > 0 else "N/A"
            
            message = f"""
📊 **RAPPORT DÉTAILLÉ** [Instance {self.instance_port}]

📈 **GLOBAL**
• Trades: {total_trades} ({wins}W / {losses}L)
• Winrate: {winrate:.1f}%
• PnL Total: {total_pnl_usdt:+.2f} USDT ({total_pnl_pct:+.2f}%)
• Durée moyenne: {avg_duration_str}

📊 **PAR DIRECTION**
• LONG: {len(long_trades)} trades | {long_pnl:+.2f} USDT
• SHORT: {len(short_trades)} trades | {short_pnl:+.2f} USDT

🎯 **TOP 5 RAISONS DE FERMETURE**
"""
            for reason, data in top_reasons:
                reason_emoji = {
                    'TP': '🎯',
                    'SL': '🛑',
                    'TS': '📈',
                    'EARLY_INVALIDATION': '⚡',
                    'TIMEOUT': '⏱️',
                    'MANUAL': '👤'
                }.get(reason, '❓')
                message += f"• {reason_emoji} {reason}: {data['count']} trades | {data['pnl']:+.2f} USDT\n"
            
            message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"❌ Erreur génération rapport: {e}")
            return f"❌ Erreur génération rapport : {str(e)}"
    
    async def handle_status(self, chat_id: int) -> str:
        """
        Commande /status : État actuel
        
        Returns:
            Message avec état actuel
        """
        try:
            # Position active
            active_position = None
            if self.position_manager and hasattr(self.position_manager, 'active_position') and self.position_manager.active_position:
                pos = self.position_manager.active_position
                active_position = {
                    'symbol': pos.symbol,
                    'direction': pos.direction,
                    'entry': pos.entry,
                    'tp': pos.tp,
                    'sl': pos.sl,
                    'size': pos.size,
                    'start_time': pos.start_time
                }
            
            # Scanner status (si disponible)
            scanner_status = "❓ Inconnu"
            # Note: Le scanner n'est pas directement accessible depuis ici
            # On pourrait l'injecter si nécessaire
            
            message = f"""
📡 **STATUT** [Instance {self.instance_port}]

"""
            
            if active_position:
                duration = datetime.now().timestamp() - active_position['start_time']
                duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
                
                message += f"""🟢 **POSITION ACTIVE**
• Symbole: `{active_position['symbol']}`
• Direction: {active_position['direction']}
• Entry: {active_position['entry']:.6f}
• TP: {active_position['tp']:.6f}
• SL: {active_position['sl']:.6f}
• Size: {active_position['size']:.2f} USDT
• Durée: {duration_str}

"""
            else:
                message += "⚪ **Aucune position active**\n\n"
            
            message += f"""🔍 **Scanner**: {scanner_status}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"❌ Erreur récupération statut: {e}")
            return f"❌ Erreur récupération statut : {str(e)}"
    
    async def handle_trades(self, chat_id: int) -> str:
        """
        Commande /trades : Derniers 10 trades
        
        Returns:
            Message avec derniers trades
        """
        if not self.analytics_db:
            return "❌ Analytics DB non disponible"
        
        try:
            # Récupérer les 10 derniers trades
            trades = self.analytics_db.get_trades(limit=10)
            
            if not trades:
                return f"📋 **DERNIERS TRADES** [Instance {self.instance_port}]\n\nAucun trade pour le moment."
            
            message = f"""
📋 **DERNIERS 10 TRADES** [Instance {self.instance_port}]

"""
            
            for i, trade in enumerate(trades[:10], 1):
                symbol = trade.get('symbol', '?')
                direction = trade.get('direction', '?')
                reason = trade.get('reason', 'UNKNOWN')
                pnl_usdt = trade.get('net_pnl_usdt', 0)
                pnl_pct = trade.get('net_pnl_pct', 0)
                date = trade.get('date', '?')
                time = trade.get('time', '?')
                
                # Emoji selon résultat
                emoji = "✅" if pnl_usdt > 0 else "❌" if pnl_usdt < 0 else "➖"
                
                # Emoji raison
                reason_emoji = {
                    'TP': '🎯',
                    'SL': '🛑',
                    'TS': '📈',
                    'EARLY_INVALIDATION': '⚡',
                    'TIMEOUT': '⏱️',
                    'MANUAL': '👤'
                }.get(reason, '❓')
                
                message += f"""{i}. {emoji} {symbol} {direction}
   {reason_emoji} {reason} | {pnl_usdt:+.2f} USDT ({pnl_pct:+.2f}%)
   📅 {date} {time}

"""
            
            message += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            
            return message.strip()
        
        except Exception as e:
            logger.error(f"❌ Erreur récupération trades: {e}")
            return f"❌ Erreur récupération trades : {str(e)}"
    
    async def handle_help(self, chat_id: int) -> str:
        """
        Commande /help : Liste des commandes
        
        Returns:
            Message avec liste des commandes
        """
        message = f"""
📱 **COMMANDES DISPONIBLES** [Instance {self.instance_port}]

/help - Afficher cette aide
/stats - Statistiques de la session
/report - Rapport détaillé (trades, winrate, PnL)
/status - État actuel (position active, scanner)
/trades - Derniers 10 trades

💡 **Exemple**: Envoyez `/stats` pour voir les statistiques

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        return message.strip()


def create_telegram_command_handler(
    analytics_db=None,
    position_manager=None,
    notification_manager=None,
    instance_port: int = 5000
) -> TelegramCommandHandler:
    """
    Factory pour créer Telegram Command Handler
    
    Args:
        analytics_db: Instance AnalyticsDatabase
        position_manager: Instance PositionManager
        notification_manager: Instance NotificationManager
        instance_port: Port instance
    
    Returns:
        Instance TelegramCommandHandler
    """
    return TelegramCommandHandler(
        analytics_db=analytics_db,
        position_manager=position_manager,
        notification_manager=notification_manager,
        instance_port=instance_port
    )

