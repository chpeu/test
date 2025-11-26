#!/usr/bin/env python3
"""
Fix: Supprimer les colonnes entry_timestamp_live et exit_timestamp_live
qui font doublon avec entry_timestamp et exit_timestamp
"""
import sqlite3
import os

DB_PATH = "data/analytics.db"

def fix_db():
    if not os.path.exists(DB_PATH):
        print(f"[ERREUR] Base de données non trouvée: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Vérifier les colonnes existantes
    cur.execute("PRAGMA table_info(trades)")
    cols = cur.fetchall()
    col_names = [col[1] for col in cols]
    
    print(f"[INFO] Colonnes actuelles: {len(col_names)}")
    
    # Vérifier si les colonnes problématiques existent
    has_live_versions = 'entry_timestamp_live' in col_names or 'exit_timestamp_live' in col_names
    
    if not has_live_versions:
        print("[INFO] Pas de colonnes *_live à supprimer")
        conn.close()
        return True
    
    print("[INFO] Colonnes *_live détectées, migration nécessaire...")
    
    # SQLite ne supporte pas DROP COLUMN avant la version 3.35
    # On doit recréer la table sans ces colonnes
    
    # 1. Récupérer la liste des colonnes à conserver
    keep_cols = [col[1] for col in cols if col[1] not in ['entry_timestamp_live', 'exit_timestamp_live']]
    
    print(f"[INFO] Colonnes à conserver: {len(keep_cols)}")
    
    # 2. Créer une table temporaire
    print("[INFO] Création table temporaire...")
    
    # Construire le schéma de la nouvelle table (sans *_live)
    col_defs = []
    for col in cols:
        name = col[1]
        if name not in ['entry_timestamp_live', 'exit_timestamp_live']:
            ctype = col[2]
            notnull = col[3]
            dflt = col[4]
            pk = col[5]
            
            col_def = f"{name} {ctype}"
            if notnull:
                col_def += " NOT NULL"
            if dflt is not None:
                col_def += f" DEFAULT {dflt}"
            if pk:
                col_def += " PRIMARY KEY"
            
            col_defs.append(col_def)
    
    create_temp = f"CREATE TABLE trades_temp ({', '.join(col_defs)})"
    cur.execute(create_temp)
    
    # 3. Copier les données
    print("[INFO] Copie des données...")
    cols_str = ', '.join(keep_cols)
    cur.execute(f"INSERT INTO trades_temp ({cols_str}) SELECT {cols_str} FROM trades")
    
    # 4. Supprimer l'ancienne table
    print("[INFO] Suppression ancienne table...")
    cur.execute("DROP TABLE trades")
    
    # 5. Renommer la table temporaire
    print("[INFO] Renommage table...")
    cur.execute("ALTER TABLE trades_temp RENAME TO trades")
    
    # 6. Recréer les index
    print("[INFO] Recréation des index...")
    indices = [
        'CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)',
        'CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)',
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
            print(f"[WARN] Index: {e}")
    
    conn.commit()
    
    # 7. Vérifier résultat
    cur.execute("PRAGMA table_info(trades)")
    new_cols = cur.fetchall()
    print(f"[INFO] Nombre final de colonnes: {len(new_cols)}")
    
    conn.close()
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Fix SQLite: Suppression colonnes *_live en doublon")
    print("=" * 60)
    
    success = fix_db()
    
    print("=" * 60)
    if success:
        print("[OK] Fix terminé avec succès")
        print("[INFO] Relancez le backend")
    else:
        print("[ERREUR] Fix échoué")
    print("=" * 60)
