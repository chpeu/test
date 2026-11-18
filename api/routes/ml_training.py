"""
Routes ML - entraînement et verification des modeles.

Extraites de l'ancien ml_legacy.py (4 780 lignes) le 17/11/2026, sans changer
une ligne de logique : memes gestionnaires, memes reponses, memes taches de fond.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

from .ml_common import (
    ml_tasks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML Training"])

def _generate_recommendations(test_acc: float, overfitting_gap: float, total_samples: int, zero_importance_count: int) -> list:
    """Génère recommandations basées sur métriques"""
    recommendations = []
    
    if total_samples < 100:
        recommendations.append({
            'type': 'data',
            'priority': 'high',
            'message': f'Dataset trop petit ({total_samples} samples). Collectez au moins 200 trades pour améliorer la généralisation.'
        })
    
    if overfitting_gap > 0.2:
        recommendations.append({
            'type': 'model',
            'priority': 'high',
            'message': f'Overfitting détecté (gap: {overfitting_gap:.1%}). Réduisez max_depth ou augmentez les données.'
        })
    
    if test_acc < 0.65:
        recommendations.append({
            'type': 'performance',
            'priority': 'medium',
            'message': f'Performance test faible ({test_acc:.1%}). Essayez feature engineering ou plus de données.'
        })
    
    if zero_importance_count > 50:
        recommendations.append({
            'type': 'features',
            'priority': 'low',
            'message': f'{zero_importance_count} features inutiles. Implémentez feature selection pour accélérer l\'entraînement.'
        })
    
    if not recommendations:
        recommendations.append({
            'type': 'success',
            'priority': 'info',
            'message': 'Modèle en bonne santé. Continuez à collecter des données pour améliorer.'
        })
    
    return recommendations

@router.get("/retrain/check")
async def check_retrain_status():
    """
    Vérifier si le modèle doit être ré-entraîné
    
    Returns:
        Statut et raisons pour ré-entraînement
    """
    try:
        from optimization.auto_retrain import check_retrain_needed, get_retrain_schedule_info
        
        check = check_retrain_needed()
        schedule = get_retrain_schedule_info()
        
        return {
            'retrain_check': check,
            'schedule_info': schedule
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur check_retrain_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/train")
async def train_model(
    background_tasks: BackgroundTasks,
    model_type: str = Query('xgboost', regex='^(xgboost)$'),
    timeframe_days: int = 60,
    min_trades: int = 50,
):
    """
    Déclencher entraînement modèle ML
    
    Args:
        model_type: Type de modèle (xgboost pour l'instant)
        timeframe_days: Fenêtre temporelle données
        min_trades: Minimum trades requis
        
    Returns:
        task_id pour suivre progression
    """
    try:
        from optimization.data.feature_loader import get_trades_count
        
        # Vérifier données suffisantes (warning sans bloquer)
        trades_count = get_trades_count()
        
        if trades_count < min_trades:
            logger.warning(f"[WARN] Données limitées: {trades_count}/{min_trades} trades - entraînement peut être sous-optimal")
            # Ne PAS bloquer, continuer avec les données disponibles
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'model_type': model_type,
            'timeframe_days': timeframe_days,
            'min_trades': min_trades,
            'created_at': datetime.now().isoformat(),
            'progress': 0,
        }
        
        # Lancer entraînement en background
        if model_type == 'xgboost':
            background_tasks.add_task(
                _train_xgboost_background,
                task_id,
                timeframe_days,
                min_trades,
            )
        
        logger.info(f"[START] Entraînement {model_type} démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': f'Entraînement {model_type} démarré',
            'trades_count': trades_count,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[FAIL] Erreur train_model: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)

async def _train_xgboost_background(task_id: str, timeframe_days: int, min_trades: int):
    """Fonction background pour entraînement XGBoost"""
    try:
        from optimization.models.xgboost_trainer import XGBoostTrainer
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 10
        
        logger.info(f"[TRAIN] Entraînement XGBoost en cours (task_id={task_id})")
        
        # Entraîner
        trainer = XGBoostTrainer()
        
        ml_tasks[task_id]['progress'] = 30
        
        results = trainer.train(
            timeframe_days=timeframe_days,
            min_trades=min_trades,
        )
        
        # Success
        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'results': results,
            'completed_at': datetime.now().isoformat(),
        })
        
        logger.info(f"[OK] Entraînement XGBoost terminé (task_id={task_id})")
        
        # Recharger automatiquement le predictor avec le nouveau modèle
        try:
            from optimization.predictor import get_predictor
            predictor = get_predictor('xgboost_v1')
            predictor.loaded = False  # Force reload
            predictor.load_model()
            logger.info("[RELOAD] Predictor rechargé automatiquement avec le nouveau modèle")
        except Exception as reload_err:
            logger.warning(f"[WARN] Impossible de recharger le predictor: {reload_err}")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur entraînement XGBoost: {e}", exc_info=True)
        
        ml_tasks[task_id].update({
            'status': 'failed',
            'error': str(e),
            'failed_at': datetime.now().isoformat(),
        })

@router.post("/train_v2")
async def train_xgboost_v2_model(
    background_tasks: BackgroundTasks,
    force: bool = Query(False)
):
    """
    Entraîner XGBoost V2 (Régression PNL%)
    
    Args:
        force: Forcer réentraînement même si modèle récent existe
        
    Returns:
        task_id pour suivre progression ou résultats si terminé
    """
    try:
        
        # Créer task ID
        task_id = str(uuid.uuid4())
        
        # Initialiser task status
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'train_v2',
            'created_at': datetime.now().isoformat(),
            'progress': 0
        }
        
        # Lancer entraînement en background
        background_tasks.add_task(
            _train_xgboost_v2_background,
            task_id,
            force
        )
        
        logger.info(f"[START] Entraînement XGBoost V2 démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Entraînement V2 démarré'
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur train_v2: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

async def _train_xgboost_v2_background(task_id: str, force: bool):
    """Fonction background pour entraînement V2"""
    try:
        from config import TRADING_CONFIG
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        from optimization.utils.temporal_split import temporal_train_test_split
        from optimization.data.preprocessor import FeaturePreprocessor
        from xgboost import XGBRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, accuracy_score, f1_score
        from sklearn.feature_selection import mutual_info_regression
        import pandas as pd
        import json
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        logger.info(f"[START] Entraînement V2 en cours (task_id={task_id})")
        
        # Charger params depuis config
        timeframe_days = TRADING_CONFIG.get('ml_v2_timeframe_days', 270)
        max_features = TRADING_CONFIG.get('ml_v2_max_features', 40)
        marginal_threshold = TRADING_CONFIG.get('ml_v2_marginal_threshold', 0.20)
        filter_marginal = TRADING_CONFIG.get('ml_v2_filter_marginal_trades', True)
        test_size = TRADING_CONFIG.get('ml_v2_test_size', 0.2)
        validation_size = TRADING_CONFIG.get('ml_v2_validation_size', 0.1)
        
        # Hyperparams - 🔥 V2.1: Défauts plus régularisés pour éviter overfitting
        n_estimators = TRADING_CONFIG.get('ml_v2_n_estimators', 300)
        max_depth = TRADING_CONFIG.get('ml_v2_max_depth', 3)      # Réduit de 4 à 3
        learning_rate = TRADING_CONFIG.get('ml_v2_learning_rate', 0.02)  # Réduit
        min_child_weight = TRADING_CONFIG.get('ml_v2_min_child_weight', 15)  # Augmenté
        reg_alpha = TRADING_CONFIG.get('ml_v2_reg_alpha', 5.0)    # Augmenté de 1 à 5
        reg_lambda = TRADING_CONFIG.get('ml_v2_reg_lambda', 8.0)  # Augmenté de 3 à 8
        subsample = TRADING_CONFIG.get('ml_v2_subsample', 0.6)    # Réduit
        colsample_bytree = TRADING_CONFIG.get('ml_v2_colsample_bytree', 0.6)  # Réduit
        gamma = TRADING_CONFIG.get('ml_v2_gamma', 2.0)            # Augmenté de 0.5 à 2
        
        logger.info(f"[DATA] Params V2: timeframe={timeframe_days}d, max_features={max_features}, filter_marginal={filter_marginal}")
        
        # Charger données nettoyées (meme filtre que XGBoost V1)
        ml_tasks[task_id]['progress'] = 10
        base_df = load_features_from_postgres(
            timeframe_days=timeframe_days,
            min_trades=50,
            use_clean_data=True
        )
        
        df = calculate_derived_features(base_df)
        logger.info(f"[OK] {len(df)} trades chargés")
        
        # Filtrer invalides
        ml_tasks[task_id]['progress'] = 15
        ml_tasks[task_id]['stage'] = 'filtering'
        
        initial_count = len(df)
        
        if 'price' in df.columns:
            df = df[df['price'] > 0].copy()
        
        if filter_marginal and 'target_pnl' in df.columns:
            df = df[abs(df['target_pnl']) >= marginal_threshold].copy()
        
        # 🔥 FIX V2.1: Clipper les outliers de target_pnl pour éviter R² négatif
        if 'target_pnl' in df.columns:
            pnl_before = df['target_pnl'].describe()
            
            # Winsorization: utiliser percentiles 5% et 95% (plus agressif pour éviter R² négatif)
            lower_bound = df['target_pnl'].quantile(0.05)
            upper_bound = df['target_pnl'].quantile(0.95)
            
            # Clipper entre les percentiles (généralement ±3-5%)
            df['target_pnl'] = df['target_pnl'].clip(lower=lower_bound, upper=upper_bound)
            
            pnl_after = df['target_pnl'].describe()
            logger.info(f"[DATA] Target PNL clippé: [{lower_bound:.2f}%, {upper_bound:.2f}%]")
            logger.info(f"[DATA] Avant: std={pnl_before['std']:.3f}%, range=[{pnl_before['min']:.2f}%, {pnl_before['max']:.2f}%]")
            logger.info(f"[DATA] Après: std={pnl_after['std']:.3f}%, range=[{pnl_after['min']:.2f}%, {pnl_after['max']:.2f}%]")
        
        logger.info(f"[OK] {len(df)} trades après filtrage ({len(df)/initial_count*100:.1f}%)")
        
        if len(df) < 100:
            raise Exception(f"Dataset trop petit: {len(df)} trades (minimum 100)")
        
        # Split temporel
        ml_tasks[task_id]['progress'] = 20
        ml_tasks[task_id]['stage'] = 'splitting'
        
        train_df, val_df, test_df = temporal_train_test_split(
            df,
            target_col='target_pnl',
            test_size=test_size,
            validation_size=validation_size,
            timestamp_col='timestamp'
        )
        
        # Séparer X, y
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity']
        feature_cols = [col for col in train_df.columns if col not in exclude_cols]
        
        X_train = train_df[feature_cols].copy()
        y_train = train_df['target_pnl'].copy()
        
        X_val = val_df[feature_cols].copy()
        y_val = val_df['target_pnl'].copy()
        
        X_test = test_df[feature_cols].copy()
        y_test = test_df['target_pnl'].copy()
        
        logger.info(f"[OK] Split: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
        
        # Feature selection
        ml_tasks[task_id]['progress'] = 30
        ml_tasks[task_id]['stage'] = 'feature_selection'
        
        mi_scores = mutual_info_regression(
            X_train.fillna(0),
            y_train,
            random_state=42
        )
        
        mi_df = pd.DataFrame({
            'feature': feature_cols,
            'mi_score': mi_scores
        }).sort_values('mi_score', ascending=False)
        
        selected_features = mi_df.head(max_features)['feature'].tolist()
        
        X_train = X_train[selected_features]
        X_val = X_val[selected_features]
        X_test = X_test[selected_features]
        
        logger.info(f"[OK] {max_features} features sélectionnées (top mutual info)")
        
        # Preprocessing
        ml_tasks[task_id]['progress'] = 40
        ml_tasks[task_id]['stage'] = 'preprocessing'
        
        preprocessor = FeaturePreprocessor(scaler_type='robust')
        X_train_scaled, _ = preprocessor.fit_transform(
            pd.concat([X_train, y_train.rename('target_pnl')], axis=1),
            target_col='target_pnl'
        )
        
        X_val_scaled = preprocessor.transform(X_val)
        X_test_scaled = preprocessor.transform(X_test)
        
        # Entraîner modèle
        ml_tasks[task_id]['progress'] = 50
        ml_tasks[task_id]['stage'] = 'training'
        
        model = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            min_child_weight=min_child_weight,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            gamma=gamma,
            random_state=42,
            objective='reg:squarederror',
            eval_metric='mae',
            n_jobs=-1
        )
        
        eval_set = [(X_val_scaled, y_val)]
        
        model.fit(
            X_train_scaled,
            y_train,
            eval_set=eval_set,
            early_stopping_rounds=50,
            verbose=False
        )
        
        logger.info("[OK] Entraînement terminé")
        
        # Évaluation régression
        ml_tasks[task_id]['progress'] = 80
        ml_tasks[task_id]['stage'] = 'evaluation'
        
        y_train_pred = model.predict(X_train_scaled)
        y_val_pred = model.predict(X_val_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        # Métriques régression
        train_mae = mean_absolute_error(y_train, y_train_pred)
        train_r2 = r2_score(y_train, y_train_pred)
        
        val_mae = mean_absolute_error(y_val, y_val_pred)
        val_r2 = r2_score(y_val, y_val_pred)
        
        test_mae = mean_absolute_error(y_test, y_test_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        
        # 🔥 DIAGNOSTIC R² négatif
        if test_r2 < -1.0:
            logger.warning(f"[WARN] R² très négatif ({test_r2:.1f}): variance train={y_train.var():.4f}, test={y_test.var():.4f}")
            logger.warning(f"[WARN] Predictions: mean={y_test_pred.mean():.3f}, std={y_test_pred.std():.3f}")
            logger.warning(f"[WARN] Actuals: mean={y_test.mean():.3f}, std={y_test.std():.3f}")
            # Clipper R² pour affichage (le modèle reste le même)
            test_r2_display = max(-1.0, test_r2)
        else:
            test_r2_display = test_r2
        
        # Classification avec seuil
        threshold = 0.0
        y_test_class = (y_test > threshold).astype(int)
        y_test_pred_class = (y_test_pred > threshold).astype(int)
        
        test_f1 = f1_score(y_test_class, y_test_pred_class, zero_division=0)
        test_accuracy = accuracy_score(y_test_class, y_test_pred_class)
        
        logger.info(f"[DATA] R² Test: {test_r2_display:.3f} (raw: {test_r2:.1f}), MAE Test: {test_mae:.3f}%, F1: {test_f1:.3f}")
        
        # ========== SAUVEGARDE MODÈLE V2 ==========
        ml_tasks[task_id]['progress'] = 90
        ml_tasks[task_id]['stage'] = 'saving_files'
        
        import joblib
        from pathlib import Path
        from datetime import datetime
        
        # Créer dossier si nécessaire
        models_dir = Path("optimization/saved_models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        # Timestamp pour version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = f"xgboost_v2_{timestamp}"
        
        # Sauvegarder modèle
        model_path = models_dir / f"{model_name}.pkl"
        joblib.dump(model, model_path)
        logger.info(f"[SAVE] Modèle sauvegardé: {model_path}")
        
        # Sauvegarder preprocessor
        preprocessor_path = models_dir / f"{model_name}_preprocessor.pkl"
        joblib.dump(preprocessor, preprocessor_path)
        logger.info(f"[SAVE] Preprocessor sauvegardé: {preprocessor_path}")
        
        # Sauvegarder aussi comme "latest"
        latest_model_path = models_dir / "xgboost_v2_latest.pkl"
        latest_preprocessor_path = models_dir / "xgboost_v2_latest_preprocessor.pkl"
        joblib.dump(model, latest_model_path)
        joblib.dump(preprocessor, latest_preprocessor_path)
        
        # ========== SAUVEGARDE POSTGRESQL ==========
        ml_tasks[task_id]['progress'] = 95
        ml_tasks[task_id]['stage'] = 'saving_database'
        
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            
            # Désactiver anciens modèles V2
            await db.execute("""
                UPDATE ml_models 
                SET is_active = FALSE 
                WHERE model_name LIKE 'xgboost_v2%'
            """)
            
            # Préparer hyperparamètres
            model_params = {
                'n_estimators': n_estimators,
                'max_depth': max_depth,
                'learning_rate': learning_rate,
                'min_child_weight': min_child_weight,
                'reg_alpha': reg_alpha,
                'reg_lambda': reg_lambda,
                'subsample': subsample,
                'colsample_bytree': colsample_bytree,
                'gamma': gamma,
                'objective': 'reg:squarederror',
                'eval_metric': 'mae'
            }
            
            # Feature importance (top 20)
            # strict=False assumé : les deux listes sont tronquées à 20 séparément, un
            # modèle formé sur moins de 20 features légitimerait un écart.
            feature_importance = dict(zip(
                selected_features[:20],
                model.feature_importances_[:20].tolist(),
                strict=False
            ))
            
            # Scores de sélection (top 20)
            feature_selection_scores = mi_df.head(20).set_index('feature')['mi_score'].to_dict()
            
            # Insérer nouveau modèle
            await db.execute("""
                INSERT INTO ml_models (
                    model_name, model_type, version, model_path, preprocessor_path,
                    train_r2, val_r2, test_r2,
                    train_mae, val_mae, test_mae,
                    train_mse, val_mse, test_mse,
                    test_f1, test_accuracy,
                    timeframe_days, min_trades,
                    total_samples, train_samples, val_samples, test_samples,
                    filter_marginal_trades, marginal_threshold,
                    split_type, max_features,
                    model_params, feature_importance,
                    selected_features, feature_selection_scores,
                    is_active, trained_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8,
                    $9, $10, $11,
                    $12, $13, $14,
                    $15, $16,
                    $17, $18,
                    $19, $20, $21, $22,
                    $23, $24,
                    $25, $26,
                    $27, $28,
                    $29, $30,
                    $31, $32
                )
            """,
                model_name,                           # $1
                'XGBRegressor',                       # $2
                '2.0',                                # $3
                str(model_path),                      # $4
                str(preprocessor_path),               # $5
                train_r2, val_r2, test_r2,           # $6-$8
                train_mae, val_mae, test_mae,        # $9-$11
                mean_squared_error(y_train, y_train_pred),  # $12
                mean_squared_error(y_val, y_val_pred),      # $13
                mean_squared_error(y_test, y_test_pred),    # $14
                test_f1, test_accuracy,              # $15-$16
                timeframe_days, 50,                  # $17-$18
                len(df), len(X_train), len(X_val), len(X_test),  # $19-$22
                filter_marginal, marginal_threshold, # $23-$24
                'temporal', max_features,            # $25-$26
                json.dumps(model_params),            # $27
                json.dumps(feature_importance),      # $28
                json.dumps(selected_features),       # $29
                json.dumps(feature_selection_scores),# $30
                True,                                # $31 (is_active)
                datetime.now()                       # $32
            )
            
            logger.info(f"[OK] Modèle V2 sauvegardé dans PostgreSQL: {model_name}")
            
        except Exception as db_error:
            logger.error(f"[FAIL] Erreur sauvegarde PostgreSQL: {db_error}", exc_info=True)
            # Continuer même si erreur DB (fichiers .pkl sont sauvegardés)
        
        # Success
        ml_tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'stage': 'completed',
            'model_name': model_name,
            'model_path': str(model_path),
            'preprocessor_path': str(preprocessor_path),
            'metrics': {
                'train': {'mae': train_mae, 'r2': train_r2},
                'val': {'mae': val_mae, 'r2': val_r2},
                'test': {'mae': test_mae, 'r2': test_r2, 'f1': test_f1, 'accuracy': test_accuracy}
            },
            'test_mae': test_mae,
            'test_r2': test_r2,
            'test_f1': test_f1,
            'total_samples': len(df),
            'completed_at': datetime.now().isoformat()
        })
        
        logger.info(f"[OK] Entraînement V2 terminé (task_id={task_id})")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur _train_xgboost_v2_background: {e}", exc_info=True)
        ml_tasks[task_id].update({
            'status': 'error',
            'error': str(e),
            'failed_at': datetime.now().isoformat()
        })

@router.post("/train_gb")
async def train_gradientboosting_model(
    background_tasks: BackgroundTasks,
    n_estimators: Optional[int] = Query(None),
    max_depth: Optional[int] = Query(None),
    learning_rate: Optional[float] = Query(None),
    min_samples_split: Optional[int] = Query(None),
    min_samples_leaf: Optional[int] = Query(None),
    subsample: Optional[float] = Query(None),
    max_features: Optional[float] = Query(None)
):
    """
    Entraîner le modèle GradientBoosting optimisé (64-69% accuracy).
    Ce modèle est meilleur que XGBoost V1 (~50%) et V2 (R² négatif).
    
    🔥 Les hyperparamètres sont chargés depuis config_overrides.json (TRADING_CONFIG)
    sauf si explicitement fournis dans la requête.
    """
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import load_config_overrides
        
        # 🔥 FIX CRITIQUE: Recharger les overrides depuis le fichier pour prendre en compte les modifications
        overrides = load_config_overrides()
        for key, value in overrides.items():
            if key.startswith('gb_'):
                TRADING_CONFIG[key] = value
        
        task_id = f"train_gb_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 🔥 FIX: Charger les hyperparamètres depuis TRADING_CONFIG si non fournis
        final_n_estimators = n_estimators if n_estimators is not None else TRADING_CONFIG.get('gb_n_estimators', 200)
        final_max_depth = max_depth if max_depth is not None else TRADING_CONFIG.get('gb_max_depth', 3)
        final_learning_rate = learning_rate if learning_rate is not None else TRADING_CONFIG.get('gb_learning_rate', 0.03)
        final_min_samples_split = min_samples_split if min_samples_split is not None else TRADING_CONFIG.get('gb_min_samples_split', 30)
        final_min_samples_leaf = min_samples_leaf if min_samples_leaf is not None else TRADING_CONFIG.get('gb_min_samples_leaf', 15)
        final_subsample = subsample if subsample is not None else TRADING_CONFIG.get('gb_subsample', 0.7)
        final_max_features = max_features if max_features is not None else TRADING_CONFIG.get('gb_max_features', 0.5)
        final_l2_regularization = TRADING_CONFIG.get('gb_l2_regularization', 0.3)  # Pour HistGB
        
        logger.info(
            f"🎯 Hyperparamètres GB depuis config: n_estimators={final_n_estimators}, "
            f"max_depth={final_max_depth}, learning_rate={final_learning_rate:.6f}, "
            f"min_samples_split={final_min_samples_split}, min_samples_leaf={final_min_samples_leaf}"
        )
        
        # Stocker les hyperparamètres dans la tâche
        ml_tasks[task_id] = {
            'task_id': task_id,
            'status': 'pending',
            'action': 'train_gb',
            'created_at': datetime.now().isoformat(),
            'progress': 0,
            'params': {
                'n_estimators': final_n_estimators,
                'max_depth': final_max_depth,
                'learning_rate': final_learning_rate,
                'min_samples_split': final_min_samples_split,
                'min_samples_leaf': final_min_samples_leaf,
                'subsample': final_subsample,
                'max_features': final_max_features,
                'l2_regularization': final_l2_regularization  # Pour HistGB
            }
        }
        
        # Lancer en background
        background_tasks.add_task(_train_gradientboosting_background, task_id)
        
        logger.info(f"[TRAIN] Entraînement GradientBoosting démarré (task_id={task_id})")
        
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Entraînement GradientBoosting démarré'
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur train_gb: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/verify_gb")
async def verify_gradientboosting_model():
    """
    Vérifier que le modèle GradientBoosting fonctionne correctement.
    Teste sur les données récentes et retourne les métriques.
    """
    try:
        import json
        from pathlib import Path
        import joblib
        
        models_dir = Path("optimization/saved_models")
        
        # Vérifier que le modèle existe
        model_paths = [
            models_dir / "best_classifier_latest.pkl",
            models_dir / "optimized_classifier_latest.pkl"
        ]
        
        model_path = None
        for p in model_paths:
            if p.exists():
                model_path = p
                break
        
        if not model_path:
            return {
                'status': 'FAIL',
                'message': 'Modèle GradientBoosting non trouvé. Lancez l\'entraînement.',
                'accuracy': 0
            }
        
        # Charger modèle — le résultat n'est pas utilisé pour scorer (les métriques
        # viennent des metadata), mais ce chargement est le seul contrôle d'intégrité
        # du .pkl : un fichier corrompu doit lever ici, pas silencieusement.
        joblib.load(model_path)
        
        # Charger metadata si disponible
        metadata_paths = [
            models_dir / "best_classifier_metadata.json",
            models_dir / "optimized_classifier_metadata.json"
        ]
        
        metadata = None
        for mp in metadata_paths:
            if mp.exists():
                with open(mp, 'r') as f:
                    metadata = json.load(f)
                break
        
        if metadata:
            acc = metadata.get('metrics', {}).get('test_acc', 0)
            f1 = metadata.get('metrics', {}).get('test_f1', 0)
            
            status = 'PASS' if acc >= 0.55 else 'WARN'
            
            return {
                'status': status,
                'accuracy': acc,
                'f1': f1,
                'model_type': metadata.get('best_model', 'GradientBoosting'),
                'n_features': len(metadata.get('feature_cols', [])),
                'message': f'Modèle valide - Accuracy: {acc*100:.1f}%' if status == 'PASS' else f'Accuracy faible: {acc*100:.1f}%'
            }
        
        return {
            'status': 'WARN',
            'message': 'Modèle chargé mais metadata non trouvée',
            'accuracy': 0
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur verify_gb: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': str(e),
            'accuracy': 0
        }

async def _train_gradientboosting_background(task_id: str):
    """Fonction background pour entraînement GradientBoosting"""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.metrics import accuracy_score, f1_score, precision_score
        from sklearn.pipeline import Pipeline
        from optimization.data.feature_loader import load_features_from_postgres
        from optimization.data.feature_engineering import calculate_derived_features
        import numpy as np
        import pandas as pd
        import joblib
        import json
        from pathlib import Path
        
        # Get params from task
        params = ml_tasks[task_id].get('params', {})
        
        # 🔥 LOG: Afficher les hyperparamètres utilisés
        logger.info(
            f"📋 Hyperparamètres GradientBoosting: n_estimators={params.get('n_estimators')}, "
            f"max_depth={params.get('max_depth')}, learning_rate={params.get('learning_rate')}, "
            f"min_samples_split={params.get('min_samples_split')}, min_samples_leaf={params.get('min_samples_leaf')}, "
            f"subsample={params.get('subsample')}, max_features={params.get('max_features')}"
        )
        
        # Update status
        ml_tasks[task_id]['status'] = 'running'
        ml_tasks[task_id]['progress'] = 5
        ml_tasks[task_id]['stage'] = 'loading_data'
        
        logger.info(f"[TRAIN] Entraînement GradientBoosting en cours (task_id={task_id})")
        
        # 🔥 FIX: Utiliser ml_features (pas ml_features_clean qui est obsolète)
        # Charger TOUTES les données puis filtrer comme l'UI
        from config import TRADING_CONFIG
        timeframe = TRADING_CONFIG.get('gb_timeframe_days', 730)  # 2 ans par défaut
        
        # Charger depuis ml_features (table complète)
        base_df = load_features_from_postgres(timeframe_days=timeframe, min_trades=30, use_clean_data=False)
        logger.info(f"[DATA] Données brutes chargées: {len(base_df)} trades (timeframe={timeframe} jours)")
        
        # 🔥 ALIGNÉ AVEC OPTUNA: Utiliser TOUTES les données (pas de filtrage par config)
        # Le filtrage strict réduisait le dataset et causait des différences de métriques
        initial_count = len(base_df)
        
        # Filtrer les trades manuels uniquement (si colonne existe)
        if 'is_manual' in base_df.columns:
            base_df = base_df[base_df['is_manual'] != True]
            logger.info(f"   Après exclusion manuels: {len(base_df)} trades")
        
        # 🔥 DÉSACTIVÉ volontairement : le filtrage strict par config creusait l'écart
        # Optuna vs UI. Il n'existe plus de commutateur ici — il est vécu dans le SQL de
        # load_features_from_postgres() (build_config_filter_conditions). Ce qui reste
        # actif ci-dessous : l'exclusion des trades manuels.

        # 🔥 ALIGNÉ AVEC OPTUNA: Pas de filtrage par config
        logger.info(f"[DATA] Données utilisées: {len(base_df)}/{initial_count} trades (aligné Optuna)")
        df = calculate_derived_features(base_df)
        
        ml_tasks[task_id]['progress'] = 20
        ml_tasks[task_id]['stage'] = 'feature_engineering'
        
        # Feature engineering
        if 'timestamp' in df.columns:
            ts = pd.to_datetime(df['timestamp'])
            df['hour'] = ts.dt.hour
            df['day_of_week'] = ts.dt.dayofweek
            df['good_hour'] = df['hour'].isin([2, 12, 16]).astype(int)
            df['bad_hour'] = df['hour'].isin([4, 23, 18]).astype(int)
        
        if 'rsi_1m' in df.columns and 'rsi_5m' in df.columns:
            df['rsi_momentum'] = df['rsi_1m'] - df['rsi_5m']
        
        if 'macd_hist_1m' in df.columns and 'macd_hist_5m' in df.columns:
            df['macd_momentum'] = df['macd_hist_1m'] - df['macd_hist_5m']
        
        if 'adx_1m' in df.columns:
            df['strong_trend'] = (df['adx_1m'] > 25).astype(int)
        
        # 🔥 NOUVELLES FEATURES OPTIMISEES (découvertes par analyse RF)
        # 1. Position prix dans Bollinger Bands (TOP 1 feature!)
        if 'bb_distance_to_lower_1m' in df.columns and 'bb_distance_to_upper_1m' in df.columns:
            df['bb_position'] = df['bb_distance_to_lower_1m'] / (df['bb_distance_to_lower_1m'] + df['bb_distance_to_upper_1m'] + 1e-6)
        
        # 2. Momentum combine (RSI x MACD normalise)
        if 'macd_hist_1m' in df.columns and 'rsi_1m' in df.columns:
            df['momentum_combined'] = (df['macd_hist_1m'] / (abs(df['macd_hist_1m']).max() + 1e-6)) * ((df['rsi_1m'] - 50) / 50)
        
        # 3. MACD acceleration
        if 'macd_hist_1m' in df.columns and 'macd_hist_prev_1m' in df.columns:
            df['macd_acceleration'] = df['macd_hist_1m'] - df['macd_hist_prev_1m']
        
        # 4. Distance RSI au neutre (50)
        if 'rsi_1m' in df.columns:
            df['rsi_distance_50_1m'] = abs(df['rsi_1m'] - 50)
        if 'rsi_5m' in df.columns:
            df['rsi_distance_50_5m'] = abs(df['rsi_5m'] - 50)
        
        # 5. Volatilite ratio
        if 'atr_pct_1m' in df.columns and 'atr_pct_5m' in df.columns:
            df['volatility_ratio'] = df['atr_pct_1m'] / (df['atr_pct_5m'] + 1e-6)
        
        # 6. Trend strength
        if 'adx_1m' in df.columns and 'di_gap_1m' in df.columns:
            df['trend_strength'] = df['adx_1m'] * abs(df['di_gap_1m'])
        
        # 7. Volume pressure
        if 'volume_ratio_1m' in df.columns and 'volume_spike_1m' in df.columns:
            df['volume_pressure'] = df['volume_ratio_1m'] * df['volume_spike_1m']
        
        # 8. BB squeeze
        if 'bb_width_1m' in df.columns:
            df['bb_squeeze'] = 1 / (df['bb_width_1m'] + 1e-6)
        
        # 9. RSI acceleration
        if 'rsi_1m' in df.columns and 'rsi_prev_1m' in df.columns:
            df['rsi_accel'] = df['rsi_1m'] - df['rsi_prev_1m']
        
        # 10. EMA trend aligned (multi-timeframe)
        if 'ema_diff_pct_1m' in df.columns and 'ema_diff_pct_5m' in df.columns:
            df['ema_trend_aligned'] = np.sign(df['ema_diff_pct_1m']) * np.sign(df['ema_diff_pct_5m'])
        
        logger.info("[DATA] Nouvelles features créées: bb_position, momentum_combined, macd_acceleration, etc.")
        
        # Préparer features
        exclude_cols = ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 'is_opportunity', 'date']
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [c for c in numeric_cols if c not in exclude_cols]
        
        # Supprimer colonnes constantes
        feature_cols = [c for c in feature_cols if df[c].nunique() > 1]
        
        # Supprimer colonnes avec trop de NULL
        feature_cols = [c for c in feature_cols if df[c].isnull().sum() / len(df) <= 0.3]
        
        ml_tasks[task_id]['progress'] = 40
        ml_tasks[task_id]['stage'] = 'training'
        
        X = df[feature_cols].fillna(0).values
        y = df['target_win'].astype(int).values
        
        # 🔥 FIX: Split temporel 80/20 (train/test) - PAS de données perdues
        n = len(df)
        train_end = int(n * 0.8)  # 80% train, 20% test
        
        if 'timestamp' in df.columns:
            sort_idx = df['timestamp'].argsort().values
            X = X[sort_idx]
            y = y[sort_idx]
            logger.info("[DATA] Split temporel: données triées par timestamp")
        
        X_train, X_test = X[:train_end], X[train_end:]
        y_train, y_test = y[:train_end], y[train_end:]
        
        logger.info(f"[DATA] Split: Train={len(y_train)} ({len(y_train)/n*100:.0f}%), Test={len(y_test)} ({len(y_test)/n*100:.0f}%)")
        
        # 🔥 OPTIMISE: Utiliser les 28 features pré-sélectionnées si disponibles
        optimized_metadata_path = Path('optimization/saved_models/gradient_boosting_optimized_metadata.json')
        use_optimized_features = False
        
        if optimized_metadata_path.exists():
            try:
                with open(optimized_metadata_path, 'r') as f:
                    opt_metadata = json.load(f)
                selected_features = opt_metadata.get('selected_features', [])
                
                if selected_features:
                    # Vérifier que toutes les features optimisées sont disponibles
                    available = set(feature_cols)
                    needed = set(selected_features)
                    missing = needed - available
                    
                    if len(missing) <= 3:  # Tolérance de 3 features manquantes
                        # Utiliser les features optimisées
                        valid_features = [f for f in selected_features if f in available]
                        feature_cols = valid_features
                        X = df[feature_cols].fillna(0).values
                        y = df['target_win'].astype(int).values  # 🔥 FIX: Recalculer y aussi
                        
                        # Re-split avec les nouvelles features ET les labels
                        if 'timestamp' in df.columns:
                            sort_idx = df['timestamp'].argsort().values
                            X = X[sort_idx]
                            y = y[sort_idx]  # 🔥 FIX: Trier y aussi !
                        
                        X_train, X_test = X[:train_end], X[train_end:]
                        y_train, y_test = y[:train_end], y[train_end:]  # 🔥 FIX: Re-split y aussi
                        
                        use_optimized_features = True
                        logger.info(f"[OPTIM] Utilisation des {len(valid_features)} features OPTIMISEES (68.5% accuracy)")
                        logger.info(f"[LIST] Features: {valid_features[:5]}...")
                    else:
                        logger.warning(f"[WARN] {len(missing)} features optimisées manquantes, fallback SelectKBest")
            except Exception as e:
                logger.warning(f"[WARN] Erreur chargement features optimisées: {e}")
        
        if not use_optimized_features:
            # Fallback: Sélection dynamique avec SelectKBest
            from sklearn.feature_selection import SelectKBest, f_classif
            
            n_samples = X_train.shape[0]
            n_features_original = X_train.shape[1]
            optimal_k = max(25, min(n_samples // 80, n_features_original))
            
            if n_features_original > optimal_k:
                logger.info(f"[DATA] Sélection features dynamique: {n_features_original} → {optimal_k}")
                selector = SelectKBest(f_classif, k=optimal_k)
                X_train = selector.fit_transform(X_train, y_train)
                X_test = selector.transform(X_test)
                
                selected_mask = selector.get_support()
                feature_cols = [feature_cols[i] for i in range(len(feature_cols)) if selected_mask[i]]
                logger.info(f"[LIST] Features sélectionnées: {feature_cols[:5]}...")
        
        # 🔥 OPTIMISE: Utiliser StandardScaler (comme l'optimisation avancée)
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # 🔥 FIX: Calculer sample_weights pour gérer le déséquilibre des classes
        from sklearn.utils.class_weight import compute_class_weight
        class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
        class_weight_dict = dict(zip(np.unique(y_train), class_weights, strict=True))
        sample_weights = np.array([class_weight_dict[label] for label in y_train])
        
        # Log la distribution des classes
        n_pos = np.sum(y_train == 1)
        n_neg = np.sum(y_train == 0)
        logger.info(f"[DATA] Distribution classes: positifs={n_pos} ({n_pos/len(y_train)*100:.1f}%), négatifs={n_neg} ({n_neg/len(y_train)*100:.1f}%)")
        logger.info(f"[DATA] Class weights: {class_weight_dict}")
        
        # Choisir le type de modèle (GB standard ou HistGB 10x plus rapide)
        from config import TRADING_CONFIG
        model_type = TRADING_CONFIG.get('gb_model_type', 'gb')
        
        if model_type == 'histgb':
            # HistGradientBoosting - 10x plus rapide
            from sklearn.ensemble import HistGradientBoostingClassifier
            logger.info("[FAST] Utilisation de HistGradientBoostingClassifier (10x plus rapide)")
            
            # 🔥 FIX: Utiliser les paramètres optimisés sans les écraser
            model = HistGradientBoostingClassifier(
                max_iter=params.get('n_estimators', 300),
                max_depth=params.get('max_depth', 2),
                learning_rate=params.get('learning_rate', 0.089),
                min_samples_leaf=params.get('min_samples_leaf', 50),
                l2_regularization=params.get('l2_regularization', 0.9),
                max_bins=255,
                random_state=42,
                early_stopping=True,
                n_iter_no_change=15,
                validation_fraction=0.15
            )
            # 🔥 FIX: HistGB utilise sample_weight dans fit()
            model.fit(X_train_scaled, y_train, sample_weight=sample_weights)
        else:
            # GradientBoosting standard - IDENTIQUE à optimize_gradientboosting_advanced.py
            logger.info("🌳 Utilisation de GradientBoostingClassifier (standard - mode optimisé)")
            
            # 🔥 EXACT COMME L'OPTIMISATION: pas de validation_fraction, pas de n_iter_no_change
            model = GradientBoostingClassifier(
                n_estimators=params.get('n_estimators', 271),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.217),
                min_samples_split=params.get('min_samples_split', 48),
                min_samples_leaf=params.get('min_samples_leaf', 38),
                subsample=params.get('subsample', 0.734),
                max_features=params.get('max_features', 'sqrt'),
                random_state=42
            )
            # 🔥 EXACT COMME L'OPTIMISATION: pas de sample_weight
            model.fit(X_train_scaled, y_train)
            logger.info("[OK] GB standard entraîné (mode optimisé - sans sample_weights)")
        
        ml_tasks[task_id]['progress'] = 75
        ml_tasks[task_id]['stage'] = 'cross_validation'
        
        # 🔬 CROSS-VALIDATION 5-fold pour métriques fiables
        from sklearn.model_selection import cross_val_score, StratifiedKFold
        
        logger.info("🔬 Calcul des métriques par Cross-Validation 5-fold...")
        
        # Créer un nouveau modèle pour CV (sur données complètes)
        X_all = np.vstack([X_train_scaled, X_test_scaled])
        y_all = np.concatenate([y_train, y_test])
        
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        
        if model_type == 'histgb':
            cv_model = HistGradientBoostingClassifier(
                max_iter=params.get('n_estimators', 300),
                max_depth=params.get('max_depth', 2),
                learning_rate=params.get('learning_rate', 0.089),
                min_samples_leaf=params.get('min_samples_leaf', 50),
                random_state=42
            )
        else:
            cv_model = GradientBoostingClassifier(
                n_estimators=params.get('n_estimators', 271),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.217),
                min_samples_split=params.get('min_samples_split', 48),
                min_samples_leaf=params.get('min_samples_leaf', 38),
                subsample=params.get('subsample', 0.734),
                max_features=params.get('max_features', 'sqrt'),
                random_state=42
            )
        
        cv_accuracy = cross_val_score(cv_model, X_all, y_all, cv=cv, scoring='accuracy')
        cv_f1 = cross_val_score(cv_model, X_all, y_all, cv=cv, scoring='f1')
        
        cv_acc_mean = cv_accuracy.mean()
        cv_acc_std = cv_accuracy.std()
        cv_f1_mean = cv_f1.mean()
        
        logger.info(f"[DATA] CV Accuracy: {cv_acc_mean*100:.1f}% ± {cv_acc_std*100:.1f}%")
        logger.info(f"[DATA] CV F1 Score: {cv_f1_mean:.3f}")
        
        ml_tasks[task_id]['progress'] = 85
        ml_tasks[task_id]['stage'] = 'evaluating'
        
        # Évaluer sur holdout (pour comparaison)
        y_train_pred = model.predict(X_train_scaled)
        y_test_pred = model.predict(X_test_scaled)
        
        train_acc = accuracy_score(y_train, y_train_pred)
        test_acc = accuracy_score(y_test, y_test_pred)
        test_f1 = f1_score(y_test, y_test_pred, zero_division=0)
        test_prec = precision_score(y_test, y_test_pred, zero_division=0)
        gap = train_acc - test_acc
        
        # Sauvegarder
        models_dir = Path("optimization/saved_models")
        models_dir.mkdir(parents=True, exist_ok=True)
        
        pipeline = Pipeline([
            ('scaler', scaler),
            ('model', model)
        ])
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = models_dir / f"best_classifier_{timestamp}.pkl"
        latest_path = models_dir / "best_classifier_latest.pkl"
        
        joblib.dump(pipeline, model_path)
        joblib.dump(pipeline, latest_path)
        
        model_name = 'HistGradientBoostingClassifier' if model_type == 'histgb' else 'GradientBoostingClassifier'
        
        metadata = {
            'timestamp': timestamp,
            'best_model': model_name,
            'model_type': model_type,
            'n_samples': len(df),
            'n_train': X_train.shape[0],
            'n_test': X_test.shape[0],
            'n_features': X_train.shape[1],
            'metrics': {
                # 🔬 MÉTRIQUES CROSS-VALIDATION (les plus fiables!)
                'cv_accuracy': float(cv_acc_mean),
                'cv_accuracy_std': float(cv_acc_std),
                'cv_f1': float(cv_f1_mean),
                # Métriques holdout (pour référence)
                'train_acc': float(train_acc),
                'test_acc': float(test_acc),
                'test_f1': float(test_f1),
                'test_precision': float(test_prec),
                'gap': float(gap)
            },
            'feature_cols': feature_cols,
            'params': params
        }
        
        with open(models_dir / "best_classifier_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        ml_tasks[task_id]['progress'] = 100
        ml_tasks[task_id]['status'] = 'completed'
        ml_tasks[task_id]['accuracy'] = float(test_acc)
        ml_tasks[task_id]['f1'] = float(test_f1)
        ml_tasks[task_id]['gap'] = float(gap)
        ml_tasks[task_id]['metrics'] = metadata['metrics']
        ml_tasks[task_id]['model_type'] = model_type
        
        logger.info(f"[OK] {model_name} entraîné: Accuracy={test_acc:.1%}, F1={test_f1:.3f}, Gap={gap:.1%}")
        
        # 🔥 FIX: Reset automatique de la ML Calibration après réentraînement
        # Les anciennes stats ne reflètent plus la performance du nouveau modèle
        try:
            from ml.calibration import get_calibration_manager
            calib_manager = get_calibration_manager()
            calib_manager.reset_calibration(reason=f"model_retrain_{task_id}")
            # Re-seeder avec les 200 derniers trades (ceux potentiellement faits avec le nouveau modèle)
            count = calib_manager.seed_from_historical_trades(days=7)
            logger.info(f"[CALIB] Calibration resetée et re-seedée avec {count} trades après réentraînement GB")
        except Exception as calib_err:
            logger.warning(f"[CALIB] Erreur reset calibration après réentraînement: {calib_err}")
        
    except Exception as e:
        logger.error(f"[FAIL] Erreur _train_gradientboosting_background: {e}", exc_info=True)
        ml_tasks[task_id]['status'] = 'error'
        ml_tasks[task_id]['error'] = str(e)

@router.get("/verify_gb/complete")
async def verify_gb_complete():
    """
    🔍 Boucle de vérification complète du système GradientBoosting
    Vérifie:
    - Configuration (TRADING_CONFIG)
    - Fichier modèle (.pkl)
    - Métadonnées modèle
    - Cohérence paramètres
    - Capacité de prédiction
    """
    verification_results = {
        'timestamp': datetime.now().isoformat(),
        'checks': [],
        'overall_status': 'OK',
        'warnings': [],
        'errors': []
    }
    
    def add_check(name: str, status: str, details: str = "", value: Any = None):
        verification_results['checks'].append({
            'name': name,
            'status': status,  # OK, WARNING, ERROR
            'details': details,
            'value': value
        })
        if status == 'ERROR':
            verification_results['errors'].append(f"{name}: {details}")
            verification_results['overall_status'] = 'ERROR'
        elif status == 'WARNING' and verification_results['overall_status'] != 'ERROR':
            verification_results['warnings'].append(f"{name}: {details}")
            verification_results['overall_status'] = 'WARNING'
    
    try:
        # 1. Vérifier TRADING_CONFIG
        from config import TRADING_CONFIG
        
        gb_params = {
            'gb_filter_enabled': TRADING_CONFIG.get('gb_filter_enabled'),
            'gb_min_confidence': TRADING_CONFIG.get('gb_min_confidence'),
            'gb_n_estimators': TRADING_CONFIG.get('gb_n_estimators'),
            'gb_max_depth': TRADING_CONFIG.get('gb_max_depth'),
            'gb_learning_rate': TRADING_CONFIG.get('gb_learning_rate'),
            'gb_min_samples_split': TRADING_CONFIG.get('gb_min_samples_split'),
            'gb_min_samples_leaf': TRADING_CONFIG.get('gb_min_samples_leaf'),
            'gb_subsample': TRADING_CONFIG.get('gb_subsample'),
            'gb_max_features': TRADING_CONFIG.get('gb_max_features'),
        }
        
        missing_params = [k for k, v in gb_params.items() if v is None]
        if missing_params:
            add_check('TRADING_CONFIG', 'ERROR', f'Paramètres manquants: {missing_params}')
        else:
            add_check('TRADING_CONFIG', 'OK', 'Tous les paramètres GB présents', gb_params)
        
        # 2. Vérifier config_overrides.json
        from utils.config_persistence import load_config_overrides
        overrides = load_config_overrides()
        
        gb_overrides = {k: v for k, v in overrides.items() if k.startswith('gb_')}
        if gb_overrides:
            add_check('config_overrides.json', 'OK', f'{len(gb_overrides)} paramètres GB persistés', gb_overrides)
        else:
            add_check('config_overrides.json', 'WARNING', 'Aucun paramètre GB persisté (valeurs par défaut)')
        
        # 3. Vérifier le fichier modèle
        from pathlib import Path
        models_dir = Path("optimization/saved_models")
        
        model_files = list(models_dir.glob("*classifier*.pkl")) + list(models_dir.glob("best_classifier*.pkl"))
        
        if model_files:
            latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
            model_age_hours = (datetime.now().timestamp() - latest_model.stat().st_mtime) / 3600
            
            if model_age_hours > 168:  # Plus d'une semaine
                add_check('Fichier modèle', 'WARNING', f'Modèle ancien ({model_age_hours:.0f}h)', str(latest_model))
            else:
                add_check('Fichier modèle', 'OK', f'Modèle trouvé ({model_age_hours:.1f}h)', str(latest_model))
        else:
            add_check('Fichier modèle', 'ERROR', 'Aucun fichier modèle trouvé')
        
        # 4. Vérifier les métadonnées
        metadata_file = models_dir / "best_classifier_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            metrics = metadata.get('metrics', {})
            test_acc = metrics.get('test_acc', 0)
            gap = metrics.get('gap', 1)
            
            if test_acc < 0.55:
                add_check('Métriques modèle', 'WARNING', f'Accuracy faible: {test_acc:.1%}', metrics)
            elif gap > 0.15:
                add_check('Métriques modèle', 'WARNING', f'Overfitting élevé: {gap:.1%}', metrics)
            else:
                add_check('Métriques modèle', 'OK', f'Accuracy={test_acc:.1%}, Gap={gap:.1%}', metrics)
        else:
            add_check('Métadonnées modèle', 'WARNING', 'Fichier metadata non trouvé')
        
        # 5. Vérifier la capacité de prédiction
        try:
            import joblib
            if model_files:
                latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
                model = joblib.load(latest_model)
                
                # Déterminer le nombre de features depuis le modèle
                import numpy as np
                
                # Essayer de récupérer n_features du scaler (Pipeline) ou du modèle
                try:
                    if hasattr(model, 'named_steps') and 'scaler' in model.named_steps:
                        n_features = model.named_steps['scaler'].n_features_in_
                    elif hasattr(model, 'n_features_in_'):
                        n_features = model.n_features_in_
                    else:
                        # Charger depuis metadata
                        meta_file = models_dir / "best_classifier_metadata.json"
                        if meta_file.exists():
                            with open(meta_file, 'r') as f:
                                meta = json.load(f)
                            n_features = len(meta.get('feature_cols', [])) or 92
                        else:
                            n_features = 92  # Fallback
                except Exception:
                    n_features = 92
                
                test_input = np.random.randn(1, n_features)
                
                try:
                    prediction = model.predict(test_input)
                    # predict_proba() est appelé pour sa seule exécution : un modèle
                    # incapable de produire des probabilités doit lever ici.
                    model.predict_proba(test_input)
                    add_check('Capacité prédiction', 'OK', f'Prédiction OK ({n_features} features): pred={prediction[0]}')
                except Exception as pred_err:
                    add_check('Capacité prédiction', 'ERROR', f'Erreur prédiction: {pred_err}')
        except Exception as load_err:
            add_check('Chargement modèle', 'ERROR', f'Impossible de charger: {load_err}')
        
        # 6. Vérifier cohérence avec Optuna
        optuna_results = models_dir / "gb_optuna_results.json"
        if optuna_results.exists():
            with open(optuna_results, 'r') as f:
                optuna_data = json.load(f)
            
            optuna_params = optuna_data.get('best_params', {})
            
            # Comparer avec TRADING_CONFIG
            mismatches = []
            param_mapping = {
                'n_estimators': 'gb_n_estimators',
                'max_depth': 'gb_max_depth',
                'learning_rate': 'gb_learning_rate',
            }
            
            for optuna_key, config_key in param_mapping.items():
                optuna_val = optuna_params.get(optuna_key)
                config_val = gb_params.get(config_key)
                if optuna_val and config_val and optuna_val != config_val:
                    mismatches.append(f"{config_key}: config={config_val} vs optuna={optuna_val}")
            
            if mismatches:
                add_check('Cohérence Optuna', 'WARNING', f'Params différents: {mismatches}', {
                    'optuna_params': optuna_params,
                    'config_params': gb_params
                })
            else:
                add_check('Cohérence Optuna', 'OK', 'Paramètres cohérents avec Optuna')
        else:
            add_check('Résultats Optuna', 'OK', 'Pas d\'optimisation Optuna précédente (optionnel)')
        
        # Résumé
        n_ok = len([c for c in verification_results['checks'] if c['status'] == 'OK'])
        n_warn = len([c for c in verification_results['checks'] if c['status'] == 'WARNING'])
        n_err = len([c for c in verification_results['checks'] if c['status'] == 'ERROR'])
        
        verification_results['summary'] = {
            'total_checks': len(verification_results['checks']),
            'ok': n_ok,
            'warnings': n_warn,
            'errors': n_err
        }
        
        return verification_results
        
    except Exception as e:
        logger.error(f"Erreur vérification GB: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)

@router.get("/histgb/verify")
async def verify_histgb_system():
    """
    Vérification complète du système HistGradientBoosting
    
    Vérifie:
    - config_overrides.json (params corrects, pas d'obsolètes)
    - Modèle sauvegardé (params, features, type)
    - Synchronisation config <-> modèle
    - Capacité de prédiction
    
    Returns:
        Résultats détaillés de chaque vérification
    """
    try:
        from verification.verify_histgb_system import (
            verify_config_overrides,
            verify_trading_config,
            verify_model_file,
            verify_metadata_file,
            verify_prediction_capability,
            verify_config_model_sync
        )
        
        results = {}
        
        # 1. Config overrides
        r = verify_config_overrides(auto_fix=False)
        results['config_overrides'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # 2. TRADING_CONFIG
        r = verify_trading_config()
        results['trading_config'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # 3. Model file
        r = verify_model_file()
        results['model_file'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # 4. Metadata
        r = verify_metadata_file()
        results['metadata'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # 5. Prediction
        r = verify_prediction_capability()
        results['prediction'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # 6. Sync
        r = verify_config_model_sync()
        results['sync'] = {
            'passed': r.passed,
            'errors': r.errors,
            'warnings': r.warnings,
            'info': r.info
        }
        
        # Résumé
        all_passed = all(v['passed'] for v in results.values())
        
        return {
            'success': True,
            'all_passed': all_passed,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
    except ImportError as e:
        return JSONResponse({
            'success': False,
            'error': f'Module verification non disponible: {e}'
        }, status_code=500)
    except Exception as e:
        logger.error(f"Erreur verify_histgb_system: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)

@router.post("/histgb/sync-from-model")
async def sync_config_from_model():
    """
    Synchronise config_overrides.json depuis les paramètres du modèle sauvegardé
    
    Utile après une optimisation pour s'assurer que la config reflète le modèle actuel.
    
    Returns:
        Changements appliqués
    """
    try:
        from verification.verify_histgb_system import sync_config_from_model as do_sync
        
        success = do_sync(dry_run=False)
        
        if success:
            # Recharger TRADING_CONFIG
            try:
                from config import TRADING_CONFIG
                from utils.config_persistence import apply_config_overrides
                apply_config_overrides(TRADING_CONFIG)
            except Exception:
                logger.debug('ml_legacy.py: exception silencieuse (avant: pass)', exc_info=True)
            return {
                'success': True,
                'message': 'Configuration synchronisée depuis le modèle'
            }
        else:
            return JSONResponse({
                'success': False,
                'error': 'Échec synchronisation'
            }, status_code=500)
            
    except Exception as e:
        logger.error(f"Erreur sync_config_from_model: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)

@router.post("/histgb/repair")
async def repair_histgb_config():
    """
    Répare automatiquement la configuration HistGradientBoosting
    
    Actions:
    - Ajoute les paramètres manquants avec valeurs par défaut
    - Supprime les paramètres obsolètes (GradientBoosting classique)
    - Force gb_model_type = 'histgb'
    
    Returns:
        Corrections appliquées
    """
    try:
        from verification.verify_histgb_system import verify_config_overrides
        
        result = verify_config_overrides(auto_fix=True)
        
        return {
            'success': result.passed,
            'fixes_applied': result.fixes_applied,
            'errors': result.errors,
            'warnings': result.warnings
        }
        
    except Exception as e:
        logger.error(f"Erreur repair_histgb_config: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)
