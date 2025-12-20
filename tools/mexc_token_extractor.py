#!/usr/bin/env python3
"""
MEXC Token Extractor - Solution Permanente
Extrait automatiquement les tokens MEXC sans extension Firefox
"""

import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import browser_cookie3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class MEXCTokenExtractor:
    def __init__(self, config_file="mexc_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        self.token_file = "mexc_tokens.json"
        
    def load_config(self):
        """Charge la configuration"""
        default_config = {
            "headless": True,
            "check_interval": 300,  # 5 minutes
            "auto_login": False,
            "credentials": {
                "username": "",
                "password": ""
            },
            "browser": "chrome",  # chrome, firefox, edge
            "token_validity_hours": 24
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                default_config.update(loaded_config)
            except Exception as e:
                print(f"Erreur lecture config: {e}")
        else:
            self.save_config(default_config)
            
        return default_config
    
    def save_config(self, config):
        """Sauvegarde la configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def extract_cookies_method(self):
        """Méthode 1: Extraction via cookies du navigateur"""
        try:
            # Essayer Firefox d'abord
            cookies = browser_cookie3.firefox(domain_name='mexc.com')
            mexc_cookies = {cookie.name: cookie.value for cookie in cookies}
            
            if not mexc_cookies:
                # Essayer Chrome
                cookies = browser_cookie3.chrome(domain_name='mexc.com')
                mexc_cookies = {cookie.name: cookie.value for cookie in cookies}
            
            # Chercher les cookies d'authentification
            auth_cookies = {}
            for name, value in mexc_cookies.items():
                if any(keyword in name.lower() for keyword in ['auth', 'token', 'session', 'jwt']):
                    auth_cookies[name] = value
            
            if auth_cookies:
                return self.validate_token_from_cookies(auth_cookies)
            
        except Exception as e:
            print(f"Erreur extraction cookies: {e}")
        
        return None
    
    def extract_selenium_method(self):
        """Méthode 2: Extraction via Selenium"""
        driver = None
        try:
            # Configuration du driver
            if self.config['browser'] == 'chrome':
                options = Options()
                if self.config['headless']:
                    options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                driver = webdriver.Chrome(options=options)
            
            # Aller sur MEXC
            driver.get('https://futures.mexc.com')
            
            # Auto-login si configuré
            if self.config['auto_login'] and self.config['credentials']['username']:
                self.auto_login(driver)
            
            # Attendre que l'utilisateur se connecte (si pas auto-login)
            if not self.config['auto_login']:
                print("Veuillez vous connecter sur MEXC dans le navigateur...")
                input("Appuyez sur Entrée une fois connecté...")
            
            # Extraire le token des requêtes réseau
            token = self.extract_token_from_network(driver)
            
            return token
            
        except Exception as e:
            print(f"Erreur Selenium: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    def auto_login(self, driver):
        """Connexion automatique (optionnelle)"""
        try:
            # Cliquer sur connexion
            login_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Login')]"))
            )
            login_btn.click()
            
            # Remplir username
            username_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            username_field.send_keys(self.config['credentials']['username'])
            
            # Remplir password
            password_field = driver.find_element(By.NAME, "password")
            password_field.send_keys(self.config['credentials']['password'])
            
            # Cliquer sur submit
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_btn.click()
            
            # Attendre la redirection
            WebDriverWait(driver, 30).until(
                EC.url_contains('futures.mexc.com')
            )
            
        except Exception as e:
            print(f"Erreur auto-login: {e}")
    
    def extract_token_from_network(self, driver):
        """Extrait le token des requêtes réseau"""
        try:
            # Exécuter du JavaScript pour intercepter les requêtes
            js_code = """
            var originalFetch = window.fetch;
            window.interceptedRequests = [];
            
            window.fetch = function(...args) {
                var [resource, config] = args;
                
                // Capturer les headers Authorization
                if (config && config.headers) {
                    var authHeader = config.headers['Authorization'] || 
                                   config.headers['authorization'] ||
                                   config.headers['X-MEXC-APIKEY'] ||
                                   config.headers['x-mexc-apikey'];
                    
                    if (authHeader) {
                        window.interceptedRequests.push({
                            url: resource,
                            token: authHeader,
                            timestamp: Date.now()
                        });
                    }
                }
                
                return originalFetch.apply(this, args);
            };
            
            // Déclencher quelques requêtes API
            setTimeout(() => {
                fetch('/api/v1/private/account/info', {
                    headers: { 'Authorization': localStorage.getItem('token') || '' }
                }).catch(() => {});
            }, 1000);
            """
            
            driver.execute_script(js_code)
            
            # Attendre que des requêtes soient interceptées
            time.sleep(5)
            
            # Récupérer les tokens interceptés
            intercepted = driver.execute_script("return window.interceptedRequests;")
            
            if intercepted:
                # Prendre le token le plus récent
                latest = max(intercepted, key=lambda x: x['timestamp'])
                return latest['token']
            
            # Fallback: chercher dans localStorage
            token = driver.execute_script("return localStorage.getItem('token') || localStorage.getItem('auth_token') || '';")
            
            if token:
                return token
                
        except Exception as e:
            print(f"Erreur extraction network: {e}")
        
        return None
    
    def validate_token_from_cookies(self, cookies):
        """Valide et convertit les cookies en token utilisable"""
        try:
            # Essayer de faire une requête d'authentification avec les cookies
            session = requests.Session()
            
            # Ajouter les cookies à la session
            for name, value in cookies.items():
                session.cookies.set(name, value, domain='mexc.com')
            
            # Test API call
            response = session.get('https://futures.mexc.com/api/v1/private/account/info')
            
            if response.status_code == 200:
                # Extraire le token des headers de réponse si disponible
                auth_header = response.headers.get('Authorization') or response.headers.get('X-MEXC-APIKEY')
                if auth_header:
                    return auth_header
                
                # Sinon, créer un token composite des cookies
                token_data = {
                    'cookies': cookies,
                    'type': 'cookie_composite',
                    'extracted_at': datetime.now().isoformat()
                }
                return json.dumps(token_data)
            
        except Exception as e:
            print(f"Erreur validation cookies: {e}")
        
        return None
    
    def save_token(self, token):
        """Sauvegarde le token extrait"""
        if not token:
            return False
        
        token_data = {
            'token': token,
            'extracted_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=self.config['token_validity_hours'])).isoformat(),
            'status': 'active'
        }
        
        try:
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            print(f"✅ Token sauvegardé: {self.token_file}")
            return True
            
        except Exception as e:
            print(f"Erreur sauvegarde token: {e}")
            return False
    
    def load_token(self):
        """Charge le token sauvegardé"""
        if not os.path.exists(self.token_file):
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Vérifier l'expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() > expires_at:
                print("Token expiré")
                return None
            
            return token_data['token']
            
        except Exception as e:
            print(f"Erreur lecture token: {e}")
            return None
    
    def extract_token(self):
        """Extraction principale du token"""
        print("🔍 Extraction du token MEXC...")
        
        # Méthode 1: Cookies
        print("Tentative extraction via cookies...")
        token = self.extract_cookies_method()
        
        if token:
            print("✅ Token extrait via cookies")
            return token
        
        # Méthode 2: Selenium
        print("Tentative extraction via Selenium...")
        token = self.extract_selenium_method()
        
        if token:
            print("✅ Token extrait via Selenium")
            return token
        
        print("❌ Échec extraction token")
        return None
    
    def run_once(self):
        """Exécution unique"""
        # Vérifier si un token valide existe
        existing_token = self.load_token()
        if existing_token:
            print("✅ Token valide trouvé")
            return existing_token
        
        # Extraire nouveau token
        token = self.extract_token()
        if token:
            self.save_token(token)
        
        return token
    
    def run_daemon(self):
        """Mode daemon - vérification continue"""
        print(f"🔄 Démarrage du daemon (vérification toutes les {self.config['check_interval']}s)")
        
        while True:
            try:
                token = self.run_once()
                if token:
                    print(f"✅ Token disponible ({datetime.now().strftime('%H:%M:%S')})")
                else:
                    print(f"⚠️ Pas de token disponible ({datetime.now().strftime('%H:%M:%S')})")
                
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                print("\n🛑 Arrêt du daemon")
                break
            except Exception as e:
                print(f"❌ Erreur daemon: {e}")
                time.sleep(60)  # Attendre 1 minute en cas d'erreur

def main():
    extractor = MEXCTokenExtractor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "daemon":
            extractor.run_daemon()
        elif command == "once":
            token = extractor.run_once()
            if token:
                print(f"Token: {token[:50]}...")
            else:
                print("Aucun token extrait")
        elif command == "config":
            print("Configuration actuelle:")
            print(json.dumps(extractor.config, indent=2))
        else:
            print("Usage: python mexc_token_extractor.py [once|daemon|config]")
    else:
        # Mode interactif
        token = extractor.run_once()
        if token:
            print(f"\n✅ Token extrait avec succès!")
            print(f"Sauvegardé dans: {extractor.token_file}")
        else:
            print("\n❌ Échec de l'extraction du token")

if __name__ == "__main__":
    main()
