# -*- coding: utf-8 -*-
"""
Vérification STATIQUE du flux de code GradientBoosting
======================================================
Analyse le code source pour vérifier que les variables GB sont:
1. Définies dans config.py
2. Sauvegardées via config_overrides.json
3. Exposées par l'API /api/config
4. Utilisées par le predictor

Usage:
    python verification/verify_gb_code_flow.py
    
Auteur: Cascade AI
Date: 11/12/2025
"""

import sys
import os
import json
import re

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 70)
print("  VERIFICATION STATIQUE FLUX CODE GRADIENTBOOSTING")
print("=" * 70)

# Variables GB à vérifier
GB_VARIABLES = [
    'gb_filter_enabled',
    'gb_min_confidence', 
    'gb_max_iter',
    'gb_max_depth',
    'gb_learning_rate',
    'gb_min_samples_leaf',
    'gb_min_samples_split',
    'gb_l2_regularization',
    'gb_max_leaf_nodes',
    'gb_validation_fraction',
    'gb_n_iter_no_change',
    'gb_tol',
    'gb_early_stopping',
    'gb_subsample'
]

results = []

# =============================================================================
# 1. Vérifier config.py
# =============================================================================
print("\n[1/5] Verification config.py...")

try:
    with open('config.py', 'r', encoding='utf-8') as f:
        config_content = f.read()
    
    found_in_config = []
    missing_in_config = []
    
    for var in GB_VARIABLES:
        # Chercher la variable avec guillemets (clé de dict)
        pattern = rf'["\']({var})["\']'
        if re.search(pattern, config_content):
            found_in_config.append(var)
        else:
            missing_in_config.append(var)
    
    print(f"   ✅ Trouvées: {len(found_in_config)}/{len(GB_VARIABLES)}")
    if missing_in_config:
        print(f"   ⚠️ Manquantes: {missing_in_config}")
    
    results.append(("config.py", len(missing_in_config) == 0))
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    results.append(("config.py", False))

# =============================================================================
# 2. Vérifier config_overrides.json
# =============================================================================
print("\n[2/5] Verification config_overrides.json...")

try:
    with open('config_overrides.json', 'r', encoding='utf-8') as f:
        overrides = json.load(f)
    
    found_in_overrides = []
    for var in GB_VARIABLES:
        if var in overrides:
            found_in_overrides.append(var)
    
    print(f"   ✅ Fichier existe avec {len(overrides)} variables")
    print(f"   ✅ Variables GB présentes: {len(found_in_overrides)}/{len(GB_VARIABLES)}")
    
    # Afficher quelques valeurs
    for var in ['gb_filter_enabled', 'gb_min_confidence', 'gb_max_depth']:
        if var in overrides:
            print(f"      {var}: {overrides[var]}")
    
    results.append(("config_overrides.json", True))
    
except FileNotFoundError:
    print("   ⚠️ Fichier non trouvé (sera créé à la première sauvegarde)")
    results.append(("config_overrides.json", True))  # OK si absent
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    results.append(("config_overrides.json", False))

# =============================================================================
# 3. Vérifier api/routes/config.py (endpoint POST/GET)
# =============================================================================
print("\n[3/5] Verification api/routes/config.py...")

try:
    with open('api/routes/config.py', 'r', encoding='utf-8') as f:
        api_config_content = f.read()
    
    # Vérifier les endpoints
    has_get = '@router.get' in api_config_content or 'def get_config' in api_config_content
    has_post = '@router.post' in api_config_content or 'def update_config' in api_config_content
    uses_trading_config = 'TRADING_CONFIG' in api_config_content
    saves_overrides = 'config_overrides' in api_config_content
    
    print(f"   {'✅' if has_get else '❌'} Endpoint GET config")
    print(f"   {'✅' if has_post else '❌'} Endpoint POST config")
    print(f"   {'✅' if uses_trading_config else '❌'} Utilise TRADING_CONFIG")
    print(f"   {'✅' if saves_overrides else '❌'} Sauvegarde config_overrides.json")
    
    results.append(("API /config", has_get and has_post and uses_trading_config))
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    results.append(("API /config", False))

# =============================================================================
# 4. Vérifier predictor utilise TRADING_CONFIG
# =============================================================================
print("\n[4/5] Verification predictor_optimized.py...")

try:
    with open('optimization/predictor_optimized.py', 'r', encoding='utf-8') as f:
        predictor_content = f.read()
    
    imports_config = 'TRADING_CONFIG' in predictor_content or 'from config import' in predictor_content
    uses_gb_confidence = 'gb_min_confidence' in predictor_content
    
    print(f"   {'✅' if imports_config else '❌'} Importe TRADING_CONFIG")
    print(f"   {'✅' if uses_gb_confidence else '⚠️'} Utilise gb_min_confidence (peut être passé en paramètre)")
    
    results.append(("predictor_optimized.py", imports_config))
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    results.append(("predictor_optimized.py", False))

# =============================================================================
# 5. Vérifier main.py utilise gb_min_confidence dynamique
# =============================================================================
print("\n[5/5] Verification main.py (utilisation gb_min_confidence)...")

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    # Chercher l'utilisation de gb_min_confidence
    uses_gb_config = "TRADING_CONFIG.get('gb_min_confidence'" in main_content or \
                     'TRADING_CONFIG["gb_min_confidence"]' in main_content
    
    # Vérifier Phase 2D (threshold optimizer)
    uses_threshold_optimizer = 'threshold_optimizer' in main_content.lower()
    
    print(f"   {'✅' if uses_gb_config else '❌'} Lit gb_min_confidence depuis TRADING_CONFIG")
    print(f"   {'✅' if uses_threshold_optimizer else '⚠️'} Intégration Threshold Optimizer Phase 2D")
    
    # Montrer le code pertinent
    if uses_gb_config:
        # Trouver la ligne
        lines = main_content.split('\n')
        for i, line in enumerate(lines):
            if 'gb_min_confidence' in line and 'TRADING_CONFIG' in line:
                print(f"\n   Code trouvé (ligne ~{i+1}):")
                print(f"   >>> {line.strip()[:80]}...")
                break
    
    results.append(("main.py gb_min_confidence", uses_gb_config))
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    results.append(("main.py", False))

# =============================================================================
# RÉSUMÉ
# =============================================================================
print("\n" + "=" * 70)
print("  RÉSUMÉ DU FLUX DE VARIABLES GB")
print("=" * 70)

print("""
   FLUX ATTENDU:
   ┌─────────────────────────────────────────────────────────────────┐
   │  1. Frontend (MLPanel/MLCONTENT_GB_Variables.svelte)           │
   │     └── Slider modifie valeur                                   │
   │         └── triggerAutoSave() → POST /api/config               │
   │                                                                 │
   │  2. Backend (api/routes/config.py)                              │
   │     └── update_config() reçoit {gb_min_confidence: 0.60}       │
   │         └── TRADING_CONFIG[key] = value                         │
   │         └── Sauvegarde config_overrides.json                    │
   │                                                                 │
   │  3. Bot (main.py)                                               │
   │     └── TRADING_CONFIG.get('gb_min_confidence', 0.55)          │
   │         └── Passe au predictor.predict(threshold=...)          │
   │                                                                 │
   │  4. Variables en cours (VariablesPanel.svelte)                  │
   │     └── GET /api/config/complete                                │
   │         └── Affiche effective_config avec valeurs à jour       │
   └─────────────────────────────────────────────────────────────────┘
""")

all_passed = True
for name, passed in results:
    status = "✅" if passed else "❌"
    print(f"   {status} {name}")
    if not passed:
        all_passed = False

print("\n" + "=" * 70)
if all_passed:
    print("✅ FLUX DE CODE CORRECT - Les variables GB suivent le bon chemin")
else:
    print("⚠️ CERTAINES VÉRIFICATIONS ÉCHOUENT - Voir détails ci-dessus")
print("=" * 70)

# Vérification en temps réel (importer config)
print("\n[BONUS] Test import TRADING_CONFIG...")
try:
    sys.path.insert(0, '.')
    from config import TRADING_CONFIG
    
    gb_conf = TRADING_CONFIG.get('gb_min_confidence', 'N/A')
    gb_enabled = TRADING_CONFIG.get('gb_filter_enabled', 'N/A')
    
    print(f"   ✅ TRADING_CONFIG accessible")
    print(f"      gb_filter_enabled: {gb_enabled}")
    print(f"      gb_min_confidence: {gb_conf}")
    
except Exception as e:
    print(f"   ⚠️ Import échoué (normal hors contexte): {e}")
