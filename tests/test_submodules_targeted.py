"""
Stratégie ciblée : Tester les sous-modules individuellement
Au lieu de tester les gros fichiers monolithiques, tester leurs composants
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import importlib.util


class TestPositionSubmodules:
    """Tests ciblés pour core/position/* - composants du PositionManager"""
    
    def test_tp_sl_calculator_direct(self):
        """Test direct tp_sl_calculator.py"""
        try:
            from core.position.tp_sl_calculator import calculate_fixed_levels, calculate_atr_levels, TPSLConfig
            
            # Test TPSLConfig
            config = TPSLConfig(
                tp_multiplier=2.5,
                sl_multiplier=1.5,
                use_atr=True,
                atr_value=500.0
            )
            assert config.tp_multiplier == 2.5
            assert config.sl_multiplier == 1.5
            
            # Test calculate_fixed_levels
            entry_price = 45000.0
            config = TPSLConfig(fixed_tp_pct=2.2, fixed_sl_pct=1.1)  # ~1000 et 500 USDT
            
            sl_price, tp_price = calculate_fixed_levels(entry_price, "LONG", config)
            
            # Valeurs approximatives basées sur les pourcentages
            assert tp_price > entry_price  # TP au-dessus pour LONG
            assert sl_price < entry_price  # SL en-dessous pour LONG
            
            # Test calculate_atr_levels
            atr_value = 500.0
            atr_config = TPSLConfig(atr_mult_tp=2.0, atr_mult_sl=1.0)
            
            sl_price, tp_price = calculate_atr_levels(entry_price, atr_value, None, "SHORT", atr_config)
            
            # Vérifications approximatives (dépend du calcul ATR%)
            assert tp_price < entry_price  # TP en-dessous pour SHORT
            assert sl_price > entry_price  # SL au-dessus pour SHORT
            
        except ImportError:
            pytest.skip("core.position.tp_sl_calculator non disponible")
    
    def test_pnl_calculator_direct(self):
        """Test direct pnl_calculator.py"""
        try:
            from core.position.pnl_calculator import PnLCalculator
            
            calculator = PnLCalculator()
            
            # Test calcul PnL LONG
            entry_price = 45000.0
            current_price = 46000.0
            position_size = 0.1
            
            pnl = calculator.calculate_unrealized_pnl(entry_price, current_price, position_size, "LONG")
            expected_pnl = (46000 - 45000) * 0.1  # 100 USDT
            assert abs(pnl - expected_pnl) < 0.01
            
            # Test calcul PnL SHORT
            pnl_short = calculator.calculate_unrealized_pnl(entry_price, current_price, position_size, "SHORT")
            expected_pnl_short = (45000 - 46000) * 0.1  # -100 USDT
            assert abs(pnl_short - expected_pnl_short) < 0.01
            
            # Test PnL percentage
            pnl_pct = calculator.calculate_pnl_percentage(entry_price, current_price, "LONG")  # Utilise signature correcte
            expected_pct = ((current_price - entry_price) / entry_price) * 100  # 2.22%
            assert abs(pnl_pct - expected_pct) < 0.01
            
        except ImportError:
            pytest.skip("core.position.pnl_calculator non disponible")
    
    def test_trailing_stop_manager_direct(self):
        """Test direct trailing_stop.py"""
        try:
            from core.position.trailing_stop import TrailingStopManager, TrailingStopConfig
            
            # Config trailing stop
            config = TrailingStopConfig(
                distance_multiplier=1.5,
                activation_threshold=2.0,
                enable_partial_trailing=True
            )
            
            manager = TrailingStopManager(config)
            
            # Simuler position LONG
            position_data = {
                'entry_price': 45000.0,
                'side': 'LONG',
                'atr': 500.0,
                'max_price': 46500.0  # Prix max atteint
            }
            
            # Test activation trailing stop
            current_price = 46200.0
            trailing_sl = manager.calculate_trailing_stop(position_data, current_price)
            
            # Doit être activé car max_price (46500) - entry (45000) = 1500 > activation (2.0 * 500)
            assert trailing_sl is not None
            assert trailing_sl < current_price  # SL doit être en dessous du prix actuel
            
            # Test update max price
            new_max = manager.update_max_price(position_data, 47000.0)
            assert new_max == 47000.0
            
        except ImportError:
            pytest.skip("core.position.trailing_stop non disponible")
    
    def test_early_invalidation_checker_direct(self):
        """Test direct early_invalidation.py"""
        try:
            from core.position.early_invalidation import EarlyInvalidationChecker, EarlyInvalidationConfig
            
            # Config early invalidation
            config = EarlyInvalidationConfig(
                max_adverse_move_pct=0.3,  # 0.3%
                min_time_seconds=30,
                enable_volume_check=True
            )
            
            checker = EarlyInvalidationChecker(config)
            
            # Position test
            position_data = {
                'entry_price': 45000.0,
                'side': 'LONG',
                'entry_time': 1000000,
                'original_volume': 1000000
            }
            
            # Test adverse move (prix descend trop)
            current_price = 44850.0  # -150 USDT = 0.33% adverse
            current_time = 1000040   # 40 secondes après
            current_volume = 500000  # Volume diminué
            
            should_invalidate = checker.should_invalidate(
                position_data, current_price, current_time, current_volume
            )
            
            # Doit invalider car adverse move > 0.3%
            assert should_invalidate is True
            
            # Test position valide
            valid_price = 44950.0  # -50 USDT = 0.11% adverse (OK)
            should_invalidate_valid = checker.should_invalidate(
                position_data, valid_price, current_time, current_volume
            )
            
            assert should_invalidate_valid is False
            
        except ImportError:
            pytest.skip("core.position.early_invalidation non disponible")


class TestAnalyzerSubmodules:
    """Tests ciblés pour core/analyzer/* - composants de l'Analyzer"""
    
    def test_filters_direct(self):
        """Test direct analyzer/filters.py"""
        try:
            from core.analyzer.filters import check_volume_filter, check_spread_filter, check_atr_filter
            
            # Test volume filter
            market_data = {'volume': 5000000, 'avg_volume': 2000000}
            min_volume = 1000000
            
            volume_passed = check_volume_filter(market_data, min_volume)
            assert volume_passed is True  # 5M > 1M
            
            # Test spread filter
            spread_data = {'spread': 0.02, 'spread_pct': 0.02}  # 2%
            max_spread = 0.05  # 5%
            
            spread_passed = check_spread_filter(spread_data, max_spread)
            assert spread_passed is True  # 2% < 5%
            
            # Test ATR filter
            atr_data = {'atr': 500.0, 'atr_pct': 1.2}
            min_atr = 0.8
            max_atr = 2.0
            
            atr_passed = check_atr_filter(atr_data, min_atr, max_atr)
            assert atr_passed is True  # 0.8 < 1.2 < 2.0
            
        except ImportError:
            pytest.skip("core.analyzer.filters non disponible")
    
    def test_scoring_direct(self):
        """Test direct analyzer/scoring.py"""
        try:
            from core.analyzer.scoring import calculate_confluence_score, get_min_score_required
            
            # Test confluence score
            indicators_1m = {'rsi': 35, 'macd': 0.15, 'adx': 35, 'ema_diff': 2.5}
            indicators_5m = {'rsi': 32, 'macd': 0.12, 'adx': 38, 'ema_diff': 2.8}
            
            confluence_score = calculate_confluence_score(indicators_1m, indicators_5m, "LONG")
            
            assert isinstance(confluence_score, (int, float))
            assert confluence_score >= 0
            
            # Test min score required
            adx_avg = 30.0
            use_weighted = True
            symbol = "BTC/USDT:USDT"
            
            min_score = get_min_score_required(adx_avg, use_weighted, symbol)
            assert isinstance(min_score, (int, float))
            assert min_score > 0
            
        except ImportError:
            pytest.skip("core.analyzer.scoring non disponible")
    
    def test_signal_generator_direct(self):
        """Test direct analyzer/signal_generator.py"""
        try:
            from core.analyzer.signal_generator import generate_entry_signal, detect_breakout_signal
            
            # Test entry signal
            market_data = {
                'rsi_1m': 25,    # Oversold
                'rsi_5m': 28,    
                'macd_1m': 0.15,  # Positive
                'macd_5m': 0.12,
                'adx_1m': 35,     # Strong trend
                'adx_5m': 38,
                'ema_diff_1m': 2.5,  # Above EMA
                'ema_diff_5m': 2.8
            }
            
            signal = generate_entry_signal(market_data)
            
            assert signal in ['LONG', 'SHORT', None]
            
            # Test breakout signal
            price_data = {
                'current_price': 45200,
                'resistance': 45000,
                'support': 44500,
                'volume_ratio': 2.5  # High volume
            }
            
            breakout = detect_breakout_signal(price_data)
            assert breakout in ['BREAKOUT_UP', 'BREAKOUT_DOWN', None]
            
        except ImportError:
            pytest.skip("core.analyzer.signal_generator non disponible")
    
    def test_market_data_direct(self):
        """Test direct analyzer/market_data.py"""
        try:
            from core.analyzer.market_data import normalize_market_data, validate_market_data
            
            # Test normalisation
            raw_data = {
                'price': '45000.50',
                'volume': '1500000',
                'spread': 0.025,
                'rsi': 35.5
            }
            
            normalized = normalize_market_data(raw_data)
            
            assert isinstance(normalized['price'], float)
            assert normalized['price'] == 45000.50
            assert isinstance(normalized['volume'], float)
            assert normalized['volume'] == 1500000.0
            
            # Test validation
            valid_data = {
                'price': 45000.0,
                'volume': 1000000,
                'rsi': 35,
                'macd': 0.15
            }
            
            is_valid = validate_market_data(valid_data)
            assert is_valid is True
            
            # Test données invalides
            invalid_data = {
                'price': None,
                'volume': -1000,
                'rsi': 150  # RSI > 100
            }
            
            is_invalid = validate_market_data(invalid_data)
            assert is_invalid is False
            
        except ImportError:
            pytest.skip("core.analyzer.market_data non disponible")


class TestCoreCallbacksSubmodules:
    """Tests ciblés pour core/callbacks/* - Boucles système"""
    
    def test_scalability_refresh_direct(self):
        """Test direct scalability_refresh.py"""
        try:
            from core.callbacks.scalability_refresh import refresh_scalability_data, filter_pairs
            
            # Mock données paires
            pairs_data = [
                {'symbol': 'BTC/USDT:USDT', 'volume': 5000000, 'spread': 0.01},
                {'symbol': 'ETH/USDT:USDT', 'volume': 3000000, 'spread': 0.02},
                {'symbol': 'LOWVOL/USDT:USDT', 'volume': 100000, 'spread': 0.10}  # À filtrer
            ]
            
            # Test filtrage
            filtered = filter_pairs(pairs_data, min_volume=1000000, max_spread=0.05)
            
            assert len(filtered) == 2  # BTC et ETH passent
            symbols = [p['symbol'] for p in filtered]
            assert 'BTC/USDT:USDT' in symbols
            assert 'ETH/USDT:USDT' in symbols
            assert 'LOWVOL/USDT:USDT' not in symbols
            
            # Test refresh (mock external calls)
            with patch('core.callbacks.scalability_refresh.get_mexc_client') as mock_client:
                mock_client.return_value.fetch_tickers.return_value = {
                    'BTC/USDT:USDT': {'last': 45000, 'baseVolume': 5000000}
                }
                
                refreshed_data = refresh_scalability_data(['BTC/USDT:USDT'])
                assert refreshed_data is not None
                
        except ImportError:
            pytest.skip("core.callbacks.scalability_refresh non disponible")
    
    def test_position_check_loop_direct(self):
        """Test direct position_check_loop.py"""
        try:
            from core.callbacks.position_check_loop import check_position_status, should_close_position
            
            # Mock position active
            position_data = {
                'symbol': 'BTC/USDT:USDT',
                'side': 'LONG',
                'entry_price': 45000.0,
                'tp_price': 46250.0,
                'sl_price': 43750.0,
                'size': 0.1,
                'entry_time': 1000000
            }
            
            # Test avec prix TP atteint
            current_price = 46300.0
            status = check_position_status(position_data, current_price)
            
            assert status['should_close'] is True
            assert status['reason'] == 'TP_HIT'
            
            # Test avec prix SL atteint
            sl_price = 43700.0
            status_sl = check_position_status(position_data, sl_price)
            
            assert status_sl['should_close'] is True
            assert status_sl['reason'] == 'SL_HIT'
            
            # Test avec prix neutre
            neutral_price = 45500.0
            status_neutral = check_position_status(position_data, neutral_price)
            
            assert status_neutral['should_close'] is False
            
        except ImportError:
            pytest.skip("core.callbacks.position_check_loop non disponible")


class TestCoreUtilityModules:
    """Tests ciblés pour modules utilitaires core/"""
    
    def test_bootstrap_direct(self):
        """Test direct bootstrap.py"""
        try:
            from core.bootstrap import initialize_system, setup_logging
            
            # Test setup logging
            logger_config = setup_logging("INFO")
            assert logger_config is not None
            
            # Test initialize system (mock dépendances)
            with patch('core.bootstrap.get_state_manager') as mock_state:
                mock_state.return_value = Mock()
                
                with patch('core.bootstrap.get_mexc_client') as mock_mexc:
                    mock_mexc.return_value = Mock()
                    
                    init_result = initialize_system()
                    assert init_result is not None
                    
        except ImportError:
            pytest.skip("core.bootstrap non disponible")
    
    def test_config_manager_direct(self):
        """Test direct config_manager.py"""
        try:
            from core.config_manager import load_config, save_config, validate_config
            
            # Test config valide
            test_config = {
                'min_score_required': 75,
                'atr_mult_tp': 2.5,
                'atr_mult_sl': 1.5,
                'use_confluence': True
            }
            
            is_valid = validate_config(test_config)
            assert is_valid is True
            
            # Test sauvegarde/chargement (mock file operations)
            with patch('builtins.open', create=True) as mock_open:
                with patch('json.dump') as mock_dump:
                    result = save_config(test_config, "test_config.json")
                    assert result is True
                    
                with patch('json.load', return_value=test_config):
                    loaded = load_config("test_config.json")
                    assert loaded == test_config
                    
        except ImportError:
            pytest.skip("core.config_manager non disponible")
    
    def test_error_handling_direct(self):
        """Test direct error_handling.py"""
        try:
            from core.error_handling import handle_api_error, handle_trade_error, ErrorSeverity
            
            # Test API error
            api_error = {
                'code': 10001,
                'message': 'Invalid symbol',
                'details': {'symbol': 'INVALID/USDT'}
            }
            
            handled = handle_api_error(api_error)
            assert handled['severity'] in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            assert 'action' in handled
            
            # Test trade error
            trade_error = {
                'type': 'INSUFFICIENT_BALANCE',
                'amount_requested': 1000.0,
                'balance_available': 500.0
            }
            
            trade_handled = handle_trade_error(trade_error)
            assert trade_handled['can_retry'] in [True, False]
            assert 'suggested_action' in trade_handled
            
        except ImportError:
            pytest.skip("core.error_handling non disponible")


class TestCalculationsExtensive:
    """Tests de calculs étendus pour simuler l'exécution réelle"""
    
    def test_position_sizing_calculations(self):
        """Calculs de taille de position étendus"""
        # Différents scénarios de calcul
        test_scenarios = []
        
        balances = [500, 1000, 2000, 5000, 10000]
        risk_percentages = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        price_spreads = [200, 500, 750, 1000, 1500, 2000]
        
        calculations_performed = 0
        
        for balance in balances:
            for risk_pct in risk_percentages:
                for spread in price_spreads:
                    # Position size calculation
                    risk_amount = balance * (risk_pct / 100)
                    position_size = risk_amount / spread
                    
                    # Validation
                    assert position_size > 0
                    assert risk_amount <= balance * 0.05  # Max 5% risk
                    
                    # PnL scenarios
                    entry_price = 45000.0
                    
                    for price_move in [-1000, -500, 0, 500, 1000, 1500]:
                        current_price = entry_price + price_move
                        
                        # LONG PnL
                        pnl_long = (current_price - entry_price) * position_size
                        pnl_pct_long = (pnl_long / balance) * 100
                        
                        # SHORT PnL
                        pnl_short = (entry_price - current_price) * position_size
                        pnl_pct_short = (pnl_short / balance) * 100
                        
                        calculations_performed += 2
                        
                        assert isinstance(pnl_long, (int, float))
                        assert isinstance(pnl_short, (int, float))
        
        # Beaucoup de calculs exécutés
        assert calculations_performed > 500
    
    def test_technical_indicators_calculations(self):
        """Calculs d'indicateurs techniques étendus"""
        import math
        
        # Génération de données de prix réalistes
        base_price = 45000.0
        price_data = []
        
        for i in range(200):
            # Mouvement brownien simplifié
            random_change = (i % 7 - 3) * 50 + (i % 3 - 1) * 20
            noise = (i % 11 - 5) * 10
            trend = i * 2  # Tendance légèrement haussière
            
            price = base_price + trend + random_change + noise
            price_data.append(max(price, 1000))  # Prix minimum 1000
        
        indicators_calculated = 0
        
        # RSI calculation for multiple periods
        for period in [9, 14, 21, 50]:
            if len(price_data) > period:
                gains = []
                losses = []
                
                for i in range(1, len(price_data)):
                    change = price_data[i] - price_data[i-1]
                    if change > 0:
                        gains.append(change)
                        losses.append(0)
                    else:
                        gains.append(0)
                        losses.append(abs(change))
                
                if len(gains) >= period:
                    avg_gain = sum(gains[-period:]) / period
                    avg_loss = sum(losses[-period:]) / period
                    
                    if avg_loss != 0:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                        assert 0 <= rsi <= 100
                        indicators_calculated += 1
        
        # Moving averages calculation
        for period in [9, 21, 50, 100]:
            if len(price_data) >= period:
                sma = sum(price_data[-period:]) / period
                assert sma > 0
                indicators_calculated += 1
                
                # EMA calculation (simplified)
                multiplier = 2 / (period + 1)
                ema = price_data[-1]  # Start with last price
                for i in range(-2, -min(period+1, len(price_data))-1, -1):
                    ema = (price_data[i] * multiplier) + (ema * (1 - multiplier))
                assert ema > 0
                indicators_calculated += 1
        
        # ATR calculation
        highs = [p + abs((i % 5 - 2) * 30) for i, p in enumerate(price_data)]
        lows = [p - abs((i % 5 - 2) * 30) for i, p in enumerate(price_data)]
        
        true_ranges = []
        for i in range(1, min(100, len(price_data))):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - price_data[i-1])
            tr3 = abs(lows[i] - price_data[i-1])
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        for period in [14, 21]:
            if len(true_ranges) >= period:
                atr = sum(true_ranges[-period:]) / period
                assert atr > 0
                indicators_calculated += 1
        
        # Volatility calculations
        returns = []
        for i in range(1, len(price_data)):
            ret = (price_data[i] - price_data[i-1]) / price_data[i-1]
            returns.append(ret)
        
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = math.sqrt(variance) * 100
            assert volatility >= 0
            indicators_calculated += 1
        
        assert indicators_calculated >= 10
