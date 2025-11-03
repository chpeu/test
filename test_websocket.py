"""
Test WebSocket MEXC pour Phase 2
Teste plusieurs URLs possibles pour trouver la bonne
"""
import asyncio
import json
from api.reliability import WebSocketManager


def handle_ticker_update(data):
    """Callback appelé pour chaque update ticker"""
    print(f"Ticker update: {json.dumps(data, indent=2)}")


async def test_url(url):
    """Tester une URL WebSocket spécifique"""
    print(f"\n{'='*60}")
    print(f"Test URL: {url}")
    print('='*60)
    
    manager = WebSocketManager(
        url=url,
        callback=handle_ticker_update
    )
    
    try:
        await manager.start()
        print("Connexion OK!")
        
        print("\nAbonnement BTC_USDT...")
        await manager.subscribe_ticker("BTC_USDT")
        
        print("\nAttente 10s pour messages...")
        await asyncio.sleep(10)
        
        print("URL VALIDE!")
        return True
        
    except Exception as e:
        print(f"ERREUR: {str(e)[:100]}")
        return False
    finally:
        await manager.disconnect()


async def test_all_urls():
    """Tester toutes les URLs possibles"""
    urls_a_tester = [
        "wss://contract.mexc.com/ws",           # Le plus probable
        "wss://futures.mexc.com/ws",            # Alternative
        "wss://api.mexc.com/ws",                # Spot (probablement pas)
        "wss://contract.mexc.com/edge",         # Variante
        "wss://contract.mexc.com/api/ws",       # Avec /api/
    ]
    
    print("Test de plusieurs URLs WebSocket MEXC Futures...")
    
    valid_url = None
    for url in urls_a_tester:
        if await test_url(url):
            valid_url = url
            break
    
    if valid_url:
        print(f"\n\n{'#'*60}")
        print(f"URL VALIDE TROUVEE: {valid_url}")
        print('#'*60)
    else:
        print("\n\nAucune URL valide trouvee")
    
    return valid_url


if __name__ == "__main__":
    asyncio.run(test_all_urls())

