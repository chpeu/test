#!/usr/bin/env python3
"""
Installateur pour MEXC Token Extractor - Solution Permanente
Installe les dépendances et configure l'extracteur automatique
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def install_dependencies():
    """Installe les dépendances Python requises"""
    dependencies = [
        'selenium',
        'browser-cookie3',
        'requests',
        'webdriver-manager'
    ]
    
    print("Installation des dependances...")
    
    for dep in dependencies:
        try:
            print(f"Installation de {dep}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])
            print(f"OK {dep} installe")
        except subprocess.CalledProcessError as e:
            print(f"ERREUR installation {dep}: {e}")
            return False
    
    return True

def download_chromedriver():
    """Télécharge et configure ChromeDriver automatiquement"""
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium import webdriver
        
        print("Telechargement ChromeDriver...")
        driver_path = ChromeDriverManager().install()
        print(f"OK ChromeDriver installe: {driver_path}")
        
        return True
    except Exception as e:
        print(f"ERREUR ChromeDriver: {e}")
        return False

def create_config():
    """Crée la configuration initiale"""
    config = {
        "headless": False,
        "check_interval": 300,
        "auto_login": False,
        "credentials": {
            "username": "",
            "password": "",
            "note": "Laissez vide pour connexion manuelle"
        },
        "browser": "chrome",
        "token_validity_hours": 24,
        "auto_start": False,
        "log_level": "INFO"
    }
    
    config_file = "mexc_config.json"
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"OK Configuration creee: {config_file}")
        return True
    except Exception as e:
        print(f"ERREUR creation config: {e}")
        return False

def create_launcher_script():
    """Crée un script de lancement facile"""
    launcher_content = '''@echo off
echo MEXC Token Extractor - Solution Permanente
echo ==========================================
echo.
echo 1. Extraction unique
echo 2. Mode daemon (continu)
echo 3. Voir configuration
echo 4. Quitter
echo.
set /p choice=Choisissez une option (1-4): 

if "%choice%"=="1" (
    python mexc_token_extractor.py once
    pause
    goto :start
)
if "%choice%"=="2" (
    echo Demarrage du mode daemon...
    python mexc_token_extractor.py daemon
    pause
    goto :start
)
if "%choice%"=="3" (
    python mexc_token_extractor.py config
    pause
    goto :start
)
if "%choice%"=="4" (
    exit
)

:start
cls
goto :EOF
'''
    
    try:
        with open('run_mexc_extractor.bat', 'w') as f:
            f.write(launcher_content)
        print("OK Script de lancement cree: run_mexc_extractor.bat")
        return True
    except Exception as e:
        print(f"ERREUR creation launcher: {e}")
        return False

def create_service_script():
    """Crée un script pour lancer comme service Windows"""
    service_content = '''import os
import sys
import time
import subprocess
from pathlib import Path

def run_as_service():
    """Lance l'extracteur comme service Windows"""
    script_dir = Path(__file__).parent
    extractor_path = script_dir / "mexc_token_extractor.py"
    
    if not extractor_path.exists():
        print(f"Erreur: {extractor_path} non trouvé")
        return
    
    print("Demarrage service MEXC Token Extractor...")
    
    try:
        # Lancer en mode daemon
        subprocess.Popen([
            sys.executable, 
            str(extractor_path), 
            "daemon"
        ], 
        cwd=str(script_dir),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        print("OK Service demarre avec succes")
        
    except Exception as e:
        print(f"ERREUR demarrage service: {e}")

if __name__ == "__main__":
    run_as_service()
'''
    
    try:
        with open('mexc_service.py', 'w') as f:
            f.write(service_content)
        print("OK Script service cree: mexc_service.py")
        return True
    except Exception as e:
        print(f"ERREUR creation service: {e}")
        return False

def create_integration_example():
    """Crée un exemple d'intégration avec le bot de trading"""
    integration_content = '''#!/usr/bin/env python3
"""
Exemple d'intégration MEXC Token Extractor avec le bot de trading
"""

import json
import os
from datetime import datetime

class MEXCTokenProvider:
    def __init__(self, token_file="mexc_tokens.json"):
        self.token_file = token_file
    
    def get_current_token(self):
        """Récupère le token MEXC actuel"""
        if not os.path.exists(self.token_file):
            print("ATTENTION: Fichier token non trouve. Lancez l'extracteur d'abord.")
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Vérifier l'expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() > expires_at:
                print("ATTENTION: Token expire")
                return None
            
            return token_data['token']
            
        except Exception as e:
            print(f"ERREUR lecture token: {e}")
            return None
    
    def is_token_valid(self):
        """Vérifie si le token est valide"""
        return self.get_current_token() is not None

# Exemple d'utilisation dans votre bot
if __name__ == "__main__":
    provider = MEXCTokenProvider()
    
    token = provider.get_current_token()
    if token:
        print(f"OK Token disponible: {token[:20]}...")
        
        # Intégrer dans votre client MEXC
        # mexc_client.set_token(token)
        
    else:
        print("ERREUR: Aucun token valide disponible")
        print("Lancez: python mexc_token_extractor.py once")
'''
    
    try:
        with open('mexc_integration_example.py', 'w') as f:
            f.write(integration_content)
        print("OK Exemple d'integration cree: mexc_integration_example.py")
        return True
    except Exception as e:
        print(f"ERREUR creation integration: {e}")
        return False

def main():
    print("INSTALLATEUR MEXC TOKEN EXTRACTOR - SOLUTION PERMANENTE")
    print("=" * 60)
    
    success = True
    
    # 1. Installer les dépendances
    if not install_dependencies():
        success = False
    
    # 2. Télécharger ChromeDriver
    if success and not download_chromedriver():
        success = False
    
    # 3. Créer la configuration
    if success and not create_config():
        success = False
    
    # 4. Créer le script de lancement
    if success and not create_launcher_script():
        success = False
    
    # 5. Créer le script service
    if success and not create_service_script():
        success = False
    
    # 6. Créer l'exemple d'intégration
    if success and not create_integration_example():
        success = False
    
    print("\n" + "=" * 60)
    
    if success:
        print("OK INSTALLATION TERMINEE AVEC SUCCES !")
        print("\nFICHIERS CREES :")
        print("   - mexc_token_extractor.py      (extracteur principal)")
        print("   - mexc_config.json             (configuration)")
        print("   - run_mexc_extractor.bat       (lanceur facile)")
        print("   - mexc_service.py              (service Windows)")
        print("   - mexc_integration_example.py  (exemple intégration)")
        
        print("\nUTILISATION :")
        print("   1. Double-cliquez sur 'run_mexc_extractor.bat'")
        print("   2. Choisissez 'Extraction unique' pour tester")
        print("   3. Utilisez 'Mode daemon' pour extraction continue")
        
        print("\nINTEGRATION BOT :")
        print("   - Voir mexc_integration_example.py")
        print("   - Le token est sauvé dans mexc_tokens.json")
        print("   - Rechargement automatique toutes les 5 minutes")
        
    else:
        print("ERREURS PENDANT L'INSTALLATION")
        print("Vérifiez les messages d'erreur ci-dessus")

if __name__ == "__main__":
    main()
