"""
Tests unitaires pour TestablePositionValidator
Valide la logique de validation métier
"""

import pytest
import sys
import os

# Ajouter le répertoire parent au path pour imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core.interfaces.position_interfaces import PositionSize, ValidationResult
from core.implementations.testable_position_validator import TestablePositionValidator


class TestTestablePositionValidator:
    """Suite de tests pour TestablePositionValidator"""
    
    def setup_method(self):
        """Setup avant chaque test"""
        self.config = {
            'min_score': 3.0,
            'max_risk_per_trade': 5.0,
            'max_position_value': 10000.0,
            'min_volume': 100000,
            'min_position_size': 10.0
        }
        self.validator = TestablePositionValidator(self.config)
        
        # Setup valide standard
        self.valid_setup = {
            'symbol': 'BTCUSDT',
            'side': 'long',
            'current_price': 50000.0,
            'score_1m': 6.0,
            'score_5m': 5.5,
            'atr': 1000.0,
            'volume': 5000000,
            'risk_percentage': 2.0
        }
    
    def test_validate_setup_valid(self):
        """Test validation d'un setup valide"""
        result = self.validator.validate_setup(self.valid_setup)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert len(result.errors) == 0
        # Peut avoir des warnings mais pas d'erreurs
    
    def test_validate_setup_missing_required_fields(self):
        """Test validation avec champs obligatoires manquants"""
        # Setup sans symbol
        invalid_setup = self.valid_setup.copy()
        del invalid_setup['symbol']
        
        result = self.validator.validate_setup(invalid_setup)
        
        assert not result.is_valid
        assert any('symbol' in error.lower() for error in result.errors)
        
        # Setup sans side
        invalid_setup2 = self.valid_setup.copy()
        del invalid_setup2['side']
        
        result2 = self.validator.validate_setup(invalid_setup2)
        assert not result2.is_valid
        assert any('side' in error.lower() for error in result2.errors)
    
    def test_validate_setup_invalid_price(self):
        """Test validation prix invalide"""
        # Prix négatif
        invalid_setup = self.valid_setup.copy()
        invalid_setup['current_price'] = -100.0
        
        result = self.validator.validate_setup(invalid_setup)
        assert not result.is_valid
        assert any('prix' in error.lower() for error in result.errors)
        
        # Prix trop faible
        invalid_setup2 = self.valid_setup.copy()
        invalid_setup2['current_price'] = 0.000001  # Trop petit
        
        result2 = self.validator.validate_setup(invalid_setup2)
        assert not result2.is_valid
    
    def test_validate_setup_invalid_side(self):
        """Test validation side invalide"""
        invalid_setup = self.valid_setup.copy()
        invalid_setup['side'] = 'invalid_side'
        
        result = self.validator.validate_setup(invalid_setup)
        
        assert not result.is_valid
        assert any('side' in error.lower() for error in result.errors)
    
    def test_validate_setup_invalid_scores(self):
        """Test validation scores invalides"""
        # Score hors limites (> 10)
        invalid_setup = self.valid_setup.copy()
        invalid_setup['score_1m'] = 15.0
        
        result = self.validator.validate_setup(invalid_setup)
        assert not result.is_valid
        assert any('score_1m' in error.lower() for error in result.errors)
        
        # Score négatif
        invalid_setup2 = self.valid_setup.copy()
        invalid_setup2['score_5m'] = -2.0
        
        result2 = self.validator.validate_setup(invalid_setup2)
        assert not result2.is_valid
    
    def test_validate_setup_atr_consistency(self):
        """Test validation cohérence ATR/prix"""
        # ATR supérieur au prix (impossible)
        invalid_setup = self.valid_setup.copy()
        invalid_setup['atr'] = 60000.0  # > current_price
        
        result = self.validator.validate_setup(invalid_setup)
        assert not result.is_valid
        assert any('atr' in error.lower() for error in result.errors)
    
    def test_validate_setup_low_scores_warning(self):
        """Test warnings pour scores faibles"""
        low_score_setup = self.valid_setup.copy()
        low_score_setup['score_1m'] = 2.0  # < min_score
        low_score_setup['score_5m'] = 2.5  # < min_score
        
        result = self.validator.validate_setup(low_score_setup)
        
        # Doit être valide mais avec warnings
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any('score_1m' in warning.lower() for warning in result.warnings)
    
    def test_validate_setup_score_divergence_warning(self):
        """Test warning pour divergence entre scores"""
        divergent_setup = self.valid_setup.copy()
        divergent_setup['score_1m'] = 8.0
        divergent_setup['score_5m'] = 3.0  # Divergence importante
        
        result = self.validator.validate_setup(divergent_setup)
        
        assert result.is_valid  # Valide mais warning
        assert any('divergence' in warning.lower() for warning in result.warnings)
    
    def test_validate_market_conditions_valid_symbol(self):
        """Test validation conditions marché symbol valide"""
        result = self.validator.validate_market_conditions('BTCUSDT')
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_market_conditions_invalid_format(self):
        """Test validation format symbol invalide"""
        # Format invalide
        result1 = self.validator.validate_market_conditions('btc')  # Trop court
        assert not result1.is_valid
        
        result2 = self.validator.validate_market_conditions('BTCEUR')  # Pas USDT
        assert not result2.is_valid
        
        result3 = self.validator.validate_market_conditions('btcusdt')  # Pas majuscule
        assert not result3.is_valid
    
    def test_validate_market_conditions_inactive_symbol(self):
        """Test validation symbol inactif"""
        result = self.validator.validate_market_conditions('INVALIDUSDT')
        
        assert not result.is_valid
        assert any('inactif' in error.lower() for error in result.errors)
    
    def test_validate_risk_parameters_valid(self):
        """Test validation paramètres risque valides"""
        position_size = PositionSize(
            base_size=100.0,
            adjusted_size=120.0,
            final_size=120.0,
            risk_percentage=2.0,
            stop_loss_distance=50.0,
            take_profit_distance=100.0
        )
        capital = 10000.0
        
        result = self.validator.validate_risk_parameters(position_size, capital)
        
        assert result.is_valid
    
    def test_validate_risk_parameters_invalid_position(self):
        """Test validation position invalide"""
        # Position size invalide
        invalid_position = PositionSize(
            base_size=0,  # Invalide
            adjusted_size=0,
            final_size=0,
            risk_percentage=0,
            stop_loss_distance=0,
            take_profit_distance=0
        )
        
        result = self.validator.validate_risk_parameters(invalid_position, 10000.0)
        
        assert not result.is_valid
        assert any('invalide' in error.lower() for error in result.errors)
    
    def test_validate_risk_parameters_insufficient_capital(self):
        """Test validation capital insuffisant"""
        large_position = PositionSize(
            base_size=5000.0,
            adjusted_size=5000.0,
            final_size=15000.0,  # > capital disponible
            risk_percentage=2.0,
            stop_loss_distance=50.0,
            take_profit_distance=100.0
        )
        capital = 10000.0
        
        result = self.validator.validate_risk_parameters(large_position, capital)
        
        assert not result.is_valid
        assert any('capital' in error.lower() for error in result.errors)
    
    def test_validate_risk_parameters_excessive_risk(self):
        """Test validation risque excessif"""
        high_risk_position = PositionSize(
            base_size=100.0,
            adjusted_size=120.0,
            final_size=120.0,
            risk_percentage=8.0,  # > max_risk_per_trade
            stop_loss_distance=50.0,
            take_profit_distance=100.0
        )
        
        result = self.validator.validate_risk_parameters(high_risk_position, 10000.0)
        
        assert not result.is_valid
        assert any('risque' in error.lower() for error in result.errors)
    
    def test_validate_risk_parameters_poor_risk_reward(self):
        """Test validation mauvais ratio risk/reward"""
        poor_ratio_position = PositionSize(
            base_size=100.0,
            adjusted_size=120.0,
            final_size=120.0,
            risk_percentage=2.0,
            stop_loss_distance=100.0,  # SL éloigné
            take_profit_distance=50.0,  # TP proche = mauvais ratio
        )
        
        result = self.validator.validate_risk_parameters(poor_ratio_position, 10000.0)
        
        # Valide mais avec warning
        assert result.is_valid
        assert any('risk/reward' in warning.lower() for warning in result.warnings)
    
    def test_validate_risk_parameters_position_too_small(self):
        """Test validation position trop petite"""
        tiny_position = PositionSize(
            base_size=5.0,
            adjusted_size=5.0,
            final_size=5.0,  # < min_position_size
            risk_percentage=0.1,
            stop_loss_distance=10.0,
            take_profit_distance=20.0
        )
        
        result = self.validator.validate_risk_parameters(tiny_position, 10000.0)
        
        assert not result.is_valid
        assert any('petite' in error.lower() for error in result.errors)
    
    def test_validate_setup_high_risk_warning(self):
        """Test warning pour risque élevé mais acceptable"""
        high_risk_setup = self.valid_setup.copy()
        high_risk_setup['risk_percentage'] = 4.0  # Élevé mais < max_risk_per_trade
        
        result = self.validator.validate_setup(high_risk_setup)
        
        assert result.is_valid
        assert any('risque élevé' in warning.lower() for warning in result.warnings)
    
    def test_validate_setup_excessive_risk_error(self):
        """Test erreur pour risque excessif"""
        excessive_risk_setup = self.valid_setup.copy()
        excessive_risk_setup['risk_percentage'] = 7.0  # > max_risk_per_trade
        
        result = self.validator.validate_setup(excessive_risk_setup)
        
        assert not result.is_valid
        assert any('risque trop élevé' in error.lower() for error in result.errors)
    
    def test_error_handling_in_validation(self):
        """Test gestion d'erreurs dans la validation"""
        # Setup avec données corrompues
        corrupted_setup = {
            'symbol': 'BTCUSDT',
            'side': 'long',
            'current_price': 'invalid_price',  # String au lieu de float
            'score_1m': 6.0
        }
        
        result = self.validator.validate_setup(corrupted_setup)
        
        # Doit gérer l'erreur gracieusement
        assert not result.is_valid
        assert len(result.errors) > 0
    
    def test_validation_result_properties(self):
        """Test propriétés de ValidationResult"""
        # Test avec erreurs
        result_with_errors = ValidationResult(False, ['error1', 'error2'], ['warning1'])
        assert result_with_errors.has_errors
        assert not result_with_errors.is_valid
        
        # Test sans erreurs
        result_no_errors = ValidationResult(True, [], ['warning1'])
        assert not result_no_errors.has_errors
        assert result_no_errors.is_valid
        
        # Test méthodes factory
        success_result = ValidationResult.success(['warning1'])
        assert success_result.is_valid
        assert not success_result.has_errors
        assert len(success_result.warnings) == 1
        
        error_result = ValidationResult.error(['error1'], ['warning1'])
        assert not error_result.is_valid
        assert error_result.has_errors
        assert len(error_result.errors) == 1


if __name__ == '__main__':
    # Permet d'exécuter les tests directement
    pytest.main([__file__, '-v'])
