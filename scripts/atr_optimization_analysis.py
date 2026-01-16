#!/usr/bin/env python3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
ATR TP/SL Optimization Analysis
===============================
1. Construit le dataset joint trades <-> trade_atr_metrics
2. Calcule un PnL% cohérent (net_pnl_usdt / size proxy)
3. Analyse exploratoire par régime de volatilité
4. Grid search sur multiplicateurs ATR (SL, TP, trailing, BE)
5. Produit les meilleurs paramètres + trade-offs
"""

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv
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
    """Charge le dataset joint trades + trade_atr_metrics"""
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
        t.timestamp_entry,
        t.timestamp_exit,
        t.partial_tp_profit,
        -- ATR Metrics
        m.entry_atr_1m,
        m.entry_atr_5m,
        m.entry_atr_pct_1m,
        m.entry_atr_pct_5m,
        m.param_atr_mult_sl,
        m.param_atr_mult_tp,
        m.param_trailing_trigger_mult,
        m.param_trailing_distance_mult,
        m.param_be_atr_mult,
        m.market_volatility_state,
        m.market_trend_state,
        m.entry_adx,
        m.calculated_sl_pct,
        m.calculated_tp_pct,
        m.be_triggered,
        m.trailing_activated,
        m.max_pnl_reached,
        m.min_pnl_reached,
        m.max_price_reached,
        m.min_price_reached,
        m.time_to_max_pnl_seconds,
        m.time_to_min_pnl_seconds,
        m.stagnation_detected,
        -- What-If scenarios
        m.pnl_if_no_be,
        m.pnl_if_no_trailing,
        m.pnl_if_fixed_tp,
        m.pnl_if_wider_sl,
        m.pnl_if_tighter_sl,
        m.pnl_if_wider_trailing,
        m.pnl_if_tighter_trailing,
        m.pnl_if_calme_params,
        m.pnl_if_normal_params,
        m.pnl_if_volatile_params,
        m.optimal_regime_retrospective,
        -- Session context
        m.session_market,
        m.hour_utc,
        m.day_of_week
    FROM trades t
    INNER JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR'
      AND t.timestamp_exit IS NOT NULL
      AND t.exit_price IS NOT NULL
    ORDER BY t.timestamp_exit DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df

def compute_consistent_pnl_pct(df):
    """
    Calcule un PnL% cohérent basé sur net_pnl_usdt / notional_entry
    Pour tenir compte des partial TPs, on utilise:
    - notional = size * entry_price (valeur notionnelle à l'entrée)
    - pnl_pct_computed = (net_pnl_usdt / notional) * 100 * leverage
    """
    df = df.copy()
    
    # size_usdt est déjà la valeur notionnelle en USDT
    # PnL% recomputé: net_pnl_usdt / size_usdt * 100 * leverage
    df['pnl_pct_computed'] = np.where(
        df['size_usdt'] > 0,
        (df['net_pnl_usdt'] / df['size_usdt']) * 100 * df['leverage_used'].fillna(1),
        df['pnl_pct']  # fallback
    )
    
    # Comparaison avec pnl_pct original
    df['pnl_diff'] = df['pnl_pct_computed'] - df['pnl_pct']
    
    return df

def analyze_by_regime(df):
    """Analyse des performances par régime de volatilité"""
    print("\n" + "="*70)
    print("ANALYSE PAR REGIME DE VOLATILITE")
    print("="*70)
    
    regimes = df['market_volatility_state'].dropna().unique()
    
    results = []
    for regime in sorted(regimes):
        subset = df[df['market_volatility_state'] == regime]
        n = len(subset)
        if n == 0:
            continue
            
        wins = (subset['net_pnl_usdt'] > 0).sum()
        wr = wins / n * 100
        total_pnl = subset['net_pnl_usdt'].sum()
        avg_pnl = subset['net_pnl_usdt'].mean()
        avg_pnl_pct = subset['pnl_pct_computed'].mean()
        
        # Params moyens utilisés
        avg_sl_mult = subset['param_atr_mult_sl'].mean()
        avg_tp_mult = subset['param_atr_mult_tp'].mean()
        avg_trailing_trigger = subset['param_trailing_trigger_mult'].mean()
        avg_be_mult = subset['param_be_atr_mult'].mean()
        
        # BE/Trailing activation rates
        be_rate = subset['be_triggered'].sum() / n * 100 if n > 0 else 0
        trailing_rate = subset['trailing_activated'].sum() / n * 100 if n > 0 else 0
        
        results.append({
            'regime': regime,
            'n_trades': n,
            'win_rate': wr,
            'total_pnl_usdt': total_pnl,
            'avg_pnl_usdt': avg_pnl,
            'avg_pnl_pct': avg_pnl_pct,
            'avg_sl_mult': avg_sl_mult,
            'avg_tp_mult': avg_tp_mult,
            'avg_trailing_trigger': avg_trailing_trigger,
            'avg_be_mult': avg_be_mult,
            'be_activation_pct': be_rate,
            'trailing_activation_pct': trailing_rate
        })
        
        print(f"\n[{regime}] n={n}")
        print(f"  Win Rate: {wr:.1f}% | Total PnL: {total_pnl:.2f} USDT | Avg: {avg_pnl:.4f} USDT ({avg_pnl_pct:.3f}%)")
        print(f"  Params: SL={avg_sl_mult:.2f}x, TP={avg_tp_mult:.2f}x, Trailing={avg_trailing_trigger:.2f}x, BE={avg_be_mult:.2f}x")
        print(f"  BE activated: {be_rate:.1f}% | Trailing activated: {trailing_rate:.1f}%")
    
    return pd.DataFrame(results)

def analyze_whatif_scenarios(df):
    """Analyse des scénarios What-If"""
    print("\n" + "="*70)
    print("ANALYSE WHAT-IF SCENARIOS")
    print("="*70)
    
    # Colonnes What-If disponibles
    whatif_cols = [
        ('pnl_if_no_be', 'Sans Break-Even'),
        ('pnl_if_no_trailing', 'Sans Trailing Stop'),
        ('pnl_if_fixed_tp', 'TP Fixe (pas trailing)'),
        ('pnl_if_wider_sl', 'SL +50% plus large'),
        ('pnl_if_tighter_sl', 'SL -25% plus serré'),
        ('pnl_if_wider_trailing', 'Trailing +50% plus large'),
        ('pnl_if_tighter_trailing', 'Trailing -25% plus serré'),
    ]
    
    # PnL réel moyen
    actual_avg = df['pnl_pct_computed'].mean()
    print(f"\nPnL% moyen réel: {actual_avg:.4f}%")
    
    results = []
    for col, label in whatif_cols:
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                avg = valid.mean()
                diff = avg - actual_avg
                n = len(valid)
                results.append({
                    'scenario': label,
                    'avg_pnl_pct': avg,
                    'diff_vs_actual': diff,
                    'n_samples': n
                })
                sign = '+' if diff > 0 else ''
                print(f"  {label}: {avg:.4f}% ({sign}{diff:.4f}%) [n={n}]")
    
    # Analyse par régime optimal rétrospectif
    print("\n--- Régime Optimal Rétrospectif ---")
    if 'optimal_regime_retrospective' in df.columns:
        opt_regime = df['optimal_regime_retrospective'].value_counts()
        for regime, count in opt_regime.items():
            pct = count / len(df) * 100
            print(f"  {regime}: {count} trades ({pct:.1f}%)")
    
    return pd.DataFrame(results)

def analyze_exit_reasons(df):
    """Analyse des raisons de sortie"""
    print("\n" + "="*70)
    print("ANALYSE PAR RAISON DE SORTIE")
    print("="*70)
    
    exit_stats = df.groupby('exit_reason').agg({
        'trade_id': 'count',
        'net_pnl_usdt': ['sum', 'mean'],
        'pnl_pct_computed': 'mean'
    }).round(4)
    
    exit_stats.columns = ['n_trades', 'total_pnl', 'avg_pnl_usdt', 'avg_pnl_pct']
    exit_stats = exit_stats.sort_values('n_trades', ascending=False)
    
    print(exit_stats.to_string())
    
    return exit_stats

def analyze_sl_tp_distances(df):
    """Analyse des distances SL/TP calculées vs atteintes"""
    print("\n" + "="*70)
    print("ANALYSE DISTANCES SL/TP")
    print("="*70)
    
    # Filtrer les lignes avec des valeurs valides
    valid = df[(df['calculated_sl_pct'].notna()) & (df['calculated_sl_pct'] > 0)]
    
    if len(valid) > 0:
        print(f"\nTrades avec SL% valide: {len(valid)}")
        print(f"  SL% moyen calculé: {valid['calculated_sl_pct'].mean():.3f}%")
        print(f"  TP% moyen calculé: {valid['calculated_tp_pct'].mean():.3f}%")
        print(f"  Min PnL atteint (drawdown): {valid['min_pnl_reached'].mean():.3f}%")
        print(f"  Max PnL atteint (MFE): {valid['max_pnl_reached'].mean():.3f}%")
        
        # Ratio SL touché vs MFE atteint
        sl_hit = (valid['exit_reason'].isin(['SL', 'SL_EXCHANGE'])).sum()
        tp_hit = (valid['exit_reason'] == 'TP').sum()
        trailing_hit = (valid['exit_reason'] == 'TS').sum()
        
        print(f"\n  Sorties SL: {sl_hit} ({sl_hit/len(valid)*100:.1f}%)")
        print(f"  Sorties TP: {tp_hit} ({tp_hit/len(valid)*100:.1f}%)")
        print(f"  Sorties Trailing: {trailing_hit} ({trailing_hit/len(valid)*100:.1f}%)")
        
        # MFE vs exit - opportunités manquées
        mfe_vs_exit = valid['max_pnl_reached'] - valid['pnl_pct_computed']
        print(f"\n  MFE - PnL final (opportunité manquée moyenne): {mfe_vs_exit.mean():.3f}%")

def grid_search_simulation(df):
    """
    Simule différentes combinaisons de paramètres ATR basées sur les données What-If
    et les métriques max/min PnL atteints.
    """
    print("\n" + "="*70)
    print("GRID SEARCH SIMULATION (basée sur What-If)")
    print("="*70)
    
    # Utilise les colonnes What-If pour estimer l'impact des changements
    scenarios = {
        'Actuel': df['pnl_pct_computed'],
        'Sans BE': df['pnl_if_no_be'],
        'Sans Trailing': df['pnl_if_no_trailing'],
        'TP Fixe': df['pnl_if_fixed_tp'],
        'SL Large (+50%)': df['pnl_if_wider_sl'],
        'SL Serré (-25%)': df['pnl_if_tighter_sl'],
        'Trailing Large': df['pnl_if_wider_trailing'],
        'Trailing Serré': df['pnl_if_tighter_trailing'],
    }
    
    # Scénarios par régime
    regime_scenarios = {
        'Params CALME': df['pnl_if_calme_params'],
        'Params NORMAL': df['pnl_if_normal_params'],
        'Params VOLATILE': df['pnl_if_volatile_params'],
    }
    
    print("\n--- Comparaison Globale ---")
    results = []
    for name, pnl_series in scenarios.items():
        valid = pnl_series.dropna()
        if len(valid) > 10:
            avg = valid.mean()
            total = valid.sum()
            wr = (valid > 0).sum() / len(valid) * 100
            results.append({
                'scenario': name,
                'avg_pnl_pct': avg,
                'total_pnl_pct': total,
                'win_rate': wr,
                'n': len(valid)
            })
    
    results_df = pd.DataFrame(results).sort_values('avg_pnl_pct', ascending=False)
    print(results_df.to_string(index=False))
    
    print("\n--- Scénarios par Régime ---")
    regime_results = []
    for name, pnl_series in regime_scenarios.items():
        valid = pnl_series.dropna()
        if len(valid) > 10:
            avg = valid.mean()
            total = valid.sum()
            wr = (valid > 0).sum() / len(valid) * 100
            regime_results.append({
                'scenario': name,
                'avg_pnl_pct': avg,
                'total_pnl_pct': total,
                'win_rate': wr,
                'n': len(valid)
            })
    
    if regime_results:
        regime_df = pd.DataFrame(regime_results).sort_values('avg_pnl_pct', ascending=False)
        print(regime_df.to_string(index=False))
    
    return results_df

def generate_recommendations(df, regime_stats, whatif_stats):
    """Génère des recommandations basées sur l'analyse"""
    print("\n" + "="*70)
    print("RECOMMANDATIONS")
    print("="*70)
    
    # 1. Régime le plus performant
    if len(regime_stats) > 0:
        best_regime = regime_stats.loc[regime_stats['avg_pnl_pct'].idxmax()]
        print(f"\n1. MEILLEUR REGIME: {best_regime['regime']}")
        print(f"   Win Rate: {best_regime['win_rate']:.1f}%, Avg PnL: {best_regime['avg_pnl_pct']:.4f}%")
        print(f"   Params utilisés: SL={best_regime['avg_sl_mult']:.2f}x, TP={best_regime['avg_tp_mult']:.2f}x")
    
    # 2. Impact du Break-Even
    if 'pnl_if_no_be' in df.columns:
        actual = df['pnl_pct_computed'].mean()
        no_be = df['pnl_if_no_be'].dropna().mean()
        be_impact = actual - no_be
        if be_impact > 0:
            print(f"\n2. BREAK-EVEN: +{be_impact:.4f}% d'amélioration (GARDER)")
        else:
            print(f"\n2. BREAK-EVEN: {be_impact:.4f}% d'impact (RECONSIDERER)")
    
    # 3. Impact du Trailing Stop
    if 'pnl_if_no_trailing' in df.columns:
        no_ts = df['pnl_if_no_trailing'].dropna().mean()
        ts_impact = actual - no_ts
        if ts_impact > 0:
            print(f"\n3. TRAILING STOP: +{ts_impact:.4f}% d'amélioration (GARDER)")
        else:
            print(f"\n3. TRAILING STOP: {ts_impact:.4f}% d'impact (RECONSIDERER)")
    
    # 4. SL optimal
    if 'pnl_if_wider_sl' in df.columns and 'pnl_if_tighter_sl' in df.columns:
        wider = df['pnl_if_wider_sl'].dropna().mean()
        tighter = df['pnl_if_tighter_sl'].dropna().mean()
        if wider > actual and wider > tighter:
            print(f"\n4. SL RECOMMANDE: ELARGIR (+50%) -> +{wider-actual:.4f}%")
        elif tighter > actual:
            print(f"\n4. SL RECOMMANDE: RESSERRER (-25%) -> +{tighter-actual:.4f}%")
        else:
            print(f"\n4. SL ACTUEL: Optimal ou proche")
    
    # 5. Sessions les plus rentables
    if 'session_market' in df.columns:
        session_stats = df.groupby('session_market')['pnl_pct_computed'].agg(['mean', 'count'])
        session_stats = session_stats[session_stats['count'] >= 20].sort_values('mean', ascending=False)
        if len(session_stats) > 0:
            print(f"\n5. MEILLEURES SESSIONS:")
            for sess, row in session_stats.head(3).iterrows():
                print(f"   {sess}: {row['mean']:.4f}% avg (n={int(row['count'])})")

def main():
    print("="*70)
    print("ATR TP/SL OPTIMIZATION ANALYSIS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    # 1. Charger le dataset
    print("\n[1/7] Chargement du dataset...")
    df = load_dataset()
    print(f"   {len(df)} trades ATR avec métriques chargés")
    
    # 2. Calculer PnL% cohérent
    print("\n[2/7] Calcul du PnL% cohérent...")
    df = compute_consistent_pnl_pct(df)
    print(f"   PnL% original moyen: {df['pnl_pct'].mean():.4f}%")
    print(f"   PnL% recomputé moyen: {df['pnl_pct_computed'].mean():.4f}%")
    print(f"   Différence moyenne: {df['pnl_diff'].mean():.4f}%")
    
    # 3. Analyse par régime
    print("\n[3/7] Analyse par régime...")
    regime_stats = analyze_by_regime(df)
    
    # 4. Analyse What-If
    print("\n[4/7] Analyse What-If...")
    whatif_stats = analyze_whatif_scenarios(df)
    
    # 5. Analyse exit reasons
    print("\n[5/7] Analyse raisons de sortie...")
    analyze_exit_reasons(df)
    
    # 6. Analyse distances SL/TP
    print("\n[6/7] Analyse distances SL/TP...")
    analyze_sl_tp_distances(df)
    
    # 7. Grid search simulation
    print("\n[7/7] Grid search simulation...")
    grid_results = grid_search_simulation(df)
    
    # Recommandations
    generate_recommendations(df, regime_stats, whatif_stats)
    
    # Export CSV pour analyse approfondie
    output_path = os.path.join(os.path.dirname(__file__), 'atr_optimization_dataset.csv')
    df.to_csv(output_path, index=False)
    print(f"\n\nDataset exporté: {output_path}")
    
    print("\n" + "="*70)
    print("ANALYSE TERMINEE")
    print("="*70)
    
    return df, regime_stats, grid_results

if __name__ == "__main__":
    main()
