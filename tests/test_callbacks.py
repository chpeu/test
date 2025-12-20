"""
Tests pour core/callbacks/*.py
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime


class TestPositionCheckLoop:
    """Tests pour core/callbacks/position_check_loop.py"""

    def test_setters(self):
        """Test fonctions d'injection"""
        from core.callbacks.position_check_loop import (
            set_position_manager, set_price_provider, set_app_state,
            set_socketio, set_websocket_manager, set_position_lock, set_analytics_db
        )

        mock_pm = Mock()
        mock_pp = Mock()
        mock_state = {}
        mock_sio = Mock()
        mock_ws = Mock()
        mock_lock = asyncio.Lock()
        mock_db = Mock()

        # Ne devraient pas lever d'exception
        set_position_manager(mock_pm)
        set_price_provider(mock_pp)
        set_app_state(mock_state)
        set_socketio(mock_sio)
        set_websocket_manager(mock_ws)
        set_position_lock(mock_lock)
        set_analytics_db(mock_db)

    @pytest.mark.asyncio
    async def test_position_check_loop_callback_no_instances(self):
        """Test callback sans instances injectées"""
        from core.callbacks import position_check_loop

        # Reset instances
        position_check_loop._position_manager = None
        position_check_loop._price_provider = None
        position_check_loop._app_state = None

        # Ne devrait pas lever d'exception
        await position_check_loop.position_check_loop_callback()

    @pytest.mark.asyncio
    async def test_position_check_loop_callback_no_position(self):
        """Test callback sans position active"""
        from core.callbacks import position_check_loop

        mock_pm = Mock()
        mock_pm.active_position = None
        mock_pp = AsyncMock()
        mock_state = {}

        position_check_loop._position_manager = mock_pm
        position_check_loop._price_provider = mock_pp
        position_check_loop._app_state = mock_state

        # Ne devrait pas lever d'exception
        await position_check_loop.position_check_loop_callback()

    @pytest.mark.asyncio
    async def test_position_check_loop_with_active_position(self):
        """Test callback avec position active"""
        from core.callbacks import position_check_loop

        # Mock position
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry = 50000.0
        mock_position.direction = "LONG"
        mock_position.sl = 49000.0
        mock_position.tp = 52000.0
        mock_position.size = 100.0

        # Mock position_manager
        mock_pm = Mock()
        mock_pm.active_position = mock_position
        mock_pm.check_position = AsyncMock(return_value=None)  # Position toujours active

        # Mock price_provider
        mock_pp = AsyncMock()
        mock_pp.get_price = AsyncMock(return_value={"lastPrice": 50500.0})

        # Mock app_state
        mock_state = {"active_position": {"symbol": "BTC/USDT:USDT"}}

        # Mock ws_manager
        mock_ws = AsyncMock()

        position_check_loop._position_manager = mock_pm
        position_check_loop._price_provider = mock_pp
        position_check_loop._app_state = mock_state
        position_check_loop._ws_manager = mock_ws

        await position_check_loop.position_check_loop_callback()

        # Vérifier que get_price a été appelé
        mock_pp.get_price.assert_called_once_with("BTC/USDT:USDT")

        # Vérifier que check_position a été appelé
        mock_pm.check_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_position_check_loop_price_unavailable(self):
        """Test callback avec prix indisponible"""
        from core.callbacks import position_check_loop

        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"

        mock_pm = Mock()
        mock_pm.active_position = mock_position

        mock_pp = AsyncMock()
        mock_pp.get_price = AsyncMock(return_value=None)  # Prix indisponible

        mock_state = {"check_interval": 2}

        position_check_loop._position_manager = mock_pm
        position_check_loop._price_provider = mock_pp
        position_check_loop._app_state = mock_state

        # Ne devrait pas lever d'exception
        await position_check_loop.position_check_loop_callback()

    @pytest.mark.asyncio
    async def test_position_check_loop_position_closed(self):
        """Test callback avec fermeture de position"""
        from core.callbacks import position_check_loop

        # Mock position
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry = 50000.0
        mock_position.direction = "LONG"

        # Mock position_manager
        mock_pm = Mock()
        mock_pm.active_position = mock_position
        mock_pm.check_position = AsyncMock(return_value="TP_HIT")  # Position fermée
        mock_pm.close_position = Mock(return_value={
            "symbol": "BTC/USDT:USDT",
            "net_pnl_usdt": 100.0,
            "pnl_pct": 2.0
        })

        # Mock price_provider
        mock_pp = AsyncMock()
        mock_pp.get_price = AsyncMock(return_value={"lastPrice": 52000.0})
        mock_pp.stop_websocket = AsyncMock()

        # Mock app_state
        mock_state = {
            "active_position": {"symbol": "BTC/USDT:USDT"},
            "stats": {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "winrate": 0.0
            }
        }

        # Mock ws_manager
        mock_ws = AsyncMock()

        # Mock lock
        mock_lock = asyncio.Lock()

        position_check_loop._position_manager = mock_pm
        position_check_loop._price_provider = mock_pp
        position_check_loop._app_state = mock_state
        position_check_loop._ws_manager = mock_ws
        position_check_loop._position_lock = mock_lock

        await position_check_loop.position_check_loop_callback()

        # Vérifier que close_position a été appelé
        mock_pm.close_position.assert_called_once()

        # Vérifier que stats ont été mises à jour
        assert mock_state['stats']['total_trades'] == 1
        assert mock_state['stats']['wins'] == 1
        assert mock_state['active_position'] is None

    def test_update_session_stats_win(self):
        """Test mise à jour stats après un win"""
        from core.callbacks.position_check_loop import _update_session_stats

        mock_state = {
            "stats": {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "winrate": 0.0
            }
        }

        from core.callbacks import position_check_loop
        position_check_loop._app_state = mock_state

        result = {"net_pnl_usdt": 100.0}
        _update_session_stats(result)

        assert mock_state['stats']['total_trades'] == 1
        assert mock_state['stats']['wins'] == 1
        assert mock_state['stats']['losses'] == 0
        assert mock_state['stats']['winrate'] == 100.0

    def test_update_session_stats_loss(self):
        """Test mise à jour stats après une loss"""
        from core.callbacks.position_check_loop import _update_session_stats

        mock_state = {
            "stats": {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "winrate": 0.0
            }
        }

        from core.callbacks import position_check_loop
        position_check_loop._app_state = mock_state

        result = {"net_pnl_usdt": -50.0}
        _update_session_stats(result)

        assert mock_state['stats']['total_trades'] == 1
        assert mock_state['stats']['wins'] == 0
        assert mock_state['stats']['losses'] == 1
        assert mock_state['stats']['winrate'] == 0.0


class TestScalabilityRefresh:
    """Tests pour core/callbacks/scalability_refresh.py"""

    def test_setters(self):
        """Test fonctions d'injection"""
        from core.callbacks.scalability_refresh import (
            set_scanner, set_position_manager, set_price_provider,
            set_app_state, set_socketio, set_websocket_manager
        )

        mock_scanner = Mock()
        mock_pm = Mock()
        mock_pp = Mock()
        mock_state = {}
        mock_sio = Mock()
        mock_ws = Mock()

        # Ne devraient pas lever d'exception
        set_scanner(mock_scanner)
        set_position_manager(mock_pm)
        set_price_provider(mock_pp)
        set_app_state(mock_state)
        set_socketio(mock_sio)
        set_websocket_manager(mock_ws)

    @pytest.mark.asyncio
    async def test_scalability_refresh_scanner_inactive(self):
        """Test callback avec scanner inactif"""
        from core.callbacks import scalability_refresh

        mock_state = {"is_scanning": False}
        scalability_refresh._app_state = mock_state

        # Ne devrait pas lever d'exception
        await scalability_refresh.scalability_refresh_loop_callback()

    @pytest.mark.asyncio
    async def test_scalability_refresh_no_scanner(self):
        """Test callback sans scanner"""
        from core.callbacks import scalability_refresh

        mock_state = {"is_scanning": True}
        scalability_refresh._app_state = mock_state
        scalability_refresh._scanner = None

        # Ne devrait pas lever d'exception
        await scalability_refresh.scalability_refresh_loop_callback()

    @pytest.mark.asyncio
    async def test_scalability_refresh_with_active_position(self):
        """Test callback avec position active (devrait être ignoré)"""
        from core.callbacks import scalability_refresh

        mock_position = Mock()
        mock_pm = Mock()
        mock_pm.active_position = mock_position

        mock_scanner = Mock()
        mock_state = {
            "is_scanning": True,
            "active_position": {"symbol": "BTC/USDT:USDT"}
        }

        scalability_refresh._scanner = mock_scanner
        scalability_refresh._position_manager = mock_pm
        scalability_refresh._app_state = mock_state

        await scalability_refresh.scalability_refresh_loop_callback()

        # Scanner ne devrait PAS être appelé (position active)

    @pytest.mark.asyncio
    async def test_scalability_refresh_success(self):
        """Test rafraîchissement réussi"""
        from core.callbacks import scalability_refresh

        # Mock scanner
        mock_scanner = AsyncMock()
        mock_scanner.scan_top_pairs = AsyncMock(return_value=[
            {"symbol": "BTC/USDT:USDT", "score": 90},
            {"symbol": "ETH/USDT:USDT", "score": 85}
        ])

        # Mock position_manager (pas de position active)
        mock_pm = Mock()
        mock_pm.active_position = None

        # Mock price_provider
        mock_pp = AsyncMock()
        mock_pp.stop_websocket = AsyncMock()
        mock_pp.start_websocket = AsyncMock()

        # Mock ws_manager
        mock_ws = AsyncMock()

        mock_state = {
            "is_scanning": True,
            "active_position": None,
            "top_pairs": []
        }

        scalability_refresh._scanner = mock_scanner
        scalability_refresh._position_manager = mock_pm
        scalability_refresh._price_provider = mock_pp
        scalability_refresh._app_state = mock_state
        scalability_refresh._ws_manager = mock_ws

        await scalability_refresh.scalability_refresh_loop_callback()

        # Vérifier que scanner a été appelé (top_pairs_limit = 40 dans config)
        mock_scanner.scan_top_pairs.assert_called_once_with(40)

        # Vérifier que top_pairs a été mis à jour
        assert len(mock_state['top_pairs']) == 2

        # Vérifier que WebSocket a été mis à jour
        mock_pp.stop_websocket.assert_called_once()
        mock_pp.start_websocket.assert_called_once()


class TestScannerLoop:
    """Tests pour core/callbacks/scanner_loop.py"""

    def test_setters(self):
        """Test fonctions d'injection"""
        from core.callbacks.scanner_loop import (
            set_scanner, set_analyzer, set_position_manager,
            set_price_provider, set_app_state, set_socketio,
            set_websocket_manager, set_scanner_lock
        )

        mock_scanner = Mock()
        mock_analyzer = Mock()
        mock_pm = Mock()
        mock_pp = Mock()
        mock_state = {}
        mock_sio = Mock()
        mock_ws = Mock()
        mock_lock = asyncio.Lock()

        # Ne devraient pas lever d'exception
        set_scanner(mock_scanner)
        set_analyzer(mock_analyzer)
        set_position_manager(mock_pm)
        set_price_provider(mock_pp)
        set_app_state(mock_state)
        set_socketio(mock_sio)
        set_websocket_manager(mock_ws)
        set_scanner_lock(mock_lock)

    @pytest.mark.asyncio
    async def test_scanner_loop_no_instances(self):
        """Test callback sans instances"""
        from core.callbacks import scanner_loop

        scanner_loop._scanner = None
        scanner_loop._app_state = None
        scanner_loop._scanner_lock = None

        # Ne devrait pas lever d'exception
        await scanner_loop.scanner_loop_callback()

    @pytest.mark.asyncio
    async def test_scanner_loop_with_active_position(self):
        """Test callback avec position active (devrait être ignoré)"""
        from core.callbacks import scanner_loop

        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"

        mock_pm = Mock()
        mock_pm.active_position = mock_position

        mock_scanner = Mock()
        mock_state = {"active_position": {"symbol": "BTC/USDT:USDT"}}
        mock_lock = asyncio.Lock()

        scanner_loop._scanner = mock_scanner
        scanner_loop._position_manager = mock_pm
        scanner_loop._app_state = mock_state
        scanner_loop._scanner_lock = mock_lock

        await scanner_loop.scanner_loop_callback()

        # Scanner ne devrait PAS être appelé

    @pytest.mark.asyncio
    async def test_scanner_loop_initial_scan(self):
        """Test scan initial des top pairs"""
        from core.callbacks import scanner_loop

        # Mock scanner
        mock_scanner = AsyncMock()
        mock_scanner.scan_top_pairs = AsyncMock(return_value=[
            {"symbol": "BTC/USDT:USDT", "score": 90}
        ])

        # Mock price_provider
        mock_pp = AsyncMock()
        mock_pp.start_websocket = AsyncMock()

        # Mock ws_manager
        mock_ws = AsyncMock()

        mock_state = {"top_pairs": None}  # Pas encore de top_pairs
        mock_lock = asyncio.Lock()

        scanner_loop._scanner = mock_scanner
        scanner_loop._price_provider = mock_pp
        scanner_loop._app_state = mock_state
        scanner_loop._scanner_lock = mock_lock
        scanner_loop._ws_manager = mock_ws
        scanner_loop._position_manager = None

        await scanner_loop.scanner_loop_callback()

        # Vérifier que scan initial a été fait
        mock_scanner.scan_top_pairs.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_no_analyzer(self):
        """Test scan_pair_for_setup sans analyzer"""
        from core.callbacks.scanner_loop import scan_pair_for_setup
        from core.callbacks import scanner_loop

        scanner_loop._analyzer = None

        result = await scan_pair_for_setup("BTC/USDT:USDT")
        assert result is None

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_success(self):
        """Test scan_pair_for_setup réussi"""
        from core.callbacks.scanner_loop import scan_pair_for_setup
        from core.callbacks import scanner_loop

        # Mock analyzer
        mock_analyzer = AsyncMock()
        mock_analyzer.calculate_trend_data = AsyncMock(return_value={
            "trend": "UP",
            "ema_diff": 0.5
        })
        mock_analyzer.analyze_pair = AsyncMock(return_value={
            "symbol": "BTC/USDT:USDT",
            "direction": "LONG",
            "entry": 50000.0,
            "score": 85,
            "price": 50000.0,  # Ajout clé price pour compatibilité
            "tp": 52000.0,      # Ajout TP/SL pour éviter erreurs
            "sl": 49000.0,
            "tp_sl_mode": "FIXE",
            "indicators_1m": {"rsi": 60, "adx": 25},
            "indicators_5m": {"rsi": 58, "adx": 24}
        })

        scanner_loop._analyzer = mock_analyzer

        # Mock config
        with patch('config.TRADING_CONFIG', {
            'use_confluence': False,
            'volume_multiplier': 1.0,
            'trend_timeframe': '15m'
        }):
            result = await scan_pair_for_setup("BTC/USDT:USDT")

        assert result is not None
        assert result['symbol'] == "BTC/USDT:USDT"
        assert result['direction'] == "LONG"

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_rejection(self):
        """Test scan_pair_for_setup avec rejet"""
        from core.callbacks.scanner_loop import scan_pair_for_setup
        from core.callbacks import scanner_loop

        # Mock analyzer qui retourne un rejet
        mock_analyzer = AsyncMock()
        mock_analyzer.calculate_trend_data = AsyncMock(return_value={})
        mock_analyzer.analyze_pair = AsyncMock(return_value={
            "reason": "Volume insuffisant"
        })

        scanner_loop._analyzer = mock_analyzer

        with patch('config.TRADING_CONFIG', {
            'use_confluence': False,
            'volume_multiplier': 1.0,
            'trend_timeframe': '15m'
        }):
            result = await scan_pair_for_setup("BTC/USDT:USDT")

        assert result is not None
        assert 'reason' in result

    @pytest.mark.asyncio
    async def test_scan_pair_for_setup_exception(self):
        """Test scan_pair_for_setup avec exception"""
        from core.callbacks.scanner_loop import scan_pair_for_setup
        from core.callbacks import scanner_loop

        # Mock analyzer qui lève une exception
        mock_analyzer = AsyncMock()
        mock_analyzer.calculate_trend_data = AsyncMock(side_effect=Exception("API error"))

        scanner_loop._analyzer = mock_analyzer

        result = await scan_pair_for_setup("BTC/USDT:USDT")
        assert result is None


# Tests d'intégration
class TestCallbacksIntegration:
    """Tests d'intégration pour les callbacks"""

    @pytest.mark.asyncio
    async def test_full_position_lifecycle(self):
        """Test cycle complet: scanner trouve setup → position ouverte → position fermée"""
        from core.callbacks import scanner_loop, position_check_loop

        # Mock analyzer qui trouve un setup
        mock_analyzer = AsyncMock()
        mock_analyzer.calculate_trend_data = AsyncMock(return_value={})
        mock_analyzer.analyze_pair = AsyncMock(return_value={
            "symbol": "BTC/USDT:USDT",
            "direction": "LONG",
            "entry": 50000.0,
            "price": 50000.0,
            "atr": 500.0,
            "atr5m": 250.0,
            "condition_types": ["EMA_CROSS"],
            "tp": 52000.0,
            "sl": 48000.0,
            "tp_sl_mode": "ATR",
            "score": 85,
            "indicators_1m": {"rsi": 60, "adx": 25, "ema9": 50100, "ema21": 49900},
            "indicators_5m": {"rsi": 58, "adx": 24, "ema9": 50050, "ema21": 49950}
        })

        # Mock position_manager
        mock_position = Mock()
        mock_position.symbol = "BTC/USDT:USDT"
        mock_position.entry = 50000.0
        mock_position.direction = "LONG"
        mock_position.sl = 49500.0
        mock_position.tp = 51000.0
        mock_position.size = 100.0
        mock_position.to_dict = Mock(return_value={
            "symbol": "BTC/USDT:USDT",
            "direction": "LONG",
            "entry": 50000.0
        })

        mock_pm = Mock()
        mock_pm.active_position = None
        mock_pm.calculate_position_size = Mock(return_value=100.0)
        mock_pm.open_position = Mock(return_value=mock_position)

        # Mock scanner
        mock_scanner = AsyncMock()
        mock_scanner.scan_top_pairs = AsyncMock(return_value=[
            {"symbol": "BTC/USDT:USDT", "score": 90}
        ])

        # Mock ws_manager
        mock_ws = AsyncMock()

        mock_state = {
            "top_pairs": [{"symbol": "BTC/USDT:USDT"}],
            "active_position": None
        }
        mock_lock = asyncio.Lock()

        scanner_loop._scanner = mock_scanner
        scanner_loop._analyzer = mock_analyzer
        scanner_loop._position_manager = mock_pm
        scanner_loop._app_state = mock_state
        scanner_loop._scanner_lock = mock_lock
        scanner_loop._ws_manager = mock_ws

        # Mock TRADING_CONFIG
        with patch('config.TRADING_CONFIG', {
            'top_pairs_limit': 20,
            'use_confluence': False,
            'volume_multiplier': 1.0,
            'trend_timeframe': '15m',
            'account_size': 1000.0
        }):
            await scanner_loop.scanner_loop_callback()

        # Vérifier qu'une position a été ouverte
        mock_pm.open_position.assert_called_once()
        assert mock_state['active_position'] is not None
