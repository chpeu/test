"""
Monitoring et Drift Detection pour XGBoost V2 (Régression PNL%)
Surveille la performance du modèle en production et détecte la dégradation
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformanceMetrics:
    """Métriques de performance du modèle"""
    r2_score: float
    mae: float
    mse: float
    predictions_count: int
    profitable_pct: float
    avg_error: float
    timestamp: datetime
    period_start: datetime
    period_end: datetime


@dataclass
class DriftAlert:
    """Alerte de drift détectée"""
    metric_name: str
    current_value: float
    baseline_value: float
    drift_magnitude: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    detected_at: datetime
    message: str


class ModelDriftDetector:
    """Détecteur de drift pour modèle V2"""
    
    def __init__(self):
        self.baseline_metrics: Optional[ModelPerformanceMetrics] = None
        self.alerts_history: List[DriftAlert] = []
        
        # Seuils de drift (en déviation absolue)
        self.thresholds = {
            'r2': {
                'low': 0.03,      # -3% R²
                'medium': 0.05,   # -5% R²
                'high': 0.10,     # -10% R²
                'critical': 0.15  # -15% R²
            },
            'mae': {
                'low': 0.10,      # +10% MAE
                'medium': 0.20,   # +20% MAE
                'high': 0.30,     # +30% MAE
                'critical': 0.50  # +50% MAE
            },
            'profitable_pct': {
                'low': 5.0,       # -5%
                'medium': 10.0,   # -10%
                'high': 15.0,     # -15%
                'critical': 20.0  # -20%
            }
        }
    
    def load_baseline_from_postgres(self) -> bool:
        """
        Charger baseline depuis le modèle actif dans PostgreSQL
        
        Returns:
            True si succès, False sinon
        """
        try:
            from core.simple_pg_logger import SimplePGLogger
            
            pg = SimplePGLogger()
            if not pg.enabled:
                logger.warning("PostgreSQL non disponible")
                return False
            
            cursor = pg.conn.cursor()
            cursor.execute("""
                SELECT 
                    test_r2,
                    test_mae,
                    test_mse,
                    total_samples,
                    trained_at
                FROM ml_models
                WHERE model_name LIKE 'xgboost_v2%'
                  AND is_active = TRUE
                ORDER BY trained_at DESC
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                logger.warning("Aucun modèle V2 actif trouvé")
                return False
            
            self.baseline_metrics = ModelPerformanceMetrics(
                r2_score=row[0] or 0.0,
                mae=row[1] or 0.5,
                mse=row[2] or 0.3,
                predictions_count=row[3] or 0,
                profitable_pct=50.0,  # Approximation
                avg_error=row[1] or 0.5,
                timestamp=row[4] or datetime.now(),
                period_start=row[4] or datetime.now(),
                period_end=row[4] or datetime.now()
            )
            
            logger.info(f"✅ Baseline chargée: R²={self.baseline_metrics.r2_score:.3f}, MAE={self.baseline_metrics.mae:.3f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur chargement baseline: {e}")
            return False
    
    def set_baseline(self, metrics: ModelPerformanceMetrics):
        """Définir manuellement la baseline"""
        self.baseline_metrics = metrics
        logger.info(f"✅ Baseline définie: R²={metrics.r2_score:.3f}, MAE={metrics.mae:.3f}")
    
    def calculate_current_performance(
        self,
        predictions: pd.DataFrame,
        actuals: pd.DataFrame
    ) -> ModelPerformanceMetrics:
        """
        Calculer performance actuelle sur nouvelles prédictions
        
        Args:
            predictions: DataFrame avec predicted_pnl
            actuals: DataFrame avec actual_pnl (PNL réel)
            
        Returns:
            Métriques actuelles
        """
        try:
            from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
            
            # Assurer même taille
            if len(predictions) != len(actuals):
                logger.warning(f"Tailles différentes: {len(predictions)} vs {len(actuals)}")
                min_len = min(len(predictions), len(actuals))
                predictions = predictions.iloc[:min_len]
                actuals = actuals.iloc[:min_len]
            
            # Extraire valeurs
            y_pred = predictions['predicted_pnl'].values
            y_true = actuals['actual_pnl'].values
            
            # Calculer métriques
            r2 = r2_score(y_true, y_pred)
            mae = mean_absolute_error(y_true, y_pred)
            mse = mean_squared_error(y_true, y_pred)
            
            # Stats additionnelles
            profitable_count = sum(1 for p in y_pred if p > 0)
            profitable_pct = (profitable_count / len(y_pred)) * 100 if len(y_pred) > 0 else 0
            avg_error = mae
            
            metrics = ModelPerformanceMetrics(
                r2_score=r2,
                mae=mae,
                mse=mse,
                predictions_count=len(predictions),
                profitable_pct=profitable_pct,
                avg_error=avg_error,
                timestamp=datetime.now(),
                period_start=predictions.iloc[0]['timestamp'] if 'timestamp' in predictions.columns else datetime.now(),
                period_end=predictions.iloc[-1]['timestamp'] if 'timestamp' in predictions.columns else datetime.now()
            )
            
            logger.info(f"📊 Performance actuelle: R²={r2:.3f}, MAE={mae:.3f}, Samples={len(predictions)}")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul performance: {e}")
            raise
    
    def detect_drift(
        self,
        current_metrics: ModelPerformanceMetrics
    ) -> List[DriftAlert]:
        """
        Détecter drift entre baseline et métriques actuelles
        
        Args:
            current_metrics: Métriques actuelles
            
        Returns:
            Liste des alertes de drift
        """
        if not self.baseline_metrics:
            logger.warning("⚠️ Baseline non définie, chargement depuis PostgreSQL...")
            if not self.load_baseline_from_postgres():
                return []
        
        alerts = []
        
        # 1. Drift R² (baisse = problème)
        r2_drift = self.baseline_metrics.r2_score - current_metrics.r2_score
        if r2_drift > 0:  # R² a baissé
            severity = self._get_severity('r2', r2_drift)
            if severity:
                alert = DriftAlert(
                    metric_name='R² Score',
                    current_value=current_metrics.r2_score,
                    baseline_value=self.baseline_metrics.r2_score,
                    drift_magnitude=r2_drift,
                    severity=severity,
                    detected_at=datetime.now(),
                    message=f"R² a baissé de {r2_drift:.3f} ({self.baseline_metrics.r2_score:.3f} → {current_metrics.r2_score:.3f})"
                )
                alerts.append(alert)
                logger.warning(f"⚠️ [{severity.upper()}] Drift R² détecté: {alert.message}")
        
        # 2. Drift MAE (hausse = problème)
        mae_drift = current_metrics.mae - self.baseline_metrics.mae
        if mae_drift > 0:  # MAE a augmenté
            severity = self._get_severity('mae', mae_drift)
            if severity:
                alert = DriftAlert(
                    metric_name='MAE',
                    current_value=current_metrics.mae,
                    baseline_value=self.baseline_metrics.mae,
                    drift_magnitude=mae_drift,
                    severity=severity,
                    detected_at=datetime.now(),
                    message=f"MAE a augmenté de {mae_drift:.3f}% ({self.baseline_metrics.mae:.3f}% → {current_metrics.mae:.3f}%)"
                )
                alerts.append(alert)
                logger.warning(f"⚠️ [{severity.upper()}] Drift MAE détecté: {alert.message}")
        
        # 3. Drift % Profitable (baisse = problème)
        profitable_drift = self.baseline_metrics.profitable_pct - current_metrics.profitable_pct
        if profitable_drift > 0:  # % profitable a baissé
            severity = self._get_severity('profitable_pct', profitable_drift)
            if severity:
                alert = DriftAlert(
                    metric_name='Profitable %',
                    current_value=current_metrics.profitable_pct,
                    baseline_value=self.baseline_metrics.profitable_pct,
                    drift_magnitude=profitable_drift,
                    severity=severity,
                    detected_at=datetime.now(),
                    message=f"% Profitable a baissé de {profitable_drift:.1f}% ({self.baseline_metrics.profitable_pct:.1f}% → {current_metrics.profitable_pct:.1f}%)"
                )
                alerts.append(alert)
                logger.warning(f"⚠️ [{severity.upper()}] Drift Profitable% détecté: {alert.message}")
        
        # Ajouter à l'historique
        self.alerts_history.extend(alerts)
        
        if not alerts:
            logger.info("✅ Aucun drift détecté")
        
        return alerts
    
    def _get_severity(self, metric: str, drift_value: float) -> Optional[str]:
        """
        Déterminer sévérité du drift
        
        Args:
            metric: Nom de la métrique ('r2', 'mae', 'profitable_pct')
            drift_value: Magnitude du drift
            
        Returns:
            Niveau de sévérité ou None si pas de drift significatif
        """
        thresholds = self.thresholds.get(metric, {})
        
        if drift_value >= thresholds.get('critical', float('inf')):
            return 'critical'
        elif drift_value >= thresholds.get('high', float('inf')):
            return 'high'
        elif drift_value >= thresholds.get('medium', float('inf')):
            return 'medium'
        elif drift_value >= thresholds.get('low', float('inf')):
            return 'low'
        else:
            return None
    
    def should_retrain(self, alerts: List[DriftAlert]) -> bool:
        """
        Déterminer si réentraînement nécessaire basé sur alertes
        
        Args:
            alerts: Liste des alertes de drift
            
        Returns:
            True si réentraînement recommandé
        """
        if not alerts:
            return False
        
        # Réentraîner si au moins une alerte HIGH ou CRITICAL
        high_severity = ['high', 'critical']
        critical_alerts = [a for a in alerts if a.severity in high_severity]
        
        if critical_alerts:
            logger.warning(f"🚨 {len(critical_alerts)} alerte(s) critique(s) → Réentraînement recommandé!")
            return True
        
        # Réentraîner si > 2 alertes MEDIUM
        medium_alerts = [a for a in alerts if a.severity == 'medium']
        if len(medium_alerts) > 2:
            logger.warning(f"⚠️ {len(medium_alerts)} alertes moyennes → Réentraînement recommandé!")
            return True
        
        return False
    
    def get_drift_report(
        self,
        current_metrics: ModelPerformanceMetrics,
        alerts: List[DriftAlert]
    ) -> Dict:
        """
        Générer rapport complet de drift
        
        Args:
            current_metrics: Métriques actuelles
            alerts: Alertes détectées
            
        Returns:
            Rapport JSON-sérialisable
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'baseline': {
                'r2': self.baseline_metrics.r2_score if self.baseline_metrics else None,
                'mae': self.baseline_metrics.mae if self.baseline_metrics else None,
                'trained_at': self.baseline_metrics.timestamp.isoformat() if self.baseline_metrics else None
            },
            'current': {
                'r2': current_metrics.r2_score,
                'mae': current_metrics.mae,
                'predictions_count': current_metrics.predictions_count,
                'profitable_pct': current_metrics.profitable_pct,
                'period': {
                    'start': current_metrics.period_start.isoformat(),
                    'end': current_metrics.period_end.isoformat()
                }
            },
            'drift': {
                'r2_drift': (self.baseline_metrics.r2_score - current_metrics.r2_score) if self.baseline_metrics else 0,
                'mae_drift': (current_metrics.mae - self.baseline_metrics.mae) if self.baseline_metrics else 0,
                'alerts_count': len(alerts),
                'alerts': [
                    {
                        'metric': a.metric_name,
                        'severity': a.severity,
                        'drift': a.drift_magnitude,
                        'message': a.message
                    }
                    for a in alerts
                ]
            },
            'recommendation': {
                'should_retrain': self.should_retrain(alerts),
                'severity_level': max([a.severity for a in alerts], key=lambda x: ['low', 'medium', 'high', 'critical'].index(x)) if alerts else 'none'
            }
        }
        
        return report
    
    def save_report_to_file(self, report: Dict, filepath: str = "monitoring/drift_reports"):
        """Sauvegarder rapport dans fichier"""
        try:
            from pathlib import Path
            
            output_dir = Path(filepath)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = output_dir / f"drift_report_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"📄 Rapport sauvegardé: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde rapport: {e}")
            return None


# Singleton pour éviter multiples instances
_drift_detector_instance: Optional[ModelDriftDetector] = None


def get_drift_detector() -> ModelDriftDetector:
    """Récupérer ou créer instance singleton du détecteur"""
    global _drift_detector_instance
    
    if _drift_detector_instance is None:
        _drift_detector_instance = ModelDriftDetector()
        _drift_detector_instance.load_baseline_from_postgres()
    
    return _drift_detector_instance


def monitor_model_performance(
    predictions: pd.DataFrame,
    actuals: pd.DataFrame,
    save_report: bool = True
) -> Dict:
    """
    Helper function pour monitorer performance et détecter drift
    
    Args:
        predictions: DataFrame avec predicted_pnl
        actuals: DataFrame avec actual_pnl
        save_report: Si True, sauvegarder rapport dans fichier
        
    Returns:
        Rapport de drift
    """
    try:
        detector = get_drift_detector()
        
        # Calculer performance actuelle
        current_metrics = detector.calculate_current_performance(predictions, actuals)
        
        # Détecter drift
        alerts = detector.detect_drift(current_metrics)
        
        # Générer rapport
        report = detector.get_drift_report(current_metrics, alerts)
        
        # Sauvegarder si demandé
        if save_report:
            detector.save_report_to_file(report)
        
        # Afficher résumé
        if alerts:
            logger.warning(f"⚠️ {len(alerts)} alerte(s) de drift détectée(s)!")
            for alert in alerts:
                logger.warning(f"  [{alert.severity.upper()}] {alert.message}")
            
            if report['recommendation']['should_retrain']:
                logger.warning("🚨 RECOMMANDATION: Réentraîner le modèle V2!")
        else:
            logger.info("✅ Modèle V2 stable, aucun drift détecté")
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Erreur monitoring: {e}", exc_info=True)
        raise
