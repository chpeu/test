#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exemple d'integration MEXC Token Extractor avec le bot de trading
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
