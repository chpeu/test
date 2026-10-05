"""\
Comparer les calculs PnL session entre DB et affichage frontend.
Période demandée: 2026-01-06 20:19:41 -> maintenant.

Hypothèses de diff:
- Frontend somme net_pnl_usdt (très probablement trade.net_pnl_usdt)
- Frontend somme net_pnl_pct (ce qui explique -1.74%)
- Pour un % session correct: total_usdt / total_size_usdt * 100
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

START_TIME = datetime(2026, 1, 6, 20, 19, 41)

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*90)
print("🔍 COMPARAISON PnL SESSION (06/01 20:19:41 → maintenant)")
print("="*90)

# Récupérer trades de la période
cur.execute("""
    SELECT *
    FROM trades
    WHERE exit_price IS NOT NULL
      AND timestamp_exit >= %s
    ORDER BY timestamp_exit DESC
""", (START_TIME,))
trades = [dict(r) for r in cur.fetchall()]

print(f"\nTrades trouvés: {len(trades)}")

# Colonnes candidates
pnl_usdt_keys = ['net_pnl_usdt', 'pnl_usdt', 'mexc_actual_pnl_usdt', 'realized_pnl_usdt']
pnl_pct_keys = ['net_pnl_pct', 'pnl_pct', 'mexc_actual_pnl_pct', 'realized_pnl_pct']
size_keys = ['size_executed_usdt', 'size_usdt', 'filled_size_usdt', 'position_size_usdt', 'size_initial_usdt', 'size']
fee_keys = ['fees_usdt', 'fee_usdt', 'fees', 'commission_usdt']

present_cols = set(trades[0].keys()) if trades else set()

def pick_first_present(keys):
    for k in keys:
        if k in present_cols:
            return k
    return None

pnl_usdt_col = pick_first_present(pnl_usdt_keys)
pnl_pct_col = pick_first_present(pnl_pct_keys)
size_col = pick_first_present(size_keys)
fee_col = pick_first_present(fee_keys)

print("\nColonnes détectées:")
print(f"- pnl_usdt_col: {pnl_usdt_col}")
print(f"- pnl_pct_col:  {pnl_pct_col}")
print(f"- size_col:     {size_col}")
print(f"- fee_col:      {fee_col}")

if not trades:
    cur.close()
    conn.close()
    raise SystemExit(0)

# Calculs
sum_usdt = sum(float(t.get(pnl_usdt_col) or 0) for t in trades) if pnl_usdt_col else 0
sum_pct = sum(float(t.get(pnl_pct_col) or 0) for t in trades) if pnl_pct_col else 0
sum_usdt_rounded4 = sum(round(float(t.get(pnl_usdt_col) or 0), 4) for t in trades) if pnl_usdt_col else 0
sum_size = sum(float(t.get(size_col) or 0) for t in trades) if size_col else 0
sum_fees = sum(float(t.get(fee_col) or 0) for t in trades) if fee_col else 0

weighted_pct = (sum_usdt / sum_size * 100) if (sum_size and pnl_usdt_col) else None

print("\nRésultats:")
print(f"- Somme USDT ({pnl_usdt_col}): {sum_usdt:+.6f}")
print(f"- Somme USDT arrondie(4):     {sum_usdt_rounded4:+.6f}")
print(f"- Somme % ({pnl_pct_col}):    {sum_pct:+.6f}")
if sum_size:
    print(f"- Somme size ({size_col}):    {sum_size:.6f}")
else:
    print(f"- Somme size:                N/A (pas de colonne size exploitable)")
if weighted_pct is not None:
    print(f"- % pondéré (USDT/size):      {weighted_pct:+.6f}%")
else:
    print(f"- % pondéré (USDT/size):      N/A")
if fee_col:
    print(f"- Somme fees ({fee_col}):     {sum_fees:+.6f}")

# Détails last 21 (comme UI)
print("\nDétails (comme UI: dernièrs 21 trades de la période, ordre DESC):")
print(f"{'time':<8} | {'symbol':<16} | {'dir':<5} | {'reason':<12} | {'size':>10} | {'pnl_usdt':>10} | {'pnl_pct':>8}")
print("-"*90)
for t in trades[:21]:
    ts = t.get('timestamp_exit')
    ts_str = ts.strftime('%H:%M:%S') if ts else '??:??:??'
    sym = t.get('symbol')
    direction = t.get('direction')
    reason = t.get('exit_reason') or t.get('reason')
    size_val = float(t.get(size_col) or 0) if size_col else 0
    pnl_u = float(t.get(pnl_usdt_col) or 0) if pnl_usdt_col else 0
    pnl_p = float(t.get(pnl_pct_col) or 0) if pnl_pct_col else 0
    print(f"{ts_str:<8} | {sym:<16} | {direction:<5} | {str(reason):<12} | {size_val:10.2f} | {pnl_u:10.4f} | {pnl_p:8.3f}")

cur.close()
conn.close()
print("="*90)
