# -*- coding: utf-8 -*-
"""
Script de debug pour verifier le calcul de size en temps reel
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Load .env
from dotenv import load_dotenv
load_dotenv()

import time
from trading.live_order_manager_futures import LiveOrderManagerFutures
from config import TRADING_CONFIG

# Get API keys from env
API_KEY = os.getenv('MEXC_API_KEY')
API_SECRET = os.getenv('MEXC_API_SECRET')

def debug_position_size():
    """Debug le calcul de size pour la position active"""
    
    print("=" * 60)
    print("[DEBUG] POSITION SIZE")
    print("=" * 60)
    
    # Initialiser le manager
    print(f"API Key: {API_KEY[:10]}..." if API_KEY else "API Key: MISSING")
    
    manager = LiveOrderManagerFutures(
        api_key=API_KEY,
        api_secret=API_SECRET,
        default_leverage=TRADING_CONFIG.get('default_leverage', 1),
        dry_run=False,
        use_bypass=True
    )
    
    print("\n[*] Recuperation des positions ouvertes via CCXT...")
    
    try:
        # Recuperer toutes les positions
        positions = manager.exchange.fetch_positions()
        
        open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
        
        if not open_positions:
            print("[X] Aucune position ouverte")
            return
        
        for pos in open_positions:
            symbol = pos.get('symbol')
            print(f"\n{'='*60}")
            print(f"[POSITION] {symbol}")
            print(f"{'='*60}")
            
            # Donnees brutes CCXT
            contracts = float(pos.get('contracts') or 0)
            entry_price = float(pos.get('entryPrice') or 0)
            notional = float(pos.get('notional') or 0)
            contract_size_ccxt = float(pos.get('contractSize') or 0)
            contract_size_info = float((pos.get('info') or {}).get('contractSize') or 0)
            
            print(f"\n[Donnees brutes CCXT]")
            print(f"   contracts (MEXC): {contracts}")
            print(f"   entryPrice: {entry_price}")
            print(f"   notional: {notional}")
            print(f"   contractSize (root): {contract_size_ccxt}")
            print(f"   contractSize (info): {contract_size_info}")
            
            # Contract size utilise
            if contract_size_ccxt > 0:
                cs = contract_size_ccxt
                cs_source = "root"
            elif contract_size_info > 0:
                cs = contract_size_info
                cs_source = "info"
            else:
                cs = 1.0
                cs_source = "default"
            
            print(f"\n[Contract size utilise] {cs} (source: {cs_source})")
            
            # Calculs
            real_tokens = contracts * cs
            size_usdt_calculated = real_tokens * entry_price
            
            print(f"\n[Calcul CORRECT]")
            print(f"   real_tokens = {contracts} x {cs} = {real_tokens}")
            print(f"   size_usdt = {real_tokens} x {entry_price} = {size_usdt_calculated:.4f} USDT")
            
            print(f"\n[Comparaison]")
            print(f"   notional (CCXT):     {notional:.4f} USDT")
            print(f"   calcule (correct):   {size_usdt_calculated:.4f} USDT")
            
            if abs(notional - size_usdt_calculated) > 0.01:
                print(f"   [!] DIFFERENCE: {abs(notional - size_usdt_calculated):.4f} USDT")
                print(f"   [!] Ratio notional/calcule: {notional/size_usdt_calculated:.4f}")
            else:
                print(f"   [OK] Valeurs coherentes")
            
            # Test via get_position
            print(f"\n[Test get_position()]")
            spot_symbol = symbol.replace(':USDT', '').replace('/USDT', '') + '/USDT'
            result = manager.get_position(spot_symbol, prefer_ccxt=True)
            
            if result:
                print(f"   size (retourne): {result.get('size', 'N/A')}")
                print(f"   contracts: {result.get('contracts', 'N/A')}")
                print(f"   tokens: {result.get('tokens', 'N/A')}")
                print(f"   contract_size: {result.get('contract_size', 'N/A')}")
                print(f"   entry_price: {result.get('entry_price', 'N/A')}")
                
                # Verifier la coherence
                ret_size = result.get('size', 0)
                ret_tokens = result.get('tokens', 0)
                ret_entry = result.get('entry_price', 0)
                
                if ret_tokens > 0 and ret_entry > 0:
                    expected = ret_tokens * ret_entry
                    print(f"\n   [Verification] tokens x entry = {ret_tokens} x {ret_entry} = {expected:.4f}")
                    print(f"   [Verification] size retourne: {ret_size:.4f}")
                    if abs(expected - ret_size) > 0.01:
                        print(f"   [ERREUR] size devrait etre {expected:.4f}, pas {ret_size:.4f}")
                    else:
                        print(f"   [OK] Calcul correct!")
            else:
                print(f"   [X] get_position retourne None")
            
            # Test via _verify_position_size
            print(f"\n[Test _verify_position_size()]")
            verify_result = manager._verify_position_size(spot_symbol, entry_price, retries=1, delay_sec=0)
            
            if verify_result:
                print(f"   size_usdt: {verify_result.get('size_usdt', 'N/A')}")
                print(f"   contracts: {verify_result.get('contracts', 'N/A')}")
                print(f"   tokens: {verify_result.get('tokens', 'N/A')}")
                print(f"   contract_size: {verify_result.get('contract_size', 'N/A')}")
                print(f"   entry_price: {verify_result.get('entry_price', 'N/A')}")
            else:
                print(f"   [X] _verify_position_size retourne None")
                
    except Exception as e:
        print(f"[ERREUR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_position_size()
