#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse des 30 derniers trades : PnL, inversion de signaux, et rentabilité
"""
import psycopg2
import pandas as pd
from datetime import datetime

def analyze_recent_trades():
    """Analyser les 30 derniers trades pour identifier les problèmes de rentabilité"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    conn.set_client_encoding('WIN1252')
    
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
            -- Extraire config_invert_signals du JSON config_snapshot
            (config_snapshot::json->>'invert_signals')::boolean as config_invert_signals
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        ORDER BY timestamp_exit DESC 
        LIMIT 30
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("📊 ANALYSE DES 30 DERNIERS TRADES")
    print("=" * 80)
    
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
    print(f"   Gain moyen: {avg_win:.2f}%")
    print(f"   Perte moyenne: {avg_loss:.2f}%")
    print(f"   Ratio Profit Factor: {(avg_win * winning_trades) / (abs(avg_loss) * losing_trades):.2f}" if avg_loss != 0 else "N/A")
    
    # Analyse par inversion de signaux
    print(f"\n🔄 ANALYSE PAR INVERSION DE SIGNAUX:")
    
    # Séparer les trades avec et sans inversion
    df['config_invert_signals'] = df['config_invert_signals'].fillna(False)
    inverted_trades = df[df['config_invert_signals'] == True]
    normal_trades = df[df['config_invert_signals'] == False]
    
    print(f"\n   📌 TRADES NORMAUX ({len(normal_trades)} trades):")
    if len(normal_trades) > 0:
        normal_wins = len(normal_trades[normal_trades['net_pnl_pct'] > 0])
        normal_winrate = (normal_wins / len(normal_trades)) * 100
        normal_pnl = normal_trades['net_pnl_usdt'].sum()
        normal_avg_win = normal_trades[normal_trades['net_pnl_pct'] > 0]['net_pnl_pct'].mean() if normal_wins > 0 else 0
        normal_avg_loss = normal_trades[normal_trades['net_pnl_pct'] < 0]['net_pnl_pct'].mean() if (len(normal_trades) - normal_wins) > 0 else 0
        
        print(f"      Winrate: {normal_winrate:.1f}%")
        print(f"      PnL total: {normal_pnl:.2f} USDT")
        print(f"      Gain moyen: {normal_avg_win:.2f}%")
        print(f"      Perte moyenne: {normal_avg_loss:.2f}%")
    
    print(f"\n   🔄 TRADES AVEC INVERSION ({len(inverted_trades)} trades):")
    if len(inverted_trades) > 0:
        inv_wins = len(inverted_trades[inverted_trades['net_pnl_pct'] > 0])
        inv_winrate = (inv_wins / len(inverted_trades)) * 100
        inv_pnl = inverted_trades['net_pnl_usdt'].sum()
        inv_avg_win = inverted_trades[inverted_trades['net_pnl_pct'] > 0]['net_pnl_pct'].mean() if inv_wins > 0 else 0
        inv_avg_loss = inverted_trades[inverted_trades['net_pnl_pct'] < 0]['net_pnl_pct'].mean() if (len(inverted_trades) - inv_wins) > 0 else 0
        
        print(f"      Winrate: {inv_winrate:.1f}%")
        print(f"      PnL total: {inv_pnl:.2f} USDT")
        print(f"      Gain moyen: {inv_avg_win:.2f}%")
        print(f"      Perte moyenne: {inv_avg_loss:.2f}%")
    
    # Analyse des plus grosses pertes
    print(f"\n💰 TOP 10 DES PLUS GROSSES PERTES:")
    worst_trades = df.nsmallest(10, 'net_pnl_pct')[['symbol', 'direction', 'net_pnl_pct', 'net_pnl_usdt', 'exit_reason', 'config_invert_signals']]
    for idx, row in worst_trades.iterrows():
        inv_mark = "🔄" if row['config_invert_signals'] else "📌"
        print(f"   {inv_mark} {row['symbol']:12s} {row['direction']:5s}: {row['net_pnl_pct']:6.2f}% ({row['net_pnl_usdt']:7.2f} USDT) - {row['exit_reason']}")
    
    # Analyse des plus gros gains
    print(f"\n🎯 TOP 10 DES PLUS GROS GAINS:")
    best_trades = df.nlargest(10, 'net_pnl_pct')[['symbol', 'direction', 'net_pnl_pct', 'net_pnl_usdt', 'exit_reason', 'config_invert_signals']]
    for idx, row in best_trades.iterrows():
        inv_mark = "🔄" if row['config_invert_signals'] else "📌"
        print(f"   {inv_mark} {row['symbol']:12s} {row['direction']:5s}: {row['net_pnl_pct']:6.2f}% ({row['net_pnl_usdt']:7.2f} USDT) - {row['exit_reason']}")
    
    # Analyse des raisons de sortie
    print(f"\n📋 ANALYSE PAR RAISON DE SORTIE:")
    exit_reasons = df['exit_reason'].value_counts()
    for reason, count in exit_reasons.items():
        subset = df[df['exit_reason'] == reason]
        avg_pnl = subset['net_pnl_pct'].mean()
        print(f"   {reason:20s}: {count:2d} trades (PnL moyen: {avg_pnl:+.2f}%)")
    
    # Analyse du Risk/Reward
    print(f"\n⚖️  ANALYSE RISK/REWARD:")
    risk_reward_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    print(f"   Ratio Gain/Perte moyen: {risk_reward_ratio:.2f}")
    print(f"   Recommandé: > 2.0 pour être rentable")
    
    # Distribution des PnL
    print(f"\n📊 DISTRIBUTION DES PnL:")
    bins = [-100, -2, -1, -0.5, 0, 0.5, 1, 2, 100]
    labels = ['<-2%', '-2% à -1%', '-1% à -0.5%', '-0.5% à 0%', '0% à 0.5%', '0.5% à 1%', '1% à 2%', '>2%']
    
    df['pnl_category'] = pd.cut(df['net_pnl_pct'], bins=bins, labels=labels)
    distribution = df['pnl_category'].value_counts().sort_index()
    
    for cat, count in distribution.items():
        pct = (count / total_trades) * 100
        print(f"   {cat:15s}: {count:2d} trades ({pct:5.1f}%)")
    
    # Conclusions
    print(f"\n🎯 CONCLUSIONS:")
    if total_pnl < 0:
        print(f"   ❌ PnL négatif: {total_pnl:.2f} USDT")
        if avg_loss < -1.0:
            print(f"   ⚠️  Les pertes sont trop grosses en moyenne ({avg_loss:.2f}%)")
        if risk_reward_ratio < 1.5:
            print(f"   ⚠️  Ratio Risk/Reward trop faible ({risk_reward_ratio:.2f})")
        if len(inverted_trades) > 0 and inverted_trades['net_pnl_usdt'].sum() < 0:
            inv_pnl = inverted_trades['net_pnl_usdt'].sum()
            print(f"   ⚠️  Les trades avec inversion perdent {inv_pnl:.2f} USDT")
    else:
        print(f"   ✅ PnL positif: {total_pnl:.2f} USDT")
    
    # Détail des derniers trades
    print(f"\n📋 DÉTAIL DES 10 DERNIERS TRADES:")
    recent = df.head(10)[['symbol', 'direction', 'net_pnl_pct', 'net_pnl_usdt', 'exit_reason', 'config_invert_signals']]
    for idx, row in recent.iterrows():
        inv_mark = "🔄" if row['config_invert_signals'] else "📌"
        pnl_sign = "+" if row['net_pnl_pct'] >= 0 else ""
        print(f"   {inv_mark} {row['symbol']:12s} {row['direction']:5s}: {pnl_sign}{row['net_pnl_pct']:6.2f}% ({row['net_pnl_usdt']:+7.2f} USDT) - {row['exit_reason']}")

if __name__ == '__main__':
    try:
        analyze_recent_trades()
    except Exception as e:
        print(f"Erreur: {e}")
