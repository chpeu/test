# -*- coding: utf-8 -*-
"""Check existing exit_reason values in database"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def main():
    # Use individual params like existing code
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    print("=" * 60)
    print("EXIT REASONS IN DATABASE (trades table)")
    print("=" * 60)
    cur.execute('SELECT exit_reason, COUNT(*) FROM trades GROUP BY exit_reason ORDER BY COUNT(*) DESC')
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} trades")
    
    print("\n" + "=" * 60)
    print("STAGNATION-related columns in trade_atr_metrics")
    print("=" * 60)
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' 
        AND column_name LIKE '%stagnation%'
        ORDER BY column_name
    """)
    for row in cur.fetchall():
        print(f"  - {row[0]}")
    
    print("\n" + "=" * 60)
    print("TRAILING MFE columns in trade_atr_metrics")
    print("=" * 60)
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' 
        AND column_name LIKE '%trailing_mfe%'
        ORDER BY column_name
    """)
    for row in cur.fetchall():
        print(f"  - {row[0]}")
    
    print("\n" + "=" * 60)
    print("Check for STAGNATION_POSITIVE/MFE_PROTECT trades")
    print("=" * 60)
    cur.execute("""
        SELECT exit_reason, COUNT(*) 
        FROM trades 
        WHERE exit_reason LIKE '%STAGNATION%'
        GROUP BY exit_reason
    """)
    rows = cur.fetchall()
    if rows:
        for row in rows:
            print(f"  {row[0]}: {row[1]} trades")
    else:
        print("  No STAGNATION-related exit_reason found yet")

    print("\n" + "=" * 60)
    print("STAGNATION/TRAILING columns in trades")
    print("=" * 60)
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'trades'
        AND (column_name LIKE '%stagnation%' OR column_name LIKE '%trailing_mfe%')
        ORDER BY column_name
    """)
    for row in cur.fetchall():
        print(f"  - {row[0]}")

    print("\n" + "=" * 60)
    print("Sanity: STAGNATION_POSITIVE flags/metrics in trades")
    print("=" * 60)
    cur.execute("SELECT COUNT(*) FROM trades WHERE exit_reason = 'STAGNATION_POSITIVE'")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trades WHERE exit_reason = 'STAGNATION_POSITIVE' AND stagnation_positive_triggered = TRUE")
    triggered = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trades WHERE exit_reason = 'STAGNATION_POSITIVE' AND stagnation_mfe_at_exit IS NOT NULL")
    mfe_present = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trades WHERE exit_reason = 'STAGNATION_POSITIVE' AND stagnation_pullback_at_exit IS NOT NULL")
    pullback_present = cur.fetchone()[0]
    print(f"  total={total}")
    print(f"  stagnation_positive_triggered TRUE={triggered}")
    print(f"  stagnation_mfe_at_exit non-NULL={mfe_present}")
    print(f"  stagnation_pullback_at_exit non-NULL={pullback_present}")

    print("\n" + "=" * 60)
    print("Sanity: trade_atr_metrics presence + non-NULL for STAGNATION_POSITIVE")
    print("=" * 60)
    cur.execute("""
        SELECT COUNT(DISTINCT t.id)
        FROM trades t
        WHERE t.exit_reason = 'STAGNATION_POSITIVE'
    """)
    total_pos = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT m.trade_id)
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE t.exit_reason = 'STAGNATION_POSITIVE'
    """)
    pos_with_metrics = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT m.trade_id)
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE t.exit_reason = 'STAGNATION_POSITIVE'
        AND m.param_stagnation_positive_timeout IS NOT NULL
    """)
    pos_with_timeout_param = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT m.trade_id)
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE t.exit_reason = 'STAGNATION_POSITIVE'
        AND m.stagnation_positive_triggered = TRUE
    """)
    pos_metrics_triggered_true = cur.fetchone()[0]
    print(f"  trades={total_pos}")
    print(f"  trades_with_trade_atr_metrics={pos_with_metrics}")
    print(f"  trade_atr_metrics_with_param_stagnation_positive_timeout_non_null={pos_with_timeout_param}")
    print(f"  trade_atr_metrics_with_stagnation_positive_triggered_TRUE={pos_metrics_triggered_true}")

    print("\n" + "=" * 60)
    print("Sanity: latest STAGNATION% trades joined with trade_atr_metrics")
    print("=" * 60)
    cur.execute("""
        SELECT
            t.id,
            t.created_at,
            t.exit_reason,
            m.id AS atr_metric_id,
            m.created_at AS atr_metric_created_at,
            m.stagnation_detected,
            m.stagnation_detected_at,
            m.param_stagnation_positive_timeout,
            m.param_stagnation_positive_threshold,
            m.stagnation_positive_triggered,
            m.stagnation_mfe_at_exit,
            m.stagnation_pullback_at_exit
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON m.trade_id = t.id
        WHERE t.exit_reason LIKE 'STAGNATION%'
        ORDER BY t.created_at DESC NULLS LAST
        LIMIT 20
    """)
    for row in cur.fetchall():
        print(f"  {row}")

    print("\n" + "=" * 60)
    print("Latest STAGNATION_POSITIVE trades (config_snapshot + columns)")
    print("=" * 60)
    cur.execute("""
        SELECT
            id,
            created_at,
            exit_reason,
            config_snapshot->>'stagnation_positive_exit_enabled' AS snapshot_positive_enabled,
            config_snapshot->>'stagnation_positive_timeout_seconds' AS snapshot_positive_timeout,
            config_stagnation_positive_exit_enabled,
            config_stagnation_positive_timeout_seconds,
            stagnation_positive_triggered,
            stagnation_mfe_at_exit,
            stagnation_pullback_at_exit
        FROM trades
        WHERE exit_reason = 'STAGNATION_POSITIVE'
        ORDER BY created_at DESC NULLS LAST
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(f"  {row}")
    
    conn.close()

if __name__ == '__main__':
    main()
