#!/usr/bin/env python3
"""
Script de démarrage du Dashboard de Monitoring de Refactoring
Lance le serveur Flask avec toutes les configurations nécessaires
"""

import sys
import os
import logging
from pathlib import Path

# Ajouter le répertoire courant au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.monitoring.refactoring_dashboard import create_dashboard, RefactoringDashboard
from core.feature_flags import get_feature_flags_manager

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('refactoring_dashboard.log')
    ]
)

logger = logging.getLogger(__name__)


def initialize_feature_flags():
    """Initialise les feature flags pour le refactoring"""
    logger.info("🔧 Initialisation des feature flags...")
    
    fm = get_feature_flags_manager()
    
    # Vérifier les flags existants
    flags_status = fm.list_all_flags()
    logger.info(f"📊 {len(flags_status)} feature flags détectés")
    
    for flag_name, status in flags_status.items():
        enabled = "✅" if status.get('enabled', False) else "❌"
        rollout = status.get('rollout_percentage', 0)
        logger.info(f"  {enabled} {flag_name}: {rollout}%")
    
    return fm


def setup_dashboard_environment():
    """Prépare l'environnement pour le dashboard"""
    logger.info("🚀 Configuration environnement dashboard...")
    
    # Créer dossiers nécessaires s'ils n'existent pas
    required_dirs = [
        'core/monitoring',
        'templates',
        'static',
        'logs'
    ]
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Dossier créé: {dir_name}")
    
    # Vérifier template HTML
    template_path = Path('templates/refactoring_dashboard.html')
    if template_path.exists():
        logger.info("✅ Template HTML trouvé")
    else:
        logger.warning("⚠️ Template HTML manquant")


def main():
    """Fonction principale"""
    print("\n" + "="*60)
    print("🔧 DASHBOARD REFACTORING - Trade Cursor v7.0")
    print("="*60 + "\n")
    
    try:
        # 1. Préparer environnement
        setup_dashboard_environment()
        
        # 2. Initialiser feature flags
        fm = initialize_feature_flags()
        
        # 3. Créer dashboard
        logger.info("🌐 Création du dashboard Flask...")
        dashboard = create_dashboard(host='localhost', port=5001)
        
        # 4. Démarrer monitoring automatique
        logger.info("🔍 Démarrage du monitoring automatique...")
        dashboard.start_monitoring()
        
        print("\n" + "🟢 DASHBOARD PRÊT!")
        print("━" * 40)
        print(f"🌐 URL: http://localhost:5001")
        print(f"📊 Monitoring: ACTIF")
        print(f"🎯 Feature Flags: {len(fm.list_all_flags())} configurés")
        print("━" * 40)
        print("\nℹ️  Fonctionnalités disponibles:")
        print("   • Monitoring temps réel des métriques")
        print("   • Contrôle des feature flags")
        print("   • Alertes automatiques")
        print("   • Rollback d'urgence")
        print("   • Comparaison Legacy vs Nouveau")
        print("\n⚠️  Pour arrêter: Ctrl+C")
        print("="*60 + "\n")
        
        # 5. Lancer serveur Flask
        dashboard.run(debug=False)
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Arrêt du dashboard demandé par l'utilisateur")
        print("\n🔴 Dashboard arrêté proprement.")
        
    except Exception as e:
        logger.error(f"💥 Erreur critique: {e}")
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)
    
    finally:
        logger.info("🏁 Nettoyage et fermeture")


if __name__ == '__main__':
    main()
