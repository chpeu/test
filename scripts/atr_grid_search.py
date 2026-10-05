#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
ATR Grid Search Optimization
============================
Simule différentes combinaisons de multiplicateurs ATR pour trouver les paramètres optimaux.
Utilise les données max_pnl_reached/min_pnl_reached pour simuler les issues de trades.
"""

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv
from itertools import product
from datetime import datetime

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def load_dataset():
    """Charge le dataset avec les données nécessaires pour la simulation"""
    conn = get_connection()
    
    query = """
    SELECT 
        t.id as trade_id,
        t.symbol,
        t.direction,
        t.entry_price,
        t.exit_price,
        t.size_usdt,
        t.leverage_used,
        t.pnl_pct,
        t.net_pnl_usdt,
        t.exit_reason,
        -- ATR Metrics
        m.entry_atr_pct_1m,
        m.entry_atr_pct_5m,
        m.param_atr_mult_sl,
        m.param_atr_mult_tp,
        m.param_trailing_trigger_mult,
        m.param_trailing_distance_mult,
        m.param_be_atr_mult,
        m.market_volatility_state,
        m.calculated_sl_pct,
        m.calculated_tp_pct,
        m.max_pnl_reached,
        m.min_pnl_reached,
        m.max_price_reached,
        m.min_price_reached,
        m.session_market
    FROM trades t
    INNER JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR'
      AND t.timestamp_exit IS NOT NULL
      AND m.max_pnl_reached IS NOT NULL
      AND m.min_pnl_reached IS NOT NULL
      AND m.entry_atr_pct_1m IS NOT NULL
    ORDER BY t.timestamp_exit DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def simulate_trade_outcome(row, sl_mult, tp_mult, be_mult=None, trailing_trigger_mult=None, trailing_distance_mult=None):
    """
    Simule l'issue d'un trade avec des multiplicateurs ATR donnés.
    
    Returns: simulated PnL %
    """
    atr_pct = row['entry_atr_pct_1m']
    if pd.isna(atr_pct) or atr_pct <= 0:
        atr_pct = row['entry_atr_pct_5m']
    if pd.isna(atr_pct) or atr_pct <= 0:
        return row['pnl_pct']  # fallback
    
    # Calcul SL/TP en % basé sur ATR
    sl_pct = atr_pct * sl_mult
    tp_pct = atr_pct * tp_mult
    
    max_pnl = row['max_pnl_reached']
    min_pnl = row['min_pnl_reached']
    
    # Simulation simplifiée:
    # - Si min_pnl <= -sl_pct : SL touché -> pnl = -sl_pct
    # - Si max_pnl >= tp_pct : TP touché -> pnl = +tp_pct
    # - Sinon : on garde le PnL réel (autres sorties)
    
    # On doit déterminer ce qui arrive EN PREMIER (SL ou TP)
    # Approximation: si le drawdown max est plus extrême que le gain max relatif au seuil
    
    sl_hit = min_pnl <= -sl_pct
    tp_hit = max_pnl >= tp_pct
    
    if sl_hit and tp_hit:
        # Les deux auraient été touchés, on prend le plus probable
        # Heuristique: si |min_pnl| / sl_pct > max_pnl / tp_pct, SL probablement premier
        sl_ratio = abs(min_pnl) / sl_pct if sl_pct > 0 else 0
        tp_ratio = max_pnl / tp_pct if tp_pct > 0 else 0
        if sl_ratio > tp_ratio:
            return -sl_pct
        else:
            return tp_pct
    elif sl_hit:
        return -sl_pct
    elif tp_hit:
        return tp_pct
    else:
        # Ni SL ni TP touché avec ces params, retourne PnL réel (autre sortie)
        return row['pnl_pct']

def run_grid_search(df, regime=None):
    """
    Grid search sur les multiplicateurs ATR.
    """
    if regime:
        subset = df[df['market_volatility_state'] == regime].copy()
        print(f"\n--- Grid Search pour régime {regime} (n={len(subset)}) ---")
    else:
        subset = df.copy()
        print(f"\n--- Grid Search Global (n={len(subset)}) ---")
    
    if len(subset) < 50:
        print("   Pas assez de trades pour une analyse significative")
        return None
    
    # Grille de paramètres
    sl_mults = [0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
    tp_mults = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    
    results = []
    
    for sl_mult, tp_mult in product(sl_mults, tp_mults):
        # Simuler tous les trades
        sim_pnls = subset.apply(
            lambda row: simulate_trade_outcome(row, sl_mult, tp_mult), 
            axis=1
        )
        
        avg_pnl = sim_pnls.mean()
        total_pnl = sim_pnls.sum()
        win_rate = (sim_pnls > 0).sum() / len(sim_pnls) * 100
        
        # Profit Factor
        gains = sim_pnls[sim_pnls > 0].sum()
        losses = abs(sim_pnls[sim_pnls < 0].sum())
        pf = gains / losses if losses > 0 else float('inf')
        
        results.append({
            'sl_mult': sl_mult,
            'tp_mult': tp_mult,
            'avg_pnl_pct': avg_pnl,
            'total_pnl_pct': total_pnl,
            'win_rate': win_rate,
            'profit_factor': pf,
            'n_trades': len(subset)
        })
    
    results_df = pd.DataFrame(results)
    
    # Top 5 par avg_pnl
    print("\nTop 5 par PnL moyen:")
    top5 = results_df.nlargest(5, 'avg_pnl_pct')
    for _, row in top5.iterrows():
        print(f"  SL={row['sl_mult']:.1f}x TP={row['tp_mult']:.1f}x -> "
              f"Avg: {row['avg_pnl_pct']:.4f}% | WR: {row['win_rate']:.1f}% | PF: {row['profit_factor']:.2f}")
    
    # Top 5 par Profit Factor (avec WR > 40%)
    print("\nTop 5 par Profit Factor (WR > 40%):")
    filtered = results_df[results_df['win_rate'] > 40]
    if len(filtered) > 0:
        top5_pf = filtered.nlargest(5, 'profit_factor')
        for _, row in top5_pf.iterrows():
            print(f"  SL={row['sl_mult']:.1f}x TP={row['tp_mult']:.1f}x -> "
                  f"Avg: {row['avg_pnl_pct']:.4f}% | WR: {row['win_rate']:.1f}% | PF: {row['profit_factor']:.2f}")
    
    return results_df

def compare_current_vs_optimal(df):
    """Compare la config actuelle vs optimale"""
    print("\n" + "="*70)
    print("COMPARAISON ACTUEL vs OPTIMAL")
    print("="*70)
    
    # PnL actuel
    actual_avg = df['pnl_pct'].mean()
    actual_total = df['pnl_pct'].sum()
    actual_wr = (df['pnl_pct'] > 0).sum() / len(df) * 100
    
    print(f"\nConfiguration ACTUELLE:")
    print(f"  Avg PnL: {actual_avg:.4f}%")
    print(f"  Total PnL: {actual_total:.2f}%")
    print(f"  Win Rate: {actual_wr:.1f}%")
    
    # Params moyens actuels
    avg_sl = df['param_atr_mult_sl'].mean()
    avg_tp = df['param_atr_mult_tp'].mean()
    print(f"  Params moyens: SL={avg_sl:.2f}x, TP={avg_tp:.2f}x")

def generate_optimal_config(all_results, regime_results):
    """Génère la configuration optimale recommandée"""
    print("\n" + "="*70)
    print("CONFIGURATION OPTIMALE RECOMMANDEE")
    print("="*70)
    
    # Global
    if all_results is not None and len(all_results) > 0:
        best_global = all_results.nlargest(1, 'avg_pnl_pct').iloc[0]
        print(f"\nGLOBAL (fallback):")
        print(f"  SL: {best_global['sl_mult']:.1f}x ATR")
        print(f"  TP: {best_global['tp_mult']:.1f}x ATR")
        print(f"  Expected: {best_global['avg_pnl_pct']:.4f}% avg, {best_global['win_rate']:.1f}% WR")
    
    # Par régime
    print("\nPAR REGIME:")
    for regime, results in regime_results.items():
        if results is not None and len(results) > 0:
            best = results.nlargest(1, 'avg_pnl_pct').iloc[0]
            print(f"\n  [{regime}]")
            print(f"    SL: {best['sl_mult']:.1f}x ATR")
            print(f"    TP: {best['tp_mult']:.1f}x ATR")
            print(f"    Expected: {best['avg_pnl_pct']:.4f}% avg, {best['win_rate']:.1f}% WR, PF={best['profit_factor']:.2f}")

def main():
    print("="*70)
    print("ATR GRID SEARCH OPTIMIZATION")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # Charger les données
    print("\n[1/4] Chargement du dataset...")
    df = load_dataset()
    print(f"   {len(df)} trades avec données complètes")
    
    # Stats actuelles
    print("\n[2/4] Analyse configuration actuelle...")
    compare_current_vs_optimal(df)
    
    # Grid search global
    print("\n[3/4] Grid Search...")
    all_results = run_grid_search(df)
    
    # Grid search par régime
    regime_results = {}
    for regime in ['LOW', 'MEDIUM', 'HIGH']:
        regime_results[regime] = run_grid_search(df, regime)
    
    # Recommandations finales
    print("\n[4/4] Génération des recommandations...")
    generate_optimal_config(all_results, regime_results)
    
    # Export des résultats
    if all_results is not None:
        output_path = os.path.join(os.path.dirname(__file__), 'atr_grid_search_results.csv')
        all_results.to_csv(output_path, index=False)
        print(f"\nRésultats exportés: {output_path}")
    
    print("\n" + "="*70)
    print("GRID SEARCH TERMINE")
    print("="*70)

if __name__ == "__main__":
    main()
