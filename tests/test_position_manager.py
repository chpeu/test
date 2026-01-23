"""
Tests pour le gestionnaire de positions
"""
import pytest
from core.position_manager import PositionManager, PositionConfig


class TestPositionManager:
    """Tests pour le gestionnaire de positions"""

    def test_position_config_creation(self):
        """Test création de configuration de position"""
        config = PositionConfig()
        assert config is not None

    def test_position_config_with_params(self):
        """Test configuration de position avec paramètres"""
        config = PositionConfig(
            use_atr=True,
            fixed_tp_pct=0.6,
            fixed_sl_pct=0.25,
            win_streak=3,
            loss_streak=2
        )
        assert config.use_atr is True
        assert config.fixed_tp_pct == 0.6
        assert config.fixed_sl_pct == 0.25
        assert config.win_streak == 3
        assert config.loss_streak == 2

    def test_position_manager_creation(self):
        """Test création du gestionnaire de positions"""
        config = PositionConfig()
        manager = PositionManager(config=config)
        assert manager is not None
        assert manager.config == config

    def test_format_price(self):
        """Test formatage de prix"""
        price = PositionManager._format_price(50000.123456)
        assert isinstance(price, str)
        assert '50000' in price

    def test_format_price_decimals(self):
        """Test formatage de prix avec décimales"""
        price = PositionManager._format_price(50000.123456, min_decimals=2, max_decimals=4)
        assert isinstance(price, str)
        assert '50000' in price
