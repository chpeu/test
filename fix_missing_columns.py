#!/usr/bin/env python3
"""
Script pour créer manuellement les colonnes anti-giveback manquantes
"""

import os
import psycopg2
from dotenv import load_dotenv

def fix_missing_columns():
    load_dotenv()
    
    pg_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD'),
    }
    
    missing_columns = [
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS config_trailing_mfe_enabled BOOLEAN DEFAULT NULL",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_triggered BOOLEAN DEFAULT FALSE", 
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_mfe_new_sl DOUBLE PRECISION DEFAULT NULL"
    ]
    
    comments = [
        "COMMENT ON COLUMN trades.config_trailing_mfe_enabled IS 'Config: trailing MFE activé pour ce trade'",
        "COMMENT ON COLUMN trades.trailing_mfe_triggered IS 'True si Trailing MFE a déclenché (SL déplacé)'",
        "COMMENT ON COLUMN trades.trailing_mfe_new_sl IS 'SL appliqué au moment du déclenchement Trailing MFE'"
    ]
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_trade_trailing_mfe_triggered ON trades (trailing_mfe_triggered) WHERE trailing_mfe_triggered = TRUE",
        "CREATE INDEX IF NOT EXISTS idx_trade_exit_reason_sl_exchange ON trades (exit_reason) WHERE exit_reason = 'SL_EXCHANGE'"
    ]
    
    try:
        conn = psycopg2.connect(**pg_config)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Création des colonnes manquantes...")
        for i, stmt in enumerate(missing_columns, 1):
            try:
                cursor.execute(stmt)
                print(f"  [{i}/3] ✅ Colonne créée")
            except psycopg2.Error as e:
                if 'already exists' in str(e):
                    print(f"  [{i}/3] ⚠️ Déjà existante")
                else:
                    print(f"  [{i}/3] ❌ {e}")
        
        print("\nAjout des commentaires...")
        for i, stmt in enumerate(comments, 1):
            try:
                cursor.execute(stmt)
                print(f"  [{i}/3] ✅ Commentaire ajouté")
            except psycopg2.Error as e:
                print(f"  [{i}/3] ❌ {e}")
        
        print("\nCréation des index...")
        for i, stmt in enumerate(indexes, 1):
            try:
                cursor.execute(stmt)
                print(f"  [{i}/2] ✅ Index créé")
            except psycopg2.Error as e:
                if 'already exists' in str(e):
                    print(f"  [{i}/2] ⚠️ Déjà existant")
                else:
                    print(f"  [{i}/2] ❌ {e}")
        
        # Vérification finale
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND (column_name LIKE '%trailing_mfe%' OR column_name LIKE '%partial_tp_be%')
            ORDER BY column_name;
        """)
        
        final_columns = [row[0] for row in cursor.fetchall()]
        print(f"\n✅ Colonnes anti-giveback finales ({len(final_columns)}/9):")
        for col in final_columns:
            print(f"  - {col}")
        
        cursor.close()
        conn.close()
        
        return len(final_columns) >= 9
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    success = fix_missing_columns()
    if success:
        print("\n🎉 Migration complètement terminée!")
    else:
        print("\n⚠️ Migration encore incomplète.")
