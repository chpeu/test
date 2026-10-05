"""
Analyse du dernier trade FARTCOIN
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

# Dernier trade
cur.execute("SELECT * FROM trades WHERE exit_price IS NOT NULL ORDER BY timestamp_exit DESC LIMIT 1")
t = dict(cur.fetchone())

print("="*70)
print("🎬 FILM DU TRADE: FARTCOIN/USDT")
print("="*70)

print(f"\n📊 DONNÉES DE BASE")
print("-"*40)
print(f"   ID: {t['id']}")
print(f"   Symbol: {t['symbol']}")
print(f"   Direction: {t['direction']}")
print(f"   Entry: {t['entry_price']}")
print(f"   Exit: {t['exit_price']}")
print(f"   SL final: {t['sl_price']}")
print(f"   TP: {t['tp_price']}")
print(f"   PnL: {t['pnl_pct']:+.4f}%")
print(f"   PnL USDT: {t['pnl_usdt']:+.4f}")
print(f"   Exit Reason: {t['exit_reason']}")

ts_entry = t['timestamp_entry']
ts_exit = t['timestamp_exit']
if ts_entry and ts_exit:
    duration = (ts_exit - ts_entry).total_seconds()
    print(f"   Durée: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"   Entrée: {ts_entry}")
    print(f"   Sortie: {ts_exit}")

entry = float(t['entry_price'])
exit_p = float(t['exit_price'])
sl = float(t['sl_price'])
tp = float(t['tp_price'])

# Calculs
sl_from_entry_pct = (sl - entry) / entry * 100
exit_from_entry_pct = (exit_p - entry) / entry * 100
tp_from_entry_pct = (tp - entry) / entry * 100

print(f"\n📐 CALCULS")
print("-"*40)
print(f"   SL depuis entry: {sl_from_entry_pct:+.4f}%")
print(f"   TP depuis entry: {tp_from_entry_pct:+.4f}%")
print(f"   Exit depuis entry: {exit_from_entry_pct:+.4f}%")

# Analyse Break-Even
print(f"\n🛡️ BREAK-EVEN")
print("-"*40)
if sl > entry:
    print(f"   ✅ SL ({sl:.6f}) > Entry ({entry:.6f})")
    print(f"   → Break-Even ACTIF (SL déplacé au-dessus de entry)")
    be_offset = (sl - entry) / entry * 100
    print(f"   → Offset BE: +{be_offset:.4f}%")
else:
    print(f"   ❌ SL ({sl:.6f}) <= Entry ({entry:.6f})")
    print(f"   → Break-Even NON actif")

# Vérifier métriques ATR
cur.execute("SELECT COUNT(*) as cnt FROM trade_atr_metrics WHERE trade_id = %s", (str(t['id']),))
cnt = cur.fetchone()['cnt']
print(f"\n📈 MÉTRIQUES ATR")
print("-"*40)
print(f"   Enregistrements: {cnt}")

if cnt == 0:
    print(f"   ⚠️ AUCUNE MÉTRIQUE ATR ENREGISTRÉE!")
    print(f"   → Possible bug: log_trade_atr_metrics non appelé")

# Reconstitution du film
print(f"\n🎬 RECONSTITUTION DU TRADE")
print("="*70)

print(f"""
[T+0s] 🟢 OUVERTURE
   Position: LONG FARTCOIN @ {entry}
   SL initial: ~{entry * 0.9975:.6f} (-0.25%)
   TP: {tp:.6f} (+{tp_from_entry_pct:.2f}%)

[T+???s] 🛡️ BREAK-EVEN ACTIVÉ
   → Le prix a monté >= +0.15%
   → SL déplacé à {sl:.6f} (+{sl_from_entry_pct:.4f}%)
   
[T+???s] 📉 PRIX REDESCEND
   → Le prix redescend sous le SL
   → SL touché à ~{sl:.6f}

[T+{duration:.0f}s] 🔴 FERMETURE (TS)
   Exit: {exit_p} ({exit_from_entry_pct:+.4f}%)
   PnL final: {t['pnl_pct']:+.4f}% ({t['pnl_usdt']:+.4f} USDT)
""")

# Diagnostic
print(f"\n🔍 DIAGNOSTIC")
print("="*70)

issues = []

# Issue 1: Pas de métriques
if cnt == 0:
    issues.append("❌ Métriques ATR non enregistrées dans trade_atr_metrics")

# Issue 2: Exit TS en perte
if t['exit_reason'] == 'TS' and t['pnl_pct'] < 0:
    issues.append(f"⚠️ Exit reason = TS mais PnL négatif ({t['pnl_pct']:+.4f}%)")
    issues.append("   → Normal si SL légèrement au-dessus de entry mais exit en slippage")

# Issue 3: SL final très proche de entry
if abs(sl_from_entry_pct) < 0.1:
    issues.append(f"⚠️ SL très proche de entry ({sl_from_entry_pct:+.4f}%)")
    issues.append("   → Le trailing n'a pas eu le temps de monter le SL davantage")

if issues:
    for i in issues:
        print(f"   {i}")
else:
    print("   ✅ Aucun problème majeur")

# 3 derniers trades avec métriques
print(f"\n📋 DERNIERS TRADES AVEC MÉTRIQUES (pour comparaison)")
print("-"*70)
cur.execute("""
    SELECT t.symbol, t.exit_reason, t.pnl_pct, 
           m.max_pnl_reached, m.trailing_activated, m.be_triggered
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.exit_price IS NOT NULL
    ORDER BY t.timestamp_exit DESC
    LIMIT 5
""")
for r in cur.fetchall():
    r = dict(r)
    mfe = r['max_pnl_reached']
    mfe_str = f"{mfe:.3f}%" if mfe else "NULL"
    trail = "✅" if r['trailing_activated'] else "❌"
    be = "✅" if r['be_triggered'] else "❌"
    print(f"   {r['symbol'][:15]:15} | {r['exit_reason']:6} | PnL={r['pnl_pct']:+.3f}% | MFE={mfe_str:8} | Trail={trail} | BE={be}")

cur.close()
conn.close()

print("\n" + "="*70)
