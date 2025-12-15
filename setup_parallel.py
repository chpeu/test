#!/usr/bin/env python3
"""
Script Setup Parallèle - Live Trading + EDA V2
Automatise la configuration initiale
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

# Couleurs terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_step(step_num, title):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Étape {step_num}: {title}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def check_env_file():
    """Vérifier que .env existe"""
    print_step(1, "Vérification fichier .env")
    
    env_path = Path(".env")
    if not env_path.exists():
        print_error(".env introuvable!")
        print("Créer le fichier .env à la racine du projet")
        return False
    
    print_success(".env trouvé")
    return True

def setup_mexc_keys():
    """Configurer clés API MEXC"""
    print_step(2, "Configuration API Keys MEXC")
    
    load_dotenv()
    
    # Vérifier si déjà configuré
    api_key = os.getenv('MEXC_API_KEY', '')
    api_secret = os.getenv('MEXC_API_SECRET', '')
    
    if api_key and api_secret:
        print_success(f"API Key déjà configurée: {api_key[:10]}...")
        reconfig = input("Reconfigurer les clés? (y/N): ").strip().lower()
        if reconfig != 'y':
            return True
    
    # Demander les clés
    print("\nObtenir clés API MEXC:")
    print("1. Aller sur https://www.mexc.com/")
    print("2. Account → API Management")
    print("3. Créer API Key avec permissions: Spot Trading")
    print("4. Copier API Key et Secret\n")
    
    api_key = input("API Key MEXC: ").strip()
    api_secret = input("API Secret MEXC: ").strip()
    
    if not api_key or not api_secret:
        print_error("API Key ou Secret vide!")
        return False
    
    # Sauvegarder dans .env
    env_path = Path(".env")
    set_key(env_path, 'MEXC_API_KEY', api_key)
    set_key(env_path, 'MEXC_API_SECRET', api_secret)
    set_key(env_path, 'MEXC_TESTNET', 'false')
    
    print_success("Clés API sauvegardées dans .env")
    return True

def update_config_v2():
    """Mettre à jour config V2 pour EDA"""
    print_step(3, "Configuration Dataset V2 (EDA)")
    
    config_file = Path("config.py")
    if not config_file.exists():
        print_warning("config.py introuvable, utiliser config_overrides.json")
        return update_config_overrides_v2()
    
    print("Configuration recommandée pour EDA:")
    print("  - ml_v2_timeframe_days: 540 (1.5 ans)")
    print("  - ml_v2_marginal_threshold: 0.15 (au lieu de 0.20)")
    print("  - ml_v2_filter_enabled: False (tests)")
    
    confirm = input("\nAppliquer ces modifications? (Y/n): ").strip().lower()
    if confirm == 'n':
        print_warning("Configuration manuelle requise")
        return False
    
    # Lire config actuel
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier si déjà modifié
    if 'ml_v2_timeframe_days' in content and '540' in content:
        print_success("Configuration déjà appliquée")
        return True
    
    print_warning("Modifier manuellement config.py:")
    print("  TRADING_CONFIG['ml_v2_timeframe_days'] = 540")
    print("  TRADING_CONFIG['ml_v2_marginal_threshold'] = 0.15")
    
    return True

def update_config_overrides_v2():
    """Mettre à jour config_overrides.json pour V2"""
    config_file = Path("config_overrides.json")
    
    # Charger config existante
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Ajouter config V2
    config['ml_v2_timeframe_days'] = 540
    config['ml_v2_marginal_threshold'] = 0.15
    config['ml_v2_filter_enabled'] = False
    
    # Sauvegarder
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print_success("config_overrides.json mis à jour")
    return True

def check_dependencies():
    """Vérifier dépendances Python"""
    print_step(4, "Vérification Dépendances")
    
    required = [
        'ccxt',
        'psycopg2',
        'pandas',
        'numpy',
        'fastapi',
        'python-dotenv'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace('-', '_'))
            print_success(f"{package} installé")
        except ImportError:
            print_error(f"{package} MANQUANT")
            missing.append(package)
    
    if missing:
        print(f"\n{Colors.YELLOW}Installer dépendances manquantes:{Colors.RESET}")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def create_live_config():
    """Créer fichier config_live_persistent.json"""
    print_step(5, "Configuration Live Trading")
    
    config_file = Path("config_live_persistent.json")
    
    if config_file.exists():
        print_success("config_live_persistent.json existe déjà")
        return True
    
    # Config par défaut
    config = {
        'trading_mode': 'PAPER',
        'dry_run': True,
        'api_key_mexc': '',
        'api_secret_mexc': '',
        'max_slippage_pct': 0.15,
        'max_latency_ms': 1000,
        'max_pnl_discrepancy_pct': 20,
        'alerts_enabled': True,
        'telegram_notify_live_trades': True
    }
    
    # Sauvegarder
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print_success("config_live_persistent.json créé")
    return True

def print_next_steps():
    """Afficher prochaines étapes"""
    print_step(6, "Prochaines Étapes")
    
    print(f"{Colors.GREEN}✅ Configuration terminée!{Colors.RESET}\n")
    
    print("🚀 Démarrer le système:")
    print("  Terminal 1: python main.py")
    print("  Terminal 2: cd frontend && npm run dev")
    print("  Navigateur: http://localhost:5173\n")
    
    print("🔴 Live Trading (DRY_RUN):")
    print("  1. Aller dans Live Trading Panel")
    print("  2. Vérifier mode: LIVE + Dry-Run ACTIVÉ")
    print("  3. Tester connexion API")
    print("  4. Laisser tourner 3 jours\n")
    
    print("🔵 EDA V2:")
    print("  1. Aller dans ML Dashboard V2")
    print("  2. Cliquer 'Réentraîner Modèle V2'")
    print("  3. Vérifier logs: dataset > 100 trades")
    print("  4. Analyser résultats (R² > 0.28)\n")
    
    print("📊 Monitoring:")
    print("  - Live stats: http://localhost:8000/api/live/stats")
    print("  - ML metrics: http://localhost:8000/api/ml/models")
    print("  - Logs backend: logs/backend.log\n")

def main():
    """Fonction principale"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}Setup Parallèle - Live Trading + EDA V2{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    # Vérifier .env
    if not check_env_file():
        print_error("Setup annulé")
        return 1
    
    # Configurer MEXC
    if not setup_mexc_keys():
        print_error("Configuration MEXC échouée")
        return 1
    
    # Config V2
    if not update_config_v2():
        print_warning("Configuration V2 manuelle requise")
    
    # Vérifier dépendances
    if not check_dependencies():
        print_error("Installer dépendances manquantes")
        return 1
    
    # Config live
    if not create_live_config():
        print_error("Configuration live échouée")
        return 1
    
    # Prochaines étapes
    print_next_steps()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
