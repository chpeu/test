"""
Tests pour core/websocket_manager.py
Couverture des fonctionnalités WebSocket natives
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from core.websocket_manager import WebSocketManager, get_websocket_manager


class TestWebSocketManager:
    """Tests pour la classe WebSocketManager"""

    @pytest.fixture
    def ws_manager(self):
        """Créer une instance de WebSocketManager pour les tests"""
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_init(self, ws_manager):
        """Test initialisation du WebSocketManager"""
        assert ws_manager.active_connections == set()
        assert ws_manager.rooms == {}

    @pytest.mark.asyncio
    async def test_connect_adds_websocket(self, ws_manager):
        """Test ajout d'une connexion WebSocket"""
        mock_websocket = AsyncMock()

        await ws_manager.connect(mock_websocket)

        assert mock_websocket in ws_manager.active_connections
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_websocket(self, ws_manager):
        """Test suppression d'une connexion WebSocket"""
        mock_websocket = AsyncMock()

        await ws_manager.connect(mock_websocket)
        await ws_manager.disconnect(mock_websocket)

        assert mock_websocket not in ws_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, ws_manager):
        """Test broadcast vers toutes les connexions"""
        # Créer plusieurs connexions mock
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()

        await ws_manager.connect(mock_ws1)
        await ws_manager.connect(mock_ws2)
        await ws_manager.connect(mock_ws3)

        test_message = {'type': 'test', 'data': 'hello'}

        await ws_manager.broadcast(test_message)

        # Vérifier que tous ont reçu le message
        expected_json = json.dumps(test_message)
        mock_ws1.send_text.assert_called_once_with(expected_json)
        mock_ws2.send_text.assert_called_once_with(expected_json)
        mock_ws3.send_text.assert_called_once_with(expected_json)

    @pytest.mark.asyncio
    async def test_emit_sends_event_to_all(self, ws_manager):
        """Test émission d'événement vers toutes les connexions"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        await ws_manager.emit('test_event', {'key': 'value'})

        # Vérifier le format du message
        call_args = mock_ws.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message['type'] == 'event'
        assert message['event'] == 'test_event'
        assert message['data'] == {'key': 'value'}

    @pytest.mark.asyncio
    async def test_send_personal_message(self, ws_manager):
        """Test envoi vers un WebSocket spécifique"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await ws_manager.connect(mock_ws1)
        await ws_manager.connect(mock_ws2)

        test_message = {'type': 'test', 'data': 'specific'}

        await ws_manager.send_personal_message(test_message, mock_ws1)

        # Vérifier que seul ws1 a reçu
        assert mock_ws1.send_text.called
        assert not mock_ws2.send_text.called

    @pytest.mark.asyncio
    async def test_subscribe_to_room(self, ws_manager):
        """Test souscription à une room"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        ws_manager.subscribe(mock_ws, 'room1')

        assert 'room1' in ws_manager.rooms
        assert mock_ws in ws_manager.rooms['room1']

    @pytest.mark.asyncio
    async def test_unsubscribe_from_room(self, ws_manager):
        """Test désinscription d'une room"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        ws_manager.subscribe(mock_ws, 'room1')
        ws_manager.unsubscribe(mock_ws, 'room1')

        assert mock_ws not in ws_manager.rooms.get('room1', set())

    @pytest.mark.asyncio
    async def test_emit_to_room(self, ws_manager):
        """Test broadcast uniquement vers une room spécifique"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()

        await ws_manager.connect(mock_ws1)
        await ws_manager.connect(mock_ws2)
        await ws_manager.connect(mock_ws3)

        # Souscrire seulement ws1 et ws2 à la room
        ws_manager.subscribe(mock_ws1, 'vip_room')
        ws_manager.subscribe(mock_ws2, 'vip_room')

        await ws_manager.emit_to_room('test_event', {'data': 'vip only'}, 'vip_room')

        # Vérifier que seuls ws1 et ws2 ont reçu
        assert mock_ws1.send_text.called
        assert mock_ws2.send_text.called
        assert not mock_ws3.send_text.called

    @pytest.mark.asyncio
    async def test_get_connection_count(self, ws_manager):
        """Test comptage des connexions actives"""
        assert ws_manager.get_connection_count() == 0

        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await ws_manager.connect(mock_ws1)
        assert ws_manager.get_connection_count() == 1

        await ws_manager.connect(mock_ws2)
        assert ws_manager.get_connection_count() == 2

        await ws_manager.disconnect(mock_ws1)
        assert ws_manager.get_connection_count() == 1

    @pytest.mark.asyncio
    async def test_broadcast_handles_closed_connections(self, ws_manager):
        """Test que broadcast ignore les connexions fermées"""
        mock_ws_working = AsyncMock()
        mock_ws_broken = AsyncMock()
        mock_ws_broken.send_text.side_effect = Exception("Connection closed")

        await ws_manager.connect(mock_ws_working)
        await ws_manager.connect(mock_ws_broken)

        test_message = {'type': 'test', 'data': 'hello'}

        # Ne devrait pas lever d'exception
        await ws_manager.broadcast(test_message)

        # ws_working devrait avoir reçu le message
        assert mock_ws_working.send_text.called

    @pytest.mark.asyncio
    async def test_emit_multiple_events(self, ws_manager):
        """Test émission de plusieurs événements différents"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        # Émettre plusieurs événements
        await ws_manager.emit('event1', {'data': 1})
        await ws_manager.emit('event2', {'data': 2})
        await ws_manager.emit('event3', {'data': 3})

        # Vérifier que tous ont été envoyés
        assert mock_ws.send_text.call_count == 3

    @pytest.mark.asyncio
    async def test_send_log(self, ws_manager):
        """Test envoi de log via WebSocket"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        await ws_manager.send_log({
            'level': 'INFO',
            'message': 'Test log message'
        })

        # Vérifier le format du message
        call_args = mock_ws.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message['type'] == 'event'
        assert message['event'] == 'log'
        assert message['data']['level'] == 'INFO'
        assert message['data']['message'] == 'Test log message'

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_all_rooms(self, ws_manager):
        """Test que disconnect supprime la connexion de toutes les rooms"""
        mock_ws = AsyncMock()

        await ws_manager.connect(mock_ws)
        ws_manager.subscribe(mock_ws, 'room1')
        ws_manager.subscribe(mock_ws, 'room2')
        ws_manager.subscribe(mock_ws, 'room3')

        await ws_manager.disconnect(mock_ws)

        # Vérifier que mock_ws n'est plus dans aucune room
        assert mock_ws not in ws_manager.rooms.get('room1', set())
        assert mock_ws not in ws_manager.rooms.get('room2', set())
        assert mock_ws not in ws_manager.rooms.get('room3', set())

    @pytest.mark.asyncio
    async def test_send_status(self, ws_manager):
        """Test envoi de status via WebSocket"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        await ws_manager.send_status({'is_scanning': True})

        call_args = mock_ws.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message['type'] == 'event'
        assert message['event'] == 'status'
        assert message['data']['is_scanning'] is True

    @pytest.mark.asyncio
    async def test_send_position_update(self, ws_manager):
        """Test envoi de mise à jour de position"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        await ws_manager.send_position_update({'symbol': 'BTC/USDT', 'pnl': 100})

        call_args = mock_ws.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message['type'] == 'event'
        assert message['event'] == 'position_update'
        assert message['data']['symbol'] == 'BTC/USDT'

    @pytest.mark.asyncio
    async def test_send_config_change(self, ws_manager):
        """Test envoi de changement de config"""
        mock_ws = AsyncMock()
        await ws_manager.connect(mock_ws)

        await ws_manager.send_config_change({'tp_percent': 0.8})

        call_args = mock_ws.send_text.call_args[0][0]
        message = json.loads(call_args)

        assert message['type'] == 'event'
        assert message['event'] == 'config_change'
        assert message['data']['tp_percent'] == 0.8

    @pytest.mark.asyncio
    async def test_ping_all(self, ws_manager):
        """Test envoi de ping à tous les clients"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await ws_manager.connect(mock_ws1)
        await ws_manager.connect(mock_ws2)

        await ws_manager.ping_all()

        # Vérifier que tous ont reçu le ping
        assert mock_ws1.send_text.called
        assert mock_ws2.send_text.called

        call_args = mock_ws1.send_text.call_args[0][0]
        message = json.loads(call_args)
        assert message['type'] == 'ping'


class TestGetWebSocketManager:
    """Tests pour la fonction get_websocket_manager (singleton)"""

    def test_singleton_returns_same_instance(self):
        """Test que get_websocket_manager retourne toujours la même instance"""
        # Reset global instance
        import core.websocket_manager
        core.websocket_manager._websocket_manager = None

        instance1 = get_websocket_manager()
        instance2 = get_websocket_manager()

        assert instance1 is instance2

    def test_instance_is_websocket_manager(self):
        """Test que l'instance est bien un WebSocketManager"""
        instance = get_websocket_manager()
        assert isinstance(instance, WebSocketManager)


class TestWebSocketIntegration:
    """Tests d'intégration WebSocket"""

    @pytest.mark.asyncio
    async def test_multiple_clients_receive_broadcast(self):
        """Test que plusieurs clients reçoivent les broadcasts"""
        ws_manager = WebSocketManager()

        clients = [AsyncMock() for _ in range(5)]

        for client in clients:
            await ws_manager.connect(client)

        await ws_manager.emit('config_change', {'tp_percent': 0.8})

        # Tous les clients devraient avoir reçu
        for client in clients:
            assert client.send_text.called

    @pytest.mark.asyncio
    async def test_room_isolation(self):
        """Test que les rooms sont isolées"""
        ws_manager = WebSocketManager()

        ws_room_a1 = AsyncMock()
        ws_room_a2 = AsyncMock()
        ws_room_b1 = AsyncMock()
        ws_room_b2 = AsyncMock()

        await ws_manager.connect(ws_room_a1)
        await ws_manager.connect(ws_room_a2)
        await ws_manager.connect(ws_room_b1)
        await ws_manager.connect(ws_room_b2)

        ws_manager.subscribe(ws_room_a1, 'room_a')
        ws_manager.subscribe(ws_room_a2, 'room_a')
        ws_manager.subscribe(ws_room_b1, 'room_b')
        ws_manager.subscribe(ws_room_b2, 'room_b')

        # Broadcast vers room_a
        await ws_manager.emit_to_room('test_event', {'message': 'for A'}, 'room_a')

        # Seuls les clients de room_a devraient avoir reçu
        assert ws_room_a1.send_text.called
        assert ws_room_a2.send_text.called
        assert not ws_room_b1.send_text.called
        assert not ws_room_b2.send_text.called

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test opérations concurrentes"""
        ws_manager = WebSocketManager()

        clients = [AsyncMock() for _ in range(10)]

        # Connecter tous les clients en parallèle
        await asyncio.gather(*[ws_manager.connect(client) for client in clients])

        assert ws_manager.get_connection_count() == 10

        # Envoyer plusieurs broadcasts en parallèle
        await asyncio.gather(
            ws_manager.emit('event1', {'data': 1}),
            ws_manager.emit('event2', {'data': 2}),
            ws_manager.emit('event3', {'data': 3})
        )

        # Tous les clients devraient avoir reçu 3 messages
        for client in clients:
            assert client.send_text.call_count == 3
