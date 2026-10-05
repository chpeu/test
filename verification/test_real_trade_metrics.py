"""
Test avec un VRAI trade existant - vérifier que les colonnes mode FIXE se remplissent
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🧪 TEST AVEC VRAI TRADE - VÉRIFICATION COLONNES MODE FIXE")
print("="*70)

# Récupérer un trade récent sans métriques
cur.execute("""
    SELECT id, symbol, entry_price, exit_price, sl_price, tp_price, 
           direction, exit_reason, pnl_pct
    FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC
    LIMIT 1
""")
trade = cur.fetchone()

if not trade:
    print("❌ Aucun trade trouvé")
    exit(1)

trade = dict(trade)
trade_id = str(trade['id'])

print(f"\n📊 Trade: {trade['symbol']} (ID: {trade_id[:8]}...)")
print(f"   Entry: {trade['entry_price']}, Exit: {trade['exit_price']}")
print(f"   PnL: {trade['pnl_pct']:+.3f}%, Reason: {trade['exit_reason']}")

# Vérifier si métrique existe déjà
cur.execute("SELECT id FROM trade_atr_metrics WHERE trade_id = %s", (trade_id,))
existing = cur.fetchone()

if existing:
    print(f"\n⚠️ Métrique existe déjà (id={existing['id']}), on la supprime pour re-tester...")
    cur.execute("DELETE FROM trade_atr_metrics WHERE trade_id = %s", (trade_id,))
    conn.commit()

# Construire trade_data réaliste basé sur le vrai trade
trade_data = {
    'entry_price': float(trade['entry_price']),
    'exit_price': float(trade['exit_price']),
    'sl_price': float(trade['sl_price']) if trade['sl_price'] else None,
    'tp_price': float(trade['tp_price']) if trade['tp_price'] else None,
    'direction': trade['direction'],
    'reason': trade['exit_reason'],
    'exit_reason': trade['exit_reason'],
    # Simuler MFE/MAE réalistes
    'max_pnl_reached': 0.25,
    'min_pnl_reached': -0.08,
    'max_price_reached': float(trade['entry_price']) * 1.0025,
    'min_price_reached': float(trade['entry_price']) * 0.9992,
    'time_to_max_pnl_seconds': 120,
    'time_to_min_pnl_seconds': 45,
    # Simuler BE activé
    'break_even_triggered': True,
    'break_even_triggered_at': datetime.now().isoformat(),
    'break_even_pnl_pct': 0.16,
    'break_even_price': float(trade['entry_price']),
    # Simuler Trailing activé
    'trailing_stop_triggered': True,
    'trailing_stop_triggered_at': datetime.now().isoformat(),
    'trailing_distance_pct': 0.10,
    'trailing_final_sl': float(trade['entry_price']) * 1.0015,
}

entry_indicators = {
    'atr_1m': 0.0008,
    'atr_5m': 0.0012,
    'atr_pct_1m': 0.12,
    'atr_pct_5m': 0.18,
    'adx_1m': 32.0,
}

config_snapshot = {
    'tp_sl_mode': 'FIXE',
    'atr_mult_sl': 1.0,
    'atr_mult_tp': 1.5,
    'trailing_trigger_atr_mult': 0.6,
    'trailing_distance_atr_mult': 0.4,
    'break_even_atr_mult': 0.4,
    'stagnation_exit_timeout_seconds': 540,
    'stagnation_exit_min_pnl_to_stay': 0.03,
}

# Tester l'insertion
print("\n🔧 Insertion métriques...")

try:
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    logger = PostgreSQLDataLogger()
    result = logger.log_trade_atr_metrics(trade_id, trade_data, entry_indicators, config_snapshot)
    
    if result:
        print(f"   ✅ Insertion réussie! metric_id={result}")
    else:
        print(f"   ❌ Insertion échouée")
        exit(1)
        
except Exception as e:
    print(f"   ❌ Exception: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Vérifier les données insérées
cur.execute("SELECT * FROM trade_atr_metrics WHERE trade_id = %s", (trade_id,))
m = cur.fetchone()

if m:
    m = dict(m)
    print(f"\n✅ VÉRIFICATION DES COLONNES MODE FIXE:")
    print("-"*50)
    
    checks = [
        ('max_pnl_reached', 'MFE', True),
        ('min_pnl_reached', 'MAE', True),
        ('max_price_reached', 'Max Price', True),
        ('min_price_reached', 'Min Price', True),
        ('time_to_max_pnl_seconds', 'Time to MFE', True),
        ('time_to_min_pnl_seconds', 'Time to MAE', True),
        ('be_triggered', 'BE Triggered', True),
        ('be_triggered_at', 'BE At', True),
        ('be_triggered_pnl_pct', 'BE PnL', True),
        ('be_price_at_trigger', 'BE Price', True),
        ('trailing_activated', 'Trailing Activated', True),
        ('trailing_activated_at', 'Trailing At', True),
        ('trailing_final_sl_price', 'Trailing Final SL', True),
        ('trailing_final_distance_pct', 'Trailing Distance', True),
        ('calculated_sl_pct', 'Calculated SL %', False),
        ('calculated_tp_pct', 'Calculated TP %', False),
        ('sl_mexc_price', 'SL MEXC Price', False),
        ('session_market', 'Session', False),
    ]
    
    filled = 0
    critical_ok = True
    
    for col, label, critical in checks:
        val = m.get(col)
        if val is not None:
            filled += 1
            if isinstance(val, bool):
                val_str = "✅" if val else "❌"
            elif isinstance(val, float):
                val_str = f"{val:.4f}"
            else:
                val_str = str(val)[:25]
            print(f"   ✅ {label:20}: {val_str}")
        else:
            if critical:
                critical_ok = False
                print(f"   ❌ {label:20}: NULL (CRITIQUE!)")
            else:
                print(f"   ⚠️ {label:20}: NULL")
    
    print(f"\n📊 Résumé: {filled}/{len(checks)} colonnes remplies")
    
    if critical_ok:
        print(f"\n✅ MODE FIXE: COLONNES CRITIQUES OK!")
    else:
        print(f"\n❌ MODE FIXE: PROBLÈME AVEC COLONNES CRITIQUES")

cur.close()
conn.close()
print("="*70)
