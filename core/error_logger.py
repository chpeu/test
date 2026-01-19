"""
Error Logger - Intercepte et log les erreurs vers PostgreSQL
Trade Cursor v7.0
"""

import logging
import traceback
from typing import Optional, Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)


def log_error_to_db(
    error_type: str,
    error_message: str,
    error_stack: Optional[str] = None,
    symbol: Optional[str] = None,
    context: Optional[Dict] = None
):
    """
    Logger une erreur dans la table scan_errors via PostgreSQL DataLogger
    
    Args:
        error_type: Type d'erreur (ERROR, CRITICAL, WARNING)
        error_message: Message d'erreur
        error_stack: Stack trace complète
        symbol: Symbole concerné (optionnel)
        context: Contexte additionnel (optionnel)
    """
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_datalogger = get_pg_datalogger()
        
        if pg_datalogger and pg_datalogger.enabled:
            pg_datalogger.log_error(
                error_type=error_type,
                error_message=error_message,
                error_stack=error_stack,
                symbol=symbol,
                scan_context=context
            )
    except Exception as e:
        logger.debug(f"Impossible de logger l'erreur vers DB: {e}")


def with_error_logging(error_type: str = "ERROR", symbol_arg: Optional[str] = None):
    """
    Décorateur pour logger automatiquement les erreurs vers scan_errors
    
    Args:
        error_type: Type d'erreur (ERROR, CRITICAL, WARNING)
        symbol_arg: Nom de l'argument contenant le symbole (ex: 'symbol')
    
    Usage:
        @with_error_logging(error_type="CRITICAL", symbol_arg="symbol")
        def my_function(symbol: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extraire le symbole si spécifié
                symbol = None
                if symbol_arg:
                    # Chercher dans kwargs
                    symbol = kwargs.get(symbol_arg)
                    # Si pas trouvé, chercher dans args via signature
                    if not symbol and args:
                        try:
                            import inspect
                            sig = inspect.signature(func)
                            params = list(sig.parameters.keys())
                            if symbol_arg in params:
                                idx = params.index(symbol_arg)
                                if idx < len(args):
                                    symbol = args[idx]
                        except:
                            pass
                
                # Logger vers DB
                log_error_to_db(
                    error_type=error_type,
                    error_message=str(e),
                    error_stack=traceback.format_exc(),
                    symbol=symbol,
                    context={'function': func.__name__}
                )
                
                # Re-raise l'exception
                raise
        
        return wrapper
    return decorator


class ErrorLoggerHandler(logging.Handler):
    """
    Handler logging.Handler personnalisé qui envoie les erreurs vers scan_errors
    
    Usage:
        import logging
        from core.error_logger import ErrorLoggerHandler
        
        logger = logging.getLogger(__name__)
        logger.addHandler(ErrorLoggerHandler(level=logging.ERROR))
    """
    
    def __init__(self, level=logging.ERROR):
        super().__init__(level=level)
    
    def emit(self, record: logging.LogRecord):
        """Appelé à chaque log >= level"""
        try:
            # Mapper les niveaux Python vers nos types
            level_map = {
                logging.CRITICAL: 'CRITICAL',
                logging.ERROR: 'ERROR',
                logging.WARNING: 'WARNING'
            }
            
            error_type = level_map.get(record.levelno, 'ERROR')
            
            # Extraire le symbole du message si présent (format: "BTCUSDT: error...")
            symbol = None
            msg = record.getMessage()
            if ':' in msg and '/' in msg.split(':')[0]:
                potential_symbol = msg.split(':')[0].strip()
                if 'USDT' in potential_symbol:
                    symbol = potential_symbol
            
            # Stack trace si disponible
            error_stack = None
            if record.exc_info:
                error_stack = ''.join(traceback.format_exception(*record.exc_info))
            
            # Contexte
            context = {
                'logger': record.name,
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Logger vers DB
            log_error_to_db(
                error_type=error_type,
                error_message=msg,
                error_stack=error_stack,
                symbol=symbol,
                context=context
            )
            
        except Exception:
            # Ne pas crasher si le logging échoue
            self.handleError(record)
