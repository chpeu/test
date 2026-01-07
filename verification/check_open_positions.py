"""
Vérifier les positions ouvertes et leur PnL actuel
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔍 VÉRIFICATION POSITIONS OUVERTES")
print("="*70)

# 1. Lire le state.json pour voir les positions actives
try:
    with open('state.json', 'r') as f:
        state = json.load(f)
    
    active_positions = state.get('active_positions', {})
    print(f"\n📊 Positions dans state.json: {len(active_positions)}")
    
    for pos_id, pos in active_positions.items():
        symbol = pos.get('symbol', 'N/A')
        direction = pos.get('direction', 'N/A')
        entry_price = pos.get('entry_price', 0)
        current_price = pos.get('current_price', 0)
        size = pos.get('size', 0)
        
        if current_price and entry_price:
            if direction == 'LONG':
                pnl_pct = (current_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - current_price) / entry_price * 100
        else:
            pnl_pct = 0
        
        print(f"\n   {symbol} | {direction}")
        print(f"   Entry: {entry_price:.6f} | Current: {current_price:.6f}")
        print(f"   Size: {size} | PnL: {pnl_pct:+.3f}%")
        
except Exception as e:
    print(f"\n❌ Erreur lecture state.json: {e}")

# 2. Vérifier dans PostgreSQL les trades ouverts (exit_price NULL)
cur.execute("""
    SELECT 
        symbol,
        direction,
        entry_price,
        timestamp_entry,
        COUNT(*) as count
    FROM trades
    WHERE exit_price IS NULL
    GROUP BY symbol, direction, entry_price, timestamp_entry
    ORDER BY timestamp_entry DESC
""")
open_trades = cur.fetchall()

print(f"\n📊 Trades ouverts dans PostgreSQL: {len(open_trades)}")
for trade in open_trades:
    trade = dict(trade)
    print(f"\n   {trade['symbol']} | {trade['direction']}")
    print(f"   Entry: {trade['entry_price']:.6f}")
    print(f"   Ouvert: {trade['timestamp_entry']}")

# 3. PnL du dashboard - dernières 24h
cur.execute("""
    SELECT 
        COUNT(*) as trades_24h,
        SUM(pnl_pct) as pnl_24h,
        SUM(pnl_usdt) as pnl_usdt_24h
    FROM trades
    WHERE timestamp_exit >= NOW() - INTERVAL '24 hours'
    AND exit_price IS NOT NULL
""")
last_24h = cur.fetchone()

print(f"\n📊 Dernières 24h:")
print(f"   Trades: {last_24h['trades_24h']}")
print(f"   PnL: {last_24h['pnl_24h']:+.3f}% ({last_24h['pnl_usdt_24h']:+.4f} USDT)")

# 4. PnL aujourd'hui (depuis 00:00 UTC)
cur.execute("""
    SELECT 
        COUNT(*) as trades_today,
        SUM(pnl_pct) as pnl_today,
        SUM(pnl_usdt) as pnl_usdt_today
    FROM trades
    WHERE DATE(timestamp_exit) = CURRENT_DATE
    AND exit_price IS NOT NULL
""")
today = cur.fetchone()

print(f"\n📊 Aujourd'hui (UTC):")
print(f"   Trades: {today['trades_today']}")
print(f"   PnL: {today['pnl_today']:+.3f}% ({today['pnl_usdt_today']:+.4f} USDT)")

# 5. PnL avec positions ouvertes simulées
print(f"\n🔍 Simulation avec positions ouvertes:")
total_pnl = float(today['pnl_today'] or 0)
total_usdt = float(today['pnl_usdt_today'] or 0)

# Ajouter PnL des positions ouvertes (approximation)
for pos_id, pos in active_positions.items():
    symbol = pos.get('symbol', 'N/A')
    direction = pos.get('direction', 'N/A')
    entry_price = float(pos.get('entry_price', 0))
    current_price = float(pos.get('current_price', 0))
    size = float(pos.get('size', 0))
    
    if current_price and entry_price:
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100
        
        # Approximation USDT (size * entry_price * pnl_pct/100)
        pnl_usdt = size * entry_price * pnl_pct / 100
        
        total_pnl += pnl_pct * 0.1  # Pondération faible car taille inconnue
        total_usdt += pnl_usdt
        
        print(f"   +{symbol}: {pnl_pct:+.3f}% ({pnl_usdt:+.4f} USDT)")

print(f"\n📊 Total estimé avec positions ouvertes:")
print(f"   PnL: {total_pnl:+.3f}% ({total_usdt:+.4f} USDT)")

cur.close()
conn.close()
print("="*70)
