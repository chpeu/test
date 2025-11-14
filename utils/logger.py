"""
Système de logging pour Trade Cursor
"""
import logging
import sys
from datetime import datetime
from config import DEBUG_ENABLED

# 🔥 FIX: Handler personnalisé pour envoyer les logs au frontend
class WebSocketLogHandler(logging.Handler):
    """Handler qui envoie les logs au frontend via WebSocket"""
    
    def __init__(self):
        super().__init__()
        self.ws_manager = None
    
    def set_ws_manager(self, ws_manager):
        """Définir le websocket manager"""
        self.ws_manager = ws_manager
    
    def emit(self, record):
        """Envoyer le log au frontend"""
        try:
            if not self.ws_manager:
                return
            
            # Convertir le niveau de logging en string
            level_map = {
                logging.DEBUG: 'DEBUG',
                logging.INFO: 'INFO',
                logging.WARNING: 'WARNING',
                logging.ERROR: 'ERROR',
                logging.CRITICAL: 'CRITICAL'
            }
            level = level_map.get(record.levelno, 'INFO')
            
            # 🔥 FIX: Formater le message avec le ColoredFormatter pour préserver les couleurs ANSI et emojis
            # Utiliser le formatter pour obtenir les couleurs ANSI
            formatter = ColoredFormatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            formatted_message = formatter.format(record)
            
            # Extraire le message avec couleurs (tout après le timestamp et level)
            # Format: [HH:MM:SS] LEVEL - message
            # On veut garder le message avec ses couleurs ANSI
            message_with_colors = record.getMessage()
            # Ajouter les couleurs ANSI selon le niveau
            color_codes = {
                'DEBUG': '\x1b[36m',      # Cyan
                'INFO': '\x1b[32m',       # Vert
                'WARNING': '\x1b[33m',    # Jaune
                'ERROR': '\x1b[31m',      # Rouge
                'CRITICAL': '\x1b[35m',   # Magenta
            }
            reset_code = '\x1b[0m'
            color = color_codes.get(level, '')
            colored_message = f"{color}{message_with_colors}{reset_code}" if color else message_with_colors
            
            # Créer l'entrée de log
            entry = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'level': level,
                'message': colored_message,  # Message avec couleurs ANSI et emojis préservés
                'detail': '',
                'raw_message': message_with_colors  # Message sans couleur pour recherche
            }
            
            # Envoyer via WebSocket (asynchrone, donc on crée une tâche)
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                async def send_log():
                    await self.ws_manager.emit('log', entry)
                loop.create_task(send_log())
            except RuntimeError:
                # Pas de loop en cours, ignorer
                pass
        except Exception as e:
            # 🔥 FIX: Ne pas bloquer le logging si l'envoi échoue, mais logger l'erreur
            # Utiliser print() au lieu de logger pour éviter les boucles infinies
            import sys
            print(f"⚠️ Erreur envoi log WebSocket: {e}", file=sys.stderr)


class ColoredFormatter(logging.Formatter):
    """Formatter avec couleurs ANSI pour le terminal"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Vert
        'WARNING': '\033[33m',    # Jaune
        'ERROR': '\033[31m',      # Rouge
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(name: str = "TradeCursor", level: int = logging.INFO, ws_manager=None) -> logging.Logger:
    """
    Configure le logger avec formatage et couleurs
    
    Args:
        name: Nom du logger
        level: Niveau de log (INFO, DEBUG, etc.)
        ws_manager: WebSocket manager pour envoyer les logs au frontend (optionnel)
        
    Returns:
        Logger configuré
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
    
    # Éviter les doublons
    if logger.handlers:
        return logger
    
    # Handler pour console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
    
    # Format avec timestamp et couleurs
    formatter = ColoredFormatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # 🔥 FIX: Ajouter handler WebSocket pour envoyer les logs au frontend
    if ws_manager:
        ws_handler = WebSocketLogHandler()
        ws_handler.set_ws_manager(ws_manager)
        ws_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
        logger.addHandler(ws_handler)
    
    return logger


# Logger global
_logger: logging.Logger = None


def get_logger() -> logging.Logger:
    """Retourne le logger global"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger






