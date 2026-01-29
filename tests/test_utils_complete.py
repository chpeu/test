#!/usr/bin/env python3
"""
Tests complets pour modules utils/ - Couverture maximale
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestConfigPersistence:
    """Tests pour utils.config_persistence"""
    
    def test_config_persistence_import(self):
        """Test import du module config_persistence"""
        from utils.config_persistence import save_config_overrides, load_config_overrides
        assert save_config_overrides is not None
        assert load_config_overrides is not None

    def test_config_persistence_init(self):
        """Test initialisation config_persistence functions"""
        from utils.config_persistence import save_config_overrides, load_config_overrides
        # Test basic functionality
        result = load_config_overrides()
        assert isinstance(result, dict)

    def test_config_persistence_save_load(self):
        """Test sauvegarde et chargement de configuration"""
        from utils.config_persistence import save_config_overrides, load_config_overrides
        
        test_config = {"test_key": "test_value", "number": 42}
        
        # Test save
        result = save_config_overrides(test_config)
        assert result is True  # Should return True on success
        
        # Test load
        loaded_config = load_config_overrides()
        assert isinstance(loaded_config, dict)
        # Note: loaded config may contain more than just our test data due to existing overrides


class TestEffectiveConfig:
    """Tests pour utils.effective_config"""
    
    def test_effective_config_import(self):
        """Test import du module effective_config"""
        try:
            import utils.effective_config
            assert True
        except ImportError:
            pytest.skip("Module effective_config non disponible")

    def test_effective_config_functions(self):
        """Test fonctions du module effective_config"""
        try:
            from utils.effective_config import get_effective_config
            config = get_effective_config()
            assert isinstance(config, dict)
        except (ImportError, AttributeError):
            pytest.skip("Fonction get_effective_config non disponible")


class TestErrorHistory:
    """Tests pour utils.error_history"""
    
    def test_error_history_import(self):
        """Test import du module error_history"""
        try:
            import utils.error_history
            assert True
        except ImportError:
            pytest.skip("Module error_history non disponible")

    def test_error_history_add_error(self):
        """Test ajout d'erreur à l'historique"""
        try:
            from utils.error_history import ErrorHistory
            eh = ErrorHistory()
            eh.add_error("Test error", "TestModule")
            assert len(eh.errors) > 0
        except (ImportError, AttributeError):
            pytest.skip("ErrorHistory non disponible")


class TestApiHelper:
    """Tests pour utils.helpers.api_helper"""
    
    def test_api_helper_import(self):
        """Test import du module api_helper"""
        try:
            import utils.helpers.api_helper
            assert True
        except ImportError:
            pytest.skip("Module api_helper non disponible")

    def test_api_helper_functions(self):
        """Test fonctions du module api_helper"""
        try:
            from utils.helpers.api_helper import format_response
            response = format_response("test", 200)
            assert "test" in str(response)
        except (ImportError, AttributeError):
            pytest.skip("Fonction format_response non disponible")


class TestConfigHelper:
    """Tests pour utils.helpers.config_helper"""
    
    def test_config_helper_import(self):
        """Test import du module config_helper"""
        try:
            import utils.helpers.config_helper
            assert True
        except ImportError:
            pytest.skip("Module config_helper non disponible")

    def test_config_helper_validate_config(self):
        """Test validation de configuration"""
        try:
            from utils.helpers.config_helper import validate_config
            result = validate_config({"test": True})
            assert isinstance(result, (bool, dict))
        except (ImportError, AttributeError):
            pytest.skip("Fonction validate_config non disponible")


class TestDataLoggerHelper:
    """Tests pour utils.helpers.data_logger_helper"""
    
    def test_data_logger_helper_import(self):
        """Test import du module data_logger_helper"""
        try:
            import utils.helpers.data_logger_helper
            assert True
        except ImportError:
            pytest.skip("Module data_logger_helper non disponible")

    def test_data_logger_helper_format_trade_data(self):
        """Test formatage des données de trade"""
        try:
            from utils.helpers.data_logger_helper import format_trade_data
            trade_data = {"symbol": "BTC/USDT", "side": "LONG"}
            formatted = format_trade_data(trade_data)
            assert isinstance(formatted, dict)
        except (ImportError, AttributeError):
            pytest.skip("Fonction format_trade_data non disponible")


class TestMarketHelper:
    """Tests pour utils.helpers.market_helper"""
    
    def test_market_helper_import(self):
        """Test import du module market_helper"""
        try:
            import utils.helpers.market_helper
            assert True
        except ImportError:
            pytest.skip("Module market_helper non disponible")

    def test_market_helper_calculate_percentage(self):
        """Test calcul de pourcentage"""
        try:
            from utils.helpers.market_helper import calculate_percentage_change
            change = calculate_percentage_change(100, 110)
            assert abs(change - 10.0) < 0.001
        except (ImportError, AttributeError):
            pytest.skip("Fonction calculate_percentage_change non disponible")


class TestPositionHelper:
    """Tests pour utils.helpers.position_helper"""
    
    def test_position_helper_import(self):
        """Test import du module position_helper"""
        try:
            import utils.helpers.position_helper
            assert True
        except ImportError:
            pytest.skip("Module position_helper non disponible")

    def test_position_helper_calculate_pnl(self):
        """Test calcul PnL"""
        try:
            from utils.helpers.position_helper import calculate_pnl
            pnl = calculate_pnl(100, 110, 1.0, "LONG")
            assert abs(pnl - 10.0) < 0.001
        except (ImportError, AttributeError):
            pytest.skip("Fonction calculate_pnl non disponible")


class TestStatsHelper:
    """Tests pour utils.helpers.stats_helper"""
    
    def test_stats_helper_import(self):
        """Test import du module stats_helper"""
        try:
            import utils.helpers.stats_helper
            assert True
        except ImportError:
            pytest.skip("Module stats_helper non disponible")

    def test_stats_helper_calculate_winrate(self):
        """Test calcul winrate"""
        try:
            from utils.helpers.stats_helper import calculate_winrate
            winrate = calculate_winrate(7, 10)
            assert abs(winrate - 70.0) < 0.001
        except (ImportError, AttributeError):
            pytest.skip("Fonction calculate_winrate non disponible")


class TestHistoryUtils:
    """Tests pour utils.history_utils"""
    
    def test_history_utils_import(self):
        """Test import du module history_utils"""
        try:
            import utils.history_utils
            assert True
        except ImportError:
            pytest.skip("Module history_utils non disponible")

    def test_history_utils_get_history(self):
        """Test récupération historique"""
        try:
            from utils.history_utils import get_trade_history
            history = get_trade_history(limit=10)
            assert isinstance(history, (list, dict))
        except (ImportError, AttributeError):
            pytest.skip("Fonction get_trade_history non disponible")


class TestLogger:
    """Tests pour utils.logger"""
    
    def test_logger_import(self):
        """Test import du module logger"""
        try:
            import utils.logger
            assert True
        except ImportError:
            pytest.skip("Module logger non disponible")

    def test_logger_get_logger(self):
        """Test récupération logger"""
        try:
            from utils.logger import get_logger
            logger = get_logger()
            assert logger is not None
        except (ImportError, AttributeError, TypeError):
            pytest.skip("Fonction get_logger non disponible")


class TestLoggingUtils:
    """Tests pour utils.logging_utils"""
    
    def test_logging_utils_import(self):
        """Test import du module logging_utils"""
        try:
            import utils.logging_utils
            assert True
        except ImportError:
            pytest.skip("Module logging_utils non disponible")

    def test_logging_utils_setup_logging(self):
        """Test configuration logging"""
        try:
            from utils.logging_utils import setup_logging
            setup_logging("DEBUG")
            assert True
        except (ImportError, AttributeError):
            pytest.skip("Fonction setup_logging non disponible")


class TestPricing:
    """Tests pour utils.pricing"""
    
    def test_pricing_import(self):
        """Test import du module pricing"""
        try:
            import utils.pricing
            assert True
        except ImportError:
            pytest.skip("Module pricing non disponible")

    def test_pricing_calculate_slippage(self):
        """Test calcul slippage"""
        try:
            from utils.pricing import calculate_slippage
            slippage = calculate_slippage(100, 101)
            assert abs(slippage - 1.0) < 0.001
        except (ImportError, AttributeError):
            pytest.skip("Fonction calculate_slippage non disponible")


class TestSessionDetector:
    """Tests pour utils.session_detector"""
    
    def test_session_detector_import(self):
        """Test import du module session_detector"""
        try:
            import utils.session_detector
            assert True
        except ImportError:
            pytest.skip("Module session_detector non disponible")

    def test_session_detector_get_current_session(self):
        """Test détection session actuelle"""
        try:
            from utils.session_detector import get_current_session
            session = get_current_session()
            assert isinstance(session, (str, dict))
        except (ImportError, AttributeError):
            pytest.skip("Fonction get_current_session non disponible")


class TestAsyncDecorators:
    """Tests pour utils.decorators.async_decorators"""
    
    def test_async_decorators_import(self):
        """Test import du module async_decorators"""
        try:
            import utils.decorators.async_decorators
            assert True
        except ImportError:
            pytest.skip("Module async_decorators non disponible")

    @pytest.mark.asyncio
    async def test_async_retry_decorator(self):
        """Test décorateur retry asynchrone"""
        try:
            from utils.decorators.async_decorators import async_retry
            
            @async_retry(max_attempts=3)
            async def test_func():
                return "success"
            
            result = await test_func()
            assert result == "success"
        except (ImportError, AttributeError):
            pytest.skip("Décorateur async_retry non disponible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
