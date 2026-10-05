#!/usr/bin/env python3
"""
🔍 Trouver l'endpoint WebSocket - Test multiple URLs
"""

import asyncio
import websockets
import requests
import sys

async def test_websocket_url(url):
    """Tester une URL WebSocket spécifique"""
    try:
        print(f"🔗 Test: {url}")
        
        async with websockets.connect(url, timeout=5) as websocket:
            print(f"✅ SUCCÈS: {url} - Connexion établie")
            return True
            
    except Exception as e:
        print(f"❌ ÉCHEC: {url} - {type(e).__name__}: {str(e)[:100]}")
        return False

def test_http_endpoint(url):
    """Tester un endpoint HTTP"""
    try:
        print(f"🌐 Test HTTP: {url}")
        response = requests.get(url, timeout=5)
        print(f"📝 HTTP {url}: Status {response.status_code}")
        return response.status_code
    except Exception as e:
        print(f"❌ HTTP {url}: {type(e).__name__}: {str(e)[:100]}")
        return None

async def find_websocket_endpoint():
    """Trouver l'endpoint WebSocket qui fonctionne"""
    
    # URLs WebSocket possibles (PORT 5000!)
    websocket_urls = [
        "ws://localhost:5000/ws",
        "ws://localhost:5000/api/ws", 
        "ws://localhost:5000/websocket",
        "ws://localhost:5000/api/websocket",
    ]
    
    # URLs HTTP pour vérifier les routes
    http_urls = [
        "http://localhost:5000/",
        "http://localhost:5000/api/",
        "http://localhost:5000/docs",
        "http://localhost:5000/openapi.json",
    ]
    
    print("🔍 Recherche de l'endpoint WebSocket...")
    print("=" * 50)
    
    # Test HTTP endpoints d'abord
    print("\n🌐 Test des endpoints HTTP:")
    for url in http_urls:
        test_http_endpoint(url)
    
    # Test WebSocket endpoints
    print("\n🔗 Test des endpoints WebSocket:")
    working_urls = []
    
    for url in websocket_urls:
        if await test_websocket_url(url):
            working_urls.append(url)
    
    print("\n" + "=" * 50)
    if working_urls:
        print("✅ Endpoints WebSocket fonctionnels:")
        for url in working_urls:
            print(f"   - {url}")
    else:
        print("❌ Aucun endpoint WebSocket accessible")
        
        # Suggestions de diagnostic
        print("\n🔧 Diagnostic supplémentaire:")
        print("1. Vérifier que le serveur FastAPI expose bien l'endpoint WebSocket")
        print("2. Vérifier la configuration des routes dans main.py")
        print("3. Vérifier les logs du serveur pour erreurs")
    
    return working_urls

if __name__ == "__main__":
    print("🔍 Recherche d'endpoint WebSocket")
    working = asyncio.run(find_websocket_endpoint())
    
    if working:
        print(f"\n🎯 URL WebSocket à utiliser: {working[0]}")
    else:
        print("\n💔 Endpoint WebSocket introuvable - problème de configuration serveur")
