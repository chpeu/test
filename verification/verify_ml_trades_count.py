"""
🔍 Script de vérification du compteur ML Trades
Vérifie que le compteur reflète correctement le nombre de trades
correspondant à la config actuelle.
"""

import json
import requests
from pathlib import Path

# Couleurs pour affichage
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def load_current_config():
    """Charge la config depuis config_overrides.json"""
    config_path = Path("config_overrides.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}

def test_api_endpoint():
    """Teste l'endpoint /api/ml/dashboard/ml_trades_count"""
    print(f"\n{BLUE}=" * 60)
    print("TEST ENDPOINT /api/ml/dashboard/ml_trades_count")
    print(f"=" * 60 + RESET)
    
    try:
        response = requests.get("http://localhost:8000/api/ml/dashboard/ml_trades_count", timeout=10)
        if response.status_code != 200:
            print(f"{RED}❌ Erreur HTTP: {response.status_code}{RESET}")
            return None
        
        data = response.json()
        print(f"\n{GREEN}✅ Endpoint accessible{RESET}")
        return data
    except requests.exceptions.ConnectionError:
        print(f"{RED}❌ Backend non accessible sur localhost:8000{RESET}")
        return None
    except Exception as e:
        print(f"{RED}❌ Erreur: {e}{RESET}")
        return None

def display_results(data, config):
    """Affiche les résultats de manière lisible"""
    if not data:
        return
    
    print(f"\n{BLUE}📊 RÉSULTATS DU COMPTEUR{RESET}")
    print("-" * 40)
    
    # Compteurs
    total = data.get('total_trades', 0)
    manual = data.get('manual_excluded', 0)
    diff_config = data.get('different_config_excluded', 0)
    usable = data.get('config_filtered_trades', 0)
    
    print(f"  Total trades:           {total:,}")
    print(f"  - Manuels exclus:       {manual:,}")
    print(f"  - Configs différentes:  {diff_config:,}")
    print(f"  {GREEN}= Trades ML utilisables: {usable:,}{RESET}")
    
    # Config actuelle (depuis API)
    api_config = data.get('current_config', {})
    print(f"\n{BLUE}🔧 CONFIG ACTUELLE (depuis API){RESET}")
    print("-" * 40)
    
    # Validation setup
    print("  [Validation Setup]")
    print(f"    min_score:      {api_config.get('min_score')}")
    print(f"    snr_threshold:  {api_config.get('snr_threshold')}")
    print(f"    volume_mult:    {api_config.get('volume_mult')}")
    print(f"    use_confluence: {api_config.get('use_confluence')}")
    
    # ATR
    print("  [ATR Optimal]")
    print(f"    1m: [{api_config.get('atr_min_1m')} - {api_config.get('atr_max_1m')}]")
    print(f"    5m: [{api_config.get('atr_min_5m')} - {api_config.get('atr_max_5m')}]")
    
    # Filtres additionnels
    print("  [Filtres Additionnels]")
    print(f"    anti_whipsaw:   {api_config.get('use_anti_whipsaw')}")
    print(f"    candle_close:   {api_config.get('use_candle_close')}")
    print(f"    cooldown:       {api_config.get('use_cooldown')}")
    print(f"    momentum:       {api_config.get('use_momentum_continuity')}")
    print(f"    retest:         {api_config.get('use_retest_confirmation')}")
    
    # TP/SL
    print("  [TP/SL]")
    print(f"    mode:           {api_config.get('tp_sl_mode')}")
    print(f"    tp_percent:     {api_config.get('tp_percent')}")
    print(f"    sl_percent:     {api_config.get('sl_percent')}")
    
    # Breakdown
    breakdown = data.get('config_breakdown', [])
    if breakdown:
        print(f"\n{BLUE}📈 TOP 5 CONFIGS DANS LA BASE{RESET}")
        print("-" * 40)
        for i, cfg in enumerate(breakdown):
            marker = "👉" if cfg.get('is_current') else "  "
            print(f"  {marker} #{i+1}: min_score={cfg.get('min_score')}, snr={cfg.get('snr_threshold')}, "
                  f"vol={cfg.get('volume_mult')}, confluence={cfg.get('confluence')} "
                  f"→ {cfg.get('count'):,} trades")
    
    # Filtres appliqués
    filters = data.get('filters_applied', {})
    if filters:
        print(f"\n{BLUE}🔍 FILTRES APPLIQUÉS{RESET}")
        print("-" * 40)
        print(f"  Setup:      {', '.join(filters.get('setup_validation', []))}")
        print(f"  Additional: {', '.join(filters.get('additional_filters', []))}")
        print(f"  TP/SL:      {', '.join(filters.get('tp_sl', []))}")

def verify_config_match(data, config):
    """Vérifie que la config API match config_overrides.json"""
    print(f"\n{BLUE}🔍 VÉRIFICATION COHÉRENCE CONFIG{RESET}")
    print("-" * 40)
    
    api_config = data.get('current_config', {})
    
    checks = [
        ('min_score_required', 'min_score', config.get('min_score_required'), api_config.get('min_score')),
        ('snr_threshold', 'snr_threshold', config.get('snr_threshold'), api_config.get('snr_threshold')),
        ('volume_multiplier', 'volume_mult', config.get('volume_multiplier'), api_config.get('volume_mult')),
        ('use_confluence', 'use_confluence', config.get('use_confluence'), api_config.get('use_confluence')),
        ('tp_sl_mode', 'tp_sl_mode', config.get('tp_sl_mode'), api_config.get('tp_sl_mode')),
        ('tp_percent', 'tp_percent', config.get('tp_percent'), api_config.get('tp_percent')),
        ('sl_percent', 'sl_percent', config.get('sl_percent'), api_config.get('sl_percent')),
    ]
    
    all_ok = True
    for file_key, api_key, file_val, api_val in checks:
        if file_val is None:
            print(f"  ⚠️  {file_key}: pas dans config_overrides.json")
            continue
        
        # Comparaison avec tolérance pour floats
        if isinstance(file_val, float) and isinstance(api_val, float):
            match = abs(file_val - api_val) < 0.01
        else:
            match = file_val == api_val
        
        if match:
            print(f"  {GREEN}✅ {file_key}: {file_val} == {api_val}{RESET}")
        else:
            print(f"  {RED}❌ {file_key}: config_overrides={file_val} != API={api_val}{RESET}")
            all_ok = False
    
    return all_ok

def main():
    print(f"\n{BLUE}{'='*60}")
    print("   VÉRIFICATION COMPTEUR ML TRADES")
    print(f"{'='*60}{RESET}")
    
    # 1. Charger config locale
    config = load_current_config()
    print(f"\n📂 Config locale chargée: {len(config)} paramètres")
    
    # 2. Tester l'endpoint
    data = test_api_endpoint()
    if not data:
        print(f"\n{RED}❌ Impossible de tester - backend non accessible{RESET}")
        print("   Démarrez le backend avec: python main.py")
        return
    
    # 3. Afficher les résultats
    display_results(data, config)
    
    # 4. Vérifier cohérence
    config_ok = verify_config_match(data, config)
    
    # 5. Résumé
    print(f"\n{BLUE}{'='*60}")
    print("   RÉSUMÉ")
    print(f"{'='*60}{RESET}")
    
    usable = data.get('config_filtered_trades', 0)
    if usable >= 500:
        print(f"  {GREEN}✅ {usable:,} trades ML utilisables (suffisant){RESET}")
    elif usable >= 100:
        print(f"  {YELLOW}⚠️  {usable:,} trades ML utilisables (minimum){RESET}")
    else:
        print(f"  {RED}❌ {usable:,} trades ML utilisables (insuffisant){RESET}")
        print(f"     → Envisagez de relâcher les filtres ou d'attendre plus de trades")
    
    if config_ok:
        print(f"  {GREEN}✅ Config cohérente entre fichier et API{RESET}")
    else:
        print(f"  {RED}❌ Incohérence config - redémarrez le backend{RESET}")
    
    print(f"\n{BLUE}💡 Pour rafraîchir le compteur dans l'UI:{RESET}")
    print("   Cliquez sur le bouton 'Rafraîchir' dans l'onglet GradientBoosting")

if __name__ == "__main__":
    main()
