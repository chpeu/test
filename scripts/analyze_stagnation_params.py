#!/usr/bin/env python3
"""Analyse des parametres de stagnation et MFE"""
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

def analyze_params(limit=100):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(f"""
        SELECT symbol, direction, pnl_pct, pnl_usdt, 
               max_favorable_excursion as mfe, max_adverse_excursion as mae,
               duration_seconds, exit_reason, break_even_set, trailing_stop_activated
        FROM trades
        ORDER BY timestamp_entry DESC
        LIMIT {limit}
    """)
    trades = cur.fetchall()
    
    print(f"\n{'='*70}")
    print(f"ANALYSE DES {len(trades)} DERNIERS TRADES")
    print(f"{'='*70}")
    
    # Stats globales
    wins = [t for t in trades if (t['pnl_pct'] or 0) > 0]
    losses = [t for t in trades if (t['pnl_pct'] or 0) < 0]
    total_pnl = sum(t['pnl_usdt'] or 0 for t in trades)
    
    print(f"\nWin Rate: {len(wins)/len(trades)*100:.1f}% | PnL Total: {total_pnl:.2f} USDT")
    
    # Analyse par raison de sortie
    print(f"\n{'='*70}")
    print("ANALYSE PAR RAISON DE SORTIE")
    print(f"{'='*70}")
    
    reasons = {}
    for t in trades:
        r = t['exit_reason'] or 'UNKNOWN'
        if r not in reasons:
            reasons[r] = {'count': 0, 'wins': 0, 'pnl': 0, 'durations': []}
        reasons[r]['count'] += 1
        reasons[r]['pnl'] += t['pnl_usdt'] or 0
        reasons[r]['durations'].append(t['duration_seconds'] or 0)
        if (t['pnl_pct'] or 0) > 0:
            reasons[r]['wins'] += 1
    
    for r, data in sorted(reasons.items(), key=lambda x: -x[1]['count']):
        wr = data['wins'] / data['count'] * 100 if data['count'] > 0 else 0
        avg_dur = sum(data['durations']) / len(data['durations']) if data['durations'] else 0
        print(f"\n{r}:")
        print(f"  Count: {data['count']} | WR: {wr:.1f}% | PnL: {data['pnl']:.2f} USDT | Duree moy: {avg_dur:.0f}s")
    
    # Analyse STAGNATION
    print(f"\n{'='*70}")
    print("ANALYSE STAGNATION (timeout=540s, min_pnl=0.03%, max_loss=-0.12%)")
    print(f"{'='*70}")
    
    stag_trades = [t for t in trades if 'STAGNATION' in (t['exit_reason'] or '')]
    stag_positive = [t for t in stag_trades if 'POSITIVE' in (t['exit_reason'] or '')]
    stag_mfe = [t for t in stag_trades if 'MFE' in (t['exit_reason'] or '')]
    stag_normal = [t for t in stag_trades if t['exit_reason'] == 'STAGNATION']
    
    print(f"\nSTAGNATION_POSITIVE: {len(stag_positive)} trades")
    if stag_positive:
        sp_wins = len([t for t in stag_positive if (t['pnl_pct'] or 0) > 0])
        sp_pnl = sum(t['pnl_usdt'] or 0 for t in stag_positive)
        print(f"  WR: {sp_wins/len(stag_positive)*100:.1f}% | PnL: {sp_pnl:.2f} USDT")
        print(f"  -> Recommandation: {'OK' if sp_wins/len(stag_positive) > 0.7 else 'A OPTIMISER'}")
    
    print(f"\nSTAGNATION_MFE_PROTECT: {len(stag_mfe)} trades")
    if stag_mfe:
        sm_wins = len([t for t in stag_mfe if (t['pnl_pct'] or 0) > 0])
        sm_pnl = sum(t['pnl_usdt'] or 0 for t in stag_mfe)
        print(f"  WR: {sm_wins/len(stag_mfe)*100:.1f}% | PnL: {sm_pnl:.2f} USDT")
        if sm_wins/len(stag_mfe) < 0.3:
            print(f"  -> PROBLEME: WR trop bas! Pullback 0.05% trop serre?")
    
    print(f"\nSTAGNATION (normal): {len(stag_normal)} trades")
    if stag_normal:
        sn_wins = len([t for t in stag_normal if (t['pnl_pct'] or 0) > 0])
        sn_pnl = sum(t['pnl_usdt'] or 0 for t in stag_normal)
        print(f"  WR: {sn_wins/len(stag_normal)*100:.1f}% | PnL: {sn_pnl:.2f} USDT")
    
    # Analyse MFE et Trailing
    print(f"\n{'='*70}")
    print("ANALYSE MFE ET TRAILING (trigger=0.08%)")
    print(f"{'='*70}")
    
    # Trades avec bon MFE mais mauvais PnL
    good_mfe_bad_pnl = [t for t in trades if (t['mfe'] or 0) >= 0.1 and (t['pnl_pct'] or 0) < 0]
    print(f"\nTrades avec MFE >= 0.1% mais PnL negatif: {len(good_mfe_bad_pnl)}")
    if good_mfe_bad_pnl:
        total_lost = sum(abs(t['pnl_pct'] or 0) for t in good_mfe_bad_pnl)
        print(f"  Profit perdu: {total_lost:.2f}%")
        for t in good_mfe_bad_pnl[:5]:
            print(f"  - {t['symbol']} {t['direction']}: MFE={t['mfe']:.2f}% -> PnL={t['pnl_pct']:.2f}% ({t['exit_reason']})")
    
    # Trailing MFE efficacite
    trailing_triggered = [t for t in trades if t['break_even_set']]
    print(f"\nTrades avec BE set (Trailing MFE trigger): {len(trailing_triggered)}/{len(trades)}")
    if trailing_triggered:
        tt_wins = len([t for t in trailing_triggered if (t['pnl_pct'] or 0) > 0])
        tt_pnl = sum(t['pnl_usdt'] or 0 for t in trailing_triggered)
        print(f"  WR: {tt_wins/len(trailing_triggered)*100:.1f}% | PnL: {tt_pnl:.2f} USDT")
    
    # Recommandations
    print(f"\n{'='*70}")
    print("RECOMMANDATIONS")
    print(f"{'='*70}")
    
    # 1. Stagnation Positive
    if stag_positive and len([t for t in stag_positive if (t['pnl_pct'] or 0) > 0])/len(stag_positive) > 0.7:
        print("\n[OK] Sortie Positive: WR > 70% - Garder active!")
    else:
        print("\n[?] Sortie Positive: Vous l'avez desactivee. A tester.")
    
    # 2. MFE Pullback
    if stag_mfe and len([t for t in stag_mfe if (t['pnl_pct'] or 0) > 0])/len(stag_mfe) < 0.2:
        print("\n[OPTIMISER] Pullback MFE 0.05% trop serre -> Essayer 0.08%")
    
    # 3. Trailing MFE trigger
    if good_mfe_bad_pnl and len(good_mfe_bad_pnl) > 5:
        print("\n[OPTIMISER] Trailing MFE trigger 0.08% peut-etre trop haut")
        print("  -> Essayer 0.06% pour proteger plus tot")
    
    # 4. Timeout stagnation
    long_trades = [t for t in trades if (t['duration_seconds'] or 0) > 540]
    if long_trades:
        long_wins = len([t for t in long_trades if (t['pnl_pct'] or 0) > 0])
        print(f"\n[INFO] Trades > 540s: {len(long_trades)} (WR: {long_wins/len(long_trades)*100:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_params(100)
