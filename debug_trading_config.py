#!/usr/bin/env python3
"""
Script pour debugger l'erreur TRADING_CONFIG
"""
import traceback
import requests

BASE_URL = "http://localhost:5000"

def test_with_debug():
    """Test avec capture de l'erreur complète"""
    print("🔍 Test debug pour TRADING_CONFIG")
    print("=" * 50)
    
    # Test simple
    data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry": 98000,
        "size": 0.001
    }
    
    try:
        print("📍 Envoi requête...")
        response = requests.post(f"{BASE_URL}/api/position/open", 
                               json=data, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Erreur {response.status_code}")
            try:
                error_data = response.json()
                print(f"Erreur: {error_data.get('error')}")
                
                # Demander les logs au backend
                print("\n📋 Demande des logs...")
                logs_response = requests.get(f"{BASE_URL}/api/logs", timeout=5)
                if logs_response.status_code == 200:
                    logs = logs_response.text
                    # Chercher l'erreur dans les logs
                    for line in logs.split('\n')[-50:]:  # 50 dernières lignes
                        if 'TRADING_CONFIG' in line or 'NameError' in line or 'open_position' in line:
                            print(f"Log: {line}")
            except:
                print("Impossible de parser l'erreur")
        else:
            print("✅ Succès!")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_with_debug()
