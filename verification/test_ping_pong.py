#!/usr/bin/env python3
"""
Test simple : envoyer un ping et attendre un pong
"""
import asyncio
import websockets
import json
import time

async def test_one_ping():
    uri = "ws://127.0.0.1:5000/ws"
    try:
        # Désactiver le ping/pong automatique de websockets pour éviter les interférences
        async with websockets.connect(uri, timeout=10, ping_interval=None, ping_timeout=None) as ws:
            print("✅ Connecté")
            # Attendre server_hello et ping de test
            msg1 = await ws.recv()
            print("📨 1:", json.loads(msg1))
            msg2 = await ws.recv()
            print("📨 2:", json.loads(msg2))
            # Envoyer un ping et attendre un pong
            await asyncio.sleep(3)  # Attendre 3s pour être sûr que le backend est dans sa boucle d'écoute
            ping = {"type": "ping", "timestamp": time.time(), "ping_id": 12345}
            await ws.send(json.dumps(ping))
            print("📤 Ping envoyé (ping_id=12345)")
            # Envoyer un deuxième ping après 2s au cas où le premier est perdu
            await asyncio.sleep(2)
            ping2 = {"type": "ping", "timestamp": time.time(), "ping_id": 54321}
            await ws.send(json.dumps(ping2))
            print("📤 Deuxième ping envoyé (ping_id=54321)")
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(resp)
                print("📨 Réponse:", data)
                if data.get('type') == 'pong' and data.get('ping_id') in (12345, 54321):
                    print("✅ Pong reçu ! Le backend répond bien aux pings.")
                else:
                    print("⚠️ Réponse inattendue")
            except asyncio.TimeoutError:
                print("❌ Timeout : pas de pong reçu")
    except Exception as e:
        print("❌ Erreur :", e)

asyncio.run(test_one_ping())
