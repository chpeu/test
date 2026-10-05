#!/usr/bin/env python3
"""
Analyse de l'impact des modifications ATR sur les trades existants.
Compare ATR% brut (1m) vs ATR% blende/clampe pour evaluer l'impact.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def analyze_trades():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Recuperer les trades avec leurs metriques ATR
    cur.execute("""
        SELECT 
            t.id,
            t.symbol,
            t.direction,
            t.net_pnl_pct,
            t.exit_reason,
            t.entry_price,
            tam.entry_atr_1m,
            tam.entry_atr_5m,
            tam.entry_atr_pct_1m,
            tam.entry_atr_pct_5m,
            tam.param_be_atr_mult,
            tam.param_trailing_trigger_mult,
            tam.param_trailing_distance_mult,
            tam.calculated_be_trigger_pnl_pct,
            tam.calculated_trailing_trigger_pnl_pct,
            tam.be_triggered,
            tam.trailing_activated,
            tam.max_pnl_reached,
            tam.min_pnl_reached
        FROM trades t
        LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
        ORDER BY t.created_at DESC
        LIMIT 39
    """)
    
    trades = cur.fetchall()
    cur.close()
    conn.close()
    
    print("=" * 80)
    print("ANALYSE IMPACT MODIFICATIONS ATR SUR 39 TRADES")
    print("=" * 80)
    print(f"\nTrades analyses: {len(trades)}")
    
    # Config par defaut
    ATR_MIN = 0.10
    ATR_MAX = 1.0
    
    impacts = []
    
    for t in trades:
        if not t['entry_atr_pct_1m'] or not t['entry_price']:
            continue
            
        atr_1m = t['entry_atr_1m'] or 0
        atr_5m = t['entry_atr_5m'] or 0
        entry = t['entry_price']
        
        # ATR% brut (ancien calcul)
        atr_pct_old = t['entry_atr_pct_1m']
        
        # ATR% blende + clampe (nouveau calcul)
        if atr_1m > 0 and atr_5m > 0:
            atr_blended = (atr_1m * 0.7) + (atr_5m * 0.3)
        else:
            atr_blended = atr_1m
        
        atr_pct_new = (atr_blended / entry) * 100 if entry > 0 else 0
        atr_pct_new = max(ATR_MIN, min(ATR_MAX, atr_pct_new))
        
        # Difference
        diff = atr_pct_new - atr_pct_old
        diff_pct = (diff / atr_pct_old * 100) if atr_pct_old > 0 else 0
        
        # Impact sur les triggers
        be_mult = t['param_be_atr_mult'] or 1.0
        trail_mult = t['param_trailing_trigger_mult'] or 1.5
        
        be_old = atr_pct_old * be_mult
        be_new = atr_pct_new * be_mult
        
        trail_old = atr_pct_old * trail_mult
        trail_new = atr_pct_new * trail_mult
        
        # Determiner si le comportement aurait change
        max_pnl = t['max_pnl_reached'] or 0
        be_triggered = t['be_triggered']
        trail_activated = t['trailing_activated']
        
        # Le BE/Trailing aurait-il ete declenche differemment?
        be_would_change = (max_pnl >= be_old) != (max_pnl >= be_new)
        trail_would_change = (max_pnl >= trail_old) != (max_pnl >= trail_new)
        
        impacts.append({
            'symbol': t['symbol'],
            'pnl': t['net_pnl_pct'] or 0,
            'exit': t['exit_reason'],
            'atr_old': atr_pct_old,
            'atr_new': atr_pct_new,
            'diff': diff,
            'diff_pct': diff_pct,
            'be_old': be_old,
            'be_new': be_new,
            'trail_old': trail_old,
            'trail_new': trail_new,
            'be_would_change': be_would_change,
            'trail_would_change': trail_would_change,
            'max_pnl': max_pnl
        })
    
    # Statistiques
    print("\n" + "-" * 80)
    print("COMPARAISON ATR% BRUT vs BLENDE/CLAMPE")
    print("-" * 80)
    
    if not impacts:
        print("Aucun trade avec donnees ATR completes")
        return
    
    avg_old = sum(i['atr_old'] for i in impacts) / len(impacts)
    avg_new = sum(i['atr_new'] for i in impacts) / len(impacts)
    avg_diff = sum(i['diff'] for i in impacts) / len(impacts)
    
    print(f"ATR% moyen (ancien):  {avg_old:.4f}%")
    print(f"ATR% moyen (nouveau): {avg_new:.4f}%")
    print(f"Difference moyenne:   {avg_diff:+.4f}%")
    
    # Trades ou le comportement aurait change
    be_changes = [i for i in impacts if i['be_would_change']]
    trail_changes = [i for i in impacts if i['trail_would_change']]
    
    print("\n" + "-" * 80)
    print("IMPACT SUR LES TRIGGERS")
    print("-" * 80)
    print(f"Trades ou BE aurait change:       {len(be_changes)}/{len(impacts)}")
    print(f"Trades ou Trailing aurait change: {len(trail_changes)}/{len(impacts)}")
    
    if be_changes or trail_changes:
        print("\nDetails des trades impactes:")
        for i in be_changes + trail_changes:
            if i not in be_changes or i not in trail_changes:
                impact_type = "BE" if i in be_changes else "TRAIL"
                print(f"  {i['symbol']:12} | PnL: {i['pnl']:+.2f}% | MaxPnL: {i['max_pnl']:.2f}% | "
                      f"ATR: {i['atr_old']:.3f}% -> {i['atr_new']:.3f}% | Impact: {impact_type}")
    
    # Distribution des differences
    print("\n" + "-" * 80)
    print("DISTRIBUTION DES DIFFERENCES ATR%")
    print("-" * 80)
    
    clamped_low = len([i for i in impacts if i['atr_new'] == ATR_MIN and i['atr_old'] < ATR_MIN])
    clamped_high = len([i for i in impacts if i['atr_new'] == ATR_MAX and i['atr_old'] > ATR_MAX])
    blended_diff = len([i for i in impacts if abs(i['diff']) > 0.01])
    
    print(f"Trades clampes a {ATR_MIN}% (min): {clamped_low}")
    print(f"Trades clampes a {ATR_MAX}% (max): {clamped_high}")
    print(f"Trades avec diff > 0.01%:        {blended_diff}")
    
    # Conclusion
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    
    total_impacted = len(set(be_changes + trail_changes))
    if total_impacted == 0:
        print(">>> AUCUN TRADE N'AURAIT EU UN COMPORTEMENT DIFFERENT")
        print("    Les modifications n'auraient pas change la performance passee.")
    else:
        print(f">>> {total_impacted} TRADE(S) AURAIT EU UN COMPORTEMENT DIFFERENT")
        print("    Impact potentiel sur la performance.")
        
        # Calculer l'impact PnL potentiel
        impacted_pnl = sum(i['pnl'] for i in be_changes + trail_changes if i in be_changes or i in trail_changes)
        print(f"    PnL cumule des trades impactes: {impacted_pnl:+.2f}%")

if __name__ == '__main__':
    analyze_trades()
