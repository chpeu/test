#!/usr/bin/env python3
"""Check PnL sign consistency vs entry/exit/size from DB."""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

conn = psycopg2.connect(
    dbname=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", "@Cmtr1di12345"),
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
)
cur = conn.cursor()

cur.execute(
    "SELECT column_name FROM information_schema.columns WHERE table_name='trades'"
)
cols = {row[0] for row in cur.fetchall()}

size_candidates = ["size", "size_usdt", "size_initial_usdt", "size_executed_usdt"]
size_col = next((c for c in size_candidates if c in cols), None)
print(f"Size column selected: {size_col}")

extra_cols = [
    col for col in [
        "partial_tp_executed",
        "partial_tp_triggered",
        "partial_tp_profit",
        "partial_tp_percent",
    ]
    if col in cols
]
extra_select = ", " + ", ".join(extra_cols) if extra_cols else ""

size_expr = size_col if size_col else "NULL"

cur.execute(
    f"""
    SELECT id, symbol, direction, entry_price, exit_price,
           pnl_usdt, net_pnl_usdt, {size_expr} AS size_value, timestamp_exit{extra_select}
    FROM trades
    WHERE timestamp_exit >= '2026-02-01 22:00:00'
      AND timestamp_exit <= '2026-02-02 07:00:00'
    ORDER BY timestamp_exit ASC
    """
)
rows = cur.fetchall()

sign_mismatch = []
net_sign_mismatch = []
size_negative = []

for row in rows:
    base = row[:9]
    extra_values = row[9:]
    tid, sym, direction, entry, exit_p, pnl, net_pnl, size_value, ts = base
    extra_map = dict(zip(extra_cols, extra_values))
    if size_value is not None and size_value < 0:
        size_negative.append((sym, direction, size_value, ts))
    if entry is None or exit_p is None or pnl is None or size_value is None:
        continue
    if entry == 0:
        continue

    direction = (direction or "").upper()
    if direction == "LONG":
        price_diff = exit_p - entry
    else:
        price_diff = entry - exit_p

    expected_pnl = size_value * (price_diff / entry)
    expected_positive = expected_pnl > 0

    if (expected_positive and pnl < 0) or (not expected_positive and pnl > 0):
        sign_mismatch.append((sym, direction, entry, exit_p, size_value, pnl, expected_pnl, net_pnl, ts, extra_map))

    if net_pnl is not None:
        if (expected_positive and net_pnl < 0) or (not expected_positive and net_pnl > 0):
            net_sign_mismatch.append((sym, direction, entry, exit_p, size_value, pnl, expected_pnl, net_pnl, ts, extra_map))

print(f"Total trades: {len(rows)}")
print(f"Gross pnl_usdt sign mismatches: {len(sign_mismatch)}")
print(f"Net pnl_usdt sign mismatches: {len(net_sign_mismatch)}")
print(f"Rows with negative size_value: {len(size_negative)}")

print("\nSample gross mismatches:")
for item in sign_mismatch[:10]:
    sym, direction, entry, exit_p, size_value, pnl, expected_pnl, net_pnl, ts, extra_map = item
    extra_info = (
        " | " + ", ".join(f"{k}={v}" for k, v in extra_map.items())
        if extra_map else ""
    )
    print(
        f"- {sym} {direction} {entry}→{exit_p} size={size_value} "
        f"expected={expected_pnl:+.4f} pnl_usdt={pnl:+.4f} net={net_pnl} ts={ts}{extra_info}"
    )

print("\nSample net mismatches:")
for item in net_sign_mismatch[:10]:
    sym, direction, entry, exit_p, size_value, pnl, expected_pnl, net_pnl, ts, extra_map = item
    extra_info = (
        " | " + ", ".join(f"{k}={v}" for k, v in extra_map.items())
        if extra_map else ""
    )
    print(
        f"- {sym} {direction} {entry}→{exit_p} size={size_value} "
        f"expected={expected_pnl:+.4f} net_pnl={net_pnl:+.4f} pnl_usdt={pnl} ts={ts}{extra_info}"
    )

if size_negative:
    print("\nSample negative sizes:")
    for item in size_negative[:10]:
        sym, direction, size_value, ts = item
        print(f"- {sym} {direction} size={size_value} ts={ts}")

cur.close()
conn.close()
