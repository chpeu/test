"""
Feature Loader - Charge features depuis PostgreSQL
Source unique de vérité pour ML
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import logging
from typing import Optional, Dict, List
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_postgres_connection():
    """Connexion PostgreSQL depuis variables d'environnement"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'tradecursor'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
        raise


def get_trades_count(completed_only: bool = True) -> int:
    """
    Compte nombre de trades dans PostgreSQL
    
    Args:
        completed_only: Si True, compte seulement trades fermés
        
    Returns:
        Nombre de trades
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        if completed_only:
            query = "SELECT COUNT(*) as count FROM trades WHERE timestamp_exit IS NOT NULL"
        else:
            query = "SELECT COUNT(*) as count FROM trades"
        
        cursor.execute(query)
        result = cursor.fetchone()
        count = result['count'] if result else 0
        
        cursor.close()
        conn.close()
        
        logger.info(f"📊 Trades count: {count} (completed_only={completed_only})")
        return count
        
    except Exception as e:
        logger.error(f"❌ Erreur get_trades_count: {e}")
        return 0


def load_features_from_postgres(
    min_trades: int = 50,
    timeframe_days: int = 30,
    max_trades: Optional[int] = None,
    include_open_trades: bool = False
) -> pd.DataFrame:
    """
    Charge features depuis PostgreSQL via vue ml_features
    
    Args:
        min_trades: Nombre minimum de trades requis
        timeframe_days: Nombre de jours à charger
        max_trades: Limite maximum de trades (None = tous)
        include_open_trades: Inclure trades non fermés
        
    Returns:
        DataFrame avec features + target
        
    Raises:
        ValueError: Si pas assez de données
    """
    try:
        conn = get_postgres_connection()
        
        # Requête optimisée sur vue ml_features
        query = """
        SELECT 
            -- Identifiants
            scan_id,
            timestamp,
            symbol,
            
            -- Features 1m
            rsi_1m, rsi_prev_1m,
            macd_hist_1m, macd_hist_prev_1m,
            adx_1m, di_plus_1m, di_minus_1m, di_gap_1m,
            atr_pct_1m,
            ema_diff_pct_1m,
            volume_ratio_1m, volume_spike_1m,
            bb_width_1m, bb_distance_to_lower_1m, bb_distance_to_upper_1m,
            
            -- Features 5m
            rsi_5m, rsi_prev_5m,
            macd_hist_5m, macd_hist_prev_5m,
            adx_5m, di_plus_5m, di_minus_5m, di_gap_5m,
            atr_pct_5m,
            ema_diff_pct_5m,
            volume_ratio_5m, volume_spike_5m,
            bb_width_5m, bb_distance_to_lower_5m, bb_distance_to_upper_5m,
            
            -- Filtres qualité
            snr_passed_1m, snr_passed_5m,
            breakout_passed_1m, breakout_passed_5m,
            wick_passed_1m, wick_passed_5m,
            atr_optimal_passed_1m, atr_optimal_passed_5m,
            volume_filter_passed_1m, volume_filter_passed_5m,
            
            -- Labels ML
            is_opportunity,
            target_win,
            target_pnl
            
        FROM ml_features
        WHERE timestamp > NOW() - INTERVAL '%s days'
        """
        
        # Ajouter filtre trades fermés si nécessaire
        if not include_open_trades:
            query += " AND target_win IS NOT NULL"
        
        query += " ORDER BY timestamp DESC"
        
        # Ajouter limite si spécifiée
        if max_trades:
            query += f" LIMIT {max_trades}"
        
        # Charger dans DataFrame
        df = pd.read_sql(query, conn, params=(timeframe_days,))
        conn.close()
        
        logger.info(f"📊 Features chargées: {len(df)} rows depuis PostgreSQL")
        
        # Convertir toutes les colonnes numériques (gère TEXT stocké comme string)
        numeric_cols = [col for col in df.columns if col not in ['scan_id', 'timestamp', 'symbol', 'opportunity_direction']]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        logger.info(f"🔄 Conversion des types numériques effectuée")
        
        # Validation minimum
        if len(df) < min_trades:
            raise ValueError(
                f"❌ Pas assez de données: {len(df)}/{min_trades} trades requis"
            )
        
        # Nettoyer NaN
        df = df.dropna(subset=['target_win'])
        
        logger.info(f"✅ Features prêtes: {len(df)} rows, {len(df.columns)} features")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Erreur load_features_from_postgres: {e}")
        raise


def get_feature_statistics(timeframe_days: int = 30) -> Dict:
    """
    Statistiques sur les features disponibles
    
    Returns:
        Dict avec stats (count, missing, quality)
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        # Stats globales
        stats_query = """
        SELECT 
            COUNT(*) as total_scans,
            COUNT(CASE WHEN is_opportunity THEN 1 END) as opportunities,
            COUNT(target_win) as completed_trades,
            AVG(CASE WHEN target_win THEN 1.0 ELSE 0.0 END) as win_rate
        FROM ml_features
        WHERE timestamp > NOW() - INTERVAL '%s days'
        """
        
        cursor.execute(stats_query, (timeframe_days,))
        result = cursor.fetchone()
        
        stats = {
            'total_scans': result['total_scans'] if result else 0,
            'opportunities': result['opportunities'] if result else 0,
            'completed_trades': result['completed_trades'] if result else 0,
            'win_rate': float(result['win_rate']) if result and result['win_rate'] else 0.0,
            'timeframe_days': timeframe_days,
            'last_updated': datetime.now().isoformat()
        }
        
        cursor.close()
        conn.close()
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erreur get_feature_statistics: {e}")
        return {
            'total_scans': 0,
            'opportunities': 0,
            'completed_trades': 0,
            'win_rate': 0.0,
            'error': str(e)
        }


def get_ml_readiness() -> Dict:
    """
    Vérifie si ML est prêt pour chaque modèle
    
    Returns:
        Dict avec status de chaque modèle
    """
    trades_count = get_trades_count()
    
    return {
        'trades_count': trades_count,
        'exploratory': {
            'ready': trades_count >= 10,
            'min_required': 10,
            'confidence': 'exploratory' if trades_count >= 10 else None
        },
        'features': {
            'ready': trades_count >= 30,
            'min_required': 30,
            'confidence': 'low' if trades_count >= 30 else None
        },
        'xgboost': {
            'ready': trades_count >= 50,
            'min_required': 50,
            'optimal_required': 100,
            'confidence': 'low' if trades_count < 100 else 'medium',
            'warning': '⚠️ Performances optimales après 100 trades' if trades_count < 100 else None
        },
        'gru': {
            'ready': trades_count >= 200,
            'min_required': 200,
            'optimal_required': 500,
            'confidence': 'experimental' if trades_count < 500 else 'medium',
            'warning': '⚠️ GRU expérimental - Performances réelles après 500 trades' if trades_count < 500 else None
        },
        'ppo': {
            'ready': trades_count >= 500,
            'min_required': 500,
            'optimal_required': 1000,
            'confidence': 'exploration' if trades_count < 1000 else 'medium',
            'warning': '⚠️ Agent en apprentissage - NE PAS utiliser en production' if trades_count < 1000 else None
        }
    }
