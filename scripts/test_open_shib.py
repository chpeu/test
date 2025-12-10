#!/usr/bin/env python3
"""
Script de test: Ouvrir une position SHIB via WebSocket du backend
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import requests
import json

def main():
    print("=" * 60)
    print("TEST: Forcer ouverture position SHIB via WebSocket")
    print("=" * 60)
    
    # Le backend doit être en cours d'exécution
    BASE_URL = "http://localhost:5000"
    
    # Vérifier que le backend répond
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code != 200:
            print(f"[ERREUR] Backend non disponible: {resp.status_code}")
            return
        print("[OK] Backend disponible")
    except Exception as e:
        print(f"[ERREUR] Backend non accessible: {e}")
        print("   Lancez d'abord: python main.py")
        return
    
    print("\n[INFO] Pour ouvrir une position SHIB:")
    print("   1. Ouvrez le dashboard dans le navigateur: http://localhost:3000")
    print("   2. Attendez qu'un setup SHIB soit détecté par le scanner")
    print("   3. Ou modifiez temporairement min_score_required pour accepter plus de setups")
    print("\n[INFO] La position s'ouvrira automatiquement quand le scanner")
    print("   trouvera un setup valide pour SHIB/USDT:USDT")
    print("\n[INFO] Sinon, vous pouvez ouvrir manuellement depuis MEXC")
    print("   et le bot synchronisera automatiquement la position.")

if __name__ == "__main__":
    main()
