#!/usr/bin/env python3
"""
🔥 Test final de stabilité WebSocket après fix critique
Simule exactement le comportement du client frontend fixé
"""
import asyncio
import websockets
import json
import time
import sys

class MockFrontendWebSocketClient:
    """Client simulant le comportement du frontend après fix"""
    
    def __init__(self):
        self.last_ping = time.time() * 1000  # lastPing en ms
        self.last_pong_at = time.time() * 1000  # lastPongAt en ms  
        self.client_ping_counter = 0
        self.connected = False
        
    def update_activity(self):
        """Mettre à jour activité comme le vrai client"""
        now_ms = time.time() * 1000
        self.last_ping = now_ms
        
    def update_pong_activity(self):
        """Mettre à jour activité pong (ping serveur reçu ou pong reçu)"""
        now_ms = time.time() * 1000
        self.last_pong_at = now_ms
        
    def is_connection_alive(self, pong_timeout_ms=75000):
        """Vérifier si connexion vivante (comme le vrai client)"""
        now_ms = time.time() * 1000
        time_since_last_pong = (now_ms - self.last_pong_at) if self.last_pong_at else (now_ms - self.last_ping)
        return time_since_last_pong <= pong_timeout_ms

async def test_websocket_stability_with_fix():
    """Test stabilité avec simulation du fix frontend"""
    uri = "ws://localhost:3000/ws"
    client = MockFrontendWebSocketClient()
    
    print("🔥 Test de stabilité WebSocket avec fix frontend")
    print(f"📡 Connexion à {uri} (via proxy Vite)")
    
    try:
        async with websockets.connect(uri) as websocket:
            client.connected = True
            client.update_activity()
            client.update_pong_activity()  # Connexion = activité
            
            print("✅ WebSocket connecté - simulation fix frontend active")
            
            # Client hello
            await websocket.send(json.dumps({
                "type": "client_hello", 
                "client_id": "test-stability-final",
                "timestamp": time.time()
            }))
            
            ping_from_server = 0
            connection_alive_checks = 0
            forced_disconnections = 0
            start_time = time.time()
            test_duration = 120  # Test 2 minutes pour dépasser les 75s critiques
            
            print(f"⏱️ Test pendant {test_duration}s (seuil critique: 75s)")
            print("🔍 Simulation comportement frontend avec fix...")
            
            while (time.time() - start_time) < test_duration:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    # Toute réception = activité
                    client.update_activity()
                    
                    elapsed = int(time.time() - start_time)
                    
                    if msg_type == "server_hello":
                        conn_id = data.get("connection_id")
                        print(f"🤝 [{elapsed}s] server_hello reçu: {conn_id}")
                        
                    elif msg_type == "ping":
                        # 🔥 FIX CRITIQUE APPLIQUÉ: ping serveur = connexion vivante
                        client.update_pong_activity()  # NOUVEAU COMPORTEMENT
                        
                        ping_from_server += 1
                        ping_id = data.get("ping_id")
                        print(f"📡 [{elapsed}s] Ping serveur #{ping_from_server} (id={ping_id}) → lastPongAt mis à jour!")
                        
                        # Répondre au ping (comme le frontend)
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "ping_id": ping_id,
                            "timestamp": time.time(),
                            "server_ts": data.get("timestamp")
                        }))
                        
                    elif msg_type == "pong":
                        # Pong en réponse à nos pings client
                        client.update_pong_activity()
                        ping_id = data.get("ping_id")
                        print(f"🏓 [{elapsed}s] Pong serveur reçu (ping_id={ping_id})")
                        
                    # Vérification périodique de la connexion (comme le frontend)
                    if elapsed % 15 == 0 and elapsed > 0:  # Toutes les 15 secondes
                        connection_alive_checks += 1
                        is_alive = client.is_connection_alive()
                        time_since_pong = (time.time() * 1000 - client.last_pong_at) / 1000
                        
                        if is_alive:
                            print(f"✅ [{elapsed}s] Check #{connection_alive_checks}: Connexion VIVANTE (dernière activité: {time_since_pong:.1f}s)")
                        else:
                            print(f"❌ [{elapsed}s] Check #{connection_alive_checks}: Connexion MORTE (dernière activité: {time_since_pong:.1f}s)")
                            forced_disconnections += 1
                            break
                            
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    if elapsed % 20 == 0:  # Log toutes les 20 secondes
                        time_since_pong = (time.time() * 1000 - client.last_pong_at) / 1000
                        print(f"⏳ [{elapsed}s] Attente... (pings serveur: {ping_from_server}, dernière activité: {time_since_pong:.1f}s)")
                    continue
            
            elapsed_total = int(time.time() - start_time)
            print(f"\n📊 RÉSULTATS test de stabilité ({elapsed_total}s):")
            print(f"   • Pings serveur reçus: {ping_from_server}")
            print(f"   • Checks connexion: {connection_alive_checks}")
            print(f"   • Déconnexions forcées: {forced_disconnections}")
            print(f"   • Temps critique 75s: {'✅ DÉPASSÉ' if elapsed_total > 75 else '⏳ Pas encore'}")
            
            if forced_disconnections == 0 and elapsed_total >= 75:
                print("🎉 FIX VALIDÉ: Pas de déconnexion après 75s critiques!")
                return True
            else:
                print("❌ PROBLÈME PERSISTE: Déconnexion détectée")
                return False
                
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return False

async def main():
    print("🔥 Test final de stabilité WebSocket avec fix critique")
    print("=" * 65)
    
    success = await test_websocket_stability_with_fix()
    
    print("=" * 65)
    if success:
        print("🎉 PROBLÈME RÉSOLU: WebSocket stable après fix frontend")
        print("✅ Les déconnexions après 75s sont corrigées")
        sys.exit(0)
    else:
        print("⚠️ PROBLÈME PERSISTE: Analyser logs serveur/client")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrompu")
        sys.exit(1)
