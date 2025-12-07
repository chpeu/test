#!/usr/bin/env python3
"""
TEST IMPACT ORDER FLOW SUR GRADIENTBOOSTING
============================================
Compare les performances avec et sans les 3 features order flow.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Config B Anti-Overfit (recommandée)
CONFIG_B = {
    'n_estimators': 150,
    'max_depth': 3,
    'learning_rate': 0.03,
    'min_samples_split': 80,
    'min_samples_leaf': 60,
    'subsample': 0.7,
    'max_features': 0.5,
    'random_state': 42
}

ORDER_FLOW_COLS = ['delta_volume', 'imbalance_normalized', 'book_depth_ratio']

def load_data():
    """Charge les données depuis PostgreSQL"""
    from optimization.data.feature_loader import load_features_from_postgres
    
    # Charger avec timeframe long pour avoir assez de données
    df = load_features_from_postgres(
        min_trades=50,
        timeframe_days=365,
        include_open_trades=False
    )
    
    return df

def prepare_features(df, include_orderflow=True):
    """Prépare les features pour l'entraînement"""
    # Colonnes à exclure
    exclude_cols = [
        'scan_id', 'timestamp', 'symbol', 'opportunity_direction',
        'target_win', 'target_pnl', 'is_opportunity',
        'reject_reason_category'
    ]
    
    # Si on exclut order flow
    if not include_orderflow:
        exclude_cols.extend(ORDER_FLOW_COLS)
    
    # Sélectionner features numériques
    feature_cols = [col for col in df.columns 
                    if col not in exclude_cols 
                    and df[col].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    X = df[feature_cols].copy()
    y = df['target_win'].copy()
    
    # Imputer les NaN
    X = X.fillna(0)
    
    # Supprimer lignes avec target NaN
    valid_idx = y.notna()
    X = X[valid_idx]
    y = y[valid_idx].astype(int)
    
    return X, y, feature_cols

def run_comparison(n_trials=30):
    """Compare performances avec/sans order flow"""
    print("=" * 70)
    print("  TEST IMPACT ORDER FLOW SUR GRADIENTBOOSTING")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Charger données
    print("\n[1/3] Chargement des données...")
    df = load_data()
    print(f"      Trades chargés: {len(df)}")
    
    # Vérifier disponibilité order flow
    orderflow_available = all(col in df.columns for col in ORDER_FLOW_COLS)
    if orderflow_available:
        non_null = df[ORDER_FLOW_COLS].notna().all(axis=1).sum()
        print(f"      Order Flow disponible: {non_null}/{len(df)} trades ({100*non_null//len(df)}%)")
    else:
        print("      ❌ Order Flow non disponible dans les données")
        return
    
    # Résultats
    results = {
        'sans_orderflow': {'test_acc': [], 'f1': [], 'precision': [], 'recall': [], 'gap': []},
        'avec_orderflow': {'test_acc': [], 'f1': [], 'precision': [], 'recall': [], 'gap': []}
    }
    
    print(f"\n[2/3] Test SANS Order Flow ({n_trials} trials)...")
    X_no, y_no, cols_no = prepare_features(df, include_orderflow=False)
    print(f"      Features: {len(cols_no)}")
    
    for i in range(n_trials):
        X_train, X_test, y_train, y_test = train_test_split(
            X_no, y_no, test_size=0.2, random_state=i, stratify=y_no
        )
        
        model = GradientBoostingClassifier(**CONFIG_B)
        model.fit(X_train, y_train)
        
        train_acc = model.score(X_train, y_train)
        test_acc = model.score(X_test, y_test)
        y_pred = model.predict(X_test)
        
        results['sans_orderflow']['test_acc'].append(test_acc)
        results['sans_orderflow']['f1'].append(f1_score(y_test, y_pred))
        results['sans_orderflow']['precision'].append(precision_score(y_test, y_pred))
        results['sans_orderflow']['recall'].append(recall_score(y_test, y_pred))
        results['sans_orderflow']['gap'].append(train_acc - test_acc)
        
        if (i + 1) % 10 == 0:
            print(f"      Trial {i+1}/{n_trials}...")
    
    print(f"\n[3/3] Test AVEC Order Flow ({n_trials} trials)...")
    X_of, y_of, cols_of = prepare_features(df, include_orderflow=True)
    print(f"      Features: {len(cols_of)} (+{len(cols_of) - len(cols_no)} order flow)")
    
    for i in range(n_trials):
        X_train, X_test, y_train, y_test = train_test_split(
            X_of, y_of, test_size=0.2, random_state=i, stratify=y_of
        )
        
        model = GradientBoostingClassifier(**CONFIG_B)
        model.fit(X_train, y_train)
        
        train_acc = model.score(X_train, y_train)
        test_acc = model.score(X_test, y_test)
        y_pred = model.predict(X_test)
        
        results['avec_orderflow']['test_acc'].append(test_acc)
        results['avec_orderflow']['f1'].append(f1_score(y_test, y_pred))
        results['avec_orderflow']['precision'].append(precision_score(y_test, y_pred))
        results['avec_orderflow']['recall'].append(recall_score(y_test, y_pred))
        results['avec_orderflow']['gap'].append(train_acc - test_acc)
        
        if (i + 1) % 10 == 0:
            print(f"      Trial {i+1}/{n_trials}...")
    
    # Afficher résultats
    print("\n" + "=" * 70)
    print("  RÉSULTATS COMPARATIFS")
    print("=" * 70)
    
    metrics = ['test_acc', 'f1', 'precision', 'recall', 'gap']
    metric_names = ['Test Accuracy', 'F1 Score', 'Precision', 'Recall', 'Overfitting Gap']
    
    for metric, name in zip(metrics, metric_names):
        sans = np.array(results['sans_orderflow'][metric])
        avec = np.array(results['avec_orderflow'][metric])
        
        diff = np.mean(avec) - np.mean(sans)
        winner = "AVEC" if (diff > 0 and metric != 'gap') or (diff < 0 and metric == 'gap') else "SANS"
        
        print(f"\n📊 {name}:")
        print(f"   SANS Order Flow: {np.mean(sans):.4f} ± {np.std(sans):.4f}")
        print(f"   AVEC Order Flow: {np.mean(avec):.4f} ± {np.std(avec):.4f}")
        print(f"   Différence: {diff:+.4f} → 🏆 {winner} gagne")
    
    # Feature importance si avec order flow gagne
    print("\n" + "=" * 70)
    print("  IMPORTANCE DES FEATURES ORDER FLOW")
    print("=" * 70)
    
    # Entraîner un modèle final pour feature importance
    X_train, X_test, y_train, y_test = train_test_split(
        X_of, y_of, test_size=0.2, random_state=42, stratify=y_of
    )
    model = GradientBoostingClassifier(**CONFIG_B)
    model.fit(X_train, y_train)
    
    importance = pd.DataFrame({
        'feature': cols_of,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 15 features:")
    for i, row in importance.head(15).iterrows():
        marker = "🔥" if row['feature'] in ORDER_FLOW_COLS else "  "
        print(f"   {marker} {row['feature']}: {row['importance']:.4f}")
    
    # Position des features order flow
    print("\n📊 Position des features Order Flow:")
    for col in ORDER_FLOW_COLS:
        if col in importance['feature'].values:
            rank = importance[importance['feature'] == col].index[0] + 1
            imp = importance[importance['feature'] == col]['importance'].values[0]
            print(f"   {col}: rang #{rank}, importance={imp:.4f}")
    
    # Conclusion
    test_diff = np.mean(results['avec_orderflow']['test_acc']) - np.mean(results['sans_orderflow']['test_acc'])
    
    print("\n" + "=" * 70)
    print("  CONCLUSION")
    print("=" * 70)
    
    if test_diff > 0.005:
        print(f"\n   ✅ Order Flow AMÉLIORE les performances (+{test_diff*100:.2f}% accuracy)")
        print("   → Recommandation: GARDER les features order flow")
    elif test_diff < -0.005:
        print(f"\n   ❌ Order Flow DÉGRADE les performances ({test_diff*100:.2f}% accuracy)")
        print("   → Recommandation: EXCLURE les features order flow")
    else:
        print(f"\n   ⚖️ Order Flow n'a PAS d'impact significatif ({test_diff*100:.2f}% accuracy)")
        print("   → Recommandation: GARDER pour diversité des features")
    
    print("=" * 70)

if __name__ == "__main__":
    run_comparison(n_trials=30)
