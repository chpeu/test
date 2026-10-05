"""
Analyse du dernier trade avec colonnes correctes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

def get_db():
    password = quote_plus("@Cmtr1di12345")
    return psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")

# 1. Lister les colonnes de trade_atr_metrics
print("📋 Colonnes trade_atr_metrics:")
conn = get_db()
cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'trade_atr_metrics' 
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print(cols)
cur.close()
conn.close()

# 2. Récupérer le dernier trade
print("\n" + "="*80)
print("🎬 DERNIER TRADE FERMÉ")
print("="*80)

conn = get_db()
cur = conn.cursor(cursor_factory=RealDictCursor)

# Trade de base
cur.execute("""
    SELECT * FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC 
    LIMIT 1
""")
trade = cur.fetchone()

if trade:
    trade = dict(trade)
    trade_id = trade['id']
    
    print(f"\n📊 INFOS DE BASE")
    print(f"   ID: {trade_id}")
    print(f"   Symbol: {trade.get('symbol')}")
    print(f"   Direction: {trade.get('direction')}")
    print(f"   Entry: {trade.get('entry_price')}")
    print(f"   Exit: {trade.get('exit_price')}")
    print(f"   Size USDT: {trade.get('size_usdt')}")
    print(f"   SL: {trade.get('sl_price')}")
    print(f"   TP: {trade.get('tp_price')}")
    print(f"   PnL: {trade.get('pnl_pct'):+.3f}%")
    print(f"   PnL USDT: {trade.get('pnl_usdt'):+.4f}")
    print(f"   Net PnL: {trade.get('net_pnl_pct')}")
    print(f"   Net PnL USDT: {trade.get('net_pnl_usdt')}")
    print(f"   Exit Reason: {trade.get('exit_reason')}")
    
    ts_entry = trade.get('timestamp_entry')
    ts_exit = trade.get('timestamp_exit')
    if ts_entry and ts_exit:
        duration = (ts_exit - ts_entry).total_seconds()
        print(f"   Durée: {duration:.0f}s ({duration/60:.1f} min)")
        print(f"   Entrée: {ts_entry}")
        print(f"   Sortie: {ts_exit}")
    
    # Métriques ATR
    cur.execute("SELECT * FROM trade_atr_metrics WHERE trade_id = %s", (str(trade_id),))
    metrics = cur.fetchone()
    
    if metrics:
        metrics = dict(metrics)
        print(f"\n📈 MÉTRIQUES ATR")
        print(f"   ATR 1m: {metrics.get('entry_atr_pct_1m')}%")
        print(f"   ATR 5m: {metrics.get('entry_atr_pct_5m')}%")
        
        print(f"\n🎯 MFE / MAE")
        mfe = metrics.get('max_pnl_reached')
        mae = metrics.get('min_pnl_reached')
        print(f"   MFE: {mfe}")
        print(f"   MAE: {mae}")
        print(f"   Max Price: {metrics.get('max_price_reached')}")
        print(f"   Min Price: {metrics.get('min_price_reached')}")
        print(f"   Time to Max: {metrics.get('time_to_max_pnl_seconds')}s")
        print(f"   Time to Min: {metrics.get('time_to_min_pnl_seconds')}s")
        
        print(f"\n🛡️ BREAK-EVEN")
        print(f"   BE Triggered: {metrics.get('be_triggered')}")
        print(f"   BE At: {metrics.get('be_triggered_at')}")
        print(f"   BE PnL: {metrics.get('be_triggered_pnl_pct')}")
        
        print(f"\n🎢 TRAILING")
        print(f"   Trailing Activated: {metrics.get('trailing_activated')}")
        print(f"   Trailing At: {metrics.get('trailing_activated_at')}")
        print(f"   Final SL: {metrics.get('trailing_final_sl_price')}")
        print(f"   Final Distance: {metrics.get('trailing_final_distance_pct')}")
        
        print(f"\n⏰ STAGNATION")
        print(f"   Detected: {metrics.get('stagnation_detected')}")
        print(f"   Duration: {metrics.get('stagnation_duration_seconds')}s")
        
        # Diagnostic
        print(f"\n🔍 DIAGNOSTIC")
        print("-"*40)
        
        pnl = trade.get('pnl_pct', 0)
        exit_reason = trade.get('exit_reason')
        trailing_activated = metrics.get('trailing_activated')
        be_triggered = metrics.get('be_triggered')
        
        issues = []
        
        if mfe is None:
            issues.append("❌ MFE non enregistré")
        
        if exit_reason == 'TS' and not trailing_activated:
            issues.append("❌ Exit=TS mais trailing_activated=False")
        
        if mfe and mfe > 0.15 and not trailing_activated:
            issues.append(f"⚠️ MFE {mfe:.3f}% >= 0.15% mais trailing non activé")
        
        if mfe and mfe > 0.15 and not be_triggered:
            issues.append(f"⚠️ MFE {mfe:.3f}% >= 0.15% mais BE non activé")
        
        if mfe and pnl and mfe > 0:
            capture = pnl / mfe * 100
            if capture < 50:
                issues.append(f"⚠️ Capture MFE faible: {capture:.1f}%")
        
        if issues:
            for i in issues:
                print(f"   {i}")
        else:
            print("   ✅ Aucun problème détecté")
    else:
        print("\n❌ Pas de métriques ATR trouvées")
    
    # Events
    cur.execute("SELECT * FROM trade_events WHERE trade_id = %s ORDER BY event_timestamp", (str(trade_id),))
    events = cur.fetchall()
    
    if events:
        print(f"\n📋 ÉVÉNEMENTS ({len(events)})")
        print("-"*40)
        for e in events:
            e = dict(e)
            print(f"   [{e.get('event_type')}] {e.get('event_timestamp')}")
            if e.get('details'):
                print(f"      {e.get('details')}")
    
cur.close()
conn.close()

print("\n" + "="*80)
