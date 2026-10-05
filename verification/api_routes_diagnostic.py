
import asyncio
import os
import sys
import json
from fastapi.testclient import TestClient

# Path setup
sys.path.append(os.getcwd())

from main import app
from core.state_manager import get_state_manager

def test_api_routes():
    print("\n🧪 Test des routes API FastAPI...")
    client = TestClient(app)
    
    routes_to_test = [
        ("/api/status", "GET"),
        ("/api/state", "GET"),
        ("/api/config", "GET"),
        ("/api/regime/status", "GET"),
        ("/api/regime/force-check", "POST"),
        ("/api/live/stats", "GET")
    ]
    
    results = []
    for route, method in routes_to_test:
        try:
            if method == "GET":
                response = client.get(route)
            elif method == "POST":
                # Pour force-check, on n'a pas besoin de body
                response = client.post(route)
            
            status_code = response.status_code
            status_emoji = "✅" if status_code == 200 else "❌"
            print(f"{status_emoji} {method} {route}: {status_code}")
            
            data = None
            if status_code == 200:
                try:
                    data = response.json()
                except:
                    data = "Could not parse JSON"
            
            results.append({
                "route": route,
                "status": status_code,
                "ok": status_code == 200,
                "data": data
            })
                
        except Exception as e:
            print(f"❌ {method} {route}: Exception: {str(e)}")
            results.append({"route": route, "status": "ERROR", "ok": False, "error": str(e)})

    # Sauvegarder les résultats dans un fichier
    with open("verification/api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n✅ Résultats sauvegardés dans verification/api_test_results.json")

async def run_diagnostic_with_api():
    print("🚀 Initialisation des instances pour le test API...")
    from core.bootstrap import init_instances
    await init_instances()
    
    test_api_routes()
    
    # Petit délai pour laisser les logs se terminer
    await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(run_diagnostic_with_api())
