"""
Script pour analyser pourquoi ml_prediction et ml_features ne sont pas propagés
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import json

conn = sqlite3.connect('data/analytics.db')
cursor = conn.cursor()

print("=" * 100)
print("ANALYSE DE LA PROPAGATION ML")
print("=" * 100)

# 1. Vérifier les 5 derniers trades
cursor.execute('''
    SELECT 
        id,
        symbol,
        direction,
        ml_confidence,
        ml_prediction,
        ml_features
    FROM trades 
    ORDER BY id DESC 
    LIMIT 5
''')

print("\n📊 5 derniers trades:")
print("-" * 100)
for row in cursor.fetchall():
    trade_id, symbol, direction, ml_conf, ml_pred, ml_feat = row
    
    # Parser ml_features si présent
    features_status = "NULL"
    if ml_feat:
        try:
            feat_dict = json.loads(ml_feat)
            if feat_dict and isinstance(feat_dict, dict):
                features_status = f"populated ({len(feat_dict)} features)"
            else:
                features_status = "json_null"
        except:
            features_status = "invalid_json"
    
    print(f"ID={trade_id:3d} | {symbol:15s} {direction:5s} | ml_conf={ml_conf} | ml_pred={ml_pred} | ml_feat={features_status}")

# 2. Stats globales
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ml_confidence IS NOT NULL THEN 1 ELSE 0 END) as with_confidence,
        SUM(CASE WHEN ml_prediction IS NOT NULL THEN 1 ELSE 0 END) as with_prediction,
        SUM(CASE WHEN ml_features IS NOT NULL AND ml_features != 'null' THEN 1 ELSE 0 END) as with_features
    FROM trades
''')

stats = cursor.fetchone()
print("\n" + "=" * 100)
print("📈 STATS GLOBALES:")
print(f"  Total trades: {stats[0]}")
print(f"  Avec ml_confidence: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
print(f"  Avec ml_prediction: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
print(f"  Avec ml_features: {stats[3]} ({stats[3]/stats[0]*100:.1f}%)")

# 3. Vérifier un exemple de ml_features s'il existe
cursor.execute('''
    SELECT ml_features 
    FROM trades 
    WHERE ml_features IS NOT NULL 
      AND ml_features != 'null' 
    LIMIT 1
''')

result = cursor.fetchone()
if result:
    print("\n" + "=" * 100)
    print("🔍 EXEMPLE DE ml_features:")
    try:
        features = json.loads(result[0])
        print(json.dumps(features, indent=2))
    except:
        print(f"  Erreur de parsing: {result[0]}")
else:
    print("\n" + "=" * 100)
    print("❌ AUCUN ml_features trouvé dans la base")
    print("\n🔍 DIAGNOSTIC:")
    print("  1. Le filtre ML dans scanner_loop.py est probablement DÉSACTIVÉ")
    print("  2. Vérifier config_overrides.json: 'ml_filter_enabled' devrait être true")
    print("  3. Le filtre GradientBoosting dans position_manager.py calcule gb_ml_prediction/gb_ml_features")
    print("  4. Mais ces valeurs ne sont assignées à la position QUE si gb_enabled=true")
    print("\n💡 SOLUTION:")
    print("  Option 1: Activer ml_filter_enabled dans config_overrides.json")
    print("  Option 2: Vérifier que gb_filter_enabled=true ET que les features GB sont bien assignées")

conn.close()
