#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour démarrer le WebSocket et vérifier l'état
"""
import requests
import json
import time
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:5000"

def check_websocket_status():
    """Vérifier l'état actuel du WebSocket"""
    try:
        response = requests.get(f"{BASE_URL}/api/prices/live", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"📊 État WebSocket:")
            print(f"   - Connecté: {data.get('websocket_connected', False)}")
            print(f"   - Cache size: {data.get('cache_size', 0)}")
            print(f"   - Prix en cache: {len(data.get('prices', {}))}")
            return data
        else:
            print(f"❌ Erreur: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return None

def start_scanner_if_needed():
    """Démarrer le scanner si pas de top pairs"""
    try:
        # Vérifier si on a des top pairs (essayer /api/scanner/top-pairs d'abord)
        response = requests.get(f"{BASE_URL}/api/scanner/top-pairs", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # La réponse peut être {'pairs': [...]} ou directement une liste
            top_pairs = data.get('pairs', data) if isinstance(data, dict) else data
            if isinstance(top_pairs, list) and len(top_pairs) > 0:
                print(f"✅ {len(top_pairs)} top pairs disponibles")
                return True
        
        # Essayer aussi /api/state si disponible
        try:
            response = requests.get(f"{BASE_URL}/api/state", timeout=5)
            if response.status_code == 200:
                state = response.json()
                top_pairs = state.get('top_pairs', [])
                if top_pairs:
                    print(f"✅ {len(top_pairs)} top pairs disponibles")
                    return True
        except:
            pass
        
        # Pas de top pairs, démarrer le scanner
        print("📡 Aucune top pair trouvée, démarrage du scanner...")
        response = requests.post(
            f"{BASE_URL}/api/scanner/start",
            json={"top_n": 20},
            timeout=60
        )
        if response.status_code == 200:
            print("✅ Scanner démarré, attente de la fin du scan...")
            # Attendre que le scan se termine (vérifier périodiquement)
            max_wait = 60  # Maximum 60 secondes
            waited = 0
            check_interval = 2  # Vérifier toutes les 2 secondes
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                # Vérifier si on a maintenant des top pairs
                response = requests.get(f"{BASE_URL}/api/scanner/top-pairs", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    top_pairs = data.get('pairs', data) if isinstance(data, dict) else data
                    if isinstance(top_pairs, list) and len(top_pairs) > 0:
                        print(f"✅ Scan terminé ! {len(top_pairs)} top pairs disponibles")
                        return True
                
                # Afficher progression
                if waited % 10 == 0:
                    print(f"   ... attente ({waited}/{max_wait}s)...")
            
            print("⚠️ Timeout: le scan prend plus de temps que prévu")
            return False
        elif response.status_code == 400 and "Déjà en cours" in response.text:
            # Scanner déjà en cours, attendre qu'il se termine
            print("⚠️ Scanner déjà en cours, attente de la fin...")
            max_wait = 60
            waited = 0
            check_interval = 2
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                # Vérifier si on a maintenant des top pairs
                response = requests.get(f"{BASE_URL}/api/scanner/top-pairs", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    top_pairs = data.get('pairs', data) if isinstance(data, dict) else data
                    if isinstance(top_pairs, list) and len(top_pairs) > 0:
                        print(f"✅ Scan terminé ! {len(top_pairs)} top pairs disponibles")
                        return True
                
                # Afficher progression
                if waited % 10 == 0:
                    print(f"   ... attente ({waited}/{max_wait}s)...")
            
            print("⚠️ Timeout: le scan prend plus de temps que prévu")
            return False
        else:
            print(f"❌ Erreur démarrage scanner: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def start_websocket():
    """Démarrer le WebSocket"""
    try:
        print("🚀 Démarrage du WebSocket...")
        response = requests.post(f"{BASE_URL}/api/websocket/start", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ WebSocket démarré!")
            print(f"   - Symboles: {data.get('symbols_count', 0)}")
            print(f"   - Premiers: {', '.join(data.get('symbols', [])[:5])}")
            return True
        elif response.status_code == 400:
            error_data = response.json()
            if error_data.get('status') == 'no_pairs':
                print("⚠️ Aucune top pair disponible, démarrage du scanner...")
                if start_scanner_if_needed():
                    # Réessayer après le scan
                    time.sleep(2)
                    return start_websocket()
                else:
                    return False
            else:
                print(f"❌ Erreur: {error_data.get('error', 'Unknown')}")
                return False
        else:
            print(f"❌ Erreur: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Erreur démarrage WebSocket: {e}")
        return False

def main():
    print("=" * 50)
    print("🔍 VÉRIFICATION ET DÉMARRAGE WEBSOCKET")
    print("=" * 50)
    print()
    
    # 1. Vérifier l'état actuel
    print("1️⃣ Vérification de l'état actuel...")
    status = check_websocket_status()
    print()
    
    # 2. Si pas connecté, démarrer
    if not status or not status.get('websocket_connected', False):
        print("2️⃣ WebSocket non connecté, démarrage...")
        if start_websocket():
            print()
            print("3️⃣ Attente de 2 secondes pour la connexion...")
            time.sleep(2)
            
            # 4. Vérifier à nouveau
            print("4️⃣ Vérification finale...")
            final_status = check_websocket_status()
            
            if final_status and final_status.get('websocket_connected', False):
                print()
                print("=" * 50)
                print("✅ SUCCÈS: WebSocket connecté et fonctionnel!")
                print("=" * 50)
                
                # Afficher quelques prix
                prices = final_status.get('prices', {})
                if prices:
                    print("\n📊 Premiers prix en cache:")
                    for i, (symbol, price_data) in enumerate(list(prices.items())[:5]):
                        print(f"   {symbol}: {price_data.get('price', 0)} (âge: {price_data.get('age_seconds', 0)}s)")
            else:
                print()
                print("=" * 50)
                print("⚠️ WebSocket démarré mais pas encore connecté")
                print("   Attendez quelques secondes et réessayez")
                print("=" * 50)
        else:
            print()
            print("=" * 50)
            print("❌ ÉCHEC: Impossible de démarrer le WebSocket")
            print("=" * 50)
    else:
        print()
        print("=" * 50)
        print("✅ WebSocket déjà connecté!")
        print("=" * 50)
        
        # Afficher quelques prix
        prices = status.get('prices', {})
        if prices:
            print("\n📊 Premiers prix en cache:")
            for i, (symbol, price_data) in enumerate(list(prices.items())[:5]):
                print(f"   {symbol}: {price_data.get('price', 0)} (âge: {price_data.get('age_seconds', 0)}s)")

if __name__ == "__main__":
    main()

