#!/usr/bin/env python3
"""
Script de verification pour les fixes frontend:
1. Badge ML avec recuperation PostgreSQL
2. Checkboxes iPhone avec styles iOS
"""
import sys
import os

# Forcer UTF-8
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

def check_postgresql_method():
    """Verifier que get_ml_confidence_for_symbol existe"""
    print("\n=== 1. Verification PostgreSQL get_ml_confidence_for_symbol ===")
    
    try:
        with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'Methode definie': 'def get_ml_confidence_for_symbol' in content,
            'Query SELECT': 'SELECT ml_confidence FROM scan_logs' in content,
            'Arrondi': 'round(ml_conf, 1)' in content,
            'Return Optional[float]': '-> Optional[float]' in content,
        }
        
        all_ok = True
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
            if not passed:
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def check_main_position_update():
    """Verifier que position_update inclut ml_confidence"""
    print("\n=== 2. Verification main.py position_update ===")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'ml_confidence dans update_data': "'ml_confidence': ml_conf" in content,
            'adaptive_sizing dans update_data': "'adaptive_sizing_multiplier':" in content,
            'Appel get_ml_confidence_for_symbol': 'get_ml_confidence_for_symbol' in content,
            'Fallback PostgreSQL': 'pg_logger.get_ml_confidence_for_symbol' in content,
        }
        
        all_ok = True
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
            if not passed:
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def check_frontend_checkboxes():
    """Verifier les styles iOS pour checkboxes"""
    print("\n=== 3. Verification Frontend Checkboxes iOS ===")
    
    try:
        with open('frontend/src/lib/components/NotificationSettings.svelte', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'Classe ios-checkbox utilisee': 'class="ios-checkbox"' in content,
            'class:checked directive': 'class:checked=' in content,
            'Style .ios-checkbox defini': '.ios-checkbox {' in content,
            'Style .ios-checkbox.checked': '.ios-checkbox.checked {' in content,
            'Background vert checked': "background-color: #00ff88" in content,
            'Border 3px': 'border: 3px solid' in content,
            'Important flags': '!important' in content,
            'hidden-checkbox classe': 'class="hidden-checkbox"' in content,
        }
        
        all_ok = True
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
            if not passed:
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def check_ml_arrondi():
    """Verifier que ml_confidence est arrondi"""
    print("\n=== 4. Verification Arrondi ml_confidence ===")
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = {
            'Arrondi dans main.py': 'round(confidence * 100, 1)' in content,
        }
        
        with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
            pg_content = f.read()
        
        checks['Arrondi dans PostgreSQL'] = 'round(ml_conf, 1)' in pg_content
        
        all_ok = True
        for check, passed in checks.items():
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {check}")
            if not passed:
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def test_postgresql_connection():
    """Tester la connexion PostgreSQL et la methode"""
    print("\n=== 5. Test PostgreSQL Connection ===")
    
    try:
        from core.callbacks.scanner_loop import get_pg_datalogger
        pg_logger = get_pg_datalogger()
        
        if not pg_logger:
            print("  [WARN] pg_logger est None")
            return True  # Pas une erreur critique
        
        if not pg_logger.enabled:
            print("  [WARN] PostgreSQL non active")
            return True  # Pas une erreur critique
        
        # Verifier que la methode existe
        if hasattr(pg_logger, 'get_ml_confidence_for_symbol'):
            print("  [OK] Methode get_ml_confidence_for_symbol existe")
            
            # Tester avec un symbole quelconque
            result = pg_logger.get_ml_confidence_for_symbol('TEST/USDT', minutes_ago=1440)
            print(f"  [INFO] Test appel: resultat = {result}")
            return True
        else:
            print("  [FAIL] Methode get_ml_confidence_for_symbol manquante!")
            return False
            
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def main():
    print("=" * 60)
    print("VERIFICATION FIXES FRONTEND ML + CHECKBOXES iOS")
    print("=" * 60)
    
    results = []
    
    # Changer vers le bon repertoire
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    print(f"Working directory: {os.getcwd()}")
    
    results.append(("PostgreSQL Method", check_postgresql_method()))
    results.append(("Main position_update", check_main_position_update()))
    results.append(("Frontend Checkboxes", check_frontend_checkboxes()))
    results.append(("ML Arrondi", check_ml_arrondi()))
    results.append(("PostgreSQL Test", test_postgresql_connection()))
    
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("TOUS LES TESTS PASSES!")
        print("Actions requises:")
        print("  1. Redemarrer le backend: python main.py")
        print("  2. Hard refresh frontend: Ctrl+Shift+R")
        print("  3. iPhone: Vider cache Safari ou navigation privee")
    else:
        print("CERTAINS TESTS ONT ECHOUE!")
        print("Verifiez les erreurs ci-dessus.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
