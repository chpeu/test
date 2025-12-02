"""
ML Dashboard - Dashboard and exploratory analytics endpoints
Migrated from ml_legacy.py as part of Phase 5 modularization
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from typing import Optional

logger = logging.getLogger(__name__)

# Router for dashboard and analytics
router = APIRouter(prefix="/api/ml", tags=["ML Dashboard"])


@router.get("/dashboard/stats")
async def get_ml_dashboard_stats():
    """
    Stats globales ML pour dashboard
    - Progression collecte données
    - Qualité données
    - Modèles débloqués
    """
    try:
        from optimization.data.feature_loader import get_trades_count, get_ml_readiness, get_feature_statistics
        
        # Compter trades
        trades_count = get_trades_count(completed_only=True)
        
        # Readiness pour chaque modèle
        readiness = get_ml_readiness()
        
        # Stats features
        feature_stats = get_feature_statistics(timeframe_days=30)
        
        # Calculer progression
        milestones = {
            'exploratory': 10,
            'features': 30,
            'xgboost': 50,
            'gru': 200,
            'ppo': 500
        }
        
        # Next milestone
        next_milestone = None
        for name, threshold in milestones.items():
            if trades_count < threshold:
                next_milestone = {
                    'name': name,
                    'threshold': threshold,
                    'remaining': threshold - trades_count,
                    'progress_pct': (trades_count / threshold) * 100
                }
                break
        
        if next_milestone is None:
            next_milestone = {
                'name': 'production',
                'threshold': 1000,
                'remaining': max(0, 1000 - trades_count),
                'progress_pct': min(100, (trades_count / 1000) * 100)
            }
        
        return {
            'trades_count': trades_count,
            'target_trades': 500,
            'progress_pct': min(100, (trades_count / 500) * 100),
            'readiness': readiness,
            'next_milestone': next_milestone,
            'feature_stats': feature_stats,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_dashboard_stats: {e}", exc_info=True)
        return JSONResponse({
            'error': str(e),
            'trades_count': 0,
            'readiness': {}
        }, status_code=500)



@router.get("/dashboard/data_quality")
async def get_data_quality():
    """
    Analyse qualité des données
    - Complétude
    - Distribution win/loss
    - Missing values
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres, get_trades_count
        
        trades_count = get_trades_count()
        
        if trades_count < 10:
            return {
                'status': 'insufficient_data',
                'trades_count': trades_count,
                'message': 'Minimum 10 trades requis pour analyse qualité'
            }
        
        # Charger features
        df = load_features_from_postgres(min_trades=10, timeframe_days=30)
        
        # Distribution win/loss
        win_count = (df['target_win'] == True).sum()
        loss_count = (df['target_win'] == False).sum()
        win_rate = win_count / (win_count + loss_count) if (win_count + loss_count) > 0 else 0
        
        # 🔥 FIX: Exclure IDs, métadonnées et config de l'analyse de qualité
        exclude_from_quality = [
            'scan_id', 'timestamp', 'symbol',  # IDs et métadonnées
            'opportunity_direction', 'reject_reason_category',  # Catégorielles (non-numériques)
            'target_win', 'target_pnl', 'is_opportunity',  # Targets (pas des features)
            # Config parameters (variance nulle intentionnelle - paramètres fixes)
            'config_min_score_required', 'config_snr_threshold',
            'config_atr_min_1m', 'config_atr_max_1m',
            'config_atr_min_5m', 'config_atr_max_5m',
            'config_volume_multiplier', 'config_use_confluence',
            # Filtres booléens (variance naturellement faible - 0/1 seulement)
            'snr_passed_1m', 'snr_passed_5m',
            'breakout_passed_1m', 'breakout_passed_5m',
            'wick_passed_1m', 'wick_passed_5m',
            'atr_optimal_passed_1m', 'atr_optimal_passed_5m',
            'volume_filter_passed_1m', 'volume_filter_passed_5m',
        ]
        
        # Missing values (features uniquement)
        feature_cols = [col for col in df.columns if col not in exclude_from_quality]
        missing_pct = (df[feature_cols].isnull().sum() / len(df) * 100).to_dict()
        high_missing = {k: v for k, v in missing_pct.items() if v > 10}
        
        # Features avec variance (features uniquement)
        numeric_cols = [col for col in df.select_dtypes(include=['float64', 'int64']).columns 
                       if col not in exclude_from_quality]
        low_variance = []
        for col in numeric_cols:
            if df[col].std() < 0.01:
                low_variance.append(col)
        
        quality_score = 100
        if high_missing:
            quality_score -= len(high_missing) * 5
        if win_rate < 0.3 or win_rate > 0.7:
            quality_score -= 10
        if low_variance:
            quality_score -= len(low_variance) * 2
        
        return {
            'trades_count': len(df),
            'win_loss_distribution': {
                'wins': int(win_count),
                'losses': int(loss_count),
                'win_rate': float(win_rate),
                'balanced': bool(0.4 <= win_rate <= 0.6)
            },
            'missing_values': {
                'high_missing_features': high_missing,
                'total_features_with_missing': len([v for v in missing_pct.values() if v > 0])
            },
            'variance': {
                'low_variance_features': low_variance,
                'count': len(low_variance)
            },
            'quality_score': max(0, min(100, quality_score)),
            'status': 'good' if quality_score >= 80 else 'acceptable' if quality_score >= 60 else 'poor'
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_data_quality: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)



@router.get("/dashboard/ml_trades_count")
async def get_ml_trades_count():
    """
    🔢 Retourne le nombre de trades utilisables pour ML après filtrage COMPLET:
    - Exclure trades manuels (exit_reason = 'MANUAL')
    - Exclure trades avec configs différentes de la CONFIG ACTUELLE
    
    🔥 FILTRE EXHAUSTIF sur TOUS les paramètres influençant:
    - Validation des setups (min_score, snr, volume, confluence, ATR, patterns, etc.)
    - Prise de position (filtres additionnels)
    - Clôture (TP/SL via config_snapshot JSONB)
    
    Le compteur se met à jour dynamiquement quand l'utilisateur change les paramètres.
    """
    try:
        from optimization.data.feature_loader import get_sqlalchemy_engine
        from config import TRADING_CONFIG
        import pandas as pd
        
        engine = get_sqlalchemy_engine()
        
        # ═══════════════════════════════════════════════════════════════════
        # 1. LIRE TOUS LES PARAMÈTRES DE LA CONFIG ACTUELLE
        # ═══════════════════════════════════════════════════════════════════
        
        # Paramètres de validation des setups (colonnes config_*)
        current_config = {
            # Paramètres de base (validation setup)
            'min_score': float(TRADING_CONFIG.get('min_score_required', 6.5)),
            'snr_threshold': float(TRADING_CONFIG.get('snr_threshold', 0.15)),
            'volume_mult': float(TRADING_CONFIG.get('volume_multiplier', 0.95)),
            'use_confluence': bool(TRADING_CONFIG.get('use_confluence', False)),
            
            # ATR optimal
            'atr_min_1m': float(TRADING_CONFIG.get('optimal_atr_min_1m', 0.12)),
            'atr_max_1m': float(TRADING_CONFIG.get('optimal_atr_max_1m', 0.75)),
            'atr_min_5m': float(TRADING_CONFIG.get('optimal_atr_min_5m', 0.22)),
            'atr_max_5m': float(TRADING_CONFIG.get('optimal_atr_max_5m', 1.4)),
            
            # Filtres additionnels (si colonnes remplies)
            'use_anti_whipsaw': bool(TRADING_CONFIG.get('use_anti_whipsaw', False)),
            'use_candle_close': bool(TRADING_CONFIG.get('use_candle_close', False)),
            'use_cooldown': bool(TRADING_CONFIG.get('use_cooldown', False)),
            'use_momentum_continuity': bool(TRADING_CONFIG.get('use_momentum_continuity', False)),
            'use_retest_confirmation': bool(TRADING_CONFIG.get('use_retest_confirmation', False)),
            
            # TP/SL (depuis config_snapshot JSONB)
            'tp_sl_mode': str(TRADING_CONFIG.get('tp_sl_mode', 'FIXE')),
            'tp_percent': float(TRADING_CONFIG.get('tp_percent', 0.5)),
            'sl_percent': float(TRADING_CONFIG.get('sl_percent', 0.2)),
            
            # Patterns techniques (depuis config_snapshot JSONB) - flags + seuils
            'use_breakout': bool(TRADING_CONFIG.get('use_breakout', True)),
            'breakout_threshold': float(TRADING_CONFIG.get('breakout_threshold', 0.25)),
            'use_snr': bool(TRADING_CONFIG.get('use_snr', True)),
            'snr_threshold': float(TRADING_CONFIG.get('snr_threshold', 0.15)),
            'use_wick': bool(TRADING_CONFIG.get('use_wick', False)),
            'wick_ratio_max': float(TRADING_CONFIG.get('wick_ratio_max', 4.5)),
            'use_divergence': bool(TRADING_CONFIG.get('use_divergence', True)),
            'di_gap_min': float(TRADING_CONFIG.get('di_gap_min', 4.0)),
            'di_gap_adx_threshold': float(TRADING_CONFIG.get('di_gap_adx_threshold', 25.0)),
        }
        
        # ═══════════════════════════════════════════════════════════════════
        # 2. COMPTER TOUS LES TRADES
        # ═══════════════════════════════════════════════════════════════════
        total_trades = int(pd.read_sql("SELECT COUNT(*) as cnt FROM trades", engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 3. COMPTER TRADES NON-MANUELS
        # ═══════════════════════════════════════════════════════════════════
        non_manual = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
        """, engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 4. CONSTRUIRE LE FILTRE COMPLET (identique à l'entraînement ML)
        # ═══════════════════════════════════════════════════════════════════
        # 🔥 Utiliser la fonction centralisée pour garantir la cohérence
        from optimization.data.feature_loader import build_config_filter_conditions
        # Note: On utilise la table trades directement, donc inclure exit_reason
        conditions = build_config_filter_conditions(for_trades_table=True)
        
        clean_query = f"SELECT COUNT(*) as cnt FROM trades WHERE {' AND '.join(conditions)}"
        clean_count = int(pd.read_sql(clean_query, engine).iloc[0]['cnt'])
        
        # ═══════════════════════════════════════════════════════════════════
        # 5. BREAKDOWN PAR CONFIG (pour debug)
        # ═══════════════════════════════════════════════════════════════════
        config_query = """
            SELECT 
                config_min_score_required,
                config_snr_threshold,
                config_volume_multiplier,
                config_use_confluence,
                COUNT(*) as cnt
            FROM trades
            WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
            GROUP BY config_min_score_required, config_snr_threshold, config_volume_multiplier, config_use_confluence
            ORDER BY cnt DESC
            LIMIT 5
        """
        config_df = pd.read_sql(config_query, engine)
        
        config_breakdown = []
        if len(config_df) > 0:
            for _, row in config_df.iterrows():
                min_score = row['config_min_score_required']
                snr_thresh = row['config_snr_threshold']
                vol_mult = row['config_volume_multiplier']
                confluence = row['config_use_confluence']
                
                is_current = (
                    pd.notna(min_score) and abs(float(min_score) - current_config['min_score']) < 0.1 and
                    pd.notna(snr_thresh) and abs(float(snr_thresh) - current_config['snr_threshold']) < 0.02 and
                    pd.notna(vol_mult) and abs(float(vol_mult) - current_config['volume_mult']) < 0.05 and
                    pd.notna(confluence) and confluence == current_config['use_confluence']
                )
                
                config_breakdown.append({
                    'min_score': float(min_score) if pd.notna(min_score) else None,
                    'snr_threshold': float(snr_thresh) if pd.notna(snr_thresh) else None,
                    'volume_mult': float(vol_mult) if pd.notna(vol_mult) else None,
                    'confluence': bool(confluence) if pd.notna(confluence) else None,
                    'count': int(row['cnt']),
                    'is_current': bool(is_current)
                })
        
        engine.dispose()
        
        # ═══════════════════════════════════════════════════════════════════
        # 6. RETOURNER LE RÉSULTAT
        # ═══════════════════════════════════════════════════════════════════
        return {
            'total_trades': total_trades,
            'manual_excluded': total_trades - non_manual,
            'non_manual_trades': non_manual,
            'config_filtered_trades': clean_count,
            'different_config_excluded': non_manual - clean_count,
            'current_config': current_config,
            'config_breakdown': config_breakdown,
            'filters_applied': {
                'setup_validation': ['min_score', 'snr_threshold', 'volume_mult', 'confluence', 'atr_1m', 'atr_5m'],
                'additional_filters': ['anti_whipsaw', 'candle_close', 'cooldown', 'momentum', 'retest'],
                'tp_sl': ['tp_sl_mode', 'tp_percent', 'sl_percent'],
                'patterns_techniques': ['use_breakout', 'breakout_threshold', 'use_snr', 'snr_threshold', 'use_wick', 'wick_ratio_max', 'use_divergence', 'di_gap_min', 'di_gap_adx_threshold']
            },
            'message': f"✅ {clean_count} trades avec config actuelle (sur {total_trades} total)"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_ml_trades_count: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== EXPLORATORY ==========


@router.get("/exploratory/performance")
async def get_performance_analysis(
    group_by: str = Query('hour', regex='^(hour|day|symbol|direction)$'),
    timeframe_days: int = 30
):
    """
    Analyse performance par contexte
    - Par heure de la journée
    - Par jour de la semaine
    - Par symbole
    - Par direction
    """
    try:
        from optimization.data.feature_loader import load_features_from_postgres
        
        df = load_features_from_postgres(min_trades=10, timeframe_days=timeframe_days)
        
        # Ajouter colonnes temporelles si pas déjà présentes
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.day_name()
        
        # Grouper selon paramètre
        if group_by == 'hour' and 'hour' in df.columns:
            grouped = df.groupby('hour')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        elif group_by == 'day' and 'day_of_week' in df.columns:
            grouped = df.groupby('day_of_week')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        elif group_by == 'symbol' and 'symbol' in df.columns:
            grouped = df.groupby('symbol')['target_win'].agg(['sum', 'count', 'mean'])
            grouped.columns = ['wins', 'total', 'win_rate']
            results = grouped.to_dict('index')
            
        else:
            results = {}
        
        return {
            'group_by': group_by,
            'timeframe_days': timeframe_days,
            'results': results,
            'total_trades': len(df)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_performance_analysis: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


# ========== MODELS ==========


logger.info("✅ ML dashboard router initialized (4 routes)")
