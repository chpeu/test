#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
Vérifie les paramètres ATR actuellement chargés dans l'instance live du bot.
"""

import os
import requests
import json

# URL de l'API du bot (ajuster si nécessaire)
API_BASE = os.getenv("BOT_API_URL", "http://localhost:8000")

def check_via_api():
    """Vérifier via l'API du bot"""
    print("="*70)
    print("VERIFICATION CONFIG LIVE VIA API")
    print("="*70)
    
    try:
        # Endpoint config
        response = requests.get(f"{API_BASE}/api/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            
            print("\n[1] Paramètres ATR depuis API:")
            atr_params = ['atr_mult_sl', 'atr_mult_tp', 'break_even_atr_mult', 'trailing_trigger_atr_mult']
            for param in atr_params:
                value = config.get(param, 'N/A')
                print(f"  {param}: {value}")
            
            # Vérifier les valeurs attendues
            print("\n[2] Vérification des nouvelles valeurs (28/12):")
            checks = [
                ('atr_mult_sl', config.get('atr_mult_sl'), 1.6),
                ('atr_mult_tp', config.get('atr_mult_tp'), 2.0),
            ]
            
            all_ok = True
            for name, actual, expected in checks:
                status = "✅" if actual == expected else "❌"
                if actual != expected:
                    all_ok = False
                print(f"  {status} {name}: {actual} (attendu: {expected})")
            
            if all_ok:
                print("\n  ✅ Nouveaux seuils ATR correctement appliqués!")
            else:
                print("\n  ❌ Certains seuils ne sont pas à jour!")
                
            return True
        else:
            print(f"  ⚠️ API retourne status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️ Impossible de se connecter à {API_BASE}")
        print("     Le bot est-il en cours d'exécution?")
        return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def check_via_regime_api():
    """Vérifier le régime actuel et ses paramètres"""
    print("\n" + "="*70)
    print("VERIFICATION REGIME ACTUEL")
    print("="*70)
    
    try:
        response = requests.get(f"{API_BASE}/api/regime/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n  Régime actuel: {data.get('current_regime', 'N/A')}")
            print(f"  ATR moyen: {data.get('avg_atr', 'N/A')}")
            print(f"  ADX moyen: {data.get('avg_adx', 'N/A')}")
            
            # Config du régime actuel
            config = data.get('current_config', {})
            if config:
                print(f"\n  Config du régime {data.get('current_regime')}:")
                print(f"    atr_mult_sl: {config.get('atr_mult_sl', 'N/A')}")
                print(f"    atr_mult_tp: {config.get('atr_mult_tp', 'N/A')}")
                print(f"    break_even_atr_mult: {config.get('break_even_atr_mult', 'N/A')}")
                print(f"    trailing_trigger_atr_mult: {config.get('trailing_trigger_atr_mult', 'N/A')}")
            
            return True
        else:
            print(f"  ⚠️ API régime retourne status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️ Endpoint régime non accessible")
        return False
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False

def check_via_effective_config():
    """Vérifier effective_config directement"""
    print("\n" + "="*70)
    print("VERIFICATION EFFECTIVE_CONFIG (IMPORT DIRECT)")
    print("="*70)
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import TRADING_CONFIG
        from utils.effective_config import get_effective_value
        
        print("\n[1] Valeurs TRADING_CONFIG:")
        print(f"  atr_mult_sl: {TRADING_CONFIG.get('atr_mult_sl', 'N/A')}")
        print(f"  atr_mult_tp: {TRADING_CONFIG.get('atr_mult_tp', 'N/A')}")
        
        print("\n[2] Valeurs effective_config (avec ajustements):")
        print(f"  atr_mult_sl: {get_effective_value('atr_mult_sl')}")
        print(f"  atr_mult_tp: {get_effective_value('atr_mult_tp')}")
        
        # Vérifier les nouvelles valeurs
        print("\n[3] Vérification des nouvelles valeurs (28/12):")
        sl_value = get_effective_value('atr_mult_sl')
        tp_value = get_effective_value('atr_mult_tp')
        
        sl_ok = sl_value == 1.6
        tp_ok = tp_value == 2.0
        
        print(f"  {'✅' if sl_ok else '❌'} atr_mult_sl: {sl_value} (attendu: 1.6)")
        print(f"  {'✅' if tp_ok else '❌'} atr_mult_tp: {tp_value} (attendu: 2.0)")
        
        if sl_ok and tp_ok:
            print("\n  ✅ NOUVEAUX SEUILS ATR CORRECTEMENT APPLIQUÉS!")
        else:
            print("\n  ❌ ATTENTION: Certains seuils ne sont pas à jour!")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*70)
    print("VERIFICATION INSTANCE LIVE - SEUILS ATR 28/12/2025")
    print("="*70)
    
    # Méthode 1: Import direct
    check_via_effective_config()
    
    # Méthode 2: Via API (si bot lance)
    api_ok = check_via_api()
    
    if api_ok:
        check_via_regime_api()
    
    print("\n" + "="*70)
    print("VERIFICATION TERMINEE")
    print("="*70)

if __name__ == "__main__":
    main()
