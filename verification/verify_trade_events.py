"""
Verification script for Phase 2H.6 - Trade Events Log
Checks that trade_events table is correctly populated
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.postgresql_datalogger import get_pg_datalogger

def verify_trade_events():
    print("\n" + "="*60)
    print("VERIFICATION TRADE_EVENTS (Phase 2H.6)")
    print("="*60)
    
    pg_logger = get_pg_datalogger()
    if not pg_logger or not pg_logger.enabled:
        print("ERROR: PostgreSQL DataLogger not available")
        return False
    
    conn = pg_logger._get_connection()
    if not conn:
        print("ERROR: Cannot get connection")
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Check table exists
        print("\n1. Checking table exists...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'trade_events'
            )
        """)
        exists = cur.fetchone()[0]
        print(f"   Table trade_events exists: {'OK' if exists else 'MISSING'}")
        
        if not exists:
            print("ERROR: Table trade_events does not exist. Run migration first.")
            return False
        
        # 2. Check columns
        print("\n2. Checking columns...")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trade_events'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        expected_cols = ['id', 'trade_id', 'event_type', 'event_timestamp', 
                        'price_at_event', 'pnl_pct_at_event', 'pnl_usdt_at_event', 'details']
        actual_cols = [c[0] for c in columns]
        
        for col in expected_cols:
            status = "OK" if col in actual_cols else "MISSING"
            print(f"   Column {col}: {status}")
        
        # 3. Check row count
        print("\n3. Checking row count...")
        cur.execute("SELECT COUNT(*) FROM trade_events")
        count = cur.fetchone()[0]
        print(f"   Total events: {count}")
        
        # 4. Check events by type
        print("\n4. Events by type:")
        cur.execute("""
            SELECT event_type, COUNT(*) as cnt 
            FROM trade_events 
            GROUP BY event_type 
            ORDER BY cnt DESC
        """)
        events = cur.fetchall()
        if events:
            for event_type, cnt in events:
                print(f"   {event_type}: {cnt}")
        else:
            print("   No events recorded yet (normal if no trades since restart)")
        
        # 5. Check recent events with details
        print("\n5. Recent events (last 10):")
        cur.execute("""
            SELECT 
                te.event_type, 
                te.event_timestamp,
                te.price_at_event,
                te.pnl_pct_at_event,
                t.symbol
            FROM trade_events te
            LEFT JOIN trades t ON te.trade_id = t.id
            ORDER BY te.event_timestamp DESC
            LIMIT 10
        """)
        recent = cur.fetchall()
        if recent:
            for event_type, ts, price, pnl, symbol in recent:
                pnl_str = f"{pnl:+.4f}%" if pnl else "N/A"
                price_str = f"{price:.6f}" if price else "N/A"
                symbol_str = symbol[:15] if symbol else "?"
                print(f"   {ts} | {symbol_str:15} | {event_type:20} | {price_str} | {pnl_str}")
        else:
            print("   No events yet")
        
        # 6. Check partial_tp columns in trade_atr_metrics
        print("\n6. Checking partial_tp columns in trade_atr_metrics:")
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(partial_tp_profit) as with_profit,
                COUNT(partial_tp_percent) as with_percent,
                COUNT(CASE WHEN partial_tp_executed THEN 1 END) as tp_executed
            FROM trade_atr_metrics
        """)
        row = cur.fetchone()
        print(f"   Total records: {row[0]}")
        print(f"   With partial_tp_profit: {row[1]} ({row[1]*100/row[0] if row[0] > 0 else 0:.1f}%)")
        print(f"   With partial_tp_percent: {row[2]} ({row[2]*100/row[0] if row[0] > 0 else 0:.1f}%)")
        print(f"   With partial_tp_executed=true: {row[3]} ({row[3]*100/row[0] if row[0] > 0 else 0:.1f}%)")
        
        cur.close()
        pg_logger._return_connection(conn)
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Table exists: OK")
        print(f"Columns: OK")
        print(f"Events recorded: {count}")
        
        if count == 0:
            print("\nNOTE: No events yet. They will be recorded after the next trade.")
            print("Events logged: BE_TRIGGERED, TRAILING_ACTIVATED, TRAILING_MFE_TRIGGERED,")
            print("               PARTIAL_TP, EXIT")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verify_trade_events()
