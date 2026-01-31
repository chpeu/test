#!/usr/bin/env python3
"""
Test : déclencher un événement backend et vérifier qu’il est reçu par un client WebSocket
"""
import asyncio
import time
import urllib.request
import websockets
import json
import os

BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5000"))
BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"
WS_URL = f"ws://127.0.0.1:{BACKEND_PORT}/ws"

async def test_backend_event():
    async with websockets.connect(WS_URL) as ws:
        print("🔌 WebSocket connecté, en attente d'événements...")
        received = []

        async def listener():
            start = time.time()
            while time.time() - start < 20:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(msg)
                    received.append(data)
                    print(f"📨 Reçu : {data.get('type')} / {data.get('event', 'N/A')}")
                    if data.get('type') == 'ping':
                        await ws.send(json.dumps({
                            'type': 'pong',
                            'timestamp': time.time(),
                            'ping_id': data.get('ping_id')
                        }))
                        print(f"📤 Pong envoyé (ping_id={data.get('ping_id')})")
                except asyncio.TimeoutError:
                    print("⏳ Timeout (5s) - toujours en attente...")
                except Exception as e:
                    print(f"❌ Erreur réception : {e}")
                    break

        async def trigger():
            await asyncio.sleep(2)
            cmd = {
                'type': 'command',
                'id': 1,
                'command': 'get_live_config',
                'params': {}
            }
            await ws.send(json.dumps(cmd))
            print("� Commande envoyée: get_live_config")
            await asyncio.sleep(1)
            try:
                raw = urllib.request.urlopen(f"{BASE_URL}/api/websocket/stats", timeout=3).read().decode()
                stats = json.loads(raw)
                conns = stats.get('detailed_stats', {}).get('connections', [])
                print(f"📊 Stats WS (mid): {stats.get('active_connections')} conn, totals={stats.get('detailed_stats', {}).get('totals')}")
                if conns:
                    print(f"📊 Connexion[0] (mid): {conns[0]}")
            except Exception as e:
                print(f"❌ Erreur stats WS (mid): {e}")

        await asyncio.gather(listener(), trigger())

        responses = [m for m in received if m.get('type') == 'command_response']
        print(f"✅ Résumé: {len(received)} messages reçus | command_response={len(responses)}")

        try:
            raw = urllib.request.urlopen(f"{BASE_URL}/api/websocket/stats", timeout=3).read().decode()
            stats = json.loads(raw)
            print(f"📊 Stats WS: {stats.get('active_connections')} conn, totals={stats.get('detailed_stats', {}).get('totals')}")
            conns = stats.get('detailed_stats', {}).get('connections', [])
            if conns:
                print(f"📊 Connexion[0]: {conns[0]}")
        except Exception as e:
            print(f"❌ Erreur stats WS: {e}")

asyncio.run(test_backend_event())
