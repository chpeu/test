"""
Système de logging pour Trade Cursor
"""
import asyncio
import contextlib
import logging
import sys
import os
import weakref
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config import DEBUG_ENABLED


_ws_log_handlers = weakref.WeakSet()

# Quiet mode globals
QUIET_MODE = False
QUIET_MODE_LOGGERS = (
    "api.routes.websocket",
    "core.websocket_manager",
    "core.callbacks.scanner_loop",
)
QUIET_MODE_TAGS = (
    "[WS-DEBUG]",
    "[WS-PING]",
    "[WS-STATUS]",
    "[WS-COMMAND]",
    "[DEBUG-SCAN]",
    "[WEBSOCKET-PONG",
    "[WEBSOCKET-FIX]",
    "[WEBSOCKET-MONITOR]",
)
_quiet_mode_prev_levels = {}


class QuietModeFilter(logging.Filter):
    """Filtre global pour réduire la verbosité quand quiet mode est actif."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not QUIET_MODE:
            return True
        if record.levelno >= logging.WARNING:
            return True
        try:
            message = record.getMessage()
        except Exception:
            message = ""
        if message and any(tag in message for tag in QUIET_MODE_TAGS):
            return False
        if any(record.name.startswith(prefix) for prefix in QUIET_MODE_LOGGERS):
            return False
        return True


_quiet_mode_filter = QuietModeFilter()


def _install_quiet_mode_filter(target_logger: logging.Logger) -> None:
    if _quiet_mode_filter not in target_logger.filters:
        target_logger.addFilter(_quiet_mode_filter)
    for handler in target_logger.handlers:
        if _quiet_mode_filter not in handler.filters:
            handler.addFilter(_quiet_mode_filter)


def _apply_quiet_logger_levels(enabled: bool) -> None:
    for logger_name in QUIET_MODE_LOGGERS:
        target = logging.getLogger(logger_name)
        if enabled:
            if logger_name not in _quiet_mode_prev_levels:
                _quiet_mode_prev_levels[logger_name] = target.level
            target.setLevel(logging.WARNING)
        else:
            if logger_name in _quiet_mode_prev_levels:
                target.setLevel(_quiet_mode_prev_levels.pop(logger_name))


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler sécurisé pour Windows qui gère les PermissionError"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rollover_failed = False
        self._last_rollover_attempt = 0
        self._rollover_retry_delay = 3600  # Retry après 1h si rotation échoue
    
    def doRollover(self):
        """Rotation sécurisée qui ne crash pas sur PermissionError"""
        try:
            # Marquer qu'on tente une rotation
            self._last_rollover_attempt = time.time()
            
            # Essayer la rotation standard
            super().doRollover()
            
            # Si succès, reset le flag d'échec
            self._rollover_failed = False
            
        except (PermissionError, OSError) as e:
            # Si rotation échoue, marquer l'échec et continuer à logger
            self._rollover_failed = True
            
            # Log l'erreur vers stderr pour éviter les boucles
            print(f"⚠️ Rotation logs échouée (continuant sans rotation): {e}", 
                  file=sys.stderr, flush=True)
            
            # Le fichier existant continuera à être utilisé
            # Pas de crash, juste pas de rotation
        except Exception as e:
            # Autres erreurs inattendues
            self._rollover_failed = True
            print(f"🔴 Erreur rotation logs inattendue: {e}", 
                  file=sys.stderr, flush=True)
    
    def shouldRollover(self, record):
        """Décider si rotation est nécessaire, en tenant compte des échecs précédents"""
        # Si rotation a échoué récemment, ne pas réessayer immédiatement
        if (self._rollover_failed and 
            time.time() - self._last_rollover_attempt < self._rollover_retry_delay):
            return False
        
        # Sinon, utiliser la logique standard
        return super().shouldRollover(record)


class _NonClosingStreamHandler(logging.StreamHandler):
    def close(self):
        try:
            self.flush()
        except Exception:
            pass
        logging.Handler.close(self)


# 🔥 FIX: Handler personnalisé pour envoyer les logs au frontend
class WebSocketLogHandler(logging.Handler):
    """Handler qui envoie les logs au frontend via WebSocket"""
    
    def __init__(self):
        super().__init__()
        self.ws_manager = None
        self._tasks = set()
        self._closing = False
        self._max_in_flight_tasks = 200
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

            if len(self._tasks) >= self._max_in_flight_tasks:
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
            if sys.stdout is sys.__stdout__ and hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if sys.stderr is sys.__stderr__ and hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    global logger
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG if DEBUG_ENABLED else level)

    for handler in list(log.handlers):
        try:
            log.removeHandler(handler)
            handler.close()
        except Exception:
            pass
    
    # Handler pour console
    console_handler = _NonClosingStreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
    
    # Format avec timestamp et couleurs
    formatter = ColoredFormatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    log.addHandler(console_handler)
    
    # 🔥 NOUVEAU: File handler pour sauvegarder les logs WARNING/ERROR/CRITICAL
    if log_to_file:
        try:
            # Créer le dossier logs/ s'il n'existe pas
            log_dir = 'logs'
            os.makedirs(log_dir, exist_ok=True)
            
            # 🔥 FIX Windows: Utilisez RotatingFileHandler avec gestion robuste des erreurs
            # TimedRotatingFileHandler cause des PermissionError sur Windows
            file_handler = SafeRotatingFileHandler(
                os.path.join(log_dir, 'app.log'),
                maxBytes=10*1024*1024,  # 10 MB par fichier
                backupCount=5,          # Garder 5 fichiers de backup
                encoding='utf-8',
                delay=True              # 🔥 KEY: delay=True évite la création immédiate
            )
            
            file_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else logging.INFO)
            
            # Format sans couleurs ANSI pour fichier
            file_formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)

            if isinstance(file_handler, logging.Handler):
                log.addHandler(file_handler)
            log.info(f"✅ File logging activé: {os.path.join(log_dir, 'app.log')} (niveau WARNING+)")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'activer file logging: {e}")
    
    # 🔥 FIX: Ajouter handler WebSocket pour envoyer les logs au frontend
    if ws_manager:
        ws_handler = WebSocketLogHandler()
        ws_handler.set_ws_manager(ws_manager)
        ws_handler.setLevel(logging.DEBUG if DEBUG_ENABLED else level)
        if isinstance(ws_handler, logging.Handler):
            log.addHandler(ws_handler)

    _install_quiet_mode_filter(log)
    
    logger = log
    return log


async def drain_websocket_log_handlers(timeout: float = 1.0) -> None:
    for handler in list(_ws_log_handlers):
        try:
            await handler.drain(timeout=timeout)
        except Exception:
            pass


# Logger global
_logger: logging.Logger = None


# Exposé pour patching dans les tests
logger: logging.Logger = logging.getLogger("TradeCursor")


def get_logger() -> logging.Logger:
    """Retourne le logger global"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def apply_quiet_mode(enabled: bool) -> None:
    """Activer/désactiver le quiet mode pour les logs."""
    global QUIET_MODE
    QUIET_MODE = bool(enabled)
    _install_quiet_mode_filter(logging.getLogger())
    _install_quiet_mode_filter(logging.getLogger("TradeCursor"))
    _apply_quiet_logger_levels(QUIET_MODE)


def is_quiet_mode() -> bool:
    return QUIET_MODE






