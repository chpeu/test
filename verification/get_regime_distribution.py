#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script pour recuperer la distribution des trades par regime."""
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import sys

# Fix encoding Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')

# Connexion via SQLAlchemy
password = quote_plus('@Cmtr1di12345')
conn_str = f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml"
engine = create_engine(conn_str)

with engine.connect() as conn:
    # Distribution par regime
    print("=" * 60)
    print("DISTRIBUTION DES TRADES PAR REGIME")
    print("=" * 60)

    result = conn.execute(text("""
        SELECT 
            entry_market_regime,
            COUNT(*) as count,
            ROUND(AVG(CASE WHEN net_pnl_usdt > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) as winrate,
            ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl
        FROM trades 
        WHERE entry_market_regime IS NOT NULL 
        GROUP BY entry_market_regime 
        ORDER BY count DESC
    """))
    rows = result.fetchall()
    total = sum(r[1] for r in rows)

    print(f"{'Regime':<12} | {'Count':>6} | {'%':>6} | {'Winrate':>8} | {'Avg PnL':>10}")
    print("-" * 60)
    for r in rows:
        pct = round(r[1] / total * 100, 1) if total > 0 else 0
        print(f"{r[0]:<12} | {r[1]:>6} | {pct:>5}% | {r[2]:>7}% | {r[3]:>10}")

    # Trades sans regime
    result = conn.execute(text("SELECT COUNT(*) FROM trades WHERE entry_market_regime IS NULL"))
    null_count = result.fetchone()[0]
    print("-" * 60)
    print(f"{'NULL':<12} | {null_count:>6}")
    print(f"{'TOTAL':<12} | {total + null_count:>6}")

    # What-If coverage par regime
    print("\n" + "=" * 60)
    print("COUVERTURE WHAT-IF PAR REGIME")
    print("=" * 60)

    result = conn.execute(text("""
        SELECT 
            t.entry_market_regime,
            COUNT(*) as total,
            COUNT(m.pnl_if_calme_params) as with_whatif,
            ROUND(COUNT(m.pnl_if_calme_params)::numeric / NULLIF(COUNT(*)::numeric, 0) * 100, 1) as coverage
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE t.entry_market_regime IS NOT NULL
        GROUP BY t.entry_market_regime
        ORDER BY total DESC
    """))
    rows = result.fetchall()
    print(f"{'Regime':<12} | {'Total':>6} | {'What-If':>8} | {'Coverage':>10}")
    print("-" * 60)
    for r in rows:
        cov = r[3] if r[3] is not None else 0
        print(f"{r[0]:<12} | {r[1]:>6} | {r[2]:>8} | {cov:>9}%")

print("\n[OK] Requete terminee")
