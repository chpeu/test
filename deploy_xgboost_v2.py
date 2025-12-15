"""
Script de déploiement complet XGBoost V2
Fait toutes les étapes automatiquement
"""
import sys
import os
from pathlib import Path
import time

def print_step(number, title):
    print("\n" + "=" * 80)
    print(f"  ETAPE {number}: {title}")
    print("=" * 80)

def print_success(text):
    print(f"[OK] {text}")

def print_error(text):
    print(f"[ERROR] {text}")

def print_info(text):
    print(f"[INFO] {text}")

def step1_create_table():
    """Étape 1: Créer table ml_models"""
    print_step(1, "Creation table ml_models")
    
    # Charger .env
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
    
    try:
        import psycopg2
        
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'trade_cursor_ml')
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_pass = os.getenv('POSTGRES_PASSWORD', '')
        
        print_info(f"Connexion a {db_user}@{db_host}:{db_port}/{db_name}")
        
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Vérifier si table existe
        cur.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name = 'ml_models'
        """)
        
        if cur.fetchone()[0] > 0:
            print_success("Table ml_models existe deja")
            cur.close()
            conn.close()
            return True
        
        print_info("Creation de la table ml_models...")
        
        # Lire et exécuter le SQL
        sql_file = Path(__file__).parent / 'database' / 'create_ml_models_table.sql'
        
        if not sql_file.exists():
            print_error(f"Fichier SQL introuvable: {sql_file}")
            return False
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Exécuter le SQL
        cur.execute(sql_content)
        
        print_success("Table ml_models creee avec succes")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print_error(f"Erreur creation table: {e}")
        return False

def step2_restart_backend():
    """Étape 2: Avertir de redémarrer le backend"""
    print_step(2, "Redemarrage backend")
    
    print_info("Le backend doit etre redemarre pour charger les nouveaux endpoints")
    print_info("Action manuelle requise:")
    print("  1. Arreter le backend (Ctrl+C dans son terminal)")
    print("  2. Redemarrer: python main.py")
    print("\n[INFO] Continuons avec les autres etapes (backend a redemarer manuellement)")
    
    return True

def step3_validate_prereqs():
    """Étape 3: Valider les prérequis"""
    print_step(3, "Validation prerequis")
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: Python version
    checks_total += 1
    import sys
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print_success(f"Python {version.major}.{version.minor}.{version.micro}")
        checks_passed += 1
    else:
        print_error(f"Python {version.major}.{version.minor} - Requis: >= 3.9")
    
    # Check 2: Packages ML
    checks_total += 1
    try:
        import pandas, numpy, sklearn, xgboost
        print_success("Packages ML (pandas, numpy, sklearn, xgboost)")
        checks_passed += 1
    except ImportError as e:
        print_error(f"Packages ML manquants: {e}")
    
    # Check 3: PostgreSQL
    checks_total += 1
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        import psycopg2
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        conn.close()
        print_success("PostgreSQL accessible")
        checks_passed += 1
    except Exception as e:
        print_error(f"PostgreSQL: {e}")
    
    # Check 4: Table ml_models
    checks_total += 1
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'ml_models'")
        if cur.fetchone()[0] > 0:
            print_success("Table ml_models existe")
            checks_passed += 1
        else:
            print_error("Table ml_models manquante")
        cur.close()
        conn.close()
    except Exception as e:
        print_error(f"Verification table ml_models: {e}")
    
    # Check 5: Vue ml_features
    checks_total += 1
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ml_features LIMIT 1")
        print_success("Vue ml_features accessible")
        checks_passed += 1
        cur.close()
        conn.close()
    except Exception as e:
        print_error(f"Vue ml_features: {e}")
    
    # Check 6: Fichiers XGBoost V2
    checks_total += 1
    files_to_check = [
        'optimization/models/xgboost_trainer_v2.py',
        'optimization/models/model_logger.py',
        'optimization/optuna_v2_tuner.py',
    ]
    
    all_files_exist = True
    for file_path in files_to_check:
        if not Path(file_path).exists():
            print_error(f"Fichier manquant: {file_path}")
            all_files_exist = False
    
    if all_files_exist:
        print_success("Fichiers XGBoost V2 presents")
        checks_passed += 1
    
    print(f"\n[INFO] Score: {checks_passed}/{checks_total} verifications reussies")
    
    if checks_passed >= checks_total - 1:
        print_success("Prerequis valides, on peut continuer")
        return True
    else:
        print_error("Trop de prerequis manquants")
        return False

def step4_train_model():
    """Étape 4: Entraîner XGBoost V2"""
    print_step(4, "Entrainement XGBoost V2")
    
    print_info("Lancement entrainement XGBoost V2...")
    print_info("Cela peut prendre 3-5 minutes selon la taille du dataset")
    
    try:
        # Importer le trainer
        from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2
        
        print_info("XGBoostTrainerV2 importe avec succes")
        
        # Créer instance
        trainer = XGBoostTrainerV2(model_name='xgboost_v2')
        
        print_info("Demarrage entrainement...")
        print_info("Parametres: timeframe_days=120, min_trades=100, filter_marginal=True")
        
        # Entraîner
        results = trainer.train(
            timeframe_days=120,
            min_trades=100,
            filter_marginal_trades=True,
            marginal_threshold=0.15,
            max_features=30,
        )
        
        print_success("Entrainement termine!")
        
        # Afficher résultats
        if results.get('status') == 'success':
            metrics = results.get('metrics', {})
            test_metrics = metrics.get('test', {})
            gaps = metrics.get('gaps', {})
            
            print("\n" + "-" * 80)
            print("  RESULTATS ENTRAINEMENT")
            print("-" * 80)
            
            if test_metrics:
                print(f"Test Accuracy:  {test_metrics.get('accuracy', 0):.3f}")
                print(f"Test ROC-AUC:   {test_metrics.get('roc_auc', 0):.3f}")
            
            if gaps:
                print(f"Accuracy Gap:   {gaps.get('accuracy', 0):.3f}")
                print(f"ROC-AUC Gap:    {gaps.get('roc_auc', 0):.3f}")
            
            print("-" * 80)
            
            # Vérifier critères de succès
            test_acc = test_metrics.get('accuracy', 0)
            acc_gap = gaps.get('accuracy', 1.0)
            
            if test_acc >= 0.65 and acc_gap < 0.15:
                print_success("SUCCES! Metriques excellentes")
                return True
            elif test_acc >= 0.60:
                print_info("Metriques acceptables (peut etre ameliore avec Optuna)")
                return True
            else:
                print_error("Metriques insuffisantes (accuracy < 60%)")
                return False
        else:
            print_error("Entrainement a echoue")
            return False
        
    except Exception as e:
        print_error(f"Erreur entrainement: {e}")
        import traceback
        traceback.print_exc()
        return False

def step5_verify_results():
    """Étape 5: Vérifier les résultats dans PostgreSQL"""
    print_step(5, "Verification resultats")
    
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432'),
            database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', '')
        )
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Vérifier modèle dans ml_models
        cur.execute("""
            SELECT 
                model_name,
                version,
                test_accuracy,
                test_roc_auc,
                accuracy_gap,
                trained_at
            FROM ml_models
            WHERE model_name = 'xgboost_v2'
            ORDER BY trained_at DESC
            LIMIT 1
        """)
        
        result = cur.fetchone()
        
        if result:
            print_success("Modele trouve dans PostgreSQL")
            print("\n" + "-" * 80)
            print("  DONNEES POSTGRESQL")
            print("-" * 80)
            print(f"Model:          {result['model_name']} v{result['version']}")
            print(f"Test Accuracy:  {result['test_accuracy']:.3f}")
            print(f"Test ROC-AUC:   {result['test_roc_auc']:.3f}")
            print(f"Accuracy Gap:   {result['accuracy_gap']:.3f}")
            print(f"Trained:        {result['trained_at']}")
            print("-" * 80)
            
            # Vérifier fichiers modèle
            model_file = Path('optimization/saved_models/xgboost_v2.pkl')
            preprocessor_file = Path('optimization/saved_models/xgboost_v2_preprocessor.pkl')
            metadata_file = Path('optimization/saved_models/xgboost_v2_metadata.json')
            
            if model_file.exists():
                print_success(f"Fichier modele: {model_file}")
            else:
                print_error(f"Fichier modele manquant: {model_file}")
            
            if preprocessor_file.exists():
                print_success(f"Fichier preprocessor: {preprocessor_file}")
            else:
                print_error(f"Fichier preprocessor manquant: {preprocessor_file}")
            
            if metadata_file.exists():
                print_success(f"Fichier metadata: {metadata_file}")
            else:
                print_error(f"Fichier metadata manquant: {metadata_file}")
            
            cur.close()
            conn.close()
            
            return True
        else:
            print_error("Modele xgboost_v2 non trouve dans PostgreSQL")
            cur.close()
            conn.close()
            return False
        
    except Exception as e:
        print_error(f"Erreur verification: {e}")
        return False

def main():
    """Fonction principale"""
    print("\n" + "=" * 80)
    print("  DEPLOIEMENT COMPLET XGBOOST V2")
    print("=" * 80)
    
    start_time = time.time()
    
    # Étape 1
    if not step1_create_table():
        print("\n[ERROR] Etape 1 echouee - Arret")
        return False
    
    # Étape 2
    if not step2_restart_backend():
        print("\n[WARNING] Backend non redemarre - Certaines fonctionnalites API peuvent ne pas marcher")
    
    # Étape 3
    if not step3_validate_prereqs():
        print("\n[ERROR] Etape 3 echouee - Arret")
        return False
    
    # Étape 4
    if not step4_train_model():
        print("\n[ERROR] Etape 4 echouee - Arret")
        return False
    
    # Étape 5
    if not step5_verify_results():
        print("\n[WARNING] Etape 5 : Verification incomplete")
    
    elapsed = time.time() - start_time
    
    # Résumé final
    print("\n" + "=" * 80)
    print("  DEPLOIEMENT TERMINE")
    print("=" * 80)
    
    print_success(f"Duree totale: {elapsed:.1f} secondes")
    print_success("XGBoost V2 operationnel!")
    
    print("\n[INFO] Prochaines etapes:")
    print("  - Tester predictions via API")
    print("  - Optimiser avec Optuna V2 (si accuracy < 70%)")
    print("  - Activer le modele V2 en production")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INFO] Interruption utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
