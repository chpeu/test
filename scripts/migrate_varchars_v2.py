
import psycopg2
import os
from dotenv import load_dotenv

def migrate():
    load_dotenv()
    
    conn_str = os.getenv('POSTGRES_URL') or (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'trade_cursor_ml')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )

    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        
        print("🚀 Démarrage de la migration SQL (Extension des colonnes VARCHAR)...")
        
        # Liste des colonnes à étendre à VARCHAR(100)
        # On cible tout ce qui pourrait contenir des strings dynamiques ou des messages d'erreur
        migrations = [
            # market_regime_history
            ("market_regime_history", "detection_method", "VARCHAR(100)"),
            ("market_regime_history", "new_regime", "VARCHAR(100)"),
            ("market_regime_history", "old_regime", "VARCHAR(100)"),
            ("market_regime_history", "session_market", "VARCHAR(100)"),
            ("market_regime_history", "trigger", "VARCHAR(100)"),
            
            # opportunities
            ("opportunities", "market_regime", "VARCHAR(100)"),
            ("opportunities", "status", "VARCHAR(100)"),
            ("opportunities", "tp_sl_mode", "VARCHAR(100)"),
            
            # scan_logs
            ("scan_logs", "divergence_type", "VARCHAR(100)"),
            ("scan_logs", "market_regime", "VARCHAR(100)"),
            ("scan_logs", "opportunity_direction", "VARCHAR(100)"),
            ("scan_logs", "regime_at_scan", "VARCHAR(100)"),
            ("scan_logs", "session_market", "VARCHAR(100)"),
            ("scan_logs", "trend_direction", "VARCHAR(100)"),
            ("scan_logs", "trend_timeframe", "VARCHAR(100)"),
            
            # trade_atr_metrics
            ("trade_atr_metrics", "market_trend_state", "VARCHAR(100)"),
            ("trade_atr_metrics", "market_volatility_state", "VARCHAR(100)"),
            ("trade_atr_metrics", "optimal_regime_retrospective", "VARCHAR(100)"),
            ("trade_atr_metrics", "regime_detection_method", "VARCHAR(100)"),
            ("trade_atr_metrics", "regime_ml_predicted", "VARCHAR(100)"),
            ("trade_atr_metrics", "session_market", "VARCHAR(100)"),
            
            # trades
            ("trades", "entry_cb_state", "VARCHAR(100)"),
            ("trades", "entry_market_regime", "VARCHAR(100)"),
            ("trades", "tp_sl_mode", "VARCHAR(100)")
        ]
        
        for table, col, new_type in migrations:
            try:
                print(f"  - Extension de {table}.{col} vers {new_type}...")
                cur.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {new_type};")
            except Exception as e:
                print(f"  ⚠️ Erreur sur {table}.{col}: {e}")
                conn.rollback()
                continue
            else:
                conn.commit()
        
        print("✅ Migration terminée avec succès.")
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erreur critique lors de la migration: {e}")

if __name__ == "__main__":
    migrate()
