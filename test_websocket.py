"""
Test WebSocket MEXC pour Phase 2
"""
import asyncio
import json
from api.reliability import WebSocketManager
from config import WEBSOCKET_CONFIG, DEBUG_ENABLED


def handle_ticker_update(data):
    """Callback appelé pour chaque update ticker"""
    print(f"Ticker update: {json.dumps(data, indent=2)}")


async def test_websocket():
    """Test connexion WebSocket MEXC"""
    print("Test WebSocket MEXC Phase 2A...")
    print(f"URL: {WEBSOCKET_CONFIG['url']}")
    
    # Créer manager WebSocket
    manager = WebSocketManager(
        url=WEBSOCKET_CONFIG['url'],
        callback=handle_ticker_update
    )
    
    try:
        # Démarrer connexion
        print("\nConnexion WebSocket...")
        await manager.start()
        
        # 🔥 v6.6.1 Phase 2A: Utiliser subscribe_ticker MEXC
        print("\nAbonnement BTC_USDT ticker (MEXC)...")
        await manager.subscribe_ticker("BTC_USDT")
        
        # Attendre messages
        print("\nAttente messages (60s)...")
        print("Cherchez 'push.ticker' messages avec lastPrice")
        await asyncio.sleep(60)
        
        print("\nTest termine")
        
    except Exception as e:
        print(f"\nERREUR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(test_websocket())

