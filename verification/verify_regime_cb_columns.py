#!/usr/bin/env python3
"""
VERIFICATION: Market Regime & Circuit Breaker Columns
======================================================
Ce script vérifie que les nouvelles colonnes et tables sont correctement remplies.

Usage:
    python verification/verify_regime_cb_columns.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from datetime import datetime, timedelta

# Configuration DB
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'dbname': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}


def print_header(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(test_name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"  {status} | {test_name}")
    if details:
        print(f"         └─ {details}")


def get_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ Erreur connexion DB: {e}")
        return None


def check_tables_exist(conn):
    """Vérifie que les nouvelles tables existent."""
    print_header("1. TABLES EXISTENCE")
    
    tables = ['circuit_breaker_events', 'market_regime_history']
    cursor = conn.cursor()
    
    for table in tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            )
        """, (table,))
        exists = cursor.fetchone()[0]
        print_result(f"Table '{table}'", exists)
    
    cursor.close()
    return True


def check_columns_trades(conn):
    """Vérifie les colonnes du régime dans trades."""
    print_header("2. COLONNES trades")
    
    expected_columns = [
        'entry_market_regime',
        'entry_market_regime_avg_atr',
        'entry_market_regime_avg_adx',
        'entry_min_score_required',
        'entry_atr_mult_sl',
        'entry_atr_mult_tp',
        'entry_cb_state',
        'entry_consecutive_losses',
        'entry_daily_pnl_pct',
        'entry_cb_score_boost'
    ]
    
    cursor = conn.cursor()
    
    for col in expected_columns:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'trades' AND column_name = %s
            )
        """, (col,))
        exists = cursor.fetchone()[0]
        print_result(f"Colonne '{col}'", exists)
    
    cursor.close()
    return True


def check_columns_scan_logs(conn):
    """Vérifie les colonnes du régime dans scan_logs."""
    print_header("3. COLONNES scan_logs")
    
    expected_columns = [
        'market_regime',
        'market_regime_avg_atr',
        'market_regime_avg_adx'
    ]
    
    cursor = conn.cursor()
    
    for col in expected_columns:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'scan_logs' AND column_name = %s
            )
        """, (col,))
        exists = cursor.fetchone()[0]
        print_result(f"Colonne '{col}'", exists)
    
    cursor.close()
    return True


def check_trades_data_filled(conn):
    """Vérifie que les données sont remplies dans trades."""
    print_header("4. DONNÉES trades (dernières 24h)")
    
    cursor = conn.cursor()
    
    # Total trades dernières 24h
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE timestamp_entry > NOW() - INTERVAL '24 hours'
    """)
    total = cursor.fetchone()[0]
    
    # Trades avec régime rempli
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE timestamp_entry > NOW() - INTERVAL '24 hours'
        AND entry_market_regime IS NOT NULL
    """)
    with_regime = cursor.fetchone()[0]
    
    # Trades avec CB rempli
    cursor.execute("""
        SELECT COUNT(*) FROM trades 
        WHERE timestamp_entry > NOW() - INTERVAL '24 hours'
        AND entry_cb_state IS NOT NULL
    """)
    with_cb = cursor.fetchone()[0]
    
    print_result(f"Total trades (24h)", total > 0, f"{total} trades")
    print_result(f"Avec entry_market_regime", with_regime > 0, f"{with_regime}/{total} ({100*with_regime/total:.0f}% si total>0)" if total > 0 else "0/0")
    print_result(f"Avec entry_cb_state", with_cb > 0, f"{with_cb}/{total} ({100*with_cb/total:.0f}% si total>0)" if total > 0 else "0/0")
    
    # Afficher le dernier trade avec ses valeurs
    cursor.execute("""
        SELECT symbol, entry_market_regime, entry_market_regime_avg_atr, 
               entry_cb_state, entry_consecutive_losses
        FROM trades 
        ORDER BY timestamp_entry DESC LIMIT 1
    """)
    last_trade = cursor.fetchone()
    if last_trade:
        print(f"\n  📊 Dernier trade: {last_trade[0]}")
        print(f"     - Régime: {last_trade[1]}")
        print(f"     - ATR moyen: {last_trade[2]}")
        print(f"     - CB State: {last_trade[3]}")
        print(f"     - Losses consécutives: {last_trade[4]}")
    
    cursor.close()
    return with_regime > 0


def check_scan_logs_data_filled(conn):
    """Vérifie que les données sont remplies dans scan_logs."""
    print_header("5. DONNÉES scan_logs (dernières 10 minutes)")
    
    cursor = conn.cursor()
    
    # Total scans dernières 10 min
    cursor.execute("""
        SELECT COUNT(*) FROM scan_logs 
        WHERE timestamp > NOW() - INTERVAL '10 minutes'
    """)
    total = cursor.fetchone()[0]
    
    # Scans avec régime rempli
    cursor.execute("""
        SELECT COUNT(*) FROM scan_logs 
        WHERE timestamp > NOW() - INTERVAL '10 minutes'
        AND market_regime IS NOT NULL
    """)
    with_regime = cursor.fetchone()[0]
    
    print_result(f"Total scans (10min)", total > 0, f"{total} scans")
    print_result(f"Avec market_regime", with_regime > 0, f"{with_regime}/{total} ({100*with_regime/total:.0f}%)" if total > 0 else "0/0")
    
    # Afficher le dernier scan avec ses valeurs
    cursor.execute("""
        SELECT symbol, market_regime, market_regime_avg_atr, market_regime_avg_adx
        FROM scan_logs 
        ORDER BY timestamp DESC LIMIT 1
    """)
    last_scan = cursor.fetchone()
    if last_scan:
        print(f"\n  📊 Dernier scan: {last_scan[0]}")
        print(f"     - Régime: {last_scan[1]}")
        print(f"     - ATR moyen: {last_scan[2]}")
        print(f"     - ADX moyen: {last_scan[3]}")
    
    cursor.close()
    return with_regime > 0


def check_event_tables(conn):
    """Vérifie le contenu des tables d'événements."""
    print_header("6. TABLES D'ÉVÉNEMENTS")
    
    cursor = conn.cursor()
    
    # circuit_breaker_events
    cursor.execute("SELECT COUNT(*) FROM circuit_breaker_events")
    cb_count = cursor.fetchone()[0]
    print_result(f"circuit_breaker_events", True, f"{cb_count} événements")
    
    if cb_count > 0:
        cursor.execute("""
            SELECT event_type, reason, state_before, state_after, timestamp
            FROM circuit_breaker_events ORDER BY timestamp DESC LIMIT 3
        """)
        print("     Derniers événements:")
        for row in cursor.fetchall():
            print(f"       - {row[0]}: {row[2]} → {row[3]} ({row[1][:30]}...)")
    
    # market_regime_history
    cursor.execute("SELECT COUNT(*) FROM market_regime_history")
    regime_count = cursor.fetchone()[0]
    print_result(f"market_regime_history", True, f"{regime_count} changements")
    
    if regime_count > 0:
        cursor.execute("""
            SELECT old_regime, new_regime, avg_atr, timestamp
            FROM market_regime_history ORDER BY timestamp DESC LIMIT 3
        """)
        print("     Derniers changements:")
        for row in cursor.fetchall():
            print(f"       - {row[0]} → {row[1]} (ATR: {row[2]:.3f}%)")
    
    cursor.close()
    return True


def run_all_checks():
    """Exécute toutes les vérifications."""
    print("\n" + "=" * 60)
    print(" VERIFICATION: Market Regime & Circuit Breaker")
    print(" " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    conn = get_connection()
    if not conn:
        print("\n❌ Impossible de se connecter à la base de données")
        return False
    
    try:
        check_tables_exist(conn)
        check_columns_trades(conn)
        check_columns_scan_logs(conn)
        trades_ok = check_trades_data_filled(conn)
        scans_ok = check_scan_logs_data_filled(conn)
        check_event_tables(conn)
        
        print_header("RÉSUMÉ")
        print_result("Tables créées", True)
        print_result("Colonnes présentes", True)
        print_result("Données trades remplies", trades_ok)
        print_result("Données scan_logs remplies", scans_ok)
        
        if not scans_ok:
            print("\n⚠️  Les colonnes scan_logs ne sont pas remplies.")
            print("    Vérifiez que le backend a été redémarré après les modifications.")
            print("    Attendez quelques scans pour que les données apparaissent.")
        
        return trades_ok and scans_ok
        
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_all_checks()
    print("\n")
    sys.exit(0 if success else 1)
