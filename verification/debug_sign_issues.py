#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.getenv('POSTGRES_USER', 'postgres'),
    password=os.getenv('POSTGRES_PASSWORD', '@Cmtr1di12345'),
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=os.getenv('POSTGRES_PORT', '5432')
)
cur = conn.cursor()

# Check columns related to pnl and mexc
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='trades' 
    AND (column_name LIKE '%pnl%' OR column_name LIKE '%mexc%' OR column_name LIKE '%fill%')
    ORDER BY column_name
""")
print("📊 Columns with pnl/mexc/fill:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

# Get SHIBUSDT trade details
cur.execute("""
    SELECT 
        id, symbol, direction, 
        entry_price, exit_price, 
        pnl_usdt, net_pnl_usdt, fees_usdt,
        timestamp_entry, timestamp_exit,
        exit_reason
    FROM trades 
    WHERE symbol LIKE '%SHIB%' 
    AND timestamp_exit >= '2026-02-01'
    ORDER BY timestamp_exit DESC 
    LIMIT 1
""")
row = cur.fetchone()
if row:
    print(f"\n🔍 SHIBUSDT Trade Details:")
    print(f"  ID: {row[0]}")
    print(f"  Symbol: {row[1]}")
    print(f"  Direction: {row[2]}")
    print(f"  Entry Price: {row[3]}")
    print(f"  Exit Price: {row[4]}")
    print(f"  PnL USDT: {row[5]}")
    print(f"  Net PnL USDT: {row[6]}")
    print(f"  Fees USDT: {row[7]}")
    print(f"  Entry Time: {row[8]}")
    print(f"  Exit Time: {row[9]}")
    print(f"  Exit Reason: {row[10]}")
    
    # Calculate expected PnL
    entry = row[3]
    exit_p = row[4]
    direction = row[2]
    
    if entry and exit_p:
        if direction == 'LONG':
            expected_pnl_pct = ((exit_p - entry) / entry) * 100
        else:  # SHORT
            expected_pnl_pct = ((entry - exit_p) / entry) * 100
        print(f"\n📈 Expected PnL %: {expected_pnl_pct:.4f}%")
        print(f"📉 Actual PnL USDT: {row[5]}")
        print(f"📉 Actual Net PnL USDT: {row[6]}")
        
        if (expected_pnl_pct > 0 and row[5] and row[5] < 0) or (expected_pnl_pct < 0 and row[5] and row[5] > 0):
            print("\n🚨 SIGN INVERSION DETECTED!")

# Get all trades with sign inversions
cur.execute("""
    SELECT 
        id, symbol, direction, 
        entry_price, exit_price, 
        pnl_usdt,
        timestamp_exit
    FROM trades 
    WHERE timestamp_exit >= '2026-02-01 22:00:00'
    AND timestamp_exit <= '2026-02-02 07:00:00'
    ORDER BY timestamp_exit ASC
""")

print(f"\n{'='*80}")
print("🔍 Checking all trades for sign consistency:")
print(f"{'='*80}")

sign_issues = []
for row in cur.fetchall():
    tid, sym, dire, entry, exit_p, pnl, ts = row
    if not entry or not exit_p or pnl is None:
        continue
    
    if dire == 'LONG':
        price_diff = exit_p - entry
    else:  # SHORT
        price_diff = entry - exit_p
    
    # Check if signs match
    if (price_diff > 0 and pnl < 0) or (price_diff < 0 and pnl > 0):
        sign_issues.append({
            'id': tid, 'symbol': sym, 'direction': dire,
            'entry': entry, 'exit': exit_p,
            'price_diff': price_diff, 'pnl': pnl,
            'timestamp': ts
        })

print(f"\nFound {len(sign_issues)} trades with sign inversions:")
for issue in sign_issues[:10]:
    print(f"\n  {issue['symbol']} ({issue['direction']})")
    print(f"    Entry: {issue['entry']} → Exit: {issue['exit']}")
    print(f"    Price diff: {issue['price_diff']:.8f}")
    print(f"    PnL: {issue['pnl']:.4f} (should be {'positive' if issue['price_diff'] > 0 else 'negative'})")

cur.close()
conn.close()
