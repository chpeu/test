#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse des conditions de marché d'aujourd'hui via les données SQL (version corrigée)
"""
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def analyze_market_today():
    """Analyser les conditions de marché d'aujourd'hui"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    print("📊 ANALYSE DU MARCHÉ - AUJOURD'HUI")
    print("=" * 80)
    
    # 1. Analyse des scans
    print("\n1️⃣ ACTIVITÉ DES SCANS:")
    print("-" * 50)
    
    scan_query = """
        SELECT 
            COUNT(*) as total_scans,
            COUNT(DISTINCT symbol) as unique_symbols,
            MIN(timestamp) as first_scan,
            MAX(timestamp) as last_scan,
            AVG(scan_duration_ms) as avg_scan_duration,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) as opportunities_found
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
    """
    
    scan_df = pd.read_sql(scan_query, conn)
    if not scan_df.empty:
        row = scan_df.iloc[0]
        print(f"   Total scans: {int(row['total_scans'])}")
        print(f"   Symboles scannés: {int(row['unique_symbols'])}")
        print(f"   Période: {row['first_scan']} → {row['last_scan']}")
        print(f"   Opportunités trouvées: {int(row['opportunities_found'])}")
        print(f"   Durée moyenne scan: {row['avg_scan_duration']:.0f}ms")
    
    # 2. Analyse des opportunités
    print("\n2️⃣ OPPORTUNITÉS DÉTECTÉES:")
    print("-" * 50)
    
    opp_query = """
        SELECT 
            COUNT(*) as total_opportunities,
            COUNT(DISTINCT symbol) as unique_symbols,
            AVG(score_total) as avg_score,
            MAX(score_total) as max_score,
            MIN(score_total) as min_score,
            AVG(atr_pct_1m) as avg_atr_pct,
            AVG(volume_ratio_1m) as avg_volume_ratio
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        AND is_opportunity = TRUE
    """
    
    opp_df = pd.read_sql(opp_query, conn)
    if not opp_df.empty and not pd.isna(opp_df.iloc[0]['total_opportunities']):
        row = opp_df.iloc[0]
        print(f"   Total opportunités: {int(row['total_opportunities'])}")
        print(f"   Symboles concernés: {int(row['unique_symbols'])}")
        print(f"   Score moyen: {row['avg_score']:.2f} (min: {row['min_score']:.2f}, max: {row['max_score']:.2f})")
        print(f"   ATR moyen: {row['avg_atr_pct']:.3f}%")
        print(f"   Volume ratio moyen: {row['avg_volume_ratio']:.2f}x")
    else:
        print("   Aucune opportunité enregistrée aujourd'hui")
    
    # 3. Top symboles aujourd'hui
    print("\n3️⃣ SYMBOLES LES PLUS ACTIFS:")
    print("-" * 50)
    
    symbols_query = """
        SELECT 
            symbol,
            COUNT(*) as scan_count,
            AVG(score_total) as avg_score,
            MAX(score_total) as max_score,
            AVG(atr_pct_1m) as avg_atr,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) as opportunity_count
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        GROUP BY symbol
        ORDER BY scan_count DESC, avg_score DESC
        LIMIT 10
    """
    
    symbols_df = pd.read_sql(symbols_query, conn)
    for _, row in symbols_df.iterrows():
        print(f"   {row['symbol']:15s}: {row['scan_count']:2d} scans | score: {row['avg_score']:.1f} (max: {row['max_score']:.1f}) | ATR: {row['avg_atr']:.3f}% | opp: {row['opportunity_count']}")
    
    # 4. Analyse de volatilité
    print("\n4️⃣ ANALYSE DE VOLATILITÉ (ATR):")
    print("-" * 50)
    
    atr_query = """
        SELECT 
            CASE 
                WHEN atr_pct_1m < 0.1 THEN 'Très basse (<0.1%)'
                WHEN atr_pct_1m < 0.2 THEN 'Basse (0.1-0.2%)'
                WHEN atr_pct_1m < 0.4 THEN 'Normale (0.2-0.4%)'
                WHEN atr_pct_1m < 0.6 THEN 'Élevée (0.4-0.6%)'
                ELSE 'Très élevée (>0.6%)'
            END as atr_category,
            COUNT(*) as count,
            AVG(score_total) as avg_score
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        AND atr_pct_1m IS NOT NULL
        GROUP BY atr_category
    """
    
    atr_df = pd.read_sql(atr_query, conn)
    for _, row in atr_df.iterrows():
        print(f"   {row['atr_category']:20s}: {row['count']:3d} scans | score moyen: {row['avg_score']:.2f}")
    
    # 5. Analyse par heure
    print("\n5️⃣ ACTIVITÉ PAR HEURE:")
    print("-" * 50)
    
    hourly_query = """
        SELECT 
            EXTRACT(HOUR FROM timestamp) as hour,
            COUNT(*) as scans,
            COUNT(DISTINCT symbol) as symbols,
            AVG(score_total) as avg_score,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) as opportunities
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY hour
    """
    
    hourly_df = pd.read_sql(hourly_query, conn)
    for _, row in hourly_df.iterrows():
        hour = int(row['hour'])
        print(f"   {hour:02d}h-{hour+1:02d}h: {int(row['scans']):3d} scans | {int(row['symbols']):2d} symboles | score: {row['avg_score']:.1f} | opp: {int(row['opportunities'])}")
    
    # 6. Analyse des rejets
    print("\n6️⃣ RAISONS DE REJET:")
    print("-" * 50)
    
    rejections_query = """
        SELECT 
            reject_reason,
            COUNT(*) as count,
            COUNT(DISTINCT symbol) as symbols
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        AND reject_reason IS NOT NULL
        GROUP BY reject_reason
        ORDER BY count DESC
    """
    
    rejections_df = pd.read_sql(rejections_query, conn)
    if not rejections_df.empty:
        for _, row in rejections_df.iterrows():
            print(f"   {row['reject_reason']:30s}: {row['count']:3d} fois ({row['symbols']} symboles)")
    else:
        print("   Aucun rejet enregistré aujourd'hui")
    
    # 7. Comparaison avec la moyenne
    print("\n7️⃣ COMPARAISON AVEC LA MOYENNE (7 derniers jours):")
    print("-" * 50)
    
    comparison_query = """
        SELECT 
            'Aujourd''hui' as period,
            COUNT(*) as scans,
            COUNT(DISTINCT symbol) as symbols,
            AVG(score_total) as avg_score,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) as opportunities
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        
        UNION ALL
        
        SELECT 
            'Moyenne 7j' as period,
            COUNT(*) / 7.0 as scans,
            COUNT(DISTINCT symbol) / 7.0 as symbols,
            AVG(score_total) as avg_score,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) / 7.0 as opportunities
        FROM scan_logs 
        WHERE DATE(timestamp) >= CURRENT_DATE - INTERVAL '7 days'
        AND DATE(timestamp) < CURRENT_DATE
    """
    
    comp_df = pd.read_sql(comparison_query, conn)
    for _, row in comp_df.iterrows():
        print(f"   {row['period']:12s}: {row['scans']:5.1f} scans/jour | {row['symbols']:4.1f} symboles | score: {row['avg_score']:.2f} | opp: {row['opportunities']:.1f}")
    
    # 8. Analyse des trades vs setups
    print("\n8️⃣ CONVERSION OPPORTUNITÉS → TRADES:")
    print("-" * 50)
    
    # Récupérer le nombre d'opportunités
    opp_count = 0
    if not opp_df.empty and not pd.isna(opp_df.iloc[0]['total_opportunities']):
        opp_count = int(opp_df.iloc[0]['total_opportunities'])
    
    trades_query = """
        SELECT COUNT(*) as count
        FROM trades 
        WHERE DATE(timestamp_entry) = CURRENT_DATE
    """
    
    trades_df = pd.read_sql(trades_query, conn)
    trades = int(trades_df.iloc[0]['count'])
    
    print(f"   Opportunités détectées: {opp_count}")
    print(f"   Trades exécutés: {trades}")
    if opp_count > 0:
        conv_rate = (trades / opp_count) * 100
        print(f"   Taux de conversion: {conv_rate:.1f}%")
    else:
        print("   Taux de conversion: N/A (pas d'opportunités)")
    
    # 9. Analyse des prix et spread
    print("\n9️⃣ ANALYSE DES PRIX ET SPREAD:")
    print("-" * 50)
    
    price_query = """
        SELECT 
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(spread_pct) as avg_spread,
            MAX(spread_pct) as max_spread,
            AVG(book_depth) as avg_depth
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE
        AND price IS NOT NULL
    """
    
    price_df = pd.read_sql(price_query, conn)
    if not price_df.empty:
        row = price_df.iloc[0]
        print(f"   Prix moyen: {row['avg_price']:.2f}")
        print(f"   Fourchette: {row['min_price']:.2f} - {row['max_price']:.2f}")
        if not pd.isna(row['avg_spread']):
            print(f"   Spread moyen: {row['avg_spread']:.3f}% (max: {row['max_spread']:.3f}%)")
        if not pd.isna(row['avg_depth']):
            print(f"   Profondeur moyenne: {row['avg_depth']:.0f}")
    
    # 10. Analyse spécifique BTC (Nouveau)
    analyze_btc_missed_moves(conn)
    
    # 11. Résumé et conclusions
    print("\n🎯 RÉSUMÉ DU MARCHÉ - AUJOURD'HUI")
    print("=" * 80)
    
    if not scan_df.empty:
        print(f"\n📈 ACTIVITÉ:")
        print(f"   • Scans: {int(scan_df.iloc[0]['total_scans'])}")
        print(f"   • Opportunités: {opp_count}")
        print(f"   • Trades: {trades}")
        if opp_count > 0:
            print(f"   • Conversion: {conv_rate:.1f}%")
        
        print(f"\n📊 CONDITIONS:")
        if not opp_df.empty and not pd.isna(opp_df.iloc[0]['avg_atr_pct']):
            print(f"   • Volatilité (ATR): {opp_df.iloc[0]['avg_atr_pct']:.3f}%")
            print(f"   • Score moyen: {opp_df.iloc[0]['avg_score']:.2f}")
            print(f"   • Volume: {opp_df.iloc[0]['avg_volume_ratio']:.2f}x")
        
        print(f"\n🔍 ANALYSE:")
        if not opp_df.empty and not pd.isna(opp_df.iloc[0]['avg_atr_pct']):
            if opp_df.iloc[0]['avg_atr_pct'] < 0.2:
                print(f"   • Volatilité FAIBLE → moins d'opportunités")
            elif opp_df.iloc[0]['avg_atr_pct'] > 0.5:
                print(f"   • Volatilité ÉLEVÉE → plus de risques")
            else:
                print(f"   • Volatilité NORMALE → conditions idéales")
        
        if opp_count > 0:
            if conv_rate < 20:
                print(f"   • Taux de conversion FAIBLE ({conv_rate:.1f}%)")
                print(f"     → Filtres trop stricts ou ML filter bloquant ?")
            elif conv_rate > 50:
                print(f"   • Taux de conversion ÉLEVÉ ({conv_rate:.1f}%)")
            else:
                print(f"   • Taux de conversion NORMAL ({conv_rate:.1f}%)")
        
        print(f"\n💡 RECOMMANDATIONS:")
        if not opp_df.empty and not pd.isna(opp_df.iloc[0]['avg_atr_pct']):
            if opp_df.iloc[0]['avg_atr_pct'] < 0.2:
                print(f"   • Volatilité faible: envisager d'élargir les filtres")
        if opp_count > 0 and conv_rate < 20:
            print(f"   • Conversion faible: vérifier les rejets ML")
        if trades < 5:
            print(f"   • Peu de trades: normal si volatilité faible ou bug corrigé récemment")

    conn.close()

def analyze_btc_missed_moves(conn):
    """Analyse spécifique des mouvements BTC manqués"""
    
    print("\n🪙 10. ANALYSE BTC - MOUVEMENTS MANQUÉS")
    print("-" * 50)
    
    # BTC hourly breakdown
    btc_hourly_query = """
        SELECT 
            EXTRACT(HOUR FROM timestamp) as hour,
            COUNT(*) as total_scans,
            COUNT(CASE WHEN is_opportunity = TRUE THEN 1 END) as opportunities,
            COUNT(CASE WHEN atr_optimal_passed_1m = FALSE THEN 1 END) as atr_1m_rejections,
            COUNT(CASE WHEN atr_optimal_passed_5m = FALSE THEN 1 END) as atr_5m_rejections,
            AVG(atr_pct_1m) as avg_atr_1m,
            AVG(score_total) as avg_score,
            MIN(atr_pct_1m) as min_atr,
            MAX(atr_pct_1m) as max_atr
        FROM scan_logs 
        WHERE DATE(timestamp) = CURRENT_DATE 
            AND (symbol LIKE '%BTC%' OR symbol LIKE '%ETH%' OR symbol LIKE '%SOL%')
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY hour
    """
    
    try:
        btc_hourly_df = pd.read_sql(btc_hourly_query, conn)
        
        print("\nActivité paires majeures par heure (BTC, ETH, SOL):")
        if not btc_hourly_df.empty:
            for _, row in btc_hourly_df.iterrows():
                hour = int(row['hour'])
                atr_1m_rej = int(row['atr_1m_rejections']) if not pd.isna(row['atr_1m_rejections']) else 0
                atr_5m_rej = int(row['atr_5m_rejections']) if not pd.isna(row['atr_5m_rejections']) else 0
                
                print(f"   {hour:02d}h: {int(row['total_scans']):2d} scans | {int(row['opportunities']):2d} opp | "
                      f"ATR 1m rejets: {atr_1m_rej:2d} | ATR 5m rejets: {atr_5m_rej:2d} | "
                      f"ATR range: {row['min_atr']:.3f}%-{row['max_atr']:.3f}%")
        else:
            print("   Aucun scan de paire majeure (BTC, ETH, SOL) trouvé aujourd'hui.")
            
            # Debug: voir quels symboles ont été scannés aujourd'hui
            debug_query = "SELECT DISTINCT symbol FROM scan_logs WHERE DATE(timestamp) = CURRENT_DATE LIMIT 10"
            debug_df = pd.read_sql(debug_query, conn)
            if not debug_df.empty:
                print(f"   Symboles scannés aujourd'hui (exemples): {', '.join(debug_df['symbol'].tolist())}")
        
        # BTC rejection analysis
        btc_rejections_query = """
            SELECT 
                reject_reason,
                COUNT(*) as count,
                AVG(atr_pct_1m) as avg_atr,
                AVG(score_total) as avg_score
            FROM scan_logs 
            WHERE DATE(timestamp) = CURRENT_DATE 
                AND (symbol LIKE '%BTC%' OR symbol LIKE '%ETH%' OR symbol LIKE '%SOL%')
                AND is_opportunity = FALSE
                AND reject_reason IS NOT NULL
            GROUP BY reject_reason
            ORDER BY count DESC
        """
        
        btc_rejections_df = pd.read_sql(btc_rejections_query, conn)
        
        print("\nRaisons de rejet paires majeures:")
        if not btc_rejections_df.empty:
            for _, row in btc_rejections_df.iterrows():
                print(f"   {row['reject_reason']:30s}: {int(row['count']):3d} | "
                      f"ATR: {row['avg_atr']:.3f}% | Score: {row['avg_score']:.2f}")
        else:
            print("   Aucune raison de rejet spécifique trouvée pour les paires majeures.")

    except Exception as e:
        print(f"   Erreur lors de l'analyse BTC: {e}")


if __name__ == '__main__':
    try:
        analyze_market_today()
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
