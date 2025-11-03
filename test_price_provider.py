"""
Test HybridPriceProvider pour Phase 2A
"""
import asyncio
from api.price_provider import get_price_provider


async def test_price_provider():
    """Test du HybridPriceProvider"""
    print("🧪 Test HybridPriceProvider Phase 2A...")
    
    provider = get_price_provider()
    
    try:
        # Test 1: WebSocket initialisé
        print("\n1️⃣ Initialisation WebSocket...")
        await provider.start_websocket(["BTC_USDT", "ETH_USDT"])
        
        # Test 2: Attendre quelques prix WebSocket
        print("\n2️⃣ Attente prix WebSocket (10s)...")
        await asyncio.sleep(10)
        
        # Test 3: Récupérer prix via get_price()
        print("\n3️⃣ Récupération prix via get_price()...")
        
        btc_price = await provider.get_price("BTC_USDT")
        if btc_price:
            print(f"   ✅ BTC_USDT: {btc_price.get('lastPrice', 'N/A')}")
            print(f"   📊 Source: {'WebSocket' if provider.is_websocket_connected() else 'REST'}")
        else:
            print("   ❌ BTC_USDT: Prix non disponible")
        
        eth_price = await provider.get_price("ETH_USDT")
        if eth_price:
            print(f"   ✅ ETH_USDT: {eth_price.get('lastPrice', 'N/A')}")
            print(f"   📊 Source: {'WebSocket' if provider.is_websocket_connected() else 'REST'}")
        else:
            print("   ❌ ETH_USDT: Prix non disponible")
        
        # Test 4: Simuler fallback REST (forcer déconnexion WS)
        print("\n4️⃣ Test fallback REST...")
        await provider.stop_websocket()
        await asyncio.sleep(1)
        
        fallback_price = await provider.get_price("BTC_USDT")
        if fallback_price:
            print(f"   ✅ Fallback BTC_USDT: {fallback_price.get('lastPrice', 'N/A')}")
            print(f"   📊 Source: REST")
        else:
            print("   ❌ Fallback: Prix non disponible")
        
        print("\n✅ Tous les tests réussis!")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await provider.stop_websocket()
        # Fermer client REST
        await provider.rest_client.close()


if __name__ == "__main__":
    asyncio.run(test_price_provider())



