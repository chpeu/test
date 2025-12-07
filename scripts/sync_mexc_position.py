#!/usr/bin/env python3
"""
Script pour synchroniser une position MEXC existante avec le bot
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

def main():
    print("=" * 60)
    print("SYNC: Recuperation position SHIB depuis MEXC")
    print("=" * 60)
    
    browser_token = os.getenv('MEXC_BROWSER_TOKEN')
    if not browser_token:
        print("[ERREUR] MEXC_BROWSER_TOKEN non trouve")
        return
    
    print(f"[OK] Token: {browser_token[:20]}...")
    
    # Importer et utiliser le bypass client directement
    from trading.mexc_futures_bypass import MexcFuturesBypass
    import asyncio
    
    async def get_positions():
        client = MexcFuturesBypass(browser_token=browser_token, debug=True)
        
        print("\n[1/3] Recuperation positions ouvertes...")
        positions = await client.get_open_positions()
        
        if positions:
            # L'API retourne soit une liste, soit un dict avec 'data'
            if isinstance(positions, list):
                data = positions
            elif isinstance(positions, dict):
                data = positions.get('data', [])
            else:
                data = []
            print(f"[OK] {len(data)} position(s) trouvee(s)")
            
            for pos in data:
                # Gerer dict ou objet Position
                if hasattr(pos, 'symbol'):
                    symbol = pos.symbol
                    size = pos.hold_vol  # Contrats MEXC
                    entry = pos.hold_avg_price
                    direction = pos.direction
                else:
                    symbol = pos.get('symbol', 'N/A')
                    size = pos.get('holdVol', 0)
                    entry = pos.get('openAvgPrice', 0)
                    side = pos.get('positionType', 0)  # 1=LONG, 2=SHORT
                    direction = "LONG" if side == 1 else "SHORT"
                
                print(f"\n   Symbol: {symbol}")
                print(f"   Direction: {direction}")
                print(f"   Contrats MEXC: {size}")
                print(f"   Prix entree: {entry}")
                
                # Recuperer contractSize pour tout symbole
                if True:  # Pour tous les symboles
                    print(f"\n[2/3] Recuperation contractSize {symbol}...")
                    spec = await client.get_contract_spec(symbol)
                    if spec:
                        contract_size = spec.contract_size
                        real_tokens = float(size) * contract_size
                        print(f"   ContractSize: {contract_size}")
                        print(f"   Tokens reels: {real_tokens:,.0f}")
                        print(f"   Valeur USDT: {real_tokens * float(entry):.2f}")
        else:
            print("[WARN] Aucune position ouverte ou erreur API")
            print(f"   Response: {positions}")
        
        await client.close()
    
    # Run async
    asyncio.run(get_positions())
    
    print("\n" + "=" * 60)
    print("[INFO] Pour que le bot synchronise cette position:")
    print("   1. Redemarrez le backend: python main.py")
    print("   2. Ou attendez le prochain cycle de scan (~30s)")
    print("=" * 60)

if __name__ == "__main__":
    main()
