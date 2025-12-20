#!/usr/bin/env python3
"""Corriger le trade SPX mal loggé"""

from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.environ.get('POSTGRES_HOST', 'localhost'),
    port=os.environ.get('POSTGRES_PORT', '5432'),
    database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.environ.get('POSTGRES_USER', 'postgres'),
    password=os.environ.get('POSTGRES_PASSWORD', '')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Trouver le trade SPX recent
print("="*60)
print("RECHERCHE TRADE SPX A CORRIGER")
print("="*60)

cur.execute("""
    SELECT id, symbol, direction, entry_price, exit_price, exit_reason,
           net_pnl_pct, net_pnl_usdt, sl_price, tp_price, created_at, duration_seconds
    FROM trades 
    WHERE symbol LIKE '%SPX%' 
    ORDER BY created_at DESC 
    LIMIT 3
""")

trades = cur.fetchall()
for t in trades:
    print(f"\nTrade ID: {t['id']}")
    print(f"  Symbol: {t['symbol']}")
    print(f"  Direction: {t['direction']}")
    print(f"  Entry: {t['entry_price']}")
    print(f"  Exit: {t['exit_price']}")
    print(f"  SL: {t['sl_price']}")
    print(f"  Exit Reason: {t['exit_reason']}")
    print(f"  PnL: {float(t['net_pnl_pct'] or 0)*100:.4f}%")
    print(f"  Created: {t['created_at']}")

# Le trade a corriger est celui avec STAGNATION_POSITIVE mais qui aurait du etre SL_EXCHANGE
# Entry: 0.5615, SL: 0.5606 (0.16%)
target_trade = None
for t in trades:
    if t['exit_reason'] == 'STAGNATION_POSITIVE' and t['entry_price']:
        entry = float(t['entry_price'])
        if abs(entry - 0.5615) < 0.001:  # Trade SPX a 0.5615
            target_trade = t
            break

if not target_trade:
    print("\n[!] Trade SPX a corriger non trouve")
else:
    print("\n" + "="*60)
    print("CORRECTION DU TRADE")
    print("="*60)
    
    trade_id = target_trade['id']
    entry_price = float(target_trade['entry_price'])
    sl_price = float(target_trade['sl_price']) if target_trade['sl_price'] else 0.5606
    
    # Calculer le vrai PnL (LONG, sorti au SL)
    # PnL = (exit - entry) / entry
    real_exit_price = sl_price  # Sorti au SL
    real_pnl_pct = (real_exit_price - entry_price) / entry_price
    
    # Taille position
    size_usdt = 24.71  # Depuis les logs
    real_pnl_usdt = size_usdt * real_pnl_pct
    
    print(f"  Trade ID: {trade_id}")
    print(f"  Entry: {entry_price}")
    print(f"  Real Exit (SL): {real_exit_price}")
    print(f"  Real PnL: {real_pnl_pct*100:.4f}%")
    print(f"  Real PnL USDT: {real_pnl_usdt:.4f}")
    
    # Mettre a jour
    print("\n  Mise a jour...")
    cur.execute("""
        UPDATE trades SET
            exit_price = %s,
            exit_reason = 'SL_EXCHANGE',
            net_pnl_pct = %s,
            net_pnl_usdt = %s,
            pnl_pct = %s,
            pnl_usdt = %s,
            win = FALSE
        WHERE id = %s
    """, (real_exit_price, real_pnl_pct, real_pnl_usdt, real_pnl_pct, real_pnl_usdt, trade_id))
    
    conn.commit()
    print("  [OK] Trade corrige!")
    
    # Verifier
    cur.execute("SELECT exit_price, exit_reason, net_pnl_pct FROM trades WHERE id = %s", (trade_id,))
    updated = cur.fetchone()
    print(f"\n  Verification:")
    print(f"    Exit: {updated['exit_price']}")
    print(f"    Reason: {updated['exit_reason']}")
    print(f"    PnL: {float(updated['net_pnl_pct'])*100:.4f}%")

conn.close()
