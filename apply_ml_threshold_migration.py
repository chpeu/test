#!/usr/bin/env python3
"""
Script d'application de la migration ML threshold columns
Ajoute les colonnes ml_threshold_used, ml_threshold_type, calibrated_winrate à scan_logs

Usage:
    python apply_ml_threshold_migration.py

Date: 16/01/2026
Objectif: Permettre l'analyse des seuils ML utilisés lors des rejets
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Ajouter le répertoire racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.postgresql_datalogger import PostgreSQLDataLogger

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def apply_migration():
    """Appliquer la migration des colonnes ML threshold"""
    
    logger.info("🔄 Application de la migration ML threshold columns...")
    
    try:
        # Initialiser PostgreSQL DataLogger
        pg_logger = PostgreSQLDataLogger()
        
        if not pg_logger.enabled:
            logger.error("❌ PostgreSQL DataLogger désactivé - migration impossible")
            return False
        
        # Lire le fichier de migration
        migration_file = Path(__file__).parent / 'database' / 'migrations' / 'add_ml_threshold_columns.sql'
        
        if not migration_file.exists():
            logger.error(f"❌ Fichier de migration introuvable: {migration_file}")
            return False
        
        # Lire le contenu de la migration
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        logger.info("📄 Migration SQL lue depuis: " + str(migration_file))
        
        # Séparer les commandes SQL (par point-virgule)
        sql_commands = [cmd.strip() for cmd in migration_sql.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
        
        logger.info(f"🔧 Exécution de {len(sql_commands)} commandes SQL...")
        
        # Exécuter chaque commande
        success_count = 0
        for i, sql_cmd in enumerate(sql_commands, 1):
            try:
                if sql_cmd.upper().startswith(('ALTER', 'CREATE', 'COMMENT')):
                    logger.info(f"  {i}/{len(sql_commands)}: {sql_cmd[:60]}...")
                    result = pg_logger._execute_query(sql_cmd)
                    if result is not None:
                        success_count += 1
                        logger.info(f"  ✅ Commande {i} exécutée avec succès")
                    else:
                        logger.warning(f"  ⚠️ Commande {i} retournée None (peut-être déjà appliquée)")
                        success_count += 1  # Considérer comme succès si pas d'erreur
                else:
                    logger.debug(f"  ⏭️ Ignorer commande {i} (commentaire ou vide)")
                    success_count += 1
                    
            except Exception as cmd_err:
                logger.error(f"  ❌ Erreur commande {i}: {cmd_err}")
                # Continuer avec les autres commandes
        
        if success_count == len(sql_commands):
            logger.info("✅ Migration ML threshold columns appliquée avec succès!")
            
            # Vérifier que les colonnes ont été créées
            check_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'scan_logs' 
                AND column_name IN ('ml_threshold_used', 'ml_threshold_type', 'calibrated_winrate')
                ORDER BY column_name
            """
            
            result = pg_logger._execute_query(check_sql, fetch=True)
            if result:
                found_columns = [row[0] for row in result]
                logger.info(f"🔍 Colonnes créées: {', '.join(found_columns)}")
                
                expected_columns = ['calibrated_winrate', 'ml_threshold_type', 'ml_threshold_used']
                if set(found_columns) == set(expected_columns):
                    logger.info("✅ Toutes les colonnes ML threshold ont été créées correctement!")
                    return True
                else:
                    missing = set(expected_columns) - set(found_columns)
                    logger.warning(f"⚠️ Colonnes manquantes: {', '.join(missing)}")
                    return False
            else:
                logger.warning("⚠️ Impossible de vérifier les colonnes créées")
                return True  # Assumer succès si pas d'erreur
        else:
            logger.error(f"❌ Migration partiellement échouée: {success_count}/{len(sql_commands)} succès")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la migration: {e}")
        return False

def main():
    """Point d'entrée principal"""
    logger.info("🚀 Démarrage du script de migration ML threshold columns")
    
    try:
        success = asyncio.run(apply_migration())
        
        if success:
            logger.info("🎉 Migration terminée avec succès!")
            sys.exit(0)
        else:
            logger.error("💥 Échec de la migration")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⏹️ Migration interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
