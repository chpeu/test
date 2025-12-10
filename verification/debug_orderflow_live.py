#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEBUG ORDER FLOW LIVE - Teste le flux complet en temps réel
============================================================
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.scanner import ScalabilityScanner

async def test_scanner():
    print("=" * 70)
    print("  DEBUG ORDER FLOW - TEST SCANNER EN DIRECT")
    print("=" * 70)
    
    scanner = ScalabilityScanner()
    
    # Test 1: Vérifier que la méthode existe
    print("\n[TEST 1] Méthode calculate_orderflow_metrics")
    if hasattr(scanner, 'calculate_orderflow_metrics'):
        print("   ✅ Méthode présente")
    else:
        print("   ❌ ERREUR: Méthode manquante!")
        return
    
    # Test 2: Scanner une paire réelle
    print("\n[TEST 2] Scanner une paire (SOL/USDT:USDT)")
    try:
        result = await scanner.scan_pair("SOL/USDT:USDT")
        
        if result:
            print(f"   ✅ Scan réussi, {len(result)} clés retournées")
            
            # Vérifier les clés order flow
            orderflow_keys = [
                'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
                'book_depth_ratio', 'volume_acceleration', 'price_momentum_5'
            ]
            
            print("\n   Clés order flow dans le résultat:")
            for key in orderflow_keys:
                value = result.get(key)
                status = "✅" if value is not None else "❌ NULL"
                print(f"      {key}: {value} {status}")
            
            # Afficher toutes les clés pour debug
            print(f"\n   Toutes les clés retournées:")
            for key in sorted(result.keys()):
                print(f"      - {key}: {result[key]}")
        else:
            print("   ❌ Scan a retourné None")
            
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Scanner top pairs
    print("\n[TEST 3] Scanner top_pairs (5 paires)")
    try:
        top_pairs = await scanner.scan_top_pairs(5)
        
        if top_pairs:
            print(f"   ✅ {len(top_pairs)} paires scannées")
            
            # Vérifier la première paire
            first_pair = top_pairs[0]
            print(f"\n   Première paire: {first_pair.get('symbol')}")
            
            orderflow_keys = [
                'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
                'book_depth_ratio', 'volume_acceleration', 'price_momentum_5'
            ]
            
            print("   Métriques order flow:")
            all_present = True
            for key in orderflow_keys:
                value = first_pair.get(key)
                status = "✅" if value is not None else "❌ NULL"
                if value is None:
                    all_present = False
                print(f"      {key}: {value} {status}")
            
            if all_present:
                print("\n   ✅ TOUTES LES MÉTRIQUES SONT PRÉSENTES DANS TOP_PAIRS!")
            else:
                print("\n   ❌ CERTAINES MÉTRIQUES MANQUENT DANS TOP_PAIRS")
        else:
            print("   ❌ top_pairs vide")
            
    except Exception as e:
        print(f"   ❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
    
    await scanner.close()
    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(test_scanner())
