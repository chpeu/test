"""
Script de test rapide pour valider la sauvegarde modèle V2
"""
import asyncio
import logging
from database.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_sauvegarde():
    """Tester la sauvegarde V2"""
    try:
        db = DatabaseManager()
        
        logger.info("🔍 Test sauvegarde modèle V2...\n")
        
        # 1. Vérifier table ml_models existe
        logger.info("1️⃣ Vérification table ml_models...")
        table_exists = await db.fetch_one("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ml_models'
            )
        """)
        
        if not table_exists or not table_exists['exists']:
            logger.error("❌ Table ml_models n'existe pas!")
            logger.info("👉 Exécuter: psql -d trading_db -f database/create_ml_models_table.sql")
            return
        
        logger.info("✅ Table ml_models existe\n")
        
        # 2. Vérifier colonnes V2
        logger.info("2️⃣ Vérification colonnes V2...")
        columns = await db.fetch("""
            SELECT column_name 
            FROM information_schema.columns
            WHERE table_name = 'ml_models'
              AND column_name IN ('train_r2', 'val_r2', 'test_r2', 'train_mae', 'val_mae', 'test_mae', 'test_f1')
            ORDER BY column_name
        """)
        
        if len(columns) < 7:
            logger.warning(f"⚠️ Seulement {len(columns)}/7 colonnes V2 trouvées!")
            logger.info("👉 Exécuter: python apply_migration_v2.py")
            for col in columns:
                logger.info(f"  ✓ {col['column_name']}")
        else:
            logger.info("✅ Toutes les colonnes V2 existent:")
            for col in columns:
                logger.info(f"  ✓ {col['column_name']}")
        
        print()
        
        # 3. Lister modèles V2 existants
        logger.info("3️⃣ Modèles V2 existants...")
        models = await db.fetch("""
            SELECT 
                model_name,
                version,
                test_r2,
                test_mae,
                total_samples,
                is_active,
                trained_at
            FROM ml_models
            WHERE model_name LIKE 'xgboost_v2%'
            ORDER BY trained_at DESC
            LIMIT 5
        """)
        
        if not models:
            logger.info("ℹ️ Aucun modèle V2 trouvé (normal si jamais entraîné)")
        else:
            logger.info(f"✅ {len(models)} modèle(s) V2 trouvé(s):")
            for model in models:
                active = "🟢 ACTIF" if model['is_active'] else "⚪"
                logger.info(f"  {active} {model['model_name']}")
                logger.info(f"     └─ R²={model['test_r2']:.3f}, MAE={model['test_mae']:.3f}, Samples={model['total_samples']}, Date={model['trained_at']}")
        
        print()
        
        # 4. Vérifier fichiers saved_models
        logger.info("4️⃣ Vérification fichiers saved_models...")
        import os
        from pathlib import Path
        
        models_dir = Path("optimization/saved_models")
        if not models_dir.exists():
            logger.warning("⚠️ Dossier optimization/saved_models n'existe pas!")
            logger.info("👉 Créer: mkdir -p optimization/saved_models")
        else:
            v2_files = list(models_dir.glob("xgboost_v2*.pkl"))
            if not v2_files:
                logger.info("ℹ️ Aucun fichier .pkl V2 trouvé (normal si jamais entraîné)")
            else:
                logger.info(f"✅ {len(v2_files)} fichier(s) V2 trouvé(s):")
                for file in sorted(v2_files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
                    size_kb = file.stat().st_size / 1024
                    logger.info(f"  📦 {file.name} ({size_kb:.1f} KB)")
        
        print()
        logger.info("=" * 60)
        logger.info("✅ Tests terminés!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_sauvegarde())
