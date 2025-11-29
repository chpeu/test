# -*- coding: utf-8 -*-
"""
Script de verification complete du systeme ML
Execute toutes les verifications pour s'assurer que le systeme est optimal et sans bug
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from urllib.parse import quote_plus

# =============================================================================
# CONFIGURATION
# =============================================================================

CHECKS = []
ERRORS = []
WARNINGS = []

def log_check(name, status, details=""):
    """Logger un check"""
    icon = "✅" if status == "OK" else "⚠️" if status == "WARNING" else "❌"
    CHECKS.append({"name": name, "status": status, "details": details})
    print(f"  {icon} {name}: {details}")
    if status == "ERROR":
        ERRORS.append(f"{name}: {details}")
    elif status == "WARNING":
        WARNINGS.append(f"{name}: {details}")

def get_db_connection():
    """Connexion DB"""
    env_vars = {}
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip()
    
    password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
    conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
    return create_engine(conn_str)

# =============================================================================
# VERIFICATIONS
# =============================================================================

print("=" * 70)
print("  VERIFICATION COMPLETE DU SYSTEME ML")
print("=" * 70)
print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# -----------------------------------------------------------------------------
# 1. FICHIERS ET CONFIGURATION
# -----------------------------------------------------------------------------
print("\n📁 1. FICHIERS ET CONFIGURATION")
print("-" * 50)

# Config overrides
config_path = Path("config_overrides.json")
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
    log_check("config_overrides.json", "OK", f"{len(config)} parametres")
    
    # Verifier parametres GB
    required_params = ['gb_n_estimators', 'gb_max_depth', 'gb_learning_rate']
    missing = [p for p in required_params if p not in config]
    if missing:
        log_check("Parametres GB", "WARNING", f"Manquants: {missing}")
    else:
        log_check("Parametres GB", "OK", f"n_est={config.get('gb_n_estimators')}, depth={config.get('gb_max_depth')}")
else:
    log_check("config_overrides.json", "ERROR", "Fichier non trouve")

# Modele sauvegarde
model_path = Path("optimization/saved_models/best_classifier_latest.pkl")
if model_path.exists():
    import joblib
    try:
        model = joblib.load(model_path)
        log_check("Modele sauvegarde", "OK", f"Type: {type(model).__name__}")
    except Exception as e:
        log_check("Modele sauvegarde", "ERROR", str(e))
else:
    log_check("Modele sauvegarde", "ERROR", "Fichier non trouve")

# Metadata
meta_path = Path("optimization/saved_models/best_classifier_metadata.json")
if meta_path.exists():
    with open(meta_path) as f:
        meta = json.load(f)
    n_features = meta.get('n_features', 0)
    n_samples = meta.get('n_samples', 0)
    log_check("Metadata modele", "OK", f"{n_features} features, {n_samples} samples")
    
    # Verifier coherence features
    feature_cols = meta.get('feature_cols', [])
    if len(feature_cols) != n_features:
        log_check("Coherence features", "WARNING", f"n_features={n_features} vs len(feature_cols)={len(feature_cols)}")
    else:
        log_check("Coherence features", "OK", f"{n_features} features coherentes")
else:
    log_check("Metadata modele", "ERROR", "Fichier non trouve")

# -----------------------------------------------------------------------------
# 2. BASE DE DONNEES
# -----------------------------------------------------------------------------
print("\n🗄️ 2. BASE DE DONNEES")
print("-" * 50)

try:
    engine = get_db_connection()
    
    # Compter trades
    trades_count = pd.read_sql("SELECT COUNT(*) as cnt FROM trades", engine).iloc[0]['cnt']
    log_check("Table trades", "OK", f"{trades_count} trades")
    
    # Compter ml_features
    try:
        ml_count = pd.read_sql("SELECT COUNT(*) as cnt FROM ml_features WHERE target_pnl IS NOT NULL", engine).iloc[0]['cnt']
        log_check("Vue ml_features", "OK", f"{ml_count} samples")
    except:
        log_check("Vue ml_features", "ERROR", "Vue non accessible")
    
    # Compter ml_features_clean
    try:
        clean_count = pd.read_sql("SELECT COUNT(*) as cnt FROM ml_features_clean", engine).iloc[0]['cnt']
        log_check("Table ml_features_clean", "OK", f"{clean_count} samples nettoyees")
    except:
        log_check("Table ml_features_clean", "WARNING", "Table non creee (executer clean_ml_data_final.py)")
    
    # Verifier trades manuels
    manual_count = pd.read_sql("SELECT COUNT(*) as cnt FROM trades WHERE exit_reason = 'MANUAL'", engine).iloc[0]['cnt']
    if manual_count > 0:
        log_check("Trades manuels", "WARNING", f"{manual_count} trades manuels (seront exclus)")
    else:
        log_check("Trades manuels", "OK", "0 trades manuels")
    
    engine.dispose()
except Exception as e:
    log_check("Connexion DB", "ERROR", str(e))

# -----------------------------------------------------------------------------
# 3. MODELE ML
# -----------------------------------------------------------------------------
print("\n🤖 3. MODELE ML")
print("-" * 50)

try:
    from optimization.predictor_optimized import OptimizedPredictor
    
    predictor = OptimizedPredictor()
    if predictor.model is not None:
        log_check("Predictor charge", "OK", f"Model ready")
        
        # Test prediction
        test_features = {
            'rsi_1m': 45.0, 'rsi_5m': 50.0,
            'macd_hist_1m': 0.001, 'macd_hist_5m': 0.002,
            'adx_1m': 25.0, 'adx_5m': 22.0,
            'atr_pct_1m': 0.5, 'atr_pct_5m': 0.4,
            'volume_ratio_1m': 1.2, 'volume_ratio_5m': 1.1
        }
        
        try:
            should_trade, proba = predictor.predict(test_features)
            if proba is not None and 0 <= proba <= 1:
                log_check("Test prediction", "OK", f"proba={proba:.3f}, trade={should_trade}")
            else:
                log_check("Test prediction", "WARNING", f"proba={proba} (valeur inattendue)")
        except Exception as e:
            log_check("Test prediction", "ERROR", str(e))
    else:
        log_check("Predictor charge", "ERROR", "Modele non charge")
except Exception as e:
    log_check("Import Predictor", "ERROR", str(e))

# -----------------------------------------------------------------------------
# 4. METRIQUES ML
# -----------------------------------------------------------------------------
print("\n📊 4. METRIQUES ML")
print("-" * 50)

if meta_path.exists():
    with open(meta_path) as f:
        meta = json.load(f)
    
    # Extraire metriques (structure: metrics.test_acc, metrics.test_f1, etc.)
    metrics = meta.get('metrics', {})
    accuracy = metrics.get('test_acc', 0)
    f1 = metrics.get('test_f1', 0)
    precision = metrics.get('test_precision', 0)
    gap = metrics.get('gap', 0)
    
    # Verifier objectifs
    if accuracy >= 0.62:
        log_check("Accuracy >= 62%", "OK", f"{accuracy*100:.1f}%")
    elif accuracy >= 0.50:
        log_check("Accuracy >= 62%", "WARNING", f"{accuracy*100:.1f}% (objectif: 62%)")
    else:
        log_check("Accuracy >= 62%", "ERROR", f"{accuracy*100:.1f}% < 50%")
    
    if f1 >= 0.50:
        log_check("F1 >= 0.50", "OK", f"{f1:.3f}")
    else:
        log_check("F1 >= 0.50", "WARNING", f"{f1:.3f} < 0.50")
    
    if precision >= 0.55:
        log_check("Precision >= 0.55", "OK", f"{precision:.3f}")
    else:
        log_check("Precision >= 0.55", "WARNING", f"{precision:.3f} < 0.55")
    
    if gap <= 0.12:
        log_check("Gap <= 12%", "OK", f"{gap*100:.1f}%")
    elif gap <= 0.20:
        log_check("Gap <= 12%", "WARNING", f"{gap*100:.1f}% (objectif: 12%)")
    else:
        log_check("Gap <= 12%", "ERROR", f"{gap*100:.1f}% > 20%")

# -----------------------------------------------------------------------------
# 5. FEATURE ENGINEERING
# -----------------------------------------------------------------------------
print("\n🔧 5. FEATURE ENGINEERING")
print("-" * 50)

try:
    from optimization.data.feature_engineering import calculate_derived_features
    
    # Test avec donnees factices
    test_df = pd.DataFrame({
        'timestamp': [pd.Timestamp.now()],
        'rsi_1m': [50.0], 'rsi_5m': [45.0],
        'rsi_prev_1m': [48.0], 'rsi_prev_5m': [47.0],
        'macd_hist_1m': [0.01], 'macd_hist_5m': [0.02],
        'macd_hist_prev_1m': [0.005], 'macd_hist_prev_5m': [0.015],
        'adx_1m': [25.0], 'adx_5m': [22.0],
        'di_plus_1m': [30.0], 'di_minus_1m': [20.0],
        'di_plus_5m': [28.0], 'di_minus_5m': [22.0],
        'di_gap_1m': [10.0], 'di_gap_5m': [6.0],
        'atr_pct_1m': [0.5], 'atr_pct_5m': [0.4],
        'ema_diff_pct_1m': [0.1], 'ema_diff_pct_5m': [0.05],
        'volume_ratio_1m': [1.2], 'volume_ratio_5m': [1.1],
        'volume_spike_1m': [False], 'volume_spike_5m': [False],
        'bb_width_1m': [2.5], 'bb_width_5m': [2.0],
        'bb_distance_to_lower_1m': [0.5], 'bb_distance_to_upper_1m': [0.5],
        'bb_distance_to_lower_5m': [0.4], 'bb_distance_to_upper_5m': [0.6],
        'snr_passed_1m': [True], 'snr_passed_5m': [True],
        'breakout_passed_1m': [True], 'breakout_passed_5m': [True],
        'wick_passed_1m': [True], 'wick_passed_5m': [True],
        'atr_optimal_passed_1m': [True], 'atr_optimal_passed_5m': [True],
        'volume_filter_passed_1m': [True], 'volume_filter_passed_5m': [True]
    })
    
    df_eng = calculate_derived_features(test_df)
    n_original = len(test_df.columns)
    n_derived = len(df_eng.columns)
    
    # Verifier features temporelles
    temporal_features = ['hour_utc', 'session_asia', 'session_europe', 'session_usa']
    missing_temporal = [f for f in temporal_features if f not in df_eng.columns]
    
    if missing_temporal:
        log_check("Features temporelles", "WARNING", f"Manquantes: {missing_temporal}")
    else:
        log_check("Features temporelles", "OK", "Toutes presentes")
    
    log_check("Feature engineering", "OK", f"{n_original} → {n_derived} features (+{n_derived-n_original})")
    
except Exception as e:
    log_check("Feature engineering", "ERROR", str(e))

# -----------------------------------------------------------------------------
# 6. API ENDPOINTS
# -----------------------------------------------------------------------------
print("\n🌐 6. API ENDPOINTS")
print("-" * 50)

import requests

try:
    # Test endpoint ml_trades_count
    response = requests.get("http://localhost:8000/api/ml/dashboard/ml_trades_count", timeout=5)
    if response.status_code == 200:
        data = response.json()
        log_check("Endpoint ml_trades_count", "OK", f"{data.get('config_filtered_trades', 0)} trades ML")
    else:
        log_check("Endpoint ml_trades_count", "ERROR", f"Status {response.status_code}")
except requests.exceptions.ConnectionError:
    log_check("Endpoint ml_trades_count", "WARNING", "Backend non accessible (normal si arrete)")
except Exception as e:
    log_check("Endpoint ml_trades_count", "ERROR", str(e))

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME DE LA VERIFICATION")
print("=" * 70)

n_ok = len([c for c in CHECKS if c['status'] == 'OK'])
n_warn = len([c for c in CHECKS if c['status'] == 'WARNING'])
n_err = len([c for c in CHECKS if c['status'] == 'ERROR'])

print(f"\n  Total: {len(CHECKS)} verifications")
print(f"    ✅ OK:       {n_ok}")
print(f"    ⚠️  WARNING: {n_warn}")
print(f"    ❌ ERROR:    {n_err}")

if ERRORS:
    print(f"\n  ❌ ERREURS A CORRIGER:")
    for err in ERRORS:
        print(f"     - {err}")

if WARNINGS:
    print(f"\n  ⚠️  AVERTISSEMENTS:")
    for warn in WARNINGS[:5]:  # Max 5
        print(f"     - {warn}")

if n_err == 0:
    print(f"\n  🎉 SYSTEME ML OPERATIONNEL")
    if n_warn == 0:
        print(f"     Aucun probleme detecte!")
    else:
        print(f"     {n_warn} avertissements mineurs")
else:
    print(f"\n  🚨 SYSTEME ML NECESSITE CORRECTIONS")
    print(f"     Corriger {n_err} erreurs avant utilisation")

print("\n" + "=" * 70)
