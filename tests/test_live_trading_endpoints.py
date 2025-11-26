"""
Tests unitaires pour api/live_trading_endpoints.py
Coverage target: 80%+
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.live_trading_endpoints import (
    router,
    load_live_config,
    save_live_config,
    register_websocket_commands,
    LIVE_CONFIG_FILE
)


@pytest.fixture
def test_app():
    """FastAPI test app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(test_app):
    """Test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_config():
    """Mock configuration"""
    return {
        'trading_mode': 'LIVE',
        'dry_run': True,
        'api_key_mexc': 'test_key',
        'api_secret_mexc': 'test_secret',
        'max_slippage_pct': 0.15,
        'max_latency_ms': 1000,
        'max_pnl_discrepancy_pct': 20,
        'default_leverage': 10
    }


class TestLoadLiveConfig:
    """Tests chargement configuration"""

    def test_load_default_config_when_file_missing(self):
        """Test chargement config par défaut si fichier manquant"""
        with patch.object(Path, 'exists', return_value=False):
            config = load_live_config()

            assert config['trading_mode'] == 'PAPER'
            assert config['dry_run'] is True
            assert config['api_key_mexc'] == ''
            assert config['max_latency_ms'] == 1000

    def test_load_config_from_file(self, mock_config):
        """Test chargement depuis fichier"""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_config))):
                config = load_live_config()

                assert config['trading_mode'] == 'LIVE'
                assert config['api_key_mexc'] == 'test_key'

    def test_load_config_file_error(self):
        """Test erreur lecture fichier"""
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', side_effect=IOError("Read error")):
                config = load_live_config()

                # Devrait retourner default config
                assert config['trading_mode'] == 'PAPER'


class TestSaveLiveConfig:
    """Tests sauvegarde configuration"""

    def test_save_config_success(self, mock_config):
        """Test sauvegarde réussie"""
        m = mock_open()
        with patch('builtins.open', m):
            result = save_live_config(mock_config)

            assert result is True
            m.assert_called_once()

    def test_save_config_error(self, mock_config):
        """Test erreur sauvegarde"""
        with patch('builtins.open', side_effect=IOError("Write error")):
            result = save_live_config(mock_config)

            assert result is False


class TestGetLiveStats:
    """Tests GET /stats"""

    @patch('main.live_order_manager')
    @patch('api.live_trading_endpoints.load_live_config')
    def test_get_stats_with_live_manager(self, mock_load_config, mock_manager, client):
        """Test stats avec LiveOrderManager actif"""
        mock_load_config.return_value = {'max_latency_ms': 1000}
        mock_manager.dry_run = False
        mock_manager.get_stats.return_value = {
            'orders_placed': 10,
            'orders_filled': 9,
            'orders_failed': 1,
            'success_rate': 90.0,
            'avg_latency_ms': 250
        }

        response = client.get("/api/live/stats")

        assert response.status_code == 200
        data = response.json()
        assert data['mode'] == 'LIVE'
        assert data['orders_placed'] == 10
        assert data['api_healthy'] is True

    @patch('main.live_order_manager', None)
    def test_get_stats_paper_mode(self, client):
        """Test stats en mode PAPER"""
        response = client.get("/api/live/stats")

        assert response.status_code == 200
        data = response.json()
        assert data['mode'] == 'PAPER'
        assert data['live_enabled'] is False
        assert data['orders_placed'] == 0


class TestGetLiveConfig:
    """Tests GET /config"""

    @patch('api.live_trading_endpoints.load_live_config')
    def test_get_config_with_api_key_masking(self, mock_load, client):
        """Test récupération config avec masquage API keys"""
        mock_load.return_value = {
            'trading_mode': 'LIVE',
            'api_key_mexc': 'abcdef12345',
            'api_secret_mexc': 'secret12345',
            'dry_run': True
        }

        response = client.get("/api/live/config")

        assert response.status_code == 200
        data = response.json()
        assert data['api_key_mexc'] == '***ef12345'  # Masqué
        assert data['api_secret_mexc'] == '***12345'  # Masqué

    @patch('api.live_trading_endpoints.load_live_config')
    def test_get_config_empty_api_keys(self, mock_load, client):
        """Test config avec API keys vides"""
        mock_load.return_value = {
            'trading_mode': 'PAPER',
            'api_key_mexc': '',
            'api_secret_mexc': '',
            'dry_run': True
        }

        response = client.get("/api/live/config")

        assert response.status_code == 200
        data = response.json()
        assert data['api_key_mexc'] == ''
        assert data['api_secret_mexc'] == ''


class TestUpdateLiveConfig:
    """Tests POST /config"""

    @patch('api.live_trading_endpoints.save_live_config')
    @patch('api.live_trading_endpoints.load_live_config')
    @patch('main.live_order_manager')
    def test_update_config_success(self, mock_manager, mock_load, mock_save, client):
        """Test mise à jour config réussie"""
        mock_load.return_value = {'trading_mode': 'PAPER'}
        mock_save.return_value = True
        mock_manager = None  # Pas de manager actif

        response = client.post("/api/live/config", json={
            'trading_mode': 'LIVE',
            'dry_run': True
        })

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'updated' in data

    @patch('api.live_trading_endpoints.save_live_config')
    @patch('api.live_trading_endpoints.load_live_config')
    def test_update_config_save_error(self, mock_load, mock_save, client):
        """Test erreur sauvegarde"""
        mock_load.return_value = {'trading_mode': 'PAPER'}
        mock_save.return_value = False

        response = client.post("/api/live/config", json={
            'trading_mode': 'LIVE'
        })

        assert response.status_code == 500
        data = response.json()
        assert 'Erreur sauvegarde' in data['detail']


class TestTestMexcConnection:
    """Tests POST /test-connection"""

    def test_test_connection_success(self, client):
        """Test connexion MEXC réussie"""
        with patch('api.live_trading_endpoints.ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_exchange.fetch_balance.return_value = {
                'USDT': {'free': 1000, 'used': 0, 'total': 1000}
            }
            mock_mexc.return_value = mock_exchange

            response = client.post("/api/live/test-connection", json={
                'api_key': 'test_key',
                'api_secret': 'test_secret'
            })

            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['balance_usdt'] == 1000

    def test_test_connection_missing_keys(self, client):
        """Test connexion sans API keys"""
        response = client.post("/api/live/test-connection", json={})

        assert response.status_code == 400

    def test_test_connection_api_error(self, client):
        """Test erreur API MEXC"""
        with patch('api.live_trading_endpoints.ccxt.mexc') as mock_mexc:
            mock_exchange = Mock()
            mock_exchange.fetch_balance.side_effect = Exception("API Error")
            mock_mexc.return_value = mock_exchange

            response = client.post("/api/live/test-connection", json={
                'api_key': 'test_key',
                'api_secret': 'test_secret'
            })

            assert response.status_code == 400
            data = response.json()
            assert 'API Error' in data['detail']


class TestEmergencyStop:
    """Tests POST /emergency-stop"""

    @patch('main.live_order_manager')
    def test_emergency_stop_with_manager(self, mock_manager, client):
        """Test arrêt d'urgence avec manager actif"""
        mock_manager.dry_run = False
        mock_manager.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'size': 0.1}
        ]

        response = client.post("/api/live/emergency-stop")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'stopped' in data

    @patch('main.live_order_manager', None)
    def test_emergency_stop_no_manager(self, client):
        """Test arrêt d'urgence sans manager"""
        response = client.post("/api/live/emergency-stop")

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['positions_closed'] == 0


class TestGetPositions:
    """Tests GET /positions"""

    @patch('main.live_order_manager')
    def test_get_positions_with_manager(self, mock_manager, client):
        """Test récupération positions"""
        mock_manager.get_open_positions.return_value = [
            {'symbol': 'BTCUSDT', 'size': 0.1, 'pnl': 50}
        ]

        response = client.get("/api/live/positions")

        assert response.status_code == 200
        data = response.json()
        assert len(data['positions']) == 1
        assert data['positions'][0]['symbol'] == 'BTCUSDT'

    @patch('main.live_order_manager', None)
    def test_get_positions_paper_mode(self, client):
        """Test positions en mode PAPER"""
        response = client.get("/api/live/positions")

        assert response.status_code == 200
        data = response.json()
        assert data['positions'] == []


class TestGetBalance:
    """Tests GET /balance"""

    @patch('main.live_order_manager')
    def test_get_balance_with_manager(self, mock_manager, client):
        """Test récupération balance"""
        mock_manager.get_balance.return_value = {
            'USDT': {'free': 1000, 'used': 100, 'total': 1100}
        }

        response = client.get("/api/live/balance")

        assert response.status_code == 200
        data = response.json()
        assert data['balance']['USDT']['total'] == 1100

    @patch('main.live_order_manager', None)
    def test_get_balance_paper_mode(self, client):
        """Test balance en mode PAPER"""
        response = client.get("/api/live/balance")

        assert response.status_code == 200
        data = response.json()
        assert data['balance'] == {}


class TestRegisterWebSocketCommands:
    """Tests enregistrement commandes WebSocket"""

    def test_register_commands(self):
        """Test enregistrement des commandes"""
        mock_ws_manager = Mock()

        register_websocket_commands(mock_ws_manager)

        # Vérifier que les commandes ont été enregistrées
        assert mock_ws_manager.register_command.called
        call_count = mock_ws_manager.register_command.call_count
        assert call_count >= 5  # Au moins 5 commandes enregistrées


class TestSetTrailingStop:
    """Tests POST /trailing-stop"""

    @patch('main.live_order_manager')
    def test_set_trailing_stop_success(self, mock_manager, client):
        """Test mise en place trailing stop"""
        mock_manager.set_trailing_stop.return_value = {'success': True}

        response = client.post("/api/live/trailing-stop", json={
            'symbol': 'BTCUSDT',
            'callback_rate': 1.0
        })

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @patch('main.live_order_manager', None)
    def test_set_trailing_stop_no_manager(self, client):
        """Test trailing stop sans manager"""
        response = client.post("/api/live/trailing-stop", json={
            'symbol': 'BTCUSDT',
            'callback_rate': 1.0
        })

        assert response.status_code == 400


class TestSetTpSl:
    """Tests POST /set-tp-sl"""

    @patch('main.live_order_manager')
    def test_set_tp_sl_success(self, mock_manager, client):
        """Test mise en place TP/SL"""
        mock_manager.set_tp_sl.return_value = {'success': True}

        response = client.post("/api/live/set-tp-sl", json={
            'symbol': 'BTCUSDT',
            'take_profit': 50000,
            'stop_loss': 40000
        })

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    @patch('main.live_order_manager', None)
    def test_set_tp_sl_no_manager(self, client):
        """Test TP/SL sans manager"""
        response = client.post("/api/live/set-tp-sl", json={
            'symbol': 'BTCUSDT',
            'take_profit': 50000
        })

        assert response.status_code == 400


class TestGetFundingRate:
    """Tests GET /funding-rate/{symbol}"""

    @patch('main.live_order_manager')
    def test_get_funding_rate_success(self, mock_manager, client):
        """Test récupération funding rate"""
        mock_manager.get_funding_rate.return_value = 0.0001

        response = client.get("/api/live/funding-rate/BTCUSDT")

        assert response.status_code == 200
        data = response.json()
        assert data['symbol'] == 'BTCUSDT'
        assert 'funding_rate' in data

    @patch('main.live_order_manager', None)
    def test_get_funding_rate_no_manager(self, client):
        """Test funding rate sans manager"""
        response = client.get("/api/live/funding-rate/BTCUSDT")

        assert response.status_code == 400
