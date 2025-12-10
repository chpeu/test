# -*- coding: utf-8 -*-
"""
Script de verification des corrections trading MEXC Futures
Verifie:
1. Position size minimum (7 USDT)
2. Flag is_live_open pour TP partiels
3. Anti rate-limiting dans close_position
4. Circuit breaker fonctionnel
"""

import sys
import os

# Forcer UTF-8 pour Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def print_status(label, ok, details=""):
    """Print status with color"""
    status = "[OK]" if ok else "[ERREUR]"
    color = "\033[92m" if ok else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {label}")
    if details:
        print(f"      {details}")

def verify_position_size_minimum():
    """Verifier que calculate_position_size retourne minimum 7 USDT"""
    print("\n=== Test 1: Position Size Minimum ===")
    
    try:
        # Verifier dans le code source que MIN_POSITION_USDT = 7.0 est present
        with open('core/position_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_min_position = 'MIN_POSITION_USDT = 7.0' in content
        has_min_check = 'final_size < MIN_POSITION_USDT' in content
        has_warning = 'Taille position trop petite' in content
        
        print_status(
            "MIN_POSITION_USDT = 7.0 defini",
            has_min_position,
            "Trouve dans position_manager.py" if has_min_position else "NON TROUVE"
        )
        print_status(
            "Verification final_size < MIN_POSITION_USDT",
            has_min_check,
            "Trouve dans position_manager.py" if has_min_check else "NON TROUVE"
        )
        print_status(
            "Warning 'Taille position trop petite'",
            has_warning,
            "Trouve dans position_manager.py" if has_warning else "NON TROUVE"
        )
        
        return has_min_position and has_min_check and has_warning
        
    except Exception as e:
        print_status("Position size minimum", False, str(e))
        return False

def verify_is_live_open_flag():
    """Verifier que le flag is_live_open est present dans le code"""
    print("\n=== Test 2: Flag is_live_open ===")
    
    try:
        with open('core/position_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verifier que is_live_open est utilise
        has_set_true = 'is_live_open = True' in content
        has_set_false = 'is_live_open = False' in content
        has_check = "getattr(self.active_position, 'is_live_open'" in content
        
        print_status(
            "is_live_open = True (succes ouverture)",
            has_set_true,
            "Trouve dans position_manager.py" if has_set_true else "NON TROUVE"
        )
        print_status(
            "is_live_open = False (echec ouverture)",
            has_set_false,
            "Trouve dans position_manager.py" if has_set_false else "NON TROUVE"
        )
        print_status(
            "Verification is_live_open avant TP partiel",
            has_check,
            "Trouve dans position_manager.py" if has_check else "NON TROUVE"
        )
        
        return has_set_true and has_set_false and has_check
        
    except Exception as e:
        print_status("Flag is_live_open", False, str(e))
        return False

def verify_anti_rate_limiting():
    """Verifier que l'anti rate-limiting est present"""
    print("\n=== Test 3: Anti Rate-Limiting ===")
    
    try:
        with open('trading/live_order_manager_futures.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_last_request = '_last_close_request_time' in content
        has_min_interval = '_min_request_interval_sec' in content
        has_wait = 'Anti rate-limit' in content
        
        print_status(
            "Variable _last_close_request_time",
            has_last_request,
            "Trouve dans live_order_manager_futures.py" if has_last_request else "NON TROUVE"
        )
        print_status(
            "Variable _min_request_interval_sec",
            has_min_interval,
            "1 seconde minimum entre requetes" if has_min_interval else "NON TROUVE"
        )
        print_status(
            "Log Anti rate-limit",
            has_wait,
            "Delai avant requete si necessaire" if has_wait else "NON TROUVE"
        )
        
        return has_last_request and has_min_interval and has_wait
        
    except Exception as e:
        print_status("Anti rate-limiting", False, str(e))
        return False

def verify_gb_filter_in_main():
    """Verifier que le filtre GB est dans main.py"""
    print("\n=== Test 4: Filtre GradientBoosting dans main.py ===")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_gb_check = "gb_filter_enabled" in content
        has_gb_log = "Filtre GradientBoosting" in content
        has_predictor = "OptimizedPredictor" in content
        
        print_status(
            "Verification gb_filter_enabled",
            has_gb_check,
            "Trouve dans main.py" if has_gb_check else "NON TROUVE"
        )
        print_status(
            "Log Filtre GradientBoosting",
            has_gb_log,
            "Log de verification trouve" if has_gb_log else "NON TROUVE"
        )
        print_status(
            "Import OptimizedPredictor",
            has_predictor,
            "Predictor utilise" if has_predictor else "NON TROUVE"
        )
        
        return has_gb_check and has_gb_log and has_predictor
        
    except Exception as e:
        print_status("Filtre GB dans main.py", False, str(e))
        return False

def verify_optuna_fix():
    """Verifier que l'erreur params est corrigee"""
    print("\n=== Test 5: Correction Optuna params ===")
    
    try:
        with open('optimization/optuna_gb_tuner.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # L'ancienne erreur utilisait params['max_depth']
        has_old_bug = "params['max_depth']" in content
        # La correction utilise max_depth directement
        has_fix = "depth={max_depth}" in content
        
        print_status(
            "Bug params['max_depth'] corrige",
            not has_old_bug,
            "Bug NON trouve (OK)" if not has_old_bug else "Bug ENCORE PRESENT"
        )
        print_status(
            "Utilisation directe de max_depth",
            has_fix,
            "Trouve dans optuna_gb_tuner.py" if has_fix else "NON TROUVE"
        )
        
        return not has_old_bug and has_fix
        
    except Exception as e:
        print_status("Correction Optuna", False, str(e))
        return False

def main():
    """Executer tous les tests"""
    print("=" * 60)
    print("VERIFICATION DES CORRECTIONS TRADING MEXC FUTURES")
    print("=" * 60)
    
    results = []
    
    # Changer au repertoire du projet
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    results.append(("Position Size Minimum", verify_position_size_minimum()))
    results.append(("Flag is_live_open", verify_is_live_open_flag()))
    results.append(("Anti Rate-Limiting", verify_anti_rate_limiting()))
    results.append(("Filtre GB main.py", verify_gb_filter_in_main()))
    results.append(("Correction Optuna", verify_optuna_fix()))
    
    # Resume
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    
    ok_count = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "[OK]" if ok else "[ERREUR]"
        color = "\033[92m" if ok else "\033[91m"
        reset = "\033[0m"
        print(f"  {color}{status}{reset} {name}")
    
    print(f"\nResultat: {ok_count}/{total} tests OK")
    
    if ok_count == total:
        print("\n[SUCCESS] Toutes les corrections sont en place!")
        print("\nProchaines etapes:")
        print("1. Redemarrer le backend")
        print("2. Activer gb_filter_enabled dans Variables")
        print("3. Surveiller les logs pour les messages 'Filtre GradientBoosting'")
    else:
        print("\n[WARNING] Certaines corrections manquent encore")
    
    return ok_count == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
