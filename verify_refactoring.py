#!/usr/bin/env python3
"""
Script de vérification de la refactorisation
Vérifie que tous les modules et imports sont corrects
"""

import os
import sys
import importlib.util

def check_file_exists(filepath, description):
    """Vérifier qu'un fichier existe"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description} MANQUANT: {filepath}")
        return False

def check_module_import(module_path, description):
    """Vérifier qu'un module peut être importé"""
    try:
        spec = importlib.util.find_spec(module_path)
        if spec is not None:
            print(f"✅ {description}: {module_path}")
            return True
        else:
            print(f"❌ {description} NON TROUVÉ: {module_path}")
            return False
    except Exception as e:
        print(f"❌ {description} ERREUR: {module_path} - {e}")
        return False

def check_python_syntax(filepath, description):
    """Vérifier la syntaxe Python d'un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        print(f"✅ {description} syntaxe valide: {filepath}")
        return True
    except SyntaxError as e:
        print(f"❌ {description} ERREUR SYNTAXE: {filepath}")
        print(f"   Ligne {e.lineno}: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {description} ERREUR: {filepath} - {e}")
        return False

def count_routes(filepath):
    """Compter le nombre de routes @app dans un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        count = content.count('@app.get(') + content.count('@app.post(')
        return count
    except:
        return 0

def count_lines(filepath):
    """Compter le nombre de lignes dans un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return len(f.readlines())
    except:
        return 0

def main():
    print("=" * 70)
    print("🔍 VÉRIFICATION DE LA REFACTORISATION - Trade Cursor v7.0")
    print("=" * 70)
    print()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    all_checks_passed = True

    # 1. Vérifier fichiers principaux
    print("📁 1. FICHIERS PRINCIPAUX")
    print("-" * 70)
    all_checks_passed &= check_file_exists("main.py", "Fichier original")
    all_checks_passed &= check_file_exists("main_refactored.py", "Fichier refactorisé")
    all_checks_passed &= check_file_exists("REFACTORING_GUIDE.md", "Guide de refactorisation")
    print()

    # 2. Vérifier modules refactorisés
    print("📦 2. MODULES REFACTORISÉS")
    print("-" * 70)
    all_checks_passed &= check_file_exists("api/routes/scanner.py", "Module scanner routes")
    all_checks_passed &= check_file_exists("api/routes/dashboard.py", "Module dashboard routes")
    all_checks_passed &= check_file_exists("core/callbacks/scanner_loop.py", "Module scanner callback")
    all_checks_passed &= check_file_exists("core/callbacks/position_check_loop.py", "Module position check callback")
    all_checks_passed &= check_file_exists("core/callbacks/scalability_refresh.py", "Module scalability refresh callback")
    print()

    # 3. Vérifier __init__.py
    print("📦 3. FICHIERS __init__.py")
    print("-" * 70)
    all_checks_passed &= check_file_exists("api/__init__.py", "api/__init__.py")
    all_checks_passed &= check_file_exists("api/routes/__init__.py", "api/routes/__init__.py")
    all_checks_passed &= check_file_exists("core/__init__.py", "core/__init__.py")
    all_checks_passed &= check_file_exists("core/callbacks/__init__.py", "core/callbacks/__init__.py")
    print()

    # 4. Vérifier syntaxe Python
    print("🐍 4. SYNTAXE PYTHON")
    print("-" * 70)
    all_checks_passed &= check_python_syntax("main_refactored.py", "main_refactored.py")
    all_checks_passed &= check_python_syntax("api/routes/scanner.py", "scanner.py")
    all_checks_passed &= check_python_syntax("api/routes/dashboard.py", "dashboard.py")
    all_checks_passed &= check_python_syntax("core/callbacks/scanner_loop.py", "scanner_loop.py")
    all_checks_passed &= check_python_syntax("core/callbacks/position_check_loop.py", "position_check_loop.py")
    all_checks_passed &= check_python_syntax("core/callbacks/scalability_refresh.py", "scalability_refresh.py")
    print()

    # 5. Statistiques
    print("📊 5. STATISTIQUES")
    print("-" * 70)
    original_lines = count_lines("main.py")
    refactored_lines = count_lines("main_refactored.py")
    original_routes = count_routes("main.py")
    refactored_routes = count_routes("main_refactored.py")

    print(f"📏 Lignes de code:")
    print(f"   Original:     {original_lines} lignes")
    print(f"   Refactorisé:  {refactored_lines} lignes")
    if original_lines > 0:
        reduction = original_lines - refactored_lines
        percent = (reduction / original_lines) * 100
        print(f"   Réduction:    {reduction} lignes (-{percent:.1f}%)")

    print(f"\n🛣️  Routes @app:")
    print(f"   Original:     {original_routes} routes")
    print(f"   Refactorisé:  {refactored_routes} routes")
    if original_routes > 0:
        routes_removed = original_routes - refactored_routes
        print(f"   Supprimées:   {routes_removed} routes")

    # Modules créés
    scanner_lines = count_lines("api/routes/scanner.py")
    dashboard_lines = count_lines("api/routes/dashboard.py")
    scanner_cb_lines = count_lines("core/callbacks/scanner_loop.py")
    position_cb_lines = count_lines("core/callbacks/position_check_loop.py")
    scalability_cb_lines = count_lines("core/callbacks/scalability_refresh.py")

    total_module_lines = scanner_lines + dashboard_lines + scanner_cb_lines + position_cb_lines + scalability_cb_lines

    print(f"\n📦 Modules créés:")
    print(f"   scanner.py:                  {scanner_lines} lignes")
    print(f"   dashboard.py:                {dashboard_lines} lignes")
    print(f"   scanner_loop.py:             {scanner_cb_lines} lignes")
    print(f"   position_check_loop.py:      {position_cb_lines} lignes")
    print(f"   scalability_refresh.py:      {scalability_cb_lines} lignes")
    print(f"   TOTAL modules:               {total_module_lines} lignes")
    print()

    # 6. Résumé
    print("=" * 70)
    if all_checks_passed:
        print("✅ TOUTES LES VÉRIFICATIONS SONT PASSÉES !")
        print()
        print("🎯 PROCHAINES ÉTAPES:")
        print("   1. Tester le fichier refactorisé: python3 main_refactored.py 5000")
        print("   2. Vérifier que toutes les routes fonctionnent")
        print("   3. Vérifier que les callbacks s'exécutent")
        print("   4. Si tout fonctionne, remplacer main.py:")
        print("      mv main.py main_original_2133_lines.py")
        print("      mv main_refactored.py main.py")
        print()
        print("📖 Consultez REFACTORING_GUIDE.md pour plus de détails")
        return 0
    else:
        print("❌ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ")
        print()
        print("Corrigez les erreurs ci-dessus avant de continuer.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
