"""
🔥 SPRINT 1.5: Tests pour Helpers Module

Tests pour tous les helpers créés:
- ConfigHelper
- DataLoggerHelper
- APIHelper
- MarketHelper
- StatsHelper
- PositionHelper
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json

# Import helpers
from utils.helpers import (
    ConfigHelper,
    DataLoggerHelper,
    APIHelper,
    MarketHelper,
    StatsHelper,
    PositionHelper,
    PositionProxy,
)


class TestConfigHelper:
    """Tests pour ConfigHelper"""

    def test_get_trading_params_with_default_config(self):
        """Test récupération paramètres trading avec config par défaut"""
        params = ConfigHelper.get_trading_params({})

        assert 'account_size' in params
        assert 'risk_per_trade' in params
        assert params['account_size'] == 1000.0
        assert params['risk_per_trade'] == 0.02  # 2% converti en décimal

    def test_get_trading_params_with_custom_config(self):
        """Test avec config custom"""
        custom_config = {
            'account_size': 5000.0,
            'risk_per_trade': 3.0,  # 3%
            'tp_sl_mode': 'ATR',
        }

        params = ConfigHelper.get_trading_params(custom_config)

        assert params['account_size'] == 5000.0
        assert params['risk_per_trade'] == 0.03
        assert params['tp_sl_mode'] == 'ATR'

    def test_get_scanner_params(self):
        """Test paramètres scanner"""
        params = ConfigHelper.get_scanner_params({})

        assert 'scan_interval' in params
        assert 'top_pairs_count' in params
        assert params['scan_interval'] == 60

    def test_get_position_params(self):
        """Test paramètres position management"""
        params = ConfigHelper.get_position_params({})

        assert 'max_position_duration' in params
        assert 'enable_breakeven' in params
        assert params['enable_breakeven'] is True

    def test_get_param_single(self):
        """Test récupération paramètre unique"""
        config = {'my_param': 'my_value'}
        value = ConfigHelper.get_param('my_param', 'default', config)

        assert value == 'my_value'

        # Test default
        value = ConfigHelper.get_param('non_existent', 'default', config)
        assert value == 'default'

    def test_get_all_params(self):
        """Test récupération TOUS les paramètres"""
        all_params = ConfigHelper.get_all_params({})

        # Devrait contenir paramètres de toutes les catégories
        assert 'account_size' in all_params  # trading
        assert 'scan_interval' in all_params  # scanner
        assert 'max_position_duration' in all_params  # position
        assert 'exchange' in all_params  # api


class TestAPIHelper:
    """Tests pour APIHelper"""

    def test_validate_price_simple_valid(self):
        """Test validation simple prix valide"""
        assert APIHelper.validate_price_simple(50000.0) is True
        assert APIHelper.validate_price_simple(1.0) is True

    def test_validate_price_simple_invalid(self):
        """Test validation simple prix invalide"""
        assert APIHelper.validate_price_simple(None) is False
        assert APIHelper.validate_price_simple(0) is False
        assert APIHelper.validate_price_simple(-100) is False

    def test_validate_price_with_fallback_valid(self):
        """Test validation avec fallback - prix valide"""
        price, source = APIHelper.validate_price_with_fallback(
            price=50000.0,
            symbol="BTC/USDT",
            fallback_price=45000.0
        )

        assert price == 50000.0
        assert source == "api"

    def test_validate_price_with_fallback_invalid_uses_fallback(self):
        """Test fallback quand prix invalide et pas de cache"""
        price, source = APIHelper.validate_price_with_fallback(
            price=None,
            symbol="BTC/USDT",
            fallback_price=45000.0
        )

        assert price == 45000.0
        assert source == "fallback"

    def test_validate_price_with_fallback_uses_cache(self):
        """Test utilisation cache quand prix invalide"""
        # Mock cache manager
        cache_manager = Mock()
        cache_manager.get_cached_price = Mock(return_value=48000.0)

        price, source = APIHelper.validate_price_with_fallback(
            price=None,
            symbol="BTC/USDT",
            fallback_price=45000.0,
            cache_manager=cache_manager
        )

        assert price == 48000.0
        assert source == "cache"

    def test_safe_get_float(self):
        """Test extraction float depuis dict"""
        data = {'price': '50000.5', 'volume': 1000}

        assert APIHelper.safe_get_float(data, 'price', 0.0) == 50000.5
        assert APIHelper.safe_get_float(data, 'volume', 0.0) == 1000.0
        assert APIHelper.safe_get_float(data, 'missing', 99.9) == 99.9

    def test_safe_get_float_nan(self):
        """Test gestion NaN"""
        data = {'price': float('nan')}

        price = APIHelper.safe_get_float(data, 'price', 0.0)
        assert price == 0.0

    def test_safe_get_int(self):
        """Test extraction int depuis dict"""
        data = {'count': '10', 'value': 20.5}

        assert APIHelper.safe_get_int(data, 'count', 0) == 10
        assert APIHelper.safe_get_int(data, 'value', 0) == 20
        assert APIHelper.safe_get_int(data, 'missing', 99) == 99

    def test_extract_price_from_ticker(self):
        """Test extraction prix depuis ticker"""
        ticker = {'lastPrice': 50000.0, 'volume': 1000}

        price = APIHelper.extract_price_from_ticker(ticker, "BTC/USDT")
        assert price == 50000.0

        # Test avec clé alternative
        ticker2 = {'last': 50001.0}
        price = APIHelper.extract_price_from_ticker(ticker2)
        assert price == 50001.0

    def test_extract_price_from_ticker_none(self):
        """Test ticker None"""
        price = APIHelper.extract_price_from_ticker(None, "BTC/USDT")
        assert price is None

    def test_check_nan(self):
        """Test vérification NaN"""
        assert APIHelper.check_nan(100.0, 0.0) == 100.0
        assert APIHelper.check_nan(float('nan'), 99.0) == 99.0


class TestMarketHelper:
    """Tests pour MarketHelper"""

    def test_extract_scalability_data(self):
        """Test extraction données scalabilité"""
        pair = {
            'spread': 0.05,
            'bookDepth': 500000,
            'balanceScore': 0.8,
            'bidVol': 250000,
            'askVol': 250000,
        }

        data = MarketHelper.extract_scalability_data(pair, "BTC/USDT")

        assert data['spread_pct'] == 0.05
        assert data['depth'] == 500000
        assert data['balance'] == 0.8
        assert data['bid_vol'] == 250000
        assert data['ask_vol'] == 250000

    def test_extract_scalability_data_nan_spread(self):
        """Test gestion spread NaN"""
        pair = {
            'spread': float('nan'),
            'bookDepth': 0,
            'bidVol': 100000,
            'askVol': 150000,
        }

        data = MarketHelper.extract_scalability_data(pair)

        assert data['spread_pct'] == 0  # NaN → 0
        assert data['depth'] == 250000  # Calculé depuis bidVol + askVol

    def test_validate_volume(self):
        """Test validation volume"""
        assert MarketHelper.validate_volume(2000000, 1000000) is True
        assert MarketHelper.validate_volume(500000, 1000000) is False
        assert MarketHelper.validate_volume(None, 1000000) is False

    def test_validate_liquidity_score(self):
        """Test validation liquidity score"""
        assert MarketHelper.validate_liquidity_score(0.7, 0.5) is True
        assert MarketHelper.validate_liquidity_score(0.3, 0.5) is False

    def test_calculate_liquidity_score(self):
        """Test calcul liquidity score"""
        score = MarketHelper.calculate_liquidity_score(
            bid_vol=100000,
            ask_vol=100000,
            spread_pct=0.05,
            book_depth=1000000
        )

        # Balance parfait (bid=ask) + spread faible + depth OK → score élevé
        assert score > 0.8

    def test_format_volume(self):
        """Test formatage volume"""
        assert MarketHelper.format_volume(1500000) == "1.5M"
        assert MarketHelper.format_volume(500000) == "500K"
        assert MarketHelper.format_volume(500) == "500"

    def test_extract_ticker_data(self):
        """Test extraction ticker data"""
        ticker = {
            'lastPrice': 50000,
            'quoteVolume': 5000000,
            'high': 51000,
            'low': 49000,
            'percentage': 2.5,
        }

        data = MarketHelper.extract_ticker_data(ticker)

        assert data['price'] == 50000
        assert data['volume'] == 5000000
        assert data['high'] == 51000
        assert data['low'] == 49000
        assert data['change_pct'] == 2.5


class TestStatsHelper:
    """Tests pour StatsHelper"""

    def test_calculate_stats_empty_trades(self):
        """Test stats avec liste vide"""
        stats = StatsHelper.calculate_stats_from_trades([])

        assert stats['total_trades'] == 0
        assert stats['wins'] == 0
        assert stats['winrate'] == 0.0

    def test_calculate_stats_from_trades(self):
        """Test calcul stats depuis trades"""
        trades = [
            {'pnl_usdt': 100, 'pnl_pct': 2.0},
            {'pnl_usdt': -50, 'pnl_pct': -1.0},
            {'pnl_usdt': 150, 'pnl_pct': 3.0},
            {'pnl_usdt': 200, 'pnl_pct': 4.0},
            {'pnl_usdt': -75, 'pnl_pct': -1.5},
        ]

        stats = StatsHelper.calculate_stats_from_trades(trades)

        assert stats['total_trades'] == 5
        assert stats['wins'] == 3
        assert stats['losses'] == 2
        assert stats['winrate'] == 60.0  # 3/5 * 100
        assert stats['total_pnl_usdt'] == 325  # 100-50+150+200-75
        assert stats['avg_pnl_pct'] == (2.0 - 1.0 + 3.0 + 4.0 - 1.5) / 5
        assert stats['best_trade'] == 4.0
        assert stats['worst_trade'] == -1.5

    def test_calculate_sharpe_ratio(self):
        """Test calcul Sharpe ratio"""
        trades = [
            {'pnl_pct': 2.0},
            {'pnl_pct': -1.0},
            {'pnl_pct': 3.0},
            {'pnl_pct': 1.5},
        ]

        sharpe = StatsHelper.calculate_sharpe_ratio(trades, risk_free_rate=0.0)

        # Sharpe devrait être positif (rendement moyen positif)
        assert sharpe > 0

    def test_calculate_max_drawdown(self):
        """Test calcul max drawdown"""
        trades = [
            {'pnl_usdt': 100},  # +100
            {'pnl_usdt': 50},   # +150
            {'pnl_usdt': -200}, # -50 (DD de 200)
            {'pnl_usdt': -50},  # -100 (DD de 250)
            {'pnl_usdt': 300},  # +200 (recovery)
        ]

        dd_data = StatsHelper.calculate_max_drawdown(trades)

        # Max DD devrait être > 100% (peak 150, low -100)
        assert dd_data['max_drawdown_usdt'] == 250

    def test_calculate_profit_factor(self):
        """Test calcul profit factor"""
        trades = [
            {'pnl_usdt': 100},
            {'pnl_usdt': 200},
            {'pnl_usdt': -50},
            {'pnl_usdt': -25},
        ]

        pf = StatsHelper.calculate_profit_factor(trades)

        # Gross profit = 300, Gross loss = 75
        assert pf == 300 / 75  # = 4.0

    def test_get_trade_pnl(self):
        """Test extraction PnL depuis trade"""
        trade = {'pnl_usdt': 100, 'pnl_pct': 2.0}

        assert StatsHelper.get_trade_pnl(trade, 'usdt') == 100
        assert StatsHelper.get_trade_pnl(trade, 'pct') == 2.0

        # Test format alternatif
        trade2 = {'netPnlUSDT': 150, 'netPnlPct': 3.0}
        assert StatsHelper.get_trade_pnl(trade2, 'usdt') == 150


class TestPositionHelper:
    """Tests pour PositionHelper"""

    def test_position_proxy(self):
        """Test PositionProxy"""
        data = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry': 50000.0,
            'quantity': 0.01,
            'take_profit': 51000.0,
            'stop_loss': 49000.0,
        }

        proxy = PositionProxy(data)

        assert proxy.symbol == 'BTC/USDT'
        assert proxy.side == 'LONG'
        assert proxy.entry == 50000.0
        assert proxy.take_profit == 51000.0

    def test_normalize_position_from_dict(self):
        """Test normalisation depuis dict"""
        position_dict = {'symbol': 'BTC/USDT', 'entry': 50000.0}

        position = PositionHelper.normalize_position(position_dict)

        assert hasattr(position, 'symbol')
        assert position.symbol == 'BTC/USDT'

    def test_normalize_position_from_json(self):
        """Test normalisation depuis JSON string"""
        position_json = json.dumps({'symbol': 'ETH/USDT', 'entry': 3000.0})

        position = PositionHelper.normalize_position(position_json)

        assert position.symbol == 'ETH/USDT'
        assert position.entry == 3000.0

    def test_normalize_position_from_object(self):
        """Test normalisation depuis object (déjà normalisé)"""
        position_obj = PositionProxy({'symbol': 'SOL/USDT', 'entry': 100.0})

        position = PositionHelper.normalize_position(position_obj)

        assert position is position_obj  # Même objet retourné

    def test_to_dict_from_proxy(self):
        """Test conversion vers dict depuis proxy"""
        data = {'symbol': 'BTC/USDT', 'entry': 50000.0}
        proxy = PositionProxy(data)

        position_dict = PositionHelper.to_dict(proxy)

        assert isinstance(position_dict, dict)
        assert position_dict['symbol'] == 'BTC/USDT'

    def test_to_dict_from_dict(self):
        """Test conversion vers dict (déjà dict)"""
        data = {'symbol': 'BTC/USDT', 'entry': 50000.0}

        position_dict = PositionHelper.to_dict(data)

        assert position_dict is data  # Même dict retourné

    def test_extract_key_fields(self):
        """Test extraction champs clés"""
        position = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry': 50000.0,
            'quantity': 0.01,
            'leverage': 10,
            'take_profit': 51000.0,
            'stop_loss': 49000.0,
        }

        fields = PositionHelper.extract_key_fields(position)

        assert fields['symbol'] == 'BTC/USDT'
        assert fields['side'] == 'LONG'
        assert fields['entry'] == 50000.0
        assert fields['quantity'] == 0.01
        assert fields['leverage'] == 10

    def test_calculate_pnl_long(self):
        """Test calcul PnL LONG"""
        position = {
            'entry': 50000.0,
            'quantity': 0.01,
            'side': 'LONG',
            'leverage': 10,
        }

        pnl = PositionHelper.calculate_pnl(position, current_price=51000.0, include_fees=False)

        # +2% sans leverage = +20% avec leverage 10x
        assert pnl['gross_pnl_pct'] == pytest.approx(20.0, rel=0.01)

    def test_calculate_pnl_short(self):
        """Test calcul PnL SHORT"""
        position = {
            'entry': 50000.0,
            'quantity': 0.01,
            'side': 'SHORT',
            'leverage': 10,
        }

        pnl = PositionHelper.calculate_pnl(position, current_price=49000.0, include_fees=False)

        # +2% sans leverage = +20% avec leverage 10x
        assert pnl['gross_pnl_pct'] == pytest.approx(20.0, rel=0.01)

    def test_calculate_pnl_with_fees(self):
        """Test calcul PnL avec fees"""
        position = {
            'entry': 50000.0,
            'quantity': 0.01,
            'side': 'LONG',
            'leverage': 1,
        }

        pnl_no_fees = PositionHelper.calculate_pnl(position, 51000.0, include_fees=False)
        pnl_with_fees = PositionHelper.calculate_pnl(position, 51000.0, include_fees=True)

        # PnL net doit être inférieur au PnL brut
        assert pnl_with_fees['net_pnl_pct'] < pnl_no_fees['gross_pnl_pct']

    def test_is_long(self):
        """Test vérification LONG"""
        assert PositionHelper.is_long({'side': 'LONG'}) is True
        assert PositionHelper.is_long({'side': 'SHORT'}) is False

    def test_is_short(self):
        """Test vérification SHORT"""
        assert PositionHelper.is_short({'side': 'SHORT'}) is True
        assert PositionHelper.is_short({'side': 'LONG'}) is False

    def test_format_position_summary(self):
        """Test formatage résumé position"""
        position = {
            'symbol': 'BTC/USDT',
            'side': 'LONG',
            'entry': 50000.0,
            'leverage': 10,
            'take_profit': 51000.0,
            'stop_loss': 49000.0,
        }

        summary = PositionHelper.format_position_summary(position)

        assert 'BTC/USDT' in summary
        assert 'LONG' in summary
        assert '50000.00' in summary
        assert 'x10' in summary
        assert 'TP: 51000.00' in summary
        assert 'SL: 49000.00' in summary


class TestDataLoggerHelper:
    """Tests pour DataLoggerHelper"""

    def test_is_available_when_not_imported(self):
        """Test availability quand DataLogger pas importé"""
        # Reset instance
        DataLoggerHelper.reset_instance()

        # Should return False si backend.ml.data_logger non dispo
        available = DataLoggerHelper.is_available()

        # Peut être True ou False selon environnement
        assert isinstance(available, bool)

    @pytest.mark.asyncio
    async def test_safe_log_scan_returns_none_when_unavailable(self):
        """Test safe_log_scan retourne None si unavailable"""
        # Mock _get_data_logger to return None
        with patch.object(DataLoggerHelper, '_get_data_logger', return_value=None):
            result = await DataLoggerHelper.safe_log_scan(
                symbol="BTC/USDT",
                price=50000.0
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_safe_log_scan_with_mock_logger(self):
        """Test safe_log_scan avec mock logger"""
        # Mock DataLogger
        mock_logger = Mock()
        mock_logger.is_running = True
        mock_logger.log_scan = AsyncMock(return_value="scan-uuid-123")

        with patch.object(DataLoggerHelper, '_get_data_logger', return_value=mock_logger):
            result = await DataLoggerHelper.safe_log_scan(
                symbol="BTC/USDT",
                price=50000.0
            )

            assert result == "scan-uuid-123"
            mock_logger.log_scan.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
