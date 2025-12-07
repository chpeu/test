import requests
import json

BASE_URL = "http://localhost:8000"

def check_endpoint(name, path):
    try:
        response = requests.get(f"{BASE_URL}{path}", timeout=2)
        print(f"\n--- {name} ---")
        if response.status_code == 200:
            print("✅ STATUS: 200 OK")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text[:200])
        else:
            print(f"❌ STATUS: {response.status_code}")
            print(response.text[:200])
    except Exception as e:
        print(f"\n--- {name} ---")
        print(f"❌ ERREUR: {str(e)}")

# Vérifications
check_endpoint("Health", "/api/health")
check_endpoint("Market Regime", "/api/regime/status")
check_endpoint("Trading Circuit Breaker", "/api/circuit-breaker/trading/status")
