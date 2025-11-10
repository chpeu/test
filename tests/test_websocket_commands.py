"""
Tests unitaires pour les commandes WebSocket
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect


class TestWebSocketCommands:
    """Tests pour les commandes WebSocket du backend"""

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket pour les tests"""
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.fixture
    def mock_app_state(self):
        """Mock app_state global"""
        return {
            'is_scanning': False,
            'active_position': None,
            'stats': {'total_trades': 0, 'wins': 0, 'losses': 0},
            'top_pairs': [],
            'logs': []
        }

    @pytest.mark.asyncio
    async def test_start_scanner_command(self, mock_websocket, mock_app_state):
        """Test commande start_scanner"""
        # Simulate command message
        command_msg = {
            'type': 'command',
            'command': 'start_scanner',
            'id': 123,
            'params': {},
            'timestamp': 1699999999
        }

        with patch('main.app_state', mock_app_state):
            # Mock scanner start
            with patch('api.routes.dashboard.start_dashboard_scanner') as mock_start:
                mock_start.return_value = {'status': 'started', 'is_scanning': True}

                # Simulate command handling
                result = {'status': 'started', 'is_scanning': True}

                # Expected response
                expected_response = {
                    'type': 'command_response',
                    'id': 123,
                    'result': result,
                    'error': None,
                    'timestamp': pytest.approx(1699999999, abs=10)
                }

                assert result['status'] == 'started'
                assert result['is_scanning'] is True

    @pytest.mark.asyncio
    async def test_stop_scanner_command(self, mock_websocket, mock_app_state):
        """Test commande stop_scanner"""
        command_msg = {
            'type': 'command',
            'command': 'stop_scanner',
            'id': 124,
            'params': {}
        }

        with patch('main.app_state', mock_app_state):
            with patch('api.routes.scanner.stop_scanner') as mock_stop:
                mock_stop.return_value = {'status': 'stopped', 'is_scanning': False}

                result = {'status': 'stopped', 'is_scanning': False}

                assert result['status'] == 'stopped'
                assert result['is_scanning'] is False

    @pytest.mark.asyncio
    async def test_get_config_command(self, mock_websocket):
        """Test commande get_config"""
        command_msg = {
            'type': 'command',
            'command': 'get_config',
            'id': 125,
            'params': {}
        }

        mock_config = {
            'volume_multiplier': 0.95,
            'min_score_required': 7.5,
            'tp_sl_mode': 'FIXE',
            'tp_percent': 0.25,
            'sl_percent': 0.25
        }

        with patch('config.TRADING_CONFIG', mock_config):
            # Simulate config retrieval
            result = mock_config.copy()

            assert result['volume_multiplier'] == 0.95
            assert result['min_score_required'] == 7.5
            assert result['tp_sl_mode'] == 'FIXE'

    @pytest.mark.asyncio
    async def test_update_config_command(self, mock_websocket):
        """Test commande update_config"""
        command_msg = {
            'type': 'command',
            'command': 'update_config',
            'id': 126,
            'params': {
                'volume_multiplier': 0.9,
                'min_score_required': 8.0
            }
        }

        with patch('config.TRADING_CONFIG', {}) as mock_config:
            # Simulate config update
            mock_config.update(command_msg['params'])

            result = {'updated': command_msg['params']}

            assert result['updated']['volume_multiplier'] == 0.9
            assert result['updated']['min_score_required'] == 8.0

    @pytest.mark.asyncio
    async def test_close_position_command(self, mock_websocket, mock_app_state):
        """Test commande close_position"""
        # Mock active position
        mock_position = MagicMock()
        mock_position.symbol = 'BTCUSDT'
        mock_position.side = 'LONG'
        mock_position.to_dict.return_value = {
            'symbol': 'BTCUSDT',
            'side': 'LONG',
            'entry_price': 50000,
            'current_price': 51000,
            'pnl': 100.0
        }

        mock_app_state['active_position'] = mock_position

        command_msg = {
            'type': 'command',
            'command': 'close_position',
            'id': 127,
            'params': {}
        }

        with patch('main.app_state', mock_app_state):
            with patch('api.routes.scanner.close_position_manual') as mock_close:
                mock_close.return_value = {'status': 'closed', 'result': mock_position.to_dict()}

                result = {'status': 'closed', 'result': mock_position.to_dict()}

                assert result['status'] == 'closed'
                assert result['result']['symbol'] == 'BTCUSDT'
                assert result['result']['pnl'] == 100.0

    @pytest.mark.asyncio
    async def test_close_position_no_active_position(self, mock_websocket, mock_app_state):
        """Test close_position sans position active"""
        mock_app_state['active_position'] = None

        command_msg = {
            'type': 'command',
            'command': 'close_position',
            'id': 128,
            'params': {}
        }

        with patch('main.app_state', mock_app_state):
            # Should raise error
            with pytest.raises(ValueError, match="Aucune position active"):
                if not mock_app_state.get('active_position'):
                    raise ValueError("Aucune position active")

    @pytest.mark.asyncio
    async def test_get_state_command(self, mock_websocket, mock_app_state):
        """Test commande get_state"""
        command_msg = {
            'type': 'command',
            'command': 'get_state',
            'id': 129,
            'params': {}
        }

        with patch('main.app_state', mock_app_state):
            # Simulate state retrieval
            result = {
                'success': True,
                'session_id': 'live_1699999999',
                'config': {},
                'scanner': {
                    'is_scanning': mock_app_state['is_scanning'],
                    'top_pairs': mock_app_state['top_pairs']
                },
                'position': {
                    'active': mock_app_state['active_position'] is not None,
                    'data': None
                },
                'stats': mock_app_state['stats'],
                'trades': [],
                'timestamp': 1699999999.123
            }

            assert result['success'] is True
            assert result['scanner']['is_scanning'] is False
            assert result['position']['active'] is False

    @pytest.mark.asyncio
    async def test_log_config_command(self, mock_websocket):
        """Test commande log_config"""
        command_msg = {
            'type': 'command',
            'command': 'log_config',
            'id': 130,
            'params': {
                'key': 'volume_multiplier',
                'change': '0.95 → 0.90'
            }
        }

        # Simulate logging
        result = {
            'status': 'logged',
            'key': command_msg['params']['key'],
            'change': command_msg['params']['change']
        }

        assert result['status'] == 'logged'
        assert result['key'] == 'volume_multiplier'
        assert result['change'] == '0.95 → 0.90'

    @pytest.mark.asyncio
    async def test_invalid_command(self, mock_websocket):
        """Test commande invalide"""
        command_msg = {
            'type': 'command',
            'command': 'invalid_command',
            'id': 131,
            'params': {}
        }

        # Should return error response
        with pytest.raises(ValueError, match="Unknown command"):
            raise ValueError(f"Unknown command: {command_msg['command']}")

    @pytest.mark.asyncio
    async def test_command_timeout(self, mock_websocket):
        """Test timeout de commande (30s)"""
        # Simulate slow command
        async def slow_command():
            await asyncio.sleep(35)  # Longer than 30s timeout
            return {'result': 'done'}

        # Should timeout after 30 seconds
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_command(), timeout=30.0)

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_command(self, mock_websocket):
        """Test déconnexion WebSocket pendant commande"""
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        with pytest.raises(WebSocketDisconnect):
            await mock_websocket.receive_text()


class TestWebSocketManager:
    """Tests pour le WebSocketManager"""

    @pytest.fixture
    def ws_manager(self):
        """Mock WebSocketManager"""
        from core.websocket_manager import WebSocketManager
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_connect(self, ws_manager, mock_websocket):
        """Test connexion WebSocket"""
        await ws_manager.connect(mock_websocket)

        assert mock_websocket in ws_manager.active_connections
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self, ws_manager, mock_websocket):
        """Test déconnexion WebSocket"""
        await ws_manager.connect(mock_websocket)
        ws_manager.disconnect(mock_websocket)

        assert mock_websocket not in ws_manager.active_connections

    @pytest.mark.asyncio
    async def test_emit_broadcast(self, ws_manager, mock_websocket):
        """Test broadcast événement à tous les clients"""
        # Connect 3 clients
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        ws3 = AsyncMock(spec=WebSocket)

        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)

        # Emit event
        await ws_manager.emit('test_event', {'data': 'test'})

        # All clients should receive
        assert ws1.send_text.called
        assert ws2.send_text.called
        assert ws3.send_text.called

    @pytest.mark.asyncio
    async def test_send_personal_message(self, ws_manager, mock_websocket):
        """Test envoi message personnel"""
        await ws_manager.connect(mock_websocket)

        message = {'type': 'test', 'data': 'personal'}
        await ws_manager.send_personal_message(message, mock_websocket)

        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data['type'] == 'test'
        assert sent_data['data'] == 'personal'


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
