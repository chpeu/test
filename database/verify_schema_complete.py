#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de vérification complète du schéma PostgreSQL
Compare le schéma SQL avec le code Python pour détecter les incohérences
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

# Encodage UTF-8 pour Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def parse_args():
    """Parse CLI arguments"""
    parser = argparse.ArgumentParser(description="Vérification complète du schéma PostgreSQL")
    parser.add_argument('--password', help='Mot de passe PostgreSQL (prioritaire sur POSTGRES_PASSWORD)')
    return parser.parse_args()


def get_connection():
    """Obtenir une connexion PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL: {e}")
        return None

def get_table_columns(conn, table_name):
    """Récupérer toutes les colonnes d'une table"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT 
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """
    cursor.execute(query, (table_name,))
    return cursor.fetchall()

def get_all_tables(conn):
    """Récupérer toutes les tables"""
    cursor = conn.cursor()
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """
    cursor.execute(query)
    return [row[0] for row in cursor.fetchall()]

def get_indexes(conn, table_name):
    """Récupérer tous les index d'une table"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = %s
        AND schemaname = 'public'
        ORDER BY indexname
    """
    cursor.execute(query, (table_name,))
    return cursor.fetchall()

def get_foreign_keys(conn, table_name):
    """Récupérer toutes les clés étrangères d'une table"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_name = %s
    """
    cursor.execute(query, (table_name,))
    return cursor.fetchall()

def print_table_schema(conn, table_name):
    """Afficher le schéma complet d'une table"""
    print(f"\n{'='*80}")
    print(f"📊 TABLE: {table_name}")
    print(f"{'='*80}")
    
    # Colonnes
    columns = get_table_columns(conn, table_name)
    print(f"\n📋 COLONNES ({len(columns)}):")
    print("-" * 80)
    for col in columns:
        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
        default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
        print(f"  • {col['column_name']:<40} {col['data_type']:<20} {nullable}{default}")
    
    # Index
    indexes = get_indexes(conn, table_name)
    if indexes:
        print(f"\n🔍 INDEX ({len(indexes)}):")
        print("-" * 80)
        for idx in indexes:
            print(f"  • {idx['indexname']}")
            print(f"    {idx['indexdef']}")
    
    # Clés étrangères
    fks = get_foreign_keys(conn, table_name)
    if fks:
        print(f"\n🔗 CLÉS ÉTRANGÈRES ({len(fks)}):")
        print("-" * 80)
        for fk in fks:
            print(f"  • {fk['column_name']} → {fk['foreign_table_name']}.{fk['foreign_column_name']}")

def verify_trades_table(conn):
    """Vérifier que la table trades a toutes les colonnes attendues"""
    print(f"\n{'='*80}")
    print("✅ VÉRIFICATION TABLE: trades")
    print(f"{'='*80}")
    
    # Colonnes attendues (depuis le code Python)
    expected_columns = {
        # Base
        'id', 'opportunity_id', 'scan_log_id', 'session_id', 'symbol', 'direction',
        # Entry
        'timestamp_entry', 'entry_price', 'size_usdt', 'tp_price', 'sl_price', 'tp_sl_mode',
        # Entry indicators - RSI
        'entry_rsi_1m', 'entry_rsi_5m', 'entry_rsi_prev_1m', 'entry_rsi_prev_5m',
        # Entry indicators - MACD
        'entry_macd_1m', 'entry_macd_signal_1m', 'entry_macd_hist_1m', 'entry_macd_hist_prev_1m',
        'entry_macd_5m', 'entry_macd_signal_5m', 'entry_macd_hist_5m', 'entry_macd_hist_prev_5m',
        # Entry indicators - ADX
        'entry_adx_1m', 'entry_adx_5m', 'entry_di_plus_1m', 'entry_di_minus_1m', 'entry_di_gap_1m',
        'entry_di_plus_5m', 'entry_di_minus_5m', 'entry_di_gap_5m',
        # Entry indicators - EMA
        'entry_ema9_1m', 'entry_ema21_1m', 'entry_ema_diff_pct_1m',
        'entry_ema9_5m', 'entry_ema21_5m', 'entry_ema_diff_pct_5m',
        # Entry indicators - ATR
        'entry_atr_1m', 'entry_atr_pct_1m', 'entry_atr_5m', 'entry_atr_pct_5m',
        # Entry indicators - Bollinger
        'entry_bb_upper_1m', 'entry_bb_middle_1m', 'entry_bb_lower_1m',
        'entry_bb_width_1m', 'entry_bb_distance_to_lower_1m', 'entry_bb_distance_to_upper_1m',
        'entry_bb_upper_5m', 'entry_bb_middle_5m', 'entry_bb_lower_5m',
        'entry_bb_width_5m', 'entry_bb_distance_to_lower_5m', 'entry_bb_distance_to_upper_5m',
        # Entry indicators - Volume
        'entry_volume_1m', 'entry_volume_avg_1m', 'entry_volume_ratio_1m', 'entry_volume_spike_1m',
        'entry_volume_5m', 'entry_volume_avg_5m', 'entry_volume_ratio_5m', 'entry_volume_spike_5m',
        # Entry - Score et autres
        'entry_score', 'entry_spread_pct', 'entry_balance_score',
        'entry_conditions', 'entry_condition_count',
        # Entry - Temporel
        'entry_hour_of_day', 'entry_day_of_week',
        # Exit
        'timestamp_exit', 'exit_price', 'exit_reason',
        # Exit indicators
        'exit_rsi_1m', 'exit_rsi_5m', 'exit_macd_hist_1m', 'exit_macd_hist_5m',
        'exit_adx_1m', 'exit_adx_5m', 'exit_atr_pct_1m', 'exit_atr_pct_5m',
        'exit_score', 'exit_volume_ratio_1m', 'exit_volume_ratio_5m',
        'exit_spread_pct', 'exit_balance_score', 'entry_to_exit_price_change_pct',
        # Exit - Temporel
        'exit_hour_of_day', 'exit_day_of_week',
        # Résultats
        'duration_seconds', 'pnl_pct', 'pnl_usdt', 'gross_pnl_usdt',
        'slippage_pct', 'slippage_usdt', 'fees_usdt', 'net_pnl_usdt', 'net_pnl_pct',
        'win',
        # Events
        'break_even_set', 'break_even_triggered_at', 'partial_tp_executed', 'partial_tp_triggered_at',
        'partial_tp_profit', 'partial_tp_percent', 'tp_escalier_levels_executed', 'tp_escalier_profits',
        'trailing_stop_activated', 'trailing_stop_triggered_at',
        # Métriques position
        'max_favorable_excursion', 'max_adverse_excursion',
        'max_favorable_excursion_usdt', 'max_adverse_excursion_usdt',
        # Métriques qualité
        'risk_reward_ratio', 'profit_factor',
        # Métriques performance
        'entry_to_max_profit_price_change_pct', 'entry_to_max_loss_price_change_pct',
        'max_drawdown_pct', 'max_drawdown_usdt',
        # Scalability
        'entry_book_depth', 'entry_bid_vol', 'entry_ask_vol', 'entry_orderbook_imbalance',
        # Config
        'config_snapshot',
        # Métadonnées
        'created_at', 'updated_at'
    }
    
    columns = get_table_columns(conn, 'trades')
    actual_columns = {col['column_name'] for col in columns}
    
    missing = expected_columns - actual_columns
    extra = actual_columns - expected_columns
    
    if missing:
        print(f"❌ COLONNES MANQUANTES ({len(missing)}):")
        for col in sorted(missing):
            print(f"  • {col}")
    else:
        print("✅ Toutes les colonnes attendues sont présentes")
    
    if extra:
        print(f"\n⚠️ COLONNES SUPPLÉMENTAIRES ({len(extra)}):")
        for col in sorted(extra):
            print(f"  • {col}")
    
    print(f"\n📊 RÉSUMÉ: {len(actual_columns)} colonnes dans la table, {len(expected_columns)} attendues")
    
    return len(missing) == 0

def main():
    """Fonction principale"""
    print("🔍 VÉRIFICATION COMPLÈTE DU SCHÉMA POSTGRESQL")
    print("=" * 80)
    
    args = parse_args()
    if args.password:
        DB_CONFIG['password'] = args.password

    conn = get_connection()
    if not conn:
        return 1
    
    try:
        # Lister toutes les tables
        tables = get_all_tables(conn)
        print(f"\n📋 TABLES TROUVÉES ({len(tables)}):")
        for table in tables:
            print(f"  • {table}")
        
        # Afficher le schéma de chaque table
        for table in tables:
            print_table_schema(conn, table)
        
        # Vérification spécifique de trades
        if 'trades' in tables:
            is_valid = verify_trades_table(conn)
            if is_valid:
                print("\n✅ La table trades est à jour avec le code Python")
            else:
                print("\n❌ La table trades n'est pas à jour - exécutez la migration")
                return 1
        
        print(f"\n{'='*80}")
        print("✅ VÉRIFICATION TERMINÉE")
        print(f"{'='*80}")
        return 0
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()

if __name__ == '__main__':
    sys.exit(main())

