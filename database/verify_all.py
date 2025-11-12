#!/usr/bin/env python3
"""
Script de vérification complète - PostgreSQL Datalogger
Vérifie le schéma, la connexion, et les données
"""

import os
import sys
import json

# Encodage UTF-8 pour Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', '')
}

def print_section(title):
    """Afficher un titre de section"""
    print(f"\n{'='*80}")
    print(f"🔍 {title}")
    print(f"{'='*80}")

def print_ok(message):
    """Afficher un message de succès"""
    print(f"✅ {message}")

def print_error(message):
    """Afficher un message d'erreur"""
    print(f"❌ {message}")

def print_warning(message):
    """Afficher un message d'avertissement"""
    print(f"⚠️ {message}")

def check_connection():
    """Vérifier la connexion PostgreSQL"""
    print_section("1. Vérification de la Connexion PostgreSQL")
    
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print_ok(f"Connexion réussie: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"   Version: {version.split(',')[0]}")
        cursor.close()
        conn.close()
        return True
    except ImportError:
        print_error("psycopg2 non installé - Installez avec: pip install psycopg2-binary")
        return False
    except Exception as e:
        print_error(f"Erreur connexion: {e}")
        return False

def check_schema():
    """Vérifier le schéma SQL"""
    print_section("2. Vérification du Schéma SQL")
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier les tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cursor.fetchall()]
        print_ok(f"Tables trouvées: {len(tables)}")
        for table in tables:
            print(f"   • {table}")
        
        # Vérifier trades
        if 'trades' in tables:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM information_schema.columns
                WHERE table_name = 'trades'
            """)
            count = cursor.fetchone()['count']
            print_ok(f"Colonnes dans trades: {count}")
            
            if count < 100:
                print_warning(f"Seulement {count} colonnes - La migration n'a peut-être pas été appliquée")
            else:
                print_ok(f"Nombre de colonnes OK ({count} colonnes)")
            
            # Vérifier colonnes spécifiques
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'trades'
                AND column_name IN (
                    'config_snapshot',
                    'early_invalidation_triggered',
                    'entry_rsi_prev_1m',
                    'entry_ema9_1m',
                    'entry_bb_upper_1m',
                    'exit_rsi_1m',
                    'entry_hour_of_day',
                    'exit_hour_of_day'
                )
                ORDER BY column_name
            """)
            important_cols = [row['column_name'] for row in cursor.fetchall()]
            print_ok(f"Colonnes importantes trouvées: {len(important_cols)}/8")
            for col in important_cols:
                print(f"   • {col}")
            
            if len(important_cols) < 8:
                missing = ['config_snapshot', 'early_invalidation_triggered', 'entry_rsi_prev_1m',
                          'entry_ema9_1m', 'entry_bb_upper_1m', 'exit_rsi_1m',
                          'entry_hour_of_day', 'exit_hour_of_day']
                missing = [c for c in missing if c not in important_cols]
                print_error(f"Colonnes manquantes: {', '.join(missing)}")
                print_warning("Exécutez: psql -U postgres -d trade_cursor_ml -f database/migration_complete_all_changes.sql")
        
        # Vérifier market_context
        if 'market_context' in tables:
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'market_context'
                AND column_name IN ('global_metrics', 'session_stats')
            """)
            jsonb_cols = cursor.fetchall()
            if len(jsonb_cols) == 2:
                print_ok("Colonnes JSONB market_context présentes")
            else:
                print_warning("Colonnes JSONB market_context manquantes")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"Erreur vérification schéma: {e}")
        return False

def check_data():
    """Vérifier les données"""
    print_section("3. Vérification des Données")
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Scans
        cursor.execute("SELECT COUNT(*) as count FROM scan_logs")
        scan_count = cursor.fetchone()['count']
        print(f"📊 Scans loggés: {scan_count}")
        if scan_count > 0:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM scan_logs
                WHERE rsi_1m IS NOT NULL
            """)
            scans_with_indicators = cursor.fetchone()['count']
            print_ok(f"   Scans avec indicateurs: {scans_with_indicators}/{scan_count}")
        else:
            print_warning("Aucun scan loggé - Attendez quelques minutes")
        
        # Opportunités
        cursor.execute("SELECT COUNT(*) as count FROM opportunities")
        opp_count = cursor.fetchone()['count']
        print(f"📊 Opportunités loggées: {opp_count}")
        
        # Trades
        cursor.execute("SELECT COUNT(*) as count FROM trades")
        trade_count = cursor.fetchone()['count']
        print(f"📊 Trades loggés: {trade_count}")
        
        if trade_count > 0:
            # Vérifier indicateurs d'entrée
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM trades
                WHERE entry_rsi_1m IS NOT NULL
            """)
            trades_with_entry_indicators = cursor.fetchone()['count']
            print_ok(f"   Trades avec indicateurs d'entrée: {trades_with_entry_indicators}/{trade_count}")
            
            # Vérifier config_snapshot
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM trades
                WHERE config_snapshot IS NOT NULL
            """)
            trades_with_config = cursor.fetchone()['count']
            print_ok(f"   Trades avec config_snapshot: {trades_with_config}/{trade_count}")
            
            # Vérifier early_invalidation
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM trades
                WHERE early_invalidation_triggered = TRUE
            """)
            early_invalidations = cursor.fetchone()['count']
            if early_invalidations > 0:
                print_ok(f"   Early invalidations: {early_invalidations}")
            
            # Vérifier trades fermés
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM trades
                WHERE timestamp_exit IS NOT NULL
            """)
            closed_trades = cursor.fetchone()['count']
            print(f"   Trades fermés: {closed_trades}/{trade_count}")
            
            if closed_trades > 0:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE win = TRUE) as wins,
                        COUNT(*) FILTER (WHERE win = FALSE) as losses
                    FROM trades
                    WHERE timestamp_exit IS NOT NULL
                """)
                stats = cursor.fetchone()
                print_ok(f"   Wins: {stats['wins']}, Losses: {stats['losses']}")
        else:
            print_warning("Aucun trade loggé - Ouvrez et fermez une position pour tester")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print_error(f"Erreur vérification données: {e}")
        return False

def check_config():
    """Vérifier la configuration"""
    print_section("4. Vérification de la Configuration")
    
    postgres_enabled = os.getenv('POSTGRES_ENABLED', 'false').lower() == 'true'
    if postgres_enabled:
        print_ok("POSTGRES_ENABLED=true")
    else:
        print_error("POSTGRES_ENABLED=false - Le datalogger ne fonctionnera pas")
    
    host = os.getenv('POSTGRES_HOST', 'localhost')
    db = os.getenv('POSTGRES_DB', 'trade_cursor_ml')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    
    print(f"   POSTGRES_HOST: {host}")
    print(f"   POSTGRES_DB: {db}")
    print(f"   POSTGRES_USER: {user}")
    if password:
        print_ok("   POSTGRES_PASSWORD: défini")
    else:
        print_error("   POSTGRES_PASSWORD: non défini")
    
    return postgres_enabled and bool(password)

def check_code():
    """Vérifier le code Python"""
    print_section("5. Vérification du Code Python")
    
    import py_compile
    import os
    
    base_path = os.path.dirname(os.path.dirname(__file__))
    files_to_check = [
        'core/postgresql_datalogger.py',
        'core/position_manager.py',
        'core/callbacks/scanner_loop.py'
    ]
    
    all_ok = True
    for file_path in files_to_check:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            try:
                py_compile.compile(full_path, doraise=True)
                print_ok(f"{file_path} - Syntaxe OK")
            except py_compile.PyCompileError as e:
                print_error(f"{file_path} - Erreur de syntaxe: {e}")
                all_ok = False
        else:
            print_warning(f"{file_path} - Fichier introuvable")
    
    return all_ok

def main():
    """Fonction principale"""
    print("="*80)
    print("🔍 VÉRIFICATION COMPLÈTE - PostgreSQL Datalogger")
    print("="*80)
    
    results = {
        'connection': False,
        'schema': False,
        'data': False,
        'config': False,
        'code': False
    }
    
    # Vérifications
    results['connection'] = check_connection()
    if not results['connection']:
        print_error("\n❌ Impossible de continuer sans connexion PostgreSQL")
        return 1
    
    results['config'] = check_config()
    results['schema'] = check_schema()
    results['data'] = check_data()
    results['code'] = check_code()
    
    # Résumé
    print_section("RÉSUMÉ")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for check, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check.upper()}")
    
    print(f"\n📊 Résultat: {passed}/{total} vérifications réussies")
    
    if passed == total:
        print_ok("\n🎉 TOUT EST OK ! Le datalogger est prêt.")
        return 0
    else:
        print_error(f"\n⚠️ {total - passed} vérification(s) ont échoué")
        print("\nConsultez database/VERIFICATION_COMPLETE.md pour plus de détails")
        return 1

if __name__ == '__main__':
    sys.exit(main())

