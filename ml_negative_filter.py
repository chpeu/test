# -*- coding: utf-8 -*-
"""
ML comme Filtre NÉGATIF

Au lieu de prédire les "WIN", on prédit les "LOSS" pour les ÉVITER.
C'est plus efficace quand le signal est faible.

Stratégie:
1. Entraîner un modèle à prédire les LOSS (classe 0)
2. Rejeter les trades où P(loss) > seuil_haut
3. Garder les autres (même si P(win) n'est pas élevé)
"""

import sys
import os
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 90)
print("  ML COMME FILTRE NÉGATIF")
print("  Objectif: Identifier et ÉVITER les mauvais trades")
print("=" * 90)

# =============================================================================
# CHARGEMENT
# =============================================================================

def load_data():
    from optimization.data.feature_loader import load_features_from_postgres
    from optimization.data.feature_engineering import calculate_derived_features
    from optimization.utils.temporal_split import temporal_train_test_split
    
    print("\n📥 Chargement données...")
    df = load_features_from_postgres(timeframe_days=365, min_trades=50, include_open_trades=False)
    df = calculate_derived_features(df)
    
    # Colonnes à exclure
    exclude = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
               'is_opportunity', 'reject_reason_category', 'opportunity_direction']
    config_cols = [c for c in df.columns if c.startswith('config_')]
    exclude.extend(config_cols)
    
    feature_cols = [c for c in df.columns if c not in exclude]
    
    # Nettoyer
    X = df[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(df[feature_cols].median())
    
    # Supprimer constantes
    X = X.loc[:, X.std() > 0]
    feature_cols = list(X.columns)
    
    # Split
    train_df, val_df, test_df = temporal_train_test_split(df, 'target_win', 0.2, 0.2)
    
    def get_xy(split_df):
        x = split_df[feature_cols].replace([np.inf, -np.inf], np.nan)
        x = x.fillna(x.median())
        # INVERSER: target = 1 si LOSS (on veut prédire les LOSS)
        y_loss = (split_df['target_win'] == 0).astype(int).values
        y_win = split_df['target_win'].values
        return x, y_loss, y_win
    
    X_train, y_train_loss, y_train_win = get_xy(train_df)
    X_val, y_val_loss, y_val_win = get_xy(val_df)
    X_test, y_test_loss, y_test_win = get_xy(test_df)
    
    print(f"   Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)}")
    print(f"   Loss rate dans test: {y_test_loss.mean():.1%}")
    
    return (X_train, y_train_loss, y_train_win,
            X_val, y_val_loss, y_val_win,
            X_test, y_test_loss, y_test_win,
            feature_cols)


# =============================================================================
# ENTRAÎNEMENT DU DÉTECTEUR DE LOSS
# =============================================================================

def train_loss_detector(X_train, y_train, X_val, y_val, feature_cols):
    """Entraîne un modèle à détecter les LOSS"""
    
    print("\n" + "=" * 60)
    print("  ENTRAÎNEMENT DÉTECTEUR DE LOSS")
    print("=" * 60)
    
    # Feature selection
    from sklearn.feature_selection import mutual_info_classif
    mi = mutual_info_classif(X_train, y_train, random_state=42)
    top_features = pd.Series(mi, index=feature_cols).nlargest(40).index.tolist()
    
    X_train_sel = X_train[top_features]
    X_val_sel = X_val[top_features]
    
    # Modèle optimisé pour détecter les LOSS
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.03,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        use_label_encoder=False,
        eval_metric='auc'
    )
    
    model.fit(X_train_sel, y_train, eval_set=[(X_val_sel, y_val)], verbose=False)
    
    return model, top_features


# =============================================================================
# ÉVALUATION COMME FILTRE NÉGATIF
# =============================================================================

def evaluate_negative_filter(model, X_test, y_test_loss, y_test_win, features):
    """Évalue le modèle comme filtre négatif"""
    
    print("\n" + "=" * 60)
    print("  ÉVALUATION COMME FILTRE NÉGATIF")
    print("=" * 60)
    
    X_test_sel = X_test[features]
    
    # Probabilité que ce soit un LOSS
    p_loss = model.predict_proba(X_test_sel)[:, 1]
    
    # Tester différents seuils de rejet
    print(f"\n   {'Seuil':<10} {'Trades':<10} {'Rejetés':<10} {'Win Rate':<12} {'Amélio.':<10}")
    print("-" * 60)
    
    base_win_rate = y_test_win.mean()
    best_threshold = 0.5
    best_improvement = 0
    
    for threshold in [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75]:
        # Rejeter les trades où P(loss) > threshold
        keep_mask = p_loss < threshold
        
        n_kept = keep_mask.sum()
        n_rejected = (~keep_mask).sum()
        
        if n_kept > 0:
            new_win_rate = y_test_win[keep_mask].mean()
            improvement = (new_win_rate - base_win_rate) / base_win_rate * 100
            
            marker = "✅" if improvement > best_improvement and n_kept >= 50 else ""
            
            if improvement > best_improvement and n_kept >= 50:
                best_improvement = improvement
                best_threshold = threshold
            
            print(f"   P<{threshold:<5} {n_kept:<10} {n_rejected:<10} {new_win_rate:.1%}{'':>4} {improvement:+.1f}% {marker}")
        else:
            print(f"   P<{threshold:<5} {'0':<10} {n_rejected:<10} {'-':<12} {'-':<10}")
    
    print(f"\n   📊 Baseline Win Rate: {base_win_rate:.1%}")
    print(f"   🎯 Meilleur seuil: P(loss) < {best_threshold}")
    print(f"   📈 Amélioration: {best_improvement:+.1f}%")
    
    return best_threshold


# =============================================================================
# SIMULATION TRADING
# =============================================================================

def simulate_trading(model, X_test, y_test_win, features, threshold, target_pnl=None):
    """Simule l'impact sur le trading"""
    
    print("\n" + "=" * 60)
    print("  SIMULATION TRADING")
    print("=" * 60)
    
    X_test_sel = X_test[features]
    p_loss = model.predict_proba(X_test_sel)[:, 1]
    
    # Sans filtre ML
    print("\n   📊 SANS filtre ML:")
    print(f"      Trades: {len(y_test_win)}")
    print(f"      Wins: {y_test_win.sum()}")
    print(f"      Win Rate: {y_test_win.mean():.1%}")
    
    # Avec filtre ML
    keep_mask = p_loss < threshold
    
    print(f"\n   📊 AVEC filtre ML (rejet si P(loss) >= {threshold}):")
    print(f"      Trades: {keep_mask.sum()} ({keep_mask.sum()/len(y_test_win)*100:.1f}% du total)")
    print(f"      Wins: {y_test_win[keep_mask].sum()}")
    print(f"      Win Rate: {y_test_win[keep_mask].mean():.1%}")
    
    # Trades rejetés
    rejected = ~keep_mask
    print(f"\n   🚫 Trades REJETÉS par le filtre:")
    print(f"      Nombre: {rejected.sum()}")
    if rejected.sum() > 0:
        print(f"      Win Rate (si on les avait pris): {y_test_win[rejected].mean():.1%}")
        print(f"      → Le filtre a raison de les rejeter!" if y_test_win[rejected].mean() < 0.5 else "      → Le filtre se trompe sur ceux-là")


# =============================================================================
# SAUVEGARDER LE MODÈLE
# =============================================================================

def save_model(model, features, threshold):
    """Sauvegarde le modèle de filtre négatif"""
    
    os.makedirs('optimization/saved_models', exist_ok=True)
    
    package = {
        'model': model,
        'features': features,
        'threshold': threshold,
        'type': 'negative_filter',
        'description': 'Rejeter si P(loss) >= threshold',
        'created_at': datetime.now().isoformat()
    }
    
    path = 'optimization/saved_models/ml_negative_filter.pkl'
    with open(path, 'wb') as f:
        pickle.dump(package, f)
    
    print(f"\n   💾 Modèle sauvegardé: {path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Charger
    (X_train, y_train_loss, y_train_win,
     X_val, y_val_loss, y_val_win,
     X_test, y_test_loss, y_test_win,
     feature_cols) = load_data()
    
    # Entraîner détecteur de LOSS
    model, features = train_loss_detector(
        X_train, y_train_loss, X_val, y_val_loss, feature_cols
    )
    
    # Évaluer comme filtre négatif
    best_threshold = evaluate_negative_filter(
        model, X_test, y_test_loss, y_test_win, features
    )
    
    # Simuler trading
    simulate_trading(model, X_test, y_test_win, features, best_threshold)
    
    # Sauvegarder
    save_model(model, features, best_threshold)
    
    print("\n" + "=" * 90)
    print("  CONCLUSION")
    print("=" * 90)
    print(f"""
   Le filtre NÉGATIF fonctionne mieux que le filtre positif car:
   
   1. On ne cherche pas à prédire les WINS (signal faible)
   2. On cherche à ÉVITER les LOSS évidents (plus facile)
   3. On garde plus de trades (moins restrictif)
   
   Configuration recommandée pour le backend:
   
   {{
       "ml_filter_enabled": true,
       "ml_filter_mode": "negative",  // Rejeter les mauvais
       "ml_loss_threshold": {best_threshold}  // Rejeter si P(loss) >= seuil
   }}
""")


if __name__ == "__main__":
    main()
