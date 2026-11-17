#!/usr/bin/env python3
"""
Script d'application de la migration model_version pour ml_calibration
"""

import sys
import os
import logging

# Ajouter le répertoire du projet au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def apply_model_version_migration():
    """Applique la migration model_version à la table ml_calibration"""
    try:
        # Import des modules DB
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        logger.info("🔧 Application migration model_version...")
        
        # Créer une instance du datalogger
        pg_logger = PostgreSQLDataLogger()
        
        # Obtenir une connexion
        conn = pg_logger.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # Vérifier si la colonne existe déjà
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'ml_calibration' 
                    AND column_name = 'model_version'
                """)
                
                if cur.fetchone():
                    logger.info("✅ Colonne model_version existe déjà")
                    return True
                
                logger.info("📝 Ajout colonne model_version...")
                
                # Ajouter la colonne model_version
                cur.execute("""
                    ALTER TABLE ml_calibration 
                    ADD COLUMN model_version VARCHAR(50) DEFAULT NULL
                """)
                
                # Ajouter l'index
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ml_calibration_model_version 
                    ON ml_calibration(model_version)
                """)
                
                # Ajouter le commentaire
                cur.execute("""
                    COMMENT ON COLUMN ml_calibration.model_version IS 
                    'Timestamp du modèle GB utilisé pour cette calibration (format: 2025-12-20T00:41:39.610296)'
                """)
                
                # Commit des changements
                conn.commit()
                
                logger.info("✅ Migration model_version appliquée avec succès")
                return True
                
        finally:
            # Remettre la connexion dans le pool
            pg_logger.pool.putconn(conn)
            
    except Exception as e:
        logger.error(f"❌ Erreur migration: {e}")
        return False

def test_auto_reset_after_migration():
    """Teste le système auto-reset après la migration"""
    try:
        logger.info("🧪 Test auto-reset après migration...")
        
        from ml.calibration import MLCalibrationManager
        
        calibration_manager = MLCalibrationManager()
        
        # Test de détection du modèle
        model_info = calibration_manager.get_current_model_info()
        logger.info(f"📊 Modèle détecté: {model_info.get('timestamp', 'unknown')}")
        
        # Test de vérification de version
        last_version = calibration_manager.get_last_calibration_model_version()
        logger.info(f"📋 Dernière version calibrée: {last_version}")
        
        # Test d'auto-reset
        reset_performed = calibration_manager.check_model_change_and_auto_reset()
        
        if reset_performed:
            logger.info("✅ Auto-reset exécuté avec succès!")
        else:
            logger.info("ℹ️ Pas de reset nécessaire")
        
        # Test should_take_trade
        should_take, calibrated_wr, reason = calibration_manager.should_take_trade("LONG", 50.0)
        logger.info(f"🎯 Test trade LONG 50%: {'ACCEPT' if should_take else 'REJECT'} (WR={calibrated_wr}%, raison={reason})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur test auto-reset: {e}")
        return False

def main():
    """Fonction principale"""
    logger.info("🚀 === MIGRATION MODEL_VERSION POUR ML CALIBRATION ===")
    
    # 1. Appliquer la migration
    if not apply_model_version_migration():
        logger.error("❌ Échec de la migration")
        return False
    
    # 2. Tester l'auto-reset
    if not test_auto_reset_after_migration():
        logger.error("❌ Échec du test auto-reset")
        return False
    
    logger.info("🎉 Migration et tests terminés avec succès!")
    logger.info("📋 L'auto-reset calibration est maintenant 100% opérationnel")
    logger.info("🔄 Le prochain réentraînement GB déclenchera automatiquement un reset")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
