"""
Unit tests for core/config_manager.py
"""
import pytest
import json
import tempfile
from pathlib import Path
from core.config_manager import (
    ConfigManager,
    TradingConfigSection,
    get_config_manager,
    reset_config_manager
)


class TestTradingConfigSection:
    """Tests for TradingConfigSection dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = TradingConfigSection()

        assert config.fee_per_trade == 0.0004
        assert config.tp_percent == 0.50
        assert config.sl_percent == 0.20
        assert config.trend_timeframe == "15m"
        assert config.tp_sl_mode == "FIXE"

    def test_validate_valid_config(self):
        """Test validation with valid configuration."""
        config = TradingConfigSection()
        # Should not raise
        config.validate()

    def test_validate_invalid_fee(self):
        """Test validation fails with invalid fee."""
        config = TradingConfigSection(fee_per_trade=1.5)

        with pytest.raises(ValueError, match="fee_per_trade must be between 0 and 1"):
            config.validate()
