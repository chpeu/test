#!/usr/bin/env python3
"""
🔥 Validation et Amélioration du Modèle de Régression V2 (Prédiction PNL%)

Ce script analyse pourquoi le R² est négatif et propose des solutions.

Problèmes potentiels analysés:
1. Distribution de target_pnl (skewed, outliers)
2. Features pas informatives
3. Overfitting (train R² >> test R²)
4. Dataset trop petit
5. Hyperparamètres inadaptés

Usage:
    python validate_regression_v2.py
"""
import logging
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Seuils de performance pour régression
REGRESSION_THRESHOLDS = {
    'min_r2': 0.05,             # R² minimum (> 0 = mieux que moyenne)
    'target_r2': 0.20,          # R² cible réaliste pour trading
    'max_mae': 0.50,            # MAE max acceptable (%)
    'target_mae': 0.35,         # MAE cible
    'max_overfit_gap': 0.30,    # Gap R² train-test max
    'min_samples': 500,         # Nombre minimum de samples
    'min_features_mi': 0.01,    # Mutual info minimum pour features utiles
}


class RegressionV2Validator:
    """Validateur pour le modèle de régression V2"""
    
    def __init__(self):
        self.results: Dict = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'recommendations': [],
            'overall_status': 'pending'
        }
        self.df = None
    
    def run_all_checks(self) -> Dict:
        """Exécuter toutes les vérifications"""
        logger.info("=" * 70)
        logger.info("🔬 VALIDATION MODÈLE RÉGRESSION V2 (Prédiction PNL%)")
        logger.info("=" * 70)
        
        checks = [
            ("Chargement données", self._check_data_loading),
            ("Distribution target_pnl", self._check_target_distribution),
            ("Qualité features", self._check_feature_quality),
            ("Test entraînement baseline", self._test_baseline_model),
            ("Test avec régularisation forte", self._test_regularized_model),
            ("Détection overfitting", self._check_overfitting),
            ("Recommandations", self._generate_recommendations),
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
                logger.info(f"{status_emoji} {name}: {result['status']} - {result.get('message', '')}")
                
                if result['status'] == 'FAIL':
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"❌ {name}: ERROR - {str(e)}")
                self.results['checks'].append({
                    'name': name,
                    'status': 'ERROR',
                    'message': str(e)
                })
                all_passed = False
        
        self.results['overall_status'] = 'PASS' if all_passed else 'NEEDS_IMPROVEMENT'
        self._print_summary()
        
        return self.results
    
    def _check_data_loading(self) -> Dict:
        """Charger et vérifier les données"""
        try:
            from optimization.data.feature_loader import load_features_from_postgres
            from optimization.data.feature_engineering import calculate_derived_features
            
            base_df = load_features_from_postgres(
                timeframe_days=120,
                min_trades=50
            )
            
            self.df = calculate_derived_features(base_df)
            
            n_samples = len(self.df)
            
            if 'target_pnl' not in self.df.columns:
                return {'status': 'FAIL', 'message': 'Colonne target_pnl manquante'}
            
            n_pnl_valid = self.df['target_pnl'].notna().sum()
            
            details = {
                'n_samples': n_samples,
                'n_pnl_valid': n_pnl_valid,
                'n_features': len(self.df.columns)
            }
            
            if n_samples < REGRESSION_THRESHOLDS['min_samples']:
                return {
                    'status': 'WARN',
                    'message': f'{n_samples} samples < {REGRESSION_THRESHOLDS["min_samples"]} recommandés',
                    'details': details
                }
            
            return {'status': 'PASS', 'message': f'{n_samples} samples chargés', 'details': details}
            
        except Exception as e:
            return {'status': 'FAIL', 'message': str(e)}
    
    def _check_target_distribution(self) -> Dict:
        """Analyser la distribution de target_pnl"""
        if self.df is None:
            return {'status': 'SKIP', 'message': 'Données non chargées'}
        
        target = self.df['target_pnl'].dropna()
        
        # Statistiques
        mean_pnl = target.mean()
        std_pnl = target.std()
        median_pnl = target.median()
        skewness = target.skew()
        kurtosis = target.kurtosis()
        
        # Outliers (> 3 std)
        outlier_threshold = 3 * std_pnl
        n_outliers = ((target - mean_pnl).abs() > outlier_threshold).sum()
        outlier_pct = n_outliers / len(target) * 100
        
        # Concentration autour de 0
        near_zero = (target.abs() < 0.1).sum() / len(target) * 100
        
        details = {
            'mean': f'{mean_pnl:.4f}%',
            'std': f'{std_pnl:.4f}%',
            'median': f'{median_pnl:.4f}%',
            'skewness': f'{skewness:.2f}',
            'kurtosis': f'{kurtosis:.2f}',
            'outliers_pct': f'{outlier_pct:.1f}%',
            'near_zero_pct': f'{near_zero:.1f}%',
            'min': f'{target.min():.4f}%',
            'max': f'{target.max():.4f}%'
        }
        
        logger.info(f"  📊 Distribution: mean={mean_pnl:.4f}%, std={std_pnl:.4f}%, skew={skewness:.2f}")
        logger.info(f"  📊 Range: [{target.min():.4f}%, {target.max():.4f}%]")
        logger.info(f"  📊 Outliers (>3σ): {outlier_pct:.1f}%, Near zero (<0.1%): {near_zero:.1f}%")
        
        issues = []
        
        # Vérifier problèmes
        if abs(skewness) > 2:
            issues.append(f"Distribution très skewed ({skewness:.2f})")
            self.results['recommendations'].append("🔧 Appliquer transformation log ou winsorization sur target_pnl")
        
        if outlier_pct > 10:
            issues.append(f"Trop d'outliers ({outlier_pct:.1f}%)")
            self.results['recommendations'].append("🔧 Filtrer ou winsorizer les outliers (>3σ)")
        
        if near_zero > 50:
            issues.append(f"Trop de valeurs proches de 0 ({near_zero:.1f}%)")
            self.results['recommendations'].append("🔧 Filtrer les trades marginaux (|PNL| < 0.1%)")
        
        if std_pnl < 0.1:
            issues.append("Variance très faible")
            self.results['recommendations'].append("🔧 La cible a peu de variance - difficile à prédire")
        
        if issues:
            return {'status': 'WARN', 'message': '; '.join(issues), 'details': details}
        
        return {'status': 'PASS', 'message': 'Distribution acceptable', 'details': details}
    
    def _check_feature_quality(self) -> Dict:
        """Vérifier la qualité des features avec mutual information"""
        if self.df is None:
            return {'status': 'SKIP', 'message': 'Données non chargées'}
        
        from sklearn.feature_selection import mutual_info_regression
        
        # Colonnes à exclure
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [c for c in self.df.columns if c not in exclude_cols]
        
        X = self.df[feature_cols].fillna(0)
        y = self.df['target_pnl'].fillna(0)
        
        # Calculer mutual information
        mi_scores = mutual_info_regression(X, y, random_state=42)
        
        mi_df = pd.DataFrame({
            'feature': feature_cols,
            'mi_score': mi_scores
        }).sort_values('mi_score', ascending=False)
        
        # Analyser
        n_useful = (mi_df['mi_score'] > REGRESSION_THRESHOLDS['min_features_mi']).sum()
        top_features = mi_df.head(10)
        
        logger.info(f"  📊 Features utiles (MI > {REGRESSION_THRESHOLDS['min_features_mi']}): {n_useful}/{len(feature_cols)}")
        logger.info(f"  📊 Top 5 features:")
        for _, row in top_features.head(5).iterrows():
            logger.info(f"      - {row['feature']}: {row['mi_score']:.4f}")
        
        details = {
            'total_features': len(feature_cols),
            'useful_features': n_useful,
            'top_mi_score': f"{mi_df['mi_score'].max():.4f}",
            'mean_mi_score': f"{mi_df['mi_score'].mean():.4f}",
            'top_5_features': top_features.head(5).to_dict('records')
        }
        
        if n_useful < 10:
            self.results['recommendations'].append("🔧 Peu de features informatives - ajouter features de volatilité, momentum")
            return {'status': 'WARN', 'message': f'Seulement {n_useful} features utiles', 'details': details}
        
        if mi_df['mi_score'].max() < 0.05:
            self.results['recommendations'].append("🔧 Aucune feature fortement corrélée au PNL - revoir feature engineering")
            return {'status': 'WARN', 'message': 'Features faiblement corrélées au target', 'details': details}
        
        return {'status': 'PASS', 'message': f'{n_useful} features utiles', 'details': details}
    
    def _test_baseline_model(self) -> Dict:
        """Tester un modèle baseline simple"""
        if self.df is None:
            return {'status': 'SKIP', 'message': 'Données non chargées'}
        
        from sklearn.model_selection import train_test_split
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import RobustScaler
        from sklearn.metrics import r2_score, mean_absolute_error
        
        # Préparer données
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [c for c in self.df.columns if c not in exclude_cols]
        
        X = self.df[feature_cols].fillna(0)
        y = self.df['target_pnl'].fillna(0)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scaler
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Modèle Ridge simple (très régularisé)
        model = Ridge(alpha=10.0)
        model.fit(X_train_scaled, y_train)
        
        # Évaluer
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        train_r2 = r2_score(y_train, y_train_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        train_mae = mean_absolute_error(y_train, y_train_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        
        logger.info(f"  📊 Ridge Baseline: Train R²={train_r2:.4f}, Test R²={test_r2:.4f}")
        logger.info(f"  📊 Ridge Baseline: Train MAE={train_mae:.4f}%, Test MAE={test_mae:.4f}%")
        
        details = {
            'train_r2': f'{train_r2:.4f}',
            'test_r2': f'{test_r2:.4f}',
            'train_mae': f'{train_mae:.4f}%',
            'test_mae': f'{test_mae:.4f}%',
            'model': 'Ridge(alpha=10)'
        }
        
        if test_r2 < 0:
            self.results['recommendations'].append("🔧 Même Ridge baseline a R² < 0 - problème avec les données")
            return {'status': 'FAIL', 'message': f'R² test négatif ({test_r2:.4f})', 'details': details}
        
        if test_r2 < REGRESSION_THRESHOLDS['min_r2']:
            return {'status': 'WARN', 'message': f'R² faible ({test_r2:.4f})', 'details': details}
        
        return {'status': 'PASS', 'message': f'R² test: {test_r2:.4f}', 'details': details}
    
    def _test_regularized_model(self) -> Dict:
        """Tester XGBoost avec forte régularisation + winsorization"""
        if self.df is None:
            return {'status': 'SKIP', 'message': 'Données non chargées'}
        
        from xgboost import XGBRegressor
        from sklearn.preprocessing import RobustScaler
        from sklearn.metrics import r2_score, mean_absolute_error
        from optimization.utils.temporal_split import temporal_train_test_split
        
        # 🔥 V2.1: Filtrer trades marginaux ET appliquer winsorization
        df_filtered = self.df[self.df['target_pnl'].abs() > 0.1].copy()  # Exclure trades marginaux
        
        # Winsorization: clipper les percentiles 1% et 99%
        lower_bound = df_filtered['target_pnl'].quantile(0.01)
        upper_bound = df_filtered['target_pnl'].quantile(0.99)
        df_filtered['target_pnl'] = df_filtered['target_pnl'].clip(lower=lower_bound, upper=upper_bound)
        
        logger.info(f"  📊 Winsorization appliquée: [{lower_bound:.2f}%, {upper_bound:.2f}%]")
        
        logger.info(f"  📊 Après filtrage: {len(df_filtered)} samples (vs {len(self.df)} original)")
        
        if len(df_filtered) < 100:
            return {'status': 'FAIL', 'message': f'Pas assez de données après filtrage ({len(df_filtered)})'}
        
        # Préparer données
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [c for c in df_filtered.columns if c not in exclude_cols]
        
        # Split temporel
        train_df, val_df, test_df = temporal_train_test_split(
            df_filtered,
            target_col='target_pnl',
            test_size=0.2,
            validation_size=0.1,
            timestamp_col='timestamp'
        )
        
        X_train = train_df[feature_cols].fillna(0)
        y_train = train_df['target_pnl']
        X_val = val_df[feature_cols].fillna(0)
        y_val = val_df['target_pnl']
        X_test = test_df[feature_cols].fillna(0)
        y_test = test_df['target_pnl']
        
        # Scaler
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)
        
        # XGBoost avec FORTE régularisation
        model = XGBRegressor(
            n_estimators=200,
            max_depth=3,          # Très peu profond
            learning_rate=0.01,   # Très lent
            min_child_weight=20,  # Nœuds avec beaucoup de samples
            reg_alpha=10.0,       # Forte régularisation L1
            reg_lambda=10.0,      # Forte régularisation L2
            subsample=0.6,        # Sous-échantillonnage
            colsample_bytree=0.6,
            gamma=2.0,            # Pénalité de complexité
            random_state=42,
            objective='reg:squarederror'
        )
        
        model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_val_scaled, y_val)],
            verbose=False
        )
        
        # Évaluer
        y_train_pred = model.predict(X_train_scaled)
        y_val_pred = model.predict(X_val_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        train_r2 = r2_score(y_train, y_train_pred)
        val_r2 = r2_score(y_val, y_val_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        
        train_mae = mean_absolute_error(y_train, y_train_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        
        gap = train_r2 - test_r2
        
        logger.info(f"  📊 XGBoost Régularisé: Train R²={train_r2:.4f}, Val R²={val_r2:.4f}, Test R²={test_r2:.4f}")
        logger.info(f"  📊 Gap Train-Test: {gap:.4f}")
        logger.info(f"  📊 MAE: Train={train_mae:.4f}%, Test={test_mae:.4f}%")
        
        details = {
            'train_r2': f'{train_r2:.4f}',
            'val_r2': f'{val_r2:.4f}',
            'test_r2': f'{test_r2:.4f}',
            'gap': f'{gap:.4f}',
            'train_mae': f'{train_mae:.4f}%',
            'test_mae': f'{test_mae:.4f}%',
            'n_samples_filtered': len(df_filtered)
        }
        
        # Stocker pour comparaison
        self._regularized_results = details
        
        if test_r2 < 0:
            self.results['recommendations'].append("🔧 Même avec forte régularisation, R² < 0 - le PNL% est très difficile à prédire")
            self.results['recommendations'].append("🔧 Considérer: (1) plus de données, (2) features différentes, (3) transformer la cible")
            return {'status': 'FAIL', 'message': f'R² test toujours négatif ({test_r2:.4f})', 'details': details}
        
        if test_r2 < REGRESSION_THRESHOLDS['min_r2']:
            return {'status': 'WARN', 'message': f'R² faible mais > 0 ({test_r2:.4f})', 'details': details}
        
        return {'status': 'PASS', 'message': f'R² test: {test_r2:.4f}', 'details': details}
    
    def _check_overfitting(self) -> Dict:
        """Vérifier le niveau d'overfitting"""
        if not hasattr(self, '_regularized_results'):
            return {'status': 'SKIP', 'message': 'Test régularisé non exécuté'}
        
        train_r2 = float(self._regularized_results['train_r2'])
        test_r2 = float(self._regularized_results['test_r2'])
        gap = train_r2 - test_r2
        
        details = {
            'train_r2': f'{train_r2:.4f}',
            'test_r2': f'{test_r2:.4f}',
            'gap': f'{gap:.4f}'
        }
        
        if gap > REGRESSION_THRESHOLDS['max_overfit_gap']:
            self.results['recommendations'].append(f"🔧 Overfitting sévère (gap={gap:.3f}) - augmenter régularisation")
            return {'status': 'FAIL', 'message': f'Overfitting: gap={gap:.4f}', 'details': details}
        
        if gap > 0.15:
            return {'status': 'WARN', 'message': f'Overfitting modéré: gap={gap:.4f}', 'details': details}
        
        return {'status': 'PASS', 'message': f'Gap OK: {gap:.4f}', 'details': details}
    
    def _generate_recommendations(self) -> Dict:
        """Générer les recommandations finales"""
        # Recommandations générales si R² < 0
        if not self.results['recommendations']:
            self.results['recommendations'].append("✅ Le modèle semble fonctionner correctement")
        
        # Ajouter recommandations selon les résultats
        checks_failed = [c for c in self.results['checks'] if c['status'] == 'FAIL']
        
        if len(checks_failed) >= 3:
            self.results['recommendations'].append("⚠️ PROBLÈME FONDAMENTAL: Le PNL% est peut-être imprévisible avec les features actuelles")
            self.results['recommendations'].append("💡 Alternative: Utiliser le modèle de CLASSIFICATION (V1) qui prédit WIN/LOSS")
        
        return {'status': 'INFO', 'message': f'{len(self.results["recommendations"])} recommandations'}
    
    def _print_summary(self):
        """Afficher le résumé"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 RÉSUMÉ VALIDATION RÉGRESSION V2")
        logger.info("=" * 70)
        
        passed = sum(1 for c in self.results['checks'] if c['status'] == 'PASS')
        warned = sum(1 for c in self.results['checks'] if c['status'] == 'WARN')
        failed = sum(1 for c in self.results['checks'] if c['status'] in ['FAIL', 'ERROR'])
        
        logger.info(f"\n✅ PASS: {passed}")
        logger.info(f"⚠️ WARN: {warned}")
        logger.info(f"❌ FAIL: {failed}")
        
        logger.info(f"\n📋 RECOMMANDATIONS:")
        for i, rec in enumerate(self.results['recommendations'], 1):
            logger.info(f"  {i}. {rec}")
        
        logger.info("\n" + "=" * 70)
        status_emoji = "✅" if self.results['overall_status'] == 'PASS' else "⚠️"
        logger.info(f"{status_emoji} STATUT: {self.results['overall_status']}")
        logger.info("=" * 70)
    
    def save_report(self, filepath: str = "regression_v2_validation_report.json"):
        """Sauvegarder le rapport"""
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        logger.info(f"📄 Rapport sauvegardé: {filepath}")


def main():
    """Point d'entrée"""
    validator = RegressionV2Validator()
    results = validator.run_all_checks()
    validator.save_report()
    
    # Code de sortie basé sur le nombre d'échecs
    n_fails = sum(1 for c in results['checks'] if c['status'] in ['FAIL', 'ERROR'])
    sys.exit(0 if n_fails == 0 else 1)


if __name__ == "__main__":
    main()
