#!/usr/bin/env python3
"""
🔥 Test WebSocket via proxy Vite (port 3000)
Reproduire exactement le problème du frontend
"""
import asyncio
import websockets
import json
import time
import sys

async def test_websocket_via_vite_proxy():
    """Test la connexion WebSocket via le proxy Vite"""
    # Tester via le proxy Vite (comme le frontend)
    vite_proxy_uri = "ws://localhost:3000/ws"
    
    print("🔧 Test WebSocket via proxy Vite...")
    print(f"📡 Connexion à {vite_proxy_uri} (comme le frontend)")
    
    try:
        async with websockets.connect(vite_proxy_uri) as websocket:
            print("✅ WebSocket connecté via proxy Vite")
            
            # Envoyer client_hello
            await websocket.send(json.dumps({
                "type": "client_hello",
                "client_id": "test-vite-proxy",
                "timestamp": time.time()
            }))
            print("📤 client_hello envoyé via proxy")
            
            ping_received = 0
            pong_sent = 0
            pong_received_back = 0
            start_time = time.time()
            timeout_seconds = 100  # Test sur 100 secondes pour voir la déconnexion
            
            print(f"⏱️ Test pendant {timeout_seconds}s pour reproduire le problème...")
            
            while (time.time() - start_time) < timeout_seconds:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    msg_type = data.get("type")
                    now = time.time()
                    elapsed = int(now - start_time)
                    
                    if msg_type == "server_hello":
                        conn_id = data.get("connection_id")
                        print(f"🤝 [{elapsed}s] server_hello: connection_id={conn_id}")
                    
                    elif msg_type == "ping":
                        ping_received += 1
                        ping_id = data.get("ping_id")
                        
                        print(f"📡 [{elapsed}s] PING #{ping_received} reçu (id={ping_id}) via proxy")
                        
                        # Répondre avec pong
                        pong_response = {
                            "type": "pong",
                            "ping_id": ping_id,
                            "timestamp": time.time(),
                            "server_ts": data.get("timestamp")
                        }
                        
                        await websocket.send(json.dumps(pong_response))
                        pong_sent += 1
                        print(f"🏓 [{elapsed}s] PONG #{pong_sent} envoyé (id={ping_id}) via proxy")
                    
                    elif msg_type == "pong":
                        # Pong de retour du serveur (confirmation de réception)
                        pong_received_back += 1
                        ping_id = data.get("ping_id")
                        print(f"🎯 [{elapsed}s] Confirmation PONG reçue du serveur (id={ping_id})")
                    
                    elif msg_type == "event":
                        # Ignorer les messages event pour ne pas spammer
                        pass
                    
                    else:
                        print(f"📬 [{elapsed}s] Autre: {msg_type}")
                
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0:  # Log toutes les 10 secondes
                        print(f"⏳ [{elapsed}s] Attente... (pings: {ping_received}, pongs: {pong_sent})")
                    continue
            
            print(f"\n📊 RÉSULTATS test via proxy Vite:")
            print(f"   • Durée: {timeout_seconds}s")
            print(f"   • Pings reçus: {ping_received}")
            print(f"   • Pongs envoyés: {pong_sent}")
            print(f"   • Confirmations reçues: {pong_received_back}")
            
            if ping_received >= 3 and pong_sent >= 3:
                print("✅ PROXY FONCTIONNE: Communication ping/pong OK")
                return True
            else:
                print("❌ PROXY DÉFAILLANT: Pas assez de ping/pong")
                return False
    
    except Exception as e:
        print(f"❌ Erreur connexion via proxy Vite: {e}")
        return False

async def main():
    print("🔥 Test WebSocket via proxy Vite (reproduire problème frontend)")
    print("=" * 70)
    
    success = await test_websocket_via_vite_proxy()
    
    print("=" * 70)
    if success:
        print("🎉 PROXY OK: Le problème vient d'ailleurs")
    else:
        print("⚠️ PROXY DÉFAILLANT: Configuration Vite à corriger")
        
    return success

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu")
        sys.exit(1)
