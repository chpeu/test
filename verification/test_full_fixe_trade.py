"""
Test avec données complètes d'un trade mode FIXE
Simule un trade où BE et Trailing sont activés
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime
import uuid

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🧪 TEST COMPLET MODE FIXE - DONNÉES RÉALISTES")
print("="*70)

# Simuler un trade_id fictif pour le test
test_trade_id = str(uuid.uuid4())
print(f"\n📊 Trade test ID: {test_trade_id[:8]}...")

# Données d'un trade FIXE réaliste avec BE et Trailing activés
trade_data = {
    'entry_price': 0.7749,
    'exit_price': 0.7780,
    'sl_price': 0.7770,  # SL après trailing
    'tp_price': 0.8136,  # +5%
    'direction': 'LONG',
    'reason': 'TS',
    'pnl_pct': 0.30,
    # MFE/MAE
    'max_pnl_reached': 0.45,  # Prix monté à +0.45%
    'min_pnl_reached': -0.05,
    'max_price_reached': 0.7784,
    'min_price_reached': 0.7745,
    'time_to_max_pnl_seconds': 180,
    'time_to_min_pnl_seconds': 30,
    # Break-Even
    'break_even_triggered': True,
    'break_even_triggered_at': datetime.now().isoformat(),
    'break_even_pnl_pct': 0.16,
    'break_even_price': 0.7749,
    # Trailing
    'trailing_stop_triggered': True,
    'trailing_stop_triggered_at': datetime.now().isoformat(),
    'trailing_distance_pct': 0.10,
    'trailing_final_sl': 0.7770,
    # Stagnation (non détectée)
    'stagnation_detected': False,
}

entry_indicators = {
    'atr_1m': 0.0008,
    'atr_5m': 0.0012,
    'atr_pct_1m': 0.10,
    'atr_pct_5m': 0.15,
    'adx_1m': 35.0,
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
    'trailing_trigger_pnl': 0.15,  # Mode FIXE
    'trailing_distance': 0.10,  # Mode FIXE
    'break_even_trigger': 0.15,  # Mode FIXE
}

# Tester l'insertion
print("\n🔧 Test insertion avec PostgreSQLDataLogger...")

try:
    from core.postgresql_datalogger import PostgreSQLDataLogger
    
    logger = PostgreSQLDataLogger()
    result = logger.log_trade_atr_metrics(test_trade_id, trade_data, entry_indicators, config_snapshot)
    
    if result:
        print(f"   ✅ Insertion réussie! metric_id={result}")
    else:
        print(f"   ❌ Insertion échouée")
        
except Exception as e:
    print(f"   ❌ Exception: {e}")
    import traceback
    traceback.print_exc()

# Vérifier les données insérées
cur.execute("SELECT * FROM trade_atr_metrics WHERE trade_id = %s", (test_trade_id,))
m = cur.fetchone()

if m:
    m = dict(m)
    print(f"\n✅ DONNÉES INSÉRÉES:")
    print("-"*50)
    
    # Colonnes critiques mode FIXE
    checks = [
        ('max_pnl_reached', 0.45, 'MFE'),
        ('min_pnl_reached', -0.05, 'MAE'),
        ('max_price_reached', 0.7784, 'Max Price'),
        ('min_price_reached', 0.7745, 'Min Price'),
        ('time_to_max_pnl_seconds', 180, 'Time to MFE'),
        ('time_to_min_pnl_seconds', 30, 'Time to MAE'),
        ('be_triggered', True, 'BE Triggered'),
        ('be_triggered_pnl_pct', 0.16, 'BE PnL'),
        ('trailing_activated', True, 'Trailing Activated'),
        ('trailing_final_sl_price', 0.7770, 'Trailing Final SL'),
        ('trailing_final_distance_pct', 0.10, 'Trailing Distance'),
        ('stagnation_detected', False, 'Stagnation'),
    ]
    
    all_ok = True
    for col, expected, label in checks:
        actual = m.get(col)
        if actual is None:
            status = "❌ NULL"
            all_ok = False
        elif isinstance(expected, bool):
            status = "✅" if actual == expected else f"❌ {actual}"
            if actual != expected:
                all_ok = False
        elif isinstance(expected, float):
            if abs(float(actual) - expected) < 0.001:
                status = f"✅ {actual}"
            else:
                status = f"⚠️ {actual} (attendu {expected})"
        else:
            status = f"✅ {actual}" if actual == expected else f"⚠️ {actual}"
        
        print(f"   {label:20} : {status}")
    
    # Nettoyage du test
    cur.execute("DELETE FROM trade_atr_metrics WHERE trade_id = %s", (test_trade_id,))
    conn.commit()
    print(f"\n🧹 Métrique test supprimée")
    
    if all_ok:
        print(f"\n✅ MODE FIXE: TOUTES LES COLONNES SE REMPLISSENT CORRECTEMENT!")
    else:
        print(f"\n⚠️ MODE FIXE: CERTAINES COLONNES NE SONT PAS REMPLIES")
else:
    print(f"\n❌ Métrique NON trouvée")

cur.close()
conn.close()
print("="*70)
