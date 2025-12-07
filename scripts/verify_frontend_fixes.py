#!/usr/bin/env python3
"""
Script de verification des fixes frontend
- ML Confidence & Sizing badges dans PositionCard
- Checkboxes Telegram dans NotificationSettings
"""

import os
import sys

# Desactiver les couleurs sur Windows pour eviter les problemes d'encodage
if sys.platform == 'win32':
    GREEN = ""
    RED = ""
    YELLOW = ""
    RESET = ""
else:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

def check_file_contains(filepath: str, patterns: list, description: str) -> bool:
    """Verifie qu'un fichier contient tous les patterns"""
    if not os.path.exists(filepath):
        print(f"{RED}[X] Fichier non trouve: {filepath}{RESET}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        if pattern in content:
            print(f"  {GREEN}[OK]{RESET} '{pattern[:50]}...' trouve")
        else:
            print(f"  {RED}[X]{RESET} '{pattern[:50]}...' MANQUANT")
            all_found = False
    
    if all_found:
        print(f"{GREEN}[OK] {description}: OK{RESET}")
    else:
        print(f"{RED}[X] {description}: INCOMPLET{RESET}")
    
    return all_found

def main():
    print("=" * 60)
    print("VERIFICATION DES FIXES FRONTEND")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)
    
    all_ok = True
    
    # 1. Verifier PositionCard.svelte - HTML
    print("\n[1] PositionCard.svelte - Badges ML/Sizing (HTML)")
    print("-" * 40)
    ok = check_file_contains(
        "frontend/src/lib/components/PositionCard.svelte",
        [
            "ml-sizing-badges",
            "$activePosition.ml_confidence",
            "$activePosition.adaptive_sizing_multiplier",
            "ml-badge",
            "sizing-badge"
        ],
        "Badges ML/Sizing HTML"
    )
    all_ok = all_ok and ok
    
    # 2. Verifier PositionCard.svelte - CSS
    print("\n[2] PositionCard.svelte - Badges ML/Sizing (CSS)")
    print("-" * 40)
    ok = check_file_contains(
        "frontend/src/lib/components/PositionCard.svelte",
        [
            ".ml-sizing-badges {",
            ".ml-badge {",
            ".sizing-badge {",
            ".sizing-badge.boost {"
        ],
        "Badges ML/Sizing CSS"
    )
    all_ok = all_ok and ok
    
    # 3. Verifier NotificationSettings.svelte - Checkboxes CSS
    print("\n[3] NotificationSettings.svelte - Checkboxes Telegram (CSS)")
    print("-" * 40)
    ok = check_file_contains(
        "frontend/src/lib/components/NotificationSettings.svelte",
        [
            ".notify-type-item {",
            '.notify-type-item input[type="checkbox"]',
            "-webkit-appearance: none",
            "min-width: 22px",
            ".notify-type-item input[type=\"checkbox\"]:checked::after"
        ],
        "Checkboxes Telegram CSS"
    )
    all_ok = all_ok and ok
    
    # 4. Verifier position_manager.py - Champs Position
    print("\n[4] position_manager.py - Champs Position dataclass")
    print("-" * 40)
    ok = check_file_contains(
        "core/position_manager.py",
        [
            "ml_confidence: Optional[float]",
            "adaptive_sizing_multiplier: Optional[float]",
            "'ml_confidence': self.ml_confidence",
            "'adaptive_sizing_multiplier': self.adaptive_sizing_multiplier"
        ],
        "Champs Position dataclass"
    )
    all_ok = all_ok and ok
    
    # 5. Verifier main.py - Passage des valeurs
    print("\n[5] main.py - Passage ml_confidence & adaptive_sizing_multiplier")
    print("-" * 40)
    ok = check_file_contains(
        "main.py",
        [
            "adaptive_sizing_mult = ",
            "get_adaptive_sizing_manager()",
            "adaptive_sizing_multiplier=adaptive_sizing_mult"
        ],
        "Passage valeurs main.py"
    )
    all_ok = all_ok and ok
    
    # 6. Verifier scanner_loop.py - Passage des valeurs
    print("\n[6] scanner_loop.py - Passage adaptive_sizing_multiplier")
    print("-" * 40)
    ok = check_file_contains(
        "core/callbacks/scanner_loop.py",
        [
            "adaptive_sizing_mult = ",
            "adaptive_sizing_multiplier=adaptive_sizing_mult"
        ],
        "Passage valeurs scanner_loop.py"
    )
    all_ok = all_ok and ok
    
    # Resume
    print("\n" + "=" * 60)
    if all_ok:
        print(f"{GREEN}[OK] TOUTES LES VERIFICATIONS PASSEES{RESET}")
        print(f"\n{YELLOW}ACTIONS REQUISES:{RESET}")
        print("  1. Redemarrer le backend (python main.py)")
        print("  2. Hard refresh frontend (Ctrl+Shift+R ou Cmd+Shift+R)")
        print("  3. Sur iPhone: vider cache Safari (Reglages > Safari > Effacer historique)")
        print("  4. Les badges ML n'apparaissent que si une position a ete ouverte APRES le fix")
    else:
        print(f"{RED}[X] CERTAINES VERIFICATIONS ONT ECHOUE{RESET}")
        print("Verifiez les fichiers ci-dessus pour les patterns manquants.")
    print("=" * 60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
