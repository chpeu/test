#!/usr/bin/env python3
"""
Script de test pour vérifier la fonctionnalité next_event
"""
import requests
import json
import time

BASE_URL = "http://localhost:5000"

def test_bot_functionality():
    """Test complet du bot avec nouvelle fonctionnalité"""
    print("🚀 Test de la fonctionnalité next_event")
    print("=" * 50)
    
    # 1. Vérifier que le backend est en ligne
    try:
        response = requests.get(f"{BASE_URL}/api/status", timeout=5)
        print("✅ Backend en ligne")
    except:
        print("❌ Backend hors ligne")
        return False
    
    # 2. Vérifier la configuration
    try:
        config = requests.get(f"{BASE_URL}/api/live/config", timeout=5).json()
        print(f"📊 Config: dry_run={config.get('dry_run')}, mode={config.get('trading_mode')}")
    except:
        print("❌ Impossible de récupérer la config")
    
    # 3. Arrêter le scanner si actif
    try:
        status = requests.get(f"{BASE_URL}/api/status", timeout=5).json()
        if status.get('is_scanning'):
            print("⏹️ Arrêt du scanner...")
            requests.post(f"{BASE_URL}/api/stop", timeout=5)
            time.sleep(1)
    except:
        print("⚠️ Impossible d'arrêter le scanner")
    
    # 4. Créer une position test
    print("\n📍 Création position test...")
    entry_price = 98000
    try:
        price_data = requests.get(f"{BASE_URL}/api/price/BTCUSDT", timeout=5).json()
        entry_price = float(price_data.get('referencePrice') or price_data.get('lastPrice') or entry_price)
    except Exception:
        entry_price = 98000

    position_data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry": entry_price,
        "size": 7.0,
        "tp_pct": 2.0,
        "sl_pct": 1.5,
        "tp_mode": "FIXE",
        "sl_mode": "FIXE"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/position/open", 
                               json=position_data, timeout=10)
        if response.status_code == 200:
            print("✅ Position créée avec succès")
        else:
            print(f"❌ Erreur création position: {response.status_code}")
            print(f"   Détail: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    
    # 5. Attendre et vérifier les updates
    print("\n⏳ Vérification des updates...")
    for i in range(5):
        time.sleep(1)
        try:
            status = requests.get(f"{BASE_URL}/api/status", timeout=5).json()
            pos = status.get('active_position')
            if pos:
                pnl_pct = pos.get('pnl_pct')
                pnl_pct = pnl_pct if isinstance(pnl_pct, (int, float)) else 0
                print(f"  Update {i+1}: PnL={pnl_pct*100:.2f}%")
                
                # Vérifier next_event
                next_event = pos.get('next_event')
                if next_event:
                    print(f"  🎯 Next event: {next_event.get('type')} - {next_event.get('description')}")
                    print(f"     Distance: {next_event.get('distance_pct', 0):.2f}%")
                    print(f"     Prix: {next_event.get('price')}")
                else:
                    print("  ⚠️ Pas de next_event")
            else:
                print("  ⚠️ Pas de position active")
        except Exception as e:
            print(f"  ❌ Erreur update {i+1}: {e}")
    
    # 6. Nettoyage
    print("\n🧹 Nettoyage...")
    try:
        requests.post(f"{BASE_URL}/api/position/close", 
                     json={"reason": "TEST_CLEANUP"}, timeout=5)
        print("✅ Position fermée")
    except:
        print("⚠️ Impossible de fermer la position")
    
    print("\n✅ Test terminé")
    return True

if __name__ == "__main__":
    test_bot_functionality()
