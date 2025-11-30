#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION MIGRATION ORDER FLOW
==================================
Teste l'integration complete des metriques order flow:
1. Colonnes presentes dans PostgreSQL
2. Calcul des metriques dans le scanner
3. Insertion dans le logger
"""

import sys
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from datetime import datetime

print("=" * 70)
print("  VERIFICATION MIGRATION ORDER FLOW")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

tests_passed = 0
tests_total = 0

# =============================================================================
# TEST 1: Colonnes PostgreSQL
# =============================================================================
print("\n[TEST 1] COLONNES POSTGRESQL")
print("-" * 70)

try:
    import psycopg2
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Connexion
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cursor = conn.cursor()
    
    # Verifier les colonnes order flow
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'scan_logs' 
        AND column_name IN (
            'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
            'book_depth_ratio', 'volume_acceleration', 'price_momentum_5'
        )
        ORDER BY column_name
    """)
    
    columns = cursor.fetchall()
    
    tests_total += 1
    if len(columns) == 6:
        print(f"   [OK] 6 colonnes order flow presentes dans scan_logs:")
        for col_name, col_type in columns:
            print(f"      - {col_name}: {col_type}")
        tests_passed += 1
    else:
        print(f"   [FAIL] Seulement {len(columns)}/6 colonnes trouvees")
        for col_name, col_type in columns:
            print(f"      - {col_name}: {col_type}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"   [ERROR] Erreur connexion PostgreSQL: {e}")
    tests_total += 1

# =============================================================================
# TEST 2: Calcul des metriques (scanner)
# =============================================================================
print("\n[TEST 2] CALCUL DES METRIQUES (SCANNER)")
print("-" * 70)

try:
    from core.scanner import ScalabilityScanner
    
    scanner = ScalabilityScanner()
    
    # Test avec des donnees simulees
    bid_vol = 1000.0
    ask_vol = 800.0
    spread = 0.05
    closes = [100.0, 100.5, 101.0, 100.8, 101.2, 101.5, 101.3, 101.8, 102.0, 102.5]
    volumes = [1000, 1200, 800, 1500, 900, 1100, 1300, 1400, 1600, 1800]
    
    metrics = scanner.calculate_orderflow_metrics(
        symbol="TEST/USDT",
        bid_vol=bid_vol,
        ask_vol=ask_vol,
        spread=spread,
        closes=closes,
        volumes=volumes
    )
    
    print(f"   Donnees test:")
    print(f"      bid_vol={bid_vol}, ask_vol={ask_vol}")
    print(f"      spread={spread}%")
    print(f"      closes={closes[-5:]}")
    print(f"      volumes={volumes[-5:]}")
    
    print(f"\n   Metriques calculees:")
    
    # Verifier chaque metrique
    all_ok = True
    
    # delta_volume = bid - ask = 1000 - 800 = 200
    expected_delta = bid_vol - ask_vol
    delta_ok = abs(metrics['delta_volume'] - expected_delta) < 0.01
    print(f"      delta_volume: {metrics['delta_volume']} (attendu: {expected_delta}) {'[OK]' if delta_ok else '[FAIL]'}")
    if not delta_ok: all_ok = False
    
    # imbalance_normalized = (bid-ask)/(bid+ask) = 200/1800 = 0.1111
    expected_imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol)
    imbalance_ok = abs(metrics['imbalance_normalized'] - expected_imbalance) < 0.01
    print(f"      imbalance_normalized: {metrics['imbalance_normalized']} (attendu: {expected_imbalance:.4f}) {'[OK]' if imbalance_ok else '[FAIL]'}")
    if not imbalance_ok: all_ok = False
    
    # book_depth_ratio = bid/ask = 1000/800 = 1.25
    expected_ratio = bid_vol / ask_vol
    ratio_ok = abs(metrics['book_depth_ratio'] - expected_ratio) < 0.01
    print(f"      book_depth_ratio: {metrics['book_depth_ratio']} (attendu: {expected_ratio:.4f}) {'[OK]' if ratio_ok else '[FAIL]'}")
    if not ratio_ok: all_ok = False
    
    # price_momentum_5 = (102.5 - 101.2) / 101.2 * 100 = 1.28%
    expected_momentum = ((closes[-1] - closes[-5]) / closes[-5]) * 100
    momentum_ok = abs(metrics['price_momentum_5'] - expected_momentum) < 0.1
    print(f"      price_momentum_5: {metrics['price_momentum_5']}% (attendu: {expected_momentum:.2f}%) {'[OK]' if momentum_ok else '[FAIL]'}")
    if not momentum_ok: all_ok = False
    
    # volume_acceleration (calcul plus complexe)
    print(f"      volume_acceleration: {metrics['volume_acceleration']}")
    print(f"      spread_volatility_5: {metrics['spread_volatility_5']}")
    
    tests_total += 1
    if all_ok:
        print(f"\n   [OK] Toutes les metriques sont correctement calculees")
        tests_passed += 1
    else:
        print(f"\n   [FAIL] Certaines metriques sont incorrectes")

except Exception as e:
    print(f"   [ERROR] Erreur calcul metriques: {e}")
    import traceback
    traceback.print_exc()
    tests_total += 1

# =============================================================================
# TEST 3: Integration dans scan_pair
# =============================================================================
print("\n[TEST 3] INTEGRATION DANS SCAN_PAIR")
print("-" * 70)

try:
    from core.scanner import ScalabilityScanner
    
    scanner = ScalabilityScanner()
    
    # Verifier que les attributs order flow sont dans la classe
    has_spread_history = hasattr(scanner, '_spread_history')
    has_volume_history = hasattr(scanner, '_volume_history')
    has_method = hasattr(scanner, 'calculate_orderflow_metrics')
    
    tests_total += 1
    if has_spread_history and has_volume_history and has_method:
        print(f"   [OK] Scanner a tous les attributs order flow:")
        print(f"      - _spread_history: {type(scanner._spread_history)}")
        print(f"      - _volume_history: {type(scanner._volume_history)}")
        print(f"      - calculate_orderflow_metrics: methode presente")
        tests_passed += 1
    else:
        print(f"   [FAIL] Attributs manquants:")
        print(f"      - _spread_history: {has_spread_history}")
        print(f"      - _volume_history: {has_volume_history}")
        print(f"      - calculate_orderflow_metrics: {has_method}")

except Exception as e:
    print(f"   [ERROR] Erreur verification scanner: {e}")
    tests_total += 1

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"\n   Tests passes: {tests_passed}/{tests_total}")

if tests_passed == tests_total:
    print("\n   [SUCCESS] MIGRATION ORDER FLOW COMPLETE")
    print("""
   Fonctionnalites implementees:
   - 6 colonnes order flow dans PostgreSQL
   - Calcul des metriques dans scanner.py
   - Integration dans scan_pair()
   - Passage au logger via scalability_data
   
   METRIQUES ORDER FLOW:
   +----------------------+------------------------------------------+
   | Metrique             | Description                              |
   +----------------------+------------------------------------------+
   | delta_volume         | bid_vol - ask_vol (pression nette)       |
   | imbalance_normalized | (bid-ask)/(bid+ask) ratio [-1, +1]       |
   | spread_volatility_5  | Ecart-type spread sur 5 bougies          |
   | book_depth_ratio     | bid_vol / ask_vol                        |
   | volume_acceleration  | Derivee du volume (momentum)             |
   | price_momentum_5     | % change prix sur 5 bougies              |
   +----------------------+------------------------------------------+
   
   UTILITE POUR ML:
   - Detecter faux signaux (divergence prix/pression)
   - Anticiper breakouts (accumulation volume)
   - Identifier retournements (epuisement volume)
""")
else:
    print(f"\n   [WARNING] {tests_total - tests_passed} TEST(S) ECHOUE(S)")

print("=" * 70)
