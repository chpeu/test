#!/usr/bin/env python3
"""Check contractSize for common symbols"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import asyncio
from trading.mexc_futures_bypass import MexcFuturesBypass

SYMBOLS = ['SOL_USDT', 'SHIB_USDT', 'BTC_USDT', 'ETH_USDT', 'XRP_USDT', 'INJ_USDT']

async def main():
    print("=" * 60)
    print("ContractSize pour differents symboles")
    print("=" * 60)
    
    token = os.getenv('MEXC_BROWSER_TOKEN')
    if not token:
        print("[ERREUR] MEXC_BROWSER_TOKEN non trouve")
        return
    
    client = MexcFuturesBypass(browser_token=token, debug=False)
    
    print(f"\n{'Symbol':<15} {'ContractSize':<15} {'Interpretation'}")
    print("-" * 60)
    
    for symbol in SYMBOLS:
        try:
            spec = await client.get_contract_spec(symbol)
            if spec:
                cs = spec.contract_size
                if cs > 1:
                    interp = f"1 contrat = {cs} tokens"
                elif cs < 1:
                    interp = f"1 contrat = {cs} tokens (micro)"
                else:
                    interp = "1 contrat = 1 token"
                print(f"{symbol:<15} {cs:<15} {interp}")
            else:
                print(f"{symbol:<15} {'N/A':<15} Spec non trouvee")
        except Exception as e:
            print(f"{symbol:<15} {'ERROR':<15} {e}")
    
    await client.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
