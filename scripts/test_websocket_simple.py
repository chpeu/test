#!/usr/bin/env python3
"""
🔧 Test WebSocket Simple - Diagnostic Rapide
Test basique pour identifier le problème de déconnexion WebSocket
"""

import asyncio
import websockets
import json
import time
import sys

async def test_websocket_connection():
    """Test simple de connexion WebSocket"""
    uri = "ws://localhost:5000/ws"
    
    try:
        print(f"🔗 Tentative de connexion à {uri}")
        
        async with websockets.connect(uri, timeout=10) as websocket:
            print("✅ Connexion WebSocket établie")
            
            # Envoyer hello
            hello = {
                'type': 'client_hello',
                'client_id': 'diagnostic_test',
                'context': {'userAgent': 'DiagnosticTest', 'diagnostic': True}
            }
            await websocket.send(json.dumps(hello))
            print("📤 Client hello envoyé")
            
            # Écouter pendant 2 minutes et compter les pings/pongs
            start_time = time.time()
            ping_count = 0
            pong_received = 0
            last_server_ping = None
            
            while time.time() - start_time < 120:  # 2 minutes
                try:
                    # Attendre un message du serveur avec timeout
                    message_data = await asyncio.wait_for(websocket.recv(), timeout=35.0)
                    message = json.loads(message_data)
                    
                    elapsed = time.time() - start_time
                    msg_type = message.get('type')
                    
                    print(f"[{elapsed:06.1f}s] 📥 Reçu: {msg_type}")
                    
                    if msg_type == 'ping':
                        ping_count += 1
                        last_server_ping = time.time()
                        
                        # Répondre immédiatement
                        pong_response = {
                            'type': 'pong',
                            'timestamp': time.time(),
                            'ping_id': message.get('ping_id')
                        }
                        await websocket.send(json.dumps(pong_response))
                        print(f"[{elapsed:06.1f}s] 📤 Pong envoyé (ping_id={message.get('ping_id')})")
                        
                    elif msg_type == 'pong':
                        pong_received += 1
                        print(f"[{elapsed:06.1f}s] 🏓 Pong du serveur reçu")
                        
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    time_since_ping = time.time() - last_server_ping if last_server_ping else None
                    
                    print(f"[{elapsed:06.1f}s] ⏰ TIMEOUT 35s - Pas de message du serveur")
                    if time_since_ping:
                        print(f"[{elapsed:06.1f}s] ⚠️ Dernier ping serveur: {time_since_ping:.1f}s ago")
                    
                    # Si pas de ping depuis plus de 60s, c'est le problème
                    if time_since_ping and time_since_ping > 60:
                        print(f"[{elapsed:06.1f}s] 🚨 SERVEUR ARRÊTÉ DE PING - CAUSE IDENTIFIÉE!")
                        break
            
            print(f"\n📊 Résultats après {time.time() - start_time:.1f}s:")
            print(f"   Pings serveur reçus: {ping_count}")  
            print(f"   Pongs serveur reçus: {pong_received}")
            if last_server_ping:
                print(f"   Dernier ping serveur: {time.time() - last_server_ping:.1f}s ago")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 Test WebSocket Simple - Diagnostic des déconnexions")
    asyncio.run(test_websocket_connection())
