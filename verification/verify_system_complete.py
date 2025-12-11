"""
Script de vérification complète du système
Vérifie: Frontend, Backend, API, Config, Suggestions
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check_api(endpoint, method="GET", expected_keys=None):
    """Vérifie qu'un endpoint API répond correctement"""
    try:
        if method == "GET":
            resp = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
        else:
            resp = requests.post(f"{BASE_URL}{endpoint}", timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if expected_keys:
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    return False, f"Clés manquantes: {missing}"
            return True, data
        else:
            return False, f"Status {resp.status_code}"
    except Exception as e:
        return False, str(e)

def main():
    print("\n" + "🔍 VÉRIFICATION SYSTÈME COMPLÈTE".center(60))
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # 1. API Config
    print_section("1. API Configuration")
    ok, data = check_api("/api/config")
    if ok:
        print(f"   ✅ /api/config OK")
        print(f"   📊 Paramètres: {len(data)} clés")
        results.append(("Config API", True))
    else:
        print(f"   ❌ /api/config ERREUR: {data}")
        results.append(("Config API", False))
    
    # 2. API Régime
    print_section("2. API Market Regime")
    ok, data = check_api("/api/regime/status")
    if ok:
        print(f"   ✅ /api/regime/status OK")
        print(f"   📈 Régime actuel: {data.get('current_regime', 'N/A')}")
        print(f"   📊 ATR moyen: {data.get('avg_atr', 0):.4f}%")
        results.append(("Regime API", True))
    else:
        print(f"   ❌ /api/regime/status ERREUR: {data}")
        results.append(("Regime API", False))
    
    # 3. API Corrélations
    print_section("3. API Corrélations & Suggestions")
    ok, data = check_api("/api/ml/analytics/correlations?days=7")
    if ok:
        print(f"   ✅ /api/ml/analytics/correlations OK")
        suggestions = data.get('suggestions', [])
        print(f"   💡 Suggestions: {len(suggestions)}")
        for s in suggestions[:3]:
            print(f"      [{s.get('confidence')}] {s.get('parameter')}: {s.get('suggested_value')}")
        results.append(("Correlations API", True))
    else:
        print(f"   ❌ /api/ml/analytics/correlations ERREUR: {data}")
        results.append(("Correlations API", False))
    
    # 4. API Bot Status
    print_section("4. API Bot Status")
    ok, data = check_api("/api/status")
    if ok:
        print(f"   ✅ /api/status OK")
        print(f"   🤖 Bot actif: {data.get('active', 'N/A')}")
        print(f"   💰 Position: {data.get('position', 'None')}")
        results.append(("Bot Status API", True))
    else:
        print(f"   ❌ /api/status ERREUR: {data}")
        results.append(("Bot Status API", False))
    
    # 5. Vérification config appliquée
    print_section("5. Vérification Config Active")
    ok, config = check_api("/api/config")
    ok2, regime = check_api("/api/regime/status")
    if ok and ok2:
        regime_config = regime.get('config_active', {})
        print(f"   📋 Config bot:")
        print(f"      - min_score_required: {config.get('min_score_required', 'N/A')}")
        print(f"      - atr_mult_sl: {config.get('atr_mult_sl', 'N/A')}")
        print(f"   📋 Config régime actif:")
        print(f"      - min_score_required: {regime_config.get('min_score_required', 'N/A')}")
        print(f"      - atr_mult_sl: {regime_config.get('atr_mult_sl', 'N/A')}")
        results.append(("Config Active", True))
    
    # Résumé
    print_section("RÉSUMÉ")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"   {'✅' if passed == total else '⚠️'} {passed}/{total} vérifications OK")
    
    for name, ok in results:
        print(f"   {'✅' if ok else '❌'} {name}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    print("\n")
    exit(0 if success else 1)
