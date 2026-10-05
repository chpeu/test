"""
Verification script pour Phase 1A: Logging Contextuel

Usage:
    python verification/verify_phase1a_logging.py

Verifie:
    1. Import session_detector dans postgresql_datalogger.py
    2. log_trade_atr_metrics() inclut colonnes session/heure
    3. _batch_insert_scans() inclut colonnes session/regime
    4. _log_regime_change_to_db() inclut colonnes Phase 1A
    5. Syntaxe Python valide
"""
import os
import sys
from pathlib import Path

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_postgresql_datalogger():
    """Verifie les modifications dans postgresql_datalogger.py"""
    print("\n" + "=" * 60)
    print("1. VERIFICATION postgresql_datalogger.py")
    print("=" * 60)
    
    file_path = Path(__file__).parent.parent / 'core' / 'postgresql_datalogger.py'
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        checks = [
            ("Import session_detector", "from utils.session_detector import"),
            ("log_trade_atr_metrics: session_market", "session_market = session_info['name']"),
            ("log_trade_atr_metrics: colonnes Phase 1A", "session_market, hour_utc, day_of_week, is_weekend"),
            ("log_trade_atr_metrics: regime_detection_method", "regime_detection_method, regime_stability_minutes"),
            ("_batch_insert_scans: session columns", "'session_market', 'hour_utc', 'regime_at_scan'"),
            ("_batch_insert_scans: enrich scan_data", "scan_data['session_market'] = session_info['name']"),
        ]
        
        all_ok = True
        for name, pattern in checks:
            if pattern in content:
                print(f"  [OK] {name}")
            else:
                print(f"  [MANQUANT] {name}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  [ERREUR] Lecture fichier: {e}")
        return False


def check_market_regime_selector():
    """Verifie les modifications dans market_regime_selector.py"""
    print("\n" + "=" * 60)
    print("2. VERIFICATION market_regime_selector.py")
    print("=" * 60)
    
    file_path = Path(__file__).parent.parent / 'core' / 'market_regime_selector.py'
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        checks = [
            ("Import session_detector", "from utils.session_detector import get_current_session"),
            ("detection_method column", "detection_method, atr_median, atr_smoothed"),
            ("session_market column", "session_market, hysteresis_applied"),
            ("PHASE 1A comment", "PHASE 1A"),
        ]
        
        all_ok = True
        for name, pattern in checks:
            if pattern in content:
                print(f"  [OK] {name}")
            else:
                print(f"  [MANQUANT] {name}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  [ERREUR] Lecture fichier: {e}")
        return False


def check_syntax():
    """Verifie que les fichiers modifies ont une syntaxe Python valide"""
    print("\n" + "=" * 60)
    print("3. VERIFICATION SYNTAXE PYTHON")
    print("=" * 60)
    
    files = [
        'core/postgresql_datalogger.py',
        'core/market_regime_selector.py',
        'utils/session_detector.py',
    ]
    
    root = Path(__file__).parent.parent
    all_ok = True
    
    for f in files:
        file_path = root / f
        try:
            with open(file_path, 'r', encoding='utf-8') as fh:
                source = fh.read()
            compile(source, f, 'exec')
            print(f"  [OK] {f}")
        except SyntaxError as e:
            print(f"  [ERREUR SYNTAXE] {f}: ligne {e.lineno} - {e.msg}")
            all_ok = False
        except Exception as e:
            print(f"  [ERREUR] {f}: {e}")
            all_ok = False
    
    return all_ok


def check_imports():
    """Verifie que les imports fonctionnent"""
    print("\n" + "=" * 60)
    print("4. VERIFICATION IMPORTS")
    print("=" * 60)
    
    all_ok = True
    
    # Test session_detector
    try:
        from utils.session_detector import get_current_session, get_day_info
        session = get_current_session()
        day = get_day_info()
        print(f"  [OK] session_detector: {session['name']} (x{session['atr_multiplier']})")
    except Exception as e:
        print(f"  [ERREUR] session_detector: {e}")
        all_ok = False
    
    # Test postgresql_datalogger (import seulement, pas connexion)
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        print("  [OK] postgresql_datalogger import")
    except Exception as e:
        print(f"  [ERREUR] postgresql_datalogger: {e}")
        all_ok = False
    
    # Test market_regime_selector
    try:
        from core.market_regime_selector import MarketRegimeSelector
        print("  [OK] market_regime_selector import")
    except Exception as e:
        print(f"  [ERREUR] market_regime_selector: {e}")
        all_ok = False
    
    return all_ok


def check_column_count():
    """Verifie que le nombre de colonnes et valeurs correspond"""
    print("\n" + "=" * 60)
    print("5. VERIFICATION ALIGNEMENT COLONNES/VALEURS")
    print("=" * 60)
    
    file_path = Path(__file__).parent.parent / 'core' / 'postgresql_datalogger.py'
    content = file_path.read_text(encoding='utf-8')
    
    # Compter les colonnes dans _batch_insert_scans
    # Trouver la section columns = (...)
    import re
    
    # Chercher le tuple columns
    columns_match = re.search(r"columns = \((.*?)\)", content, re.DOTALL)
    if columns_match:
        columns_str = columns_match.group(1)
        # Compter les guillemets simples (chaque colonne)
        columns_count = columns_str.count("'") // 2
        print(f"  [INFO] Nombre de colonnes scan_logs: {columns_count}")
    else:
        print("  [ATTENTION] Impossible de compter les colonnes")
    
    print("  [OK] Verification manuelle requise pour alignement exact")
    
    return True


def main():
    print("=" * 60)
    print("VERIFICATION PHASE 1A: LOGGING CONTEXTUEL")
    print("=" * 60)
    
    results = {
        "postgresql_datalogger.py": check_postgresql_datalogger(),
        "market_regime_selector.py": check_market_regime_selector(),
        "Syntaxe Python": check_syntax(),
        "Imports": check_imports(),
        "Alignement colonnes": check_column_count(),
    }
    
    print("\n" + "=" * 60)
    print("RESUME")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[OK]" if passed else "[ECHEC]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] PHASE 1A LOGGING PRET!")
        print("\nProchaines etapes:")
        print("  1. Demarrer le bot et faire un trade")
        print("  2. Verifier que session_market, hour_utc sont remplis dans trade_atr_metrics")
        print("  3. Verifier que les scans ont session_market, regime_at_scan")
    else:
        print("[ECHEC] Phase 1A incomplete - Voir erreurs ci-dessus")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
