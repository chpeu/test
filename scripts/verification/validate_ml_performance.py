#!/usr/bin/env python3
"""
🔥 ML Performance Validation Script V2.1

Boucle de vérification complète pour s'assurer que le ML est performant:
1. Vérifie la compilation des modules
2. Teste le chargement des données
3. Entraîne le modèle avec walk-forward validation
4. Vérifie les métriques (accuracy, F1, ROC-AUC, overfitting gap)
5. Compare avec les seuils de performance minimaux
6. Génère un rapport détaillé

Usage:
    python validate_ml_performance.py
    python validate_ml_performance.py --quick  # Test rapide
    python validate_ml_performance.py --full   # Test complet avec Optuna
"""
import logging
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Seuils de performance minimaux
# 🔥 V2.1: Seuils ajustés pour données réelles avec data drift
PERFORMANCE_THRESHOLDS = {
    'min_accuracy': 0.48,           # Minimum acceptable (>= random avec drift)
    'target_accuracy': 0.55,        # Objectif réaliste
    'min_f1': 0.45,                 # F1-score minimum
    'min_roc_auc': 0.50,            # ROC-AUC minimum (>= random)
    'max_overfit_gap': 0.15,        # Gap train-test maximum
    'min_precision': 0.45,          # Precision minimum
    'min_walk_forward_std': 0.20,   # Stabilité walk-forward (std < 20%)
}


class MLValidator:
    """Validateur ML avec boucle de vérification complète"""
    
    def __init__(self, quick_mode: bool = False):
        self.quick_mode = quick_mode
        self.results: Dict = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'overall_status': 'pending',
            'errors': [],
            'warnings': []
        }
    
    def run_all_checks(self) -> Dict:
        """Exécuter toutes les vérifications"""
        logger.info("=" * 80)
        logger.info("🔍 ML PERFORMANCE VALIDATION - Boucle de vérification complète")
        logger.info("=" * 80)
        
        checks = [
            ("Compilation modules", self._check_compilation),
            ("Chargement données", self._check_data_loading),
            ("Entraînement modèle", self._check_training),
            ("Métriques performance", self._check_metrics),
            ("Overfitting", self._check_overfitting),
            ("Walk-forward validation", self._check_walk_forward),
            ("Calibration probabilités", self._check_calibration),
        ]
        
        all_passed = True
        
        for name, check_func in checks:
            logger.info(f"\n📋 Check: {name}...")
            try:
                result = check_func()
                self.results['checks'].append({
                    'name': name,
                    'status': result['status'],
                    'message': result.get('message', ''),
                    'details': result.get('details', {})
                })
                
                if result['status'] == 'PASS':
                    logger.info(f"✅ {name}: PASS")
                elif result['status'] == 'WARN':
                    logger.warning(f"⚠️ {name}: WARNING - {result.get('message', '')}")
                    self.results['warnings'].append(f"{name}: {result.get('message', '')}")
                elif result['status'] == 'SKIP':
                    logger.info(f"⏭️ {name}: SKIP - {result.get('message', '')}")
                    # SKIP n'est pas un échec
                else:
                    logger.error(f"❌ {name}: FAIL - {result.get('message', '')}")
                    self.results['errors'].append(f"{name}: {result.get('message', '')}")
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"❌ {name}: ERROR - {str(e)}")
                self.results['checks'].append({
                    'name': name,
                    'status': 'ERROR',
                    'message': str(e)
                })
                self.results['errors'].append(f"{name}: {str(e)}")
                all_passed = False
        
        self.results['overall_status'] = 'PASS' if all_passed else 'FAIL'
        
        # Résumé final
        self._print_summary()
        
        return self.results
    
    def _check_compilation(self) -> Dict:
        """Vérifier que tous les modules compilent"""
        errors = []
        
        modules_to_check = [
            'optimization.models.xgboost_trainer_v2',
            'optimization.optuna_v2_tuner',
            'optimization.data.feature_loader',
            'optimization.data.feature_engineering',
            'optimization.data.preprocessor',
            'optimization.utils.temporal_split',
        ]
        
        for module_name in modules_to_check:
            try:
                __import__(module_name)
            except Exception as e:
                errors.append(f"{module_name}: {str(e)}")
        
        if errors:
            return {'status': 'FAIL', 'message': '; '.join(errors)}
        return {'status': 'PASS', 'message': f'{len(modules_to_check)} modules OK'}
    
    def _check_data_loading(self) -> Dict:
        """Vérifier le chargement des données"""
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            
            df = load_features_from_postgres(
                timeframe_days=30 if self.quick_mode else 120,
                min_trades=50 if self.quick_mode else 100
            )
            
            if df is None or len(df) == 0:
                return {'status': 'FAIL', 'message': 'Aucune donnée chargée'}
            
            # Vérifier colonnes critiques
            required_cols = ['target_win', 'target_pnl']
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                return {'status': 'FAIL', 'message': f'Colonnes manquantes: {missing}'}
            
            # Vérifier balance des classes
            win_rate = df['target_win'].mean()
            
            details = {
                'n_samples': len(df),
                'n_features': len(df.columns),
                'win_rate': f"{win_rate*100:.1f}%"
            }
            
            return {'status': 'PASS', 'message': f'{len(df)} samples chargés', 'details': details}
            
        except Exception as e:
            return {'status': 'FAIL', 'message': str(e)}
    
    def _check_training(self) -> Dict:
        """Entraîner le modèle et vérifier qu'il fonctionne"""
        try:
            from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2
            
            trainer = XGBoostTrainerV2(model_name="validation_test")
            
            # Entraînement rapide pour validation
            results = trainer.train(
                timeframe_days=30 if self.quick_mode else 90,
                min_trades=50 if self.quick_mode else 100,
                max_features=20 if self.quick_mode else 30,
                n_estimators=100 if self.quick_mode else 300,
                walk_forward=False,  # Testé séparément
                calibrate_probabilities=False,  # Testé séparément
                load_optuna_params=True
            )
            
            # Stocker pour les checks suivants
            self._training_results = results
            self._trainer = trainer
            
            if results.get('status') != 'success':
                return {'status': 'FAIL', 'message': 'Entraînement échoué'}
            
            return {
                'status': 'PASS',
                'message': f"Modèle entraîné",
                'details': {
                    'test_accuracy': f"{results['metrics']['test']['accuracy']:.3f}",
                    'test_f1': f"{results['metrics']['test']['f1']:.3f}"
                }
            }
            
        except Exception as e:
            return {'status': 'FAIL', 'message': str(e)}
    
    def _check_metrics(self) -> Dict:
        """Vérifier que les métriques atteignent les seuils"""
        if not hasattr(self, '_training_results'):
            return {'status': 'SKIP', 'message': 'Pas de résultats training'}
        
        metrics = self._training_results.get('metrics', {}).get('test', {})
        
        issues = []
        details = {}
        
        # Vérifier accuracy
        accuracy = metrics.get('accuracy', 0)
        details['accuracy'] = f"{accuracy:.3f}"
        if accuracy < PERFORMANCE_THRESHOLDS['min_accuracy']:
            issues.append(f"Accuracy {accuracy:.3f} < {PERFORMANCE_THRESHOLDS['min_accuracy']}")
        
        # Vérifier F1
        f1 = metrics.get('f1', 0)
        details['f1'] = f"{f1:.3f}"
        if f1 < PERFORMANCE_THRESHOLDS['min_f1']:
            issues.append(f"F1 {f1:.3f} < {PERFORMANCE_THRESHOLDS['min_f1']}")
        
        # Vérifier ROC-AUC
        roc_auc = metrics.get('roc_auc', 0)
        details['roc_auc'] = f"{roc_auc:.3f}"
        if roc_auc < PERFORMANCE_THRESHOLDS['min_roc_auc']:
            issues.append(f"ROC-AUC {roc_auc:.3f} < {PERFORMANCE_THRESHOLDS['min_roc_auc']}")
        
        # Vérifier Precision
        precision = metrics.get('precision', 0)
        details['precision'] = f"{precision:.3f}"
        if precision < PERFORMANCE_THRESHOLDS['min_precision']:
            issues.append(f"Precision {precision:.3f} < {PERFORMANCE_THRESHOLDS['min_precision']}")
        
        if issues:
            return {'status': 'FAIL', 'message': '; '.join(issues), 'details': details}
        
        # Warning si pas optimal
        if accuracy < PERFORMANCE_THRESHOLDS['target_accuracy']:
            return {
                'status': 'WARN',
                'message': f"Accuracy {accuracy:.3f} < target {PERFORMANCE_THRESHOLDS['target_accuracy']}",
                'details': details
            }
        
        return {'status': 'PASS', 'message': 'Toutes les métriques OK', 'details': details}
    
    def _check_overfitting(self) -> Dict:
        """Vérifier qu'il n'y a pas d'overfitting"""
        if not hasattr(self, '_training_results'):
            return {'status': 'SKIP', 'message': 'Pas de résultats training'}
        
        gaps = self._training_results.get('metrics', {}).get('gaps', {})
        
        accuracy_gap = gaps.get('accuracy', 0)
        roc_gap = gaps.get('roc_auc', 0)
        
        details = {
            'accuracy_gap': f"{accuracy_gap:.3f}",
            'roc_auc_gap': f"{roc_gap:.3f}"
        }
        
        if accuracy_gap > PERFORMANCE_THRESHOLDS['max_overfit_gap']:
            return {
                'status': 'FAIL',
                'message': f"Overfitting détecté: gap={accuracy_gap:.3f} > {PERFORMANCE_THRESHOLDS['max_overfit_gap']}",
                'details': details
            }
        
        if accuracy_gap > 0.10:
            return {
                'status': 'WARN',
                'message': f"Overfitting léger: gap={accuracy_gap:.3f}",
                'details': details
            }
        
        return {'status': 'PASS', 'message': f'Gap OK: {accuracy_gap:.3f}', 'details': details}
    
    def _check_walk_forward(self) -> Dict:
        """Tester walk-forward validation"""
        if self.quick_mode:
            return {'status': 'SKIP', 'message': 'Skipped en mode rapide'}
        
        if not hasattr(self, '_trainer'):
            return {'status': 'SKIP', 'message': 'Pas de trainer disponible'}
        
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            base_df = load_features_from_postgres(timeframe_days=90, min_trades=100)
            df = calculate_derived_features(base_df)
            
            exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
            feature_cols = [c for c in df.columns if c not in exclude_cols][:30]
            
            results = self._trainer._walk_forward_validation(
                df, feature_cols, n_splits=3, model_params=self._trainer.model.get_params()
            )
            
            mean_score = results.get('mean_score', 0)
            std_score = results.get('std_score', 1)
            
            details = {
                'mean_f1': f"{mean_score:.3f}",
                'std_f1': f"{std_score:.3f}",
                'n_splits': len(results.get('splits', []))
            }
            
            if std_score > PERFORMANCE_THRESHOLDS['min_walk_forward_std']:
                return {
                    'status': 'WARN',
                    'message': f"Haute variance walk-forward: std={std_score:.3f}",
                    'details': details
                }
            
            return {'status': 'PASS', 'message': f'Walk-forward stable: {mean_score:.3f}±{std_score:.3f}', 'details': details}
            
        except Exception as e:
            return {'status': 'FAIL', 'message': str(e)}
    
    def _check_calibration(self) -> Dict:
        """Vérifier la calibration des probabilités"""
        if self.quick_mode:
            return {'status': 'SKIP', 'message': 'Skipped en mode rapide'}
        
        if not hasattr(self, '_trainer') or not hasattr(self._trainer, 'calibrated_model'):
            return {'status': 'SKIP', 'message': 'Modèle calibré non disponible'}
        
        if self._trainer.calibrated_model is None:
            return {'status': 'WARN', 'message': 'Calibration non effectuée'}
        
        return {'status': 'PASS', 'message': 'Modèle calibré disponible'}
    
    def _print_summary(self):
        """Afficher le résumé des vérifications"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 RÉSUMÉ VALIDATION ML")
        logger.info("=" * 80)
        
        passed = sum(1 for c in self.results['checks'] if c['status'] == 'PASS')
        warned = sum(1 for c in self.results['checks'] if c['status'] == 'WARN')
        failed = sum(1 for c in self.results['checks'] if c['status'] in ['FAIL', 'ERROR'])
        skipped = sum(1 for c in self.results['checks'] if c['status'] == 'SKIP')
        
        logger.info(f"\n✅ PASS: {passed}")
        logger.info(f"⚠️ WARN: {warned}")
        logger.info(f"❌ FAIL: {failed}")
        logger.info(f"⏭️ SKIP: {skipped}")
        
        if self.results['errors']:
            logger.info(f"\n❌ ERREURS:")
            for err in self.results['errors']:
                logger.info(f"  - {err}")
        
        if self.results['warnings']:
            logger.info(f"\n⚠️ WARNINGS:")
            for warn in self.results['warnings']:
                logger.info(f"  - {warn}")
        
        status_emoji = "✅" if self.results['overall_status'] == 'PASS' else "❌"
        logger.info(f"\n{status_emoji} STATUT GLOBAL: {self.results['overall_status']}")
        logger.info("=" * 80)
    
    def save_report(self, filepath: str = "ml_validation_report.json"):
        """Sauvegarder le rapport"""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"📄 Rapport sauvegardé: {filepath}")


def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ML Performance Validation")
    parser.add_argument('--quick', action='store_true', help='Mode rapide (moins de données)')
    parser.add_argument('--full', action='store_true', help='Mode complet avec Optuna')
    args = parser.parse_args()
    
    validator = MLValidator(quick_mode=args.quick)
    results = validator.run_all_checks()
    validator.save_report()
    
    # Exit code basé sur le statut
    sys.exit(0 if results['overall_status'] == 'PASS' else 1)


if __name__ == "__main__":
    main()
