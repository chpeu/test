import os
import psycopg2
from dotenv import load_dotenv
import json

def apply_migration_robust():
    load_dotenv()
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print(f"Connexion à PostgreSQL: {pg_config['user']}@{pg_config['host']}:{pg_config['port']}/{pg_config['database']}")
    
    conn = None
    try:
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = False
        cursor = conn.cursor()
        
        # 1. Identifier les vues dépendantes
        # On cherche toutes les vues qui dépendent des tables concernées
        tables_to_fix = ['scan_logs', 'opportunities', 'trades', 'scan_errors']
        
        print("🔍 Recherche des vues dépendantes...")
        cursor.execute("""
            SELECT DISTINCT viewname
            FROM pg_views
            WHERE schemaname = 'public'
            AND definition ILIKE ANY(%s);
        """, ([f'%{t}%' for t in tables_to_fix],))
        
        views = [row[0] for row in cursor.fetchall()]
        print(f"Vues identifiées : {', '.join(views)}")
        
        # 2. Sauvegarder les définitions des vues et les supprimer
        view_defs = {}
        # Ordre de suppression (on essaie de gérer les dépendances entre vues si possible)
        # Pour faire simple, on va tenter de les supprimer une par une et recommencer si ça échoue à cause de dépendances
        views_to_drop = list(views)
        dropped_views = []
        
        while views_to_drop:
            initial_count = len(views_to_drop)
            for view in list(views_to_drop):
                try:
                    # Obtenir définition
                    cursor.execute(f"SELECT pg_get_viewdef('{view}', true);")
                    definition = cursor.fetchone()[0]
                    view_defs[view] = definition
                    
                    # Supprimer
                    cursor.execute(f"DROP VIEW IF EXISTS {view} CASCADE;")
                    dropped_views.append(view)
                    views_to_drop.remove(view)
                    print(f"  ✓ Vue '{view}' supprimée (CASCADE)")
                except Exception as e:
                    # Probablement une autre vue dépend de celle-ci, CASCADE devrait gérer ça
                    # mais on garde l'erreur au cas où
                    print(f"  ⚠️ Erreur lors de la suppression de '{view}': {e}")
                    conn.rollback()
                    # Si CASCADE a supprimé la vue indirectement, elle n'est plus là
                    cursor.execute(f"SELECT count(*) FROM pg_views WHERE viewname = '{view}'")
                    if cursor.fetchone()[0] == 0:
                        views_to_drop.remove(view)
            
            if len(views_to_drop) == initial_count:
                # On tourne en rond
                print("❌ Impossible de supprimer certaines vues.")
                break

        # 3. Appliquer les ALTER TABLE
        print("\n🛠️ Expansion des colonnes VARCHAR(30) -> VARCHAR(100)...")
        alter_statements = [
            "ALTER TABLE scan_logs ALTER COLUMN symbol TYPE VARCHAR(100);",
            "ALTER TABLE opportunities ALTER COLUMN symbol TYPE VARCHAR(100);",
            "ALTER TABLE trades ALTER COLUMN symbol TYPE VARCHAR(100);",
            "ALTER TABLE scan_errors ALTER COLUMN symbol TYPE VARCHAR(100);",
            "ALTER TABLE trades ALTER COLUMN exit_reason TYPE VARCHAR(100);"
        ]
        
        for sql in alter_statements:
            try:
                print(f"  Exécution: {sql}")
                cursor.execute(sql)
                print("  ✓ OK")
            except Exception as e:
                print(f"  ❌ Erreur: {e}")
                raise

        # 4. Recréer les vues (dans l'ordre inverse de suppression si possible)
        print("\n🔄 Recréation des vues...")
        # On tente de recréer plusieurs fois pour gérer les dépendances (une vue dépendant d'une autre)
        recreated_views = []
        failed_views = list(view_defs.keys())
        
        for attempt in range(5):
            if not failed_views: break
            print(f"  Tentative {attempt + 1}...")
            for view in list(failed_views):
                try:
                    definition = view_defs[view]
                    # S'assurer que la définition se termine par ; si nécessaire ou est bien formée
                    sql = f"CREATE VIEW {view} AS {definition}"
                    cursor.execute(sql)
                    recreated_views.append(view)
                    failed_views.remove(view)
                    print(f"    ✓ Vue '{view}' recréée")
                except Exception as e:
                    # Probablement une dépendance manquante pour l'instant
                    pass
        
        if failed_views:
            print(f"⚠️ Certaines vues n'ont pas pu être recréées : {', '.join(failed_views)}")
            # On affiche l'erreur de la première vue qui a échoué pour debug
            try:
                view = failed_views[0]
                cursor.execute(f"CREATE VIEW {view} AS {view_defs[view]}")
            except Exception as e:
                print(f"Détail erreur pour '{view}': {e}")
        
        # 5. Commit final
        conn.commit()
        print("\n🎉 Migration terminée avec succès!")
        
        # Vérification finale
        print("\n🔍 Vérification des types:")
        for table in tables_to_fix:
            cursor.execute(f"""
                SELECT column_name, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = '{table}' AND column_name IN ('symbol', 'exit_reason');
            """)
            for col, length in cursor.fetchall():
                print(f"  - {table}.{col}: {length}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"💥 Erreur fatale: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    apply_migration_robust()
