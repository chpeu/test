#!/usr/bin/env python3
"""
Script pour créer une position via WebSocket
"""
import asyncio
import websockets
import json

async def create_position_via_ws():
    """Crée une position via WebSocket"""
    uri = "ws://localhost:5000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Attendre le message initial
            init_msg = await websocket.recv()
            print("📡 Connecté au WebSocket")
            
            # Créer la position via commande
            command = {
                "type": "command",
                "command": "open_position",
                "params": {
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "entry": "98000",
                    "size": "0.001",
                    "tp_pct": 2.0,
                    "sl_pct": 1.5,
                    "tp_mode": "FIXE",
                    "sl_mode": "FIXE"
                }
            }
            
            await websocket.send(json.dumps(command))
            print("✅ Commande open_position envoyée")
            
            # Écouter les réponses
            for _ in range(5):
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    
                    if data.get('type') == 'position_opened':
                        print("🎉 Position ouverte avec succès!")
                        pos = data.get('position', {})
                        print(f"   Symbol: {pos.get('symbol')} {pos.get('direction')}")
                        print(f"   Entry: {pos.get('entry')}")
                        return True
                    elif data.get('type') == 'error':
                        print(f"❌ Erreur: {data.get('message')}")
                        return False
                        
                except asyncio.TimeoutError:
                    continue
                    
    except Exception as e:
        print(f"❌ Erreur WebSocket: {e}")
        return False

async def check_next_event():
    """Vérifie le next_event via WebSocket"""
    uri = "ws://localhost:5000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            # Attendre le message initial avec la position
            init_msg = await websocket.recv()
            data = json.loads(init_msg)
            
            if data.get('type') == 'status':
                pos = data.get('active_position')
                if pos:
                    print("\n🎯 Position active détectée:")
                    print(f"   Symbol: {pos.get('symbol')} {pos.get('direction')}")
                    print(f"   PnL: {pos.get('pnl_pct', 0)*100:.2f}%")
                    
                    next_event = pos.get('next_event')
                    if next_event:
                        print(f"\n📍 Prochaine étape:")
                        print(f"   Type: {next_event.get('type')} - {next_event.get('description')}")
                        print(f"   Distance: {next_event.get('distance_pct', 0):.2f}%")
                        if next_event.get('price'):
                            print(f"   Prix: {next_event.get('price')}")
                        print(f"   Couleur: {next_event.get('color')}")
                        return True
                    else:
                        print("\n❌ Pas de next_event reçu")
                        
    except Exception as e:
        print(f"❌ Erreur vérification: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Test de la fonctionnalité 'Prochaine étape'")
    print("=" * 50)
    
    # Créer la position
    if asyncio.run(create_position_via_ws()):
        print("\n⏳ Attente de la mise à jour...")
        asyncio.run(check_next_event())
    else:
        print("\n❌ Échec de la création de position")
