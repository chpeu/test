"""
Vérifier que les colonnes mode FIXE sont correctement remplies
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*70)
print("🔍 VÉRIFICATION COLONNES MODE FIXE")
print("="*70)

# Récupérer la dernière métrique insérée
cur.execute("""
    SELECT * FROM trade_atr_metrics 
    ORDER BY created_at DESC 
    LIMIT 1
""")
m = dict(cur.fetchone())

# Colonnes importantes pour MODE FIXE
fixe_columns = {
    'Identité': ['trade_id', 'created_at'],
    'ATR Entry': ['entry_atr_1m', 'entry_atr_5m', 'entry_atr_pct_1m', 'entry_atr_pct_5m'],
    'Params Config': ['param_atr_mult_sl', 'param_atr_mult_tp', 'param_be_atr_mult', 
                      'param_trailing_trigger_mult', 'param_trailing_distance_mult'],
    'Niveaux Calculés': ['calculated_sl_price', 'calculated_tp_price', 
                         'calculated_sl_pct', 'calculated_tp_pct',
                         'calculated_be_trigger_pnl_pct', 'calculated_trailing_trigger_pnl_pct'],
    'Break-Even': ['be_triggered', 'be_triggered_at', 'be_triggered_pnl_pct', 'be_price_at_trigger'],
    'Trailing Stop': ['trailing_activated', 'trailing_activated_at', 
                      'trailing_final_distance_pct', 'trailing_final_sl_price'],
    'MFE/MAE': ['max_pnl_reached', 'min_pnl_reached', 
                'max_price_reached', 'min_price_reached',
                'time_to_max_pnl_seconds', 'time_to_min_pnl_seconds'],
    'Stagnation': ['stagnation_detected', 'stagnation_detected_at', 
                   'stagnation_duration_seconds', 'stagnation_pnl_at_exit'],
    'SL MEXC': ['sl_mexc_price', 'sl_mexc_pct', 'sl_mexc_margin_used',
                'sl_mexc_touched', 'sl_mexc_touched_at'],
    'Session/Régime': ['session_market', 'hour_utc', 'day_of_week', 'is_weekend'],
}

print(f"\n📊 Métrique ID: {m.get('id')} | Trade: {m.get('trade_id', 'N/A')[:8]}...")
print(f"   Created: {m.get('created_at')}")

total_cols = 0
filled_cols = 0
null_cols = []

for category, columns in fixe_columns.items():
    print(f"\n📋 {category}:")
    for col in columns:
        total_cols += 1
        val = m.get(col)
        if val is not None:
            filled_cols += 1
            # Formater la valeur
            if isinstance(val, float):
                val_str = f"{val:.4f}"
            elif isinstance(val, bool):
                val_str = "✅" if val else "❌"
            else:
                val_str = str(val)[:30]
            print(f"   ✅ {col}: {val_str}")
        else:
            null_cols.append(col)
            print(f"   ⚠️ {col}: NULL")

# Résumé
print(f"\n{'='*70}")
print(f"📈 RÉSUMÉ")
print(f"   Colonnes remplies: {filled_cols}/{total_cols} ({filled_cols/total_cols*100:.0f}%)")
print(f"   Colonnes NULL: {len(null_cols)}")

if null_cols:
    print(f"\n⚠️ Colonnes NULL à vérifier:")
    for col in null_cols:
        print(f"   - {col}")

# Vérifier si les colonnes critiques mode FIXE sont remplies
critical_fixe = ['max_pnl_reached', 'min_pnl_reached', 'be_triggered', 'trailing_activated']
critical_ok = all(col in [c for c in fixe_columns['MFE/MAE'] + fixe_columns['Break-Even'] + fixe_columns['Trailing Stop'] 
                          if m.get(c) is not None or isinstance(m.get(c), bool)] for col in critical_fixe)

print(f"\n🎯 COLONNES CRITIQUES MODE FIXE:")
for col in critical_fixe:
    val = m.get(col)
    if val is not None or isinstance(val, bool):
        print(f"   ✅ {col}: {val}")
    else:
        print(f"   ❌ {col}: NULL (PROBLÈME!)")

cur.close()
conn.close()
print("="*70)
