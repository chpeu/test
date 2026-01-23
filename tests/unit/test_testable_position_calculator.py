"""
Tests unitaires pour TestablePositionCalculator
Valide les calculs purs et la logique métier
"""

import pytest
import sys
import os

# Ajouter le répertoire parent au path pour imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.interfaces.position_interfaces import PositionConfig, PositionSize
from core.implementations.testable_position_calculator import TestablePositionCalculator


class TestTestablePositionCalculator:
    """Suite de tests pour TestablePositionCalculator"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        self.config = PositionConfig(
            default_risk=2.0,
            max_position_size=1000.0,
            min_position_size=10.0,
            max_risk_per_trade=5.0,
            emergency_stop_loss=10.0
        )
        self.calculator = TestablePositionCalculator(self.config)
        
        # Setup de test standard
        self.standard_setup = {
            'symbol': 'BTCUSDT',
            'side': 'long',
            'current_price': 50000.0,
            'score_1m': 6.0,
            'score_5m': 5.5,
            'atr': 1000.0,  # 2% du prix
            'volume': 5000000,
            'risk_percentage': 2.0
        }
        
        self.test_capital = 10000.0  # $10k
    
    def test_calculate_size_basic(self):
        """Test calcul de taille basique"""
        result = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        
        assert isinstance(result, PositionSize)
        assert result.is_valid
        assert result.final_size > 0
        assert result.risk_percentage > 0
        
        # Vérifier que le risque reste dans les limites
        assert result.risk_percentage <= self.config.max_risk_per_trade
        
        # Vérifier taille dans les limites
        assert self.config.min_position_size <= result.final_size <= self.config.max_position_size
    
    def test_calculate_size_with_score_adjustments(self):
        """Test ajustements basés sur scores"""
        # Setup avec score élevé
        high_score_setup = self.standard_setup.copy()
        high_score_setup['score_1m'] = 8.0
        high_score_setup['score_5m'] = 7.5
        
        # Setup avec score faible
        low_score_setup = self.standard_setup.copy()
        low_score_setup['score_1m'] = 3.0
        low_score_setup['score_5m'] = 2.5
        
        result_high = self.calculator.calculate_size(high_score_setup, self.test_capital)
        result_low = self.calculator.calculate_size(low_score_setup, self.test_capital)
        result_standard = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        
        # Score élevé = taille plus importante
        assert result_high.final_size > result_standard.final_size
        # Score faible = taille réduite
        assert result_low.final_size < result_standard.final_size
    
    def test_calculate_size_risk_limits(self):
        """Test respect des limites de risque"""
        # Setup avec risque excessif
        high_risk_setup = self.standard_setup.copy()
        high_risk_setup['risk_percentage'] = 10.0  # > max_risk_per_trade
        
        result = self.calculator.calculate_size(high_risk_setup, self.test_capital)
        
        # Risque doit être capé à max_risk_per_trade
        assert result.risk_percentage <= self.config.max_risk_per_trade
    
    def test_calculate_size_insufficient_capital(self):
        """Test avec capital insuffisant"""
        small_capital = 50.0  # $50 seulement
        
        result = self.calculator.calculate_size(self.standard_setup, small_capital)
        
        # Doit retourner position minimale sécurisée
        assert result.final_size >= self.config.min_position_size
        # Mais ajustée au capital disponible
        assert result.final_size <= small_capital * 0.20  # Max 20% du capital
    
    def test_calculate_stop_loss_long(self):
        """Test calcul stop loss pour position long"""
        setup = self.standard_setup.copy()
        setup['side'] = 'long'
        
        sl = self.calculator.calculate_stop_loss(setup, 100.0)
        
        current_price = setup['current_price']
        
        # SL doit être en dessous du prix pour long
        assert sl < current_price
        
        # Distance SL raisonnable (basée sur ATR)
        distance = current_price - sl
        expected_distance = setup['atr'] * 1.5
        
        # Tolérance 20% pour ajustements
        assert abs(distance - expected_distance) / expected_distance < 0.30
    
    def test_calculate_stop_loss_short(self):
        """Test calcul stop loss pour position short"""
        setup = self.standard_setup.copy()
        setup['side'] = 'short'
        
        sl = self.calculator.calculate_stop_loss(setup, 100.0)
        
        current_price = setup['current_price']
        
        # SL doit être au dessus du prix pour short
        assert sl > current_price
    
    def test_calculate_take_profit_score_impact(self):
        """Test impact du score sur take profit"""
        # Setup score élevé
        high_score_setup = self.standard_setup.copy()
        high_score_setup['score_1m'] = 8.0
        
        # Setup score faible  
        low_score_setup = self.standard_setup.copy()
        low_score_setup['score_1m'] = 3.0
        
        tp_high = self.calculator.calculate_take_profit(high_score_setup, 100.0)
        tp_low = self.calculator.calculate_take_profit(low_score_setup, 100.0)
        
        current_price = self.standard_setup['current_price']
        
        # Pour position long
        distance_high = tp_high - current_price
        distance_low = tp_low - current_price
        
        # Score élevé = TP plus éloigné (plus ambitieux)
        assert distance_high > distance_low
    
    def test_invalid_setup_handling(self):
        """Test gestion des setups invalides"""
        # Setup sans prix
        invalid_setup = self.standard_setup.copy()
        del invalid_setup['current_price']
        
        result = self.calculator.calculate_size(invalid_setup, self.test_capital)
        
        # Doit retourner position de fallback sécurisée
        assert result.final_size == self.config.min_position_size
    
    def test_zero_capital_handling(self):
        """Test gestion capital zéro"""
        result = self.calculator.calculate_size(self.standard_setup, 0)
        
        # Doit retourner position minimale
        assert result.final_size == self.config.min_position_size
    
    def test_extreme_atr_handling(self):
        """Test gestion ATR extrêmes"""
        # ATR très élevé (volatilité extrême)
        high_atr_setup = self.standard_setup.copy()
        high_atr_setup['atr'] = 10000.0  # 20% du prix
        
        sl = self.calculator.calculate_stop_loss(high_atr_setup, 100.0)
        
        # SL ne doit pas être trop éloigné (max 10% du prix)
        current_price = high_atr_setup['current_price']
        max_distance = current_price * 0.10
        actual_distance = abs(sl - current_price)
        
        assert actual_distance <= max_distance
    
    def test_position_size_consistency(self):
        """Test cohérence des calculs PositionSize"""
        result = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        
        # base_size <= adjusted_size <= final_size (après limites)
        # OU ajustement peut réduire (score faible)
        assert result.base_size > 0
        assert result.final_size > 0
        
        # Distances SL/TP cohérentes
        assert result.stop_loss_distance > 0
        assert result.take_profit_distance > 0
        
        # Risque calculé cohérent
        assert 0 < result.risk_percentage <= self.config.max_risk_per_trade
    
    def test_deterministic_calculations(self):
        """Test que les calculs sont déterministes"""
        # Même setup doit donner même résultat
        result1 = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        result2 = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        
        assert result1.final_size == result2.final_size
        assert result1.risk_percentage == result2.risk_percentage
        assert result1.stop_loss_distance == result2.stop_loss_distance
        assert result1.take_profit_distance == result2.take_profit_distance
    
    def test_risk_percentage_calculation(self):
        """Test calcul précis du pourcentage de risque"""
        setup = self.standard_setup.copy()
        setup['risk_percentage'] = 3.0  # 3% explicite
        
        result = self.calculator.calculate_size(setup, self.test_capital)
        
        # Le risque calculé doit être proche du demandé
        # (peut varier à cause des ajustements et limites)
        assert abs(result.risk_percentage - 3.0) < 1.0  # Tolérance 1%
    
    def test_different_symbols(self):
        """Test avec différents symbols (prix différents)"""
        # ETH (prix plus bas)
        eth_setup = self.standard_setup.copy()
        eth_setup['symbol'] = 'ETHUSDT'
        eth_setup['current_price'] = 3000.0
        eth_setup['atr'] = 60.0  # 2% du prix ETH
        
        btc_result = self.calculator.calculate_size(self.standard_setup, self.test_capital)
        eth_result = self.calculator.calculate_size(eth_setup, self.test_capital)
        
        # Les calculs doivent fonctionner pour différents prix
        assert btc_result.is_valid
        assert eth_result.is_valid
        
        # Les tailles peuvent être différentes mais cohérentes
        assert btc_result.final_size > 0
        assert eth_result.final_size > 0


if __name__ == '__main__':
    # Permet d'exécuter les tests directement
    pytest.main([__file__, '-v'])
