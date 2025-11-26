"""
Script pour appliquer la migration V2 (métriques régression)
Execute ce script avant de lancer l'entraînement V2
"""
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Charger .env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())
    logger.info("✅ .env chargé")

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

def apply_migration():
    """Appliquer la migration pour ajouter colonnes V2"""
    if not PSYCOPG2_AVAILABLE:
        logger.error("❌ psycopg2 non disponible! Installer avec: pip install psycopg2-binary")
        return
    
    try:
        # Connexion PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        cursor = conn.cursor()
        
        logger.info("🚀 Application migration V2...")
        
        # Commandes SQL individuelles
        commands = [
            # Colonnes R²
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_r2 DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_r2 DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_r2 DOUBLE PRECISION",
            
            # Colonnes MAE
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_mae DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_mae DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_mae DOUBLE PRECISION",
            
            # Colonnes MSE
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS train_mse DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS val_mse DOUBLE PRECISION",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_mse DOUBLE PRECISION",
            
            # F1 Score
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS test_f1 DOUBLE PRECISION",
            
            # Features
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS selected_features JSONB",
            "ALTER TABLE ml_models ADD COLUMN IF NOT EXISTS feature_selection_scores JSONB",
        ]
        
        # Exécuter chaque commande
        for i, cmd in enumerate(commands, 1):
            try:
                cursor.execute(cmd)
                logger.info(f"  ✓ Commande {i}/{len(commands)} OK")
            except Exception as e:
                logger.warning(f"  ⚠️ Commande {i}: {e}")
        
        conn.commit()
        logger.info("✅ Migration appliquée avec succès!")
        
        # Vérifier les nouvelles colonnes
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns
            WHERE table_name = 'ml_models'
              AND column_name IN ('train_r2', 'val_r2', 'test_r2', 'train_mae', 'val_mae', 'test_mae', 'test_f1', 'selected_features')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        if columns:
            logger.info("\n✅ Colonnes V2 créées:")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]}")
        else:
            logger.warning("⚠️ Aucune colonne V2 trouvée!")
        
        # Vérifier table ml_models existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ml_models'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            logger.info("\n✅ Table ml_models existe")
            
            # Compter modèles existants
            cursor.execute("SELECT COUNT(*) FROM ml_models")
            count = cursor.fetchone()[0]
            logger.info(f"📊 Modèles existants: {count}")
        else:
            logger.error("\n❌ Table ml_models n'existe pas!")
            logger.info("👉 Exécuter d'abord: psql -d trade_cursor_ml -f database/create_ml_models_table.sql")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Erreur migration: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    apply_migration()
