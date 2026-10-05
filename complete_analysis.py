#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse complète de toutes les données de trading dans la base PostgreSQL
"""
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def complete_analysis():
    """Analyse complète de toutes les données de trading"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    print("📊 ANALYSE COMPLÈTE DE LA BASE DE DONNÉES TRADING")
    print("=" * 80)
    
    # 1. Statistiques générales
    print("\n1️⃣ STATISTIQUES GLOBALES (TOUTES DONNÉES):")
    print("-" * 50)
    
    df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_trades,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as winning_trades,
            COUNT(CASE WHEN net_pnl_pct < 0 THEN 1 END) as losing_trades,
            SUM(net_pnl_usdt) as total_pnl_usdt,
            AVG(net_pnl_pct) as avg_pnl_pct,
            MAX(net_pnl_pct) as best_trade_pct,
            MIN(net_pnl_pct) as worst_trade_pct,
            AVG(CASE WHEN net_pnl_pct > 0 THEN net_pnl_pct END) as avg_win_pct,
            AVG(CASE WHEN net_pnl_pct < 0 THEN net_pnl_pct END) as avg_loss_pct,
            MIN(timestamp_entry) as first_trade,
            MAX(timestamp_entry) as last_trade
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
    """, conn)
    
    stats = df.iloc[0]
    winrate = (stats['winning_trades'] / stats['total_trades']) * 100
    profit_factor = (stats['avg_win_pct'] * stats['winning_trades']) / (abs(stats['avg_loss_pct']) * stats['losing_trades']) if stats['avg_loss_pct'] != 0 else 0
    
    print(f"   Total trades: {stats['total_trades']:,}")
    print(f"   Période: {stats['first_trade']} → {stats['last_trade']}")
    print(f"   Winrate: {winrate:.2f}%")
    print(f"   PnL total: {stats['total_pnl_usdt']:.2f} USDT")
    print(f"   Gain moyen: {stats['avg_win_pct']:.3f}%")
    print(f"   Perte moyenne: {stats['avg_loss_pct']:.3f}%")
    print(f"   Profit Factor: {profit_factor:.3f}")
    print(f"   Meilleur trade: +{stats['best_trade_pct']:.2f}%")
    print(f"   Pire trade: {stats['worst_trade_pct']:.2f}%")
    
    # 2. Évolution du PnL dans le temps
    print("\n2️⃣ ÉVOLUTION DU PnL (PAR MOIS):")
    print("-" * 50)
    
    monthly = pd.read_sql("""
        SELECT 
            DATE_TRUNC('month', timestamp_exit) as month,
            COUNT(*) as trades,
            SUM(net_pnl_usdt) as pnl_usdt,
            AVG(net_pnl_pct) as avg_pct,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins,
            ROUND(COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) * 100.0 / COUNT(*), 1) as winrate
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        GROUP BY DATE_TRUNC('month', timestamp_exit)
        ORDER BY month DESC
        LIMIT 12
    """, conn)
    
    for _, row in monthly.iterrows():
        month_str = str(row['month'])[:7]  # Convertir en string puis extraire
        print(f"   {month_str}: {row['trades']:3d} trades | PnL: {row['pnl_usdt']:7.2f} USDT | Winrate: {row['winrate']:5.1f}%")
    
    # 3. Analyse par configuration TP/SL
    print("\n3️⃣ PERFORMANCE PAR CONFIGURATION TP/SL:")
    print("-" * 50)
    
    configs = pd.read_sql("""
        SELECT 
            tp_sl_mode,
            COUNT(*) as trades,
            AVG(net_pnl_pct) as avg_pnl,
            STDDEV(net_pnl_pct) as std_pnl,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins,
            -- PostgreSQL utilise ROUND(numeric, integer) pas ROUND(double, integer)
            AVG(CASE WHEN net_pnl_pct > 0 THEN net_pnl_pct END) as avg_win,
            AVG(CASE WHEN net_pnl_pct < 0 THEN net_pnl_pct END) as avg_loss,
            -- Extraire configs du JSON
            (config_snapshot::json->>'tp_percent')::float as tp_pct,
            (config_snapshot::json->>'sl_percent')::float as sl_pct,
            (config_snapshot::json->>'atr_mult_tp')::float as atr_tp,
            (config_snapshot::json->>'atr_mult_sl')::float as atr_sl
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        AND tp_sl_mode IS NOT NULL
        GROUP BY tp_sl_mode, tp_pct, sl_pct, atr_tp, atr_sl
        HAVING COUNT(*) > 10
        ORDER BY trades DESC
    """, conn)
    
    for _, row in configs.iterrows():
        mode = row['tp_sl_mode']
        if mode == 'ATR':
            config_str = f"ATR TP:{row['atr_tp']}x SL:{row['atr_sl']}x"
        else:
            config_str = f"TP:{row['tp_pct']:.1f}% SL:{row['sl_pct']:.1f}%"
        
        wr = (row['wins'] / row['trades']) * 100
        print(f"   {mode:6s} ({config_str}): {row['trades']:4d} trades | PnL: {row['avg_pnl']:+.3f}% | WR: {wr:.1f}%")
    
    # 4. Top paires performantes
    print("\n4️⃣ TOP 20 PAIRES (PAR NOMBRE DE TRADES):")
    print("-" * 50)
    
    pairs = pd.read_sql("""
        SELECT 
            symbol,
            COUNT(*) as trades,
            SUM(net_pnl_usdt) as total_pnl,
            AVG(net_pnl_pct) as avg_pct,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        GROUP BY symbol
        HAVING COUNT(*) >= 10
        ORDER BY trades DESC
        LIMIT 20
    """, conn)
    
    print("   Symbole      | Trades | PnL USDT | Avg %  | WR")
    print("   ------------|--------|----------|--------|----")
    for _, row in pairs.iterrows():
        wr = (row['wins'] / row['trades']) * 100
        print(f"   {row['symbol']:12s} | {row['trades']:6d} | {row['total_pnl']:8.2f} | {row['avg_pct']:+6.3f}% | {wr:.1f}%")
    
    # 5. Analyse des raisons de sortie
    print("\n5️⃣ ANALYSE DÉTAILLÉE DES RAISONS DE SORTIE:")
    print("-" * 50)
    
    exits = pd.read_sql("""
        SELECT 
            exit_reason,
            COUNT(*) as trades,
            SUM(net_pnl_usdt) as total_pnl,
            AVG(net_pnl_pct) as avg_pct,
            STDDEV(net_pnl_pct) as std_pct,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins,
            AVG(CASE WHEN net_pnl_pct > 0 THEN net_pnl_pct END) as avg_win,
            AVG(CASE WHEN net_pnl_pct < 0 THEN net_pnl_pct END) as avg_loss,
            AVG(duration_seconds) as avg_duration
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        GROUP BY exit_reason
        ORDER BY trades DESC
    """, conn)
    
    for _, row in exits.iterrows():
        wr = (row['wins'] / row['trades']) * 100
        print(f"\n   {row['exit_reason']:20s}:")
        print(f"      Trades: {row['trades']:3d} | PnL: {row['total_pnl']:7.2f} USDT ({row['avg_pct']:+.3f}%)")
        print(f"      Winrate: {wr:.1f}% | Gain moy: {row['avg_win']:+.3f}% | Perte moy: {row['avg_loss']:+.3f}%")
        print(f"      Durée moy: {row['avg_duration']/60:.1f} min")
    
    # 6. Impact du trailing stop
    print("\n6️⃣ IMPACT DU TRAILING STOP:")
    print("-" * 50)
    
    trailing = pd.read_sql("""
        SELECT 
            trailing_stop_activated,
            COUNT(*) as trades,
            AVG(net_pnl_pct) as avg_pct,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins,
            AVG(CASE WHEN net_pnl_pct > 0 THEN net_pnl_pct END) as avg_win,
            AVG(CASE WHEN net_pnl_pct < 0 THEN net_pnl_pct END) as avg_loss
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        AND trailing_stop_activated IS NOT NULL
        GROUP BY trailing_stop_activated
    """, conn)
    
    for _, row in trailing.iterrows():
        status = "Activé" if row['trailing_stop_activated'] else "Désactivé"
        wr = (row['wins'] / row['trades']) * 100
        print(f"   Trailing {status:10s}: {row['trades']:4d} trades | PnL: {row['avg_pct']:+.3f}% | WR: {wr:.1f}%")
        print(f"                     Gain moy: {row['avg_win']:+.3f}% | Perte moy: {row['avg_loss']:+.3f}%")
    
    # 7. Analyse par heure de la journée
    print("\n7️⃣ PERFORMANCE PAR HEURE DE LA JOURNÉE (UTC):")
    print("-" * 50)
    
    hourly = pd.read_sql("""
        SELECT 
            EXTRACT(HOUR FROM timestamp_entry) as hour,
            COUNT(*) as trades,
            AVG(net_pnl_pct) as avg_pct,
            COUNT(CASE WHEN net_pnl_pct > 0 THEN 1 END) as wins
        FROM trades 
        WHERE timestamp_exit IS NOT NULL
        GROUP BY EXTRACT(HOUR FROM timestamp_entry)
        ORDER BY hour
    """, conn)
    
    print("   Heure | Trades | PnL moyen | Winrate")
    print("   ------|--------|-----------|--------")
    for _, row in hourly.iterrows():
        hour = int(row['hour'])
        wr = (row['wins'] / row['trades']) * 100
        print(f"   {hour:02d}h   | {int(row['trades']):6d} | {row['avg_pct']:+9.3f}% | {wr:6.1f}%")
    
    # 8. Recommandations basées sur les données
    print("\n8️⃣ RECOMMANDATIONS BASÉES SUR L'ANALYSE COMPLÈTE:")
    print("-" * 50)
    
    # Meilleure configuration identifiée
    best_config = configs.loc[configs['avg_pnl'].idxmax()] if not configs.empty else None
    if best_config is not None:
        print(f"\n   🎯 MEILLEURE CONFIGURATION IDENTIFIÉE:")
        if best_config['tp_sl_mode'] == 'ATR':
            print(f"      Mode: ATR avec TP={best_config['atr_tp']}x, SL={best_config['atr_sl']}x")
        else:
            print(f"      Mode: FIXE avec TP={best_config['tp_pct']:.1f}%, SL={best_config['sl_pct']:.1f}%")
        print(f"      Performance: PnL moyen {best_config['avg_pnl']:+.3f}%")
    
    # Pires paires
    worst_pairs = pairs[pairs['total_pnl'] < 0].sort_values('total_pnl').head(5)
    if not worst_pairs.empty:
        print(f"\n   ❌ PAIRES À ÉVITER (pertes les plus importantes):")
        for _, row in worst_pairs.iterrows():
            print(f"      {row['symbol']:12s}: {row['total_pnl']:7.2f} USDT de perte")
    
    # Meilleures heures
    best_hours = hourly[hourly['avg_pct'] > 0].sort_values('avg_pct', ascending=False).head(3)
    if not best_hours.empty:
        print(f"\n   ⏰ MEILLEURES HEURES DE TRADING:")
        for _, row in best_hours.iterrows():
            print(f"      {int(row['hour']):02d}h: PnL moyen {row['avg_pct']:+.3f}%")
    
    # Conclusion finale
    print(f"\n🎯 CONCLUSION FINALE:")
    if stats['total_pnl_usdt'] < 0:
        print(f"   ❌ Le bot est globalement perdant de {abs(stats['total_pnl_usdt']):.2f} USDT")
        if profit_factor < 1:
            print(f"   ⚠️  Le Profit Factor ({profit_factor:.2f}) est critique : les gains ne compensent pas les pertes")
        print(f"\n   🔧 ACTIONS IMMÉDIATES RECOMMANDÉES:")
        print(f"      1. Réduire le trailing ou le désactiver")
        print(f"      2. Augmenter le TP cible de 0.5% à 1.0%")
        print(f"      3. Réduire le SL de 0.3% à 0.2%")
        print(f"      4. Éviter les paires les plus perdantes")
    else:
        print(f"   ✅ Le bot est globalement profitable de {stats['total_pnl_usdt']:.2f} USDT")
        print(f"   💡 Continuer avec la configuration actuelle")
    
    conn.close()

if __name__ == '__main__':
    try:
        complete_analysis()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
