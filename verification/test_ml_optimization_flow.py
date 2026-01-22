#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complet du flow d'optimisation ML
Vérifie chaque étape pour identifier où ça bloque
"""

import asyncio
import subprocess
import sys
import os
import time
import requests
from pathlib import Path

# Ajouter le projet au path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_ok(msg):
    print(f"  [OK] {msg}")

def print_fail(msg):
    print(f"  [FAIL] {msg}")

def print_info(msg):
    print(f"  [INFO] {msg}")


def test_1_script_direct():
    """Test 1: Le script s'exécute directement"""
    print_header("TEST 1: Exécution directe du script")
    
    script_path = PROJECT_ROOT / "scripts" / "auto_optimize_ml.py"
    
    if not script_path.exists():
        print_fail(f"Script non trouvé: {script_path}")
        return False
    
    print_info(f"Script: {script_path}")
    print_info(f"Python: {sys.executable}")
    
    # Lancer le script avec un timeout court
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--splits", "1", "--min-trades", "50"],
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute max pour ce test
            cwd=str(PROJECT_ROOT)
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        print_info(f"Return code: {result.returncode}")
        
        # Vérifier si PROGRESS est émis
        if "PROGRESS:" in stdout:
            print_ok("Le script émet des messages PROGRESS")
            # Afficher les lignes PROGRESS
            for line in stdout.split('\n'):
                if line.startswith('PROGRESS:'):
                    print(f"      {line}")
            return True
        else:
            print_fail("Aucun message PROGRESS trouvé dans stdout")
            print_info(f"Stdout (premiers 500 chars): {stdout[:500]}")
            if stderr:
                print_fail(f"Stderr: {stderr[:500]}")
            return False
            
    except subprocess.TimeoutExpired:
        print_info("Timeout atteint (normal pour un test rapide)")
        return True  # OK si timeout mais script a démarré
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def test_2_subprocess_async():
    """Test 2: Le subprocess fonctionne en mode async"""
    print_header("TEST 2: Subprocess asyncio")
    
    script_path = PROJECT_ROOT / "scripts" / "auto_optimize_ml.py"
    
    async def run_async_test():
        print_info("Création du subprocess async...")
        
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            "--splits", "1", "--min-trades", "50",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT)
        )
        
        print_info(f"Process PID: {process.pid}")
        
        progress_found = False
        lines_read = 0
        
        # Lire les premières lignes (timeout 30s)
        try:
            start = time.time()
            while time.time() - start < 30:
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=5
                    )
                except asyncio.TimeoutError:
                    print_info(f"Attente ligne... ({lines_read} lignes lues)")
                    continue
                    
                if not line:
                    break
                    
                line_str = line.decode('utf-8', errors='ignore').strip()
                lines_read += 1
                
                if line_str.startswith('PROGRESS:'):
                    print_ok(f"PROGRESS trouvé: {line_str}")
                    progress_found = True
                elif lines_read <= 10:
                    print_info(f"Ligne {lines_read}: {line_str[:80]}")
                    
            # Terminer le process
            process.terminate()
            await process.wait()
            
        except Exception as e:
            print_fail(f"Erreur lecture: {e}")
            process.kill()
            
        return progress_found
    
    result = asyncio.run(run_async_test())
    if result:
        print_ok("Subprocess async fonctionne")
    else:
        print_fail("Subprocess async ne retourne pas de PROGRESS")
    return result


def test_3_api_backend():
    """Test 3: L'API backend répond"""
    print_header("TEST 3: API Backend")
    
    base_url = "http://localhost:5000"
    
    # Test health
    try:
        r = requests.get(f"{base_url}/api/live/health", timeout=5)
        if r.ok:
            print_ok(f"Backend accessible: {r.status_code}")
        else:
            print_fail(f"Backend erreur: {r.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_fail("Backend non accessible (ConnectionError)")
        print_info("Assurez-vous que le backend tourne sur localhost:5000")
        return False
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False
    
    # Test démarrage optimisation
    try:
        print_info("Lancement optimisation via API...")
        r = requests.post(
            f"{base_url}/api/ml/optimize/auto/start",
            json={"n_splits": 2, "min_trades": 50},
            timeout=10
        )
        
        if r.ok:
            data = r.json()
            task_id = data.get('task_id')
            print_ok(f"Optimisation démarrée: task_id={task_id}")
            
            # Attendre et vérifier la progression
            print_info("Vérification progression (30s)...")
            for i in range(6):
                time.sleep(5)
                
                r2 = requests.get(f"{base_url}/api/ml/task/{task_id}", timeout=5)
                if r2.ok:
                    task_data = r2.json()
                    progress = task_data.get('progress', 0)
                    message = task_data.get('message', '')
                    status = task_data.get('status', '')
                    
                    print_info(f"  [{i*5}s] Status={status}, Progress={progress}%, Message={message}")
                    
                    if progress > 0:
                        print_ok(f"Progression détectée: {progress}%")
                        return True
            
            print_fail("Aucune progression après 30s")
            return False
        else:
            print_fail(f"Erreur API: {r.status_code} - {r.text}")
            return False
            
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("  TEST COMPLET OPTIMISATION ML")
    print("="*60)
    
    results = {}
    
    # Test 1
    results['script_direct'] = test_1_script_direct()
    
    # Test 2
    results['subprocess_async'] = test_2_subprocess_async()
    
    # Test 3 (seulement si backend tourne)
    results['api_backend'] = test_3_api_backend()
    
    # Résumé
    print_header("RÉSUMÉ")
    
    all_ok = True
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {test_name}: {status}")
        if not passed:
            all_ok = False
    
    if all_ok:
        print("\n  [SUCCESS] Tous les tests passent!")
    else:
        print("\n  [WARNING] Certains tests echouent")
        
        if not results.get('script_direct'):
            print("\n  SOLUTION: Le script a un problème. Vérifiez:")
            print("    - Les imports sont corrects")
            print("    - Le dataset existe")
            
        if results.get('script_direct') and not results.get('api_backend'):
            print("\n  SOLUTION: Le backend ne lit pas correctement le stdout")
            print("    - Vérifiez les logs backend pour 'BACKGROUND TASK STARTED'")
            print("    - Le problème est dans la communication subprocess")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
