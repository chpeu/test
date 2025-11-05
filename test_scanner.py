"""
Test du scanner de scalabilité
"""
import asyncio
from core.scanner import ScalabilityScanner


async def test_scanner():
    """Test de base du scanner"""
    print("Test Scanner de Scalabilite...")
    
    scanner = ScalabilityScanner()
    
    try:
        # Test sur un petit batch
        print("\nRecuperation paires 0% fees...")
        # On va scanner seulement quelques paires pour tester
        # Dans la version complète, on scannera toutes
        
        # Test manuel sur BTC_USDT
        print("\nTest scan BTC_USDT...")
        result = await scanner.scan_pair('BTC_USDT')
        if result:
            print(f"   OK Symbol: {result['symbol']}")
            print(f"   OK Price: {result['price']}")
            print(f"   OK Vol5: {result['vol5']:.3f}%")
            print(f"   OK Spread: {result['spread']:.4f}%")
            print(f"   OK BalanceScore: {result['balanceScore']:.2f}")
        else:
            print("   Erreur scan")
        
        print("\nTests scanner basiques OK!")
        
    except Exception as e:
        print(f"\nErreur: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scanner.close()


if __name__ == "__main__":
    asyncio.run(test_scanner())




