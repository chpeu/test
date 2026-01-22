#!/usr/bin/env python3
"""
Detecter les contractSize pour toutes les paires tradables
Compare les valeurs API avec les valeurs connues incorrectes
"""

import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import asyncio
import aiohttp

# Overrides connus (a completer manuellement apres verification sur MEXC)
KNOWN_OVERRIDES = {
    # Micro-contrats (1 contrat < 1 token)
    'ZEC_USDT': 0.01,
    'BCH_USDT': 0.01,
    'ETC_USDT': 0.01,
    'LTC_USDT': 0.01,
    'SOL_USDT': 0.1,
    # Mega-contrats (1 contrat > 1 token)
    'SHIB_USDT': 1000,
    'PEPE_USDT': 1000000,  # A verifier
    'FLOKI_USDT': 1000000,  # A verifier
    'BONK_USDT': 1000000,  # A verifier
    'LUNC_USDT': 1000,  # A verifier
}

async def fetch_all_contracts():
    """Recuperer les specs de tous les contrats depuis l'API MEXC"""
    url = "https://contract.mexc.com/api/v1/contract/detail"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('success'):
                    return data.get('data', [])
    return []

async def main():
    print("=" * 80)
    print("DETECTION ContractSize - Toutes les paires MEXC Futures")
    print("=" * 80)
    
    contracts = await fetch_all_contracts()
    print(f"\n[OK] {len(contracts)} contrats recuperes depuis MEXC API\n")
    
    # Categoriser les contrats
    micro_contracts = []  # contractSize < 1
    mega_contracts = []   # contractSize > 1
    normal_contracts = [] # contractSize = 1
    
    for contract in contracts:
        symbol = contract.get('symbol', '')
        if not symbol.endswith('_USDT'):
            continue
            
        contract_size = float(contract.get('contractSize', 1))
        
        if contract_size < 1:
            micro_contracts.append((symbol, contract_size))
        elif contract_size > 1:
            mega_contracts.append((symbol, contract_size))
        else:
            normal_contracts.append((symbol, contract_size))
    
    # Afficher micro-contrats
    print("=" * 80)
    print("MICRO-CONTRATS (1 contrat < 1 token) - API dit contractSize < 1")
    print("=" * 80)
    print(f"{'Symbol':<20} {'API contractSize':<20} {'Override?'}")
    print("-" * 60)
    for symbol, cs in sorted(micro_contracts):
        override = KNOWN_OVERRIDES.get(symbol, '-')
        status = "OK" if symbol in KNOWN_OVERRIDES else "A VERIFIER"
        print(f"{symbol:<20} {cs:<20} {override} ({status})")
    
    # Afficher mega-contrats
    print("\n" + "=" * 80)
    print("MEGA-CONTRATS (1 contrat > 1 token) - API dit contractSize > 1")
    print("=" * 80)
    print(f"{'Symbol':<20} {'API contractSize':<20} {'Override?'}")
    print("-" * 60)
    for symbol, cs in sorted(mega_contracts):
        override = KNOWN_OVERRIDES.get(symbol, '-')
        status = "OK" if symbol in KNOWN_OVERRIDES else "A VERIFIER"
        print(f"{symbol:<20} {cs:<20} {override} ({status})")
    
    # Afficher les overrides manuels (API dit 1.0 mais c'est faux)
    print("\n" + "=" * 80)
    print("OVERRIDES MANUELS (API dit 1.0 mais incorrect)")
    print("=" * 80)
    print(f"{'Symbol':<20} {'API contractSize':<20} {'Valeur Reelle':<20} {'Status'}")
    print("-" * 80)
    
    # Trouver les symboles ou l'API dit 1.0 mais on a un override
    for symbol, cs in normal_contracts:
        if symbol in KNOWN_OVERRIDES:
            real_cs = KNOWN_OVERRIDES[symbol]
            print(f"{symbol:<20} {'1.0 (FAUX)':<20} {real_cs:<20} OVERRIDE ACTIF")
    
    # Suggerer les symboles suspects (meme coins, etc.)
    print("\n" + "=" * 80)
    print("SYMBOLES SUSPECTS (a verifier manuellement sur MEXC)")
    print("=" * 80)
    
    suspect_keywords = ['SHIB', 'PEPE', 'FLOKI', 'BONK', 'DOGE', 'LUNC', '1000', 'SATS', 'RATS', 'ELON']
    suspects = []
    for symbol, cs in normal_contracts:
        if symbol not in KNOWN_OVERRIDES:
            for kw in suspect_keywords:
                if kw in symbol:
                    suspects.append((symbol, cs))
                    break
    
    if suspects:
        print(f"{'Symbol':<20} {'API contractSize':<20} {'Action'}")
        print("-" * 60)
        for symbol, cs in sorted(suspects):
            print(f"{symbol:<20} {cs:<20} Verifier sur MEXC!")
    else:
        print("Aucun suspect trouve.")
    
    # Instructions
    print("\n" + "=" * 80)
    print("COMMENT VERIFIER UN SYMBOLE SUR MEXC:")
    print("=" * 80)
    print("""
1. Allez sur https://futures.mexc.com/exchange/SYMBOL
2. Regardez "Contract Size" dans les specifications
3. Si different de l'API, ajoutez dans CONTRACT_SIZE_OVERRIDES:

   'SYMBOL_USDT': valeur_reelle,

4. Fichier: trading/mexc_futures_bypass.py (ligne ~1224)
""")
    
    # Generer le code Python pour les overrides
    print("=" * 80)
    print("CODE A COPIER (tous les overrides connus):")
    print("=" * 80)
    print("CONTRACT_SIZE_OVERRIDES = {")
    print("    # Micro-contrats (1 contrat < 1 token)")
    for symbol, cs in sorted(KNOWN_OVERRIDES.items()):
        if cs < 1:
            print(f"    '{symbol}': {cs},")
    print("    # Mega-contrats (1 contrat > 1 token)")
    for symbol, cs in sorted(KNOWN_OVERRIDES.items()):
        if cs >= 1:
            print(f"    '{symbol}': {cs},")
    print("}")

if __name__ == "__main__":
    asyncio.run(main())
