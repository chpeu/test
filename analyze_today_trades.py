#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse des trades d'aujourd'hui et impact du bug
"""
import psycopg2
import pandas as pd
from datetime import datetime, timezone

def analyze_today_trades():
    """Analyser les trades d'aujourd'hui et l'impact du bug"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    query = """
        SELECT 
            id,
            symbol,
            direction,
            timestamp_entry,
            timestamp_exit,
            entry_price,
            exit_price,
            net_pnl_pct,
            net_pnl_usdt,
            pnl_pct,
            pnl_usdt,
            fees_usdt,
            slippage_usdt,
            duration_seconds,
            exit_reason,
            setup_score,
            is_live_trade,
            scan_log_id,
            opportunity_id,
            config_snapshot,
            -- Extraire config du JSON
            (config_snapshot::json->>'tp_percent')::float as tp_pct,
            (config_snapshot::json->>'sl_percent')::float as sl_pct,
            (config_snapshot::json->>'trailing_distance')::float as trailing_dist,
            (config_snapshot::json->>'trailing_trigger_pnl')::float as trailing_trigger,
            (config_snapshot::json->>'tp_sl_mode') as mode
        FROM trades 
        WHERE timestamp_entry >= CURRENT_DATE
        ORDER BY timestamp_entry DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("📊 ANALYSE DES TRADES D'AUJOURD'HUI")
    print("=" * 80)
    
    if df.empty:
        print("❌ Aucun trade aujourd'hui")
        return
    
    print(f"\n📈 STATISTIQUES GLOBALES:")
    print(f"   Total trades: {len(df)}")
    print(f"   Période: {df['timestamp_entry'].min()} → {df['timestamp_exit'].max()}")
    
    # Statistiques
    winning_trades = len(df[df['net_pnl_pct'] > 0])
    losing_trades = len(df[df['net_pnl_pct'] < 0])
    winrate = (winning_trades / len(df)) * 100 if len(df) > 0 else 0
    
    total_pnl = df['net_pnl_usdt'].sum()
    avg_win = df[df['net_pnl_pct'] > 0]['net_pnl_pct'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['net_pnl_pct'] < 0]['net_pnl_pct'].mean() if losing_trades > 0 else 0
    
    print(f"   Winrate: {winrate:.1f}% ({winning_trades} wins / {losing_trades} losses)")
    print(f"   PnL total: {total_pnl:.2f} USDT")
    print(f"   Gain moyen: {avg_win:.3f}%")
    print(f"   Perte moyenne: {avg_loss:.3f}%")
    
    # Détail des trades
    print(f"\n📋 DÉTAIL DES TRADES:")
    print("   Heure  | Symbole    | Direction | PnL %   | PnL USDT | Raison  | Durée | Scan_ID")
    print("   -------|------------|-----------|---------|----------|---------|-------|---------")
    
    for _, row in df.iterrows():
        time_str = row['timestamp_entry'].strftime('%H:%M')
        pnl_sign = "+" if row['net_pnl_pct'] >= 0 else ""
        duration_min = row['duration_seconds'] / 60 if row['duration_seconds'] else 0
        scan_id = str(row['scan_log_id'])[:8] if pd.notna(row['scan_log_id']) else "NULL"
        
        print(f"   {time_str} | {row['symbol']:10s} | {row['direction']:9s} | {pnl_sign}{row['net_pnl_pct']:6.2f}% | {row['net_pnl_usdt']:+8.2f} | {row['exit_reason']:7s} | {duration_min:5.0f}m | {scan_id}")
    
    # Vérification des IDs
    print(f"\n🔍 VÉRIFICATION DES IDS:")
    scan_ids_filled = len(df[df['scan_log_id'].notna()])
    opp_ids_filled = len(df[df['opportunity_id'].notna()])
    
    print(f"   Trades avec scan_log_id: {scan_ids_filled}/{len(df)} ({scan_ids_filled/len(df)*100:.0f}%)")
    print(f"   Trades avec opportunity_id: {opp_ids_filled}/{len(df)} ({opp_ids_filled/len(df)*100:.0f}%)")
    
    if scan_ids_filled < len(df):
        print(f"   ⚠️  {len(df) - scan_ids_filled} trades ont scan_log_id = NULL")
    
    # Configuration utilisée
    print(f"\n⚙️  CONFIGURATION UTILISÉE:")
    if not df.empty:
        first_row = df.iloc[0]
        print(f"   Mode: {first_row['mode'] or 'N/A'}")
        print(f"   TP: {first_row['tp_pct']:.2f}%")
        print(f"   SL: {first_row['sl_pct']:.2f}%")
        print(f"   Trailing Distance: {first_row['trailing_dist']:.2f}%")
        print(f"   Trailing Trigger: {first_row['trailing_trigger']:.2f}%")
    
    # Analyse par heure
    print(f"\n🕐 RÉPARTITION PAR HEURE:")
    df['hour'] = df['timestamp_entry'].dt.hour
    hourly = df.groupby('hour').agg({
        'net_pnl_pct': ['count', 'mean', 'sum'],
        'net_pnl_usdt': 'sum'
    }).round(3)
    
    for hour in df['hour'].unique():
        subset = df[df['hour'] == hour]
        count = len(subset)
        avg_pnl = subset['net_pnl_pct'].mean()
        total_usdt = subset['net_pnl_usdt'].sum()
        wins = len(subset[subset['net_pnl_pct'] > 0])
        wr = (wins / count) * 100
        
        print(f"   {hour:02d}h-{hour+1:02d}h: {count:2d} trades | PnL moy: {avg_pnl:+.3f}% | Total: {total_usdt:+.2f} USDT | WR: {wr:.0f}%")
    
    # Analyse des raisons de sortie
    print(f"\n📊 RAISONS DE SORTIE:")
    for reason in df['exit_reason'].unique():
        subset = df[df['exit_reason'] == reason]
        count = len(subset)
        avg_pnl = subset['net_pnl_pct'].mean()
        total_usdt = subset['net_pnl_usdt'].sum()
        wins = len(subset[subset['net_pnl_pct'] > 0])
        wr = (wins / count) * 100
        
        print(f"   {reason:15s}: {count:2d} trades | PnL moy: {avg_pnl:+.3f}% | Total: {total_usdt:+.2f} USDT | WR: {wr:.0f}%")
    
    # Impact du bug
    print(f"\n🐛 ANALYSE DE L'IMPACT DU BUG:")
    print("-" * 50)
    
    # Heure de la correction (approximative)
    correction_time = datetime(2026, 1, 14, 18, 30, tzinfo=timezone.utc)
    
    trades_before_bug = df[df['timestamp_entry'] < correction_time]
    trades_after_fix = df[df['timestamp_entry'] >= correction_time]
    
    print(f"\n   Avant correction (avant 18:30):")
    print(f"      Trades: {len(trades_before_bug)}")
    if len(trades_before_bug) > 0:
        scan_before = len(trades_before_bug[trades_before_bug['scan_log_id'].notna()])
        print(f"      Avec scan_log_id: {scan_before}/{len(trades_before_bug)} ({scan_before/len(trades_before_bug)*100:.0f}%)")
    
    print(f"\n   Après correction (après 18:30):")
    print(f"      Trades: {len(trades_after_fix)}")
    if len(trades_after_fix) > 0:
        scan_after = len(trades_after_fix[trades_after_fix['scan_log_id'].notna()])
        print(f"      Avec scan_log_id: {scan_after}/{len(trades_after_fix)} ({scan_after/len(trades_after_fix)*100:.0f}%)")
    
    # Causes possibles du faible nombre de trades
    print(f"\n🔍 CAUSES POSSIBLES DU FAIBLE NOMBRE DE TRADES:")
    print("-" * 50)
    
    print(f"\n   1. CONFIGURATION TP/SL:")
    print(f"      - TP à {df.iloc[0]['tp_pct']:.1f}%: Plus restrictif qu'avant")
    print(f"      - SL à {df.iloc[0]['sl_pct']:.1f}%: Plus serré")
    print(f"      - Ratio: {df.iloc[0]['tp_pct']/df.iloc[0]['sl_pct']:.1f}")
    
    print(f"\n   2. CONDITIONS DE MARCHÉ:")
    print(f"      - Volatilité faible?")
    print(f"      - Pas de setups valides?")
    
    print(f"\n   3. SCANNER:")
    print(f"      - Filtres trop stricts?")
    print(f"      - ML filter bloquant?")
    
    print(f"\n   4. BUG:")
    print(f"      - Avant correction: Bot crashait peut-être")
    print(f"      - Après correction: Fonctionne mais peu de trades")
    
    # Recommandations
    print(f"\n💡 RECOMMANDATIONS:")
    print("-" * 50)
    
    if len(df) < 5:
        print(f"   1. Vérifier les logs du scanner pour voir les rejets")
        print(f"   2. Surveiller si des setups sont détectés mais non tradés")
        print(f"   3. Considérer assouplir les filtres si trop stricts")
        print(f"   4. Vérifier si le ML filter rejette trop de trades")
    
    print(f"\n🎯 CONCLUSION:")
    if total_pnl > 0:
        print(f"   ✅ PnL positif malgré peu de trades: {total_pnl:.2f} USDT")
    else:
        print(f"   ❌ PnL négatif: {total_pnl:.2f} USDT")
    
    if scan_ids_filled == len(df):
        print(f"   ✅ Bug corrigé: Tous les trades ont scan_log_id")
    else:
        print(f"   ⚠️  Bug peut-être encore présent: Certains trades sans scan_log_id")

if __name__ == '__main__':
    try:
        analyze_today_trades()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
