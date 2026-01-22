#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification detaillee des colonnes NULL sur les trades recents
"""
import psycopg2
from datetime import datetime, timedelta

def check_recent_trades():
    """Verifier les colonnes NULL sur les trades des dernieres heures"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )

    conn.set_client_encoding('WIN1252')
    
    cursor = conn.cursor()
    
    # Trades des 6 dernieres heures
    print("ANALYSE TRADES RECENTS (6 dernieres heures)")
    print("=" * 70)
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM trades 
        WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'
    """)
    total_recent = cursor.fetchone()[0]
    print(f"Total trades recents: {total_recent}")
    
    if total_recent == 0:
        print("Aucun trade recent trouve")
        return
    
    # Colonnes critiques à vérifier
    critical_trade_columns = [
        'setup_score', 'scan_log_id', 'price_at_signal', 'price_at_order_sent',
        'ml_prediction', 'ml_features', 'optimal_exit_price', 'user_rating',
        'trade_notes', 'volume_24h_at_entry', 'opportunity_id', 'config_snapshot',
        'config_rsi_filter_enabled', 'config_use_confluence', 'config_volume_multiplier',
        'config_invert_signals', 'config_use_anti_whipsaw', 'config_use_micro_confirmation',
        'entry_order_id', 'is_live_trade', 'time_to_fill_entry_ms'
    ]
    
    print(f"\nCOLONNES CRITIQUES (sur {total_recent} trades recents):")
    print("-" * 70)
    
    for col in critical_trade_columns:
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total,
                COUNT({col}) as filled,
                COUNT(*) - COUNT({col}) as nulls,
                ROUND((COUNT(*) - COUNT({col})) * 100.0 / COUNT(*), 2) as null_pct
            FROM trades 
            WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'
        """)
        
        total, filled, nulls, null_pct = cursor.fetchone()
        
        if nulls > 0:
            status = "BAD" if null_pct > 50 else "WARN" if null_pct > 10 else "OK"
            print(f"{status} {col:35s}: {nulls:3d}/{total} NULL ({null_pct:5.1f}%)")
        else:
            print(f"OK  {col:35s}: Tous remplis")
    
    # Examiner les 3 trades les plus recents en detail
    print(f"\nDETAIL 3 TRADES PLUS RECENTS:")
    print("-" * 70)
    
    cursor.execute("""
        SELECT 
            id, symbol, timestamp_entry, direction,
            setup_score, scan_log_id, price_at_signal, 
            ml_prediction, user_rating, is_live_trade,
            entry_order_id, opportunity_id
        FROM trades 
        WHERE timestamp_entry >= NOW() - INTERVAL '6 hours'
        ORDER BY timestamp_entry DESC 
        LIMIT 3
    """)
    
    for row in cursor.fetchall():
        trade_id, symbol, ts, direction, setup_score, scan_log_id, price_signal, ml_pred, rating, is_live, order_id, opp_id = row
        print(f"\nTrade {trade_id[:8]}... | {symbol} {direction} | {ts}")
        print(f"   setup_score: {setup_score}")
        print(f"   scan_log_id: {scan_log_id}")  
        print(f"   price_at_signal: {price_signal}")
        print(f"   ml_prediction: {ml_pred}")
        print(f"   user_rating: {rating}")
        print(f"   is_live_trade: {is_live}")
        print(f"   entry_order_id: {order_id}")
        print(f"   opportunity_id: {opp_id}")
    
    # Vérifier si les nouveaux scans ont les colonnes contexte remplies
    print(f"\nSCAN_LOGS RECENTS (colonnes contexte):")
    print("-" * 70)
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM scan_logs 
        WHERE timestamp >= NOW() - INTERVAL '2 hours'
    """)
    total_scans = cursor.fetchone()[0]
    print(f"Total scans recents: {total_scans}")
    
    if total_scans > 0:
        scan_context_cols = [
            'market_regime', 'session_market', 'hour_utc', 
            'regime_at_scan', 'regime_confidence_at_scan'
        ]
        
        for col in scan_context_cols:
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT({col}) as filled,
                    ROUND(COUNT({col}) * 100.0 / COUNT(*), 2) as filled_pct
                FROM scan_logs 
                WHERE timestamp >= NOW() - INTERVAL '2 hours'
            """)
            
            total, filled, filled_pct = cursor.fetchone()
            status = "OK" if filled_pct > 80 else "WARN" if filled_pct > 50 else "BAD"
            print(f"{status} {col:30s}: {filled:4d}/{total} remplis ({filled_pct:5.1f}%)")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        check_recent_trades()
    except Exception as e:
        print(f"Erreur: {e}")
