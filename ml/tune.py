"""
CLI pour optimisation d'hyperparamètres ML
Usage: python -m ml.tune [options]
"""
import argparse
import sys
import logging
from typing import Optional
import json

from ml.hyperparameter_tuning import (
    HyperparameterTuner,
    run_optimization
)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def detect_gpu() -> Optional[int]:
    """
    Détecter si GPU CUDA disponible
    
    Returns:
        GPU ID ou None
    """
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"🎮 GPU détecté: {gpu_name} ({gpu_count} GPU(s) disponibles)")
            return 0
    except ImportError:
        pass
    
    try:
        import tensorflow as tf
        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            logger.info(f"🎮 GPU détecté: {len(gpus)} GPU(s) TensorFlow")
            return 0
    except ImportError:
        pass
    
    logger.info("💻 Pas de GPU détecté, utilisation CPU multi-core")
    return None


def cmd_optimize(args):
    """Lancer optimisation"""
    logger.info("\n" + "="*80)
    logger.info("🎯 OPTIMISATION HYPERPARAMÈTRES ML")
    logger.info("="*80 + "\n")
    
    # Détecter GPU si auto
    gpu_id = args.gpu_id
    if args.auto_gpu:
        gpu_id = detect_gpu()
    
    # Lancer optimisation
    results = run_optimization(
        n_trials=args.trials,
        timeout=args.timeout,
        n_jobs=args.n_jobs,
        gpu_id=gpu_id,
        metric=args.metric,
        save_config=args.save,
        max_samples=args.max_samples
    )
    
    logger.info("\n✅ Optimisation terminée avec succès!")
    
    if args.save:
        logger.info("💾 Meilleurs paramètres sauvegardés dans config_overrides.json")
        logger.info("⚠️ Pense à relancer l'entraînement du modèle avec ces nouveaux paramètres!")
    
    return 0


def cmd_show_best(args):
    """Afficher meilleurs paramètres"""
    try:
        # Charger étude
        tuner = HyperparameterTuner(
            study_name=args.study_name,
            n_trials=1  # Juste pour charger l'étude
        )
        
        if len(tuner.study.trials) == 0:
            logger.warning("⚠️ Aucun trial trouvé dans cette étude")
            return 1
        
        # Afficher meilleurs params
        logger.info("\n" + "="*80)
        logger.info(f"🏆 MEILLEURS PARAMÈTRES (Étude: {args.study_name})")
        logger.info("="*80 + "\n")
        
        best_trial = tuner.study.best_trial
        logger.info(f"📊 Best Score: {best_trial.value:.4f}")
        logger.info(f"📅 Date: {best_trial.datetime_start}")
        logger.info(f"\n🎯 Hyperparamètres:\n")
        
        for param, value in best_trial.params.items():
            logger.info(f"  {param:25s} = {value}")
        
        logger.info(f"\n{'='*80}\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return 1


def cmd_apply_best(args):
    """Appliquer meilleurs paramètres à config"""
    try:
        # Charger étude
        tuner = HyperparameterTuner(
            study_name=args.study_name,
            n_trials=1
        )
        
        if len(tuner.study.trials) == 0:
            logger.warning("⚠️ Aucun trial trouvé dans cette étude")
            return 1
        
        # Sauvegarder
        tuner.save_best_params(filepath=args.config_file)
        
        logger.info(f"✅ Meilleurs paramètres appliqués à {args.config_file}")
        logger.info("⚠️ Relance l'entraînement du modèle pour utiliser ces paramètres!")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return 1


def cmd_history(args):
    """Afficher historique des trials"""
    try:
        # Charger étude
        tuner = HyperparameterTuner(
            study_name=args.study_name,
            n_trials=1
        )
        
        if len(tuner.study.trials) == 0:
            logger.warning("⚠️ Aucun trial trouvé")
            return 1
        
        # Afficher historique
        history = tuner.get_optimization_history()
        
        logger.info(f"\n📊 HISTORIQUE OPTIMISATION ({len(history)} trials)\n")
        logger.info(f"{'#':<6} {'Score':<12} {'État':<12} {'Date':<20}")
        logger.info("-" * 60)
        
        # Trier par score (meilleurs en premier)
        history_sorted = sorted(
            [h for h in history if h['value'] is not None],
            key=lambda x: x['value'],
            reverse=True
        )
        
        # Afficher top N
        limit = args.limit if args.limit else len(history_sorted)
        for h in history_sorted[:limit]:
            logger.info(
                f"{h['number']:<6} {h['value']:<12.4f} {h['state']:<12} "
                f"{h['datetime'].strftime('%Y-%m-%d %H:%M:%S') if h['datetime'] else 'N/A'}"
            )
        
        logger.info("")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return 1


def cmd_dashboard(args):
    """Lancer dashboard Optuna"""
    logger.info("\n🌐 Démarrage dashboard Optuna...")
    logger.info(f"📊 Accès: http://localhost:{args.port}")
    logger.info("⚠️ Appuie sur Ctrl+C pour arrêter\n")
    
    try:
        import subprocess
        
        # Charger storage de l'étude
        tuner = HyperparameterTuner(n_trials=1)
        storage = tuner.storage
        
        # Lancer dashboard
        cmd = [
            sys.executable, "-m", "optuna_dashboard",
            storage,
            "--port", str(args.port)
        ]
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        logger.info("\n👋 Dashboard arrêté")
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        logger.info("💡 Installe optuna-dashboard: pip install optuna-dashboard")
        return 1
    
    return 0


def main():
    """Point d'entrée CLI"""
    parser = argparse.ArgumentParser(
        description="Optimisation hyperparametres ML pour trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Optimisation rapide (50 trials, CPU)
  python -m ml.tune optimize --trials 50
  
  # Optimisation GPU avec 200 trials
  python -m ml.tune optimize --trials 200 --auto-gpu
  
  # Optimisation longue (12h max, tous les CPU)
  python -m ml.tune optimize --trials 500 --timeout 43200 --n-jobs -1
  
  # Voir meilleurs paramètres
  python -m ml.tune show-best
  
  # Appliquer meilleurs paramètres
  python -m ml.tune apply-best
  
  # Voir historique (top 20)
  python -m ml.tune history --limit 20
  
  # Lancer dashboard web
  python -m ml.tune dashboard
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
    
    # Commande: optimize
    parser_opt = subparsers.add_parser('optimize', help='Lancer optimisation')
    parser_opt.add_argument(
        '--trials', type=int, default=100,
        help='Nombre de trials (défaut: 100)'
    )
    parser_opt.add_argument(
        '--timeout', type=int, default=None,
        help='Timeout en secondes (défaut: illimité)'
    )
    parser_opt.add_argument(
        '--n-jobs', type=int, default=-1,
        help='Nombre de CPU (-1 = tous, défaut: -1)'
    )
    parser_opt.add_argument(
        '--gpu-id', type=int, default=None,
        help='ID du GPU (0, 1, ..., défaut: None = CPU)'
    )
    parser_opt.add_argument(
        '--auto-gpu', action='store_true',
        help='Détecter et utiliser GPU automatiquement'
    )
    parser_opt.add_argument(
        '--metric', type=str, default='trading_composite',
        choices=['trading_composite', 'f1_score', 'accuracy', 'roc_auc'],
        help='Métrique à optimiser (défaut: trading_composite)'
    )
    parser_opt.add_argument(
        '--no-save', dest='save', action='store_false',
        help="Ne pas sauvegarder les meilleurs params dans config"
    )
    parser_opt.add_argument(
        '--max-samples', type=int, default=None,
        help='Limiter nombre de samples pour rapidité (défaut: tous)'
    )
    parser_opt.set_defaults(func=cmd_optimize, save=True)
    
    # Commande: show-best
    parser_show = subparsers.add_parser('show-best', help='Afficher meilleurs paramètres')
    parser_show.add_argument(
        '--study-name', type=str, default='xgboost_trading_optimization',
        help='Nom de l\'étude (défaut: xgboost_trading_optimization)'
    )
    parser_show.set_defaults(func=cmd_show_best)
    
    # Commande: apply-best
    parser_apply = subparsers.add_parser('apply-best', help='Appliquer meilleurs params à config')
    parser_apply.add_argument(
        '--study-name', type=str, default='xgboost_trading_optimization',
        help='Nom de l\'étude'
    )
    parser_apply.add_argument(
        '--config-file', type=str, default='config_overrides.json',
        help='Fichier config (défaut: config_overrides.json)'
    )
    parser_apply.set_defaults(func=cmd_apply_best)
    
    # Commande: history
    parser_hist = subparsers.add_parser('history', help='Afficher historique')
    parser_hist.add_argument(
        '--study-name', type=str, default='xgboost_trading_optimization',
        help='Nom de l\'étude'
    )
    parser_hist.add_argument(
        '--limit', type=int, default=20,
        help='Nombre de trials à afficher (défaut: 20)'
    )
    parser_hist.set_defaults(func=cmd_history)
    
    # Commande: dashboard
    parser_dash = subparsers.add_parser('dashboard', help='Lancer dashboard web')
    parser_dash.add_argument(
        '--port', type=int, default=8080,
        help='Port du dashboard (défaut: 8080)'
    )
    parser_dash.set_defaults(func=cmd_dashboard)
    
    # Parser arguments
    args = parser.parse_args()
    
    # Exécuter commande
    if hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
