"""
Système de logging pour Trade Cursor
"""
import logging
import sys
from datetime import datetime
from config import DEBUG_ENABLED


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


def setup_logger(name: str = "TradeCursor", level: int = logging.INFO) -> logging.Logger:
    """
    Configure le logger avec formatage et couleurs
    
    Args:
        name: Nom du logger
        level: Niveau de log (INFO, DEBUG, etc.)
        
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
    
    return logger


# Logger global
_logger: logging.Logger = None


def get_logger() -> logging.Logger:
    """Retourne le logger global"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger




