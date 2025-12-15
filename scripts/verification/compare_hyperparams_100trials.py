#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 COMPARAISON HYPERPARAMÈTRES: ACTUELS vs ANTI-OVERFIT
=========================================================
Test rigoureux sur 100 trials pour comparer les deux configurations.

Config A (Actuelle):
- n_estimators: 271, max_depth: 6, learning_rate: 0.22
- min_samples_split: 48, min_samples_leaf: 38
- subsample: 0.73, max_features: sqrt

Config B (Anti-Overfit):
- n_estimators: 150, max_depth: 3, learning_rate: 0.03
- min_samples_split: 80, min_samples_leaf: 60
- subsample: 0.7, max_features: 0.5
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

# Seed pour reproductibilité de base
BASE_SEED = 42
np.random.seed(BASE_SEED)

PROJECT_ROOT = Path(__file__).parent

print("=" * 70)
print("  COMPARAISON HYPERPARAMÈTRES: 100 TRIALS")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# =============================================================================
# CONFIGURATIONS À COMPARER
# =============================================================================

CONFIG_A = {
    'name': 'ACTUELLE (UI)',
    'params': {
        'n_estimators': 271,
        'max_depth': 6,
        'learning_rate': 0.22,
        'min_samples_split': 48,
        'min_samples_leaf': 38,
        'subsample': 0.73,
        'max_features': 'sqrt',
    }
}

CONFIG_B = {
    'name': 'ANTI-OVERFIT',
    'params': {
        'n_estimators': 150,
        'max_depth': 3,
        'learning_rate': 0.03,
        'min_samples_split': 80,
        'min_samples_leaf': 60,
        'subsample': 0.70,
        'max_features': 0.5,
    }
}

N_TRIALS = 100

# =============================================================================
# 1. CHARGEMENT DES DONNÉES
# =============================================================================
print("\n[1/4] Chargement des données...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades chargés: {len(df)}")

df = calculate_derived_features(df)

# Features sélectionnées
SELECTED_FEATURES = [
    "di_plus_1m", "bb_distance_to_upper_5m", "ema_diff_pct_1m", "rsi_1m",
    "di_plus_5m", "ema_diff_pct_5m", "bb_distance_to_upper_1m", "bb_distance_to_lower_1m",
    "atr_pct_1m", "rsi_5m", "bb_width_5m", "bb_distance_to_lower_5m",
    "macd_momentum_5m", "trend_strength_1m", "rsi_prev_5m", "volatility_momentum_product",
    "di_gap_1m", "macd_hist_prev_1m", "rsi_prev_1m", "macd_hist_1m",
    "trend_strength_5m", "momentum_divergence", "bb_width_1m", "di_minus_5m",
    "momentum_5m", "momentum_1m", "volume_divergence", "adx_5m"
]

available_features = [f for f in SELECTED_FEATURES if f in df.columns]
print(f"   Features: {len(available_features)}/{len(SELECTED_FEATURES)}")

X = df[available_features].copy()
y = df['target_win'].astype(int).copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)

print(f"   Win rate: {y.mean()*100:.1f}%")

# =============================================================================
# 2. FONCTION DE TEST
# =============================================================================

def run_single_trial(
    X: pd.DataFrame, 
    y: pd.Series, 
    params: Dict,
    seed: int
) -> Dict:
    """Exécute un trial avec un seed donné"""
    
    # Split avec seed variable
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    
    # Imputer + Scaler
    imputer = SimpleImputer(strategy='median')
    scaler = StandardScaler()
    
    X_train_clean = pd.DataFrame(
        imputer.fit_transform(X_train), 
        columns=X_train.columns
    )
    X_test_clean = pd.DataFrame(
        imputer.transform(X_test), 
        columns=X_test.columns
    )
    
    X_train_scaled = scaler.fit_transform(X_train_clean)
    X_test_scaled = scaler.transform(X_test_clean)
    
    # Entraîner avec random_state fixe (seul le split change)
    model = GradientBoostingClassifier(**params, random_state=BASE_SEED)
    model.fit(X_train_scaled, y_train)
    
    # Évaluer
    train_pred = model.predict(X_train_scaled)
    test_pred = model.predict(X_test_scaled)
    
    train_acc = accuracy_score(y_train, train_pred)
    test_acc = accuracy_score(y_test, test_pred)
    test_f1 = f1_score(y_test, test_pred)
    test_precision = precision_score(y_test, test_pred, zero_division=0)
    test_recall = recall_score(y_test, test_pred, zero_division=0)
    
    gap = train_acc - test_acc
    
    return {
        'train_acc': train_acc,
        'test_acc': test_acc,
        'gap': gap,
        'f1': test_f1,
        'precision': test_precision,
        'recall': test_recall
    }


def run_100_trials(config: Dict) -> Dict:
    """Exécute 100 trials pour une configuration"""
    
    results = {
        'train_acc': [],
        'test_acc': [],
        'gap': [],
        'f1': [],
        'precision': [],
        'recall': []
    }
    
    for trial in range(N_TRIALS):
        seed = BASE_SEED + trial
        trial_result = run_single_trial(X, y, config['params'], seed)
        
        for key in results:
            results[key].append(trial_result[key])
        
        if (trial + 1) % 20 == 0:
            print(f"      Trial {trial + 1}/{N_TRIALS}...")
    
    # Statistiques
    stats = {}
    for key in results:
        arr = np.array(results[key])
        stats[key] = {
            'mean': arr.mean(),
            'std': arr.std(),
            'min': arr.min(),
            'max': arr.max(),
            'median': np.median(arr)
        }
    
    return stats


# =============================================================================
# 3. EXÉCUTION DES TESTS
# =============================================================================
print(f"\n[2/4] Test Config A: {CONFIG_A['name']} ({N_TRIALS} trials)...")
stats_A = run_100_trials(CONFIG_A)

print(f"\n[3/4] Test Config B: {CONFIG_B['name']} ({N_TRIALS} trials)...")
stats_B = run_100_trials(CONFIG_B)

# =============================================================================
# 4. RÉSULTATS
# =============================================================================
print("\n" + "=" * 70)
print("  RÉSULTATS COMPARATIFS")
print("=" * 70)

def print_comparison(metric_name: str, display_name: str, higher_better: bool = True):
    """Affiche la comparaison pour une métrique"""
    mean_A = stats_A[metric_name]['mean']
    std_A = stats_A[metric_name]['std']
    mean_B = stats_B[metric_name]['mean']
    std_B = stats_B[metric_name]['std']
    
    diff = mean_A - mean_B
    winner = "A" if (diff > 0) == higher_better else "B"
    
    print(f"\n📊 {display_name}:")
    print(f"   Config A ({CONFIG_A['name']}): {mean_A:.4f} ± {std_A:.4f}")
    print(f"   Config B ({CONFIG_B['name']}): {mean_B:.4f} ± {std_B:.4f}")
    print(f"   Différence: {diff:+.4f} → {'🏆 Config ' + winner + ' gagne' if abs(diff) > 0.005 else '🤝 Égalité'}")

print_comparison('test_acc', 'TEST ACCURACY', higher_better=True)
print_comparison('train_acc', 'TRAIN ACCURACY', higher_better=True)
print_comparison('gap', 'OVERFITTING GAP (train - test)', higher_better=False)
print_comparison('f1', 'F1 SCORE', higher_better=True)
print_comparison('precision', 'PRECISION', higher_better=True)
print_comparison('recall', 'RECALL', higher_better=True)

# Stabilité
print(f"\n📊 STABILITÉ (écart-type plus bas = plus stable):")
print(f"   Config A std(test_acc): {stats_A['test_acc']['std']:.4f}")
print(f"   Config B std(test_acc): {stats_B['test_acc']['std']:.4f}")
winner_stability = "A" if stats_A['test_acc']['std'] < stats_B['test_acc']['std'] else "B"
print(f"   → Config {winner_stability} est plus stable")

# Recommandation finale
print("\n" + "=" * 70)
print("  RECOMMANDATION")
print("=" * 70)

# Score composite: test_acc (40%) + f1 (30%) + stabilité (20%) + anti-overfit (10%)
score_A = (
    stats_A['test_acc']['mean'] * 0.4 +
    stats_A['f1']['mean'] * 0.3 +
    (1 - stats_A['test_acc']['std']) * 0.2 +
    (1 - stats_A['gap']['mean']) * 0.1
)
score_B = (
    stats_B['test_acc']['mean'] * 0.4 +
    stats_B['f1']['mean'] * 0.3 +
    (1 - stats_B['test_acc']['std']) * 0.2 +
    (1 - stats_B['gap']['mean']) * 0.1
)

print(f"\n   Score composite Config A: {score_A:.4f}")
print(f"   Score composite Config B: {score_B:.4f}")

if score_A > score_B:
    print(f"\n   🏆 RECOMMANDATION: Garder Config A ({CONFIG_A['name']})")
else:
    print(f"\n   🏆 RECOMMANDATION: Utiliser Config B ({CONFIG_B['name']})")

print(f"\n   Différence de score: {abs(score_A - score_B):.4f}")
if abs(score_A - score_B) < 0.01:
    print("   ⚠️ Différence faible, les deux configs sont équivalentes")

# Sauvegarder résultats
results_file = PROJECT_ROOT / "hyperparams_comparison_results.json"
import json
with open(results_file, 'w') as f:
    json.dump({
        'config_a': {
            'name': CONFIG_A['name'],
            'params': CONFIG_A['params'],
            'stats': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in stats_A.items()},
            'score': float(score_A)
        },
        'config_b': {
            'name': CONFIG_B['name'],
            'params': CONFIG_B['params'],
            'stats': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in stats_B.items()},
            'score': float(score_B)
        },
        'n_trials': N_TRIALS,
        'winner': 'A' if score_A > score_B else 'B',
        'timestamp': datetime.now().isoformat()
    }, f, indent=2)

print(f"\n✅ Résultats sauvegardés: {results_file}")
print("\n" + "=" * 70)
