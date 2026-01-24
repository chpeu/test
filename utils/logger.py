"""
Système de logging pour Trade Cursor
"""
import asyncio
import contextlib
import logging
import sys
import os
import weakref
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config import DEBUG_ENABLED


_ws_log_handlers = weakref.WeakSet()


# 🔥 FIX: Handler personnalisé pour envoyer les logs au frontend
class WebSocketLogHandler(logging.Handler):
    """Handler qui envoie les logs au frontend via WebSocket"""
    
    def __init__(self):
        super().__init__()
        self.ws_manager = None
        self._tasks = set()
        self._closing = False
        _ws_log_handlers.add(self)
    
    def set_ws_manager(self, ws_manager):
        """Définir le websocket manager"""
        self.ws_manager = ws_manager

    async def drain(self, timeout: float = 1.0) -> None:
        self._closing = True
        tasks = [t for t in list(self._tasks) if not t.done()]
        if not tasks:
            self._tasks.clear()
            return

        done, pending = await asyncio.wait(tasks, timeout=timeout)
        for task in pending:
            task.cancel()
        if pending:
            with contextlib.suppress(Exception):
                await asyncio.gather(*pending, return_exceptions=True)

        self._tasks.difference_update(done)
        self._tasks.difference_update(pending)

    def close(self):
        self._closing = True
        for task in list(self._tasks):
            try:
                if not task.done():
                    task.cancel()
            except Exception:
                pass
        self._tasks.clear()
        super().close()
    
    def emit(self, record):
        """Envoyer le log au frontend et stocker les erreurs de façon persistante"""
        try:
            if not self.ws_manager:
                return

            if self._closing:
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
            
            # 🔥 NEW: Stocker les erreurs de façon persistante
            if level in ['ERROR', 'CRITICAL']:
                try:
                    from utils.error_history import get_error_history
                    error_history = get_error_history()
                    message_with_colors = record.getMessage()
                    error_history.add_error(
                        level=level,
                        message=message_with_colors,
                        raw_message=message_with_colors
                    )
                except Exception as e:
                    print(f"⚠️ Erreur sauvegarde erreur: {e}", file=sys.stderr)
            
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
            
            # Envoyer via WebSocket (asynchrone, fire-and-forget)
            # 🔥 FIX: Utiliser call_soon_threadsafe avec une coroutine simplifiée
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                
                # Vérifier que le loop est actif et pas en shutdown
                if not loop.is_running() or loop.is_closed():
                    return
                
                # Vérifier si shutdown est en cours via le module shutdown
                try:
                    from core.shutdown import get_shutdown_manager
                    shutdown_mgr = get_shutdown_manager()
                    if shutdown_mgr and shutdown_mgr.is_shutting_down:
                        return  # Ne pas créer de nouvelles tasks pendant shutdown
                except Exception:
                    pass  # Module non disponible, continuer
                
                # Utiliser ensure_future avec une coroutine simple sans gather
                async def send_log_direct():
                    try:
                        # Appel direct via ws_manager.emit pour cohérence de format
                        if self.ws_manager:
                            await asyncio.wait_for(self.ws_manager.emit('log', entry), timeout=1.0)
                    except asyncio.CancelledError:
                        pass  # Normal pendant shutdown
                    except asyncio.TimeoutError:
                        pass  # Timeout, ignorer
                    except Exception:
                        pass  # Ignorer toutes les erreurs
                
                # Créer la tâche avec un nom pour le debugging
                task = loop.create_task(send_log_direct(), name=f"websocket_log_{id(entry)}")

                # Meilleure gestion du cleanup des tâches
                def cleanup_task(t):
                    try:
                        self._tasks.discard(t)
                        if not t.cancelled():
                            exc = t.exception()
                            if exc and not isinstance(exc, (asyncio.CancelledError, asyncio.TimeoutError)):
                                # Ne pas logger ici pour éviter les boucles infinies
                                pass
                    except Exception:
                        pass

                self._tasks.add(task)
                task.add_done_callback(cleanup_task)
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


def setup_logger(name: str = "TradeCursor", level: int = logging.INFO, ws_manager=None, log_to_file: bool = True) -> logging.Logger:
    """
    Configure le logger avec formatage et couleurs
    
    Args:
        name: Nom du logger
        level: Niveau de log (INFO, DEBUG, etc.)
        ws_manager: WebSocket manager pour envoyer les logs au frontend (optionnel)
        log_to_file: Si True, sauvegarde les logs WARNING+ dans logs/app.log (défaut: True)
        
    Returns:
        Logger configuré
    """
    try:
        if os.name == 'nt':
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    
    # 🔥 NOUVEAU: File handler pour sauvegarder les logs WARNING/ERROR/CRITICAL
    if log_to_file:
        try:
            # Créer le dossier logs/ s'il n'existe pas
            log_dir = 'logs'
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # 🔥 FIX Windows: TimedRotatingFileHandler au lieu de RotatingFileHandler
            # pour éviter PermissionError: [WinError 32] sur Windows
            from logging.handlers import TimedRotatingFileHandler
            file_handler = TimedRotatingFileHandler(
                os.path.join(log_dir, 'app.log'),
                when='midnight',  # Rotation quotidienne à minuit
                interval=1,       # Tous les jours
                backupCount=7,    # Garder 7 jours d'historique
                encoding='utf-8',
                utc=False        # Utiliser l'heure locale
            )
            
            # 🎯 Niveau WARNING+ uniquement (optimisé pour production)
            # 🔥 DEBUG TEMPORAIRE: Passer à DEBUG pour diagnostiquer WebSocket
            file_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else logging.INFO)
            
            # Format sans couleurs ANSI pour fichier
            file_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            
            logger.addHandler(file_handler)
            logger.info(f"✅ File logging activé: {os.path.join(log_dir, 'app.log')} (niveau WARNING+)")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'activer file logging: {e}")
    
    # 🔥 FIX: Ajouter handler WebSocket pour envoyer les logs au frontend
    if ws_manager:
        ws_handler = WebSocketLogHandler()
        ws_handler.set_ws_manager(ws_manager)
        ws_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
        logger.addHandler(ws_handler)
    
    return logger


async def drain_websocket_log_handlers(timeout: float = 1.0) -> None:
    for handler in list(_ws_log_handlers):
        try:
            await handler.drain(timeout=timeout)
        except Exception:
            pass


# Logger global
_logger: logging.Logger = None


def get_logger() -> logging.Logger:
    """Retourne le logger global"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger






