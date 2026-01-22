"""
Script pour tester l'API des erreurs et diagnostiquer le problème d'affichage
"""
import requests
import json

BASE_URL = "http://localhost:3000"

print("=" * 80)
print("🧪 TEST API ERREURS")
print("=" * 80)

# 1. Déclencher une erreur de test
print("\n1️⃣ Déclenchement d'une erreur de test...")
response = requests.post(
    f"{BASE_URL}/api/test/trigger-error",
    params={
        "error_type": "critical",
        "message": "Test API - Erreur critique de diagnostic"
    }
)
print(f"Status: {response.status_code}")
data = response.json()
print(f"Response: {json.dumps(data, indent=2)}")

# 2. Récupérer les erreurs récentes
print("\n2️⃣ Récupération des erreurs récentes...")
response = requests.get(f"{BASE_URL}/api/logs/errors/recent?limit=10")
print(f"Status: {response.status_code}")
data = response.json()
print(f"Success: {data.get('success')}")
print(f"Total count: {data.get('total_count')}")
print(f"Errors returned: {len(data.get('errors', []))}")

if data.get('errors'):
    print("\n📋 Erreurs trouvées:")
    for i, error in enumerate(data['errors'][:3], 1):
        print(f"\n  {i}. Erreur:")
        print(f"     Timestamp: {error.get('timestamp')}")
        print(f"     Level: {error.get('level')}")
        print(f"     Message: {error.get('message')}")
        print(f"     Detail: {error.get('detail')}")
        print(f"     Raw: {error.get('raw_message')}")
        print(f"     ID: {error.get('id')}")
else:
    print("\n⚠️ Aucune erreur retournée!")

# 3. Récupérer toutes les erreurs
print("\n3️⃣ Récupération de toutes les erreurs...")
response = requests.get(f"{BASE_URL}/api/logs/errors?limit=100&offset=0")
data = response.json()
print(f"Total count: {data.get('total_count')}")
print(f"Errors returned: {len(data.get('errors', []))}")

print("\n" + "=" * 80)
print("✅ Test terminé")
print("=" * 80)
