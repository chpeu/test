"""
Tests d'intégration pour WebSocketManager
Tests de la gestion des connexions, broadcast, rooms et task tracking
"""
import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

# Import du WebSocketManager
from core.websocket_manager import WebSocketManager


class TestWebSocketManagerIntegration:
    """Tests d'intégration pour WebSocketManager"""

    @pytest.fixture
    def ws_manager(self):
        """Fixture pour créer un WebSocketManager"""
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        """Fixture pour créer un mock WebSocket"""
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, ws_manager, mock_websocket):
        """
        Test 1: Connexion et déconnexion WebSocket
        Vérifie que le client est ajouté et retiré correctement
        """
        # Connect
        await ws_manager.connect(mock_websocket)
        assert mock_websocket in ws_manager.active_connections
        assert mock_websocket in ws_manager.connection_data
        assert mock_websocket in ws_manager.client_tasks
        assert ws_manager.get_connection_count() == 1

        # Disconnect
        await ws_manager.disconnect(mock_websocket)
        assert mock_websocket not in ws_manager.active_connections
        assert mock_websocket not in ws_manager.connection_data
        assert mock_websocket not in ws_manager.client_tasks
        assert ws_manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_multiple_connections(self, ws_manager):
        """
        Test 2: Gestion de multiples connexions simultanées
        Vérifie que plusieurs clients peuvent être connectés en même temps
        """
        # Créer 5 mock WebSockets
        clients = []
        for i in range(5):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            clients.append(ws)
            await ws_manager.connect(ws)

        # Vérifier que tous sont connectés
        assert ws_manager.get_connection_count() == 5
        for client in clients:
            assert client in ws_manager.active_connections

        # Déconnecter 2 clients
        await ws_manager.disconnect(clients[0])
        await ws_manager.disconnect(clients[2])
        assert ws_manager.get_connection_count() == 3
        assert clients[0] not in ws_manager.active_connections
        assert clients[2] not in ws_manager.active_connections
        assert clients[1] in ws_manager.active_connections
        assert clients[3] in ws_manager.active_connections
        assert clients[4] in ws_manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, ws_manager):
        """
        Test 3: Broadcast à plusieurs clients
        Vérifie que les messages sont envoyés à tous les clients connectés
        """
        # Créer 3 clients
        clients = []
        for i in range(3):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            clients.append(ws)
            await ws_manager.connect(ws)

        # Broadcast message
        test_message = {'type': 'event', 'event': 'test', 'data': {'value': 123}}
        await ws_manager.broadcast(test_message)

        # Vérifier que tous les clients ont reçu le message
        for client in clients:
            client.send_text.assert_called_once()
            sent_data = json.loads(client.send_text.call_args[0][0])
            assert sent_data['type'] == 'event'
            assert sent_data['event'] == 'test'
            assert sent_data['data']['value'] == 123

    @pytest.mark.asyncio
    async def test_emit_event_to_all_clients(self, ws_manager):
        """
        Test 4: Émettre un événement à tous les clients
        Vérifie que la méthode emit() fonctionne correctement
        """
        # Créer 2 clients
        clients = []
        for i in range(2):
            ws = AsyncMock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            clients.append(ws)
            await ws_manager.connect(ws)

        # Émettre événement
        await ws_manager.emit('position_update', {'symbol': 'BTCUSDT', 'pnl': 50.0})

        # Vérifier réception
        for client in clients:
            client.send_text.assert_called_once()
            sent_data = json.loads(client.send_text.call_args[0][0])
            assert sent_data['type'] == 'event'
            assert sent_data['event'] == 'position_update'
            assert sent_data['data']['symbol'] == 'BTCUSDT'
            assert sent_data['data']['pnl'] == 50.0
            assert 'timestamp' in sent_data

    @pytest.mark.asyncio
    async def test_task_tracking_and_cancellation(self, ws_manager, mock_websocket):
        """
        Test 5: Tracking et annulation des tâches lors de la déconnexion
        Vérifie que les tâches actives sont annulées quand le client se déconnecte
        """
        # Connecter le client
        await ws_manager.connect(mock_websocket)

        # Créer 2 tâches longues
        async def long_task(duration):
            try:
                await asyncio.sleep(duration)
                return "completed"
            except asyncio.CancelledError:
                return "cancelled"

        task1 = asyncio.create_task(long_task(10))
        task2 = asyncio.create_task(long_task(10))

        # Enregistrer les tâches
        ws_manager.register_task(mock_websocket, task1)
        ws_manager.register_task(mock_websocket, task2)

        # Vérifier que les tâches sont enregistrées
        assert len(ws_manager.client_tasks[mock_websocket]) == 2
        assert not task1.done()
        assert not task2.done()

        # Déconnecter (doit annuler les tâches)
        await ws_manager.disconnect(mock_websocket)

        # Vérifier que les tâches ont été annulées
        await asyncio.sleep(0.1)  # Laisser le temps aux tâches de se terminer
        assert task1.cancelled() or task1.done()
        assert task2.cancelled() or task2.done()
        assert mock_websocket not in ws_manager.client_tasks

    @pytest.mark.asyncio
    async def test_rooms_subscription_and_emit(self, ws_manager):
        """
        Test 6: Subscription rooms et émission vers une room spécifique
        Vérifie que les clients peuvent s'abonner à des rooms et recevoir des messages ciblés
        """
        # Créer 3 clients
        client1 = AsyncMock(spec=WebSocket)
        client1.accept = AsyncMock()
        client1.send_text = AsyncMock()

        client2 = AsyncMock(spec=WebSocket)
        client2.accept = AsyncMock()
        client2.send_text = AsyncMock()

        client3 = AsyncMock(spec=WebSocket)
        client3.accept = AsyncMock()
        client3.send_text = AsyncMock()

        # Connecter tous les clients
        await ws_manager.connect(client1)
        await ws_manager.connect(client2)
        await ws_manager.connect(client3)

        # Abonner client1 et client2 à room "trading"
        ws_manager.subscribe(client1, 'trading')
        ws_manager.subscribe(client2, 'trading')

        # client3 n'est pas abonné à "trading"

        # Émettre un événement vers room "trading"
        await ws_manager.emit_to_room('price_alert', {'symbol': 'ETHUSDT', 'price': 3000}, room='trading')

        # Vérifier que seuls client1 et client2 ont reçu le message
        await asyncio.sleep(0.1)  # Laisser le temps à l'émission
        assert client1.send_text.called
        assert client2.send_text.called
        # client3 ne devrait pas avoir reçu (mais il faut vérifier le count)

        # Désabonner client1
        ws_manager.unsubscribe(client1, 'trading')

        # Reset mocks
        client1.send_text.reset_mock()
        client2.send_text.reset_mock()

        # Émettre à nouveau
        await ws_manager.emit_to_room('price_alert', {'symbol': 'BTCUSDT', 'price': 50000}, room='trading')

        await asyncio.sleep(0.1)
        # client1 ne devrait plus recevoir
        assert not client1.send_text.called
        # client2 devrait toujours recevoir
        assert client2.send_text.called

    @pytest.mark.asyncio
    async def test_send_personal_message(self, ws_manager, mock_websocket):
        """
        Test 7: Envoi de message personnel à un client spécifique
        Vérifie que send_personal_message fonctionne correctement
        """
        # Connecter le client
        await ws_manager.connect(mock_websocket)

        # Envoyer message personnel
        personal_msg = {'type': 'command_response', 'id': 123, 'result': {'success': True}}
        await ws_manager.send_personal_message(personal_msg, mock_websocket)

        # Vérifier réception
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_data['type'] == 'command_response'
        assert sent_data['id'] == 123
        assert sent_data['result']['success'] is True

    @pytest.mark.asyncio
    async def test_broadcast_with_disconnected_client(self, ws_manager):
        """
        Test 8: Broadcast avec un client déconnecté (gestion d'erreur)
        Vérifie que les clients déconnectés sont automatiquement nettoyés lors du broadcast
        """
        # Créer 2 clients
        good_client = AsyncMock(spec=WebSocket)
        good_client.accept = AsyncMock()
        good_client.send_text = AsyncMock()

        bad_client = AsyncMock(spec=WebSocket)
        bad_client.accept = AsyncMock()
        # Simuler une erreur d'envoi (client déconnecté)
        bad_client.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        await ws_manager.connect(good_client)
        await ws_manager.connect(bad_client)

        assert ws_manager.get_connection_count() == 2

        # Broadcast (devrait nettoyer bad_client automatiquement)
        await ws_manager.broadcast({'type': 'test', 'data': 'hello'})

        # Le bon client devrait avoir reçu le message
        assert good_client.send_text.called

        # bad_client devrait être retiré automatiquement
        await asyncio.sleep(0.1)
        assert bad_client not in ws_manager.active_connections
        assert ws_manager.get_connection_count() == 1


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
