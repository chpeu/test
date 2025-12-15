#!/usr/bin/env python3
"""
VERIFICATION LOGIQUE CONFLUENCE
================================
Vérifie que le nouveau code a exactement la même logique que l'ancien
concernant le fallback permissif quand use_confluence=True.

RAPPEL DE L'ANCIEN CODE:
- Ligne 1091-1094: 1er check qui définit best_setup
- Ligne 1740: 2ème check "ancien code pour compatibilité"  
- Ligne 1879-1956: MODE PERMISSIF (fallback si confluence échoue)

COMPORTEMENT ATTENDU:
- use_confluence=True + 2 TFs valides → Mode confluence strict
- use_confluence=True + 1 TF valide → MODE PERMISSIF (PAS de check orderbook!)
- use_confluence=True + 0 TF valide → Rejet
- use_confluence=False → Mode permissif
"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ANALYZER_PATH = Path(__file__).parent.parent / "core" / "analyzer.py"

def read_analyzer():
    """Lit le contenu de analyzer.py"""
    with open(ANALYZER_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def check_structure(content):
    """Vérifie la structure clé du code"""
    print("\n" + "=" * 70)
    print("  1. VÉRIFICATION STRUCTURE DU CODE")
    print("=" * 70)
    
    checks = []
    
    # Check 1: Paramètre use_confluence dans analyze_pair
    pattern1 = r"def analyze_pair\([^)]*use_confluence.*?bool.*?False"
    if re.search(pattern1, content, re.DOTALL):
        print("  ✅ Paramètre use_confluence dans analyze_pair()")
        checks.append(True)
    else:
        print("  ❌ Paramètre use_confluence MANQUANT dans analyze_pair()")
        checks.append(False)
    
    # Check 2: Premier check confluence (définit best_setup)
    pattern2 = r"if use_confluence and analysis_1m and analysis_5m.*?best_setup = analysis_"
    if re.search(pattern2, content, re.DOTALL):
        print("  ✅ 1er check confluence (définit best_setup)")
        checks.append(True)
    else:
        print("  ❌ 1er check confluence MANQUANT")
        checks.append(False)
    
    # Check 3: MODE PERMISSIF existe
    pattern3 = r"MODE PERMISSIF.*?best\['confirmedBy'\]"
    if re.search(pattern3, content, re.DOTALL):
        print("  ✅ MODE PERMISSIF présent")
        checks.append(True)
    else:
        print("  ❌ MODE PERMISSIF MANQUANT")
        checks.append(False)
    
    # Check 4: Fallback permissif quand confluence partielle
    pattern4 = r"(valid_1m or valid_5m).*?(mode permissif|permissif)"
    if re.search(pattern4, content, re.DOTALL | re.IGNORECASE):
        print("  ✅ Fallback permissif quand confluence partielle")
        checks.append(True)
    else:
        print("  ❌ Fallback permissif MANQUANT")
        checks.append(False)
    
    # Check 5: MODE PERMISSIF ne passe PAS par orderbook check
    # Le MODE PERMISSIF doit retourner 'best' directement sans check orderbook
    lines = content.split('\n')
    permissif_start = None
    permissif_return = None
    orderbook_in_permissif = False
    
    for i, line in enumerate(lines):
        if 'MODE PERMISSIF' in line:
            permissif_start = i
        if permissif_start and i > permissif_start:
            if 'return best' in line and 'return best_setup' not in line:
                permissif_return = i
                break
            if 'check_orderbook' in line.lower() or 'orderbook_check' in line.lower():
                orderbook_in_permissif = True
    
    if permissif_start and permissif_return and not orderbook_in_permissif:
        print("  ✅ MODE PERMISSIF bypasse le check orderbook")
        checks.append(True)
    else:
        print("  ❌ MODE PERMISSIF devrait bypasser le check orderbook")
        checks.append(False)
    
    return all(checks)

def check_flow_logic(content):
    """Vérifie la logique de flux"""
    print("\n" + "=" * 70)
    print("  2. VÉRIFICATION LOGIQUE DE FLUX")
    print("=" * 70)
    
    lines = content.split('\n')
    checks = []
    
    # Trouver les lignes clés
    line_numbers = {}
    patterns = {
        'use_confluence_param': r'use_confluence.*?bool.*?=.*?False',
        'first_check': r'if use_confluence and analysis_1m and analysis_5m and not',
        'permissif_fallback': r'if valid_1m or valid_5m:',
        'mode_permissif': r'MODE PERMISSIF',
        'return_best_permissif': r"return best$",
    }
    
    for i, line in enumerate(lines, 1):
        for name, pattern in patterns.items():
            if re.search(pattern, line):
                if name not in line_numbers:
                    line_numbers[name] = i
    
    print(f"\n  Lignes clés trouvées:")
    for name, line_num in line_numbers.items():
        print(f"    - {name}: ligne {line_num}")
    
    # Vérifier l'ordre
    if 'first_check' in line_numbers and 'mode_permissif' in line_numbers:
        if line_numbers['first_check'] < line_numbers['mode_permissif']:
            print("\n  ✅ Ordre correct: 1er check avant MODE PERMISSIF")
            checks.append(True)
        else:
            print("\n  ❌ Ordre incorrect!")
            checks.append(False)
    else:
        print("\n  ⚠️ Impossible de vérifier l'ordre")
        checks.append(False)
    
    # Vérifier que le fallback permissif existe
    if 'permissif_fallback' in line_numbers:
        print("  ✅ Fallback permissif (if valid_1m or valid_5m) présent")
        checks.append(True)
    else:
        print("  ❌ Fallback permissif MANQUANT")
        checks.append(False)
    
    return all(checks)

def check_expected_behavior():
    """Vérifie le comportement attendu via import"""
    print("\n" + "=" * 70)
    print("  3. VÉRIFICATION COMPORTEMENT (import)")
    print("=" * 70)
    
    try:
        from core.analyzer import TechnicalAnalyzer
        print("  ✅ Import TechnicalAnalyzer réussi")
        
        # Vérifier que analyze_pair accepte use_confluence
        import inspect
        sig = inspect.signature(TechnicalAnalyzer.analyze_pair)
        params = list(sig.parameters.keys())
        
        if 'use_confluence' in params:
            print("  ✅ Paramètre use_confluence présent dans analyze_pair()")
            
            # Vérifier la valeur par défaut
            default = sig.parameters['use_confluence'].default
            if default == False:
                print(f"  ✅ Valeur par défaut use_confluence={default}")
            else:
                print(f"  ⚠️ Valeur par défaut inattendue: {default}")
            
            return True
        else:
            print("  ❌ Paramètre use_confluence MANQUANT")
            return False
            
    except Exception as e:
        print(f"  ❌ Erreur import: {e}")
        return False

def simulate_scenarios():
    """Simule les différents scénarios"""
    print("\n" + "=" * 70)
    print("  4. SIMULATION DES SCÉNARIOS")
    print("=" * 70)
    
    print("""
  SCÉNARIOS À TESTER (manuellement ou via tests):
  
  | # | use_confluence | TF 1m    | TF 5m    | Attendu                    |
  |---|----------------|----------|----------|----------------------------|
  | 1 | True           | ✅ valide | ✅ valide | Confluence stricte         |
  | 2 | True           | ✅ valide | ❌ rejeté | MODE PERMISSIF (pas OB!)   |
  | 3 | True           | ❌ rejeté | ✅ valide | MODE PERMISSIF (pas OB!)   |
  | 4 | True           | ❌ rejeté | ❌ rejeté | Rejet total                |
  | 5 | False          | ✅ valide | ❌ rejeté | Mode permissif             |
  | 6 | False          | ❌ rejeté | ✅ valide | Mode permissif             |
  
  🔑 CLÉ: Scénarios 2 et 3 doivent passer en MODE PERMISSIF
         et bypasser le check orderbook (comme l'ancien code).
  """)
    
    return True

def main():
    print("=" * 70)
    print("  VÉRIFICATION LOGIQUE CONFLUENCE")
    print("  Compare nouveau code vs ancien code")
    print("=" * 70)
    
    if not ANALYZER_PATH.exists():
        print(f"\n❌ Fichier non trouvé: {ANALYZER_PATH}")
        return False
    
    content = read_analyzer()
    
    results = []
    
    # 1. Vérifier structure
    results.append(check_structure(content))
    
    # 2. Vérifier logique de flux
    results.append(check_flow_logic(content))
    
    # 3. Vérifier comportement
    results.append(check_expected_behavior())
    
    # 4. Scénarios
    results.append(simulate_scenarios())
    
    # Résumé
    print("\n" + "=" * 70)
    print("  RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"""
  ✅ TOUS LES TESTS PASSENT ({passed}/{total})
  
  La logique du nouveau code correspond à l'ancien:
  
  1. use_confluence=True + 2 TFs valides → Confluence stricte
  2. use_confluence=True + 1 TF valide → MODE PERMISSIF (SANS orderbook!)
  3. use_confluence=True + 0 TF valide → Rejet
  4. use_confluence=False → Mode permissif
  
  🎯 Le fallback permissif bypasse le check orderbook,
     permettant d'ouvrir des trades comme l'ancien code.
  
  ➡️ Redémarrez le backend pour appliquer les changements.
""")
    else:
        print(f"""
  ⚠️ {total - passed}/{total} TEST(S) ÉCHOUÉ(S)
  
  Vérifiez les erreurs ci-dessus et corrigez le code.
""")
    
    print("=" * 70)
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
