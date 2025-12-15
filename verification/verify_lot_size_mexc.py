#!/usr/bin/env python3
"""
VERIFICATION TAILLE DE LOT MEXC
================================
Vérifie que le bot récupère correctement les tailles de lot depuis MEXC via CCXT.
"""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()

# Paires à tester
TEST_SYMBOLS = [
    'BTC/USDT:USDT',
    'ETH/USDT:USDT',
    'SOL/USDT:USDT',
    'XRP/USDT:USDT',
    'DOGE/USDT:USDT',
    'APT/USDT:USDT',
    'ZEC/USDT:USDT',
    'PEPE/USDT:USDT',
]

async def test_lot_size():
    """Test récupération taille de lot"""
    print("=" * 70)
    print("  VERIFICATION TAILLE DE LOT MEXC")
    print("=" * 70)
    
    # Initialiser CCXT
    exchange = ccxt.mexc({
        'apiKey': os.getenv('MEXC_API_KEY'),
        'secret': os.getenv('MEXC_SECRET_KEY'),
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
        }
    })
    
    try:
        # Charger les marchés
        print("\n[1/3] Chargement des marchés MEXC...")
        start = time.time()
        markets = await exchange.load_markets()
        elapsed = time.time() - start
        print(f"      ✅ {len(markets)} marchés chargés en {elapsed:.2f}s")
        
        # Tester chaque symbole
        print(f"\n[2/3] Test récupération taille de lot ({len(TEST_SYMBOLS)} paires)...")
        print(f"\n{'Symbol':<20} {'contractSize':<15} {'lotSize(min)':<15} {'precision':<15} {'Status'}")
        print("-" * 75)
        
        success_count = 0
        failed_symbols = []
        
        for symbol in TEST_SYMBOLS:
            try:
                if symbol not in markets:
                    print(f"{symbol:<20} {'N/A':<15} {'N/A':<15} {'N/A':<15} ❌ Non trouvé")
                    failed_symbols.append((symbol, "Non trouvé dans markets"))
                    continue
                
                market = markets[symbol]
                
                # Extraire les infos de lot
                contract_size = market.get('contractSize', 'N/A')
                
                # Lot size depuis limits
                limits = market.get('limits', {})
                amount_limits = limits.get('amount', {})
                min_amount = amount_limits.get('min', 'N/A')
                
                # Precision
                precision = market.get('precision', {})
                amount_precision = precision.get('amount', 'N/A')
                
                # Vérifier si valide
                if contract_size and min_amount:
                    status = "✅ OK"
                    success_count += 1
                else:
                    status = "⚠️ Partiel"
                    failed_symbols.append((symbol, f"contractSize={contract_size}, min={min_amount}"))
                
                print(f"{symbol:<20} {str(contract_size):<15} {str(min_amount):<15} {str(amount_precision):<15} {status}")
                
            except Exception as e:
                print(f"{symbol:<20} {'ERROR':<15} {'ERROR':<15} {'ERROR':<15} ❌ {str(e)[:20]}")
                failed_symbols.append((symbol, str(e)))
        
        # Test détaillé sur BTC
        print(f"\n[3/3] Test détaillé BTC/USDT:USDT...")
        if 'BTC/USDT:USDT' in markets:
            btc = markets['BTC/USDT:USDT']
            print(f"\n  Structure complète du market BTC:")
            print(f"    id: {btc.get('id')}")
            print(f"    symbol: {btc.get('symbol')}")
            print(f"    base: {btc.get('base')}")
            print(f"    quote: {btc.get('quote')}")
            print(f"    settle: {btc.get('settle')}")
            print(f"    contractSize: {btc.get('contractSize')}")
            print(f"    type: {btc.get('type')}")
            print(f"    linear: {btc.get('linear')}")
            
            print(f"\n  Limits:")
            limits = btc.get('limits', {})
            for key, val in limits.items():
                print(f"    {key}: {val}")
            
            print(f"\n  Precision:")
            precision = btc.get('precision', {})
            for key, val in precision.items():
                print(f"    {key}: {val}")
            
            print(f"\n  Info (raw MEXC):")
            info = btc.get('info', {})
            relevant_keys = ['contractSize', 'minVol', 'maxVol', 'volUnit', 'priceUnit', 'lotSize']
            for key in relevant_keys:
                if key in info:
                    print(f"    {key}: {info[key]}")
        
        # Résumé
        print("\n" + "=" * 70)
        print("  RÉSUMÉ")
        print("=" * 70)
        print(f"\n  Succès: {success_count}/{len(TEST_SYMBOLS)}")
        
        if failed_symbols:
            print(f"\n  ⚠️ Problèmes détectés:")
            for sym, reason in failed_symbols:
                print(f"    - {sym}: {reason}")
        
        if success_count == len(TEST_SYMBOLS):
            print(f"\n  ✅ Toutes les tailles de lot sont récupérables!")
        else:
            print(f"\n  ⚠️ Certaines paires ont des problèmes de récupération")
        
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()

async def test_live_order_manager():
    """Test via LiveOrderManager"""
    print("\n" + "=" * 70)
    print("  TEST VIA LIVE ORDER MANAGER")
    print("=" * 70)
    
    try:
        from trading.live_order_manager_futures import LiveOrderManagerFutures
        from config import TRADING_CONFIG
        
        # Config
        config = {
            'trading_mode': 'DRY_RUN',  # Mode simulation
            'api_key': os.getenv('MEXC_API_KEY'),
            'secret_key': os.getenv('MEXC_SECRET_KEY'),
            'default_leverage': TRADING_CONFIG.get('default_leverage', 10),
        }
        
        print("\n  Initialisation LiveOrderManagerFutures (DRY_RUN)...")
        manager = LiveOrderManagerFutures(**config)
        
        # Attendre initialisation
        await asyncio.sleep(2)
        
        # Test get_lot_size ou équivalent
        test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']
        
        print(f"\n  Test récupération lot size via manager:")
        for symbol in test_symbols:
            try:
                # Vérifier si la méthode existe
                if hasattr(manager, 'get_lot_size'):
                    lot_size = await manager.get_lot_size(symbol)
                    print(f"    {symbol}: lot_size = {lot_size}")
                elif hasattr(manager, '_get_market_info'):
                    info = await manager._get_market_info(symbol)
                    print(f"    {symbol}: market_info = {info}")
                else:
                    # Fallback: vérifier via exchange
                    if manager.exchange and hasattr(manager.exchange, 'markets'):
                        if symbol in manager.exchange.markets:
                            market = manager.exchange.markets[symbol]
                            contract_size = market.get('contractSize', 'N/A')
                            min_amount = market.get('limits', {}).get('amount', {}).get('min', 'N/A')
                            print(f"    {symbol}: contractSize={contract_size}, min={min_amount}")
                        else:
                            print(f"    {symbol}: ⚠️ Non trouvé dans exchange.markets")
                    else:
                        print(f"    {symbol}: ⚠️ Exchange non initialisé")
            except Exception as e:
                print(f"    {symbol}: ❌ Erreur - {e}")
        
        # Cleanup
        if hasattr(manager, 'close'):
            await manager.close()
        
    except Exception as e:
        print(f"\n  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main"""
    await test_lot_size()
    # await test_live_order_manager()  # Décommenter pour tester aussi via manager

if __name__ == "__main__":
    asyncio.run(main())
