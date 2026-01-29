#!/usr/bin/env python3
"""
Moniteur automatique des tokens MEXC
Vérifie périodiquement l'état des tokens et les renouvelle si nécessaire
"""

import time
import schedule
import subprocess
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

class MEXCTokenMonitor:
    def __init__(self, check_interval_minutes=30):
        self.check_interval = check_interval_minutes
        self.last_check = None
        self.setup_logging()
        
    def setup_logging(self):
        """Configure le logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/mexc_token_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('MEXCTokenMonitor')
    
    def check_token_health(self):
        """Vérifie l'état de santé des tokens"""
        self.logger.info("🔍 Vérification santé tokens MEXC...")
        
        try:
            # Exécuter le validator
            result = subprocess.run([
                'python', 'tools/validate_mexc_tokens.py'
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode == 0:
                self.logger.info("✅ Tokens en bonne santé")
                return True
            else:
                self.logger.warning("⚠️ Problème détecté avec les tokens")
                self.logger.warning(f"Output: {result.stdout}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Erreur vérification tokens: {e}")
            return False
    
    def check_token_expiry(self):
        """Vérifie si le token expire bientôt"""
        token_file = "tools/mexc_tokens.json"
        
        if not os.path.exists(token_file):
            self.logger.warning("📁 Fichier mexc_tokens.json manquant")
            return True  # Besoin de renouvellement
        
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            expires_at_str = token_data.get('expires_at')
            if not expires_at_str:
                self.logger.warning("⏰ Date d'expiration manquante")
                return True
            
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()
            time_left = expires_at - now
            
            # Renouveler si expire dans moins de 2 heures
            if time_left.total_seconds() < 7200:  # 2 heures
                self.logger.warning(f"⏰ Token expire bientôt: {time_left}")
                return True
            else:
                self.logger.info(f"✅ Token valide pour encore {time_left}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Erreur lecture expiration: {e}")
            return True
    
    def auto_renew_token(self):
        """Renouvellement automatique du token"""
        self.logger.info("🔄 Démarrage renouvellement automatique...")
        
        try:
            # 1. Extraction nouveau token
            self.logger.info("1️⃣ Extraction nouveau token...")
            result = subprocess.run([
                'python', 'tools/mexc_token_extractor.py', 'once'
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode != 0:
                self.logger.error("❌ Échec extraction token")
                self.logger.error(f"Error: {result.stderr}")
                return False
            
            self.logger.info("✅ Token extrait avec succès")
            
            # 2. Synchronisation
            self.logger.info("2️⃣ Synchronisation...")
            result = subprocess.run([
                'python', 'tools/sync_mexc_token.py'
            ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            
            if result.returncode != 0:
                self.logger.error("❌ Échec synchronisation")
                self.logger.error(f"Error: {result.stderr}")
                return False
            
            self.logger.info("✅ Synchronisation réussie")
            
            # 3. Validation finale
            self.logger.info("3️⃣ Validation finale...")
            if self.check_token_health():
                self.logger.info("🎉 Renouvellement automatique réussi!")
                return True
            else:
                self.logger.error("❌ Validation post-renouvellement échoué")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Erreur renouvellement automatique: {e}")
            return False
    
    def scheduled_check(self):
        """Vérification programmée"""
        self.logger.info(f"⏰ Vérification programmée - {datetime.now().strftime('%H:%M:%S')}")
        self.last_check = datetime.now()
        
        # 1. Vérifier santé globale
        if not self.check_token_health():
            self.logger.warning("🚨 Problème de santé détecté - tentative de correction")
            self.auto_renew_token()
            return
        
        # 2. Vérifier expiration proche
        if self.check_token_expiry():
            self.logger.info("🔄 Renouvellement préventif nécessaire")
            self.auto_renew_token()
        
        self.logger.info("✅ Vérification terminée")
    
    def run_daemon(self):
        """Mode daemon avec vérifications programmées"""
        self.logger.info(f"🚀 Démarrage moniteur MEXC (vérification toutes les {self.check_interval}min)")
        
        # Programmer la vérification
        schedule.every(self.check_interval).minutes.do(self.scheduled_check)
        
        # Vérification initiale
        self.scheduled_check()
        
        # Boucle principale
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Vérifier toutes les minutes
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Arrêt du moniteur")
    
    def run_once(self):
        """Exécution unique (check + correction si nécessaire)"""
        self.logger.info("🔍 Vérification unique...")
        self.scheduled_check()
    
    def status(self):
        """Affiche le statut actuel"""
        print("📊 STATUT MONITEUR MEXC")
        print("=" * 30)
        
        if self.last_check:
            print(f"Dernière vérification: {self.last_check.strftime('%Y-%m-%d %H:%M:%S')}")
            age = datetime.now() - self.last_check
            print(f"Il y a: {int(age.total_seconds() / 60)} minutes")
        else:
            print("Dernière vérification: Jamais")
        
        print(f"Intervalle: {self.check_interval} minutes")
        
        # État des tokens
        health = self.check_token_health()
        expiry_needed = self.check_token_expiry()
        
        print(f"Santé tokens: {'✅ OK' if health else '❌ Problème'}")
        print(f"Expiration: {'⚠️ Bientôt' if expiry_needed else '✅ OK'}")


def main():
    import sys
    
    monitor = MEXCTokenMonitor(check_interval_minutes=30)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "daemon":
            monitor.run_daemon()
        elif command == "once":
            monitor.run_once()
        elif command == "status":
            monitor.status()
        elif command == "renew":
            success = monitor.auto_renew_token()
            sys.exit(0 if success else 1)
        else:
            print("Usage: python mexc_token_monitor.py [daemon|once|status|renew]")
    else:
        print("Moniteur MEXC Token")
        print("==================")
        print("daemon - Mode daemon (vérification continue)")
        print("once   - Vérification unique")
        print("status - Afficher le statut")
        print("renew  - Forcer le renouvellement")


if __name__ == "__main__":
    main()
