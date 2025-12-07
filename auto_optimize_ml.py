# -*- coding: utf-8 -*-
"""
Auto-Optimizer ML - Boucle automatique d'optimisation et entrainement
jusqu'a obtention de resultats satisfaisants

Objectifs:
- Test Accuracy >= 62%
- F1 Score >= 0.50
- Precision >= 0.55
- Overfitting Gap <= 12%
"""

import sys
import os
import time
import json
import requests

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Configuration
API_BASE = "http://localhost:5000"
MAX_ITERATIONS = 10
N_TRIALS = 100
TIMEOUT_MINUTES = 30

# Objectifs pour "super resultats"
TARGET_ACCURACY = 0.62
TARGET_F1 = 0.50
TARGET_PRECISION = 0.55
TARGET_MAX_GAP = 0.12  # 12%

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def get_current_metrics():
    """Recupere les metriques actuelles du modele"""
    try:
        resp = requests.get(f"{API_BASE}/api/ml/models/overview", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Trouver le modele best_classifier dans la liste
            models = data.get('models', [])
            gb_model = None
            for m in models:
                if m.get('name') == 'best_classifier':
                    gb_model = m
                    break
            
            if gb_model:
                metrics = gb_model.get('metrics', {})
                test_metrics = metrics.get('test', {})
                return {
                    'accuracy': test_metrics.get('accuracy', 0),
                    'f1': test_metrics.get('f1_score', 0),
                    'precision': test_metrics.get('precision', 0),
                    'gap': gb_model.get('overfitting_gap', 100) / 100.0,  # Convertir en decimal
                    'dataset_size': gb_model.get('dataset_info', {}).get('total_samples', 0)
                }
    except Exception as e:
        log(f"Erreur recuperation metriques: {e}")
    return None

def check_targets(metrics):
    """Verifie si les objectifs sont atteints"""
    if not metrics:
        return False, []
    
    issues = []
    passed = True
    
    if metrics['accuracy'] < TARGET_ACCURACY:
        issues.append(f"Accuracy {metrics['accuracy']*100:.1f}% < {TARGET_ACCURACY*100:.0f}%")
        passed = False
    if metrics['f1'] < TARGET_F1:
        issues.append(f"F1 {metrics['f1']:.3f} < {TARGET_F1:.2f}")
        passed = False
    if metrics['precision'] < TARGET_PRECISION:
        issues.append(f"Precision {metrics['precision']:.3f} < {TARGET_PRECISION:.2f}")
        passed = False
    if metrics['gap'] > TARGET_MAX_GAP:
        issues.append(f"Gap {metrics['gap']*100:.1f}% > {TARGET_MAX_GAP*100:.0f}%")
        passed = False
    
    return passed, issues

def run_optimization():
    """Lance l'optimisation Optuna"""
    
    # Verifier si une optimisation est deja en cours
    try:
        status_resp = requests.get(f"{API_BASE}/api/ml/optimize_gb/status", timeout=10)
        if status_resp.status_code == 200:
            status = status_resp.json()
            if status.get('status') == 'running':
                log("Optimisation deja en cours, attente...")
                # Attendre qu'elle finisse
                while True:
                    time.sleep(5)
                    status_resp = requests.get(f"{API_BASE}/api/ml/optimize_gb/status", timeout=10)
                    if status_resp.status_code == 200:
                        status = status_resp.json()
                        if status.get('status') != 'running':
                            log("Optimisation precedente terminee")
                            return True
                        current = status.get('current_trial', 0)
                        total = status.get('total_trials', N_TRIALS)
                        best = status.get('best_score', 0)
                        log(f"  Trial {current}/{total} | Best score: {best:.4f}")
    except:
        pass
    
    log("Lancement optimisation Optuna...")
    try:
        resp = requests.post(
            f"{API_BASE}/api/ml/optimize_gb",
            params={'n_trials': N_TRIALS, 'timeout_minutes': TIMEOUT_MINUTES},
            timeout=10
        )
        if resp.status_code == 409:
            log("Optimisation deja en cours (409), attente...")
            # Attendre
            time.sleep(10)
            return run_optimization()  # Recursif
        elif resp.status_code != 200:
            log(f"Erreur lancement optimisation: {resp.status_code}")
            return False
        
        # Attendre la fin de l'optimisation
        log(f"Optimisation en cours ({N_TRIALS} trials, max {TIMEOUT_MINUTES} min)...")
        while True:
            time.sleep(5)
            status_resp = requests.get(f"{API_BASE}/api/ml/optimize_gb/status", timeout=10)
            if status_resp.status_code == 200:
                status = status_resp.json()
                if status.get('status') == 'running':
                    current = status.get('current_trial', 0)
                    total = status.get('total_trials', N_TRIALS)
                    best = status.get('best_score', 0)
                    log(f"  Trial {current}/{total} | Best score: {best:.4f}")
                else:
                    log("Optimisation terminee!")
                    return True
            else:
                break
        return True
    except Exception as e:
        log(f"Erreur optimisation: {e}")
        return False

def apply_best_params():
    """Applique les meilleurs parametres"""
    log("Application des meilleurs parametres...")
    
    # D'abord recuperer les meilleurs params du status
    try:
        status_resp = requests.get(f"{API_BASE}/api/ml/optimize_gb/status", timeout=10)
        if status_resp.status_code == 200:
            status = status_resp.json()
            best_params = status.get('best_params')
            best_score = status.get('best_score', 0)
            log(f"  Best score Optuna: {best_score:.4f}")
            
            if best_params:
                log(f"  Params: {best_params}")
    except:
        pass
    
    try:
        resp = requests.post(f"{API_BASE}/api/ml/optimize_gb/apply", timeout=10)
        if resp.status_code == 200:
            log("Parametres appliques!")
            return True
        elif resp.status_code == 400:
            log("Aucun parametre optimal disponible, utilisation config actuelle")
            return True  # Continuer quand meme avec les params actuels
        else:
            log(f"Erreur application: {resp.status_code}")
            return False
    except Exception as e:
        log(f"Erreur: {e}")
        return False

def run_training():
    """Lance l'entrainement du modele"""
    log("Lancement entrainement...")
    try:
        resp = requests.post(f"{API_BASE}/api/ml/train_gb", timeout=10)
        if resp.status_code != 200:
            log(f"Erreur lancement entrainement: {resp.status_code}")
            return False
        
        data = resp.json()
        task_id = data.get('task_id')
        
        # Attendre la fin de l'entrainement
        log("Entrainement en cours...")
        while True:
            time.sleep(2)
            status_resp = requests.get(f"{API_BASE}/api/ml/task/{task_id}", timeout=10)
            if status_resp.status_code == 200:
                status = status_resp.json()
                progress = status.get('progress', 0)
                stage = status.get('stage', 'unknown')
                
                if progress >= 100 or stage == 'complete' or status.get('status') == 'complete':
                    log("Entrainement termine!")
                    return True
                elif status.get('status') == 'error':
                    log(f"Erreur entrainement: {status.get('error', 'unknown')}")
                    return False
                else:
                    log(f"  Progress: {progress}% | Stage: {stage}")
            else:
                break
        return True
    except Exception as e:
        log(f"Erreur entrainement: {e}")
        return False

def display_metrics(metrics, iteration):
    """Affiche les metriques"""
    print()
    print("=" * 50)
    print(f"  ITERATION {iteration} - RESULTATS")
    print("=" * 50)
    print(f"  Test Accuracy: {metrics['accuracy']*100:.1f}%  (objectif: >= {TARGET_ACCURACY*100:.0f}%)")
    print(f"  F1 Score:      {metrics['f1']:.3f}    (objectif: >= {TARGET_F1:.2f})")
    print(f"  Precision:     {metrics['precision']:.3f}    (objectif: >= {TARGET_PRECISION:.2f})")
    print(f"  Overfit Gap:   {metrics['gap']*100:.1f}%  (objectif: <= {TARGET_MAX_GAP*100:.0f}%)")
    print(f"  Dataset:       {metrics['dataset_size']} samples")
    print("=" * 50)
    print()

def main():
    print()
    print("=" * 60)
    print("  AUTO-OPTIMIZER ML - Boucle d'optimisation automatique")
    print("=" * 60)
    print(f"  Objectifs:")
    print(f"    - Accuracy >= {TARGET_ACCURACY*100:.0f}%")
    print(f"    - F1 Score >= {TARGET_F1:.2f}")
    print(f"    - Precision >= {TARGET_PRECISION:.2f}")
    print(f"    - Overfitting Gap <= {TARGET_MAX_GAP*100:.0f}%")
    print(f"  Max iterations: {MAX_ITERATIONS}")
    print("=" * 60)
    print()
    
    # Verifier que le backend est accessible
    try:
        resp = requests.get(f"{API_BASE}/api/config/complete", timeout=5)
        if resp.status_code != 200:
            log("ERREUR: Backend non accessible!")
            return
    except:
        log("ERREUR: Backend non accessible sur http://localhost:5000")
        log("Veuillez demarrer le backend avant de lancer ce script.")
        return
    
    log("Backend accessible, demarrage de l'optimisation...")
    
    best_metrics = None
    best_iteration = 0
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        log(f"\n{'='*20} ITERATION {iteration}/{MAX_ITERATIONS} {'='*20}")
        
        # Etape 1: Optimisation
        if not run_optimization():
            log("Echec optimisation, passage a l'iteration suivante...")
            time.sleep(5)
            continue
        
        time.sleep(2)
        
        # Etape 2: Appliquer les meilleurs parametres
        if not apply_best_params():
            log("Echec application params...")
            time.sleep(5)
            continue
        
        time.sleep(2)
        
        # Etape 3: Entrainement
        if not run_training():
            log("Echec entrainement...")
            time.sleep(5)
            continue
        
        time.sleep(3)
        
        # Etape 4: Verifier les metriques
        metrics = get_current_metrics()
        if not metrics:
            log("Impossible de recuperer les metriques")
            continue
        
        display_metrics(metrics, iteration)
        
        # Sauvegarder le meilleur
        if best_metrics is None or (
            metrics['accuracy'] >= best_metrics['accuracy'] and 
            metrics['gap'] <= best_metrics['gap']
        ):
            best_metrics = metrics
            best_iteration = iteration
            log(f"Nouvelle meilleure iteration: {iteration}")
        
        # Verifier si objectifs atteints
        passed, issues = check_targets(metrics)
        
        if passed:
            print()
            print("*" * 60)
            print("  SUCCES! Objectifs atteints!")
            print("*" * 60)
            display_metrics(metrics, iteration)
            return
        else:
            log(f"Objectifs non atteints:")
            for issue in issues:
                log(f"  - {issue}")
        
        # Petite pause entre iterations
        if iteration < MAX_ITERATIONS:
            log(f"Pause de 5 secondes avant iteration {iteration + 1}...")
            time.sleep(5)
    
    # Fin des iterations
    print()
    print("=" * 60)
    print(f"  FIN - {MAX_ITERATIONS} iterations effectuees")
    print("=" * 60)
    
    if best_metrics:
        print(f"\n  Meilleurs resultats (iteration {best_iteration}):")
        display_metrics(best_metrics, best_iteration)
        
        passed, issues = check_targets(best_metrics)
        if not passed:
            print("  Objectifs non atteints apres toutes les iterations.")
            print("  Suggestions:")
            print("    1. Augmenter le nombre de samples (plus de trades)")
            print("    2. Ameliorer la qualite des features")
            print("    3. Reduire le nombre de features (selection)")
            print("    4. Augmenter le seuil gb_min_confidence")

if __name__ == "__main__":
    main()
