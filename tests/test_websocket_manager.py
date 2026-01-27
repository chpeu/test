"""
Tests pour core/websocket_manager.py
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from fastapi import WebSocket, WebSocketDisconnect
from core.websocket_manager import WebSocketManager


class TestWebSocketManager:
    """Tests pour WebSocketManager"""

    def test_init(self):
        """Test initialisation"""
        manager = WebSocketManager()
        assert len(manager.active_connections) == 0
        assert len(manager.connection_data) == 0
        assert len(manager.rooms) == 0
        # _lock est initialisé paresseusement via la propriété lock
        assert manager._lock is None
        assert manager.lock is not None
        assert manager._lock is not None

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connexion WebSocket"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        # Vérifier que le websocket est ajouté
        assert mock_websocket in manager.active_connections
        assert mock_websocket in manager.connection_data
        assert 'connected_at' in manager.connection_data[mock_websocket]
        assert 'last_ping' in manager.connection_data[mock_websocket]
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test déconnexion WebSocket"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        # Connecter d'abord
        await manager.connect(mock_websocket)
        assert mock_websocket in manager.active_connections

        # Déconnecter
        await manager.disconnect(mock_websocket)

        # Vérifier que le websocket est retiré
        assert mock_websocket not in manager.active_connections
        assert mock_websocket not in manager.connection_data

    @pytest.mark.asyncio
    async def test_disconnect_from_rooms(self):
        """Test déconnexion retire aussi des rooms"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        # Connecter et ajouter à une room
        await manager.connect(mock_websocket)
        manager.subscribe(mock_websocket, "test_room")

        # Vérifier que le websocket est dans la room
        assert mock_websocket in manager.rooms["test_room"]

        # Déconnecter
        await manager.disconnect(mock_websocket)

        # Vérifier que le websocket est retiré de la room
        assert mock_websocket not in manager.rooms["test_room"]

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self):
        """Test envoi message personnel réussi"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        message = {"test": "data"}
        await manager.send_personal_message(message, mock_websocket)

        # Vérifier que send_text a été appelé
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message == message

    @pytest.mark.asyncio
    async def test_send_personal_message_disconnected(self):
        """Test envoi message à un WebSocket déconnecté"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_text.side_effect = WebSocketDisconnect()

        await manager.connect(mock_websocket)

        message = {"test": "data"}
        await manager.send_personal_message(message, mock_websocket)

        # Le websocket devrait être déconnecté automatiquement
        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_personal_message_timeout_disconnects(self, monkeypatch: pytest.MonkeyPatch):
        """Test envoi message avec timeout"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        async def _fake_wait_for(awaitable, timeout=None):
            raise asyncio.TimeoutError

        monkeypatch.setattr(asyncio, "wait_for", _fake_wait_for)

        await manager.send_personal_message({"test": "data"}, mock_websocket)

        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_personal_message_error(self):
        """Test envoi message avec erreur"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_text.side_effect = Exception("Send error")

        await manager.connect(mock_websocket)

        message = {"test": "data"}
        await manager.send_personal_message(message, mock_websocket)

        # Le websocket devrait être déconnecté automatiquement
        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """Test broadcast sans connexions"""
        manager = WebSocketManager()

        message = {"test": "data"}
        # Ne devrait pas lever d'exception
        await manager.broadcast(message)

    @pytest.mark.asyncio
    async def test_broadcast_success(self):
        """Test broadcast réussi"""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        message = {"test": "data"}
        await manager.broadcast(message)

        # Vérifier que tous les websockets ont reçu le message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_disconnect(self):
        """Test broadcast avec déconnexion pendant envoi"""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws2.send_text.side_effect = WebSocketDisconnect()

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        message = {"test": "data"}
        await manager.broadcast(message)

        # ws1 devrait avoir reçu le message
        mock_ws1.send_text.assert_called_once()
        # ws2 devrait être déconnecté
        assert mock_ws2 not in manager.active_connections

    @pytest.mark.asyncio
    async def test_emit(self):
        """Test émission événement"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        await manager.emit('test_event', {'data': 'value'})

        # Vérifier que le message a été envoyé
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message['type'] == 'event'
        assert sent_message['event'] == 'test_event'
        assert sent_message['data'] == {'data': 'value'}

    @pytest.mark.asyncio
    async def test_send_status(self):
        """Test envoi status"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        status_data = {'status': 'active'}
        await manager.send_status(status_data)

        # Vérifier que le message a été envoyé
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message['event'] == 'status'
        assert sent_message['data'] == status_data

    @pytest.mark.asyncio
    async def test_send_log(self):
        """Test envoi log"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        log_entry = {'level': 'INFO', 'message': 'Test'}
        await manager.send_log(log_entry)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_position_update(self):
        """Test envoi position update"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        position_data = {'symbol': 'BTC/USDT', 'pnl': 100}
        await manager.send_position_update(position_data)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_position_opened(self):
        """Test envoi position opened"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        position_data = {'symbol': 'BTC/USDT'}
        await manager.send_position_opened(position_data)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_position_closed(self):
        """Test envoi position closed"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        result = {'pnl': 100}
        await manager.send_position_closed(result)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_stats_update(self):
        """Test envoi stats update"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        stats_data = {'total_trades': 10}
        await manager.send_stats_update(stats_data)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_top_pairs_update(self):
        """Test envoi top pairs update"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        pairs = [{'symbol': 'BTC/USDT'}, {'symbol': 'ETH/USDT'}]
        await manager.send_top_pairs_update(pairs)

        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert 'pairs' in sent_message['data']

    @pytest.mark.asyncio
    async def test_send_config_change(self):
        """Test envoi config change"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        config_data = {'param': 'value'}
        await manager.send_config_change(config_data)

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_scan_started(self):
        """Test envoi scan started"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        await manager.send_scan_started({'total': 100})

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_scan_complete(self):
        """Test envoi scan complete"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        await manager.send_scan_complete({'found': 5})

        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_scan_progress(self):
        """Test envoi scan progress"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        await manager.send_scan_progress(50)

        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message['data']['progress'] == 50

    def test_get_connection_count(self):
        """Test récupération nombre de connexions"""
        manager = WebSocketManager()
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_get_connection_count_with_connections(self):
        """Test récupération nombre de connexions avec connexions actives"""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)

        assert manager.get_connection_count() == 2

    @pytest.mark.asyncio
    async def test_ping_all_no_connections(self):
        """Test ping sans connexions"""
        manager = WebSocketManager()

        # Ne devrait pas lever d'exception
        await manager.ping_all()

    @pytest.mark.asyncio
    async def test_ping_all_with_connections(self):
        """Test ping avec connexions"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket)

        await manager.ping_all()

        # Vérifier que le ping a été envoyé
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message['type'] == 'ping'

    def test_subscribe_new_room(self):
        """Test souscription à une nouvelle room"""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)

        manager.subscribe(mock_websocket, "test_room")

        assert "test_room" in manager.rooms
        assert mock_websocket in manager.rooms["test_room"]

    def test_subscribe_existing_room(self):
        """Test souscription à une room existante"""
        manager = WebSocketManager()
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws2 = Mock(spec=WebSocket)

        manager.subscribe(mock_ws1, "test_room")
        manager.subscribe(mock_ws2, "test_room")

        assert len(manager.rooms["test_room"]) == 2
        assert mock_ws1 in manager.rooms["test_room"]
        assert mock_ws2 in manager.rooms["test_room"]


# Tests d'intégration
class TestWebSocketManagerIntegration:
    """Tests d'intégration pour WebSocketManager"""

    @pytest.mark.asyncio
    async def test_multiple_connections_broadcast(self):
        """Test broadcast avec plusieurs connexions"""
        manager = WebSocketManager()
        connections = [AsyncMock(spec=WebSocket) for _ in range(5)]

        # Connecter tous
        for conn in connections:
            await manager.connect(conn)

        assert manager.get_connection_count() == 5

        # Broadcast un message
        message = {"test": "data"}
        await manager.broadcast(message)

        # Tous devraient avoir reçu le message
        for conn in connections:
            conn.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self):
        """Test nettoyage automatique des connexions en erreur"""
        manager = WebSocketManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws3 = AsyncMock(spec=WebSocket)

        # ws2 va échouer lors du broadcast
        mock_ws2.send_text.side_effect = ConnectionError("Connection lost")

        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)
        await manager.connect(mock_ws3)

        assert manager.get_connection_count() == 3

        # Broadcast
        await manager.broadcast({"test": "data"})

        # ws2 devrait être déconnecté automatiquement
        assert manager.get_connection_count() == 2
        assert mock_ws2 not in manager.active_connections

    @pytest.mark.asyncio
    async def test_room_isolation(self):
        """Test isolation des rooms"""
        manager = WebSocketManager()
        ws_room1 = AsyncMock(spec=WebSocket)
        ws_room2 = AsyncMock(spec=WebSocket)

        await manager.connect(ws_room1)
        await manager.connect(ws_room2)

        manager.subscribe(ws_room1, "room1")
        manager.subscribe(ws_room2, "room2")

        # Vérifier l'isolation
        assert ws_room1 in manager.rooms["room1"]
        assert ws_room1 not in manager.rooms["room2"]
        assert ws_room2 in manager.rooms["room2"]
        assert ws_room2 not in manager.rooms["room1"]


# Tests pour les nouvelles fonctionnalités ajoutées
class TestWebSocketManagerCommands:
    """Tests pour les commandes WebSocket"""

    def test_command_decorator(self):
        """Test décorateur d'enregistrement de commandes"""
        manager = WebSocketManager()
        
        @manager.command("test_command")
        def test_handler(data, websocket):
            return {"result": "success"}
        
        # Vérifier que la commande est enregistrée
        assert "test_command" in manager._command_handlers
        commands = manager.get_registered_commands()
        assert "test_command" in commands

    def test_register_command_programmatic(self):
        """Test enregistrement programmatique de commandes"""
        manager = WebSocketManager()
        
        def test_handler(data, websocket):
            return {"result": "success"}
        
        manager.register_command("prog_command", test_handler)
        
        # Vérifier que la commande est enregistrée
        assert "prog_command" in manager._command_handlers
        commands = manager.get_registered_commands()
        assert "prog_command" in commands

    @pytest.mark.asyncio
    async def test_handle_command_sync_handler(self):
        """Test exécution commande avec handler synchrone"""
        manager = WebSocketManager()
        
        def test_handler(data, websocket):
            return {"value": data.get("input", "default")}
        
        manager.register_command("sync_cmd", test_handler)
        
        result = await manager.handle_command("sync_cmd", {"input": "test"}, None)
        assert result["value"] == "test"

    @pytest.mark.asyncio
    async def test_handle_command_async_handler(self):
        """Test exécution commande avec handler asynchrone"""
        manager = WebSocketManager()
        
        async def async_handler(data, websocket):
            return {"async_result": data.get("key", "default")}
        
        manager.register_command("async_cmd", async_handler)
        
        result = await manager.handle_command("async_cmd", {"key": "async_test"}, None)
        assert result["async_result"] == "async_test"

    @pytest.mark.asyncio
    async def test_handle_command_unknown(self):
        """Test commande inconnue"""
        manager = WebSocketManager()
        
        result = await manager.handle_command("unknown_cmd", {}, None)
        assert result["success"] is False
        assert "Unknown command" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_command_handler_exception(self):
        """Test gestion d'exception dans handler"""
        manager = WebSocketManager()
        
        def failing_handler(data, websocket):
            raise ValueError("Handler failed")
        
        manager.register_command("fail_cmd", failing_handler)
        
        result = await manager.handle_command("fail_cmd", {}, None)
        assert result["success"] is False
        assert "Handler failed" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_command_handler_returns_none(self):
        """Test handler qui retourne None"""
        manager = WebSocketManager()
        
        def none_handler(data, websocket):
            return None
        
        manager.register_command("none_cmd", none_handler)
        
        result = await manager.handle_command("none_cmd", {}, None)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_handle_command_fastapi_jsonresponse(self):
        """Test handler qui retourne JSONResponse FastAPI"""
        manager = WebSocketManager()
        
        # Mock JSONResponse object
        class MockJSONResponse:
            def __init__(self, data):
                self.body = json.dumps(data).encode()
        
        def fastapi_handler(data, websocket):
            return MockJSONResponse({"fastapi": True, "data": data})
        
        manager.register_command("fastapi_cmd", fastapi_handler)
        
        result = await manager.handle_command("fastapi_cmd", {"test": "value"}, None)
        assert result["fastapi"] is True
        assert result["data"]["test"] == "value"

    def test_get_registered_commands_empty(self):
        """Test récupération commandes vides"""
        manager = WebSocketManager()
        commands = manager.get_registered_commands()
        assert commands == []

    def test_get_registered_commands_multiple(self):
        """Test récupération plusieurs commandes"""
        manager = WebSocketManager()
        
        def handler1(data, ws): pass
        def handler2(data, ws): pass
        
        manager.register_command("cmd1", handler1)
        manager.register_command("cmd2", handler2)
        
        commands = manager.get_registered_commands()
        assert "cmd1" in commands
        assert "cmd2" in commands
        assert len(commands) == 2

    @pytest.mark.asyncio
    async def test_get_connection_id_existing(self):
        """Test récupération ID connexion existante"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        
        await manager.connect(mock_websocket)
        
        conn_id = manager.get_connection_id(mock_websocket)
        assert conn_id is not None
        assert isinstance(conn_id, int)

    def test_get_connection_id_non_existing(self):
        """Test récupération ID connexion inexistante"""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        
        conn_id = manager.get_connection_id(mock_websocket)
        assert conn_id is None

    @pytest.mark.asyncio
    async def test_unsubscribe_existing_room(self):
        """Test désabonnement d'une room existante"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        
        await manager.connect(mock_websocket)
        manager.subscribe(mock_websocket, "test_room")
        
        # Vérifier présence
        assert mock_websocket in manager.rooms["test_room"]
        
        # Désabonner
        manager.unsubscribe(mock_websocket, "test_room")
        
        # Vérifier absence
        assert mock_websocket not in manager.rooms["test_room"]

    def test_unsubscribe_non_existing_room(self):
        """Test désabonnement d'une room inexistante"""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        
        # Ne devrait pas lever d'exception
        manager.unsubscribe(mock_websocket, "non_existing_room")
        
        # Room ne devrait pas être créée
        assert "non_existing_room" not in manager.rooms

    @pytest.mark.asyncio
    async def test_ping_all_with_timestamp(self):
        """Test ping avec timestamp correct"""
        manager = WebSocketManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        
        await manager.connect(mock_websocket)
        
        with patch('core.websocket_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T12:00:00"
            
            await manager.ping_all()
            
            mock_websocket.send_text.assert_called_once()
            sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
            assert sent_message['type'] == 'ping'
            assert sent_message['timestamp'] == "2023-01-01T12:00:00"
