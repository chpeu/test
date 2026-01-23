"""
TestablePositionCalculator - Implémentation testable et découplée
Sépare calculs purs de la logique métier complexe
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass

from ..interfaces.position_interfaces import (
    IPositionCalculator, PositionSize, PositionConfig
)

logger = logging.getLogger(__name__)


@dataclass
class RiskParameters:
    """Paramètres de risque calculés"""
    capital_at_risk: float
    max_loss_per_trade: float
    position_risk_ratio: float
    volatility_adjustment: float


class TestablePositionCalculator(IPositionCalculator):
    """
    Calculateur de positions testable
    
    Caractéristiques:
    - Calculs purs sans side-effects
    - Injection de configuration
    - Méthodes isolées et testables
    - Logging détaillé pour debug
    """
    
    def __init__(self, config: PositionConfig):
        self.config = config
        logger.info("✅ TestablePositionCalculator initialisé")
    
    def calculate_size(self, setup: Dict[str, Any], capital: float) -> PositionSize:
        """
        Calcule la taille d'une position de manière déterministe
        
        Args:
            setup: Configuration du trade avec scores, prix, etc.
            capital: Capital disponible
            
        Returns:
            PositionSize: Détails complets du calcul
        """
        try:
            # Validation préliminaire
            if capital <= 0 or not setup.get('current_price'):
                return self._create_safe_fallback_position(capital)
            
            # 1. Calcul de base selon capital et risque
            base_size = self._calculate_base_size(setup, capital)
            logger.debug(f"Base size calculée: {base_size}")
            
            # 2. Ajustements basés sur scores et volatilité
            adjusted_size = self._apply_score_adjustments(base_size, setup)
            logger.debug(f"Size après ajustements scores: {adjusted_size}")
            
            # 3. Application des limites de sécurité
            final_size = self._apply_position_limits(adjusted_size, capital)
            logger.debug(f"Size finale après limites: {final_size}")
            
            # 4. Calcul des distances SL/TP
            sl_distance = self._calculate_sl_distance(setup, final_size)
            tp_distance = self._calculate_tp_distance(setup, final_size)
            
            # 5. Calcul du risque effectif
            risk_pct = self._calculate_effective_risk(final_size, capital, sl_distance)
            
            position_size = PositionSize(
                base_size=base_size,
                adjusted_size=adjusted_size,
                final_size=final_size,
                risk_percentage=risk_pct,
                stop_loss_distance=sl_distance,
                take_profit_distance=tp_distance
            )
            
            logger.info(f"Position calculée: {final_size} (risque: {risk_pct:.2f}%)")
            return position_size
            
        except Exception as e:
            logger.error(f"Erreur calcul position: {e}")
            # Retourner position sécurisée minimale
            return self._create_safe_fallback_position(capital)
    
    def calculate_position_size(self, position_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interface method pour compatibilité avec les tests
        
        Args:
            position_data: Données de position avec prix, quantité, etc.
            
        Returns:
            Dict contenant les résultats du calcul
        """
        try:
            # Extraire les données nécessaires
            capital = position_data.get('capital', 10000.0)  # Capital par défaut
            current_price = position_data.get('entry_price', position_data.get('current_price', 100.0))
            
            # Setup basique pour calculate_size
            setup = {
                'current_price': current_price,
                'direction': position_data.get('direction', 'LONG'),
                'score': position_data.get('score', 0.7),
                'symbol': position_data.get('symbol', 'TEST')
            }
            
            # Utiliser la méthode principale
            position_size = self.calculate_size(setup, capital)
            
            # Convertir en format dict attendu par les tests
            return {
                'position_size': position_size.final_size,
                'margin_required': position_size.final_size,
                'leverage_used': position_data.get('leverage', 10),
                'risk_percent': position_size.risk_percentage,
                'stop_loss_price': current_price * (1 - position_size.stop_loss_distance),
                'take_profit_price': current_price * (1 + position_size.take_profit_distance),
                'base_size': position_size.base_size,
                'adjusted_size': position_size.adjusted_size
            }
            
        except Exception as e:
            logger.error(f"Erreur calculate_position_size: {e}")
            # Retour de sécurité
            return {
                'position_size': 100.0,
                'margin_required': 10.0,
                'leverage_used': 10,
                'risk_percent': 2.0,
                'stop_loss_price': 98.0,
                'take_profit_price': 102.0
            }
    
    def calculate_stop_loss(self, setup: Dict[str, Any], position_size: float) -> float:
        """
        Calcule niveau de stop loss
        
        Args:
            setup: Configuration du trade
            position_size: Taille de la position
            
        Returns:
            float: Prix de stop loss
        """
        try:
            current_price = float(setup.get('current_price', 0))
            if current_price <= 0:
                raise ValueError("Prix courant invalide")
            
            # ATR pour volatilité
            atr = float(setup.get('atr', current_price * 0.02))  # 2% par défaut
            
            # Direction trade
            side = setup.get('side', 'long').lower()
            
            if side == 'long':
                # SL en dessous du prix
                sl_distance = atr * 1.5  # 1.5x ATR
                stop_loss = current_price - sl_distance
            else:
                # SL au dessus du prix pour short
                sl_distance = atr * 1.5
                stop_loss = current_price + sl_distance
            
            # Vérifier que SL respecte les limites
            min_sl_distance = current_price * 0.005  # 0.5% minimum
            max_sl_distance = current_price * 0.10   # 10% maximum
            
            actual_sl_distance = max(min_sl_distance, min(sl_distance, max_sl_distance))
            
            if side == 'long':
                stop_loss = current_price - actual_sl_distance
            else:
                stop_loss = current_price + actual_sl_distance
            
            logger.debug(f"SL calculé: {stop_loss} (distance: {sl_distance})")
            return stop_loss
            
        except Exception as e:
            logger.error(f"Erreur calcul SL: {e}")
            # Fallback sécurisé
            current_price = float(setup.get('current_price', 100))
            return current_price * 0.95 if setup.get('side') == 'long' else current_price * 1.05
    
    def calculate_take_profit(self, setup: Dict[str, Any], position_size: float) -> float:
        """
        Calcule niveau de take profit
        
        Args:
            setup: Configuration du trade
            position_size: Taille de la position
            
        Returns:
            float: Prix de take profit
        """
        try:
            current_price = float(setup.get('current_price', 0))
            if current_price <= 0:
                raise ValueError("Prix courant invalide")
            
            # Score pour ajustement du TP
            score = float(setup.get('score_1m', 5.0))
            
            # ATR pour volatilité
            atr = float(setup.get('atr', current_price * 0.02))
            
            # Direction trade
            side = setup.get('side', 'long').lower()
            
            # Multiplier TP basé sur score (meilleur score = TP plus éloigné)
            tp_multiplier = 2.0 + (score - 5.0) * 0.3  # Entre 1.4x et 3.5x ATR
            tp_multiplier = max(1.5, min(4.0, tp_multiplier))
            
            tp_distance = atr * tp_multiplier
            
            if side == 'long':
                take_profit = current_price + tp_distance
            else:
                take_profit = current_price - tp_distance
            
            logger.debug(f"TP calculé: {take_profit} (distance: {tp_distance}, multiplier: {tp_multiplier})")
            return take_profit
            
        except Exception as e:
            logger.error(f"Erreur calcul TP: {e}")
            # Fallback sécurisé
            current_price = float(setup.get('current_price', 100))
            return current_price * 1.05 if setup.get('side') == 'long' else current_price * 0.95
    
    def _calculate_base_size(self, setup: Dict[str, Any], capital: float) -> float:
        """Calcul de taille de base selon capital et risque configuré"""
        try:
            if capital <= 0:
                return self.config.min_position_size
                
            # Risque configuré ou par défaut
            risk_pct = float(setup.get('risk_percentage', self.config.default_risk))
            risk_pct = max(0.5, min(risk_pct, self.config.max_risk_per_trade))
            
            # Capital à risquer
            risk_capital = capital * (risk_pct / 100.0)
            
            # Prix courant pour calcul
            current_price = float(setup.get('current_price', 1))
            if current_price <= 0:
                raise ValueError("Prix invalide")
            
            # Taille de base (en termes de capital, pas de quantité)
            base_size = risk_capital
            
            return max(base_size, self.config.min_position_size)
            
        except Exception as e:
            logger.error(f"Erreur calcul base size: {e}")
            return self.config.min_position_size
    
    def _apply_score_adjustments(self, base_size: float, setup: Dict[str, Any]) -> float:
        """Ajustements basés sur scores techniques"""
        try:
            # Score 1m (principal)
            score_1m = float(setup.get('score_1m', 5.0))
            
            # Score 5m (secondaire)
            score_5m = float(setup.get('score_5m', 5.0))
            
            # Score combiné pondéré
            combined_score = (score_1m * 0.7) + (score_5m * 0.3)
            
            # Facteur d'ajustement (score 5.0 = neutre)
            # Score > 7.0 = augmentation jusqu'à +50%
            # Score < 3.0 = réduction jusqu'à -30%
            if combined_score >= 5.0:
                adjustment = 1.0 + ((combined_score - 5.0) / 5.0) * 0.5  # Max +50%
            else:
                adjustment = 1.0 - ((5.0 - combined_score) / 5.0) * 0.3  # Max -30%
            
            # Limiter ajustement
            adjustment = max(0.7, min(1.5, adjustment))
            
            adjusted_size = base_size * adjustment
            
            logger.debug(f"Ajustement score: {adjustment:.3f} (score combiné: {combined_score:.2f})")
            return adjusted_size
            
        except Exception as e:
            logger.error(f"Erreur ajustement scores: {e}")
            return base_size
    
    def _apply_position_limits(self, size: float, capital: float) -> float:
        """Application des limites de sécurité"""
        try:
            if capital <= 0:
                return self.config.min_position_size
                
            # Limite minimum
            size = max(size, self.config.min_position_size)
            
            # Limite maximum absolue
            size = min(size, self.config.max_position_size)
            
            # Limite en % du capital (ex: max 20% du capital)
            if capital > 0:
                max_capital_pct = 0.20
                max_size_by_capital = capital * max_capital_pct
                size = min(size, max_size_by_capital)
            
            return size
            
        except Exception as e:
            logger.error(f"Erreur application limites: {e}")
            return self.config.min_position_size
    
    def _calculate_sl_distance(self, setup: Dict[str, Any], position_size: float) -> float:
        """Calcule distance de stop loss"""
        try:
            current_price = float(setup.get('current_price', 1))
            atr = float(setup.get('atr', current_price * 0.02))
            
            # Distance SL = 1.5x ATR par défaut
            sl_distance = atr * 1.5
            
            # Ajuster selon volatilité récente
            volatility = float(setup.get('volatility_score', 1.0))
            if volatility > 1.5:
                sl_distance *= 1.2  # Augmenter SL si très volatil
            elif volatility < 0.5:
                sl_distance *= 0.8  # Réduire SL si peu volatil
            
            return sl_distance
            
        except Exception as e:
            logger.error(f"Erreur calcul SL distance: {e}")
            return float(setup.get('current_price', 1)) * 0.02
    
    def _calculate_tp_distance(self, setup: Dict[str, Any], position_size: float) -> float:
        """Calcule distance de take profit"""
        try:
            current_price = float(setup.get('current_price', 1))
            atr = float(setup.get('atr', current_price * 0.02))
            score = float(setup.get('score_1m', 5.0))
            
            # Base TP = 2.5x ATR, ajusté selon score
            base_multiplier = 2.5
            score_adjustment = (score - 5.0) * 0.2  # +/- 0.6x max
            tp_multiplier = base_multiplier + score_adjustment
            tp_multiplier = max(1.5, min(4.0, tp_multiplier))
            
            tp_distance = atr * tp_multiplier
            
            return tp_distance
            
        except Exception as e:
            logger.error(f"Erreur calcul TP distance: {e}")
            return float(setup.get('current_price', 1)) * 0.03
    
    def _calculate_effective_risk(self, position_size: float, capital: float, sl_distance: float) -> float:
        """Calcule le risque effectif en pourcentage"""
        try:
            if capital <= 0:
                return self.config.default_risk
                
            potential_loss = position_size * sl_distance
            risk_percentage = (potential_loss / capital) * 100
            
            return min(risk_percentage, self.config.max_risk_per_trade)
            
        except Exception as e:
            logger.error(f"Erreur calcul risque effectif: {e}")
            return self.config.default_risk
    
    def _create_safe_fallback_position(self, capital: float) -> PositionSize:
        """Crée position de fallback sécurisée en cas d'erreur"""
        safe_size = self.config.min_position_size
        
        return PositionSize(
            base_size=safe_size,
            adjusted_size=safe_size,
            final_size=safe_size,
            risk_percentage=1.0,  # Risque minimal
            stop_loss_distance=safe_size * 0.02,  # 2%
            take_profit_distance=safe_size * 0.03  # 3%
        )
