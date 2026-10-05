#!/usr/bin/env python3
"""
Script de validation automatique des tokens MEXC
Vérifie la cohérence entre tous les fichiers de configuration
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

class MEXCTokenValidator:
    def __init__(self):
        self.token_file = "tools/mexc_tokens.json"
        self.env_file = ".env"
        self.config_file = "config_live_persistent.json"
        self.errors = []
        self.warnings = []
        
    def extract_token_from_env(self):
        """Extrait le token depuis .env"""
        if not os.path.exists(self.env_file):
            return None
        
        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    if line.startswith('MEXC_BROWSER_TOKEN='):
                        return line.strip().split('=')[1]
        except Exception as e:
            self.errors.append(f"Erreur lecture .env: {e}")
        
        return None
    
    def extract_token_from_config(self):
        """Extrait le token depuis config_live_persistent.json"""
        if not os.path.exists(self.config_file):
            return None
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
                return config_data.get('browser_token_mexc')
        except Exception as e:
            self.errors.append(f"Erreur lecture config_live_persistent.json: {e}")
        
        return None
    
    def extract_token_from_mexc_tokens(self):
        """Extrait le token depuis mexc_tokens.json"""
        if not os.path.exists(self.token_file):
            return None, None, None
        
        try:
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
                
            # Token composite format
            raw_token = token_data.get('token', '')
            if isinstance(raw_token, str) and raw_token.startswith('{"'):
                composite_data = json.loads(raw_token)
                clean_token = composite_data.get('cookies', {}).get('uc_token')
            else:
                clean_token = raw_token
            
            # Dates d'expiration
            expires_at = token_data.get('expires_at')
            extracted_at = token_data.get('extracted_at')
            
            return clean_token, expires_at, extracted_at
            
        except Exception as e:
            self.errors.append(f"Erreur lecture mexc_tokens.json: {e}")
        
        return None, None, None
    
    def check_token_expiration(self, expires_at_str):
        """Vérifie si le token est expiré"""
        if not expires_at_str:
            return False, "Date d'expiration manquante"
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()
            
            if now > expires_at:
                return False, f"Token expiré depuis {now - expires_at}"
            else:
                time_left = expires_at - now
                return True, f"Expire dans {time_left}"
                
        except Exception as e:
            return False, f"Erreur parsing date: {e}"
    
    def validate_all(self):
        """Validation complète de tous les tokens"""
        print("🔍 Validation des tokens MEXC...")
        print("=" * 50)
        
        # 1. Extraire tokens de chaque source
        env_token = self.extract_token_from_env()
        config_token = self.extract_token_from_config()
        mexc_token, expires_at, extracted_at = self.extract_token_from_mexc_tokens()
        
        # 2. Afficher les tokens trouvés
        print(f"📄 .env:                     {env_token[:20] + '...' if env_token else 'NON TROUVÉ'}")
        print(f"📄 config_live_persistent:   {config_token[:20] + '...' if config_token else 'NON TROUVÉ'}")
        print(f"📄 mexc_tokens.json:         {mexc_token[:20] + '...' if mexc_token else 'NON TROUVÉ'}")
        
        # 3. Vérifier la cohérence
        print("\n🔍 Vérification de cohérence...")
        
        tokens = [t for t in [env_token, config_token, mexc_token] if t]
        if len(set(tokens)) > 1:
            self.errors.append("❌ TOKENS DIFFÉRENTS entre les fichiers!")
            print("❌ TOKENS DIFFÉRENTS entre les fichiers!")
        elif tokens:
            print("✅ Tous les tokens sont identiques")
        else:
            self.errors.append("❌ Aucun token trouvé!")
        
        # 4. Vérifier l'expiration
        if expires_at:
            print(f"\n🕒 Vérification expiration...")
            is_valid, expiry_msg = self.check_token_expiration(expires_at)
            if is_valid:
                print(f"✅ Token valide - {expiry_msg}")
            else:
                self.errors.append(f"❌ {expiry_msg}")
                print(f"❌ {expiry_msg}")
        
        # 5. Vérifier l'âge du token
        if extracted_at:
            try:
                extracted = datetime.fromisoformat(extracted_at)
                age = datetime.now() - extracted
                if age.total_seconds() > 86400:  # 24 heures
                    self.warnings.append(f"⚠️ Token extrait il y a {age.days} jours")
                print(f"📅 Token extrait: {extracted.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                pass
        
        # 6. Résumé final
        print("\n" + "=" * 50)
        if self.errors:
            print("❌ VALIDATION ÉCHOUÉE:")
            for error in self.errors:
                print(f"   {error}")
        else:
            print("✅ VALIDATION RÉUSSIE!")
        
        if self.warnings:
            print("\n⚠️ AVERTISSEMENTS:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        return len(self.errors) == 0
    
    def suggest_fix(self):
        """Suggère des corrections"""
        if self.errors:
            print("\n🔧 SUGGESTIONS DE CORRECTION:")
            print("1. Exécutez: python tools/mexc_token_extractor.py once")
            print("2. Exécutez: python tools/sync_mexc_token.py")
            print("3. Redémarrez le bot")

def main():
    validator = MEXCTokenValidator()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        # Mode avec suggestion de correction automatique
        success = validator.validate_all()
        if not success:
            validator.suggest_fix()
    else:
        # Mode validation simple
        success = validator.validate_all()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
