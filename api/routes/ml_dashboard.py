"""
ML Dashboard - Dashboard and exploratory analytics endpoints
Migrated from ml_legacy.py as part of Phase 5 modularization
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from typing import Optional

logger = logging.getLogger(__name__)

# Router for dashboard and analytics
router = APIRouter(prefix="/api/ml", tags=["ML Dashboard"])


def get_ml_dashboard() -> dict:
    """Compatibilité tests: dashboard ML simplifié."""
    return {
        "status": "ok",
        "stats": {},
    }


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
            
            # 🔥 TP/SL EXCLUS - n'affectent pas la prédiction ML (gestion post-entrée uniquement)
            # Le modèle prédit si un signal d'entrée est bon, pas comment on gère la position après
            
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
        # 3. NOUVEAUX FILTRES ML STRICTS (11/12/2025)
        # ═══════════════════════════════════════════════════════════════════
        
        # 3a. Exclure DRY-RUN (uniquement LIVE)
        dryrun_excluded = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE is_live_trade = false OR is_live_trade IS NULL
        """, engine).iloc[0]['cnt'])
        
        # 3b. Exclure non-ATR (uniquement mode ATR)
        non_atr_excluded = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE is_live_trade = true AND (tp_sl_mode != 'ATR' OR tp_sl_mode IS NULL)
        """, engine).iloc[0]['cnt'])
        
        # 3c. Exclure MANUAL + STAGNATION
        bad_exits_excluded = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE is_live_trade = true AND tp_sl_mode = 'ATR' 
              AND exit_reason IN ('MANUAL', 'STAGNATION')
        """, engine).iloc[0]['cnt'])
        
        # Compteur après filtres de base (LIVE + ATR + exits propres)
        base_filtered = int(pd.read_sql("""
            SELECT COUNT(*) as cnt FROM trades 
            WHERE is_live_trade = true 
              AND tp_sl_mode = 'ATR'
              AND (exit_reason IS NULL OR exit_reason NOT IN ('MANUAL', 'STAGNATION'))
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
        # 6. RETOURNER LE RÉSULTAT (simplifié - sans filtre config)
        # ═══════════════════════════════════════════════════════════════════
        return {
            'total_trades': total_trades,
            # 🔥 Compteurs stricts (11/12/2025)
            'dryrun_excluded': dryrun_excluded,
            'non_atr_excluded': non_atr_excluded,
            'bad_exits_excluded': bad_exits_excluded,
            'config_filtered_trades': base_filtered,  # = clean_count sans filtre config
            'current_config': current_config,
            'filters_applied': {
                'strict_filters': ['LIVE only', 'ATR mode only', 'No MANUAL/STAGNATION'],
            },
            'message': f"✅ {base_filtered} trades ML utilisables (LIVE + ATR + exits propres)"
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


# ========== PHASE 2A: CORRELATION ANALYTICS ==========


@router.get("/analytics/correlations")
async def get_correlation_analytics(
    days: int = Query(7, ge=1, le=90, description="Nombre de jours à analyser")
):
    """
    🔥 PHASE 2A: Analyse des corrélations Session/Régime/Performance.
    
    Retourne:
    - Performance par session (ASIA, EUROPE, US, NIGHT)
    - Performance par régime local (LOW, MEDIUM, HIGH)
    - Performance par heure UTC
    - Performance par exit_reason
    - Distribution des régimes optimaux (What-If)
    - Suggestions d'optimisation
    """
    try:
        from core.analysis.correlation_engine import get_correlation_engine
        
        engine = get_correlation_engine()
        report = engine.get_full_analysis_report(days)
        
        return {
            'status': 'success',
            'period_days': days,
            'generated_at': report.get('generated_at'),
            'by_session': report.get('by_session', []),
            'by_local_regime': report.get('by_local_regime', []),
            'by_hour': report.get('by_hour', []),
            'by_exit_reason': report.get('by_exit_reason', []),
            'optimal_regime_distribution': report.get('optimal_regime_distribution', {}),
            'suggestions': report.get('suggestions', [])
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_correlation_analytics: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


@router.get("/analytics/suggestions")
async def get_optimization_suggestions(
    days: int = Query(7, ge=1, le=90, description="Nombre de jours à analyser")
):
    """
    Retourne uniquement les suggestions d'optimisation prioritaires.
    """
    try:
        from core.analysis.correlation_engine import get_correlation_engine
        
        engine = get_correlation_engine()
        suggestions = engine.generate_suggestions(days)
        
        return {
            'status': 'success',
            'period_days': days,
            'suggestions': [s.__dict__ for s in suggestions]
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur get_optimization_suggestions: {e}", exc_info=True)
        return JSONResponse({'error': str(e)}, status_code=500)


def simulate_optimal_performance(cursor, trade_id_texts=None):
    """
    Simule les performances si les paramètres ML optimaux étaient appliqués.
    Utilise les paramètres RÉELS utilisés par chaque trade (stockés en DB).
    """
    import json
    import os
    from collections import defaultdict
    
    try:
        # Récupérer les trades avec leurs paramètres utilisés
        query = """
            SELECT 
                pea.*,
                t.entry_price,
                t.direction,
                t.symbol
            FROM trade_post_exit_analysis pea
            JOIN trades t ON t.id::text = pea.trade_id::text
            WHERE 
                pea.ml_optimal_sl_pct IS NOT NULL
                AND pea.post_exit_mfe_pct IS NOT NULL
                AND pea.realized_pnl_pct IS NOT NULL
        """

        if trade_id_texts:
            query += " AND pea.trade_id::text = ANY(%s)"
            cursor.execute(query, (trade_id_texts,))
        else:
            cursor.execute(query)
        
        trades = cursor.fetchall()
        if not trades:
            return None
        
        # Statistiques actuelles
        current_stats = {
            'total_trades': len(trades),
            'winning_trades': len([t for t in trades if float(t['realized_pnl_pct'] or 0) > 0]),
            'total_pnl': sum(float(t['realized_pnl_pct'] or 0) for t in trades),
            'total_efficiency': sum(float(t['exit_efficiency_pct'] or 0) for t in trades),
            'total_regret': sum(float(t['regret_pct'] or 0) for t in trades),
        }
        
        # Simulation avec paramètres optimaux
        optimal_stats = {
            'total_trades': len(trades),
            'winning_trades': 0,
            'total_pnl': 0,
            'total_efficiency': 0,
            'total_regret': 0,
        }
        
        # Grouper les trades par configuration utilisée
        config_groups = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0, 'optimal_pnl': 0})
        
        for trade in trades:
            realized_pnl = float(trade['realized_pnl_pct'] or 0)
            post_exit_mfe = float(trade['post_exit_mfe_pct'] or 0)
            current_efficiency = float(trade['exit_efficiency_pct'] or 50)
            
            # Paramètres ML optimaux calculés
            optimal_sl = float(trade['ml_optimal_sl_pct'] or 0.15)
            optimal_trailing = float(trade['ml_optimal_trailing_trigger'] or 0.15)
            optimal_be = float(trade['ml_optimal_be_trigger'] or 0.15)
            optimal_trailing_dist = float(trade.get('ml_optimal_trailing_distance') or 0.10)
            
            # 🔥 UTILISER LES PARAMÈTRES RÉELS DU TRADE (pas la config actuelle)
            used_sl = float(trade['used_sl_pct'] or 0.15)
            used_be = float(trade['used_be_trigger'] or 0.20)
            used_trailing = float(trade['used_trailing_trigger'] or 0.20)
            used_trailing_dist = float(trade.get('used_trailing_min_distance') or 0.10)
            
            # Créer une clé de configuration pour grouper
            config_key = f"SL:{used_sl:.2f}% BE:{used_be:.2f}% TR:{used_trailing:.2f}% Dist:{used_trailing_dist:.2f}%"
            
            # Simulation
            if realized_pnl > 0:
                potential_gain = 0
                # Amélioration si BE/trailing trigger plus bas OU distance trailing plus serrée
                if post_exit_mfe > 0 and (optimal_be < used_be or optimal_trailing < used_trailing or optimal_trailing_dist < used_trailing_dist):
                    # Bonus supplémentaire si la distance trailing est optimisée
                    distance_bonus = 0.1 if optimal_trailing_dist < used_trailing_dist else 0
                    potential_gain = post_exit_mfe * (0.6 + distance_bonus)
                optimal_pnl = realized_pnl + potential_gain
            else:
                if post_exit_mfe > abs(realized_pnl) and optimal_sl > used_sl:
                    optimal_pnl = post_exit_mfe * 0.5
                elif post_exit_mfe > 0 and optimal_sl > used_sl:
                    recovery = min(post_exit_mfe * 0.7, abs(realized_pnl) * 0.3)
                    optimal_pnl = realized_pnl + recovery
                else:
                    optimal_pnl = realized_pnl * 0.95
            
            if optimal_pnl > 0:
                optimal_stats['winning_trades'] += 1
            
            optimal_stats['total_pnl'] += optimal_pnl
            
            # Efficiency optimale
            pnl_improvement = optimal_pnl - realized_pnl
            if optimal_pnl > realized_pnl:
                improvement_ratio = pnl_improvement / max(abs(realized_pnl), 0.01)
                efficiency_boost = min(improvement_ratio * 20, 30)
                optimal_efficiency = min(100, current_efficiency + efficiency_boost)
            else:
                optimal_efficiency = current_efficiency
            
            optimal_stats['total_efficiency'] += optimal_efficiency
            
            # Regret optimal
            if optimal_pnl > 0:
                remaining_mfe = max(0, post_exit_mfe - pnl_improvement)
                optimal_stats['total_regret'] += remaining_mfe
            else:
                optimal_stats['total_regret'] += max(0, post_exit_mfe - pnl_improvement)
            
            # Grouper par config
            config_groups[config_key]['trades'] += 1
            if realized_pnl > 0:
                config_groups[config_key]['wins'] += 1
            config_groups[config_key]['pnl'] += realized_pnl
            config_groups[config_key]['optimal_pnl'] += optimal_pnl
        
        # Calculer les résultats
        n = current_stats['total_trades']
        
        # Trouver les configs utilisées (uniques)
        unique_configs = []
        for config_key, stats in sorted(config_groups.items(), key=lambda x: -x[1]['trades']):
            winrate = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
            improvement = stats['optimal_pnl'] - stats['pnl']
            unique_configs.append({
                'config': config_key,
                'trades': stats['trades'],
                'winrate': round(winrate, 1),
                'pnl': round(stats['pnl'], 2),
                'optimal_pnl': round(stats['optimal_pnl'], 2),
                'improvement': round(improvement, 2)
            })
        
        current_total_pnl = float(current_stats['total_pnl'] or 0)
        optimal_total_pnl = float(optimal_stats['total_pnl'] or 0)

        gain_multiplier = None
        if current_total_pnl > 0:
            gain_multiplier = round(optimal_total_pnl / current_total_pnl, 2)

        return {
            'unique_configs': unique_configs,
            'configs_count': len(unique_configs),
            'current_winrate': round(current_stats['winning_trades'] / n * 100, 1),
            'optimal_winrate': round(optimal_stats['winning_trades'] / n * 100, 1),
            'winrate_improvement': round((optimal_stats['winning_trades'] - current_stats['winning_trades']) / n * 100, 1),
            'current_pnl_total': round(current_stats['total_pnl'], 2),
            'optimal_pnl_total': round(optimal_stats['total_pnl'], 2),
            'pnl_improvement': round(optimal_stats['total_pnl'] - current_stats['total_pnl'], 2),
            'current_pnl_avg': round(current_stats['total_pnl'] / n, 3),
            'optimal_pnl_avg': round(optimal_stats['total_pnl'] / n, 3),
            'current_efficiency': round(current_stats['total_efficiency'] / n, 1),
            'optimal_efficiency': round(optimal_stats['total_efficiency'] / n, 1),
            'efficiency_improvement': round((optimal_stats['total_efficiency'] - current_stats['total_efficiency']) / n, 1),
            'current_regret': round(current_stats['total_regret'] / n, 3),
            'optimal_regret': round(optimal_stats['total_regret'] / n, 3),
            'regret_improvement': round((optimal_stats['total_regret'] - current_stats['total_regret']) / n, 3),
            'gain_multiplier': gain_multiplier
        }
        
    except Exception as e:
        logger.error(f"⚠️ Erreur simulation: {e}")
        return None


@router.post("/analytics/post-exit/analyze")
async def api_post_exit_analyze(min_trades: int = 10, force: bool = False):
    """
    Exécute l'analyse post-exit et calcule les ML targets.
    """
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        from psycopg2.extras import RealDictCursor
        
        datalogger = get_pg_datalogger()
        if not datalogger or not datalogger.enabled:
            return JSONResponse({
                "success": False,
                "error": "PostgreSQL DataLogger non disponible"
            })
        
        conn = datalogger._get_connection()
        if not conn:
            return JSONResponse({
                "success": False,
                "error": "Connexion PostgreSQL non disponible"
            })
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Compter les trades disponibles
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM trade_post_exit_analysis
                WHERE sample_count > 10
            """)
            total_trades = cursor.fetchone()['count']

            if total_trades < min_trades:
                return JSONResponse({
                    "success": False,
                    "error": f"Pas assez de trades ({total_trades}/{min_trades} minimum)",
                    "total_trades": total_trades,
                    "min_required": min_trades
                })

            cursor.execute("""
                SELECT trade_id::text as trade_id
                FROM trade_post_exit_analysis
                WHERE sample_count > 10
                ORDER BY exit_timestamp DESC
                LIMIT %s
            """, (min_trades,))
            trade_id_texts = [r['trade_id'] for r in cursor.fetchall()]

            # 2. Récupérer les trades à analyser
            conditions = ["pea.trade_id::text = ANY(%s)"]
            params = [trade_id_texts]

            if not force:
                conditions.append(
                    "(pea.ml_optimal_sl_pct IS NULL "
                    "OR (pea.ml_optimal_trailing_trigger IS NULL AND COALESCE(pea.realized_pnl_pct, 0) > 0) "
                    "OR pea.ml_optimal_be_trigger IS NULL "
                    "OR pea.ml_optimal_trailing_distance IS NULL "
                    "OR pea.ml_should_use_partial IS NULL)"
                )

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            cursor.execute(f"""
                SELECT 
                    pea.*,
                    t.entry_price, 
                    t.direction, 
                    t.symbol
                FROM trade_post_exit_analysis pea
                JOIN trades t ON t.id::text = pea.trade_id::text
                {where_clause}
                ORDER BY pea.exit_timestamp DESC
            """, tuple(params))
            rows = cursor.fetchall()
            
            # 3. Calculer les targets pour chaque trade
            updated_count = 0
            
            def calculate_ml_targets(post_exit_data):
                """Calcule les targets ML optimaux"""
                targets = {}
                realized_pnl = float(post_exit_data.get('realized_pnl_pct') or 0)
                post_exit_mae = float(post_exit_data.get('post_exit_mae_pct') or 0)
                post_exit_mfe = float(post_exit_data.get('post_exit_mfe_pct') or 0)
                used_sl = float(post_exit_data.get('used_sl_pct') or 0.15)
                would_have_hit_tp = post_exit_data.get('would_have_hit_original_tp', False)
                
                # SL optimal
                if realized_pnl > 0:
                    targets['ml_optimal_sl_pct'] = max(used_sl, abs(post_exit_mae) * 1.1 + 0.02)
                else:
                    targets['ml_optimal_sl_pct'] = used_sl * 0.9
                targets['ml_optimal_sl_pct'] = max(0.08, min(0.50, targets['ml_optimal_sl_pct']))
                
                # Trailing trigger optimal
                if realized_pnl <= 0:
                    targets['ml_optimal_trailing_trigger'] = None
                elif post_exit_mfe > 0.5:
                    targets['ml_optimal_trailing_trigger'] = realized_pnl * 0.8 if realized_pnl != 0 else 0.20
                else:
                    targets['ml_optimal_trailing_trigger'] = realized_pnl * 0.5 if realized_pnl != 0 else 0.15
                if targets['ml_optimal_trailing_trigger'] is not None:
                    targets['ml_optimal_trailing_trigger'] = max(0.10, min(0.50, targets['ml_optimal_trailing_trigger']))
                
                # BE trigger optimal
                if realized_pnl > 0:
                    targets['ml_optimal_be_trigger'] = realized_pnl * 0.4
                else:
                    targets['ml_optimal_be_trigger'] = 0.15
                targets['ml_optimal_be_trigger'] = max(0.10, min(0.40, targets['ml_optimal_be_trigger']))

                used_trailing_dist = float(post_exit_data.get('used_trailing_min_distance') or 0.10)
                if realized_pnl > 0 and post_exit_mfe > 0.05:
                    targets['ml_optimal_trailing_distance'] = max(abs(post_exit_mae) * 1.2, used_trailing_dist * 0.8)
                else:
                    targets['ml_optimal_trailing_distance'] = used_trailing_dist
                targets['ml_optimal_trailing_distance'] = max(0.03, min(0.30, targets['ml_optimal_trailing_distance']))
                
                # Should use partial TP
                targets['ml_should_use_partial'] = would_have_hit_tp
                
                return targets

            update_query = """
                UPDATE trade_post_exit_analysis
                SET 
                    ml_optimal_sl_pct = %s,
                    ml_optimal_trailing_trigger = %s,
                    ml_optimal_be_trigger = %s,
                    ml_optimal_trailing_distance = %s,
                    ml_should_use_partial = %s
                WHERE trade_id = %s
            """ if force else """
                UPDATE trade_post_exit_analysis
                SET 
                    ml_optimal_sl_pct = COALESCE(ml_optimal_sl_pct, %s),
                    ml_optimal_trailing_trigger = COALESCE(ml_optimal_trailing_trigger, %s),
                    ml_optimal_be_trigger = COALESCE(ml_optimal_be_trigger, %s),
                    ml_optimal_trailing_distance = COALESCE(ml_optimal_trailing_distance, %s),
                    ml_should_use_partial = COALESCE(ml_should_use_partial, %s)
                WHERE trade_id = %s
            """
            
            for row in rows:
                post_exit_data = dict(row)
                targets = calculate_ml_targets(post_exit_data)
                
                cursor.execute(update_query, (
                    targets['ml_optimal_sl_pct'],
                    targets['ml_optimal_trailing_trigger'],
                    targets['ml_optimal_be_trigger'],
                    targets['ml_optimal_trailing_distance'],
                    targets['ml_should_use_partial'],
                    row['trade_id']
                ))
                updated_count += 1
            
            conn.commit()
            
            # 4. Statistiques globales
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    AVG(exit_efficiency_pct) as avg_efficiency,
                    AVG(regret_pct) as avg_regret,
                    COUNT(CASE WHEN exit_timing_grade IN ('A+', 'A') THEN 1 END) as excellent_exits,
                    AVG(ml_optimal_sl_pct) as avg_optimal_sl,
                    AVG(ml_optimal_trailing_trigger) as avg_optimal_trailing,
                    AVG(ml_optimal_be_trigger) as avg_optimal_be,
                    AVG(ml_optimal_trailing_distance) as avg_optimal_trailing_distance,
                    COUNT(CASE WHEN ml_should_use_partial = true THEN 1 END) as should_use_partial_count
                FROM trade_post_exit_analysis
                WHERE trade_id::text = ANY(%s)
                    AND sample_count > 10
            """, (trade_id_texts,))
            
            stats = cursor.fetchone()
            
            # 5. Distribution des grades
            cursor.execute("""
                SELECT 
                    exit_timing_grade,
                    COUNT(*) as count
                FROM trade_post_exit_analysis
                WHERE trade_id::text = ANY(%s)
                    AND sample_count > 10
                GROUP BY exit_timing_grade
                ORDER BY exit_timing_grade
            """, (trade_id_texts,))
            
            grade_distribution = {}
            for row in cursor.fetchall():
                grade = row['exit_timing_grade'] or 'N/A'
                count = row['count']
                pct = count / stats['total_trades'] * 100 if stats['total_trades'] > 0 else 0
                grade_distribution[grade] = {
                    'count': count,
                    'percentage': round(pct, 1)
                }
            
            # 6. 🔥 SIMULATION avec paramètres optimaux
            simulation = simulate_optimal_performance(cursor, trade_id_texts)
            
            return {
                "success": True,
                "updated_count": updated_count,
                "total_trades": stats['total_trades'],
                "avg_efficiency": round(float(stats['avg_efficiency'] or 0), 1),
                "avg_regret": round(float(stats['avg_regret'] or 0), 2),
                "excellent_exit_rate": round(stats['excellent_exits'] / stats['total_trades'] * 100, 1) if stats['total_trades'] > 0 else 0,
                "avg_optimal_sl": round(float(stats['avg_optimal_sl'] or 0), 3),
                "avg_optimal_trailing": round(float(stats['avg_optimal_trailing'] or 0), 3),
                "avg_optimal_be": round(float(stats['avg_optimal_be'] or 0), 3),
                "avg_optimal_trailing_distance": round(float(stats['avg_optimal_trailing_distance'] or 0), 3),
                "should_use_partial_rate": round(stats['should_use_partial_count'] / stats['total_trades'] * 100, 1) if stats['total_trades'] > 0 else 0,
                "grade_distribution": grade_distribution,
                "simulation": simulation
            }
            
        finally:
            datalogger._return_connection(conn)
            
    except Exception as e:
        logger.error(f"❌ Erreur /api/analytics/post-exit/analyze: {e}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


logger.info("✅ ML dashboard router initialized (8 routes)")
