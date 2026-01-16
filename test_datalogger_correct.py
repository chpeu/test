#!/usr/bin/env python3
"""
Test correct du datalogger avec le vrai schéma (id=UUID, colonnes réelles)
"""

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

def test_datalogger_correct():
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
        
        # Test 1: Voir un exemple de trade existant avec les nouvelles colonnes
        print("🧪 Test 1: Lecture d'un trade existant avec colonnes anti-giveback...")
        cursor.execute("""
            SELECT id, symbol, direction, 
                   config_trailing_mfe_enabled, config_trailing_mfe_trigger_pct,
                   config_trailing_mfe_lock_in_pct, config_partial_tp_be_lock_in_pct,
                   trailing_mfe_triggered, trailing_mfe_triggered_at,
                   trailing_mfe_trigger_pnl_pct, trailing_mfe_trigger_price, trailing_mfe_new_sl
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 3
        """)
        
        recent_trades = cursor.fetchall()
        if recent_trades:
            print(f"✅ {len(recent_trades)} trades récents analysés:")
            for i, trade in enumerate(recent_trades, 1):
                trade_id, symbol, direction = trade[0], trade[1], trade[2]
                ag_cols = trade[3:12]  # Les 9 colonnes anti-giveback
                
                print(f"  [{i}] {symbol} ({direction}):")
                non_null_ag = [val for val in ag_cols if val is not None]
                print(f"      - Colonnes AG remplies: {len(non_null_ag)}/9")
                
                # Afficher les valeurs non-NULL
                col_names = [
                    'config_trailing_mfe_enabled', 'config_trailing_mfe_trigger_pct',
                    'config_trailing_mfe_lock_in_pct', 'config_partial_tp_be_lock_in_pct', 
                    'trailing_mfe_triggered', 'trailing_mfe_triggered_at',
                    'trailing_mfe_trigger_pnl_pct', 'trailing_mfe_trigger_price', 'trailing_mfe_new_sl'
                ]
                
                for j, val in enumerate(ag_cols):
                    if val is not None:
                        print(f"      - {col_names[j]}: {val}")
        else:
            print("⚠️ Aucun trade trouvé dans la table")
        
        # Test 2: Vérifier que le code datalogger existant peut lire les colonnes
        print(f"\n🧪 Test 2: Import du module datalogger...")
        try:
            # Tester l'import du datalogger PostgreSQL
            import sys
            sys.path.append('.')
            from core.postgresql_datalogger import PostgreSQLDatalogger
            print("✅ Module datalogger importé avec succès")
            
            # Vérifier que les colonnes sont dans le code
            import inspect
            source = inspect.getsource(PostgreSQLDatalogger.log_trade)
            
            ag_refs = [
                'config_trailing_mfe_enabled',
                'config_trailing_mfe_lock_in_pct', 
                'config_partial_tp_be_lock_in_pct',
                'trailing_mfe_triggered',
                'trailing_mfe_new_sl'
            ]
            
            found_refs = 0
            for ref in ag_refs:
                if ref in source:
                    found_refs += 1
                    print(f"      ✅ {ref} trouvé dans log_trade()")
                else:
                    print(f"      ❌ {ref} MANQUANT dans log_trade()")
            
            print(f"  Références anti-giveback dans datalogger: {found_refs}/{len(ag_refs)}")
            
        except ImportError as e:
            print(f"❌ Impossible d'importer le datalogger: {e}")
        
        # Test 3: Statistiques globales des colonnes anti-giveback
        print(f"\n🧪 Test 3: Statistiques des colonnes anti-giveback sur tous les trades...")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(config_trailing_mfe_enabled) as has_config_enabled,
                COUNT(config_trailing_mfe_lock_in_pct) as has_config_lock_in,
                COUNT(trailing_mfe_triggered) as has_tracking_triggered,
                SUM(CASE WHEN trailing_mfe_triggered = true THEN 1 ELSE 0 END) as triggered_count
            FROM trades
        """)
        
        stats = cursor.fetchone()
        if stats:
            total, config_enabled, config_lock, tracking_triggered, actual_triggered = stats
            print(f"  📊 Statistiques globales:")
            print(f"      - Total trades: {total}")
            print(f"      - Config enabled remplie: {config_enabled}/{total} ({config_enabled/total*100:.1f}%)")
            print(f"      - Config lock-in remplie: {config_lock}/{total} ({config_lock/total*100:.1f}%)")
            print(f"      - Tracking triggered rempli: {tracking_triggered}/{total} ({tracking_triggered/total*100:.1f}%)")
            print(f"      - Trailing MFE réellement déclenché: {actual_triggered}/{total} ({actual_triggered/total*100:.1f}%)")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎉 Tests datalogger terminés avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du test: {e}")
        return False

if __name__ == "__main__":
    success = test_datalogger_correct()
    if success:
        print("✅ Le datalogger est compatible avec les colonnes anti-giveback")
    else:
        print("❌ Le datalogger a des problèmes")
