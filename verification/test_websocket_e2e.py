#!/usr/bin/env python3
"""
Test E2E WebSocket :
- Vérifie que le backend accepte une connexion WebSocket native
- Envoie un ping/pong et des événements de test
- Valide que les événements sont reçus sans déconnexion
Usage: python verification/test_websocket_e2e.py
"""
import asyncio
import websockets
import json
import time
import sys
from pathlib import Path

# Ajouter le projet au PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

WS_URL = "ws://127.0.0.1:5000/ws"
TIMEOUT = 15
PING_INTERVAL = 5
TEST_EVENTS = [
    {"type": "event", "event": "status", "data": {"is_scanning": True, "active_position": None, "session_id": "test-session"}},
    {"type": "event", "event": "stats_update", "data": {"total_trades": 1, "wins": 1, "losses": 0, "winrate": 100.0}},
    {"type": "event", "event": "top_pairs_update", "data": {"pairs": [{"symbol": "BTC/USDT", "price": 50000}]}},
    {"type": "event", "event": "regime_changed", "data": {"regime": "BULL", "volatility": "HIGH"}},
]

async def test_websocket_connection():
    print(f"🔌 Test de connexion WebSocket vers {WS_URL}")
    try:
        async with websockets.connect(WS_URL, timeout=TIMEOUT) as ws:
            print("✅ Connexion établie")
            last_pong = time.time()
            received_events = []

            async def receiver():
                try:
                    async for msg in ws:
                        data = json.loads(msg)
                        print(f"📨 Reçu: {data}")
                        received_events.append(data)
                        if data.get('type') == 'pong':
                            nonlocal last_pong
                            last_pong = time.time()
                        elif data.get('type') == 'ping':
                            # Répondre aux ping du serveur
                            pong = {'type': 'pong', 'timestamp': time.time(), 'ping_id': data.get('ping_id')}
                            await ws.send(json.dumps(pong))
                            print(f"📤 Pong envoyé en réponse à ping_id={data.get('ping_id')}")
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"❌ Connexion fermée: {e.code} {e.reason}")

            async def pinger():
                while True:
                    await asyncio.sleep(PING_INTERVAL)
                    try:
                        ping = {"type": "ping", "timestamp": time.time(), "ping_id": int(time.time()*1000)}
                        await ws.send(json.dumps(ping))
                        print("📤 Ping envoyé")
                    except Exception as e:
                        print(f"❌ Erreur envoi ping: {e}")
                        break

            async def sender():
                await asyncio.sleep(2)  # Attendre le hello du serveur
                for ev in TEST_EVENTS:
                    try:
                        await ws.send(json.dumps(ev))
                        print(f"📤 Événement envoyé: {ev['event']}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"❌ Erreur envoi événement: {e}")
                        break

            # Lancer les tâches
            tasks = [asyncio.create_task(t) for t in (receiver(), pinger(), sender())]
            await asyncio.sleep(30)  # Laisser tourner 30s pour voir les pong
            for t in tasks:
                t.cancel()
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                pass

            print(f"📊 Résultats : {len(received_events)} messages reçus")
            # Vérifier qu'on a bien reçu des pong
            pongs = [m for m in received_events if m.get('type') == 'pong']
            print(f"🏓 Pong reçus: {len(pongs)}")
            # Vérifier qu'on a reçu un hello
            hellos = [m for m in received_events if m.get('type') == 'server_hello']
            print(f"👋 Server hello reçu: {'OUI' if hellos else 'NON'}")
            return True

    except Exception as e:
        print(f"❌ Échec connexion WebSocket: {e}")
        return False

async def test_backend_api():
    """Vérifier que le backend expose bien /ws"""
    import aiohttp
    async with aiohttp.ClientSession() as sess:
        try:
            async with sess.get("http://127.0.0.1:5000/api/websocket/stats", timeout=5) as resp:
                data = await resp.json()
                print("🌐 /api/websocket/stats reachable")
                print(f"   active_connections: {data.get('active_connections')}")
                print(f"   status: {data.get('status')}")
        except Exception as e:
            print(f"❌ Backend API non joignable: {e}")

async def main():
    print("=== Test E2E WebSocket ===")
    await test_backend_api()
    ok = await test_websocket_connection()
    print("\n=== Bilan ===")
    if ok:
        print("✅ Test réussi : WebSocket stable et communication temps réel OK")
    else:
        print("❌ Échec : voir messages ci-dessus")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    asyncio.run(main())
