#!/usr/bin/env python3
"""
Migration SQLite: Ajouter colonnes LIVE TRADING a la table trades
"""
import sqlite3
import os
import sys

DB_PATH = "data/analytics.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[ERREUR] Base de donnees non trouvee: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Recuperer colonnes existantes
    cur.execute("PRAGMA table_info(trades)")
    existing = {row[1] for row in cur.fetchall()}
    print(f"[INFO] Colonnes existantes: {len(existing)}")
    
    # Colonnes a ajouter
    columns = [
        ("is_live_trade", "INTEGER DEFAULT 0"),
        ("is_dry_run", "INTEGER DEFAULT 1"),
        ("live_execution_mode", "TEXT"),
        ("entry_order_id", "TEXT"),
        ("entry_order_type", "TEXT"),
        ("entry_requested_price", "REAL"),
        ("entry_fill_price", "REAL"),
        ("entry_slippage_pct", "REAL"),
        ("entry_latency_ms", "INTEGER"),
        ("entry_timestamp", "TEXT"),
        ("entry_api_response", "TEXT"),
        ("exit_order_id", "TEXT"),
        ("exit_order_type", "TEXT"),
        ("exit_requested_price", "REAL"),
        ("exit_fill_price", "REAL"),
        ("exit_slippage_pct", "REAL"),
        ("exit_latency_ms", "INTEGER"),
        ("exit_timestamp", "TEXT"),
        ("exit_api_response", "TEXT"),
        ("leverage_used", "INTEGER DEFAULT 1"),
        ("margin_mode", "TEXT"),
        ("position_size_usdt", "REAL"),
        ("position_size_contracts", "REAL"),
        ("liquidation_price", "REAL"),
        ("margin_used", "REAL"),
        ("maker_fee_rate", "REAL"),
        ("taker_fee_rate", "REAL"),
        ("entry_fee_usdt", "REAL"),
        ("exit_fee_usdt", "REAL"),
        ("total_fees_usdt", "REAL"),
        ("funding_rate_at_entry", "REAL"),
        ("funding_rate_at_exit", "REAL"),
        ("funding_paid_usdt", "REAL"),
        ("time_to_fill_entry_ms", "INTEGER"),
        ("time_to_fill_exit_ms", "INTEGER"),
        ("price_at_signal", "REAL"),
        ("price_at_order_sent", "REAL"),
        ("signal_to_fill_slippage_pct", "REAL"),
        ("api_errors", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("exchange_latency_ms", "INTEGER"),
        ("ws_latency_ms", "INTEGER"),
        ("market_volatility_entry", "REAL"),
        ("spread_at_entry_pct", "REAL"),
        ("volume_24h_at_entry", "REAL"),
        ("orderbook_imbalance_entry", "REAL"),
        ("atr_at_entry", "REAL"),
        ("market_volatility_exit", "REAL"),
        ("spread_at_exit_pct", "REAL"),
        ("volume_24h_at_exit", "REAL"),
        ("orderbook_imbalance_exit", "REAL"),
        ("atr_at_exit", "REAL"),
        ("rsi_at_entry", "REAL"),
        ("macd_at_entry", "REAL"),
        ("bb_position_entry", "REAL"),
        ("adx_at_entry", "REAL"),
        ("di_plus_entry", "REAL"),
        ("di_minus_entry", "REAL"),
        ("rsi_at_exit", "REAL"),
        ("macd_at_exit", "REAL"),
        ("bb_position_exit", "REAL"),
        ("adx_at_exit", "REAL"),
        ("di_plus_exit", "REAL"),
        ("di_minus_exit", "REAL"),
        ("setup_score", "REAL"),
        ("ml_confidence", "REAL"),
        ("ml_prediction", "TEXT"),
        ("ml_features", "TEXT"),
        ("optimal_exit_price", "REAL"),
        ("optimal_exit_time", "TEXT"),
        ("missed_profit_pct", "REAL"),
        ("risk_reward_actual", "REAL"),
        ("risk_reward_planned", "REAL"),
        ("trade_notes", "TEXT"),
        ("trade_tags", "TEXT"),
        ("user_rating", "INTEGER")
    ]
    
    added = 0
    for name, coltype in columns:
        if name not in existing:
            try:
                cur.execute(f"ALTER TABLE trades ADD COLUMN {name} {coltype}")
                added += 1
                print(f"[OK] Colonne ajoutee: {name}")
            except Exception as e:
                print(f"[ERREUR] Impossible d'ajouter {name}: {e}")
    
    conn.commit()
    print(f"\n[INFO] Total colonnes ajoutees: {added}")
    
    # Creer les index
    indices = [
        'CREATE INDEX IF NOT EXISTS idx_trades_is_live ON trades(is_live_trade)',
        'CREATE INDEX IF NOT EXISTS idx_trades_is_dry_run ON trades(is_dry_run)',
        'CREATE INDEX IF NOT EXISTS idx_trades_leverage ON trades(leverage_used)',
        'CREATE INDEX IF NOT EXISTS idx_trades_entry_order ON trades(entry_order_id)',
        'CREATE INDEX IF NOT EXISTS idx_trades_exit_order ON trades(exit_order_id)',
        'CREATE INDEX IF NOT EXISTS idx_trades_margin_mode ON trades(margin_mode)'
    ]
    
    for stmt in indices:
        try:
            cur.execute(stmt)
        except Exception as e:
            print(f"[ERREUR] Index: {e}")
    
    conn.commit()
    
    # Verifier resultat final
    cur.execute("PRAGMA table_info(trades)")
    cols = cur.fetchall()
    print(f"[INFO] Nombre final de colonnes: {len(cols)}")
    
    conn.close()
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Migration SQLite: Colonnes LIVE TRADING")
    print("=" * 60)
    
    success = migrate()
    
    print("=" * 60)
    if success:
        print("[OK] Migration terminee avec succes")
        print("[INFO] Relancez le backend pour appliquer les changements")
    else:
        print("[ERREUR] Migration echouee")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
