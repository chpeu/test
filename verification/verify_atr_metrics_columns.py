#!/usr/bin/env python3
"""
🔍 Vérification des colonnes trade_atr_metrics
Exécuter après quelques trades pour valider que les colonnes sont bien remplies.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from datetime import datetime, timedelta

# Colonnes critiques à vérifier
CRITICAL_COLUMNS = [
    'entry_atr_1m',
    'entry_atr_pct_1m', 
    'param_atr_mult_sl',
    'param_atr_mult_tp',
    'market_volatility_state',
    'be_triggered',
    'trailing_activated',
    'max_pnl_reached',
    'min_pnl_reached',
]

CONDITIONAL_COLUMNS = {
    'calculated_sl_price': 'Toujours (si SL défini)',
    'calculated_tp_price': 'Toujours (si TP défini)',
    'calculated_sl_pct': 'Toujours (si SL défini)',
    'calculated_tp_pct': 'Toujours (si TP défini)',
    'be_triggered_at': 'Si BE activé',
    'be_triggered_pnl_pct': 'Si BE activé',
    'be_price_at_trigger': 'Si BE activé',
    'trailing_activated_at': 'Si Trailing activé',
    'trailing_final_sl_price': 'Si Trailing activé',
    'trailing_final_distance_pct': 'Si Trailing activé',
    'max_price_reached': 'Toujours',
    'min_price_reached': 'Toujours',
    'time_to_max_pnl_seconds': 'Toujours',
    'time_to_min_pnl_seconds': 'Toujours',
    'stagnation_duration_seconds': 'Si exit = STAGNATION',
    'stagnation_pnl_at_exit': 'Si exit = STAGNATION',
}


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', 5432),
        database=os.getenv('POSTGRES_DB', 'trading_bot'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD')
    )


def check_columns():
    print("=" * 70)
    print("VERIFICATION COLONNES trade_atr_metrics")
    print("=" * 70)
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Total trades
    cur.execute("SELECT COUNT(*) FROM trade_atr_metrics")
    total = cur.fetchone()[0]
    print(f"Total trades dans trade_atr_metrics: {total}")
    
    # Trades récents (après restart)
    cur.execute("""
        SELECT COUNT(*) FROM trade_atr_metrics 
        WHERE id > (SELECT COALESCE(MAX(id) - 5, 0) FROM trade_atr_metrics)
    """)
    recent = cur.fetchone()[0]
    print(f"Trades récents analysés: {recent}")
    print()
    
    # Vérifier chaque colonne
    print("-" * 70)
    print(f"{'Colonne':<35} {'Rempli':<10} {'%':>8} {'Status'}")
    print("-" * 70)
    
    issues = []
    
    for col in CRITICAL_COLUMNS:
        cur.execute(f"SELECT COUNT({col}), COUNT(*) FROM trade_atr_metrics")
        filled, total_col = cur.fetchone()
        pct = (filled / total_col * 100) if total_col > 0 else 0
        status = "OK" if pct >= 90 else "WARN" if pct >= 50 else "ERROR"
        symbol = "[OK]" if status == "OK" else "[!!]" if status == "ERROR" else "[?]"
        print(f"{col:<35} {filled}/{total_col:<7} {pct:>7.1f}% {symbol}")
        if status == "ERROR":
            issues.append(col)
    
    print()
    print("COLONNES CONDITIONNELLES:")
    print("-" * 70)
    
    for col, condition in CONDITIONAL_COLUMNS.items():
        cur.execute(f"SELECT COUNT({col}), COUNT(*) FROM trade_atr_metrics")
        filled, total_col = cur.fetchone()
        pct = (filled / total_col * 100) if total_col > 0 else 0
        
        # Vérifier les trades récents seulement
        cur.execute(f"""
            SELECT COUNT({col}) FROM trade_atr_metrics 
            WHERE id > (SELECT COALESCE(MAX(id) - 5, 0) FROM trade_atr_metrics)
        """)
        recent_filled = cur.fetchone()[0]
        recent_pct = (recent_filled / recent * 100) if recent > 0 else 0
        
        status = "NEW" if recent_pct > pct else ("OK" if pct > 0 else "EMPTY")
        print(f"{col:<35} {filled}/{total_col:<7} {pct:>7.1f}% (recent: {recent_pct:.0f}%) | {condition}")
    
    print()
    print("=" * 70)
    
    # Afficher dernier trade
    print("\nDERNIER TRADE:")
    cur.execute("""
        SELECT 
            tam.id, t.symbol, t.exit_reason,
            tam.calculated_sl_price, tam.calculated_tp_price,
            tam.be_triggered, tam.be_triggered_pnl_pct,
            tam.trailing_activated, tam.trailing_final_sl_price,
            tam.stagnation_duration_seconds
        FROM trade_atr_metrics tam
        JOIN trades t ON tam.trade_id = t.id
        ORDER BY tam.id DESC LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        print(f"  ID: {row[0]}")
        print(f"  Symbol: {row[1]}")
        print(f"  Exit: {row[2]}")
        print(f"  SL Price: {row[3]}")
        print(f"  TP Price: {row[4]}")
        print(f"  BE: {row[5]} (PnL: {row[6]})")
        print(f"  Trailing: {row[7]} (Final SL: {row[8]})")
        print(f"  Stagnation dur: {row[9]}")
    
    print("=" * 70)
    
    if issues:
        print(f"\n[!!] COLONNES CRITIQUES VIDES: {', '.join(issues)}")
        return False
    else:
        print("\n[OK] Toutes les colonnes critiques sont remplies!")
        return True


if __name__ == "__main__":
    try:
        success = check_columns()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[ERREUR] {e}")
        sys.exit(1)
