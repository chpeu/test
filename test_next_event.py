#!/usr/bin/env python3
"""
Script pour créer une position test et vérifier next_event
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def create_test_position():
    """Crée une position test avec TP escalier"""
    data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry": "98000",
        "size": "0.001",
        "tp_pct": 2.5,
        "sl_pct": 1.5,
        "tp_mode": "ESCALIER",
        "sl_mode": "ATR",
        "tp_escalier_levels": [
            {"pct": 1.0, "size_percent": 33},
            {"pct": 2.0, "size_percent": 33},
            {"pct": 3.0, "size_percent": 34}
        ],
        "atr_pct_used": 0.8
    }
    
    print("📍 Création position test...")
    try:
        response = requests.post(f"{BASE_URL}/api/position/open", json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Position créée: {result.get('status')}")
            return result.get('position')
        else:
            print(f"❌ Erreur {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def check_position():
    """Vérifie la position active et next_event"""
    print("\n🔍 Vérification position active...")
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=5)
        if response.status_code == 200:
            status = response.json()
            pos = status.get('active_position')
            if pos:
                print(f"Symbol: {pos.get('symbol')} {pos.get('direction')}")
                print(f"Entry: {pos.get('entry')} | Current: {pos.get('current_price')}")
                print(f"PnL: {pos.get('pnl_pct', 0)*100:.2f}%")
                
                # Afficher next_event
                next_event = pos.get('next_event')
                if next_event:
                    print(f"\n🎯 Prochaine étape:")
                    print(f"  Type: {next_event.get('type')} - {next_event.get('description')}")
                    print(f"  Distance: {next_event.get('distance_pct', 0):.2f}%")
                    if next_event.get('distance_atr'):
                        print(f"  ATR: {next_event.get('distance_atr'):.2f}")
                    if next_event.get('price'):
                        print(f"  Prix: {next_event.get('price')}")
                    print(f"  Couleur: {next_event.get('color')}")
                else:
                    print("\n❌ Pas de next_event")
                
                return pos
            else:
                print("❌ Aucune position active")
        else:
            print(f"❌ Erreur status: {response.status_code}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    return None

def simulate_price_update():
    """Simule une mise à jour de prix pour tester le calcul"""
    print("\n📊 Simulation mise à jour prix...")
    # Forcer une update de position en appelant le check loop
    try:
        response = requests.post(f"{BASE_URL}/api/position/check", timeout=5)
        print("✅ Check position envoyé")
    except:
        print("⚠️ Endpoint /api/position/check non disponible (normal)")

if __name__ == "__main__":
    # Créer la position
    position = create_test_position()
    
    if position:
        # Attendre un peu pour la première update
        time.sleep(1)
        
        # Vérifier la position avec next_event
        check_position()
        
        # Simuler une update
        simulate_price_update()
        
        # Re-vérifier après update
        time.sleep(0.5)
        check_position()
    else:
        print("❌ Impossible de créer la position test")
