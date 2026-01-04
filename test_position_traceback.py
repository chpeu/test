#!/usr/bin/env python3
"""
Script pour tester la création de position avec un traceback complet
"""
import traceback
import requests
import json

BASE_URL = "http://localhost:5000"

def test_position_with_traceback():
    """Test avec capture du traceback complet"""
    print("🔍 Test création position avec traceback")
    print("=" * 50)
    
    # Données minimales
    data = {
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry": 98000,
        "size": 10.0  # Plus grand pour éviter les erreurs de taille
    }
    
    try:
        print(f"📍 Données: {json.dumps(data, indent=2)}")
        print("\n📡 Envoi requête...")
        
        response = requests.post(f"{BASE_URL}/api/position/open", 
                               json=data, timeout=10)
        
        if response.status_code != 200:
            print(f"\n❌ Erreur HTTP {response.status_code}")
            
            # Essayer de récupérer plus de détails
            try:
                error_detail = response.json()
                print(f"Message: {error_detail.get('error', 'Unknown')}")
                
                # Si c'est une erreur de serveur, essayer de récupérer le traceback
                if response.status_code == 500:
                    print("\n📋 Erreur serveur - le traceback devrait être dans les logs du backend")
                    print("   Vérifier les logs dans la console du backend ou dans logs/app.log")
                    
            except json.JSONDecodeError:
                print(f"Réponse brute: {response.text[:500]}")
        else:
            result = response.json()
            print("✅ Position créée avec succès!")
            print(f"Symbol: {result.get('symbol')}")
            print(f"Direction: {result.get('direction')}")
            print(f"Entry: {result.get('entry')}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout - le backend met trop longtemps à répondre")
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au backend")
    except Exception as e:
        print(f"❌ Exception inattendue: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_position_with_traceback()
