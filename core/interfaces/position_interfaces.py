"""
Interfaces pour le Position Manager refactorisé
Permet l'injection de dépendances et la testabilité
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class PositionStatus(Enum):
    """Statuts possibles d'une position"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class ValidationResult:
    """Résultat de validation d'une position"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @classmethod
    def success(cls, warnings: List[str] = None) -> 'ValidationResult':
        return cls(True, [], warnings or [])
    
    @classmethod
    def error(cls, errors: List[str], warnings: List[str] = None) -> 'ValidationResult':
        return cls(False, errors, warnings or [])


@dataclass
class PositionSize:
    """Taille calculée d'une position"""
    base_size: float
    adjusted_size: float
    final_size: float
    risk_percentage: float
    stop_loss_distance: float
    take_profit_distance: float
    
    @property
    def is_valid(self) -> bool:
        return (self.final_size > 0 and 
                self.risk_percentage > 0 and 
                self.stop_loss_distance > 0)


@dataclass
class PositionConfig:
    """Configuration pour calculs de position"""
    default_risk: float = 2.0
    max_position_size: float = 1000.0
    min_position_size: float = 10.0
    max_risk_per_trade: float = 5.0
    emergency_stop_loss: float = 10.0


class IPositionCalculator(ABC):
    """Interface pour calculateur de positions"""
    
    @abstractmethod
    def calculate_size(self, setup: Dict[str, Any], capital: float) -> PositionSize:
        """
        Calcule la taille d'une position
        
        Args:
            setup: Configuration du trade (symbol, scores, etc.)
            capital: Capital disponible
            
        Returns:
            PositionSize: Taille calculée avec détails
        """
        pass
    
    @abstractmethod
    def calculate_stop_loss(self, setup: Dict[str, Any], position_size: float) -> float:
        """Calcule le niveau de stop loss"""
        pass
    
    @abstractmethod
    def calculate_take_profit(self, setup: Dict[str, Any], position_size: float) -> float:
        """Calcule le niveau de take profit"""
        pass


class IPositionValidator(ABC):
    """Interface pour validation de positions"""
    
    @abstractmethod
    def validate_setup(self, setup: Dict[str, Any]) -> ValidationResult:
        """
        Valide la configuration d'un trade
        
        Args:
            setup: Configuration à valider
            
        Returns:
            ValidationResult: Résultat de la validation
        """
        pass
    
    @abstractmethod
    def validate_market_conditions(self, symbol: str) -> ValidationResult:
        """Valide les conditions de marché pour un symbol"""
        pass
    
    @abstractmethod
    def validate_risk_parameters(self, position_size: PositionSize, capital: float) -> ValidationResult:
        """Valide les paramètres de risque"""
        pass


class IPositionExecutor(ABC):
    """Interface pour exécution de positions"""
    
    @abstractmethod
    async def open_position(self, setup: Dict[str, Any], position_size: PositionSize) -> Dict[str, Any]:
        """
        Ouvre une position sur le marché
        
        Args:
            setup: Configuration du trade
            position_size: Taille calculée
            
        Returns:
            Dict avec détails de l'exécution
        """
        pass
    
    @abstractmethod
    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Ferme une position"""
        pass
    
    @abstractmethod
    async def update_position(self, position_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Met à jour une position existante"""
        pass


class IPositionRepository(ABC):
    """Interface pour persistance des positions"""
    
    @abstractmethod
    def save_position(self, position_data: Dict[str, Any]) -> str:
        """
        Sauvegarde une position en base
        
        Returns:
            str: ID de la position sauvegardée
        """
        pass
    
    @abstractmethod
    def get_position(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une position par son ID"""
        pass
    
    @abstractmethod
    def update_position_status(self, position_id: str, status: PositionStatus) -> bool:
        """Met à jour le statut d'une position"""
        pass
    
    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Récupère toutes les positions ouvertes"""
        pass


class IPositionOrchestrator(ABC):
    """Interface principale pour orchestration des positions"""
    
    @abstractmethod
    async def process_trade_request(self, setup: Dict[str, Any], capital: float) -> Dict[str, Any]:
        """
        Traite une demande de trade complète
        
        Args:
            setup: Configuration du trade
            capital: Capital disponible
            
        Returns:
            Dict avec résultat du traitement
        """
        pass
    
    @abstractmethod
    async def close_all_positions(self) -> Dict[str, Any]:
        """Ferme toutes les positions ouvertes"""
        pass
    
    @abstractmethod
    def get_positions_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des positions"""
        pass
