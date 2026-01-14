#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ajouter config_invert_signals et vérifier les colonnes manquantes
"""
import psycopg2

def add_config_invert_signals():
    """Ajouter la colonne config_invert_signals à la table trades"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    try:
        # Ajouter la colonne config_invert_signals
        print("🔧 Ajout de la colonne config_invert_signals...")
        cursor.execute("""
            ALTER TABLE trades 
            ADD COLUMN IF NOT EXISTS config_invert_signals BOOLEAN DEFAULT NULL
        """)
        print("✅ Colonne config_invert_signals ajoutée avec succès")
        
        # Valider les changements
        conn.commit()
        
    except Exception as e:
        print(f"❌ Erreur lors de l'ajout de la colonne: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()

def check_missing_columns():
    """Vérifier les colonnes de l'export qui n'existent pas dans la DB"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Colonnes mentionnées dans l'export Excel (trades)
    export_columns = [
        'config_min_score_required', 'config_snr_threshold',
        'config_optimal_atr_min_1m', 'config_optimal_atr_max_1m',
        'config_optimal_atr_min_5m', 'config_optimal_atr_max_5m',
        'config_volume_multiplier', 'config_use_confluence',
        'config_invert_signals',  # Nouvellement ajoutée
        'config_use_anti_whipsaw', 'config_whipsaw_lookback',
        'config_whipsaw_threshold_pct', 'config_whipsaw_max_alternations',
        'config_use_retest_confirmation', 'config_retest_tolerance_pct',
        'config_retest_timeout_seconds', 'config_use_cooldown',
        'config_cooldown_seconds', 'config_cooldown_same_symbol',
        'config_use_candle_close', 'config_candle_close_threshold_seconds',
        'config_use_momentum_continuity', 'config_momentum_lookback',
        'config_rsi_filter_enabled', 'config_rsi_long_max', 'config_rsi_short_min',
        'config_stagnation_positive_exit_enabled', 'config_stagnation_positive_threshold',
        'config_stagnation_positive_timeout_seconds', 'config_stagnation_use_mfe_tracking',
        'config_stagnation_mfe_pullback_pct', 'config_use_micro_confirmation',
        'config_micro_confirmation_delay_ms', 'config_trailing_mfe_enabled',
        'config_trailing_mfe_trigger_pct', 'config_trailing_mfe_lock_in_pct',
        'config_partial_tp_be_lock_in_pct',
        # Colonnes de scalabilité
        'delta_volume', 'imbalance_normalized', 'book_depth_ratio',
        # Colonnes Market Regime
        'entry_market_regime', 'entry_market_regime_avg_atr', 'entry_market_regime_avg_adx',
        'entry_min_score_required', 'entry_atr_mult_sl', 'entry_atr_mult_tp',
        'entry_cb_state', 'entry_consecutive_losses', 'entry_daily_pnl_pct', 'entry_cb_score_boost'
    ]
    
    # Récupérer les colonnes existantes
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades' 
        AND table_schema = 'public'
    """)
    
    existing_columns = {row[0] for row in cursor.fetchall()}
    
    # Vérifier les colonnes manquantes
    missing_columns = []
    for col in export_columns:
        if col not in existing_columns:
            missing_columns.append(col)
    
    if missing_columns:
        print(f"\n❌ Colonnes manquantes ({len(missing_columns)}):")
        for col in missing_columns:
            print(f"   - {col}")
        
        # Générer les ALTER TABLE pour les colonnes manquantes
        print(f"\n🔧 Requêtes SQL pour ajouter les colonnes manquantes:")
        for col in missing_columns:
            if col.startswith('config_use_') or col.endswith('_enabled'):
                sql = f"ALTER TABLE trades ADD COLUMN IF NOT EXISTS {col} BOOLEAN DEFAULT NULL;"
            elif 'pct' in col or 'threshold' in col or 'mult' in col or 'score' in col or 'atr' in col:
                sql = f"ALTER TABLE trades ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION DEFAULT NULL;"
            elif 'seconds' in col or 'lookback' in col or 'alternations' in col or 'count' in col:
                sql = f"ALTER TABLE trades ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT NULL;"
            else:
                sql = f"ALTER TABLE trades ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION DEFAULT NULL;"
            print(f"   {sql}")
    else:
        print("\n✅ Toutes les colonnes de l'export existent dans la base !")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        # D'abord ajouter config_invert_signals
        add_config_invert_signals()
        
        # Puis vérifier s'il y a d'autres colonnes manquantes
        check_missing_columns()
        
    except Exception as e:
        print(f"Erreur: {e}")
