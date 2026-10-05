#!/usr/bin/env python3
"""
Test que le datalogger PostgreSQL peut correctement insérer/lire 
les nouvelles colonnes anti-giveback dans la table trades.
"""

import os
import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv

def test_datalogger_columns():
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    try:
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Test 1: Insertion d'un trade de test avec toutes les nouvelles colonnes
        test_data = {
            'trade_id': f'TEST_ANTIGIVEBACK_{int(datetime.now().timestamp())}',
            'symbol': 'TESTUSDT',
            'direction': 'LONG',
            'entry': 1.0,
            'exit': 1.05,
            'exit_reason': 'TP',
            'pnl_pct': 5.0,
            'pnl_usdt': 50.0,
            'created_at': datetime.now(),
            'closed_at': datetime.now(),
            # Nouvelles colonnes config
            'config_trailing_mfe_enabled': True,
            'config_trailing_mfe_trigger_pct': 2.5,
            'config_trailing_mfe_lock_in_pct': 0.8,
            'config_partial_tp_be_lock_in_pct': 0.5,
            # Nouvelles colonnes tracking
            'trailing_mfe_triggered': True,
            'trailing_mfe_triggered_at': datetime.now(),
            'trailing_mfe_trigger_pnl_pct': 3.2,
            'trailing_mfe_trigger_price': 1.032,
            'trailing_mfe_new_sl': 1.008
        }
        
        insert_sql = """
            INSERT INTO trades (
                trade_id, symbol, direction, entry, exit, exit_reason, 
                pnl_pct, pnl_usdt, created_at, closed_at,
                config_trailing_mfe_enabled, config_trailing_mfe_trigger_pct,
                config_trailing_mfe_lock_in_pct, config_partial_tp_be_lock_in_pct,
                trailing_mfe_triggered, trailing_mfe_triggered_at,
                trailing_mfe_trigger_pnl_pct, trailing_mfe_trigger_price, trailing_mfe_new_sl
            ) VALUES (
                %(trade_id)s, %(symbol)s, %(direction)s, %(entry)s, %(exit)s, %(exit_reason)s,
                %(pnl_pct)s, %(pnl_usdt)s, %(created_at)s, %(closed_at)s,
                %(config_trailing_mfe_enabled)s, %(config_trailing_mfe_trigger_pct)s,
                %(config_trailing_mfe_lock_in_pct)s, %(config_partial_tp_be_lock_in_pct)s,
                %(trailing_mfe_triggered)s, %(trailing_mfe_triggered_at)s,
                %(trailing_mfe_trigger_pnl_pct)s, %(trailing_mfe_trigger_price)s, %(trailing_mfe_new_sl)s
            )
        """
        
        print("🧪 Test 1: Insertion trade de test avec colonnes anti-giveback...")
        cursor.execute(insert_sql, test_data)
        print("✅ Insertion réussie")
        
        # Test 2: Lecture du trade inséré
        print("\n🧪 Test 2: Lecture des colonnes anti-giveback...")
        cursor.execute("""
            SELECT 
                trade_id,
                config_trailing_mfe_enabled, config_trailing_mfe_trigger_pct,
                config_trailing_mfe_lock_in_pct, config_partial_tp_be_lock_in_pct,
                trailing_mfe_triggered, trailing_mfe_triggered_at,
                trailing_mfe_trigger_pnl_pct, trailing_mfe_trigger_price, trailing_mfe_new_sl
            FROM trades 
            WHERE trade_id = %s
        """, (test_data['trade_id'],))
        
        result = cursor.fetchone()
        if result:
            print("✅ Trade lu avec succès:")
            columns = [
                'trade_id', 'config_trailing_mfe_enabled', 'config_trailing_mfe_trigger_pct',
                'config_trailing_mfe_lock_in_pct', 'config_partial_tp_be_lock_in_pct',
                'trailing_mfe_triggered', 'trailing_mfe_triggered_at',
                'trailing_mfe_trigger_pnl_pct', 'trailing_mfe_trigger_price', 'trailing_mfe_new_sl'
            ]
            for i, col in enumerate(columns):
                print(f"  - {col}: {result[i]}")
        else:
            print("❌ Trade de test non trouvé")
            return False
        
        # Test 3: Vérifier que les colonnes acceptent NULL
        print("\n🧪 Test 3: Insertion avec colonnes NULL...")
        test_null_data = {
            'trade_id': f'TEST_NULL_{int(datetime.now().timestamp())}',
            'symbol': 'NULLUSDT',
            'direction': 'SHORT',
            'entry': 2.0,
            'exit': 1.9,
            'exit_reason': 'SL',
            'pnl_pct': -5.0,
            'pnl_usdt': -25.0,
            'created_at': datetime.now(),
            'closed_at': datetime.now()
            # Toutes les colonnes anti-giveback en NULL (par défaut)
        }
        
        cursor.execute("""
            INSERT INTO trades (
                trade_id, symbol, direction, entry, exit, exit_reason, 
                pnl_pct, pnl_usdt, created_at, closed_at
            ) VALUES (
                %(trade_id)s, %(symbol)s, %(direction)s, %(entry)s, %(exit)s, %(exit_reason)s,
                %(pnl_pct)s, %(pnl_usdt)s, %(created_at)s, %(closed_at)s
            )
        """, test_null_data)
        print("✅ Insertion avec NULL réussie")
        
        # Nettoyage: supprimer les trades de test
        print("\n🧹 Nettoyage des trades de test...")
        cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'TEST_%'")
        deleted_count = cursor.rowcount
        print(f"✅ {deleted_count} trades de test supprimés")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Tous les tests datalogger sont passés!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test datalogger: {e}")
        return False

if __name__ == "__main__":
    success = test_datalogger_columns()
    if success:
        print("✅ Le datalogger est compatible avec les nouvelles colonnes anti-giveback")
    else:
        print("❌ Le datalogger a des problèmes avec les nouvelles colonnes")
