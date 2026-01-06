"""
Test direct d'insertion des métriques ATR
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
print("🧪 TEST INSERTION MÉTRIQUES ATR")
print("="*70)

# Vérifier le type de trade_id dans trade_atr_metrics
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'trade_atr_metrics' AND column_name = 'trade_id'
""")
col_info = cur.fetchone()
print(f"\ntrade_atr_metrics.trade_id type: {col_info['data_type'] if col_info else 'N/A'}")

# Récupérer un trade récent
cur.execute("""
    SELECT id, symbol, pnl_pct
    FROM trades 
    WHERE exit_price IS NOT NULL 
    ORDER BY timestamp_exit DESC
    LIMIT 1
""")
trade = cur.fetchone()

if not trade:
    print("✅ Tous les trades ont des métriques ATR!")
    cur.close()
    conn.close()
    exit(0)

trade_id = str(trade['id'])
print(f"\n📊 Trade test: {trade['symbol']} (ID: {trade_id[:8]}...)")
print(f"   PnL: {trade['pnl_pct']:+.3f}%")

# Tester l'insertion avec le PostgreSQLDataLogger
print("\n🔧 Test avec PostgreSQLDataLogger...")

try:
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    logger = PostgreSQLDataLogger()
    
    # Données minimales
    trade_data = {
        'entry_price': 100.0,
        'sl_price': 99.75,
        'tp_price': 105.0,
        'max_pnl_reached': 0.15,
        'min_pnl_reached': -0.05,
        'break_even_triggered': False,
        'trailing_stop_triggered': False,
    }
    
    entry_indicators = {
        'atr_1m': 0.1,
        'atr_5m': 0.15,
        'atr_pct_1m': 0.1,
        'atr_pct_5m': 0.15,
        'adx_1m': 25.0,
    }
    
    config_snapshot = {
        'atr_mult_sl': 1.0,
        'atr_mult_tp': 1.5,
        'trailing_trigger_atr_mult': 0.6,
        'trailing_distance_atr_mult': 0.4,
        'break_even_atr_mult': 0.4,
        'stagnation_exit_timeout_seconds': 540,
        'stagnation_exit_min_pnl_to_stay': 0.03,
    }
    
    result = logger.log_trade_atr_metrics(trade_id, trade_data, entry_indicators, config_snapshot)
    
    if result:
        print(f"   ✅ Insertion réussie! metric_id={result}")
    else:
        print(f"   ❌ Insertion échouée (result=None)")
        
except Exception as e:
    print(f"   ❌ Exception: {e}")
    import traceback
    traceback.print_exc()

# Vérifier si l'insertion a fonctionné
cur.execute("SELECT * FROM trade_atr_metrics WHERE trade_id = %s", (trade_id,))
metric = cur.fetchone()

if metric:
    print(f"\n✅ Métrique trouvée dans DB!")
    print(f"   max_pnl_reached: {metric['max_pnl_reached']}")
    print(f"   trailing_activated: {metric['trailing_activated']}")
else:
    print(f"\n❌ Métrique NON trouvée dans DB")

cur.close()
conn.close()
print("="*70)
