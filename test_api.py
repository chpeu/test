"""
Test simple de l'API MEXC
"""
import asyncio
from api.mexc import get_mexc_client


async def test_api():
    """Test de connexion et récupération de données"""
    print("🧪 Test API MEXC...")
    
    client = get_mexc_client()
    
    try:
        # Test 1: Récupérer tous les tickers
        print("\n1️⃣ Récupération tickers...")
        tickers = await client.fetch_tickers()
        print(f"   ✅ {len(tickers)} tickers récupérés")
        
        # Test 2: Ticker spécifique
        print("\n2️⃣ Ticker BTC_USDT...")
        ticker = await client.fetch_ticker('BTC_USDT')
        if ticker:
            print(f"   ✅ Prix: {ticker['last']}")
        else:
            print("   ❌ Erreur")
        
        # Test 3: OHLCV
        print("\n3️⃣ OHLCV BTC_USDT 1m...")
        ohlcv = await client.fetch_ohlcv('BTC_USDT', '1m', limit=100)
        print(f"   ✅ {len(ohlcv)} bougies récupérées")
        
        # Test 4: Order book
        print("\n4️⃣ Order book BTC_USDT...")
        orderbook = await client.fetch_order_book('BTC_USDT', limit=20)
        if orderbook:
            print(f"   ✅ Bids: {len(orderbook['bids'])}, Asks: {len(orderbook['asks'])}")
        else:
            print("   ❌ Erreur")
        
        print("\n✅ Tous les tests réussis!")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_api())




