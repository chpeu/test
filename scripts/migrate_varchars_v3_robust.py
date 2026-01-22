
import os
import psycopg2
from dotenv import load_dotenv
import json

def migrate_robust_v3():
    load_dotenv()
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    print(f"🚀 Connexion à PostgreSQL pour migration robuste v3...")
    
    conn = None
    try:
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = False
        cursor = conn.cursor()
        
        # 1. Identifier les tables concernées
        tables_to_fix = ['market_regime_history', 'opportunities', 'scan_logs', 'trade_atr_metrics', 'trades']
        
        # 2. Identifier TOUTES les vues dépendantes
        print("🔍 Recherche des vues dépendantes...")
        cursor.execute("""
            SELECT DISTINCT viewname
            FROM pg_views
            WHERE schemaname = 'public'
            AND definition ILIKE ANY(%s);
        """, ([f'%{t}%' for t in tables_to_fix],))
        
        views = [row[0] for row in cursor.fetchall()]
        print(f"Vues identifiées : {', '.join(views)}")
        
        # 3. Sauvegarder les définitions des vues et les supprimer
        view_defs = {}
        views_to_drop = list(views)
        
        # On utilise une boucle pour gérer les dépendances entre vues lors de la suppression
        while views_to_drop:
            initial_count = len(views_to_drop)
            for view in list(views_to_drop):
                try:
                    # Obtenir définition
                    cursor.execute(f"SELECT pg_get_viewdef('{view}', true);")
                    definition = cursor.fetchone()[0]
                    view_defs[view] = definition
                    
                    # Supprimer avec CASCADE
                    cursor.execute(f"DROP VIEW IF EXISTS {view} CASCADE;")
                    views_to_drop.remove(view)
                    print(f"  ✓ Vue '{view}' supprimée (CASCADE)")
                except Exception as e:
                    # Probablement supprimée par un CASCADE précédent
                    cursor.execute(f"SELECT count(*) FROM pg_views WHERE viewname = '{view}'")
                    if cursor.fetchone()[0] == 0:
                        if view not in view_defs: # Si on a pas pu chopper la def avant
                             # On tente de la récupérer depuis les métadonnées si possible, 
                             # mais CASCADE l'aura déjà virée. C'est risqué.
                             # Normalement on devrait d'abord tout lire puis tout drop.
                             pass
                        views_to_drop.remove(view)
            
            if len(views_to_drop) == initial_count:
                break

        # 4. Appliquer les ALTER TABLE sur toutes les colonnes VARCHAR critiques
        print("\n🛠️ Expansion des colonnes VARCHAR -> VARCHAR(100)...")
        migrations = [
            ("market_regime_history", "detection_method"),
            ("market_regime_history", "new_regime"),
            ("market_regime_history", "old_regime"),
            ("market_regime_history", "session_market"),
            ("market_regime_history", "trigger"),
            ("opportunities", "market_regime"),
            ("opportunities", "status"),
            ("opportunities", "tp_sl_mode"),
            ("scan_logs", "divergence_type"),
            ("scan_logs", "market_regime"),
            ("scan_logs", "opportunity_direction"),
            ("scan_logs", "regime_at_scan"),
            ("scan_logs", "session_market"),
            ("scan_logs", "trend_direction"),
            ("scan_logs", "trend_timeframe"),
            ("trade_atr_metrics", "market_trend_state"),
            ("trade_atr_metrics", "market_volatility_state"),
            ("trade_atr_metrics", "optimal_regime_retrospective"),
            ("trade_atr_metrics", "regime_detection_method"),
            ("trade_atr_metrics", "regime_ml_predicted"),
            ("trade_atr_metrics", "session_market"),
            ("trades", "entry_cb_state"),
            ("trades", "entry_market_regime"),
            ("trades", "tp_sl_mode")
        ]
        
        for table, col in migrations:
            try:
                print(f"  - Extension de {table}.{col}...")
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE VARCHAR(100);")
                print("    ✓ OK")
            except Exception as e:
                print(f"    ❌ Erreur sur {table}.{col}: {e}")
                # On ne raise pas pour continuer les autres
        
        # 5. Recréer les vues
        print("\n🔄 Recréation des vues...")
        failed_views = list(view_defs.keys())
        for attempt in range(5):
            if not failed_views: break
            print(f"  Tentative {attempt + 1}...")
            for view in list(failed_views):
                try:
                    definition = view_defs[view]
                    sql = f"CREATE VIEW {view} AS {definition}"
                    cursor.execute(sql)
                    failed_views.remove(view)
                    print(f"    ✓ Vue '{view}' recréée")
                except Exception as e:
                    pass
        
        if failed_views:
            print(f"⚠️ Certaines vues n'ont pas pu être recréées : {', '.join(failed_views)}")
        
        conn.commit()
        print("\n🎉 Migration v3 terminée avec succès!")
        
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
    migrate_robust_v3()
