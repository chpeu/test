"""
Tests d'intégration pour l'endpoint WebSocket FastAPI
Tests des commandes, validation Pydantic, gestion d'erreurs et race conditions
"""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect


class TestFastAPIWebSocketEndpoint:
    """Tests d'intégration pour l'endpoint /ws de FastAPI"""

    @pytest.fixture
    def client(self):
        """Fixture pour créer un TestClient FastAPI"""
        from main import app
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_websocket_connection_and_initial_status(self, client):
        """
        Test 1: Connexion WebSocket et réception du statut initial
        Vérifie que le client reçoit bien le statut initial après connexion
        """
        with client.websocket_connect("/ws") as websocket:
            # Le serveur doit envoyer le statut initial et les logs
            data = websocket.receive_json()

            # Vérifier que c'est un événement status
            assert data['type'] == 'event'
            assert data['event'] == 'status'
            assert 'data' in data

    @pytest.mark.asyncio
    async def test_update_config_command_with_valid_params(self, client):
        """
        Test 2: Commande update_config avec paramètres valides
        Vérifie que la validation Pydantic accepte les paramètres corrects
        """
        with patch('main.TRADING_CONFIG', {}) as mock_config:
            with client.websocket_connect("/ws") as websocket:
                # Skip initial messages
                for _ in range(50):  # Skip status + logs
                    try:
                        websocket.receive_json(timeout=0.1)
                    except:
                        break

                # Envoyer commande update_config valide
                command = {
                    'type': 'command',
                    'command': 'update_config',
                    'id': 123,
                    'params': {
                        'volume_multiplier': 1.0,
                        'min_score_required': 8.0,
                        'tp_sl_mode': 'ATR'
                    },
                    'timestamp': time.time()
                }
                websocket.send_json(command)

                # Recevoir réponse
                response = None
                for _ in range(10):  # Attendre la réponse
                    try:
                        data = websocket.receive_json(timeout=1.0)
                        if data.get('type') == 'command_response' and data.get('id') == 123:
                            response = data
                            break
                    except:
                        continue

                # Vérifier la réponse
                assert response is not None
                assert response['type'] == 'command_response'
                assert response['id'] == 123
                assert response['status'] == 'success'
                assert response['result']['success'] is True
                assert 'updated' in response['result']

    @pytest.mark.asyncio
    async def test_update_config_command_with_invalid_params(self, client):
        """
        Test 3: Commande update_config avec paramètres invalides
        Vérifie que la validation Pydantic rejette les paramètres incorrects
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Envoyer commande update_config avec paramètres invalides
            invalid_commands = [
                # volume_multiplier hors limites
                {
                    'type': 'command',
                    'command': 'update_config',
                    'id': 201,
                    'params': {'volume_multiplier': 5.0},  # Max est 2.0
                },
                # tp_sl_mode invalide
                {
                    'type': 'command',
                    'command': 'update_config',
                    'id': 202,
                    'params': {'tp_sl_mode': 'INVALID_MODE'},
                },
                # min_score_required négatif
                {
                    'type': 'command',
                    'command': 'update_config',
                    'id': 203,
                    'params': {'min_score_required': -5.0},
                },
            ]

            for invalid_cmd in invalid_commands:
                websocket.send_json(invalid_cmd)

                # Recevoir réponse d'erreur
                response = None
                for _ in range(5):
                    try:
                        data = websocket.receive_json(timeout=1.0)
                        if data.get('id') == invalid_cmd['id']:
                            response = data
                            break
                    except:
                        continue

                # Vérifier que c'est une erreur
                assert response is not None
                assert data.get('type') in ['command_error', 'command_response']
                # Si c'est une command_response, vérifier qu'il y a une erreur
                if data.get('type') == 'command_response':
                    assert 'error' in data or data.get('status') != 'success'

    @pytest.mark.asyncio
    async def test_ping_pong_heartbeat(self, client):
        """
        Test 4: Heartbeat ping/pong
        Vérifie que le serveur répond correctement aux pings
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Envoyer ping
            ping_msg = {
                'type': 'ping',
                'timestamp': time.time()
            }
            websocket.send_json(ping_msg)

            # Recevoir pong
            response = None
            for _ in range(5):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('type') == 'pong':
                        response = data
                        break
                except:
                    continue

            # Vérifier le pong
            assert response is not None
            assert response['type'] == 'pong'
            assert 'timestamp' in response

    @pytest.mark.asyncio
    async def test_concurrent_config_updates_with_lock(self):
        """
        Test 5: Mises à jour concurrentes de la config avec lock
        Vérifie que l'asyncio.Lock empêche les race conditions
        """
        from main import _config_lock, UpdateConfigParams
        from pydantic import ValidationError

        # Simuler 10 mises à jour concurrentes
        update_count = [0]  # Compteur thread-safe

        async def update_config(value):
            # Simuler la validation Pydantic
            try:
                validated = UpdateConfigParams(volume_multiplier=value)
            except ValidationError:
                return

            # Utiliser le lock (comme dans handle_client_command)
            async with _config_lock:
                # Simuler mise à jour
                await asyncio.sleep(0.01)  # Simuler traitement
                update_count[0] += 1

        # Lancer 10 mises à jour en parallèle
        tasks = [update_config(0.5 + i * 0.1) for i in range(10)]
        await asyncio.gather(*tasks)

        # Vérifier que toutes les mises à jour ont été faites
        assert update_count[0] == 10

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe_channels(self, client):
        """
        Test 6: Subscription et unsubscription aux channels
        Vérifie que les clients peuvent s'abonner et se désabonner de channels
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Subscribe to channel 'positions'
            subscribe_msg = {
                'type': 'subscribe',
                'channel': 'positions'
            }
            websocket.send_json(subscribe_msg)

            # Recevoir confirmation
            response = None
            for _ in range(5):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('type') == 'subscribed':
                        response = data
                        break
                except:
                    continue

            # Vérifier subscription
            assert response is not None
            assert response['type'] == 'subscribed'
            assert response['channel'] == 'positions'

            # Unsubscribe
            unsubscribe_msg = {
                'type': 'unsubscribe',
                'channel': 'positions'
            }
            websocket.send_json(unsubscribe_msg)

            # Recevoir confirmation
            response = None
            for _ in range(5):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('type') == 'unsubscribed':
                        response = data
                        break
                except:
                    continue

            # Vérifier unsubscription
            assert response is not None
            assert response['type'] == 'unsubscribed'
            assert response['channel'] == 'positions'

    @pytest.mark.asyncio
    async def test_get_state_request(self, client):
        """
        Test 7: Requête get_state via WebSocket
        Vérifie que le client peut récupérer l'état complet via WebSocket
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Envoyer requête state
            request_msg = {
                'type': 'request',
                'request_type': 'state',
                'id': 456
            }
            websocket.send_json(request_msg)

            # Recevoir réponse
            response = None
            for _ in range(10):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('type') == 'request_response' and data.get('id') == 456:
                        response = data
                        break
                except:
                    continue

            # Vérifier la réponse
            assert response is not None
            assert response['type'] == 'request_response'
            assert response['id'] == 456
            assert response['request_type'] == 'state'
            assert 'data' in response

            state_data = response['data']
            assert 'success' in state_data
            assert 'session_id' in state_data
            assert 'config' in state_data
            assert 'scanner' in state_data
            assert 'position' in state_data
            assert 'stats' in state_data

    @pytest.mark.asyncio
    async def test_log_config_command_with_validation(self, client):
        """
        Test 8: Commande log_config avec validation Pydantic
        Vérifie que la validation LogConfigParams fonctionne
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Envoyer commande log_config valide
            command = {
                'type': 'command',
                'command': 'log_config',
                'id': 789,
                'params': {
                    'key': 'volume_multiplier',
                    'change': '0.95 → 1.00'
                }
            }
            websocket.send_json(command)

            # Recevoir réponse
            response = None
            for _ in range(10):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('type') == 'command_response' and data.get('id') == 789:
                        response = data
                        break
                except:
                    continue

            # Vérifier la réponse
            assert response is not None
            assert response['type'] == 'command_response'
            assert response['id'] == 789
            assert response['result']['status'] == 'logged'
            assert response['result']['key'] == 'volume_multiplier'
            assert response['result']['change'] == '0.95 → 1.00'

    @pytest.mark.asyncio
    async def test_unknown_command_error(self, client):
        """
        Test 9: Commande inconnue
        Vérifie que les commandes inconnues retournent une erreur
        """
        with client.websocket_connect("/ws") as websocket:
            # Skip initial messages
            for _ in range(50):
                try:
                    websocket.receive_json(timeout=0.1)
                except:
                    break

            # Envoyer commande inconnue
            command = {
                'type': 'command',
                'command': 'invalid_command_xyz',
                'id': 999,
                'params': {}
            }
            websocket.send_json(command)

            # Recevoir réponse d'erreur
            response = None
            for _ in range(5):
                try:
                    data = websocket.receive_json(timeout=1.0)
                    if data.get('id') == 999:
                        response = data
                        break
                except:
                    continue

            # Vérifier l'erreur
            assert response is not None
            assert data.get('type') == 'command_error'
            assert 'error' in data
            assert 'inconnue' in data['error'].lower() or 'unknown' in data['error'].lower()


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
