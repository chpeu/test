"""
Script d'optimisation automatique ML complet
============================================
Ce script effectue une optimisation complete du modele ML:
1. Charge les donnees de trades ML utilisables
2. Teste differentes selections de features (RF importance)
3. Optimise les hyperparametres via grid search
4. Analyse les seuils de confiance optimaux
5. Sauvegarde le meilleur modele et les metriques

Usage:
    python scripts/auto_optimize_ml.py
    python scripts/auto_optimize_ml.py --min-trades 100 --splits 20
"""

import os
import sys
import json
import argparse
import warnings
from datetime import datetime
from pathlib import Path

# Ajouter le chemin racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score, precision_score, recall_score,
    confusion_matrix, classification_report
)
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold

warnings.filterwarnings('ignore')


class MLAutoOptimizer:
    """Optimiseur automatique de modele ML pour le trading."""
    
    def __init__(self, output_dir: str = "optimization/saved_models"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Grilles de recherche (HistGradientBoosting params)
        self.feature_counts = [20, 25, 30, 35, 40]
        self.param_grid = {
            'max_depth': [2, 3, 4],
            'learning_rate': [0.03, 0.05, 0.08, 0.1],
            'max_iter': [50, 75, 100, 150],
            'min_samples_leaf': [20, 30, 40, 50],
            'l2_regularization': [0.2, 0.5, 1.0]
        }
        self.threshold_range = np.arange(0.30, 0.70, 0.05)
        
        # Resultats
        self.best_model = None
        self.best_config = None
        self.best_metrics = None
        self.threshold_analysis = None
        self.optimization_history = []
        
    def _emit_progress(self, progress: int, message: str):
        """Émet un message de progression parsable par le backend."""
        # Format: PROGRESS:XX:message
        # Force flush pour s'assurer que le backend le reçoit immédiatement
        print(f"PROGRESS:{progress}:{message}", flush=True)
        sys.stdout.flush()
    
    def load_data(self, timeframe_days: int = 365, min_trades: int = 100):
        """Charge les donnees de trading pour l'entrainement."""
        from optimization.ml_pipeline import prepare_training_dataset
        
        self._emit_progress(10, "Chargement des données...")
        print("=" * 70)
        print("CHARGEMENT DES DONNEES")
        print("=" * 70)
        
        dataset = prepare_training_dataset(
            timeframe_days=timeframe_days,
            min_trades=min_trades
        )
        
        self.X = dataset.X
        self.y = dataset.y
        self.feature_names = list(dataset.X.columns)
        
        n_win = (self.y == 1).sum()
        n_loss = (self.y == 0).sum()
        
        print(f"  Trades charges: {len(self.y)}")
        print(f"  Features disponibles: {len(self.feature_names)}")
        print(f"  Distribution: WIN={n_win} ({n_win/len(self.y)*100:.1f}%) | LOSS={n_loss} ({n_loss/len(self.y)*100:.1f}%)")
        print()
        
        return self
    
    def _select_features_rf(self, X_train, y_train, n_features: int):
        """Selectionne les top N features par importance RandomForest."""
        # n_jobs=1 pour éviter crash joblib/loky sur Windows dans sous-processus
        rf = RandomForestClassifier(
            n_estimators=50, 
            max_depth=5, 
            random_state=42, 
            n_jobs=1
        )
        rf.fit(X_train, y_train)
        
        importances = rf.feature_importances_
        top_idx = np.argsort(importances)[-n_features:]
        
        return top_idx, importances
    
    def optimize(self, n_splits: int = 20, max_overfitting: float = 0.15):
        """
        Optimisation complete du modele.
        
        Args:
            n_splits: Nombre de splits train/test a tester
            max_overfitting: Ecart max train-test accepte
        """
        self._emit_progress(20, "Début optimisation hyperparamètres...")
        print("=" * 70)
        print("OPTIMISATION DU MODELE")
        print("=" * 70)
        print(f"  Splits a tester: {n_splits}")
        print(f"  Features a tester: {self.feature_counts}")
        print(f"  Overfitting max: {max_overfitting*100}%")
        print()
        
        best_score = 0
        best_result = None
        total_configs = 0
        split_count = 0
        
        # Reference: ancien modele
        old_metrics = {'accuracy': 0.6193, 'f1': 0.5654, 'roc_auc': 0.6466}
        
        for split_rs in range(42, 42 + n_splits):
            # Mise à jour progression (20% -> 55% pendant grid search)
            split_count += 1
            progress = 20 + int((split_count / n_splits) * 35)
            self._emit_progress(progress, f"Grid search: split {split_count}/{n_splits}...")
            X_train_full, X_test_full, y_train, y_test = train_test_split(
                self.X, self.y, 
                test_size=0.2, 
                random_state=split_rs, 
                stratify=self.y
            )
            
            for n_features in self.feature_counts:
                # Selection de features
                top_idx, importances = self._select_features_rf(X_train_full, y_train, n_features)
                X_train = X_train_full.iloc[:, top_idx]
                X_test = X_test_full.iloc[:, top_idx]
                selected_features = X_train_full.columns[top_idx].tolist()
                
                # Grid search sur hyperparametres (tous les params HistGB)
                for max_depth in self.param_grid['max_depth']:
                    for lr in self.param_grid['learning_rate']:
                        for max_iter in self.param_grid['max_iter']:
                            for min_leaf in self.param_grid['min_samples_leaf']:
                                for l2_reg in self.param_grid['l2_regularization']:
                                    total_configs += 1
                                    
                                    model = HistGradientBoostingClassifier(
                                        max_depth=max_depth,
                                        learning_rate=lr,
                                        max_iter=max_iter,
                                        min_samples_leaf=min_leaf,
                                        l2_regularization=l2_reg,
                                        random_state=42
                                    )
                                    
                                    model.fit(X_train, y_train)
                                    
                                    # Predictions
                                    y_pred = model.predict(X_test)
                                    y_proba = model.predict_proba(X_test)[:, 1]
                                    y_train_pred = model.predict(X_train)
                                    
                                    # Metriques
                                    train_acc = accuracy_score(y_train, y_train_pred)
                                    test_acc = accuracy_score(y_test, y_pred)
                                    f1 = f1_score(y_test, y_pred)
                                    roc = roc_auc_score(y_test, y_proba)
                                    precision = precision_score(y_test, y_pred)
                                    recall = recall_score(y_test, y_pred)
                                    overfitting = train_acc - test_acc
                                    
                                    # Criteres de selection
                                    if overfitting < max_overfitting:
                                        # Score composite
                                        score = 0.35 * test_acc + 0.35 * f1 + 0.30 * roc
                                        
                                        # Bonus si bat l'ancien modele
                                        beats_old = (
                                            test_acc > old_metrics['accuracy'] and
                                            f1 > old_metrics['f1'] and
                                            roc > old_metrics['roc_auc']
                                        )
                                        if beats_old:
                                            score += 0.1
                                        
                                        if score > best_score:
                                            best_score = score
                                            best_result = {
                                                'model': model,
                                                'split_rs': split_rs,
                                                'n_features': n_features,
                                                'feature_idx': top_idx.tolist(),
                                                'feature_names': selected_features,
                                                'feature_importances': dict(zip(
                                                    selected_features,
                                                    importances[top_idx].tolist()
                                                )),
                                                'params': {
                                                    'max_depth': max_depth,
                                                    'learning_rate': lr,
                                                    'max_iter': max_iter,
                                                    'min_samples_leaf': min_leaf,
                                                    'l2_regularization': l2_reg
                                                },
                                                'metrics': {
                                                    'train_accuracy': train_acc,
                                                    'test_accuracy': test_acc,
                                                    'f1_score': f1,
                                                    'roc_auc': roc,
                                                    'precision': precision,
                                                    'recall': recall,
                                                    'overfitting': overfitting
                                                },
                                                'beats_old': beats_old,
                                                'X_test': X_test,
                                                'y_test': y_test,
                                                'y_proba': y_proba
                                            }
                                            
                                            if beats_old:
                                                print(f"  [NEW BEST] rs={split_rs} feat={n_features} d={max_depth} lr={lr} it={max_iter} leaf={min_leaf} l2={l2_reg}")
                                                print(f"             Acc={test_acc*100:.1f}% F1={f1:.3f} ROC={roc:.4f} Ovf={overfitting*100:.1f}%")
        
        print()
        print(f"  Configurations testees: {total_configs}")
        
        if best_result:
            self.best_model = best_result['model']
            self.best_config = {
                'split_rs': best_result['split_rs'],
                'n_features': best_result['n_features'],
                'feature_idx': best_result['feature_idx'],
                'feature_names': best_result['feature_names'],
                'feature_importances': best_result['feature_importances'],
                'params': best_result['params']
            }
            self.best_metrics = best_result['metrics']
            self._X_test = best_result['X_test']
            self._y_test = best_result['y_test']
            self._y_proba = best_result['y_proba']
            
            print()
            print("=" * 70)
            print("MEILLEUR MODELE TROUVE")
            print("=" * 70)
            print(f"  Features: {best_result['n_features']}")
            print(f"  Params: {best_result['params']}")
            print(f"  Test Accuracy: {best_result['metrics']['test_accuracy']*100:.2f}%")
            print(f"  F1 Score: {best_result['metrics']['f1_score']:.4f}")
            print(f"  ROC-AUC: {best_result['metrics']['roc_auc']:.4f}")
            print(f"  Overfitting: {best_result['metrics']['overfitting']*100:.2f}%")
            print(f"  Bat l'ancien modele: {'OUI' if best_result['beats_old'] else 'NON'}")
        else:
            print("  ATTENTION: Aucun modele satisfaisant trouve!")
        
        return self
    
    def analyze_thresholds(self):
        """Analyse les differents seuils de confiance."""
        if self._y_proba is None:
            raise ValueError("Executez optimize() d'abord")
        
        self._emit_progress(60, "Analyse des seuils de confiance...")
        print()
        print("=" * 70)
        print("ANALYSE DES SEUILS DE CONFIANCE")
        print("=" * 70)
        print()
        print(f"{'Seuil':<10} {'Accuracy':<12} {'F1':<10} {'Precision':<12} {'Recall':<10} {'Pred WIN':<10}")
        print("-" * 70)
        
        results = []
        
        for threshold in self.threshold_range:
            y_pred = (self._y_proba >= threshold).astype(int)
            
            acc = accuracy_score(self._y_test, y_pred)
            f1 = f1_score(self._y_test, y_pred, zero_division=0)
            precision = precision_score(self._y_test, y_pred, zero_division=0)
            recall = recall_score(self._y_test, y_pred, zero_division=0)
            n_pred_win = (y_pred == 1).sum()
            
            results.append({
                'threshold': threshold,
                'accuracy': acc,
                'f1_score': f1,
                'precision': precision,
                'recall': recall,
                'predicted_wins': n_pred_win,
                'total_samples': len(self._y_test)
            })
            
            print(f"{threshold:<10.2f} {acc*100:<12.2f} {f1:<10.4f} {precision:<12.4f} {recall:<10.4f} {n_pred_win:<10}")
        
        self.threshold_analysis = pd.DataFrame(results)
        
        # Trouver les seuils optimaux
        best_acc_idx = self.threshold_analysis['accuracy'].idxmax()
        best_f1_idx = self.threshold_analysis['f1_score'].idxmax()
        best_precision_idx = self.threshold_analysis['precision'].idxmax()
        
        # Score composite pour seuil equilibre (trading: precision > recall pour eviter faux positifs)
        # Precision = 0.4 (eviter de trader sur de mauvais signaux)
        # Accuracy = 0.3 (performance globale)
        # F1 = 0.2 (equilibre general)
        # Recall = 0.1 (moins important - mieux vaut rater une opportunite que perdre de l'argent)
        self.threshold_analysis['composite'] = (
            0.4 * self.threshold_analysis['precision'] +
            0.3 * self.threshold_analysis['accuracy'] +
            0.2 * self.threshold_analysis['f1_score'] +
            0.1 * self.threshold_analysis['recall']
        )
        best_composite_idx = self.threshold_analysis['composite'].idxmax()
        
        print()
        print("SEUILS OPTIMAUX:")
        print(f"  - Meilleur Accuracy: {self.threshold_analysis.loc[best_acc_idx, 'threshold']:.2f} ({self.threshold_analysis.loc[best_acc_idx, 'accuracy']*100:.2f}%)")
        print(f"  - Meilleur F1: {self.threshold_analysis.loc[best_f1_idx, 'threshold']:.2f} ({self.threshold_analysis.loc[best_f1_idx, 'f1_score']:.4f})")
        print(f"  - Meilleure Precision: {self.threshold_analysis.loc[best_precision_idx, 'threshold']:.2f} ({self.threshold_analysis.loc[best_precision_idx, 'precision']:.4f})")
        print(f"  - Meilleur Equilibre: {self.threshold_analysis.loc[best_composite_idx, 'threshold']:.2f}")
        
        # Ajouter au best_config
        self.best_config['optimal_thresholds'] = {
            'best_accuracy': float(self.threshold_analysis.loc[best_acc_idx, 'threshold']),
            'best_f1': float(self.threshold_analysis.loc[best_f1_idx, 'threshold']),
            'best_precision': float(self.threshold_analysis.loc[best_precision_idx, 'threshold']),
            'best_balanced': float(self.threshold_analysis.loc[best_composite_idx, 'threshold'])
        }
        
        return self
    
    def cross_validate(self, n_folds: int = 5):
        """Validation croisee du meilleur modele."""
        if self.best_model is None:
            raise ValueError("Executez optimize() d'abord")
        
        self._emit_progress(75, "Validation croisée en cours...")
        print()
        print("=" * 70)
        print("VALIDATION CROISEE")
        print("=" * 70)
        
        # Recreer le dataset avec les features selectionnees
        X_selected = self.X.iloc[:, self.best_config['feature_idx']]
        
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        
        cv_acc = cross_val_score(self.best_model, X_selected, self.y, cv=cv, scoring='accuracy')
        cv_f1 = cross_val_score(self.best_model, X_selected, self.y, cv=cv, scoring='f1')
        cv_roc = cross_val_score(self.best_model, X_selected, self.y, cv=cv, scoring='roc_auc')
        
        print(f"  CV Accuracy: {np.mean(cv_acc)*100:.2f}% (+/- {np.std(cv_acc)*100:.2f}%)")
        print(f"  CV F1 Score: {np.mean(cv_f1):.4f} (+/- {np.std(cv_f1):.4f})")
        print(f"  CV ROC-AUC: {np.mean(cv_roc):.4f} (+/- {np.std(cv_roc):.4f})")
        
        self.best_metrics['cv_accuracy_mean'] = float(np.mean(cv_acc))
        self.best_metrics['cv_accuracy_std'] = float(np.std(cv_acc))
        self.best_metrics['cv_f1_mean'] = float(np.mean(cv_f1))
        self.best_metrics['cv_f1_std'] = float(np.std(cv_f1))
        self.best_metrics['cv_roc_mean'] = float(np.mean(cv_roc))
        self.best_metrics['cv_roc_std'] = float(np.std(cv_roc))
        
        return self
    
    def save(self):
        """Sauvegarde le modele et les metadonnees."""
        if self.best_model is None:
            raise ValueError("Aucun modele a sauvegarder")
        
        self._emit_progress(90, "Sauvegarde du modèle...")
        print()
        print("=" * 70)
        print("SAUVEGARDE")
        print("=" * 70)
        
        # Modele pickle
        model_path = self.output_dir / "best_classifier_latest.pkl"
        model_data = {
            'model': self.best_model,
            'feature_selector_idx': self.best_config['feature_idx'],
            'feature_names': self.best_config['feature_names'],
            'params': self.best_config['params'],
            'n_features': self.best_config['n_features'],
            'optimal_thresholds': self.best_config.get('optimal_thresholds', {})
        }
        joblib.dump(model_data, model_path)
        print(f"  Modele: {model_path}")
        
        # Metadata JSON
        metadata_path = self.output_dir / "best_classifier_metadata.json"
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'model_type': 'HistGradientBoostingClassifier',
            'n_features': self.best_config['n_features'],
            'params': self.best_config['params'],
            'metrics': self.best_metrics,
            'optimal_thresholds': self.best_config.get('optimal_thresholds', {}),
            'feature_names': self.best_config['feature_names'],
            'feature_importances': self.best_config['feature_importances'],
            'comparison_vs_baseline': {
                'baseline_accuracy': 0.6193,
                'baseline_f1': 0.5654,
                'baseline_roc': 0.6466,
                'accuracy_diff': round(self.best_metrics['test_accuracy'] - 0.6193, 4),
                'f1_diff': round(self.best_metrics['f1_score'] - 0.5654, 4),
                'roc_diff': round(self.best_metrics['roc_auc'] - 0.6466, 4)
            }
        }
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"  Metadata: {metadata_path}")
        
        # Threshold analysis CSV
        if self.threshold_analysis is not None:
            threshold_path = self.output_dir / "threshold_analysis.csv"
            self.threshold_analysis.to_csv(threshold_path, index=False)
            print(f"  Thresholds: {threshold_path}")
        
        # Rapport complet
        report_path = self.output_dir / "optimization_report.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("RAPPORT D'OPTIMISATION ML\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("METRIQUES FINALES\n")
            f.write("-" * 40 + "\n")
            f.write(f"Test Accuracy: {self.best_metrics['test_accuracy']*100:.2f}%\n")
            f.write(f"F1 Score: {self.best_metrics['f1_score']:.4f}\n")
            f.write(f"ROC-AUC: {self.best_metrics['roc_auc']:.4f}\n")
            f.write(f"Precision: {self.best_metrics['precision']:.4f}\n")
            f.write(f"Recall: {self.best_metrics['recall']:.4f}\n")
            f.write(f"Overfitting: {self.best_metrics['overfitting']*100:.2f}%\n")
            if 'cv_accuracy_mean' in self.best_metrics:
                f.write(f"\nCV Accuracy: {self.best_metrics['cv_accuracy_mean']*100:.2f}% (+/- {self.best_metrics['cv_accuracy_std']*100:.2f}%)\n")
            f.write("\n")
            
            f.write("HYPERPARAMETRES\n")
            f.write("-" * 40 + "\n")
            for k, v in self.best_config['params'].items():
                f.write(f"{k}: {v}\n")
            f.write("\n")
            
            f.write(f"FEATURES ({self.best_config['n_features']})\n")
            f.write("-" * 40 + "\n")
            for fname in self.best_config['feature_names']:
                imp = self.best_config['feature_importances'].get(fname, 0)
                f.write(f"  - {fname}: {imp:.4f}\n")
            f.write("\n")
            
            if self.best_config.get('optimal_thresholds'):
                f.write("SEUILS OPTIMAUX\n")
                f.write("-" * 40 + "\n")
                for k, v in self.best_config['optimal_thresholds'].items():
                    f.write(f"{k}: {v:.2f}\n")
        
        print(f"  Rapport: {report_path}")
        
        return self
    
    def run(self, timeframe_days: int = 365, min_trades: int = 100, n_splits: int = 20):
        """Execute l'optimisation complete."""
        print()
        print("=" * 70)
        print("OPTIMISATION AUTOMATIQUE ML - DEBUT")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
        self.load_data(timeframe_days=timeframe_days, min_trades=min_trades)
        self.optimize(n_splits=n_splits)
        
        if self.best_model is not None:
            self.analyze_thresholds()
            self.cross_validate()
            self.save()
        
        self._emit_progress(100, "Optimisation terminée!")
        print()
        print("=" * 70)
        print("OPTIMISATION TERMINEE")
        print("=" * 70)
        
        return self


def main():
    try:
        parser = argparse.ArgumentParser(description="Optimisation automatique du modele ML")
        parser.add_argument('--timeframe', type=int, default=365, help="Jours de donnees a utiliser")
        parser.add_argument('--min-trades', type=int, default=100, help="Minimum de trades requis")
        parser.add_argument('--splits', type=int, default=20, help="Nombre de splits a tester")
        
        args = parser.parse_args()
        
        optimizer = MLAutoOptimizer()
        optimizer.run(
            timeframe_days=args.timeframe,
            min_trades=args.min_trades,
            n_splits=args.splits
        )
    except Exception as e:
        print(f"ERROR:CRITICAL:{str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
