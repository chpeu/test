#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse des 13 derniers trades avec nouvelle configuration
"""
import psycopg2
import pandas as pd
from datetime import datetime

def analyze_last_13_trades():
    """Analyser les 13 derniers trades"""
    
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
            config_snapshot,
            -- Extraire config du JSON
            (config_snapshot::json->>'tp_percent')::float as tp_pct,
            (config_snapshot::json->>'sl_percent')::float as sl_pct,
            (config_snapshot::json->>'trailing_distance')::float as trailing_dist,
            (config_snapshot::json->>'trailing_trigger_pnl')::float as trailing_trigger,
            (config_snapshot::json->>'tp_sl_mode') as mode
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        ORDER BY timestamp_exit DESC 
        LIMIT 13
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("📊 ANALYSE DES 13 DERNIERS TRADES")
    print("=" * 80)
    print(f"Période: {df['timestamp_exit'].min()} → {df['timestamp_exit'].max()}")
    
    # Statistiques générales
    total_trades = len(df)
    winning_trades = len(df[df['net_pnl_pct'] > 0])
    losing_trades = len(df[df['net_pnl_pct'] < 0])
    winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    total_pnl = df['net_pnl_usdt'].sum()
    avg_win = df[df['net_pnl_pct'] > 0]['net_pnl_pct'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['net_pnl_pct'] < 0]['net_pnl_pct'].mean() if losing_trades > 0 else 0
    
    print(f"\n📈 STATISTIQUES GLOBALES:")
    print(f"   Total trades: {total_trades}")
    print(f"   Winrate: {winrate:.1f}% ({winning_trades} wins / {losing_trades} losses)")
    print(f"   PnL total: {total_pnl:.2f} USDT")
    print(f"   Gain moyen: {avg_win:.3f}%")
    print(f"   Perte moyenne: {avg_loss:.3f}%")
    
    if avg_loss != 0:
        profit_factor = (avg_win * winning_trades) / (abs(avg_loss) * losing_trades)
        print(f"   Profit Factor: {profit_factor:.3f}")
    
    # Configuration utilisée
    print(f"\n⚙️  CONFIGURATION UTILISÉE:")
    if not df.empty:
        first_row = df.iloc[0]
        print(f"   Mode: {first_row['mode'] or 'N/A'}")
        print(f"   TP: {first_row['tp_pct']:.2f}%")
        print(f"   SL: {first_row['sl_pct']:.2f}%")
        print(f"   Trailing Distance: {first_row['trailing_dist']:.2f}%")
        print(f"   Trailing Trigger: {first_row['trailing_trigger']:.2f}%")
    
    # Détail des trades
    print(f"\n📋 DÉTAIL DES TRADES:")
    print("   N° | Symbole    | Direction | PnL %   | PnL USDT | Raison  | Durée")
    print("   ---|------------|-----------|---------|----------|---------|------")
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        pnl_sign = "+" if row['net_pnl_pct'] >= 0 else ""
        duration_min = row['duration_seconds'] / 60 if row['duration_seconds'] else 0
        print(f"   {idx:2d} | {row['symbol']:10s} | {row['direction']:9s} | {pnl_sign}{row['net_pnl_pct']:6.2f}% | {row['net_pnl_usdt']:+8.2f} | {row['exit_reason']:7s} | {duration_min:4.0f}m")
    
    # Analyse par raison de sortie
    print(f"\n📊 ANALYSE PAR RAISON DE SORTIE:")
    exit_stats = df.groupby('exit_reason').agg({
        'net_pnl_pct': ['count', 'mean', 'sum'],
        'net_pnl_usdt': 'sum'
    }).round(3)
    
    for reason in df['exit_reason'].unique():
        subset = df[df['exit_reason'] == reason]
        count = len(subset)
        avg_pnl = subset['net_pnl_pct'].mean()
        total_usdt = subset['net_pnl_usdt'].sum()
        wins = len(subset[subset['net_pnl_pct'] > 0])
        wr = (wins / count) * 100
        
        print(f"   {reason:15s}: {count:2d} trades | PnL moy: {avg_pnl:+.3f}% | Total: {total_usdt:+.2f} USDT | WR: {wr:.0f}%")
    
    # Distribution des PnL
    print(f"\n📈 DISTRIBUTION DES PnL:")
    bins = [-100, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 100]
    labels = ['<-0.3%', '-0.3% à -0.2%', '-0.2% à -0.1%', '-0.1% à 0%', '0% à 0.1%', '0.1% à 0.2%', '0.2% à 0.3%', '>0.3%']
    
    df['pnl_category'] = pd.cut(df['net_pnl_pct'], bins=bins, labels=labels)
    distribution = df['pnl_category'].value_counts().sort_index()
    
    for cat, count in distribution.items():
        pct = (count / total_trades) * 100
        print(f"   {cat:15s}: {count:2d} trades ({pct:5.1f}%)")
    
    # Comparaison avec avant
    print(f"\n🔄 COMPARAISON AVEC LES 30 TRADES PRÉCÉDENTS:")
    print("   Période précédente: Winrate 63.3% | PnL: -0.18 USDT | Ratio: 0.23")
    print(f"   Période actuelle  : Winrate {winrate:.1f}% | PnL: {total_pnl:+.2f} USDT | Ratio: {(avg_win/abs(avg_loss)):.2f}" if avg_loss != 0 else "")
    
    # Conclusions
    print(f"\n🎯 CONCLUSIONS:")
    if total_pnl > 0:
        print(f"   ✅ PnL positif: {total_pnl:.2f} USDT")
        if avg_win > 0.5:
            print(f"   ✅ Gains moyens améliorés: {avg_win:.3f}%")
    else:
        print(f"   ❌ PnL négatif: {total_pnl:.2f} USDT")
        if avg_win < 0.3:
            print(f"   ⚠️  Gains moyens encore trop faibles: {avg_win:.3f}%")
    
    if winrate < 50:
        print(f"   ⚠️  Winrate en baisse: {winrate:.1f}% (normal avec TP plus large)")
    
    # Recommandations
    print(f"\n💡 RECOMMANDATIONS:")
    if avg_win < 0.5:
        print(f"   - Les gains sont encore trop petits, envisagez d'augmenter TP à 2.0%")
    if avg_loss < -0.25:
        print(f"   - Les pertes sont acceptables")
    if total_pnl > 0:
        print(f"   ✅ La configuration actuelle fonctionne mieux !")
    else:
        print(f"   - Continuez à tester avec plus de trades")

if __name__ == '__main__':
    try:
        analyze_last_13_trades()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
