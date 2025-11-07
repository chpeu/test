#!/usr/bin/env python3
"""
Tests d'intégration pour les routes API refactorisées
Valide l'architecture modulaire api/routes
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_import_routes():
    """Test 1: Import des routes"""
    print("Test 1: Import routes... ", end="")

    try:
        from api.routes import scanner_router, dashboard_router
        from api.routes.scanner import router as scanner
        from api.routes.dashboard import router as dashboard

        assert scanner_router is not None
        assert dashboard_router is not None
        assert scanner is not None
        assert dashboard is not None

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        return False


def test_import_callbacks():
    """Test 2: Import des callbacks"""
    print("Test 2: Import callbacks... ", end="")

    try:
        from core.callbacks import (
            scanner_loop_callback,
            position_check_loop_callback,
            scalability_refresh_loop_callback
        )

        assert scanner_loop_callback is not None
        assert position_check_loop_callback is not None
        assert scalability_refresh_loop_callback is not None

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scanner_routes_structure():
    """Test 3: Structure routes scanner"""
    print("Test 3: Structure routes scanner... ", end="")

    try:
        from api.routes.scanner import router, set_scanner, set_analyzer, set_price_provider

        # Vérifier que les fonctions d'injection existent
        assert callable(set_scanner)
        assert callable(set_analyzer)
        assert callable(set_price_provider)

        # Vérifier que le router existe et a des routes
        assert router is not None
        assert len(router.routes) > 0  # Au moins une route

        # Vérifier les méthodes HTTP
        methods = [route.methods for route in router.routes if hasattr(route, 'methods')]
        assert any('GET' in m for m in methods)
        assert any('POST' in m for m in methods)

        print(f"✓ OK ({len(router.routes)} routes)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dashboard_routes_structure():
    """Test 4: Structure routes dashboard"""
    print("Test 4: Structure routes dashboard... ", end="")

    try:
        from api.routes.dashboard import router, set_scheduler, set_position_manager

        # Vérifier que les fonctions d'injection existent
        assert callable(set_scheduler)
        assert callable(set_position_manager)

        # Vérifier que le router existe et a des routes
        assert router is not None
        assert len(router.routes) > 0

        # Vérifier les méthodes HTTP
        methods = [route.methods for route in router.routes if hasattr(route, 'methods')]
        assert any('GET' in m for m in methods)
        assert any('POST' in m for m in methods)

        print(f"✓ OK ({len(router.routes)} routes)")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_callbacks_structure():
    """Test 5: Structure callbacks"""
    print("Test 5: Structure callbacks... ", end="")

    try:
        from core.callbacks import scanner_loop, position_check_loop, scalability_refresh

        # Vérifier que les modules existent
        assert scanner_loop is not None
        assert position_check_loop is not None
        assert scalability_refresh is not None

        # Vérifier les fonctions set_*
        assert callable(scanner_loop.set_scanner)
        assert callable(scanner_loop.set_analyzer)
        assert callable(position_check_loop.set_position_manager)
        assert callable(scalability_refresh.set_scanner)

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_integration():
    """Test 6: Intégration dans main.py"""
    print("Test 6: Intégration main.py... ", end="")

    try:
        # Vérifier que main.py peut être importé
        import main

        # Vérifier que l'app FastAPI existe
        assert hasattr(main, 'app')
        assert main.app is not None

        # Vérifier que les routers sont inclus
        # Les routers sont inclus via app.include_router()
        routes_paths = [route.path for route in main.app.routes]

        # Vérifier quelques routes clés
        assert any('/api/status' in path for path in routes_paths)
        assert any('/api/state' in path for path in routes_paths)

        print("✓ OK")
        return True
    except Exception as e:
        print(f"✗ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("TESTS D'INTÉGRATION - ROUTES API REFACTORISÉES")
    print("="*60 + "\n")

    tests = [
        test_import_routes,
        test_import_callbacks,
        test_scanner_routes_structure,
        test_dashboard_routes_structure,
        test_callbacks_structure,
        test_main_integration,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"RÉSULTATS: {passed}/{total} tests réussis")

    if passed == total:
        print("✅ TOUS LES TESTS PASSENT - Routes API validées!")
    else:
        print(f"⚠️  {total - passed} test(s) échoué(s)")

    print("="*60 + "\n")

    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
