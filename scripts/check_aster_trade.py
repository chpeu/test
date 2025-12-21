#!/usr/bin/env python3
"""Analyse du dernier trade ASTER pour diagnostic PnL"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get last ASTER trade
    cur.execute("""
        SELECT 
            t.id,
            t.symbol,
            t.direction,
            t.entry_price,
            t.exit_price,
            t.size_usdt,
            t.tp_price,
            t.sl_price,
            t.exit_reason,
            t.timestamp_entry,
            t.timestamp_exit,
            m.max_pnl_reached,
            m.min_pnl_reached,
            m.calculated_sl_pct,
            m.calculated_tp_pct,
            m.be_triggered,
            m.trailing_activated,
            m.stagnation_detected
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE t.symbol LIKE '%ASTER%'
        ORDER BY t.timestamp_entry DESC 
        LIMIT 1
    """)
    
    trade = cur.fetchone()
    if not trade:
        print("Aucun trade ASTER trouve")
        return
    
    print("=" * 60)
    print("DERNIER TRADE ASTER")
    print("=" * 60)
    
    for key, value in trade.items():
        print(f"{key}: {value}")
    
    # Calcul PnL
    print()
    print("=" * 60)
    print("ANALYSE PNL")
    print("=" * 60)
    
    entry = float(trade['entry_price']) if trade['entry_price'] else 0
    exit_p = float(trade['exit_price']) if trade['exit_price'] else 0
    size = float(trade['size_usdt']) if trade['size_usdt'] else 0
    direction = trade['direction']
    sl = float(trade['sl_price']) if trade['sl_price'] else 0
    tp = float(trade['tp_price']) if trade['tp_price'] else 0
    
    if direction == 'SHORT':
        gross_pnl_pct = (entry - exit_p) / entry * 100
        gross_pnl_usdt = size * (entry - exit_p) / entry
        sl_pnl_pct = (entry - sl) / entry * 100
        tp_pnl_pct = (entry - tp) / entry * 100
    else:
        gross_pnl_pct = (exit_p - entry) / entry * 100
        gross_pnl_usdt = size * (exit_p - entry) / entry
        sl_pnl_pct = (sl - entry) / entry * 100
        tp_pnl_pct = (tp - entry) / entry * 100
    
    print(f"Direction: {direction}")
    print(f"Entry Price: {entry}")
    print(f"Exit Price: {exit_p}")
    print(f"SL Price: {sl}")
    print(f"TP Price: {tp}")
    print(f"Size: {size} USDT")
    print()
    print(f"Gross PnL calcule: {gross_pnl_pct:+.4f}% = {gross_pnl_usdt:+.4f} USDT")
    print(f"SL PnL attendu: {sl_pnl_pct:+.4f}%")
    print(f"TP PnL attendu: {tp_pnl_pct:+.4f}%")
    print(f"Exit Reason: {trade['exit_reason']}")
    
    # Verification
    print()
    print("=" * 60)
    print("DIAGNOSTIC")
    print("=" * 60)
    
    # Le probleme: +1.07 bot vs -0.07 MEXC
    # Difference = ~1.14 USDT
    print(f"PnL Bot attendu: +1.07 USDT")
    print(f"PnL MEXC reel: -0.07 USDT")
    print(f"Difference: ~1.14 USDT")
    print()
    
    # Verifier si exit_price correspond au SL
    if direction == 'SHORT':
        exit_vs_sl_diff = (exit_p - sl) / sl * 100
    else:
        exit_vs_sl_diff = (sl - exit_p) / sl * 100
    
    print(f"Exit vs SL: {exit_vs_sl_diff:+.4f}%")
    
    if abs(gross_pnl_usdt - 1.07) < 0.1:
        print(">>> Le PnL calcule correspond au +1.07 du bot")
        print(">>> PROBLEME: Le bot utilise un mauvais exit_price!")
    elif abs(gross_pnl_usdt - (-0.07)) < 0.1:
        print(">>> Le PnL calcule correspond au -0.07 de MEXC")
    else:
        print(f">>> PnL calcule ({gross_pnl_usdt:+.4f}) ne correspond ni au bot ni a MEXC")
    
    cur.close()
    conn.close()

def check_mexc_data():
    """Check if MEXC order data is captured"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check specific columns that should have MEXC data
    cur.execute("""
        SELECT 
            exit_order_id,
            exit_order_type,
            exit_requested_price,
            exit_fill_price,
            exit_slippage_pct,
            exit_latency_ms,
            exit_fee_usdt
        FROM trades 
        WHERE symbol LIKE '%ASTER%'
        ORDER BY timestamp_entry DESC 
        LIMIT 1
    """)
    trade = cur.fetchone()
    print()
    print("=" * 60)
    print("MEXC ORDER DATA")
    print("=" * 60)
    for k, v in trade.items():
        print(f"{k}: {v}")
    
    # Check if this is common
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(exit_fill_price) as with_fill_price
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '7 days'
    """)
    stats = cur.fetchone()
    print()
    print("=" * 60)
    print("STATS DERNIERS 7 JOURS")
    print("=" * 60)
    total = stats['total']
    with_fp = stats['with_fill_price']
    missing = total - with_fp
    print(f"Total trades: {total}")
    print(f"Avec fill_price: {with_fp}")
    print(f"Sans fill_price: {missing}")
    
    cur.close()
    conn.close()

def check_short_sl_bugs():
    """Check if SL bug is common on SHORT trades"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT 
            symbol,
            direction,
            entry_price,
            sl_price,
            tp_price,
            exit_reason,
            timestamp_entry
        FROM trades 
        WHERE direction = 'SHORT' 
        AND timestamp_entry > NOW() - INTERVAL '7 days'
        ORDER BY timestamp_entry DESC 
        LIMIT 10
    """)
    trades = cur.fetchall()
    
    print()
    print("=" * 60)
    print("ANALYSE SL SHORT TRADES (7 derniers jours)")
    print("=" * 60)
    
    bug_count = 0
    for t in trades:
        entry = float(t['entry_price']) if t['entry_price'] else 0
        sl = float(t['sl_price']) if t['sl_price'] else 0
        
        # For SHORT, SL should be ABOVE entry
        sl_status = "BUG" if sl < entry else "OK"
        if sl_status == "BUG":
            bug_count += 1
        
        symbol = t['symbol'][:15].ljust(15)
        print(f"{symbol} | Entry: {entry:.6f} | SL: {sl:.6f} | {sl_status} | {t['exit_reason']}")
    
    print()
    print(f"Trades SHORT avec SL BUG: {bug_count}/{len(trades)}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
    check_mexc_data()
    check_short_sl_bugs()
