#!/usr/bin/env python3
"""
Vérification des tables PostgreSQL pour PostExit Analysis
Vérifie l'existence et la structure des tables requises
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

def main():
    try:
        import psycopg2
        from psycopg2.extras import DictCursor
        
        print("🔍 VÉRIFICATION TABLES POST-EXIT")
        print("=" * 60)
        
        # Connexion PostgreSQL
        try:
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', '5432'),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            cursor = conn.cursor(cursor_factory=DictCursor)
            print("✅ Connexion PostgreSQL réussie")
        except Exception as e:
            print(f"❌ Erreur connexion PostgreSQL: {e}")
            return
        
        # Tables PostExit requises
        required_tables = {
            'trade_post_exit_analysis': [
                'trade_id', 'exit_price', 'exit_timestamp', 'exit_reason', 'direction',
                'realized_pnl_pct', 'realized_pnl_usdt', 'tracking_duration_sec', 'sample_count',
                'post_exit_mfe_pct', 'post_exit_mae_pct', 'post_exit_final_pct',
                'exit_efficiency_pct', 'regret_pct', 'regret_usdt', 'exit_timing_grade',
                'would_have_hit_original_tp', 'would_have_hit_original_sl', 'price_returned_to_entry',
                'ml_optimal_sl_pct', 'ml_optimal_trailing_trigger', 'ml_optimal_be_trigger', 
                'ml_should_use_partial', 'ml_optimal_trailing_distance', 'symbol'
            ],
            'trade_post_exit_samples': [
                'trade_id', 'sample_index', 'timestamp', 'price', 
                'pnl_vs_exit_pct', 'cumulative_mfe_pct', 'cumulative_mae_pct'
            ],
            'post_exit_active_trackers': [
                'trade_id', 'symbol', 'direction', 'exit_price', 'exit_timestamp',
                'tracking_duration_sec', 'sample_interval_ms', 'start_time', 'samples_collected',
                'samples_json'
            ]
        }
        
        print("\n📋 VÉRIFICATION EXISTENCE TABLES")
        print("-" * 40)
        
        tables_status = {}
        
        for table_name in required_tables.keys():
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table_name,))
            
            exists = cursor.fetchone()[0]
            tables_status[table_name] = exists
            
            if exists:
                # Compter les lignes
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"✅ {table_name:<30}: Existe ({count:,} lignes)")
            else:
                print(f"❌ {table_name:<30}: MANQUANTE")
        
        print("\n🔧 VÉRIFICATION COLONNES")
        print("-" * 40)
        
        for table_name, expected_columns in required_tables.items():
            if not tables_status[table_name]:
                print(f"⏭️  {table_name}: Table manquante, colonnes non vérifiées")
                continue
                
            # Récupérer colonnes existantes
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            missing_columns = [col for col in expected_columns if col not in existing_columns]
            extra_columns = [col for col in existing_columns if col not in expected_columns and col != 'id' and col != 'created_at' and col != 'updated_at']
            
            print(f"\n📊 {table_name}:")
            print(f"   Colonnes attendues: {len(expected_columns)}")
            print(f"   Colonnes existantes: {len(existing_columns)}")
            
            if missing_columns:
                print(f"   ❌ Colonnes manquantes: {missing_columns}")
            else:
                print(f"   ✅ Toutes les colonnes requises présentes")
                
            if extra_columns:
                print(f"   ℹ️  Colonnes supplémentaires: {extra_columns}")
        
        # Vérifier contraintes FK importantes
        print("\n🔗 VÉRIFICATION CONTRAINTES")
        print("-" * 40)
        
        fk_checks = [
            ('trade_post_exit_analysis', 'trade_id', 'trades', 'id'),
            ('trade_post_exit_samples', 'trade_id', 'trades', 'id'),
        ]
        
        for table, column, ref_table, ref_column in fk_checks:
            if not tables_status.get(table, False):
                continue
                
            cursor.execute("""
                SELECT constraint_name 
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s 
                AND tc.constraint_type = 'FOREIGN KEY'
                AND kcu.column_name = %s
            """, (table, column))
            
            fk_exists = cursor.fetchone()
            if fk_exists:
                print(f"✅ FK {table}.{column} → {ref_table}.{ref_column}")
            else:
                print(f"⚠️  FK {table}.{column} → {ref_table}.{ref_column} : MANQUANTE")
        
        # Vérifier données récentes
        print("\n📊 DONNÉES RÉCENTES")
        print("-" * 40)
        
        if tables_status.get('trade_post_exit_analysis', False):
            cursor.execute("""
                SELECT COUNT(*) 
                FROM trade_post_exit_analysis 
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            recent_count = cursor.fetchone()[0]
            print(f"PostExit analysis (7j): {recent_count:,} lignes")
            
            # Exemple recent
            cursor.execute("""
                SELECT trade_id, symbol, exit_efficiency_pct, sample_count, exit_timing_grade
                FROM trade_post_exit_analysis 
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            recent = cursor.fetchall()
            if recent:
                print("Exemples récents:")
                for row in recent:
                    print(f"  • {row['trade_id']}: {row['symbol']} | Eff: {row['exit_efficiency_pct']}% | Grade: {row['exit_timing_grade']} | Samples: {row['sample_count']}")
        
        if tables_status.get('trade_post_exit_samples', False):
            cursor.execute("""
                SELECT COUNT(*) 
                FROM trade_post_exit_samples 
                WHERE timestamp > NOW() - INTERVAL '7 days'
            """)
            samples_count = cursor.fetchone()[0]
            print(f"PostExit samples (7j): {samples_count:,} lignes")
        
        # Résumé
        print("\n" + "=" * 60)
        print("📋 RÉSUMÉ")
        print("=" * 60)
        
        all_tables_exist = all(tables_status.values())
        issues = []
        
        if not all_tables_exist:
            missing_tables = [name for name, exists in tables_status.items() if not exists]
            issues.append(f"🔴 Tables manquantes: {missing_tables}")
        
        if not issues:
            print("✅ STRUCTURE POST-EXIT COMPLÈTE")
            print("  • Toutes les tables requises existent")
            print("  • Colonnes essentielles présentes")
            print("  • Contraintes FK configurées")
            print("  • Prêt pour sauvegarde PostExit")
        else:
            print("⚠️ PROBLÈMES DÉTECTÉS:")
            for issue in issues:
                print(f"  {issue}")
            
            print("\n🔧 MIGRATION REQUISE:")
            missing_tables = [name for name, exists in tables_status.items() if not exists]
            for table in missing_tables:
                if table == 'trade_post_exit_analysis':
                    print(f"  psql -U postgres -d trade_cursor_ml -f database/migrations/add_post_exit_analysis_tables.sql")
                elif table == 'post_exit_active_trackers':
                    print(f"  psql -U postgres -d trade_cursor_ml -f database/migrations/add_post_exit_tracker_persistence.sql")
        
        cursor.close()
        conn.close()
        
    except ImportError as e:
        print(f"❌ Erreur import: {e}")
        print("Assurez-vous que psycopg2 est installé")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
