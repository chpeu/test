"""
Calculer le PnL exact du dashboard avec les positions ouvertes
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime
import requests

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔍 CALCUL PnL DASHBOARD")
print("="*70)

# 1. Récupérer les prix actuels via API MEXC
def get_current_price(symbol):
    try:
        # Convertir le symbole pour l'API
        if ':' in symbol:
            api_symbol = symbol.split(':')[0]  # Enlever :USDT
        elif '/' in symbol:
            api_symbol = symbol.replace('/', '')  # BTC/USDT -> BTCUSDT
        else:
            api_symbol = symbol
        
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={api_symbol}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['price'])
    except:
        pass
    return None

# 2. PnL des trades fermés aujourd'hui
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(pnl_pct) as pnl_pct,
        SUM(pnl_usdt) as pnl_usdt
    FROM trades
    WHERE DATE(timestamp_exit) = CURRENT_DATE
    AND exit_price IS NOT NULL
""")
closed_today = cur.fetchone()

print(f"\n📊 Trades fermés aujourd'hui:")
print(f"   Count: {closed_today['count']}")
print(f"   PnL: {closed_today['pnl_pct']:+.3f}% ({closed_today['pnl_usdt']:+.4f} USDT)")

# 3. PnL des positions ouvertes
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
open_positions = cur.fetchall()

print(f"\n📊 Positions ouvertes: {len(open_positions)}")
total_open_pnl = 0
total_open_usdt = 0

# Calculer PnL pour chaque position ouverte
for pos in open_positions:
    pos = dict(pos)
    symbol = pos['symbol']
    direction = pos['direction']
    entry_price = float(pos['entry_price'])
    
    # Récupérer prix actuel
    current_price = get_current_price(symbol)
    
    if current_price:
        if direction == 'LONG':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100
        
        # Approximation USDT (en supposant taille de 10 USDT par position)
        size_usdt = 10
        pnl_usdt = size_usdt * pnl_pct / 100
        
        total_open_pnl += pnl_pct * 0.1  # Pondération faible
        total_open_usdt += pnl_usdt
        
        print(f"   {symbol:<15} | {direction:<5} | Entry: {entry_price:.6f} | "
              f"Current: {current_price:.6f} | PnL: {pnl_pct:+.3f}%")
    else:
        print(f"   {symbol:<15} | {direction:<5} | Entry: {entry_price:.6f} | "
              f"Current: N/A | ⚠️ Prix non disponible")

# 4. Total dashboard estimé
total_dashboard_pct = float(closed_today['pnl_pct'] or 0) + total_open_pnl
total_dashboard_usdt = float(closed_today['pnl_usdt'] or 0) + total_open_usdt

print(f"\n📊 TOTAL DASHBOARD ESTIMÉ:")
print(f"   Trades fermés: {closed_today['pnl_pct']:+.3f}%")
print(f"   Positions ouvertes: {total_open_pnl:+.3f}%")
print(f"   ----------------------------------------")
print(f"   TOTAL: {total_dashboard_pct:+.3f}% ({total_dashboard_usdt:+.4f} USDT)")

print(f"\n⚠️ Note: L'écart avec -1.74% peut venir de:")
print(f"   - Taille réelle des positions (estimée à 10 USDT ici)")
print(f"   - Frais de trading non inclus")
print(f"   - Période différente (peut-être dernières 24h)")

# 5. Vérifier dernières 24h complètes
cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(pnl_pct) as pnl_pct,
        SUM(pnl_usdt) as pnl_usdt
    FROM trades
    WHERE timestamp_exit >= NOW() - INTERVAL '24 hours'
    AND exit_price IS NOT NULL
""")
last_24h = cur.fetchone()

print(f"\n📊 Dernières 24h complètes:")
print(f"   PnL: {last_24h['pnl_pct']:+.3f}% ({last_24h['pnl_usdt']:+.4f} USDT)")

cur.close()
conn.close()
print("="*70)
