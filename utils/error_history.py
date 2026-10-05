"""
Gestionnaire d'historique des erreurs persistant
Stockage en mémoire avec reset au redémarrage du backend
"""
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import json

@dataclass
class ErrorEntry:
    """Entrée d'erreur avec métadonnées"""
    timestamp: str
    level: str
    message: str
    detail: str = ""
    raw_message: str = ""
    id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour sérialisation"""
        return asdict(self)

class ErrorHistoryManager:
    """Gestionnaire d'historique des erreurs persistant"""
    
    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self.errors: List[ErrorEntry] = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
    def add_error(self, level: str, message: str, detail: str = "", raw_message: str = ""):
        """Ajouter une erreur à l'historique"""
        with self.lock:
            entry = ErrorEntry(
                timestamp=datetime.now().strftime('%H:%M:%S'),
                level=level,
                message=message,
                detail=detail,
                raw_message=raw_message or message,
                id=f"{datetime.now().timestamp()}-{len(self.errors)}"
            )
            
            self.errors.append(entry)
            
            # Limiter le nombre d'erreurs en mémoire
            if len(self.errors) > self.max_errors:
                self.errors = self.errors[-self.max_errors:]
                
    def get_errors(self, limit: int = None) -> List[Dict[str, Any]]:
        """Récupérer les erreurs (les plus récentes en premier)"""
        with self.lock:
            errors = self.errors.copy()
            errors.reverse()  # Plus récentes en premier
            
            if limit:
                errors = errors[:limit]
                
            return [error.to_dict() for error in errors]
    
    def get_error_count(self) -> int:
        """Récupérer le nombre total d'erreurs"""
        with self.lock:
            return len(self.errors)
            
    def clear_errors(self):
        """Vider l'historique des erreurs"""
        with self.lock:
            self.errors.clear()
            self.logger.info("🗑️ Historique des erreurs vidé")
            
    def get_recent_errors(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les erreurs récentes pour le frontend"""
        return self.get_errors(limit=limit)

# Instance globale
_error_history = None

def get_error_history() -> ErrorHistoryManager:
    """Récupérer l'instance globale du gestionnaire d'erreurs"""
    global _error_history
    if _error_history is None:
        _error_history = ErrorHistoryManager()
    return _error_history

def reset_error_history():
    """Reset de l'historique des erreurs (au redémarrage)"""
    global _error_history
    _error_history = ErrorHistoryManager()
    logging.getLogger(__name__).info("🔄 Historique des erreurs réinitialisé")
