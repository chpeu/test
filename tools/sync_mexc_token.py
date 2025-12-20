#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de synchronisation automatique du token MEXC
Lit le token frais depuis mexc_tokens.json et met a jour .env
"""

import json
import os
import sys
from datetime import datetime

class MEXCTokenSyncer:
    def __init__(self):
        self.token_file = "mexc_tokens.json"
        self.env_file = "../.env"
        
    def extract_token_from_composite(self, token_composite):
        """Extrait le token simple d'un token composite JSON"""
        try:
            if isinstance(token_composite, str) and token_composite.startswith('{"'):
                # Token composite JSON
                composite_data = json.loads(token_composite)
                if 'cookies' in composite_data and 'uc_token' in composite_data['cookies']:
                    return composite_data['cookies']['uc_token']
            return token_composite  # Token simple deja
        except Exception as e:
            print(f"ERREUR extraction token composite: {e}")
            return token_composite
    
    def get_current_token(self):
        """Recupere le token MEXC actuel depuis mexc_tokens.json"""
        if not os.path.exists(self.token_file):
            print(f"ERREUR: {self.token_file} non trouve")
            return None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
            
            # Verifier expiration
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() > expires_at:
                print("ERREUR: Token expire")
                return None
            
            # Extraire le token simple
            raw_token = token_data['token']
            clean_token = self.extract_token_from_composite(raw_token)
            
            print(f"Token trouve: {clean_token[:20]}... (expire: {expires_at.strftime('%H:%M:%S')})")
            return clean_token
            
        except Exception as e:
            print(f"ERREUR lecture token: {e}")
            return None
    
    def update_env_file(self, new_token):
        """Met a jour le token dans .env"""
        if not os.path.exists(self.env_file):
            print(f"ERREUR: {self.env_file} non trouve")
            return False
        
        try:
            # Lire le fichier .env
            with open(self.env_file, 'r') as f:
                lines = f.readlines()
            
            # Trouver et remplacer la ligne MEXC_BROWSER_TOKEN
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('MEXC_BROWSER_TOKEN='):
                    old_token = line.strip().split('=')[1]
                    lines[i] = f'MEXC_BROWSER_TOKEN={new_token}\n'
                    print(f"Ancien: {old_token[:20]}...")
                    print(f"Nouveau: {new_token[:20]}...")
                    updated = True
                    break
            
            if not updated:
                print("ERREUR: Ligne MEXC_BROWSER_TOKEN non trouvee dans .env")
                return False
            
            # Reecrire le fichier .env
            with open(self.env_file, 'w') as f:
                f.writelines(lines)
            
            print(f"✅ Token mis a jour dans {self.env_file}")
            return True
            
        except Exception as e:
            print(f"ERREUR mise a jour .env: {e}")
            return False
    
    def sync(self):
        """Synchronise le token depuis mexc_tokens.json vers .env"""
        print("=== Synchronisation Token MEXC ===")
        
        # Recuperer le token actuel
        current_token = self.get_current_token()
        if not current_token:
            return False
        
        # Mettre a jour .env
        success = self.update_env_file(current_token)
        
        if success:
            print("✅ Synchronisation terminee avec succes")
            print("⚠️  REDEMARREZ le bot pour prendre en compte le nouveau token")
        else:
            print("❌ Echec de la synchronisation")
        
        return success

def main():
    syncer = MEXCTokenSyncer()
    success = syncer.sync()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
