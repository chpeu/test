"""
Test WebSocket MEXC pour Phase 2
"""
import asyncio
import json
from api.reliability import WebSocketManager
from config import WEBSOCKET_CONFIG, DEBUG_ENABLED


def handle_ticker_update(data):
    """Callback appelé pour chaque update ticker"""
    print(f"📊 Ticker update: {json.dumps(data, indent=2)}")


async def test_websocket():
    """Test connexion WebSocket MEXC"""
    print("🧪 Test WebSocket MEXC...")
    print(f"URL: {WEBSOCKET_CONFIG['url']}")
    
    # Créer manager WebSocket
    manager = WebSocketManager(
        url=WEBSOCKET_CONFIG['url'],
        callback=handle_ticker_update
    )
    
    try:
        # Démarrer connexion
        print("\n🔌 Connexion WebSocket...")
        await manager.start()
        
        # S'abonner à BTC_USDT
        print("\n📡 Abonnement BTC_USDT ticker...")
        await manager.subscribe("BTC_USDT")
        
        # Attendre messages
        print("\n⏳ Attente messages (60s)...")
        await asyncio.sleep(60)
        
        print("\n✅ Test terminé")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(test_websocket())

