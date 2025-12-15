# -*- coding: utf-8 -*-
"""
Boucle de vérification complète : Config Frontend/Backend/Optimisation GradientBoosting
"""

import sys
import json
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 70)
print("  VERIFICATION COMPLETE GRADIENTBOOSTING")
print("=" * 70)

# =============================================================================
# 1. VALEURS OPTIMISEES (référence)
# =============================================================================
print("\n[1/5] VALEURS OPTIMISEES (reference)...")

OPTIMIZED_VALUES = {
    'gb_n_estimators': 271,
    'gb_max_depth': 6,
    'gb_learning_rate': 0.217,
    'gb_min_samples_split': 48,
    'gb_min_samples_leaf': 38,
    'gb_subsample': 0.734,
    'gb_max_features': 'sqrt'
}

print("   Hyperparametres optimises (68.5% accuracy):")
for k, v in OPTIMIZED_VALUES.items():
    print(f"      {k}: {v}")

# =============================================================================
# 2. CONFIG_OVERRIDES.JSON
# =============================================================================
print("\n[2/5] CONFIG_OVERRIDES.JSON...")

with open('config_overrides.json', 'r') as f:
    config_overrides = json.load(f)

config_errors = []
for key, expected in OPTIMIZED_VALUES.items():
    actual = config_overrides.get(key)
    status = "✅" if actual == expected else "❌"
    if actual != expected:
        config_errors.append(f"{key}: {actual} != {expected}")
    print(f"   {status} {key}: {actual} (attendu: {expected})")

# =============================================================================
# 3. MAIN.PY BACKEND LIMITS
# =============================================================================
print("\n[3/5] LIMITES BACKEND (main.py)...")

backend_limits = {
    'gb_n_estimators': (50, 500),
    'gb_max_depth': (2, 6),
    'gb_learning_rate': (0.01, 0.3),
    'gb_min_samples_split': (5, 50),
    'gb_min_samples_leaf': (5, 50),
    'gb_subsample': (0.5, 1.0),
}

backend_errors = []
for key, (min_val, max_val) in backend_limits.items():
    expected = OPTIMIZED_VALUES[key]
    if isinstance(expected, (int, float)):
        in_range = min_val <= expected <= max_val
        status = "✅" if in_range else "❌"
        if not in_range:
            backend_errors.append(f"{key}: {expected} hors limites [{min_val}, {max_val}]")
        print(f"   {status} {key}: limites [{min_val}, {max_val}], valeur optimisee: {expected}")

# =============================================================================
# 4. FRONTEND SLIDER LIMITS
# =============================================================================
print("\n[4/5] LIMITES FRONTEND (sliders)...")

# Lire le fichier Svelte pour extraire les limites
import re
with open('frontend/src/lib/components/ml/MLCONTENT_GB_Variables.svelte', 'r', encoding='utf-8') as f:
    svelte_content = f.read()

frontend_errors = []

# Extraire les limites des sliders
slider_patterns = {
    'gb_n_estimators': r'id="gb_n_estimators"[^>]*min="([^"]+)"[^>]*max="([^"]+)"',
    'gb_learning_rate': r'id="gb_learning_rate"[^>]*min="([^"]+)"[^>]*max="([^"]+)"',
    'gb_min_samples_split': r'id="gb_min_samples_split"[^>]*min="([^"]+)"[^>]*max="([^"]+)"',
    'gb_min_samples_leaf': r'id="gb_min_samples_leaf"[^>]*min="([^"]+)"[^>]*max="([^"]+)"',
    'gb_subsample': r'id="gb_subsample"[^>]*min="([^"]+)"[^>]*max="([^"]+)"',
}

for key, pattern in slider_patterns.items():
    match = re.search(pattern, svelte_content)
    if match:
        min_val, max_val = float(match.group(1)), float(match.group(2))
        expected = OPTIMIZED_VALUES[key]
        in_range = min_val <= expected <= max_val
        status = "✅" if in_range else "❌"
        if not in_range:
            frontend_errors.append(f"{key}: {expected} hors limites slider [{min_val}, {max_val}]")
        print(f"   {status} {key}: slider [{min_val}, {max_val}], valeur optimisee: {expected}")

# Vérifier le dropdown max_depth
max_depth_match = re.search(r'id="gb_max_depth".*?</select>', svelte_content, re.DOTALL)
if max_depth_match:
    dropdown_content = max_depth_match.group(0)
    options = re.findall(r'value=\{(\d+)\}', dropdown_content)
    has_6 = '6' in options
    status = "✅" if has_6 else "❌"
    if not has_6:
        frontend_errors.append(f"gb_max_depth: valeur 6 manquante dans dropdown, options: {options}")
    print(f"   {status} gb_max_depth: dropdown options={options}, valeur optimisee: 6")

# =============================================================================
# 5. SCRIPT D'ENTRAINEMENT
# =============================================================================
print("\n[5/5] SCRIPT D'ENTRAINEMENT...")

# Vérifier quel endpoint est appelé pour entraîner
training_issues = []

# Lire api/routes/ml.py pour voir comment le modèle est entraîné
with open('api/routes/ml.py', 'r', encoding='utf-8') as f:
    ml_routes = f.read()

# Vérifier si le script utilise les features sélectionnées
if 'selected_features' not in ml_routes and 'feature_selection' not in ml_routes.lower():
    training_issues.append("Le script d'entrainement n'utilise pas la selection de features (28 features)")
    print("   ❌ Pas de feature selection dans api/routes/ml.py")
else:
    print("   ✅ Feature selection presente")

# Vérifier si le preprocessing est correct
if 'StandardScaler' not in ml_routes and 'scaler' not in ml_routes.lower():
    training_issues.append("Le script d'entrainement n'utilise pas StandardScaler")
    print("   ❌ Pas de StandardScaler dans api/routes/ml.py")
else:
    print("   ✅ StandardScaler present")

# Vérifier si random_state est fixé
if 'random_state' not in ml_routes:
    training_issues.append("random_state non fixe - resultats non reproductibles")
    print("   ⚠️ random_state non fixe")
else:
    print("   ✅ random_state present")

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME DES PROBLEMES")
print("=" * 70)

all_errors = config_errors + backend_errors + frontend_errors + training_issues

if not all_errors:
    print("\n   ✅ Aucun probleme detecte!")
else:
    print(f"\n   ❌ {len(all_errors)} probleme(s) detecte(s):\n")
    for i, error in enumerate(all_errors, 1):
        print(f"   {i}. {error}")

print("\n" + "=" * 70)
print("  SOLUTION RECOMMANDEE")
print("=" * 70)

print("""
   Pour obtenir les 68.5% accuracy:
   
   1. Utiliser le modele PRE-ENTRAINE: gradient_boosting_optimized.pkl
      -> Ce modele utilise les 28 features selectionnees et le bon preprocessing
   
   2. OU modifier le script d'entrainement pour:
      - Charger les 28 features selectionnees depuis metadata
      - Appliquer StandardScaler
      - Utiliser random_state=42
      
   3. Le bouton "Reentrainer" du frontend utilise une logique differente
      qui ne reproduit pas l'optimisation avancee.
""")
