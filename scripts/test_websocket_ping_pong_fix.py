#!/usr/bin/env python3
"""
🔥 Script de test pour vérifier le fix ping/pong WebSocket
Teste la synchronisation des ping_id entre client et serveur
"""
import asyncio
import websockets
import json
import time
import sys

async def test_ping_pong_sync():
    """Test la synchronisation ping/pong après le fix"""
    uri = "ws://localhost:5000/ws"
    
    print("🔧 Test du fix ping/pong synchronisation...")
    print(f"📡 Connexion à {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connecté")
            
            # Envoyer client_hello
            await websocket.send(json.dumps({
                "type": "client_hello",
                "client_id": "test-ping-pong-fix",
                "timestamp": time.time()
            }))
            print("📤 client_hello envoyé")
            
            ping_received = 0
            pong_sent = 0
            ping_ids_seen = []
            
            # Écouter les messages pendant 90 secondes
            timeout_seconds = 90
            start_time = time.time()
            
            print(f"⏱️ Écoute pendant {timeout_seconds} secondes pour tester ping/pong...")
            
            while (time.time() - start_time) < timeout_seconds:
                try:
                    # Attendre un message avec timeout court
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "server_hello":
                        conn_id = data.get("connection_id")
                        print(f"🤝 server_hello reçu: connection_id={conn_id}")
                    
                    elif msg_type == "ping":
                        ping_received += 1
                        ping_id = data.get("ping_id")
                        server_ts = data.get("timestamp")
                        
                        print(f"📡 [PING #{ping_received}] ping_id={ping_id}, ts={server_ts}")
                        ping_ids_seen.append(ping_id)
                        
                        # Répondre immédiatement avec pong
                        pong_response = {
                            "type": "pong",
                            "ping_id": ping_id,
                            "timestamp": time.time(),
                            "server_ts": server_ts
                        }
                        
                        await websocket.send(json.dumps(pong_response))
                        pong_sent += 1
                        print(f"🏓 [PONG #{pong_sent}] Réponse envoyée pour ping_id={ping_id}")
                    
                    elif msg_type == "pong":
                        # Pong du serveur (pas attendu dans ce test)
                        print(f"🏓 Pong inattendu du serveur: {data}")
                    
                    else:
                        print(f"📬 Autre message: {msg_type}")
                
                except asyncio.TimeoutError:
                    # Normal - continue la boucle
                    continue
            
            print(f"\n📊 RÉSULTATS du test ping/pong:")
            print(f"   • Pings reçus: {ping_received}")
            print(f"   • Pongs envoyés: {pong_sent}")
            print(f"   • IDs de ping vus: {ping_ids_seen}")
            print(f"   • Séquence correcte: {ping_ids_seen == list(range(1, len(ping_ids_seen) + 1))}")
            
            if ping_received > 0 and pong_sent == ping_received:
                print("✅ TEST RÉUSSI: Ping/pong synchronisés correctement")
                return True
            else:
                print("❌ TEST ÉCHOUÉ: Problème de synchronisation")
                return False
    
    except Exception as e:
        print(f"❌ Erreur de connexion WebSocket: {e}")
        return False

async def main():
    print("🔥 Test de vérification du fix ping/pong WebSocket")
    print("=" * 60)
    
    success = await test_ping_pong_sync()
    
    print("=" * 60)
    if success:
        print("🎉 FIX VALIDÉ: Les déconnexions devraient être résolues")
        sys.exit(0)
    else:
        print("⚠️ PROBLÈME DÉTECTÉ: Vérifier les logs serveur")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu par l'utilisateur")
        sys.exit(1)
