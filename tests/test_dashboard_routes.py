"""
Tests for api/routes/dashboard.py
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import time
import sys
from datetime import datetime

from api.routes import dashboard


@pytest.fixture
def app():
    """Create FastAPI app with dashboard router"""
    from api.auth import verify_api_key

    app = FastAPI()
    app.include_router(dashboard.router)

    # Override verify_api_key dependency for testing
    async def override_verify_api_key():
        return {"user": "test_user"}

    app.dependency_overrides[verify_api_key] = override_verify_api_key
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_app_state():
    """Mock app state"""
    return {
        'is_scanning': True,
        'active_position': True,
        'stats': {
            'total_trades': 10,
            'wins': 7,
            'losses': 3,
            'winrate': 70.0
        },
        'top_pairs': ['BTC_USDT', 'ETH_USDT'],
        'logs': [],
        'trade_history': []
    }


@pytest.fixture
def mock_scheduler():
    """Mock scheduler"""
    scheduler = Mock()
    scheduler.start = Mock()
    scheduler.stop = Mock()
    return scheduler


@pytest.fixture
def mock_position_manager():
    """Mock position manager"""
    pm = Mock()
    pm.active_position = None
    return pm


@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager"""
    ws = AsyncMock()
    ws.emit = AsyncMock()
    return ws


class TestDashboardRoutes:
    """Test cases for dashboard routes"""

    def test_set_scheduler(self):
        """Test set_scheduler injection"""
        mock_scheduler = Mock()
        dashboard.set_scheduler(mock_scheduler)
        assert dashboard._scheduler == mock_scheduler

    def test_set_position_manager(self):
        """Test set_position_manager injection"""
        mock_pm = Mock()
        dashboard.set_position_manager(mock_pm)
        assert dashboard._position_manager == mock_pm

    def test_set_app_state(self):
        """Test set_app_state injection"""
        mock_state = {'test': 'data'}
        dashboard.set_app_state(mock_state)
        assert dashboard._app_state == mock_state

    def test_set_websocket_manager(self):
        """Test set_websocket_manager injection"""
        mock_ws = Mock()
        dashboard.set_websocket_manager(mock_ws)
        assert dashboard._ws_manager == mock_ws

    def test_set_socketio_with_ws_manager(self):
        """Test set_socketio with ws_manager (legacy alias)"""
        mock_ws = Mock()
        mock_ws.emit = Mock()
        # Remove 'on' attribute to ensure it's detected as ws_manager
        mock_ws.on = None
        del mock_ws.on
        dashboard.set_socketio(mock_ws)
        assert dashboard._ws_manager == mock_ws

    def test_set_socketio_with_socketio(self):
        """Test set_socketio with actual socketio (should be ignored)"""
        mock_sio = Mock()
        mock_sio.on = Mock()
        mock_sio.emit = Mock()
        dashboard.set_socketio(mock_sio)
        assert dashboard._ws_manager is None

    def test_get_status_no_app_state(self, client):
        """Test /api/status when app state is not available"""
        dashboard._app_state = None
        response = client.get("/api/status")
        assert response.status_code == 503
        assert 'error' in response.json()

    def test_get_status_success(self, client, mock_app_state):
        """Test /api/status with app state available"""
        dashboard._app_state = mock_app_state
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data['is_scanning'] is True
        assert data['active_position'] is True

    def test_get_status_exception(self, client):
        """Test /api/status with exception"""
        # Set app_state to an object that causes exception during dict() conversion
        # Use a mock that raises an exception when iterated
        mock_broken_state = MagicMock()
        mock_broken_state.__iter__.side_effect = Exception("Serialization error")
        mock_broken_state.to_dict.side_effect = Exception("Serialization error")

        dashboard._app_state = mock_broken_state

        response = client.get("/api/status")
        assert response.status_code == 500
        assert 'error' in response.json()

    def test_get_complete_state_no_app_state(self, client):
        """Test /api/state when app state is not available"""
        dashboard._app_state = None
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'session_id' in data

    @patch('config.TRADING_CONFIG', {
        'snr_threshold': 0.25,
        'breakout_threshold': 0.35,
        'wick_ratio_max': 2.8,
        'di_gap_min': 4.0,
        'trend_timeframe': '15m',
        'account_size': 1000.0,
        'risk_per_trade': 2.0,
        'use_confluence': False,
        'tp_sl_mode': 'FIXE',
        'tp_percent': 0.25,
        'sl_percent': 0.25,
        'volume_multiplier': 0.95,
        'min_score_required': 7.5
    })
    def test_get_complete_state_success(self, client, mock_app_state, mock_position_manager):
        """Test /api/state with complete data"""
        dashboard._app_state = mock_app_state
        dashboard._position_manager = mock_position_manager

        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'config' in data
        assert 'scanner' in data
        assert 'position' in data
        assert 'stats' in data

    @patch('config.TRADING_CONFIG', {})
    def test_get_complete_state_with_active_position(self, client, mock_app_state, mock_position_manager):
        """Test /api/state with active position"""
        mock_position = Mock()
        mock_position.to_dict = Mock(return_value={'symbol': 'BTC_USDT', 'side': 'LONG'})
        mock_position_manager.active_position = mock_position

        dashboard._app_state = mock_app_state
        dashboard._position_manager = mock_position_manager

        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['position']['active'] is True
        assert data['position']['data']['symbol'] == 'BTC_USDT'

    def test_get_complete_state_exception(self, client):
        """Test /api/state with exception"""
        mock_state = Mock()
        mock_state.get.side_effect = Exception("Test error")
        dashboard._app_state = mock_state

        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'error' in data

    @pytest.mark.asyncio
    async def test_start_scanner_no_scheduler(self, client):
        """Test /api/start when scheduler is not available"""
        dashboard._scheduler = None
        dashboard._app_state = None

        with patch('main.init_instances', side_effect=Exception("Cannot init")):
            response = client.post("/api/start", headers={"X-API-Key": "test_key"})
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is False

    @pytest.mark.asyncio
    async def test_start_scanner_success(self, client, mock_scheduler, mock_app_state, mock_ws_manager):
        """Test /api/start success"""
        mock_app_state['is_scanning'] = False
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state
        dashboard._ws_manager = mock_ws_manager

        response = client.post("/api/start")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['is_scanning'] is True
        mock_scheduler.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_scanner_already_scanning(self, client, mock_scheduler, mock_app_state):
        """Test /api/start when already scanning"""
        mock_app_state['is_scanning'] = True
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state

        response = client.post("/api/start")
        # Scheduler.start should not be called
        mock_scheduler.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_scanner_exception(self, client, mock_scheduler, mock_app_state):
        """Test /api/start with exception during start"""
        mock_app_state['is_scanning'] = False
        mock_scheduler.start.side_effect = Exception("Start failed")
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state

        response = client.post("/api/start")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False

    @pytest.mark.asyncio
    async def test_stop_scanner_no_scheduler(self, client):
        """Test /api/stop when scheduler is not available"""
        dashboard._scheduler = None
        dashboard._app_state = None

        with patch('main.init_instances', side_effect=Exception("Cannot init")):
            response = client.post("/api/stop")
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is False

    @pytest.mark.asyncio
    async def test_stop_scanner_success(self, client, mock_scheduler, mock_app_state, mock_ws_manager):
        """Test /api/stop success"""
        mock_app_state['is_scanning'] = True
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state
        dashboard._ws_manager = mock_ws_manager

        response = client.post("/api/stop")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['is_scanning'] is False
        mock_scheduler.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_scanner_not_scanning(self, client, mock_scheduler, mock_app_state):
        """Test /api/stop when not scanning"""
        mock_app_state['is_scanning'] = False
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state

        response = client.post("/api/stop")
        # Scheduler.stop should not be called
        mock_scheduler.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_scanner_exception(self, client, mock_scheduler, mock_app_state):
        """Test /api/stop with exception during stop"""
        mock_app_state['is_scanning'] = True
        mock_scheduler.stop.side_effect = Exception("Stop failed")
        dashboard._scheduler = mock_scheduler
        dashboard._app_state = mock_app_state

        response = client.post("/api/stop")
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False

    def test_get_sessions_returns_current_session(self, client, mock_app_state, monkeypatch: pytest.MonkeyPatch):
        mock_app_state['session_id'] = 'sess_1'
        mock_app_state['is_scanning'] = True
        dashboard._app_state = mock_app_state

        monkeypatch.setattr(sys, 'argv', ['main.py', '5000'])

        response = client.get('/api/sessions')
        assert response.status_code == 200
        data = response.json()
        assert 'sessions' in data
        assert data['sessions'][0]['id'] == 'sess_1'
        assert data['sessions'][0]['status'] == 'running'
        assert data['sessions'][0]['port'] == 5000

    def test_get_dashboard_summary_computes_stats(self, client, monkeypatch: pytest.MonkeyPatch):
        today = datetime.now().date().isoformat()
        dashboard._app_state = {
            'trade_history': [
                {'net_pnl_usdt': 10.0, 'gross_pnl_pct': 1.0, 'timestamp': f'{today}T10:00:00'},
                {'net_pnl_usdt': -5.0, 'gross_pnl_pct': -2.0, 'timestamp': f'{today}T11:00:00'},
                {'net_pnl_usdt': 2.5, 'gross_pnl_pct': 0.5, 'timestamp': f'{today}T12:00:00'},
            ]
        }

        pos_mgr = Mock()
        pos_mgr.config = Mock()
        setattr(pos_mgr.config, 'recovery_mode_active', True)
        dashboard._position_manager = pos_mgr

        class _State:
            session_id = 'sess_1'

            def get_position_manager(self):
                return pos_mgr

        import core.state_manager as state_manager
        monkeypatch.setattr(state_manager, 'get_state_manager', lambda: _State())

        import core.bootstrap as bootstrap
        monkeypatch.setattr(bootstrap, 'init_instances', lambda: None)

        response = client.get('/api/dashboard/summary')
        assert response.status_code == 200
        data = response.json()
        assert data['total_trades'] == 3
        assert data['wins'] == 2
        assert data['losses'] == 1
        assert data['recovery_mode_active'] is True
        assert isinstance(data['equity_curve'], list)
        assert len(data['equity_curve']) == 3

    def test_calculate_max_drawdown_empty(self):
        info = dashboard.calculate_max_drawdown([])
        assert info['max_dd'] == 0
        assert info['current_dd'] == 0

    def test_calculate_max_drawdown_computes_negative_dd(self):
        trades = [
            {'gross_pnl_pct': 10, 'timestamp': '2026-01-01T00:00:00'},
            {'gross_pnl_pct': -5, 'timestamp': '2026-01-02T00:00:00'},
            {'gross_pnl_pct': -10, 'timestamp': '2026-01-03T00:00:00'},
            {'gross_pnl_pct': 20, 'timestamp': '2026-01-04T00:00:00'},
        ]
        info = dashboard.calculate_max_drawdown(trades)
        assert info['max_dd'] <= 0
        assert 'max_dd_date' in info
        assert 'current_dd' in info
