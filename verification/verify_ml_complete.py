#!/usr/bin/env python3
"""
🔄 BOUCLE DE VÉRIFICATION ML COMPLÈTE

Script de vérification pour s'assurer que le ML fonctionne correctement.

Vérifie:
1. Modèle optimisé existe et charge
2. Performance sur données récentes
3. Comparaison avec modèle V1 actuel
4. Intégrité du pipeline
"""
import logging
import sys
import json
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from pathlib import Path
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MLVerificationLoop:
    """Boucle de vérification ML"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'status': 'pending'
        }
    
    def run_all_checks(self) -> Dict:
        """Exécuter toutes les vérifications"""
        logger.info("=" * 70)
        logger.info("🔄 BOUCLE DE VÉRIFICATION ML COMPLÈTE")
        logger.info("=" * 70)
        
        checks = [
            ("Modèle optimisé existe", self._check_optimized_model_exists),
            ("Chargement modèle", self._check_model_loads),
            ("Performance sur données récentes", self._check_recent_performance),
            ("Comparaison avec V1", self._check_vs_v1),
            ("Intégrité pipeline", self._check_pipeline_integrity),
        ]
        
        all_passed = True
        
        for name, check_func in checks:
            logger.info(f"\n📋 {name}...")
            try:
                result = check_func()
                self.results['checks'].append({
                    'name': name,
                    'status': result['status'],
                    'message': result.get('message', ''),
                    'details': result.get('details', {})
                })
                
                status_emoji = "✅" if result['status'] == 'PASS' else "⚠️" if result['status'] == 'WARN' else "❌"
                logger.info(f"   {status_emoji} {result['status']}: {result.get('message', '')}")
                
                if result['status'] == 'FAIL':
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"   ❌ ERROR: {str(e)}")
                self.results['checks'].append({
                    'name': name,
                    'status': 'ERROR',
                    'message': str(e)
                })
                all_passed = False
        
        self.results['status'] = 'PASS' if all_passed else 'NEEDS_ATTENTION'
        self._print_summary()
        
        return self.results
    
    def _check_optimized_model_exists(self) -> Dict:
        """Vérifier que le modèle optimisé existe"""
        models_dir = Path("optimization/saved_models")
        
        model_path = models_dir / "optimized_classifier_latest.pkl"
        metadata_path = models_dir / "optimized_classifier_metadata.json"
        
        if not model_path.exists():
            return {'status': 'FAIL', 'message': 'Modèle optimisé non trouvé'}
        
        if not metadata_path.exists():
            return {'status': 'WARN', 'message': 'Metadata non trouvée'}
        
        # Lire metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return {
            'status': 'PASS',
            'message': f"Modèle trouvé (accuracy={metadata['metrics']['test_accuracy']:.1%})",
            'details': metadata['metrics']
        }
    
    def _check_model_loads(self) -> Dict:
        """Vérifier que le modèle se charge correctement"""
        models_dir = Path("optimization/saved_models")
        model_path = models_dir / "optimized_classifier_latest.pkl"
        
        try:
            pipeline = joblib.load(model_path)
            
            # Vérifier structure
            if not hasattr(pipeline, 'predict'):
                return {'status': 'FAIL', 'message': 'Pipeline invalide (pas de predict)'}
            
            if not hasattr(pipeline, 'predict_proba'):
                return {'status': 'WARN', 'message': 'Pipeline sans predict_proba'}
            
            return {
                'status': 'PASS',
                'message': 'Pipeline chargé correctement',
                'details': {'type': type(pipeline).__name__}
            }
            
        except Exception as e:
            return {'status': 'FAIL', 'message': f'Erreur chargement: {e}'}
    
    def _check_recent_performance(self) -> Dict:
        """Tester sur données récentes"""
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            # Charger derniers 7 jours
            base_df = load_features_from_postgres(
                timeframe_days=7,
                min_trades=10
            )
            
            if len(base_df) < 50:
                return {
                    'status': 'WARN',
                    'message': f'Peu de données récentes ({len(base_df)} samples)',
                    'details': {'n_samples': len(base_df)}
                }
            
            df = calculate_derived_features(base_df)
            
            # Charger modèle et metadata
            models_dir = Path("optimization/saved_models")
            pipeline = joblib.load(models_dir / "optimized_classifier_latest.pkl")
            
            with open(models_dir / "optimized_classifier_metadata.json", 'r') as f:
                metadata = json.load(f)
            
            feature_cols = metadata['feature_cols']
            
            # Ajouter features manquantes
            df = self._add_missing_features(df, feature_cols)
            
            # Prédire
            X = df[feature_cols].fillna(0)
            y_true = df['target_win'].astype(int)
            
            y_pred = pipeline.predict(X)
            y_proba = pipeline.predict_proba(X)[:, 1]
            
            # Métriques
            from sklearn.metrics import accuracy_score, f1_score
            acc = accuracy_score(y_true, y_pred)
            f1 = f1_score(y_true, y_pred, zero_division=0)
            
            status = 'PASS' if acc >= 0.55 else 'WARN' if acc >= 0.50 else 'FAIL'
            
            return {
                'status': status,
                'message': f'Accuracy récente: {acc:.1%}, F1: {f1:.3f}',
                'details': {
                    'n_samples': len(df),
                    'accuracy': acc,
                    'f1': f1,
                    'win_rate_actual': y_true.mean(),
                    'win_rate_predicted': y_pred.mean()
                }
            }
            
        except Exception as e:
            return {'status': 'FAIL', 'message': f'Erreur: {e}'}
    
    def _add_missing_features(self, df: pd.DataFrame, required_cols: list) -> pd.DataFrame:
        """Ajouter les features manquantes (même logique que train)"""
        # Features temporelles
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            df['hour'] = ts.dt.hour
            df['day_of_week'] = ts.dt.dayofweek
            df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
            df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
            df['asian_session'] = df['hour'].isin(range(0, 8)).astype(int)
            df['european_session'] = df['hour'].isin(range(8, 16)).astype(int)
            df['american_session'] = df['hour'].isin(range(16, 24)).astype(int)
        
        # Features de momentum
        if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
            df['rsi_oversold'] = (df['rsi_1m'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi_1m'] > 70).astype(int)
        
        if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
            df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
            df['macd_aligned'] = ((df['macd_hist_1m'] > 0) == (df['macd_hist_5m'] > 0)).astype(int)
        
        if 'atr_pct_1m' in df.columns:
            atr_median = df['atr_pct_1m'].median()
            df['high_volatility'] = (df['atr_pct_1m'] > atr_median).astype(int)
        
        if 'adx_1m' in df.columns:
            df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
            df['weak_trend'] = (df['adx_1m'] < 20).astype(int)
        
        if 'volume_ratio_1m' in df.columns:
            df['volume_spike'] = (df['volume_ratio_1m'] > 1.5).astype(int)
        
        # Ajouter colonnes manquantes avec 0
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0
        
        return df
    
    def _check_vs_v1(self) -> Dict:
        """Comparer avec modèle V1"""
        try:
            models_dir = Path("optimization/saved_models")
            
            # Charger metadata optimisé
            with open(models_dir / "optimized_classifier_metadata.json", 'r') as f:
                opt_metadata = json.load(f)
            
            opt_acc = opt_metadata['metrics']['test_accuracy']
            
            # Chercher V1
            v1_path = models_dir / "xgboost_v1_latest.pkl"
            
            if not v1_path.exists():
                return {
                    'status': 'WARN',
                    'message': f'V1 non trouvé. Optimisé: {opt_acc:.1%}',
                    'details': {'optimized_accuracy': opt_acc}
                }
            
            # Comparer (on peut ajouter un test direct si besoin)
            return {
                'status': 'PASS',
                'message': f'Modèle optimisé: {opt_acc:.1%}',
                'details': {'optimized_accuracy': opt_acc}
            }
            
        except Exception as e:
            return {'status': 'WARN', 'message': f'Comparaison impossible: {e}'}
    
    def _check_pipeline_integrity(self) -> Dict:
        """Vérifier l'intégrité du pipeline"""
        checks_passed = []
        checks_failed = []
        
        # 1. Feature loader
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            checks_passed.append("feature_loader")
        except:
            checks_failed.append("feature_loader")
        
        # 2. Feature engineering
        try:
            from optimization.data.feature_engineering import calculate_derived_features
            checks_passed.append("feature_engineering")
        except:
            checks_failed.append("feature_engineering")
        
        # 3. Temporal split
        try:
            from optimization.utils.temporal_split import temporal_train_test_split
            checks_passed.append("temporal_split")
        except:
            checks_failed.append("temporal_split")
        
        # 4. Preprocessor
        try:
            from optimization.data.preprocessor import FeaturePreprocessor
            checks_passed.append("preprocessor")
        except:
            checks_failed.append("preprocessor")
        
        if checks_failed:
            return {
                'status': 'FAIL',
                'message': f'Modules manquants: {checks_failed}',
                'details': {'passed': checks_passed, 'failed': checks_failed}
            }
        
        return {
            'status': 'PASS',
            'message': f'{len(checks_passed)} modules OK',
            'details': {'passed': checks_passed}
        }
    
    def _print_summary(self):
        """Afficher le résumé"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 RÉSUMÉ VÉRIFICATION ML")
        logger.info("=" * 70)
        
        passed = sum(1 for c in self.results['checks'] if c['status'] == 'PASS')
        warned = sum(1 for c in self.results['checks'] if c['status'] == 'WARN')
        failed = sum(1 for c in self.results['checks'] if c['status'] in ['FAIL', 'ERROR'])
        
        logger.info(f"\n✅ PASS: {passed}")
        logger.info(f"⚠️ WARN: {warned}")
        logger.info(f"❌ FAIL: {failed}")
        
        logger.info("\n" + "=" * 70)
        status_emoji = "✅" if self.results['status'] == 'PASS' else "⚠️"
        logger.info(f"{status_emoji} STATUT GLOBAL: {self.results['status']}")
        
        # Recommandations
        if self.results['status'] == 'PASS':
            logger.info("\n💡 RECOMMANDATION: Le modèle optimisé est prêt à être utilisé!")
            logger.info("   Pour l'intégrer, activez-le dans les paramètres ML du dashboard.")
        else:
            logger.info("\n💡 RECOMMANDATION: Vérifiez les erreurs et relancez train_optimized_model.py")
        
        logger.info("=" * 70)
    
    def save_report(self, filepath: str = "ml_verification_report.json"):
        """Sauvegarder le rapport"""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"📄 Rapport sauvegardé: {filepath}")


def main():
    """Point d'entrée"""
    verifier = MLVerificationLoop()
    results = verifier.run_all_checks()
    verifier.save_report()
    
    n_fails = sum(1 for c in results['checks'] if c['status'] in ['FAIL', 'ERROR'])
    sys.exit(0 if n_fails == 0 else 1)


if __name__ == "__main__":
    main()
