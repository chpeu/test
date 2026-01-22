"""
Script de validation complète XGBoost V2
Vérifie tous les prérequis et composants avant déploiement
"""
import sys
import os
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def check_python_version():
    """Vérifier version Python >= 3.9"""
    print_header("1. Vérification Python")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 9:
        print_success(f"Python {version_str} ✓")
        return True
    else:
        print_error(f"Python {version_str} - Requis: Python ≥ 3.9")
        return False

def check_packages():
    """Vérifier packages ML installés"""
    print_header("2. Vérification Packages ML")
    
    required = [
        'pandas', 'numpy', 'sklearn', 'xgboost', 
        'lightgbm', 'optuna', 'psycopg2', 'sqlalchemy'
    ]
    
    missing = []
    for package in required:
        try:
            if package == 'sklearn':
                __import__('sklearn')
            else:
                __import__(package)
            print_success(f"{package}")
        except ImportError:
            print_error(f"{package} - MANQUANT")
            missing.append(package)
    
    if missing:
        print_warning(f"Installer: pip install {' '.join(missing)}")
        return False
    
    return True

def check_files_structure():
    """Vérifier structure fichiers"""
    print_header("3. Vérification Structure Fichiers")
    
    required_files = [
        'optimization/models/xgboost_trainer_v2.py',
        'optimization/models/train_enhanced.py',
        'optimization/models/model_logger.py',
        'optimization/optuna_v2_tuner.py',
        'optimization/utils/temporal_split.py',
        'optimization/data/feature_loader.py',
        'database/create_ml_models_table.sql',
        'database/create_ml_view.sql',
        'api/routes/ml.py',
    ]
    
    missing = []
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            print_success(f"{file_path}")
        else:
            print_error(f"{file_path} - MANQUANT")
            missing.append(file_path)
    
    if missing:
        return False
    
    return True

def check_database():
    """Vérifier connexion PostgreSQL"""
    print_header("4. Vérification PostgreSQL")
    
    try:
        from core.postgresql_datalogger import get_pg_datalogger
        
        pg = get_pg_datalogger()
        if not pg or not pg.enabled:
            print_error("PostgreSQL datalogger non disponible")
            return False
        
        print_success("Connexion PostgreSQL établie")
        
        # Vérifier vue ml_features
        try:
            result = pg.execute_query("SELECT COUNT(*) as count FROM ml_features", fetch=True)
            if result:
                count = result[0]['count']
                print_success(f"Vue ml_features existe ({count} lignes)")
                
                if count < 100:
                    print_warning(f"Seulement {count} trades - Minimum recommandé: 100")
                    return False
            else:
                print_error("Impossible de compter les lignes dans ml_features")
                return False
        except Exception as e:
            print_error(f"Vue ml_features manquante: {e}")
            print_warning("Exécuter: psql -U postgres -d tradebot -f database/create_ml_view.sql")
            return False
        
        # Vérifier table ml_models
        try:
            result = pg.execute_query(
                "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_name = 'ml_models'",
                fetch=True
            )
            if result and result[0]['count'] > 0:
                print_success("Table ml_models existe")
            else:
                print_error("Table ml_models manquante")
                print_warning("Exécuter: psql -U postgres -d tradebot -f database/create_ml_models_table.sql")
                return False
        except Exception as e:
            print_error(f"Erreur vérification table ml_models: {e}")
            return False
        
        return True
        
    except Exception as e:
        print_error(f"Erreur connexion PostgreSQL: {e}")
        print_warning("Vérifier .env et que PostgreSQL est démarré")
        return False

def check_api_endpoint():
    """Vérifier endpoint /api/ml/train_v2 existe"""
    print_header("5. Vérification Endpoint API")
    
    try:
        with open('api/routes/ml.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        if '@router.post("/train_v2")' in content or '@router.post(\"/train_v2\")' in content:
            print_success("Endpoint /api/ml/train_v2 trouvé")
            return True
        else:
            print_error("Endpoint /api/ml/train_v2 manquant dans api/routes/ml.py")
            return False
    except FileNotFoundError:
        print_error("Fichier api/routes/ml.py introuvable")
        return False

def check_documentation():
    """Vérifier documentation présente"""
    print_header("6. Vérification Documentation")
    
    docs = [
        'XGBOOST_V2_README.md',
        'XGBOOST_V2_CHANGELOG.md',
        'XGBOOST_V2_INSTRUCTIONS.md',
        'QUICK_START_V2.md'
    ]
    
    found = 0
    for doc in docs:
        if Path(doc).exists():
            print_success(doc)
            found += 1
        else:
            print_warning(f"{doc} - MANQUANT (optionnel)")
    
    return found >= 2  # Au moins 2 docs présents

def run_validation():
    """Exécuter toutes les validations"""
    print("\n" + "🚀" * 40)
    print("VALIDATION XGBOOST V2 - Vérification Complète")
    print("🚀" * 40)
    
    checks = [
        ("Python Version", check_python_version),
        ("Packages ML", check_packages),
        ("Structure Fichiers", check_files_structure),
        ("PostgreSQL", check_database),
        ("API Endpoint", check_api_endpoint),
        ("Documentation", check_documentation),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Erreur lors de {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print_header("RÉSUMÉ")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:12} - {name}")
    
    print("\n" + "=" * 80)
    print(f"Score: {passed}/{total} vérifications réussies")
    
    if passed == total:
        print("\n🎉 SUCCÈS ! Tous les prérequis sont remplis.")
        print("✅ Vous pouvez procéder à l'entraînement XGBoost V2")
        print("\nProchaine étape:")
        print("  python optimization/models/train_enhanced.py")
        return 0
    else:
        print("\n⚠️  ATTENTION : Certains prérequis manquants")
        print("Corrigez les erreurs ci-dessus avant de continuer")
        return 1

if __name__ == "__main__":
    sys.exit(run_validation())
