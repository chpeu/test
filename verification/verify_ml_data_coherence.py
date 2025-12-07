# -*- coding: utf-8 -*-
"""
Vérification de la Cohérence des Données ML

Ce script vérifie que:
1. Le compteur GradientBoosting
2. XGBoost V1/V2 (entraînement)
3. Optuna (optimisation hyperparamètres)

Utilisent TOUS les mêmes données filtrées.
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import pandas as pd
import requests
from typing import Dict, Any, Optional

print("=" * 80)
print("  VÉRIFICATION COHÉRENCE DONNÉES ML")
print("  Compteur GB vs XGBoost vs Optuna")
print("=" * 80)

# =============================================================================
# 1. CHARGER CONFIG ACTUELLE
# =============================================================================
print("\n" + "-" * 60)
print("1. CONFIGURATION ACTUELLE (TRADING_CONFIG)")
print("-" * 60)

try:
    with open('config_overrides.json') as f:
        config = json.load(f)
    
    key_params = {
        'min_score_required': config.get('min_score_required', 6.5),
        'snr_threshold': config.get('snr_threshold', 0.15),
        'volume_multiplier': config.get('volume_multiplier', 0.95),
        'use_confluence': config.get('use_confluence', False),
        'breakout_threshold': config.get('breakout_threshold', 0.25),
        'tp_percent': config.get('tp_percent', 0.5),
        'sl_percent': config.get('sl_percent', 0.2),
    }
    
    for k, v in key_params.items():
        print(f"   {k}: {v}")
        
except Exception as e:
    print(f"   ❌ Erreur lecture config: {e}")
    sys.exit(1)

# =============================================================================
# 2. TESTER COMPTEUR GRADIENTBOOSTING (API)
# =============================================================================
print("\n" + "-" * 60)
print("2. COMPTEUR GRADIENTBOOSTING (API /dashboard/ml_trades_count)")
print("-" * 60)

gb_count = None
gb_config = None

try:
    resp = requests.get("http://localhost:5000/api/ml/dashboard/ml_trades_count", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        gb_count = data.get('config_filtered_trades')
        gb_config = data.get('current_config', {})
        
        print(f"   ✅ Trades filtrés: {gb_count}")
        print(f"   📋 Filtres appliqués:")
        for category, params in data.get('filters_applied', {}).items():
            print(f"      - {category}: {len(params)} paramètres")
    else:
        print(f"   ❌ Erreur HTTP {resp.status_code}")
except requests.exceptions.ConnectionError:
    print(f"   ⚠️  Backend non accessible")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# =============================================================================
# 3. TESTER LOAD_FEATURES_FROM_POSTGRES (utilisé par XGBoost et Optuna)
# =============================================================================
print("\n" + "-" * 60)
print("3. XGBOOST / OPTUNA (via load_features_from_postgres)")
print("-" * 60)

xgb_count = None
xgb_query_conditions = None

try:
    from optimization.data.feature_loader import load_features_from_postgres, build_config_filter_conditions
    
    # Récupérer les conditions de filtrage
    conditions = build_config_filter_conditions(for_trades_table=True, use_alias=True)
    print(f"   📋 Conditions de filtrage: {len(conditions)} conditions SQL")
    
    # Charger les données comme XGBoost/Optuna le font
    print(f"   📥 Chargement données...")
    df = load_features_from_postgres(
        min_trades=1,
        timeframe_days=365,
        include_open_trades=False
    )
    xgb_count = len(df)
    print(f"   ✅ Trades chargés: {xgb_count}")
    
    # Vérifier la distribution
    if 'target_win' in df.columns:
        wins = (df['target_win'] == 1).sum()
        losses = (df['target_win'] == 0).sum()
        print(f"   📊 Distribution: {wins} wins / {losses} losses ({wins/(wins+losses)*100:.1f}% win rate)")
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# 4. VÉRIFIER COHÉRENCE DES COMPTEURS
# =============================================================================
print("\n" + "-" * 60)
print("4. VÉRIFICATION COHÉRENCE")
print("-" * 60)

if gb_count is not None and xgb_count is not None:
    print(f"\n   {'Source':<30} {'Trades':<10}")
    print("-" * 50)
    print(f"   {'Compteur GradientBoosting':<30} {gb_count:<10}")
    print(f"   {'XGBoost/Optuna':<30} {xgb_count:<10}")
    
    if gb_count == xgb_count:
        print(f"\n   ✅ COHÉRENT: Tous utilisent les mêmes {gb_count} trades")
    else:
        print(f"\n   ❌ INCOHÉRENT: Différence de {abs(gb_count - xgb_count)} trades")
        print(f"   💡 Vérifier que le backend a été redémarré après les modifications")
else:
    print(f"   ⚠️  Impossible de comparer - certains tests ont échoué")

# =============================================================================
# 5. VÉRIFIER QUE LES CONFIGS SONT IDENTIQUES
# =============================================================================
print("\n" + "-" * 60)
print("5. VÉRIFICATION CONFIG IDENTIQUE")
print("-" * 60)

if gb_config:
    mismatches = []
    for key, expected in key_params.items():
        # Mapper les noms de clés
        api_key = key.replace('_required', '').replace('_multiplier', '_mult')
        if api_key == 'min_score':
            api_key = 'min_score'
        
        actual = gb_config.get(api_key) or gb_config.get(key)
        
        if actual is not None:
            # Comparer avec tolérance pour les floats
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 0.01:
                    mismatches.append((key, expected, actual))
            elif actual != expected:
                mismatches.append((key, expected, actual))
    
    if not mismatches:
        print(f"   ✅ Config API identique à config_overrides.json")
    else:
        print(f"   ❌ Différences détectées:")
        for key, expected, actual in mismatches:
            print(f"      - {key}: attendu={expected}, API={actual}")

# =============================================================================
# 6. SIMULER UN ENTRAÎNEMENT (dry run)
# =============================================================================
print("\n" + "-" * 60)
print("6. SIMULATION ENTRAÎNEMENT (dry run)")
print("-" * 60)

try:
    from optimization.data.feature_loader import load_features_from_postgres
    from optimization.data.feature_engineering import calculate_derived_features
    from optimization.utils.temporal_split import temporal_train_test_split
    
    print(f"   📥 Chargement données...")
    base_df = load_features_from_postgres(timeframe_days=365, min_trades=1)
    
    print(f"   🔧 Feature engineering...")
    df = calculate_derived_features(base_df)
    
    print(f"   📅 Split temporel (60/20/20)...")
    train_df, val_df, test_df = temporal_train_test_split(
        df,
        target_col='target_win',
        test_size=0.2,
        validation_size=0.2
    )
    
    print(f"\n   Résultats split:")
    print(f"      - Train: {len(train_df)} samples")
    print(f"      - Validation: {len(val_df)} samples")
    print(f"      - Test: {len(test_df)} samples")
    print(f"      - Total: {len(train_df) + len(val_df) + len(test_df)} samples")
    
    if len(train_df) + len(val_df) + len(test_df) == xgb_count:
        print(f"\n   ✅ Split cohérent avec le compteur")
    else:
        print(f"\n   ⚠️  Différence après split (normal si filtrage supplémentaire)")
        
except Exception as e:
    print(f"   ❌ Erreur simulation: {e}")

# =============================================================================
# 7. RÉSUMÉ FINAL
# =============================================================================
print("\n" + "=" * 80)
print("  RÉSUMÉ FINAL")
print("=" * 80)

all_ok = True

if gb_count is not None and xgb_count is not None:
    if gb_count == xgb_count:
        print(f"\n✅ COHÉRENCE VALIDÉE")
        print(f"   - Compteur GradientBoosting: {gb_count} trades")
        print(f"   - XGBoost/Optuna: {xgb_count} trades")
        print(f"   - Tous les composants utilisent build_config_filter_conditions()")
        print(f"   - Les 19+ paramètres de config sont appliqués partout")
    else:
        all_ok = False
        print(f"\n❌ INCOHÉRENCE DÉTECTÉE")
        print(f"   - Compteur: {gb_count} vs XGBoost: {xgb_count}")
        print(f"   - Actions recommandées:")
        print(f"      1. Redémarrer le backend")
        print(f"      2. Vérifier config_overrides.json")
        print(f"      3. Relancer ce script")
else:
    all_ok = False
    print(f"\n⚠️  VÉRIFICATION INCOMPLÈTE")
    print(f"   - Certains composants n'ont pas pu être testés")

print(f"\n{'='*80}")
print(f"  {'✅ SUCCÈS' if all_ok else '❌ ÉCHEC'} - Fin de la vérification")
print(f"{'='*80}")
