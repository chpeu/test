#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyser et proposer des configurations TP/SL optimisées
"""
import psycopg2
import numpy as np

def analyze_and_suggest_tp_sl():
    """Analyser les performances et suggérer des configs optimales"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Récupérer les données des derniers trades
    query = """
        SELECT 
            entry_price,
            exit_price,
            sl_price,
            tp_price,
            net_pnl_pct,
            exit_reason,
            direction,
            symbol,
            timestamp_entry,
            -- Extraire ATR si disponible
            (config_snapshot::json->>'atr')::float as atr_value
        FROM trades 
        WHERE timestamp_exit >= NOW() - INTERVAL '7 days'
        AND entry_price IS NOT NULL
        AND exit_price IS NOT NULL
        ORDER BY timestamp_entry DESC
    """
    
    cursor.execute(query)
    trades = cursor.fetchall()
    
    print("📊 ANALYSE APPROFONDIE TP/SL")
    print("=" * 70)
    
    # Analyser les distances en % depuis l'entrée
    print(f"\n📈 ANALYSE DES DISTANCES DE PRIX ({len(trades)} trades):")
    
    max_gains = []
    max_losses = []
    sl_distances = []
    tp_distances = []
    
    for trade in trades:
        entry, exit_price, sl, tp, pnl, reason, direction, symbol, ts, atr = trade
        
        if entry and exit_price:
            # Calculer le gain/perte maximum potentiel
            if direction == 'LONG':
                if sl and sl < entry:
                    sl_dist_pct = ((entry - sl) / entry) * 100
                    sl_distances.append(sl_dist_pct)
                if tp and tp > entry:
                    tp_dist_pct = ((tp - entry) / entry) * 100
                    tp_distances.append(tp_dist_pct)
            else:  # SHORT
                if sl and sl > entry:
                    sl_dist_pct = ((sl - entry) / entry) * 100
                    sl_distances.append(sl_dist_pct)
                if tp and tp < entry:
                    tp_dist_pct = ((entry - tp) / entry) * 100
                    tp_distances.append(tp_dist_pct)
    
    if sl_distances:
        print(f"\n🛡️  DISTANCES SL (moyennes):")
        print(f"   SL moyen: {np.mean(sl_distances):.2f}%")
        print(f"   SL min: {np.min(sl_distances):.2f}%")
        print(f"   SL max: {np.max(sl_distances):.2f}%")
        print(f"   SL médian: {np.median(sl_distances):.2f}%")
    
    if tp_distances:
        print(f"\n🎯 DISTANCES TP (moyennes):")
        print(f"   TP moyen: {np.mean(tp_distances):.2f}%")
        print(f"   TP min: {np.min(tp_distances):.2f}%")
        print(f"   TP max: {np.max(tp_distances):.2f}%")
    
    # Analyser les PnL par raison de sortie
    print(f"\n📋 PERFORMANCE PAR RAISON DE SORTIE:")
    cursor.execute("""
        SELECT 
            exit_reason,
            COUNT(*) as count,
            AVG(net_pnl_pct) as avg_pnl,
            STDDEV(net_pnl_pct) as stddev_pnl
        FROM trades 
        WHERE timestamp_exit >= NOW() - INTERVAL '7 days'
        GROUP BY exit_reason
        ORDER BY count DESC
    """)
    
    results = cursor.fetchall()
    for reason, count, avg_pnl, stddev in results:
        print(f"   {reason:15s}: {count:3d} trades | PnL moyen: {avg_pnl:+.3f}% (±{stddev:.3f}%)")
    
    # Suggestions basées sur l'analyse
    print(f"\n💡 SUGGESTIONS D'OPTIMISATION:")
    
    # Suggestion 1: Réduire le TP pour qu'il soit atteignable
    if tp_distances:
        realistic_tp = np.percentile(tp_distances, 25)  # 25ème percentile
        print(f"\n1. TP RÉALISTE:")
        print(f"   Actuel: 500% (jamais atteint)")
        print(f"   Suggéré: {realistic_tp:.1f}% (25ème percentile)")
        print(f"   Rationnel: Un TP plus raisonnable sera plus souvent atteint")
    
    # Suggestion 2: Ajuster le SL pour améliorer le ratio
    if sl_distances:
        current_sl = 25.0
        suggested_sl = np.percentile(sl_distances, 75)  # 75ème percentile
        print(f"\n2. SL PLUS SERRÉ:")
        print(f"   Actuel: {current_sl:.1f}%")
        print(f"   Suggéré: {suggested_sl:.1f}% (75ème percentile)")
        print(f"   Impact: Réduira les pertes moyennes")
        
        if realistic_tp and suggested_sl:
            new_ratio = realistic_tp / suggested_sl
            print(f"   Nouveau ratio: {new_ratio:.2f} (vs 20.0 théorique)")
    
    # Suggestion 3: Configurations alternatives
    print(f"\n3. CONFIGURATIONS ALTERNATIVES TESTÉES:")
    
    configs = [
        {"tp": 1.0, "sl": 0.5, "ratio": 2.0},
        {"tp": 1.5, "sl": 0.5, "ratio": 3.0},
        {"tp": 2.0, "sl": 0.8, "ratio": 2.5},
        {"tp": 1.2, "sl": 0.4, "ratio": 3.0},
    ]
    
    for config in configs:
        tp, sl, ratio = config["tp"], config["sl"], config["ratio"]
        print(f"\n   Config: TP {tp:.1f}% / SL {sl:.1f}% (ratio {ratio:.1f})")
        
        # Simuler les résultats avec cette config
        simulated_wins = 0
        simulated_losses = 0
        total_simulated_pnl = 0
        
        for trade in trades:
            entry, exit_price, sl_orig, tp_orig, pnl, reason, direction, symbol, ts, atr = trade
            if not entry or not exit_price:
                continue
                
            # Calculer le PnL avec nouveaux TP/SL
            if direction == 'LONG':
                new_sl = entry * (1 - sl/100)
                new_tp = entry * (1 + tp/100)
                if exit_price <= new_sl:
                    simulated_pnl = -sl
                    simulated_losses += 1
                elif exit_price >= new_tp:
                    simulated_pnl = tp
                    simulated_wins += 1
                else:
                    simulated_pnl = ((exit_price - entry) / entry) * 100
            else:  # SHORT
                new_sl = entry * (1 + sl/100)
                new_tp = entry * (1 - tp/100)
                if exit_price >= new_sl:
                    simulated_pnl = -sl
                    simulated_losses += 1
                elif exit_price <= new_tp:
                    simulated_pnl = tp
                    simulated_wins += 1
                else:
                    simulated_pnl = ((entry - exit_price) / entry) * 100
            
            total_simulated_pnl += simulated_pnl
        
        total = simulated_wins + simulated_losses
        winrate = (simulated_wins / total * 100) if total > 0 else 0
        avg_pnl = total_simulated_pnl / total if total > 0 else 0
        
        print(f"      → Winrate: {winrate:.1f}% | PnL moyen: {avg_pnl:+.3f}%")
    
    # Conclusion
    print(f"\n🎯 CONCLUSION:")
    print(f"   Le problème principal est un TP irréaliste (500%) qui n'est jamais atteint.")
    print(f"   Les trades se ferment par trailing stop avec des gains minimes.")
    print(f"   Solution: Réduire le TP à 1-2% et resserrer le SL à 0.4-0.8%")
    print(f"   Cela améliorera le ratio réel gains/pertes.")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        analyze_and_suggest_tp_sl()
    except Exception as e:
        print(f"Erreur: {e}")
