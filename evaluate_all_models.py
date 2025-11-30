# -*- coding: utf-8 -*-
"""
Évaluation Performance des 3 Modèles ML

Ce script évalue:
1. XGBoost V1 (Classification WIN/LOSS)
2. XGBoost V2 (Régression PNL%)
3. GradientBoosting (Classification optimisée)

Avec le nouveau filtre négatif (mode NEGATIVE)
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.metrics import confusion_matrix, classification_report

print("=" * 70)
print("  EVALUATION DES 3 MODELES ML")
print("  Avec Filtre Negatif (mode NEGATIVE)")
print("=" * 70)

# =============================================================================
# CHARGEMENT DES DONNEES
# =============================================================================
print("\n[1/6] Chargement des donnees...")

from optimization.data.feature_loader import load_features_from_postgres
from optimization.data.feature_engineering import calculate_derived_features

df = load_features_from_postgres(timeframe_days=180, min_trades=1)
print(f"   Trades charges: {len(df)}")

# Séparer features et target
target_col = 'target_win'
exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                'is_opportunity', 'reject_reason_category']

feature_cols = [c for c in df.columns if c not in exclude_cols]
X = df[feature_cols].copy()
y = df[target_col].copy()

# Nettoyer
X = X.replace([np.inf, -np.inf], np.nan)
X = X.fillna(0)

print(f"   Features: {len(feature_cols)}")
print(f"   Win rate baseline: {y.mean()*100:.1f}%")

# Split train/test (80/20 temporel)
split_idx = int(len(df) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"   Train: {len(X_train)} | Test: {len(X_test)}")

# =============================================================================
# EVALUATION MODELE 1: XGBOOST V1
# =============================================================================
print("\n" + "=" * 70)
print("[2/6] XGBOOST V1 (Classification WIN/LOSS)")
print("=" * 70)

try:
    from optimization.predictor import get_predictor
    
    predictor_v1 = get_predictor()
    
    if predictor_v1.is_loaded:
        print(f"   Modele charge: {predictor_v1.model_name}")
        
        # Prédictions sur test set
        y_pred_v1 = []
        y_proba_v1 = []
        
        for i in range(len(X_test)):
            features = X_test.iloc[i].to_dict()
            result = predictor_v1.predict(features)
            
            if result:
                pred = 1 if result.get('prediction') == 'win' else 0
                proba = result.get('confidence', 0.5)
                y_pred_v1.append(pred)
                y_proba_v1.append(proba if pred == 1 else 1 - proba)
            else:
                y_pred_v1.append(0)
                y_proba_v1.append(0.5)
        
        y_pred_v1 = np.array(y_pred_v1)
        y_proba_v1 = np.array(y_proba_v1)
        
        # Métriques
        acc_v1 = accuracy_score(y_test, y_pred_v1)
        prec_v1 = precision_score(y_test, y_pred_v1, zero_division=0)
        rec_v1 = recall_score(y_test, y_pred_v1, zero_division=0)
        f1_v1 = f1_score(y_test, y_pred_v1, zero_division=0)
        
        try:
            auc_v1 = roc_auc_score(y_test, y_proba_v1)
        except:
            auc_v1 = 0.5
        
        print(f"\n   Resultats XGBoost V1:")
        print(f"      Accuracy:  {acc_v1*100:.1f}%")
        print(f"      Precision: {prec_v1*100:.1f}%")
        print(f"      Recall:    {rec_v1*100:.1f}%")
        print(f"      F1 Score:  {f1_v1*100:.1f}%")
        print(f"      ROC-AUC:   {auc_v1*100:.1f}%")
        
        v1_results = {'acc': acc_v1, 'prec': prec_v1, 'rec': rec_v1, 'f1': f1_v1, 'auc': auc_v1}
    else:
        print("   [!] Modele non charge")
        v1_results = None
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    v1_results = None

# =============================================================================
# EVALUATION MODELE 2: XGBOOST V2 (Régression)
# =============================================================================
print("\n" + "=" * 70)
print("[3/6] XGBOOST V2 (Regression PNL%)")
print("=" * 70)

try:
    from optimization.predictor_v2 import get_predictor_v2
    
    predictor_v2 = get_predictor_v2()
    
    if predictor_v2.is_loaded:
        print(f"   Modele charge")
        
        # Pour V2, on prédit le PNL% et on convertit en classification
        y_pred_v2 = []
        y_pnl_pred = []
        
        for i in range(len(X_test)):
            features = X_test.iloc[i].to_dict()
            result = predictor_v2.predict(features, return_classification=True)
            
            if result:
                pred = 1 if result.get('prediction') == 'win' else 0
                pnl = result.get('predicted_pnl', 0)
                y_pred_v2.append(pred)
                y_pnl_pred.append(pnl)
            else:
                y_pred_v2.append(0)
                y_pnl_pred.append(0)
        
        y_pred_v2 = np.array(y_pred_v2)
        y_pnl_pred = np.array(y_pnl_pred)
        
        # Métriques classification
        acc_v2 = accuracy_score(y_test, y_pred_v2)
        prec_v2 = precision_score(y_test, y_pred_v2, zero_division=0)
        rec_v2 = recall_score(y_test, y_pred_v2, zero_division=0)
        f1_v2 = f1_score(y_test, y_pred_v2, zero_division=0)
        
        print(f"\n   Resultats XGBoost V2:")
        print(f"      Accuracy:  {acc_v2*100:.1f}%")
        print(f"      Precision: {prec_v2*100:.1f}%")
        print(f"      Recall:    {rec_v2*100:.1f}%")
        print(f"      F1 Score:  {f1_v2*100:.1f}%")
        
        v2_results = {'acc': acc_v2, 'prec': prec_v2, 'rec': rec_v2, 'f1': f1_v2}
    else:
        print("   [!] Modele non charge")
        v2_results = None
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    v2_results = None

# =============================================================================
# EVALUATION MODELE 3: GRADIENTBOOSTING
# =============================================================================
print("\n" + "=" * 70)
print("[4/6] GRADIENTBOOSTING (Classification optimisee)")
print("=" * 70)

try:
    from optimization.predictor_optimized import get_predictor as get_gb_predictor
    
    predictor_gb = get_gb_predictor()
    
    if predictor_gb.is_loaded:
        print(f"   Modele charge")
        
        y_pred_gb = []
        y_proba_gb = []
        
        for i in range(len(X_test)):
            features = X_test.iloc[i].to_dict()
            should_trade, confidence = predictor_gb.predict(features)
            
            pred = 1 if should_trade else 0
            y_pred_gb.append(pred)
            y_proba_gb.append(confidence)
        
        y_pred_gb = np.array(y_pred_gb)
        y_proba_gb = np.array(y_proba_gb)
        
        # Métriques
        acc_gb = accuracy_score(y_test, y_pred_gb)
        prec_gb = precision_score(y_test, y_pred_gb, zero_division=0)
        rec_gb = recall_score(y_test, y_pred_gb, zero_division=0)
        f1_gb = f1_score(y_test, y_pred_gb, zero_division=0)
        
        try:
            auc_gb = roc_auc_score(y_test, y_proba_gb)
        except:
            auc_gb = 0.5
        
        print(f"\n   Resultats GradientBoosting:")
        print(f"      Accuracy:  {acc_gb*100:.1f}%")
        print(f"      Precision: {prec_gb*100:.1f}%")
        print(f"      Recall:    {rec_gb*100:.1f}%")
        print(f"      F1 Score:  {f1_gb*100:.1f}%")
        print(f"      ROC-AUC:   {auc_gb*100:.1f}%")
        
        gb_results = {'acc': acc_gb, 'prec': prec_gb, 'rec': rec_gb, 'f1': f1_gb, 'auc': auc_gb}
    else:
        print("   [!] Modele non charge")
        gb_results = None
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    gb_results = None

# =============================================================================
# EVALUATION FILTRE NEGATIF
# =============================================================================
print("\n" + "=" * 70)
print("[5/6] FILTRE NEGATIF (Nouveau)")
print("=" * 70)

try:
    from optimization.predictor_negative import get_negative_predictor
    
    neg_predictor = get_negative_predictor()
    
    if neg_predictor.is_loaded:
        print(f"   Modele charge: {neg_predictor.get_info()['n_features']} features")
        
        # Test avec différents seuils
        thresholds = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
        
        print(f"\n   Test avec differents seuils P(loss):")
        print(f"   {'Seuil':<10} {'Rejetes':<12} {'Conserves':<12} {'WR Sans':<12} {'WR Avec':<12} {'Gain':<10}")
        print("   " + "-" * 68)
        
        best_threshold = 0.45
        best_gain = 0
        
        for threshold in thresholds:
            # Prédire pour chaque trade
            rejected = 0
            kept_wins = 0
            kept_total = 0
            
            for i in range(len(X_test)):
                features = X_test.iloc[i].to_dict()
                result = neg_predictor.predict(features, threshold=threshold)
                
                p_loss = result.get('p_loss', 0)
                actual_win = y_test.iloc[i]
                
                if p_loss >= threshold:
                    rejected += 1
                else:
                    kept_total += 1
                    if actual_win == 1:
                        kept_wins += 1
            
            wr_baseline = y_test.mean()
            wr_filtered = kept_wins / kept_total if kept_total > 0 else 0
            gain = wr_filtered - wr_baseline
            
            if gain > best_gain:
                best_gain = gain
                best_threshold = threshold
            
            print(f"   {threshold*100:.0f}%       {rejected:<12} {kept_total:<12} {wr_baseline*100:.1f}%        {wr_filtered*100:.1f}%        {gain*100:+.1f}%")
        
        print(f"\n   Meilleur seuil: {best_threshold*100:.0f}% (+{best_gain*100:.1f}% win rate)")
        
        neg_results = {'best_threshold': best_threshold, 'best_gain': best_gain}
    else:
        print("   [!] Modele non charge")
        neg_results = None
        
except Exception as e:
    print(f"   [X] Erreur: {e}")
    import traceback
    traceback.print_exc()
    neg_results = None

# =============================================================================
# ANALYSE COMPARATIVE
# =============================================================================
print("\n" + "=" * 70)
print("[6/6] ANALYSE COMPARATIVE")
print("=" * 70)

print("\n   TABLEAU COMPARATIF:")
print(f"   {'Modele':<25} {'Accuracy':<12} {'Precision':<12} {'F1':<12} {'AUC':<12}")
print("   " + "-" * 63)

if v1_results:
    print(f"   {'XGBoost V1':<25} {v1_results['acc']*100:.1f}%        {v1_results['prec']*100:.1f}%        {v1_results['f1']*100:.1f}%      {v1_results.get('auc', 0)*100:.1f}%")

if v2_results:
    print(f"   {'XGBoost V2':<25} {v2_results['acc']*100:.1f}%        {v2_results['prec']*100:.1f}%        {v2_results['f1']*100:.1f}%      N/A")

if gb_results:
    print(f"   {'GradientBoosting':<25} {gb_results['acc']*100:.1f}%        {gb_results['prec']*100:.1f}%        {gb_results['f1']*100:.1f}%      {gb_results.get('auc', 0)*100:.1f}%")

if neg_results:
    print(f"   {'Filtre Negatif':<25} N/A          N/A          N/A        +{neg_results['best_gain']*100:.1f}% WR")

# =============================================================================
# RECOMMANDATIONS
# =============================================================================
print("\n" + "=" * 70)
print("  ANALYSE ET RECOMMANDATIONS")
print("=" * 70)

# Déterminer le meilleur modèle
models_scores = []
if v1_results:
    models_scores.append(('XGBoost V1', v1_results['f1']))
if v2_results:
    models_scores.append(('XGBoost V2', v2_results['f1']))
if gb_results:
    models_scores.append(('GradientBoosting', gb_results['f1']))

if models_scores:
    best_model = max(models_scores, key=lambda x: x[1])
    
    print(f"""
   MEILLEUR MODELE: {best_model[0]} (F1: {best_model[1]*100:.1f}%)
   
   STRATEGIE RECOMMANDEE:
   ----------------------
   1. Utiliser le mode NEGATIVE avec seuil {neg_results['best_threshold']*100:.0f}% si disponible
      → Gain estimé: +{neg_results['best_gain']*100:.1f}% win rate
   
   2. Configuration optimale:
      ml_filter_enabled: true
      ml_filter_mode: NEGATIVE
      ml_loss_threshold: {neg_results['best_threshold']}
   
   AMELIORATIONS POSSIBLES:
   ------------------------
   1. Collecter plus de données (objectif: 5000+ trades)
   2. Ajouter des features temporelles (heure, session)
   3. Réentraîner les modèles régulièrement (tous les 500 trades)
   4. Tester un ensemble (voting) des 3 modèles
   5. Optimiser les hyperparamètres avec Optuna
   
   POINTS D'ATTENTION:
   -------------------
   - Accuracy proche de 50% = signal faible dans les features
   - Le filtre négatif compense en évitant les mauvais trades
   - Ne pas sur-optimiser le seuil (risque de surfit)
""")
else:
    print("\n   [!] Aucun modèle évalué avec succès")

print("=" * 70)
print("  FIN DE L'EVALUATION")
print("=" * 70)
