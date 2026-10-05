"""Analyse des 20 derniers trades - Verification coherence PnL et ATR"""
import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import pandas as pd

load_dotenv()

password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

# D'abord, lister les colonnes de trades pour comprendre la structure
print("=" * 80)
print("ANALYSE DES 20 DERNIERS TRADES")
print("=" * 80)

# Query pour les colonnes
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trades' 
        ORDER BY ordinal_position
    """))
    cols = [r[0] for r in result.fetchall()]
    print(f"\nColonnes disponibles dans trades: {len(cols)}")

# Query 20 derniers trades avec toutes les infos PnL
query = text("""
SELECT 
    t.id,
    t.symbol,
    t.direction,
    t.entry_price,
    t.exit_price,
    t.size_usdt,
    t.leverage_used,
    t.pnl_usdt,
    t.pnl_pct,
    t.net_pnl_usdt,
    t.net_pnl_pct,
    t.fees_usdt,
    t.gross_pnl_usdt,
    t.exit_reason,
    t.created_at,
    t.entry_atr_1m,
    t.entry_atr_mult_sl,
    t.entry_atr_mult_tp,
    t.sl_price,
    t.tp_price,
    t.entry_market_regime
FROM trades t
ORDER BY t.created_at DESC
LIMIT 20
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print(f"\n{len(df)} trades recuperes")

# Analyse de chaque trade
print("\n" + "=" * 80)
print("VERIFICATION COHERENCE PnL")
print("=" * 80)

for idx, row in df.iterrows():
    entry = float(row['entry_price']) if row['entry_price'] else 0
    exit_p = float(row['exit_price']) if row['exit_price'] else 0
    direction = row['direction']
    size = float(row['size_usdt']) if row['size_usdt'] else 0
    leverage = float(row['leverage_used']) if row['leverage_used'] else 1
    fees = float(row['fees_usdt']) if row['fees_usdt'] else 0
    
    # PnL enregistre
    pnl_pct_recorded = float(row['pnl_pct']) if row['pnl_pct'] else 0
    net_pnl_pct_recorded = float(row['net_pnl_pct']) if row['net_pnl_pct'] else 0
    pnl_usdt_recorded = float(row['pnl_usdt']) if row['pnl_usdt'] else 0
    net_pnl_usdt_recorded = float(row['net_pnl_usdt']) if row['net_pnl_usdt'] else 0
    
    # Calcul PnL theorique
    if entry > 0 and exit_p > 0:
        if direction == 'LONG':
            price_change_pct = ((exit_p - entry) / entry) * 100
        else:
            price_change_pct = ((entry - exit_p) / entry) * 100
        
        # PnL brut (sans leverage)
        pnl_brut_pct = price_change_pct
        
        # PnL avec leverage
        pnl_leverage_pct = price_change_pct * leverage
        
        # PnL en USDT
        pnl_usdt_calc = (price_change_pct / 100) * size * leverage
        
        # PnL net (avec fees)
        net_pnl_usdt_calc = pnl_usdt_calc - fees
        net_pnl_pct_calc = (net_pnl_usdt_calc / size) * 100 if size > 0 else 0
    else:
        price_change_pct = 0
        pnl_brut_pct = 0
        pnl_leverage_pct = 0
        pnl_usdt_calc = 0
        net_pnl_usdt_calc = 0
        net_pnl_pct_calc = 0
    
    # Verification ATR
    atr = float(row['entry_atr_1m']) if row['entry_atr_1m'] else 0
    sl = float(row['sl_price']) if row['sl_price'] else 0
    tp = float(row['tp_price']) if row['tp_price'] else 0
    
    if atr > 0 and entry > 0:
        sl_distance = abs(entry - sl)
        tp_distance = abs(tp - entry)
        sl_atr_real = sl_distance / atr if atr else 0
        tp_atr_real = tp_distance / atr if atr else 0
    else:
        sl_atr_real = 0
        tp_atr_real = 0
    
    sl_mult_recorded = row['entry_atr_mult_sl']
    tp_mult_recorded = row['entry_atr_mult_tp']
    
    # Affichage
    symbol_short = row['symbol'].replace('/USDT:USDT', '')
    
    # Detecter incoherences
    pnl_diff = abs(pnl_brut_pct - pnl_pct_recorded) if pnl_pct_recorded else abs(pnl_brut_pct)
    net_pnl_diff = abs(net_pnl_pct_calc - net_pnl_pct_recorded) if net_pnl_pct_recorded else 0
    
    sl_diff = abs(sl_atr_real - float(sl_mult_recorded)) if sl_mult_recorded else 0
    tp_diff = abs(tp_atr_real - float(tp_mult_recorded)) if tp_mult_recorded else 0
    
    has_issue = pnl_diff > 0.1 or sl_diff > 0.5 or tp_diff > 0.5
    
    if has_issue or idx < 5:  # Toujours afficher les 5 premiers
        print(f"\n--- Trade #{row['id']} {symbol_short} {direction} ---")
        print(f"  Entry: {entry:.6f} -> Exit: {exit_p:.6f}")
        print(f"  Size: {size:.2f} USDT, Leverage: {leverage}x, Fees: {fees:.4f}")
        print(f"  Regime: {row['entry_market_regime']}")
        
        print(f"\n  [PnL BRUT (mouvement prix)]")
        print(f"    Calcule: {pnl_brut_pct:+.4f}%")
        print(f"    Enregistre (pnl_percent): {pnl_pct_recorded:+.4f}%")
        if pnl_diff > 0.01:
            print(f"    >> ECART: {pnl_diff:.4f}%")
        
        print(f"\n  [PnL NET (avec fees)]")
        print(f"    Calcule: {net_pnl_pct_calc:+.4f}% ({net_pnl_usdt_calc:+.4f} USDT)")
        print(f"    Enregistre: {net_pnl_pct_recorded:+.4f}% ({net_pnl_usdt_recorded:+.4f} USDT)")
        
        print(f"\n  [ATR Multipliers]")
        print(f"    SL: enregistre={sl_mult_recorded}, reel={sl_atr_real:.2f}x")
        print(f"    TP: enregistre={tp_mult_recorded}, reel={tp_atr_real:.2f}x")
        if sl_diff > 0.5 or tp_diff > 0.5:
            print(f"    >> INCOHERENCE ATR detectee!")
        
        print(f"  Exit: {row['exit_reason']}")

# Resume
print("\n" + "=" * 80)
print("RESUME - INCOHERENCES DETECTEES")
print("=" * 80)

issues = []
for idx, row in df.iterrows():
    entry = float(row['entry_price']) if row['entry_price'] else 0
    exit_p = float(row['exit_price']) if row['exit_price'] else 0
    direction = row['direction']
    pnl_pct_recorded = float(row['pnl_pct']) if row['pnl_pct'] else 0
    
    if entry > 0 and exit_p > 0:
        if direction == 'LONG':
            price_change_pct = ((exit_p - entry) / entry) * 100
        else:
            price_change_pct = ((entry - exit_p) / entry) * 100
        
        diff = abs(price_change_pct - pnl_pct_recorded)
        if diff > 0.01:
            issues.append({
                'id': row['id'],
                'symbol': row['symbol'].replace('/USDT:USDT', ''),
                'calc': price_change_pct,
                'recorded': pnl_pct_recorded,
                'diff': diff
            })

if issues:
    print(f"\n{len(issues)} trades avec ecart PnL > 0.01%:")
    for i in issues:
        print(f"  #{i['id']} {i['symbol']}: calc={i['calc']:+.4f}%, recorded={i['recorded']:+.4f}%, diff={i['diff']:.4f}%")
else:
    print("\nAucune incoherence PnL detectee!")

# Analyse specifique ADA
print("\n" + "=" * 80)
print("ANALYSE SPECIFIQUE TRADE ADA #2083")
print("=" * 80)

ada_query = text("""
SELECT * FROM trades WHERE id = 2083
""")

with engine.connect() as conn:
    result = conn.execute(ada_query)
    ada = result.fetchone()
    ada_cols = list(result.keys())

if ada:
    ada_data = dict(zip(ada_cols, ada))
    print("\nToutes les colonnes PnL du trade ADA:")
    pnl_cols = [c for c in ada_cols if 'pnl' in c.lower() or 'fee' in c.lower() or 'price' in c.lower()]
    for col in pnl_cols:
        print(f"  {col}: {ada_data.get(col)}")
