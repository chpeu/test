#!/usr/bin/env python3
"""
Diagnostic approfondi contractSize: CCXT vs API Brute
"""
import sys
import json
import asyncio
import aiohttp
import ccxt.async_support as ccxt

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def analyze_symbol(symbol_ccxt, symbol_mexc):
    print(f"\n{'='*30} ANALYSE {symbol_ccxt} {'='*30}")
    
    # 1. Via CCXT
    print("\n--- 1. CCXT (Standardisé) ---")
    try:
        mexc = ccxt.mexc()
        markets = await mexc.load_markets()
        
        if symbol_ccxt in markets:
            market = markets[symbol_ccxt]
            print(f"ContractSize: {market.get('contractSize')}")
            print(f"Linear: {market.get('linear')}")
            print(f"Inverse: {market.get('inverse')}")
            print(f"Precision: {market.get('precision')}")
            print(f"Limits: {market.get('limits')}")
            print(f"Info (Raw): {json.dumps(market.get('info'), indent=2)}")
        else:
            print("Symbol non trouvé dans CCXT")
        
        await mexc.close()
    except Exception as e:
        print(f"Erreur CCXT: {e}")

    # 2. Via API REST Directe (Endpoint public)
    print("\n--- 2. API MEXC Directe (contract/detail) ---")
    url = f"https://contract.mexc.com/api/v1/contract/detail?symbol={symbol_mexc}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get('success'):
                    info = data.get('data')
                    print(json.dumps(info, indent=2))
                else:
                    print(f"Erreur API: {data}")
    except Exception as e:
        print(f"Erreur HTTP: {e}")

async def main():
    # Analyser SOL (problématique) et SHIB (correct)
    await analyze_symbol('SOL/USDT:USDT', 'SOL_USDT')
    await analyze_symbol('SHIB/USDT:USDT', 'SHIB_USDT')

if __name__ == "__main__":
    asyncio.run(main())
