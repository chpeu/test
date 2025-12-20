"""
Script de vérification pour LightGBM Trainer
"""
import logging
import sys
import os
from pathlib import Path

# Ajouter la racine du projet au path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from optimization.models.lightgbm_trainer import LightGBMTrainer

def verify_lightgbm():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("VerifyLightGBM")
    
    logger.info("🚀 Démarrage vérification LightGBM Trainer...")
    
    try:
        trainer = LightGBMTrainer(model_name="lightgbm_verification")
        
        # Entraînement sur une petite période pour test rapide
        results = trainer.train(
            timeframe_days=60,
            min_trades=50,
            test_size=0.2,
            n_estimators=50,  # Réduit pour rapidité
            load_optuna_params=False  # Désactivé pour test
        )
        
        logger.info("\n✅ Vérification terminée avec succès!")
        logger.info(f"Accuracy Test: {results['metrics']['test']['accuracy']:.3f}")
        logger.info(f"ROC-AUC Test: {results['metrics']['test']['roc_auc']:.3f}")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Erreur durant la vérification: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    verify_lightgbm()
