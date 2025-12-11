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
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)


def build_config_filter_conditions(for_trades_table: bool = True, use_alias: bool = False) -> List[str]:
    """
    Construit les conditions de filtrage sur la configuration actuelle.
    Utilisé par le compteur ML et par tous les modèles pour garantir la cohérence.
    
    Args:
        for_trades_table: Si True, inclut le filtre exit_reason (table trades).
                         Si False, l'exclut (vues ml_features qui excluent déjà les trades manuels).
        use_alias: Si True, préfixe les colonnes avec 't.' pour jointures.
    
    Returns:
        Liste de conditions SQL WHERE
    """
    try:
        # Importer la config actuelle
        from config import TRADING_CONFIG
        
        # Paramètres de base (validation setup)
        min_score = float(TRADING_CONFIG.get('min_score_required', 6.5))
        snr_threshold = float(TRADING_CONFIG.get('snr_threshold', 0.15))
        volume_mult = float(TRADING_CONFIG.get('volume_multiplier', 0.95))
        use_confluence = bool(TRADING_CONFIG.get('use_confluence', False))
        
        # ATR optimal
        atr_min_1m = float(TRADING_CONFIG.get('optimal_atr_min_1m', 0.12))
        atr_max_1m = float(TRADING_CONFIG.get('optimal_atr_max_1m', 0.75))
        atr_min_5m = float(TRADING_CONFIG.get('optimal_atr_min_5m', 0.22))
        atr_max_5m = float(TRADING_CONFIG.get('optimal_atr_max_5m', 1.4))
        
        # Filtres additionnels
        use_anti_whipsaw = bool(TRADING_CONFIG.get('use_anti_whipsaw', False))
        use_candle_close = bool(TRADING_CONFIG.get('use_candle_close', False))
        use_cooldown = bool(TRADING_CONFIG.get('use_cooldown', False))
        use_momentum_continuity = bool(TRADING_CONFIG.get('use_momentum_continuity', False))
        use_retest_confirmation = bool(TRADING_CONFIG.get('use_retest_confirmation', False))
        
        # 🔥 TP/SL EXCLUS - n'affectent pas la prédiction ML (gestion post-entrée uniquement)
        
        # Patterns techniques (flags + seuils)
        use_breakout = bool(TRADING_CONFIG.get('use_breakout', True))
        breakout_threshold = float(TRADING_CONFIG.get('breakout_threshold', 0.25))
        use_snr = bool(TRADING_CONFIG.get('use_snr', True))
        snr_threshold_pat = float(TRADING_CONFIG.get('snr_threshold', 0.15))
        use_wick = bool(TRADING_CONFIG.get('use_wick', False))
        wick_ratio_max = float(TRADING_CONFIG.get('wick_ratio_max', 4.5))
        use_divergence = bool(TRADING_CONFIG.get('use_divergence', True))
        di_gap_min = float(TRADING_CONFIG.get('di_gap_min', 4.0))
        di_gap_adx_threshold = float(TRADING_CONFIG.get('di_gap_adx_threshold', 25.0))
        
        # Construire les conditions
        conditions = []
        
        # Préfixe pour les colonnes (pour jointures)
        p = "t." if use_alias else ""
        
        # ═══════════════════════════════════════════════════════════════════
        # 🔥 FILTRES ML STRICTS (demande utilisateur 11/12/2025)
        # Uniquement: LIVE + ATR + exits propres
        # Config différentes: DÉSACTIVÉ (plus de données pour l'entraînement)
        # ═══════════════════════════════════════════════════════════════════
        if for_trades_table:
            # 1. Uniquement trades LIVE (pas de dry-run)
            conditions.append(f"{p}is_live_trade = true")
            
            # 2. Uniquement mode TP/SL ATR (cohérence avec config actuelle)
            conditions.append(f"{p}tp_sl_mode = 'ATR'")
            
            # 3. Exclure MANUAL et STAGNATION (sorties non représentatives)
            conditions.append(f"({p}exit_reason IS NULL OR {p}exit_reason NOT IN ('MANUAL', 'STAGNATION'))")
        
        logger.info(f"✅ {len(conditions)} conditions de filtrage construites")
        return conditions
        
    except Exception as e:
        logger.error(f"❌ Erreur build_config_filter_conditions: {e}")
        # Retourner un filtre minimal en cas d'erreur
        return ["(exit_reason IS NULL OR exit_reason != 'MANUAL')"]


def get_postgres_connection():
    """Connexion PostgreSQL depuis variables d'environnement"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', 5432)),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', ''),
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
        raise


def get_sqlalchemy_engine():
    """Connexion SQLAlchemy pour pandas read_sql"""
    try:
        from urllib.parse import quote_plus
        
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', 5432))
        database = os.getenv('POSTGRES_DB', 'trade_cursor_ml')
        user = os.getenv('POSTGRES_USER', 'postgres')
        password = os.getenv('POSTGRES_PASSWORD', '')
        
        # URL-encode password to handle special characters
        password_encoded = quote_plus(password) if password else ''
        
        connection_string = f"postgresql://{user}:{password_encoded}@{host}:{port}/{database}"
        engine = create_engine(connection_string)
        return engine
    except Exception as e:
        logger.error(f"❌ Erreur création SQLAlchemy engine: {e}")
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
    include_open_trades: bool = False,
    use_clean_data: bool = True  # Ignoré - on utilise directement trades + scan_logs
) -> pd.DataFrame:
    """
    Charge features depuis PostgreSQL directement depuis la table trades.
    
    🔥 IMPORTANT: Utilise le MÊME filtre complet que le compteur GradientBoosting
    pour garantir la cohérence entre le compteur et l'entraînement des modèles.
    
    Args:
        min_trades: Nombre minimum de trades requis
        timeframe_days: Nombre de jours à charger
        max_trades: Limite maximum de trades (None = tous)
        include_open_trades: Inclure trades non fermés
        use_clean_data: Ignoré (conservé pour compatibilité)
        
    Returns:
        DataFrame avec features + target
        
    Raises:
        ValueError: Si pas assez de données
    """
    try:
        engine = get_sqlalchemy_engine()
        
        # 🔥 Appliquer le MÊME filtre complet que le compteur GradientBoosting
        # Cela garantit que XGBoost V1/V2 s'entraînent sur exactement les mêmes trades
        filter_conditions = build_config_filter_conditions(for_trades_table=True, use_alias=True)
        
        logger.info(f"📊 Chargement depuis table trades avec filtre complet ({len(filter_conditions)} conditions)")
        
        # Requête directe sur trades + jointure scan_logs pour features d'entrée
        query = f"""
        SELECT 
            -- Identifiants
            t.scan_log_id AS scan_id,
            t.timestamp_entry AS timestamp,
            t.symbol,
            
            -- Features 1m (depuis trades - indicateurs à l'entrée)
            t.entry_rsi_1m AS rsi_1m,
            t.entry_rsi_prev_1m AS rsi_prev_1m,
            t.entry_macd_hist_1m AS macd_hist_1m,
            t.entry_macd_hist_prev_1m AS macd_hist_prev_1m,
            t.entry_adx_1m AS adx_1m,
            t.entry_di_plus_1m AS di_plus_1m,
            t.entry_di_minus_1m AS di_minus_1m,
            t.entry_di_gap_1m AS di_gap_1m,
            t.entry_atr_pct_1m AS atr_pct_1m,
            t.entry_ema_diff_pct_1m AS ema_diff_pct_1m,
            t.entry_volume_ratio_1m AS volume_ratio_1m,
            t.entry_volume_spike_1m AS volume_spike_1m,
            t.entry_bb_width_1m AS bb_width_1m,
            t.entry_bb_distance_to_lower_1m AS bb_distance_to_lower_1m,
            t.entry_bb_distance_to_upper_1m AS bb_distance_to_upper_1m,
            
            -- Features 5m (depuis trades - indicateurs à l'entrée)
            t.entry_rsi_5m AS rsi_5m,
            t.entry_rsi_prev_5m AS rsi_prev_5m,
            t.entry_macd_hist_5m AS macd_hist_5m,
            t.entry_macd_hist_prev_5m AS macd_hist_prev_5m,
            t.entry_adx_5m AS adx_5m,
            t.entry_di_plus_5m AS di_plus_5m,
            t.entry_di_minus_5m AS di_minus_5m,
            t.entry_di_gap_5m AS di_gap_5m,
            t.entry_atr_pct_5m AS atr_pct_5m,
            t.entry_ema_diff_pct_5m AS ema_diff_pct_5m,
            t.entry_volume_ratio_5m AS volume_ratio_5m,
            t.entry_volume_spike_5m AS volume_spike_5m,
            t.entry_bb_width_5m AS bb_width_5m,
            t.entry_bb_distance_to_lower_5m AS bb_distance_to_lower_5m,
            t.entry_bb_distance_to_upper_5m AS bb_distance_to_upper_5m,
            
            -- Filtres qualité (depuis scan_logs)
            s.snr_passed_1m,
            s.snr_passed_5m,
            s.breakout_passed_1m,
            s.breakout_passed_5m,
            s.wick_passed_1m,
            s.wick_passed_5m,
            s.atr_optimal_passed_1m,
            s.atr_optimal_passed_5m,
            s.volume_filter_passed_1m,
            s.volume_filter_passed_5m,
            
            -- Config parameters (depuis trades)
            t.config_min_score_required,
            t.config_snr_threshold,
            t.config_optimal_atr_min_1m AS config_atr_min_1m,
            t.config_optimal_atr_max_1m AS config_atr_max_1m,
            t.config_optimal_atr_min_5m AS config_atr_min_5m,
            t.config_optimal_atr_max_5m AS config_atr_max_5m,
            t.config_volume_multiplier,
            t.config_use_confluence,
            
            -- Reject category (depuis scan_logs)
            s.reject_reason_category,
            
            -- 🔥 Order Flow features (depuis trades)
            t.delta_volume,
            t.imbalance_normalized,
            t.book_depth_ratio,
            
            -- Labels ML
            s.is_opportunity,
            t.win AS target_win,
            t.pnl_pct AS target_pnl
            
        FROM trades t
        LEFT JOIN scan_logs s ON t.scan_log_id = s.id
        WHERE t.timestamp_entry > NOW() - INTERVAL '%(days)s days'
        AND {' AND '.join(filter_conditions)}
        """
        
        # Ajouter filtre trades fermés si nécessaire
        if not include_open_trades:
            query += " AND t.win IS NOT NULL"
        
        query += " ORDER BY t.timestamp_entry DESC"
        
        # Ajouter limite si spécifiée
        if max_trades:
            query += f" LIMIT {max_trades}"
        
        # Charger dans DataFrame avec SQLAlchemy
        df = pd.read_sql(query, engine, params={'days': timeframe_days})
        
        logger.info(f"📊 Features chargées: {len(df)} rows depuis PostgreSQL")
        logger.info(f"🔍 Colonnes présentes: {list(df.columns)}")
        if 'target_win' in df.columns:
            logger.info(f"🔍 target_win RAW: dtype={df['target_win'].dtype}, non-null={df['target_win'].notna().sum()}")
            logger.info(f"🔍 target_win SAMPLE VALUES: {df['target_win'].head(10).tolist()}")
            logger.info(f"🔍 target_win UNIQUE: {df['target_win'].unique()}")
        
        # Convertir colonnes numériques (exclure booléennes et texte)
        exclude_from_numeric = [
            'scan_id', 'timestamp', 'symbol', 'opportunity_direction',
            'target_win', 'is_opportunity',  # Booléens
            'snr_passed_1m', 'snr_passed_5m',  # Quality filters (bool)
            'breakout_passed_1m', 'breakout_passed_5m',
            'wick_passed_1m', 'wick_passed_5m',
            'atr_optimal_passed_1m', 'atr_optimal_passed_5m',
            'volume_filter_passed_1m', 'volume_filter_passed_5m',
            'config_use_confluence',  # 🔥 Boolean config
            'reject_reason_category',  # 🔥 Catégorie texte
        ]
        
        numeric_cols = [col for col in df.columns if col not in exclude_from_numeric]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Colonnes entièrement NaN -> remplir avec 0 pour éviter erreurs imputations/feature eng.
        feature_columns = [col for col in df.columns if col not in ['scan_id', 'timestamp', 'symbol', 'opportunity_direction']]
        all_nan_cols = [col for col in feature_columns if df[col].isna().all()]
        if all_nan_cols:
            logger.warning(
                f"⚠️ Colonnes sans données ({len(all_nan_cols)}), remplissage par 0: {all_nan_cols}"
            )
            df[all_nan_cols] = 0.0
        
        # Normaliser target_win en 0/1 (bool -> int)
        if 'target_win' in df.columns:
            # Diagnostic
            logger.info(f"🔍 target_win avant conversion: type={df['target_win'].dtype}, non-null={df['target_win'].notna().sum()}/{len(df)}, unique values={df['target_win'].unique()[:10]}")
            # Convertir PostgreSQL boolean strings ('t'/'f') en int (1/0)
            df['target_win'] = df['target_win'].map({'t': 1, 'f': 0, True: 1, False: 0, 1: 1, 0: 0})
            logger.info(f"🔍 target_win après conversion: unique={df['target_win'].unique()}, dtype={df['target_win'].dtype}")
        
        logger.info(f"🔄 Conversion des types numériques effectuée")
        
        # Validation minimum (warning au lieu de bloquer)
        if len(df) < min_trades:
            logger.warning(
                f"⚠️ Données limitées: {len(df)}/{min_trades} trades - résultats peuvent être sous-optimaux"
            )
            # Ne PAS bloquer, continuer avec les données disponibles
        
        # Nettoyer NaN
        logger.info(f"🔍 Avant dropna: {len(df)} rows, target_win non-null: {df['target_win'].notna().sum() if 'target_win' in df.columns else 'N/A'}")
        df = df.dropna(subset=['target_win'])
        logger.info(f"🔍 Après dropna: {len(df)} rows")
        
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
