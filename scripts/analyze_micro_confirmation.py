#!/usr/bin/env python3
"""Analyse de l'efficacité des micro-confirmations"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def analyze_micro_confirmation():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Verifier si micro_confirmation existe dans scan_logs
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'scan_logs' AND column_name LIKE '%micro%'
    """)
    micro_cols = cur.fetchall()
    print(f"Colonnes micro-confirmation dans scan_logs: {[c['column_name'] for c in micro_cols]}")

    # Chercher les rejets par micro-confirmation
    cur.execute("""
        SELECT COUNT(*) as count FROM scan_logs 
        WHERE reject_reason_category = 'micro_confirmation_filter'
    """)
    result = cur.fetchone()
    micro_rejects = result['count'] if result else 0
    print(f"\nRejets par micro-confirmation: {micro_rejects}")

    # Analyser les trades recents (41 derniers) pour voir MFE initial
    print("\n" + "="*70)
    print("ANALYSE MFE DES 41 DERNIERS TRADES")
    print("="*70)
    
    cur.execute("""
        SELECT symbol, direction, pnl_pct, max_favorable_excursion, max_adverse_excursion,
               duration_seconds, exit_reason
        FROM trades
        ORDER BY timestamp_entry DESC
        LIMIT 41
    """)
    trades = cur.fetchall()
    
    # Trades qui n'ont jamais ete en profit (MFE <= 0)
    never_profit = [t for t in trades if (t['max_favorable_excursion'] or 0) <= 0]
    quick_reversal = [t for t in trades if (t['max_favorable_excursion'] or 0) <= 0.05 and (t['duration_seconds'] or 0) < 60]
    
    print(f"\nTrades jamais en profit (MFE <= 0): {len(never_profit)}/{len(trades)} ({len(never_profit)/len(trades)*100:.1f}%)")
    print(f"Reversals rapides (MFE <= 0.05% et duree < 60s): {len(quick_reversal)}/{len(trades)}")
    
    if quick_reversal:
        print("\n--- REVERSALS RAPIDES (candidats pour micro-confirmation) ---")
        for t in quick_reversal[:10]:
            mfe = t['max_favorable_excursion'] or 0
            mae = t['max_adverse_excursion'] or 0
            pnl = t['pnl_pct'] or 0
            print(f"  {t['symbol']} {t['direction']}: MFE={mfe:.2f}% MAE={mae:.2f}% PnL={pnl:.2f}% ({t['duration_seconds']}s) - {t['exit_reason']}")
    
    # Estimation de l'impact de micro-confirmation
    print("\n" + "="*70)
    print("ESTIMATION IMPACT MICRO-CONFIRMATION")
    print("="*70)
    
    # Si micro-confirmation avait filtre les trades avec MFE <= 0.05%
    potential_saves = [t for t in trades if (t['max_favorable_excursion'] or 0) <= 0.05 and (t['pnl_pct'] or 0) < 0]
    total_saved = sum(abs(t['pnl_pct'] or 0) for t in potential_saves)
    
    print(f"\nTrades perdants avec MFE <= 0.05% (auraient pu etre filtres): {len(potential_saves)}")
    print(f"Pertes potentiellement evitees: {total_saved:.2f}%")
    
    # Recommandation de delai
    print("\n" + "="*70)
    print("RECOMMANDATION DELAI MICRO-CONFIRMATION")
    print("="*70)
    
    print("""
    Delai recommande selon le style de trading:
    
    | Delai    | Avantages                  | Inconvenients              |
    |----------|----------------------------|----------------------------|
    | 200-300ms| Filtre les spikes rapides  | Peut rater bons trades     |
    | 500ms    | Bon compromis              | Standard recommande        |
    | 800-1000ms| Filtre fort               | Risque de rater opportunites|
    
    Pour du scalping agressif (ATR faible, TP/SL serres):
    - 300-500ms est optimal
    
    Pour du trading moins agressif:
    - 500-800ms peut etre mieux
    
    Votre config actuelle: 500ms - C'est un bon compromis.
    """)

    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_micro_confirmation()
