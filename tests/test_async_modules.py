#!/usr/bin/env python3
"""
Comprehensive Async Tests for Trade Cursor v7.0
Target: 95% coverage for async modules
- Market Data (market_data.py)
- Correlation (correlation.py)
- Scanner (scanner.py)
- Analytics Database (analytics_database.py)
- Callbacks (scanner_loop.py, etc.)
"""

import pytest
import sys
import os
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from typing import Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules to test
from core.analyzer.market_data import check_spread, check_orderbook_imbalance
from core.analyzer.correlation import check_static_correlation, check_dynamic_correlation
from core.scanner import ScalabilityScanner
from core.analytics_database import AnalyticsDatabase, get_analytics_db
from core.callbacks.scanner_loop import (
    scanner_loop_callback,
    scan_pair_for_setup,
    set_scanner,
    set_analyzer,
    set_position_manager,
    set_price_provider,
    set_app_state,
    set_socketio,
    set_scanner_lock
)
from config import TRADING_CONFIG


# ============================================================================
# MARKET DATA TESTS (market_data.py)
# ============================================================================

class TestMarketDataAsync:
    """Tests async pour market_data.py"""

    @pytest.mark.asyncio
    async def test_check_spread_success_excellent(self):
        """Test spread check avec spread excellent (< 0.01%)"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0], [49990.0, 20.0]],
            'asks': [[50005.0, 15.0], [50010.0, 25.0]]
        })

        spread_cache = {}

        result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

        assert result['valid'] is True
        assert result['spread_pct'] < 0.01
        assert result['quality'] == 'EXCELLENT'
        assert 'BTC/USDT:USDT' in spread_cache

    @pytest.mark.asyncio
    async def test_check_spread_cached(self):
        """Test spread check avec cache valide"""
        mock_client = AsyncMock()

        # Pré-remplir le cache
        spread_cache = {
            'BTC/USDT:USDT': {
                'timestamp': time.time(),
                'data': {'valid': True, 'spread_pct': 0.015, 'max_allowed': 0.03, 'quality': 'GOOD'}
            }
        }

        result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

        # Doit utiliser le cache, pas appeler l'API
        mock_client.fetch_order_book.assert_not_called()
        assert result['valid'] is True
        assert result['quality'] == 'GOOD'

    @pytest.mark.asyncio
    async def test_check_spread_too_wide(self):
        """Test spread check avec spread trop large (> 0.03% en mode FIXE)"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0]],
            'asks': [[50025.0, 15.0]]  # Spread = 0.05%
        })

        spread_cache = {}

        # 🔥 FIX: Mocker TRADING_CONFIG pour forcer mode FIXE (seuil 0.03%)
        # En mode ATR, le seuil est 0.06% donc 0.05% serait valide
        with patch('core.analyzer.market_data.TRADING_CONFIG', {'tp_sl_mode': 'FIXE'}):
            result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

        assert result['valid'] is False
        assert result['spread_pct'] > 0.03
        assert result['quality'] == 'POOR'

    @pytest.mark.asyncio
    async def test_check_spread_empty_orderbook(self):
        """Test spread check avec orderbook vide"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [],
            'asks': []
        })

        spread_cache = {}

        result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

        assert result['valid'] is False
        assert result['spread_pct'] == 999
        assert result['quality'] == 'UNKNOWN'

    @pytest.mark.asyncio
    async def test_check_spread_error_handling(self):
        """Test spread check avec erreur API"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(side_effect=Exception("API Error"))

        spread_cache = {}

        result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

        assert result['valid'] is False
        assert result['quality'] == 'ERROR'

    @pytest.mark.asyncio
    async def test_check_spread_atr_mode(self):
        """Test spread check en mode ATR (seuil plus élevé)"""
        # Modifier temporairement la config
        original_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
        TRADING_CONFIG['tp_sl_mode'] = 'ATR'

        try:
            mock_client = AsyncMock()
            mock_client.fetch_order_book = AsyncMock(return_value={
                'bids': [[50000.0, 10.0]],
                'asks': [[50025.0, 15.0]]  # Spread = 0.05%
            })

            spread_cache = {}

            result = await check_spread(mock_client, 'BTC/USDT:USDT', spread_cache)

            # En mode ATR, max_spread = 0.06%, donc 0.05% devrait passer
            assert result['max_allowed'] == 0.06
            assert result['valid'] is True
        finally:
            TRADING_CONFIG['tp_sl_mode'] = original_mode

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_long_valid(self):
        """Test orderbook imbalance pour LONG (ratio >= 1.1)"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0], [49990.0, 8.0]],  # bid_value = 500000 + 399920 = 899920
            'asks': [[50010.0, 5.0], [50020.0, 5.0]]    # ask_value = 250050 + 250100 = 500150
        })

        orderbook_cache = {}

        result = await check_orderbook_imbalance(mock_client, 'BTC/USDT:USDT', 'LONG', orderbook_cache)

        assert result['valid'] is True
        assert result['ratio'] >= 1.1
        assert result['quality'] in ['EXCELLENT', 'GOOD', 'ACCEPTABLE']

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_short_valid(self):
        """Test orderbook imbalance pour SHORT (ratio <= 0.95)"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 5.0], [49990.0, 5.0]],    # bid_value = 250000 + 249950 = 499950
            'asks': [[50010.0, 10.0], [50020.0, 10.0]]   # ask_value = 500100 + 500200 = 1000300
        })

        orderbook_cache = {}

        result = await check_orderbook_imbalance(mock_client, 'BTC/USDT:USDT', 'SHORT', orderbook_cache)

        assert result['valid'] is True
        assert result['ratio'] <= 0.95
        assert result['quality'] in ['EXCELLENT', 'GOOD', 'ACCEPTABLE']

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_cached(self):
        """Test orderbook imbalance avec cache valide"""
        mock_client = AsyncMock()

        # Pré-remplir le cache
        orderbook_cache = {
            'BTC/USDT:USDT_LONG': {
                'timestamp': time.time(),
                'data': {'valid': True, 'ratio': 1.5, 'quality': 'EXCELLENT', 'bid_value': 1000000, 'ask_value': 666667}
            }
        }

        result = await check_orderbook_imbalance(mock_client, 'BTC/USDT:USDT', 'LONG', orderbook_cache)

        # Doit utiliser le cache
        mock_client.fetch_order_book.assert_not_called()
        assert result['valid'] is True
        assert result['ratio'] == 1.5

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_none_orderbook(self):
        """Test orderbook imbalance avec orderbook None"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value=None)

        orderbook_cache = {}

        result = await check_orderbook_imbalance(mock_client, 'BTC/USDT:USDT', 'LONG', orderbook_cache)

        assert result['valid'] is True  # Retourne True pour éviter rejets systématiques
        assert result['ratio'] == 1.0
        assert result['quality'] == 'UNKNOWN'

    @pytest.mark.asyncio
    async def test_check_orderbook_imbalance_empty_bids_asks(self):
        """Test orderbook imbalance avec bids/asks vides"""
        mock_client = AsyncMock()
        mock_client.fetch_order_book = AsyncMock(return_value={
            'bids': [],
            'asks': []
        })

        orderbook_cache = {}

        result = await check_orderbook_imbalance(mock_client, 'BTC/USDT:USDT', 'LONG', orderbook_cache)

        assert result['valid'] is True
        assert result['quality'] == 'UNKNOWN'


# ============================================================================
# CORRELATION TESTS (correlation.py)
# ============================================================================

class TestCorrelationAsync:
    """Tests async pour correlation.py"""

    @pytest.mark.asyncio
    async def test_check_static_correlation_disabled(self):
        """Test corrélation statique désactivée"""
        # Désactiver temporairement
        original_config = TRADING_CONFIG.get('correlation_filter', {}).copy()
        TRADING_CONFIG['correlation_filter'] = {'enabled': False}

        try:
            result = await check_static_correlation('BTC/USDT:USDT', ['ETH/USDT:USDT'])

            assert result['valid'] is True
            assert result['reason'] is None
        finally:
            TRADING_CONFIG['correlation_filter'] = original_config

    @pytest.mark.asyncio
    async def test_check_static_correlation_no_active_positions(self):
        """Test corrélation statique sans positions actives"""
        result = await check_static_correlation('BTC/USDT:USDT', [])

        assert result['valid'] is True
        assert result['reason'] is None

    @pytest.mark.asyncio
    async def test_check_static_correlation_no_group(self):
        """Test corrélation statique pour symbole sans groupe"""
        result = await check_static_correlation('XYZ/USDT:USDT', ['BTC/USDT:USDT'])

        assert result['valid'] is True
        assert result['group'] is None

    @pytest.mark.asyncio
    async def test_check_static_correlation_hard_mode_reject(self):
        """Test corrélation statique HARD mode avec rejet"""
        # Configurer HARD mode
        original_config = TRADING_CONFIG.get('correlation_filter', {}).copy()
        TRADING_CONFIG['correlation_filter'] = {
            'enabled': True,
            'mode': 'HARD',
            'max_positions_per_group': 1,
            'groups': {
                'btc_family': ['BTC', 'BTCUSDT']
            }
        }

        try:
            result = await check_static_correlation('BTC/USDT:USDT', ['BTC/USDT:USDT'])

            assert result['valid'] is False
            assert 'Corrélation' in result['reason']
            assert result['group'] == 'btc_family'
        finally:
            TRADING_CONFIG['correlation_filter'] = original_config

    @pytest.mark.asyncio
    async def test_check_static_correlation_soft_mode_penalty(self):
        """Test corrélation statique SOFT mode avec pénalité"""
        # Configurer SOFT mode
        original_config = TRADING_CONFIG.get('correlation_filter', {}).copy()
        TRADING_CONFIG['correlation_filter'] = {
            'enabled': True,
            'mode': 'SOFT',
            'max_positions_per_group': 1,
            'penalty_score': -1.5,
            'groups': {
                'btc_family': ['BTC', 'BTCUSDT']
            }
        }

        try:
            result = await check_static_correlation('BTC/USDT:USDT', ['BTC/USDT:USDT'])

            assert result['valid'] is True  # SOFT mode ne rejette pas
            assert result['penalty'] == -1.5
            assert result['group'] == 'btc_family'
        finally:
            TRADING_CONFIG['correlation_filter'] = original_config

    def test_check_dynamic_correlation_disabled(self):
        """Test corrélation dynamique désactivée"""
        original_config = TRADING_CONFIG.get('dynamic_correlation', {}).copy()
        TRADING_CONFIG['dynamic_correlation'] = {'enabled': False}

        try:
            result = check_dynamic_correlation(None, 'BTC/USDT:USDT', 50000.0, ['ETH/USDT:USDT'], 5.0)

            assert result['penalty'] == 0.0
            assert result['adjusted_score'] == 5.0
        finally:
            TRADING_CONFIG['dynamic_correlation'] = original_config

    def test_check_dynamic_correlation_no_filter(self):
        """Test corrélation dynamique sans filtre"""
        result = check_dynamic_correlation(None, 'BTC/USDT:USDT', 50000.0, ['ETH/USDT:USDT'], 5.0)

        assert result['penalty'] == 0.0
        assert result['adjusted_score'] == 5.0

    def test_check_dynamic_correlation_with_penalty(self):
        """Test corrélation dynamique avec pénalité"""
        # Mock correlation filter
        mock_filter = Mock()
        mock_filter.update_price = Mock()
        mock_filter.check_correlation = Mock(return_value={
            'penalty': -2.0,
            'correlated_with': 'ETH/USDT:USDT',
            'correlation': 0.85
        })

        original_config = TRADING_CONFIG.get('dynamic_correlation', {}).copy()
        TRADING_CONFIG['dynamic_correlation'] = {
            'enabled': True,
            'max_penalty': -3.0
        }

        try:
            result = check_dynamic_correlation(
                mock_filter,
                'BTC/USDT:USDT',
                50000.0,
                ['ETH/USDT:USDT'],
                5.0
            )

            assert result['penalty'] == -2.0
            assert result['adjusted_score'] == 3.0
            assert result['correlated_with'] == 'ETH/USDT:USDT'
        finally:
            TRADING_CONFIG['dynamic_correlation'] = original_config


# ============================================================================
# SCANNER TESTS (scanner.py)
# ============================================================================

class TestScannerAsync:
    """Tests async pour scanner.py"""

    def test_calculate_volatility(self):
        """Test calcul volatilité"""
        scanner = ScalabilityScanner()

        closes = [100, 102, 98, 105, 95, 110, 108, 103]
        volatility = scanner.calculate_volatility(closes, 5)

        assert volatility > 0
        assert volatility < 100  # Raisonnable

    def test_calculate_volatility_insufficient_data(self):
        """Test calcul volatilité avec données insuffisantes"""
        scanner = ScalabilityScanner()

        closes = [100, 102]
        volatility = scanner.calculate_volatility(closes, 5)

        assert volatility == 0.0

    @pytest.mark.asyncio
    async def test_fetch_spread_data_success(self):
        """Test fetch spread data avec succès"""
        scanner = ScalabilityScanner()

        # Mock client
        scanner.client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0], [49990.0, 8.0], [49980.0, 6.0]],
            'asks': [[50010.0, 12.0], [50020.0, 9.0], [50030.0, 7.0]]
        })

        result = await scanner.fetch_spread_data('BTC/USDT:USDT')

        assert result['spread'] > 0
        assert result['bookDepth'] > 0
        assert 0 <= result['balanceScore'] <= 1

    @pytest.mark.asyncio
    async def test_fetch_spread_data_empty_orderbook(self):
        """Test fetch spread data avec orderbook vide"""
        scanner = ScalabilityScanner()

        scanner.client.fetch_order_book = AsyncMock(return_value={
            'bids': [],
            'asks': []
        })

        result = await scanner.fetch_spread_data('BTC/USDT:USDT')

        assert result['spread'] != result['spread']  # NaN check
        assert result['bookDepth'] == 0

    @pytest.mark.asyncio
    async def test_fetch_spread_data_error(self):
        """Test fetch spread data avec erreur"""
        scanner = ScalabilityScanner()

        scanner.client.fetch_order_book = AsyncMock(side_effect=Exception("API Error"))

        result = await scanner.fetch_spread_data('BTC/USDT:USDT')

        assert result['spread'] != result['spread']  # NaN check
        assert result['bookDepth'] == 0

    def test_calculate_score_valid(self):
        """Test calcul score avec données valides"""
        scanner = ScalabilityScanner()

        pair = {
            'spread': 0.015,
            'vol5': 1.5,
            'recentVolume': 500000,
            'bookDepth': 10000,
            'balanceScore': 0.8
        }

        score = scanner.calculate_score(pair, 1000000, 20000)

        assert score > 0

    def test_calculate_score_high_spread(self):
        """Test calcul score avec spread trop élevé"""
        scanner = ScalabilityScanner()

        pair = {
            'spread': 0.10,  # > 0.06% (scalability_spread_max)
            'vol5': 1.5,
            'recentVolume': 500000,
            'bookDepth': 10000,
            'balanceScore': 0.8
        }

        score = scanner.calculate_score(pair, 1000000, 20000)

        assert score == 0.0

    def test_calculate_score_low_volume(self):
        """Test calcul score avec volume trop faible"""
        scanner = ScalabilityScanner()

        pair = {
            'spread': 0.015,
            'vol5': 1.5,
            'recentVolume': 20000,  # < 30000 (scalability_volume_min)
            'bookDepth': 10000,
            'balanceScore': 0.8
        }

        score = scanner.calculate_score(pair, 1000000, 20000)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_scan_pair_success(self):
        """Test scan d'une paire avec succès"""
        scanner = ScalabilityScanner()

        # Mock klines
        klines = []
        for i in range(60):
            klines.append([
                1609459200000 + i * 60000,  # timestamp
                50000.0 + i * 10,  # open
                50100.0 + i * 10,  # high
                49900.0 + i * 10,  # low
                50050.0 + i * 10,  # close
                1000.0 + i * 5     # volume
            ])

        scanner.client.fetch_ohlcv = AsyncMock(return_value=klines)
        scanner.client.fetch_order_book = AsyncMock(return_value={
            'bids': [[50000.0, 10.0]],
            'asks': [[50010.0, 12.0]]
        })

        result = await scanner.scan_pair('BTC/USDT:USDT')

        assert result is not None
        assert result['symbol'] == 'BTC/USDT:USDT'
        assert 'vol5' in result
        assert 'spread' in result

    @pytest.mark.asyncio
    async def test_scan_pair_insufficient_klines(self):
        """Test scan d'une paire avec klines insuffisantes"""
        scanner = ScalabilityScanner()

        scanner.client.fetch_ohlcv = AsyncMock(return_value=[])

        result = await scanner.scan_pair('BTC/USDT:USDT')

        assert result is None

    @pytest.mark.asyncio
    async def test_scan_pair_error(self):
        """Test scan d'une paire avec erreur"""
        scanner = ScalabilityScanner()

        scanner.client.fetch_ohlcv = AsyncMock(side_effect=Exception("API Error"))

        result = await scanner.scan_pair('BTC/USDT:USDT')

        assert result is None


# ============================================================================
# ANALYTICS DATABASE TESTS
# ============================================================================

class TestAnalyticsDatabase:
    """Tests pour analytics_database.py"""

    def test_init_database(self, tmp_path):
        """Test initialisation database"""
        db_path = str(tmp_path / "test_analytics.db")

        db = AnalyticsDatabase(db_path=db_path)

        assert db.conn is not None
        assert db.db_path == db_path

    def test_insert_rejected_setup(self, tmp_path):
        """Test insertion setup rejeté"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        setup = {
            'timestamp': '2025-11-07T10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'rejection_reason': 'Score too low',
            'rejection_category': 'SCORE',
            'price': 50000.0,
            'total_score': 2.5,
            'min_score_required': 3.0
        }

        setup_id = db.insert_rejected_setup(setup)

        assert setup_id > 0

    def test_get_rejected_setups(self, tmp_path):
        """Test récupération setups rejetés"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer quelques setups
        for i in range(5):
            setup = {
                'timestamp': f'2025-11-07T10:{i:02d}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'rejection_reason': f'Reason {i}',
                'rejection_category': 'SCORE',
                'price': 50000.0 + i * 100
            }
            db.insert_rejected_setup(setup)

        setups = db.get_rejected_setups(limit=10)

        assert len(setups) == 5

    def test_get_rejection_summary(self, tmp_path):
        """Test statistiques rejets"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer setups variés
        categories = ['SCORE', 'SPREAD', 'VOLUME', 'SCORE', 'SCORE']
        for i, cat in enumerate(categories):
            setup = {
                'timestamp': f'2025-11-07T10:{i:02d}:00',
                'symbol': 'BTC/USDT:USDT',
                'rejection_reason': f'Reason {i}',
                'rejection_category': cat,
                'price': 50000.0
            }
            db.insert_rejected_setup(setup)

        summary = db.get_rejection_summary()

        assert summary['by_category']['SCORE'] == 3
        assert summary['by_category']['SPREAD'] == 1

    def test_insert_validated_setup(self, tmp_path):
        """Test insertion setup validé"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        setup = {
            'timestamp': '2025-11-07T10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'price': 50000.0,
            'entry': 50000.0,
            'sl': 49750.0,
            'tp': 50250.0,
            'position_size': 0.1,
            'total_score': 5.0
        }

        setup_id = db.insert_validated_setup(setup)

        assert setup_id > 0

    def test_insert_trade(self, tmp_path):
        """Test insertion trade"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        trade = {
            'timestamp': '2025-11-07T10:00:00',
            'date': '2025-11-07',
            'time': '10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 50250.0,
            'gross_pnl_pct': 0.5,
            'gross_pnl_usdt': 25.0,
            'net_pnl_pct': 0.48,
            'net_pnl_usdt': 24.0
        }

        trade_id = db.insert_trade(trade)

        assert trade_id > 0

    def test_get_trades(self, tmp_path):
        """Test récupération trades"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer quelques trades
        for i in range(3):
            trade = {
                'timestamp': f'2025-11-07T10:{i:02d}:00',
                'date': '2025-11-07',
                'time': f'10:{i:02d}:00',
                'symbol': 'BTC/USDT:USDT',
                'direction': 'LONG',
                'entry': 50000.0,
                'exit': 50250.0,
                'gross_pnl_pct': 0.5,
                'gross_pnl_usdt': 25.0,
                'net_pnl_pct': 0.48,
                'net_pnl_usdt': 24.0
            }
            db.insert_trade(trade)

        trades = db.get_trades(limit=10)

        assert len(trades) == 3

    def test_insert_trade_behavior(self, tmp_path):
        """Test insertion comportement trade"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer trade d'abord
        trade = {
            'timestamp': '2025-11-07T10:00:00',
            'date': '2025-11-07',
            'time': '10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 50250.0,
            'gross_pnl_pct': 0.5,
            'gross_pnl_usdt': 25.0,
            'net_pnl_pct': 0.48,
            'net_pnl_usdt': 24.0
        }
        trade_id = db.insert_trade(trade)

        # Insérer behavior
        behavior = {
            'trade_id': trade_id,
            'timestamp': '2025-11-07T10:01:00',
            'elapsed_seconds': 60,
            'current_price': 50100.0,
            'pnl_pct': 0.2,
            'pnl_usdt': 10.0,
            'current_sl': 49750.0,
            'current_tp': 50250.0,
            'break_even_set': False,
            'trailing_active': False,
            'partial_tp_sold': False
        }

        behavior_id = db.insert_trade_behavior(behavior)

        assert behavior_id > 0

    def test_get_trade_behavior(self, tmp_path):
        """Test récupération comportement trade"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer trade
        trade = {
            'timestamp': '2025-11-07T10:00:00',
            'date': '2025-11-07',
            'time': '10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 50250.0,
            'gross_pnl_pct': 0.5,
            'gross_pnl_usdt': 25.0,
            'net_pnl_pct': 0.48,
            'net_pnl_usdt': 24.0
        }
        trade_id = db.insert_trade(trade)

        # Insérer plusieurs behaviors
        for i in range(3):
            behavior = {
                'trade_id': trade_id,
                'elapsed_seconds': i * 60,
                'current_price': 50000.0 + i * 50,
                'pnl_pct': i * 0.1,
                'pnl_usdt': i * 5.0,
                'current_sl': 49750.0,
                'current_tp': 50250.0
            }
            db.insert_trade_behavior(behavior)

        behaviors = db.get_trade_behavior(trade_id)

        assert len(behaviors) == 3

    def test_get_global_stats(self, tmp_path):
        """Test statistiques globales"""
        db_path = str(tmp_path / "test_analytics.db")
        db = AnalyticsDatabase(db_path=db_path)

        # Insérer données
        db.insert_rejected_setup({
            'timestamp': '2025-11-07T10:00:00',
            'symbol': 'BTC/USDT:USDT',
            'rejection_reason': 'Test',
            'rejection_category': 'SCORE',
            'price': 50000.0
        })

        db.insert_validated_setup({
            'timestamp': '2025-11-07T10:01:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'price': 50000.0,
            'entry': 50000.0,
            'sl': 49750.0,
            'tp': 50250.0,
            'position_size': 0.1,
            'total_score': 5.0
        })

        db.insert_trade({
            'timestamp': '2025-11-07T10:02:00',
            'date': '2025-11-07',
            'time': '10:02:00',
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'entry': 50000.0,
            'exit': 50250.0,
            'gross_pnl_pct': 0.5,
            'gross_pnl_usdt': 25.0,
            'net_pnl_pct': 0.48,
            'net_pnl_usdt': 24.0
        })

        stats = db.get_global_stats()

        assert stats['total_rejected'] == 1
        assert stats['total_validated'] == 1
        assert stats['total_trades'] == 1
        assert stats['validation_rate'] == 50.0

    def test_get_analytics_db_helper(self, tmp_path):
        """Test helper get_analytics_db"""
        # Test avec port spécifique
        db = get_analytics_db(instance_port=9999)

        assert db is not None
        assert db.instance_port == 9999


# ============================================================================
# CALLBACKS TESTS
# ============================================================================

class TestCallbacksAsync:
    """Tests async pour callbacks"""

    @pytest.mark.asyncio
    async def test_scanner_loop_callback_no_instances(self):
        """Test scanner loop sans instances"""
        # Reset instances
        set_scanner(None)
        set_app_state(None)
        set_scanner_lock(None)

        # Ne devrait pas planter
        await scanner_loop_callback()

    @pytest.mark.asyncio
    async def test_scanner_loop_callback_with_active_position(self):
        """Test scanner loop avec position active"""
        mock_scanner = Mock()
        mock_app_state = {'active_position': True, 'top_pairs': []}
        mock_lock = asyncio.Lock()

        set_scanner(mock_scanner)
        set_app_state(mock_app_state)
        set_scanner_lock(mock_lock)

        await scanner_loop_callback()

        # Scanner ne devrait pas être appelé

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_no_analyzer(self):
        """Test scan pair sans analyzer"""
        set_analyzer(None)

        result = await scan_pair_for_setup('BTC/USDT:USDT')

        assert result is None

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_success(self):
        """Test scan pair avec succès"""
        mock_analyzer = Mock()
        mock_analyzer.calculate_trend_data = AsyncMock(return_value={'trend': 'BULLISH'})
        mock_analyzer.analyze_pair = AsyncMock(return_value={
            'symbol': 'BTC/USDT:USDT',
            'direction': 'LONG',
            'score': 5.0
        })

        set_analyzer(mock_analyzer)

        result = await scan_pair_for_setup('BTC/USDT:USDT')

        assert result is not None
        assert result['symbol'] == 'BTC/USDT:USDT'

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_error(self):
        """Test scan pair avec erreur"""
        mock_analyzer = Mock()
        mock_analyzer.calculate_trend_data = AsyncMock(side_effect=Exception("Error"))

        set_analyzer(mock_analyzer)

        result = await scan_pair_for_setup('BTC/USDT:USDT')

        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
