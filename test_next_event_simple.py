#!/usr/bin/env python3
"""
Test simple pour vérifier next_event
"""
import requests
import time
import json

BASE_URL = "http://localhost:5000"

def test_simple():
    """Test simple avec une position"""
    print("🧪 Test simple next_event")
    
    # Créer position
    data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry": 98000,
        "size": 10.0,
        "tp_pct": 2.0,
        "sl_pct": 1.0
    }
    
    print("\n1. Création position...")
    response = requests.post(f"{BASE_URL}/api/position/open", json=data)
    
    if response.status_code == 200:
        print("✅ Position créée")
        
        # Attendre un peu
        time.sleep(2)
        
        # Vérifier status
        print("\n2. Vérification status...")
        status_resp = requests.get(f"{BASE_URL}/api/status")
        if status_resp.status_code == 200:
            status = status_resp.json()
            pos = status.get('active_position')
            if pos:
                print(f"Position: {pos.get('symbol')} {pos.get('direction')}")
                print(f"PnL: {pos.get('pnl_pct', 0)*100:.2f}%")
                
                # Vérifier next_event
                next_event = pos.get('next_event')
                if next_event:
                    print(f"\n🎯 Next event trouvé:")
                    print(f"  Type: {next_event.get('type')}")
                    print(f"  Description: {next_event.get('description')}")
                    print(f"  Prix: {next_event.get('price')}")
                    print(f"  Distance: {next_event.get('distance_pct', 0):.2f}%")
                else:
                    print("\n❌ Pas de next_event")
            else:
                print("❌ Pas de position active")
        
        # Fermer position
        print("\n3. Fermeture position...")
        close_resp = requests.post(f"{BASE_URL}/api/position/close", json={"reason": "TEST"})
        if close_resp.status_code == 200:
            print("✅ Position fermée")
    else:
        print(f"❌ Erreur création: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_simple()
