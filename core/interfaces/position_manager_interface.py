#!/usr/bin/env python3
"""
Interface IPositionManager - Trade Cursor v7.0
Interface pour refactorisation sécurisée du PositionManager
ZÉRO RISQUE - Code existant inchangé, interface créée à côté
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class PositionSetup:
    """Setup standardisé pour position"""
    symbol: str
    direction: str  # 'LONG' ou 'SHORT'
    entry_price: float
    sl_price: float
    tp_price: float
    atr: float
    score: float
    risk_per_trade: float
    loss_streak: int = 0
    win_streak: int = 0


@dataclass
class PositionResult:
    """Résultat standardisé d'ouverture position"""
    success: bool
    position_size: float
    message: str
    position_id: Optional[str] = None
    error_code: Optional[str] = None


class IPositionManager(ABC):
    """
    Interface pour PositionManager - Permet tests sans dépendances
    
    Cette interface définit les méthodes critiques du PositionManager
    sans toucher au code existant. Permet injection de dépendances
    et testabilité complète.
    """
    
    @abstractmethod
    def calculate_position_size(self, setup: PositionSetup, capital: float) -> float:
        """
        Calculer taille position selon setup et capital
        
        Args:
            setup: Configuration position (entry, sl, tp, etc.)
            capital: Capital disponible
            
        Returns:
            float: Taille position calculée
        """
        pass
        
    @abstractmethod
    def open_position(self, setup: PositionSetup) -> PositionResult:
        """
        Ouvrir position selon setup
        
        Args:
            setup: Configuration position complète
            
        Returns:
            PositionResult: Résultat ouverture avec détails
        """
        pass
        
    @abstractmethod
    def close_position(self, position_id: str, reason: str = "Manual") -> bool:
        """
        Fermer position active
        
        Args:
            position_id: ID position à fermer
            reason: Raison fermeture
            
        Returns:
            bool: True si fermeture réussie
        """
        pass
        
    @abstractmethod
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """
        Obtenir positions actives
        
        Returns:
            List[Dict]: Liste positions avec détails
        """
        pass
        
    @abstractmethod
    def get_recovery_state(self, loss_streak: int) -> Dict[str, Any]:
        """
        Obtenir état recovery mode
        
        Args:
            loss_streak: Nombre pertes consécutives
            
        Returns:
            Dict: État recovery (active, level, multipliers, etc.)
        """
        pass
        
    @abstractmethod
    def update_position_status(self, position_id: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mettre à jour statut position avec données marché
        
        Args:
            position_id: ID position à update
            market_data: Données marché actuelles
            
        Returns:
            Dict: Nouveau statut position
        """
        pass
        
    @abstractmethod
    def calculate_pnl(self, position_id: str, current_price: float) -> Dict[str, float]:
        """
        Calculer PnL position
        
        Args:
            position_id: ID position
            current_price: Prix actuel
            
        Returns:
            Dict: PnL détaillé (unrealized, pct, etc.)
        """
        pass
        
    @abstractmethod
    def should_close_position(self, position_id: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Déterminer si position doit être fermée
        
        Args:
            position_id: ID position à vérifier
            market_data: Données marché actuelles
            
        Returns:
            Dict: Décision fermeture (should_close, reason, urgency)
        """
        pass


class IPositionDependencies(ABC):
    """Interface pour dépendances du PositionManager"""
    
    @abstractmethod
    def get_tp_sl_calculator(self):
        """Retourne calculateur TP/SL"""
        pass
        
    @abstractmethod
    def get_pnl_calculator(self):
        """Retourne calculateur PnL"""
        pass
        
    @abstractmethod
    def get_recovery_manager(self):
        """Retourne gestionnaire recovery mode"""
        pass
        
    @abstractmethod
    def get_trailing_stop_manager(self):
        """Retourne gestionnaire trailing stop"""
        pass
        
    @abstractmethod
    def get_early_invalidation_checker(self):
        """Retourne checker early invalidation"""
        pass


class PositionManagerConfig:
    """Configuration pour PositionManager testable"""
    
    def __init__(self, **kwargs):
        # Configuration générale
        self.max_positions = kwargs.get('max_positions', 1)
        self.max_risk_per_trade = kwargs.get('max_risk_per_trade', 3.0)
        self.min_risk_per_trade = kwargs.get('min_risk_per_trade', 0.5)
        
        # Configuration recovery mode  
        self.recovery_enabled = kwargs.get('recovery_enabled', True)
        self.recovery_mode = kwargs.get('recovery_mode', 'PROGRESSIVE')
        
        # Configuration trailing stop
        self.trailing_stop_enabled = kwargs.get('trailing_stop_enabled', True)
        self.breakeven_enabled = kwargs.get('breakeven_enabled', True)
        
        # Configuration early invalidation
        self.early_invalidation_enabled = kwargs.get('early_invalidation_enabled', True)
        self.max_adverse_move_pct = kwargs.get('max_adverse_move_pct', 0.3)
        
        # Configuration tests
        self.test_mode = kwargs.get('test_mode', False)
        self.mock_external_calls = kwargs.get('mock_external_calls', False)


# Utilitaires pour conversion
def setup_from_dict(data: Dict[str, Any]) -> PositionSetup:
    """Convertir dict en PositionSetup"""
    return PositionSetup(
        symbol=data.get('symbol', ''),
        direction=data.get('direction', 'LONG'),
        entry_price=float(data.get('entry_price', data.get('entry', 0))),
        sl_price=float(data.get('sl_price', data.get('sl', 0))),
        tp_price=float(data.get('tp_price', data.get('tp', 0))),
        atr=float(data.get('atr', 1.0)),
        score=float(data.get('score', data.get('totalScore', 0))),
        risk_per_trade=float(data.get('risk_per_trade', 2.0)),
        loss_streak=int(data.get('loss_streak', 0)),
        win_streak=int(data.get('win_streak', 0))
    )


def setup_to_dict(setup: PositionSetup) -> Dict[str, Any]:
    """Convertir PositionSetup en dict"""
    return {
        'symbol': setup.symbol,
        'direction': setup.direction,
        'entry_price': setup.entry_price,
        'entry': setup.entry_price,  # Alias pour compatibilité
        'sl_price': setup.sl_price,
        'sl': setup.sl_price,        # Alias pour compatibilité
        'tp_price': setup.tp_price,
        'tp': setup.tp_price,        # Alias pour compatibilité
        'atr': setup.atr,
        'score': setup.score,
        'totalScore': setup.score,   # Alias pour compatibilité
        'risk_per_trade': setup.risk_per_trade,
        'loss_streak': setup.loss_streak,
        'win_streak': setup.win_streak
    }
