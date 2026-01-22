#!/usr/bin/env python3
"""
VERIFICATION COMPLETE DU SYSTEME ML GRADIENTBOOSTING/HISTGRADIENTBOOSTING

Ce script verifie:
1. Configuration et parametres
2. Modele et fichiers
3. Pipeline d'entrainement
4. Optimisation Optuna
5. Application des hyperparametres
6. Integration avec le bot de trading
7. Mise a jour des metriques frontend
8. Predictions en temps reel
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
import traceback

# Fix encodage Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

class MLVerifier:
    def __init__(self):
        self.checks = []
        self.errors = []
        self.warnings = []
        self.suggestions = []
        
    def add_check(self, name: str, status: str, details: str = "", suggestion: str = ""):
        icon = "[OK]" if status == "OK" else "[WARN]" if status == "WARN" else "[ERROR]"
        self.checks.append({
            'name': name,
            'status': status,
            'details': details,
            'suggestion': suggestion
        })
        print(f"{icon} {name}: {details}")
        
        if status == "ERROR":
            self.errors.append(f"{name}: {details}")
        elif status == "WARN":
            self.warnings.append(f"{name}: {details}")
        if suggestion:
            self.suggestions.append(f"{name}: {suggestion}")
    
    def run_all_checks(self):
        print("=" * 70)
        print("VERIFICATION COMPLETE SYSTEME ML GRADIENTBOOSTING")
        print("=" * 70)
        
        self.check_1_imports()
        self.check_2_config()
        self.check_3_model_files()
        self.check_4_training_pipeline()
        self.check_5_optuna_integration()
        self.check_6_bot_integration()
        self.check_7_frontend_metrics()
        self.check_8_prediction_system()
        self.check_9_histgb_support()
        self.check_10_performance()
        
        self.print_summary()
        
    def check_1_imports(self):
        print("\n[1] VERIFICATION DES IMPORTS...")
        
        try:
            from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
            self.add_check("sklearn.ensemble", "OK", "GB et HistGB disponibles")
        except Exception as e:
            self.add_check("sklearn.ensemble", "ERROR", str(e))
        
        try:
            import optuna
            self.add_check("optuna", "OK", f"Version {optuna.__version__}")
        except Exception as e:
            self.add_check("optuna", "ERROR", str(e))
        
        try:
            from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
            self.add_check("optuna_gb_tuner", "OK", "Classe importee")
        except Exception as e:
            self.add_check("optuna_gb_tuner", "ERROR", str(e))
        
        try:
            from optimization.predictor_optimized import OptimizedPredictor
            self.add_check("predictor_optimized", "OK", "Classe importee")
        except Exception as e:
            self.add_check("predictor_optimized", "ERROR", str(e))
    
    def check_2_config(self):
        print("\n[2] VERIFICATION CONFIGURATION...")
        
        try:
            from config import TRADING_CONFIG
            
            gb_params = [
                'gb_filter_enabled', 'gb_min_confidence', 'gb_n_estimators',
                'gb_max_depth', 'gb_learning_rate', 'gb_min_samples_split',
                'gb_min_samples_leaf', 'gb_subsample', 'gb_max_features', 'gb_model_type'
            ]
            
            missing = [p for p in gb_params if p not in TRADING_CONFIG]
            present = [p for p in gb_params if p in TRADING_CONFIG]
            
            if missing:
                self.add_check("TRADING_CONFIG", "WARN", 
                             f"Manquants: {missing}",
                             f"Ajouter {missing} dans config.py")
            else:
                self.add_check("TRADING_CONFIG", "OK", f"{len(present)} params GB")
            
            # Afficher valeurs actuelles
            print(f"   gb_filter_enabled: {TRADING_CONFIG.get('gb_filter_enabled')}")
            print(f"   gb_min_confidence: {TRADING_CONFIG.get('gb_min_confidence')}")
            print(f"   gb_model_type: {TRADING_CONFIG.get('gb_model_type', 'gb')}")
            print(f"   gb_n_estimators: {TRADING_CONFIG.get('gb_n_estimators')}")
            print(f"   gb_max_depth: {TRADING_CONFIG.get('gb_max_depth')}")
            print(f"   gb_learning_rate: {TRADING_CONFIG.get('gb_learning_rate')}")
            
        except Exception as e:
            self.add_check("TRADING_CONFIG", "ERROR", str(e))
        
        # Verifier config_overrides.json
        try:
            overrides_path = Path("config_overrides.json")
            if overrides_path.exists():
                with open(overrides_path, 'r') as f:
                    overrides = json.load(f)
                gb_overrides = {k: v for k, v in overrides.items() if k.startswith('gb_')}
                self.add_check("config_overrides.json", "OK", f"{len(gb_overrides)} params GB persistes")
            else:
                self.add_check("config_overrides.json", "WARN", "Fichier non trouve")
        except Exception as e:
            self.add_check("config_overrides.json", "ERROR", str(e))
    
    def check_3_model_files(self):
        print("\n[3] VERIFICATION FICHIERS MODELE...")
        
        models_dir = Path("optimization/saved_models")
        
        if not models_dir.exists():
            self.add_check("Dossier modeles", "ERROR", "optimization/saved_models n'existe pas")
            return
        
        # Chercher modeles
        model_files = list(models_dir.glob("*classifier*.pkl"))
        if model_files:
            latest = max(model_files, key=lambda p: p.stat().st_mtime)
            age_hours = (datetime.now().timestamp() - latest.stat().st_mtime) / 3600
            self.add_check("Fichier modele", "OK", f"{latest.name} (age: {age_hours:.1f}h)")
        else:
            self.add_check("Fichier modele", "ERROR", "Aucun modele .pkl trouve",
                         "Entrainer un modele via l'interface")
        
        # Verifier metadata
        meta_path = models_dir / "best_classifier_metadata.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            acc = meta.get('metrics', {}).get('test_acc', 0)
            gap = meta.get('metrics', {}).get('gap', 0)
            n_features = len(meta.get('feature_cols', []))
            self.add_check("Metadata modele", "OK", 
                         f"Acc={acc*100:.1f}%, Gap={gap*100:.1f}%, {n_features} features")
            
            # Alerter si overfitting
            if gap > 0.15:
                self.add_check("Overfitting", "WARN", 
                             f"Gap={gap*100:.1f}% > 15%",
                             "Augmenter regularisation ou reduire max_depth")
        else:
            self.add_check("Metadata modele", "WARN", "Pas de metadata.json")
        
        # Verifier resultats Optuna
        optuna_path = models_dir / "gb_optuna_results.json"
        if optuna_path.exists():
            with open(optuna_path, 'r') as f:
                optuna_results = json.load(f)
            best_score = optuna_results.get('best_score', 0)
            n_trials = optuna_results.get('n_trials', 0)
            self.add_check("Resultats Optuna", "OK", f"Best F1={best_score:.4f}, {n_trials} trials")
        else:
            self.add_check("Resultats Optuna", "WARN", "Pas d'optimisation precedente")
    
    def check_4_training_pipeline(self):
        print("\n[4] VERIFICATION PIPELINE ENTRAINEMENT...")
        
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            # Test chargement donnees
            df = load_features_from_postgres(timeframe_days=7, min_trades=10)
            if df is not None and len(df) > 0:
                self.add_check("Chargement donnees", "OK", f"{len(df)} trades charges")
            else:
                self.add_check("Chargement donnees", "ERROR", "Aucune donnee")
                return
            
            # Test feature engineering
            df_features = calculate_derived_features(df)
            
            import numpy as np
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
            numeric_cols = df_features.select_dtypes(include=[np.number]).columns.tolist()
            feature_cols = [c for c in numeric_cols if c not in exclude_cols]
            feature_cols = [c for c in feature_cols if df_features[c].nunique() > 1]
            
            self.add_check("Feature engineering", "OK", f"{len(feature_cols)} features")
            
            # Verifier target
            if 'target_win' in df_features.columns:
                win_rate = df_features['target_win'].mean() * 100
                self.add_check("Target column", "OK", f"Win rate: {win_rate:.1f}%")
            else:
                self.add_check("Target column", "ERROR", "target_win manquant")
                
        except Exception as e:
            self.add_check("Pipeline entrainement", "ERROR", str(e))
    
    def check_5_optuna_integration(self):
        print("\n[5] VERIFICATION INTEGRATION OPTUNA...")
        
        try:
            from optimization.optuna_gb_tuner import GradientBoostingOptunaOptimizer
            
            # Test creation avec GB standard
            opt_gb = GradientBoostingOptunaOptimizer(n_trials=2, timeout_minutes=1, model_type='gb')
            self.add_check("Optuna GB", "OK", "Instance creee")
            
            # Test creation avec HistGB
            opt_histgb = GradientBoostingOptunaOptimizer(n_trials=2, timeout_minutes=1, model_type='histgb')
            self.add_check("Optuna HistGB", "OK", "Instance creee")
            
            # Verifier que model_type est stocke
            if hasattr(opt_histgb, 'model_type') and opt_histgb.model_type == 'histgb':
                self.add_check("model_type stocke", "OK", "histgb")
            else:
                self.add_check("model_type stocke", "ERROR", "Attribut manquant")
                
        except Exception as e:
            self.add_check("Integration Optuna", "ERROR", str(e))
    
    def check_6_bot_integration(self):
        print("\n[6] VERIFICATION INTEGRATION BOT TRADING...")
        
        # PROBLEME CRITIQUE: Verifier si gb_filter_enabled est utilise
        scanner_loop_path = Path("core/callbacks/scanner_loop.py")
        
        if scanner_loop_path.exists():
            with open(scanner_loop_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verifier si gb_filter_enabled est utilise
            if 'gb_filter_enabled' in content:
                self.add_check("GB filter dans scanner", "OK", "gb_filter_enabled utilise")
            else:
                self.add_check("GB filter dans scanner", "ERROR", 
                             "gb_filter_enabled NON utilise dans scanner_loop.py!",
                             "Le filtre GradientBoosting n'est PAS connecte au trading!")
            
            # Verifier si OptimizedPredictor est utilise
            if 'OptimizedPredictor' in content or 'predictor_optimized' in content:
                self.add_check("OptimizedPredictor", "OK", "Importe dans scanner")
            else:
                self.add_check("OptimizedPredictor", "WARN", 
                             "OptimizedPredictor non importe dans scanner_loop.py",
                             "Le modele GB n'est pas utilise pour les predictions")
            
            # Verifier quel modele est utilise
            if "model_name=ML_CONFIG.get('model_name'" in content:
                self.add_check("Modele utilise", "WARN",
                             "Utilise ML_CONFIG['model_name'] (XGBoost)",
                             "Modifier pour utiliser le modele GB si gb_filter_enabled")
        else:
            self.add_check("scanner_loop.py", "ERROR", "Fichier non trouve")
    
    def check_7_frontend_metrics(self):
        print("\n[7] VERIFICATION MISE A JOUR METRIQUES FRONTEND...")
        
        # Verifier l'endpoint /api/ml/models/overview
        try:
            # Simuler l'appel API
            from api.routes.ml import router
            self.add_check("API routes ml", "OK", "Module importe")
            
            # Verifier que les metriques sont retournees correctement
            # apres un entrainement
            frontend_path = Path("frontend/src/lib/components/ml/MLCONTENT_GB_Variables.svelte")
            if frontend_path.exists():
                with open(frontend_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Verifier le rechargement des metriques
                if 'loadMLMetricsGB' in content:
                    self.add_check("loadMLMetricsGB", "OK", "Fonction presente")
                else:
                    self.add_check("loadMLMetricsGB", "ERROR", "Fonction manquante")
                
                # Verifier l'appel apres entrainement
                if "await loadMLMetricsGB()" in content:
                    self.add_check("Reload apres train", "OK", "loadMLMetricsGB appele apres entrainement")
                else:
                    self.add_check("Reload apres train", "WARN",
                                 "loadMLMetricsGB peut ne pas etre appele apres entrainement",
                                 "Verifier que les metriques se mettent a jour")
            else:
                self.add_check("Frontend GB", "ERROR", "Fichier non trouve")
                
        except Exception as e:
            self.add_check("Frontend metrics", "ERROR", str(e))
    
    def check_8_prediction_system(self):
        print("\n[8] VERIFICATION SYSTEME PREDICTION...")
        
        try:
            from optimization.predictor_optimized import OptimizedPredictor
            
            predictor = OptimizedPredictor()
            
            if predictor.is_loaded:
                self.add_check("OptimizedPredictor", "OK", "Modele charge")
                
                # Verifier les features attendues
                if predictor.feature_cols:
                    self.add_check("Feature cols", "OK", f"{len(predictor.feature_cols)} features")
                else:
                    self.add_check("Feature cols", "WARN", "Liste features non chargee")
                
                # Test prediction avec donnees fictives
                import numpy as np
                n_features = len(predictor.feature_cols) if predictor.feature_cols else 90
                fake_features = {f"feature_{i}": np.random.randn() for i in range(n_features)}
                
                try:
                    should_trade, confidence = predictor.predict(fake_features)
                    self.add_check("Test prediction", "OK", 
                                 f"should_trade={should_trade}, confidence={confidence:.3f}")
                except Exception as pred_err:
                    self.add_check("Test prediction", "ERROR", str(pred_err))
            else:
                self.add_check("OptimizedPredictor", "ERROR", "Modele non charge")
                
        except Exception as e:
            self.add_check("Systeme prediction", "ERROR", str(e))
    
    def check_9_histgb_support(self):
        print("\n[9] VERIFICATION SUPPORT HISTGRADIENTBOOSTING...")
        
        try:
            from config import TRADING_CONFIG
            model_type = TRADING_CONFIG.get('gb_model_type', 'gb')
            
            self.add_check("model_type config", "OK", f"'{model_type}'")
            
            # Verifier que l'entrainement utilise le bon modele
            ml_routes_path = Path("api/routes/ml.py")
            if ml_routes_path.exists():
                with open(ml_routes_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "model_type=model_type" in content or "model_type=TRADING_CONFIG" in content:
                    self.add_check("Optuna model_type", "OK", "model_type passe a l'optimiseur")
                else:
                    self.add_check("Optuna model_type", "WARN",
                                 "model_type peut ne pas etre passe a l'optimiseur",
                                 "Verifier _run_gb_optuna_optimization")
                
                # Verifier l'entrainement
                if "HistGradientBoostingClassifier" in content:
                    self.add_check("HistGB dans train", "OK", "Import present")
                else:
                    self.add_check("HistGB dans train", "WARN",
                                 "HistGradientBoostingClassifier non importe dans ml.py",
                                 "L'entrainement utilise toujours GradientBoosting")
            
        except Exception as e:
            self.add_check("Support HistGB", "ERROR", str(e))
    
    def check_10_performance(self):
        print("\n[10] VERIFICATION PERFORMANCE ET AMELIORATIONS...")
        
        # Charger les metriques actuelles
        meta_path = Path("optimization/saved_models/best_classifier_metadata.json")
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                meta = json.load(f)
            
            test_acc = meta.get('metrics', {}).get('test_acc', 0)
            train_acc = meta.get('metrics', {}).get('train_acc', 0)
            gap = train_acc - test_acc
            
            # Recommandations basees sur les metriques
            if test_acc < 0.55:
                self.suggestions.append("Accuracy faible (<55%): Ajouter plus de features ou plus de donnees")
            elif test_acc < 0.60:
                self.suggestions.append("Accuracy acceptable (55-60%): Essayer Optuna pour optimiser")
            else:
                self.add_check("Performance", "OK", f"Accuracy={test_acc*100:.1f}% (bonne)")
            
            if gap > 0.15:
                self.suggestions.append(f"Overfitting eleve ({gap*100:.1f}%): Reduire max_depth ou augmenter regularisation")
            elif gap > 0.10:
                self.suggestions.append(f"Overfitting modere ({gap*100:.1f}%): Surveiller")
            else:
                self.add_check("Overfitting", "OK", f"Gap={gap*100:.1f}% (acceptable)")
        
        # Suggestions generales
        self.suggestions.append("Utiliser HistGradientBoosting pour Optuna (10x plus rapide)")
        self.suggestions.append("Augmenter n_trials Optuna a 200+ pour de meilleurs resultats")
        self.suggestions.append("Ajouter features temporelles supplementaires (jour de semaine, heure)")
    
    def print_summary(self):
        print("\n" + "=" * 70)
        print("RESUME")
        print("=" * 70)
        
        ok_count = len([c for c in self.checks if c['status'] == 'OK'])
        warn_count = len([c for c in self.checks if c['status'] == 'WARN'])
        error_count = len([c for c in self.checks if c['status'] == 'ERROR'])
        
        print(f"\nResultats: {ok_count} OK / {warn_count} WARN / {error_count} ERROR")
        
        if self.errors:
            print(f"\n[ERREURS CRITIQUES] ({len(self.errors)})")
            for err in self.errors:
                print(f"  - {err}")
        
        if self.warnings:
            print(f"\n[AVERTISSEMENTS] ({len(self.warnings)})")
            for warn in self.warnings:
                print(f"  - {warn}")
        
        if self.suggestions:
            print(f"\n[SUGGESTIONS D'AMELIORATION] ({len(self.suggestions)})")
            for i, sugg in enumerate(self.suggestions[:10], 1):  # Max 10
                print(f"  {i}. {sugg}")
        
        print("\n" + "=" * 70)
        if error_count == 0:
            print("[SUCCESS] Systeme ML fonctionnel!")
        else:
            print(f"[ATTENTION] {error_count} erreur(s) critique(s) a corriger!")
        print("=" * 70)
        
        return error_count == 0


def main():
    verifier = MLVerifier()
    success = verifier.run_all_checks()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
