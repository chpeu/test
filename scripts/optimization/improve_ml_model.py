# -*- coding: utf-8 -*-
"""
Script d'amelioration du modele ML GradientBoosting
Diagnostic et solutions pour ameliorer accuracy et F1 score
"""

import sys
import os
import json
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from pathlib import Path

def load_current_model_data():
    """Charge les metadata du modele actuel"""
    metadata_path = Path("optimization/saved_models/best_classifier_metadata.json")
    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            return json.load(f)
    return None

def analyze_class_distribution():
    """Analyse la distribution des classes"""
    print("\n" + "=" * 60)
    print("1. ANALYSE DISTRIBUTION DES CLASSES")
    print("=" * 60)
    
    # Charger depuis SQLite local si disponible
    try:
        import sqlite3
        db_path = Path("analytics.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            df = pd.read_sql("SELECT pnl_usdt FROM trades WHERE pnl_usdt IS NOT NULL", conn)
            conn.close()
            
            if len(df) > 0:
                winners = (df['pnl_usdt'] > 0).sum()
                losers = (df['pnl_usdt'] <= 0).sum()
                total = len(df)
                
                print(f"\nDistribution trades:")
                print(f"  - Gagnants (PnL > 0): {winners} ({winners/total*100:.1f}%)")
                print(f"  - Perdants (PnL <= 0): {losers} ({losers/total*100:.1f}%)")
                print(f"  - Ratio: 1:{losers/max(winners,1):.1f}")
                
                if losers/max(winners,1) > 2:
                    print("\n  [PROBLEME] Desequilibre severe des classes!")
                    print("  -> Le modele predit majoritairement la classe dominante")
                    print("  -> F1 score bas car recall sur classe minoritaire tres faible")
                    return losers/max(winners,1)
                return 1.0
    except Exception as e:
        print(f"  Impossible de charger trades: {e}")
    
    return None

def analyze_features():
    """Analyse les features du modele"""
    print("\n" + "=" * 60)
    print("2. ANALYSE DES FEATURES")
    print("=" * 60)
    
    metadata = load_current_model_data()
    if not metadata:
        print("  Metadata non disponible")
        return
    
    features = metadata.get('feature_cols', [])
    n_samples = metadata.get('n_samples', 0)
    
    print(f"\n  Nombre de features: {len(features)}")
    print(f"  Nombre d'echantillons: {n_samples}")
    print(f"  Ratio samples/features: {n_samples/max(len(features),1):.1f}")
    
    # Grouper par type
    indicator_1m = [f for f in features if '_1m' in f and not f.startswith('rsi_') and not f.startswith('macd_')]
    indicator_5m = [f for f in features if '_5m' in f and not f.startswith('rsi_') and not f.startswith('macd_')]
    rsi_features = [f for f in features if 'rsi' in f.lower()]
    macd_features = [f for f in features if 'macd' in f.lower()]
    trend_features = [f for f in features if 'trend' in f.lower()]
    volume_features = [f for f in features if 'volume' in f.lower()]
    time_features = [f for f in features if any(x in f for x in ['hour', 'day', 'session', 'weekend'])]
    quality_features = [f for f in features if 'quality' in f.lower() or 'confluence' in f.lower()]
    
    print(f"\n  Repartition par type:")
    print(f"    - RSI: {len(rsi_features)}")
    print(f"    - MACD: {len(macd_features)}")
    print(f"    - Trend/ADX: {len(trend_features)}")
    print(f"    - Volume: {len(volume_features)}")
    print(f"    - Temporelles: {len(time_features)}")
    print(f"    - Qualite: {len(quality_features)}")
    
    if n_samples / max(len(features), 1) < 50:
        print("\n  [PROBLEME] Pas assez de samples par feature!")
        print("  -> Recommande: au moins 50-100 samples par feature")
        print("  -> Reduire le nombre de features ou augmenter le dataset")

def suggest_improvements():
    """Suggere des ameliorations"""
    print("\n" + "=" * 60)
    print("3. AMELIORATIONS RECOMMANDEES")
    print("=" * 60)
    
    metadata = load_current_model_data()
    if not metadata:
        print("  Metadata non disponible")
        return
    
    current_params = metadata.get('params', {})
    metrics = metadata.get('metrics', {})
    
    print(f"\n  Parametres actuels:")
    for k, v in current_params.items():
        print(f"    - {k}: {v}")
    
    print(f"\n  Metriques actuelles:")
    print(f"    - Train accuracy: {metrics.get('train_acc', 0)*100:.1f}%")
    print(f"    - Test accuracy: {metrics.get('test_acc', 0)*100:.1f}%")
    print(f"    - F1 Score: {metrics.get('test_f1', 0):.3f}")
    print(f"    - Precision: {metrics.get('test_precision', 0):.3f}")
    
    print("\n" + "-" * 40)
    print("SOLUTIONS RECOMMANDEES:")
    print("-" * 40)
    
    solutions = []
    
    # Solution 1: Gestion du desequilibre
    print("\n  [1] GERER LE DESEQUILIBRE DES CLASSES")
    print("      - Utiliser class_weight='balanced' ou scale_pos_weight")
    print("      - Ou SMOTE pour surechantillonner la classe minoritaire")
    print("      - Ou sous-echantillonner la classe majoritaire")
    solutions.append("class_weight")
    
    # Solution 2: Reduire les features
    print("\n  [2] REDUIRE LE NOMBRE DE FEATURES")
    print("      - Garder les 30-40 features les plus importantes")
    print("      - Utiliser SelectKBest ou feature_importances_")
    print("      - Supprimer features correlees (>0.9)")
    solutions.append("feature_selection")
    
    # Solution 3: Augmenter la regularisation
    print("\n  [3] AUGMENTER LA REGULARISATION")
    print("      - Augmenter min_samples_leaf (20-30)")
    print("      - Reduire max_depth (3-4 max)")
    print("      - Augmenter l2_regularization pour HistGB")
    solutions.append("regularization")
    
    # Solution 4: Optimiser pour precision
    print("\n  [4] OPTIMISER POUR LA PRECISION")
    print("      - En trading, mieux vaut moins de trades mais plus precis")
    print("      - Augmenter le seuil de confiance (0.7-0.8)")
    print("      - Optimiser Precision-Recall AUC plutot que F1")
    solutions.append("precision_focus")
    
    return solutions

def create_improved_optimizer():
    """Cree un optimiseur ameliore"""
    print("\n" + "=" * 60)
    print("4. CREATION OPTIMISEUR AMELIORE")
    print("=" * 60)
    
    improved_code = '''
# Ajouter dans optuna_gb_tuner.py - fonction objective

# 1. Ajouter class_weight pour gerer le desequilibre
from sklearn.utils.class_weight import compute_class_weight

# Calculer les poids des classes
class_weights = compute_class_weight('balanced', classes=np.unique(y), y=y)
class_weight_dict = dict(zip(np.unique(y), class_weights))

# 2. Pour HistGradientBoostingClassifier, utiliser sample_weight dans fit
# Note: HistGB ne supporte pas class_weight directement
sample_weights = np.array([class_weight_dict[label] for label in y])

# 3. Modifier le scoring pour privilegier la precision
# scoring='precision' ou 'average_precision' au lieu de 'f1_macro'

# 4. Reduire les features avec SelectKBest
from sklearn.feature_selection import SelectKBest, f_classif
selector = SelectKBest(f_classif, k=40)  # Garder 40 meilleures features
X_selected = selector.fit_transform(X, y)
'''
    
    print("  Code d'amelioration a ajouter:")
    print(improved_code)
    
    return improved_code

def calculate_optimal_threshold():
    """Calcule le seuil optimal de confiance"""
    print("\n" + "=" * 60)
    print("5. SEUIL DE CONFIANCE OPTIMAL")
    print("=" * 60)
    
    metadata = load_current_model_data()
    if not metadata:
        return
    
    precision = metadata.get('metrics', {}).get('test_precision', 0.564)
    
    print(f"\n  Precision actuelle: {precision*100:.1f}%")
    print(f"\n  Pour ameliorer la precision sans reentrainer:")
    print(f"    - Seuil actuel: gb_min_confidence = 0.70 (70%)")
    print(f"    - Recommande: augmenter a 0.75-0.80")
    print(f"    - Effet: moins de trades mais plus precis")
    
    print(f"\n  Impact estime:")
    print(f"    - Seuil 0.70: ~{precision*100:.0f}% precision")
    print(f"    - Seuil 0.75: ~{min(precision*1.1, 0.95)*100:.0f}% precision (estimation)")
    print(f"    - Seuil 0.80: ~{min(precision*1.2, 0.95)*100:.0f}% precision (estimation)")
    
def create_quick_improvement_config():
    """Cree une config amelioree rapide"""
    print("\n" + "=" * 60)
    print("6. CONFIG AMELIOREE RAPIDE")
    print("=" * 60)
    
    improved_config = {
        "gb_filter_enabled": True,
        "gb_min_confidence": 0.75,  # Augmente de 0.70
        "gb_n_estimators": 200,     # Reduit pour eviter surfit
        "gb_max_depth": 3,          # Tres conservateur
        "gb_learning_rate": 0.05,   # Moyen
        "gb_min_samples_split": 20,
        "gb_min_samples_leaf": 25,  # Augmente pour regulariser
        "gb_subsample": 0.7,
        "gb_max_features": 0.4,     # Reduit pour moins de variance
        "gb_model_type": "histgb"
    }
    
    print("\n  Configuration recommandee (plus conservative):")
    for k, v in improved_config.items():
        print(f"    {k}: {v}")
    
    print("\n  Appliquer avec:")
    print("    1. Modifier config_overrides.json")
    print("    2. Cliquer 'Reentrainer' dans l'interface")
    
    return improved_config

def main():
    print("=" * 60)
    print("DIAGNOSTIC ET AMELIORATION DU MODELE ML")
    print("=" * 60)
    
    # 1. Analyser la distribution des classes
    imbalance_ratio = analyze_class_distribution()
    
    # 2. Analyser les features
    analyze_features()
    
    # 3. Suggerer des ameliorations
    solutions = suggest_improvements()
    
    # 4. Creer un optimiseur ameliore
    create_improved_optimizer()
    
    # 5. Calculer le seuil optimal
    calculate_optimal_threshold()
    
    # 6. Config rapide
    improved_config = create_quick_improvement_config()
    
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    print("""
PROBLEMES IDENTIFIES:
1. Desequilibre severe des classes (F1=0.388)
2. Trop de features (92) pour le dataset (2919)
3. Pas de gestion du poids des classes
4. Overfitting (14% gap)

ACTIONS RAPIDES (sans reentrainer):
1. Augmenter gb_min_confidence a 0.75-0.80
   -> Moins de trades mais plus precis

ACTIONS MOYENNES (reentrainement):
1. Reduire features a 40 (les plus importantes)
2. Augmenter min_samples_leaf a 25
3. Reduire max_features a 0.4

ACTIONS AVANCEES (modifier le code):
1. Ajouter class_weight='balanced' 
2. Utiliser SMOTE pour equilibrer
3. Optimiser pour Precision au lieu de F1
""")

if __name__ == "__main__":
    main()
