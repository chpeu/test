#!/usr/bin/env python3
"""
Boucle de verification complete du systeme GradientBoosting
Verifie tous les composants avant de lancer Optuna
"""

import sys
import json
from pathlib import Path

# Fix encodage Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def print_status(name: str, status: str, details: str = ""):
    icon = "[OK]" if status == "OK" else "[WARN]" if status == "WARN" else "[ERROR]"
    print(f"{icon} {name}: {details}")
    return status == "OK"

def main():
    print("=" * 60)
    print("VERIFICATION SYSTEME GRADIENTBOOSTING")
    print("=" * 60)
    
    all_ok = True
    
    # 1. Imports critiques
    print("\n[1] Verification des imports...")
    
    try:
        from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
        print_status("optuna_gb_tuner", "OK", "GradientBoostingOptunaOptimizer importé")
    except Exception as e:
        all_ok = False
        print_status("optuna_gb_tuner", "ERROR", str(e))
    
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        print_status("feature_loader", "OK", "load_features_from_postgres importé")
    except Exception as e:
        all_ok = False
        print_status("feature_loader", "ERROR", str(e))
    
    try:
        from optimization.data.feature_engineering import calculate_derived_features
        print_status("feature_engineering", "OK", "calculate_derived_features importé")
    except Exception as e:
        all_ok = False
        print_status("feature_engineering", "ERROR", str(e))
    
    try:
        import optuna
        print_status("optuna", "OK", f"Version {optuna.__version__}")
    except Exception as e:
        all_ok = False
        print_status("optuna", "ERROR", str(e))
    
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        print_status("sklearn", "OK", "GradientBoostingClassifier disponible")
    except Exception as e:
        all_ok = False
        print_status("sklearn", "ERROR", str(e))
    
    # 2. Chargement données
    print("\n[2] Verification chargement donnees...")
    
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        df = load_features_from_postgres(timeframe_days=120, min_trades=30)
        
        if df is not None and len(df) > 0:
            print_status("PostgreSQL", "OK", f"{len(df)} trades chargés")
        else:
            all_ok = False
            print_status("PostgreSQL", "ERROR", "Aucune donnée chargée")
    except Exception as e:
        all_ok = False
        print_status("PostgreSQL", "ERROR", str(e))
    
    # 3. Feature engineering
    print("\n[3] Verification feature engineering...")
    
    try:
        from optimization.data.feature_engineering import calculate_derived_features
        import pandas as pd
        import numpy as np
        
        if df is not None and len(df) > 0:
            df_features = calculate_derived_features(df)
            
            # Compter features numériques
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
            numeric_cols = df_features.select_dtypes(include=[np.number]).columns.tolist()
            feature_cols = [c for c in numeric_cols if c not in exclude_cols]
            feature_cols = [c for c in feature_cols if df_features[c].nunique() > 1]
            
            print_status("Feature Engineering", "OK", f"{len(feature_cols)} features valides")
            
            # Vérifier target
            if 'target_win' in df_features.columns:
                win_rate = df_features['target_win'].mean() * 100
                print_status("Target", "OK", f"target_win présent (win_rate={win_rate:.1f}%)")
            else:
                all_ok = False
                print_status("Target", "ERROR", "target_win manquant")
        else:
            print_status("Feature Engineering", "WARN", "Pas de données à traiter")
    except Exception as e:
        all_ok = False
        print_status("Feature Engineering", "ERROR", str(e))
    
    # 4. Config TRADING_CONFIG
    print("\n[4] Verification configuration...")
    
    try:
        from config import TRADING_CONFIG
        
        gb_params = [
            'gb_filter_enabled', 'gb_min_confidence', 'gb_n_estimators',
            'gb_max_depth', 'gb_learning_rate', 'gb_min_samples_split',
            'gb_min_samples_leaf', 'gb_subsample', 'gb_max_features'
        ]
        
        missing = [p for p in gb_params if p not in TRADING_CONFIG]
        if missing:
            all_ok = False
            print_status("TRADING_CONFIG", "ERROR", f"Paramètres manquants: {missing}")
        else:
            print_status("TRADING_CONFIG", "OK", f"{len(gb_params)} paramètres GB présents")
    except Exception as e:
        all_ok = False
        print_status("TRADING_CONFIG", "ERROR", str(e))
    
    # 5. Fichiers modèle
    print("\n[5] Verification fichiers modele...")
    
    models_dir = Path("optimization/saved_models")
    if models_dir.exists():
        model_files = list(models_dir.glob("*classifier*.pkl"))
        if model_files:
            latest = max(model_files, key=lambda p: p.stat().st_mtime)
            print_status("Fichier modèle", "OK", f"{latest.name}")
        else:
            print_status("Fichier modèle", "WARN", "Aucun modèle .pkl trouvé")
        
        metadata_file = models_dir / "best_classifier_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                meta = json.load(f)
            acc = meta.get('metrics', {}).get('test_acc', 0)
            print_status("Métadonnées", "OK", f"Accuracy={acc*100:.1f}%")
        else:
            print_status("Métadonnées", "WARN", "Pas de metadata.json")
    else:
        print_status("Dossier modèles", "WARN", "optimization/saved_models n'existe pas")
    
    # 6. Test rapide Optuna (sans vraiment lancer)
    print("\n[6] Verification Optuna...")
    
    try:
        from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
        
        optimizer = GradientBoostingOptunaOptimizer(
            n_trials=5,  # Juste pour tester
            timeout_minutes=1,
            cv_folds=3
        )
        
        print_status("Optuna Optimizer", "OK", "Instance créée avec succès")
        
        # Test rapide avec données minimales si disponible
        if df is not None and len(df) >= 100:
            import numpy as np
            
            # Préparer mini-dataset
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
            numeric_cols = df_features.select_dtypes(include=[np.number]).columns.tolist()
            feature_cols = [c for c in numeric_cols if c not in exclude_cols]
            feature_cols = [c for c in feature_cols if df_features[c].nunique() > 1][:20]  # Limiter pour test rapide
            
            X = df_features[feature_cols].fillna(0).values[:200]  # 200 samples max
            y = df_features['target_win'].astype(int).values[:200]
            
            print_status("Dataset test", "OK", f"Shape: {X.shape}")
            
            # Test très rapide (2 trials seulement)
            print("  -> Test rapide Optuna (2 trials)...")
            optimizer_test = GradientBoostingOptunaOptimizer(n_trials=2, timeout_minutes=1, cv_folds=2)
            result = optimizer_test.optimize(X, y)
            
            if result['success']:
                print_status("Optuna Test", "OK", f"Best F1={result['best_score']:.4f}")
            else:
                print_status("Optuna Test", "WARN", result.get('error', 'Échec'))
    except Exception as e:
        all_ok = False
        print_status("Optuna", "ERROR", str(e))
    
    # Résumé
    print("\n" + "=" * 60)
    if all_ok:
        print("[SUCCESS] SYSTEME OK - Pret pour l'optimisation Optuna!")
        print("\nPour lancer l'optimisation complete:")
        print("  -> Frontend: Bouton 'Lancer Optimisation Optuna'")
        print("  -> API: POST /api/ml/optimize_gb?n_trials=100")
    else:
        print("[FAILED] ERREURS DETECTEES - Corriger avant de lancer Optuna")
    print("=" * 60)
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
