#!/usr/bin/env python3
"""
ANALYSE DISTRIBUTION CONFIANCE GRADIENTBOOSTING
================================================
Analyse pourquoi le modèle rejette autant de trades.
"""

import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from pathlib import Path
from sklearn.ensemble import HistGradientBoostingClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
import joblib

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "config_overrides.json"
MODELS_DIR = PROJECT_ROOT / "optimization" / "saved_models"

def load_data():
    """Charge les données d'entraînement"""
    print("\n[1/4] Chargement des données...")
    
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        
        df = load_features_from_postgres(
            min_trades=50,
            timeframe_days=365,
            include_open_trades=False
        )
        
        print(f"      ✅ {len(df)} trades chargés")
        return df
    except Exception as e:
        print(f"      ❌ Erreur: {e}")
        return None

def prepare_features(df):
    """Prépare les features"""
    exclude_cols = [
        'scan_id', 'timestamp', 'symbol', 'opportunity_direction',
        'target_win', 'target_pnl', 'is_opportunity',
        'reject_reason_category'
    ]
    
    feature_cols = [col for col in df.columns 
                    if col not in exclude_cols 
                    and df[col].dtype in ['float64', 'int64', 'float32', 'int32']]
    
    X = df[feature_cols].fillna(0)
    y = df['target_win'].dropna().astype(int)
    
    valid_idx = y.index
    X = X.loc[valid_idx]
    
    return X, y, feature_cols

def analyze_confidence_distribution():
    """Analyse la distribution des confiances"""
    print("\n" + "=" * 70)
    print("  ANALYSE DISTRIBUTION CONFIANCE GRADIENTBOOSTING")
    print("=" * 70)
    
    # Charger données
    df = load_data()
    if df is None:
        return
    
    X, y, feature_cols = prepare_features(df)
    print(f"      Features: {len(feature_cols)}")
    print(f"      Classe 0 (loss): {(y == 0).sum()} ({(y == 0).mean()*100:.1f}%)")
    print(f"      Classe 1 (win): {(y == 1).sum()} ({(y == 1).mean()*100:.1f}%)")
    
    # Charger modèle ou en créer un
    print("\n[2/4] Chargement/Création du modèle...")
    
    model_path = MODELS_DIR / "best_classifier_latest.pkl"
    if model_path.exists():
        try:
            pipeline = joblib.load(model_path)
            print(f"      ✅ Modèle chargé depuis {model_path}")
        except Exception as e:
            print(f"      ⚠️ Erreur chargement: {e}, création nouveau modèle...")
            pipeline = None
    else:
        pipeline = None
    
    if pipeline is None:
        # Créer un nouveau modèle avec la config
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        model_type = config.get('gb_model_type', 'histgb')
        
        if model_type == 'histgb':
            model = HistGradientBoostingClassifier(
                max_iter=config.get('gb_n_estimators', 150),
                max_depth=config.get('gb_max_depth', 3),
                learning_rate=config.get('gb_learning_rate', 0.03),
                min_samples_leaf=config.get('gb_min_samples_leaf', 50),
                l2_regularization=config.get('gb_l2_regularization', 0.3),
                random_state=42
            )
        else:
            model = GradientBoostingClassifier(
                n_estimators=config.get('gb_n_estimators', 150),
                max_depth=config.get('gb_max_depth', 3),
                learning_rate=config.get('gb_learning_rate', 0.03),
                min_samples_split=config.get('gb_min_samples_split', 40),
                min_samples_leaf=config.get('gb_min_samples_leaf', 50),
                subsample=config.get('gb_subsample', 0.8),
                max_features=config.get('gb_max_features', 0.7),
                random_state=42
            )
        
        print(f"      Entraînement {type(model).__name__}...")
        model.fit(X, y)
        pipeline = model
    
    # Obtenir les probabilités
    print("\n[3/4] Calcul des probabilités de confiance...")
    
    if hasattr(pipeline, 'predict_proba'):
        proba = pipeline.predict_proba(X)
    elif hasattr(pipeline, 'named_steps') and hasattr(pipeline.named_steps.get('model', None), 'predict_proba'):
        proba = pipeline.predict_proba(X)
    else:
        print("      ❌ Le modèle ne supporte pas predict_proba")
        return
    
    # proba[:,1] = probabilité de WIN (classe 1)
    confidence = proba[:, 1]
    
    # Statistiques
    print("\n[4/4] Distribution des confiances...")
    
    print(f"\n  📊 STATISTIQUES GLOBALES:")
    print(f"      Min:     {confidence.min()*100:.1f}%")
    print(f"      Max:     {confidence.max()*100:.1f}%")
    print(f"      Moyenne: {confidence.mean()*100:.1f}%")
    print(f"      Médiane: {np.median(confidence)*100:.1f}%")
    print(f"      Écart-type: {confidence.std()*100:.1f}%")
    
    # Distribution par seuils
    thresholds = [0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70]
    
    print(f"\n  📊 TAUX D'ACCEPTATION PAR SEUIL:")
    print(f"      {'Seuil':<10} {'Acceptés':<15} {'%':<10} {'Win Rate réel'}")
    print(f"      {'-'*55}")
    
    for threshold in thresholds:
        accepted = confidence >= threshold
        n_accepted = accepted.sum()
        pct_accepted = n_accepted / len(confidence) * 100
        
        # Win rate des trades acceptés
        if n_accepted > 0:
            win_rate = y[accepted].mean() * 100
        else:
            win_rate = 0
        
        marker = "👈 actuel" if threshold == 0.50 else ""
        print(f"      {threshold*100:.0f}%       {n_accepted:<15} {pct_accepted:.1f}%      {win_rate:.1f}%   {marker}")
    
    # Histogramme textuel
    print(f"\n  📊 HISTOGRAMME DES CONFIANCES:")
    bins = np.arange(0, 1.05, 0.1)
    hist, _ = np.histogram(confidence, bins=bins)
    
    max_count = max(hist)
    for i in range(len(hist)):
        bar_len = int(hist[i] / max_count * 40) if max_count > 0 else 0
        bar = "█" * bar_len
        print(f"      {bins[i]*100:3.0f}%-{bins[i+1]*100:3.0f}%: {bar} ({hist[i]})")
    
    # Recommandations
    print(f"\n  💡 RECOMMANDATIONS:")
    
    median_conf = np.median(confidence) * 100
    
    if median_conf < 50:
        print(f"""
      ⚠️ La médiane des confiances est de {median_conf:.1f}%, très basse!
      
      Causes possibles:
      1. Le modèle est trop conservateur (forte régularisation)
      2. Les features ne sont pas assez discriminantes
      3. Le dataset est mal équilibré ou bruité
      
      Solutions recommandées:
      - Baisser le seuil à 40% pour avoir ~{(confidence >= 0.40).sum()} trades
      - Désactiver temporairement le filtre GB pour collecter plus de données
      - Réentraîner avec moins de régularisation
""")
    else:
        threshold_50_pct = (confidence >= 0.50).sum() / len(confidence) * 100
        print(f"""
      ✅ Distribution normale, {threshold_50_pct:.1f}% des trades passent le seuil 50%
      
      Si trop peu de trades passent en conditions réelles:
      - Les conditions de marché actuelles peuvent être défavorables
      - Vérifier que les features temps réel correspondent à l'entraînement
""")
    
    # Seuil optimal suggéré
    for thresh in thresholds:
        if (confidence >= thresh).sum() / len(confidence) >= 0.15:  # Au moins 15% acceptés
            print(f"      📌 Seuil suggéré: {thresh*100:.0f}% ({(confidence >= thresh).sum()} trades, {(confidence >= thresh).sum() / len(confidence)*100:.1f}%)")
            break
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    analyze_confidence_distribution()
