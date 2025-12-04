#!/usr/bin/env python3
"""
🔬 Script de vérification système HistGradientBoosting
======================================================
Vérifie la cohérence et la persistance du système ML:
1. Configuration (config.py ↔ config_overrides.json ↔ TRADING_CONFIG)
2. Modèle sauvegardé (params, features, métriques)
3. Capacité de prédiction
4. Sync frontend-backend

Usage:
    python verification/verify_histgb_system.py
    python verification/verify_histgb_system.py --fix  # Auto-repair
"""

import sys
import os
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le répertoire parent au path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import joblib

# ========== CONSTANTES ==========

HISTGB_REQUIRED_PARAMS = ['max_iter', 'max_depth', 'learning_rate', 'min_samples_leaf', 'l2_regularization']
HISTGB_DEFAULT_VALUES = {
    'gb_max_iter': 100,
    'gb_max_depth': 3,
    'gb_learning_rate': 0.08,
    'gb_min_samples_leaf': 30,
    'gb_l2_regularization': 0.5,
    'gb_n_features': 30,
    'gb_min_confidence': 0.5,
    'gb_model_type': 'histgb',
    'gb_filter_enabled': True
}

# Paramètres obsolètes (GradientBoosting classique)
OBSOLETE_PARAMS = ['gb_n_estimators', 'gb_min_samples_split', 'gb_subsample', 'gb_max_features']

CONFIG_FILE = PROJECT_ROOT / "config_overrides.json"
MODELS_DIR = PROJECT_ROOT / "optimization" / "saved_models"
MODEL_FILE = MODELS_DIR / "best_classifier_latest.pkl"
METADATA_FILE = MODELS_DIR / "best_classifier_metadata.json"


class VerificationResult:
    """Résultat d'une vérification"""
    def __init__(self, name: str):
        self.name = name
        self.passed = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.fixes_applied: List[str] = []
    
    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False
    
    def add_warning(self, msg: str):
        self.warnings.append(msg)
    
    def add_info(self, msg: str):
        self.info.append(msg)
    
    def add_fix(self, msg: str):
        self.fixes_applied.append(msg)
    
    def print_result(self):
        icon = "✅" if self.passed else "❌"
        print(f"\n{icon} {self.name}")
        print("-" * 50)
        
        for msg in self.info:
            print(f"   ℹ️  {msg}")
        
        for msg in self.warnings:
            print(f"   ⚠️  {msg}")
        
        for msg in self.errors:
            print(f"   ❌ {msg}")
        
        for msg in self.fixes_applied:
            print(f"   🔧 {msg}")


def verify_config_overrides(auto_fix: bool = False) -> VerificationResult:
    """Vérifie config_overrides.json"""
    result = VerificationResult("Configuration config_overrides.json")
    
    if not CONFIG_FILE.exists():
        result.add_error(f"Fichier non trouvé: {CONFIG_FILE}")
        return result
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        result.add_error(f"Erreur lecture JSON: {e}")
        return result
    
    needs_save = False
    
    # Vérifier présence des paramètres requis
    for param, default_value in HISTGB_DEFAULT_VALUES.items():
        if param not in config:
            result.add_warning(f"Paramètre manquant: {param}")
            if auto_fix:
                config[param] = default_value
                result.add_fix(f"Ajouté {param} = {default_value}")
                needs_save = True
        else:
            result.add_info(f"{param} = {config[param]}")
    
    # Vérifier absence des paramètres obsolètes
    for param in OBSOLETE_PARAMS:
        if param in config:
            result.add_warning(f"Paramètre obsolète trouvé: {param}")
            if auto_fix:
                del config[param]
                result.add_fix(f"Supprimé paramètre obsolète: {param}")
                needs_save = True
    
    # Vérifier que gb_model_type = 'histgb'
    if config.get('gb_model_type') != 'histgb':
        result.add_warning(f"gb_model_type = '{config.get('gb_model_type')}' (devrait être 'histgb')")
        if auto_fix:
            config['gb_model_type'] = 'histgb'
            result.add_fix("Corrigé gb_model_type = 'histgb'")
            needs_save = True
    
    # Sauvegarder si modifications
    if needs_save:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        result.add_info("Configuration sauvegardée")
    
    return result


def verify_trading_config() -> VerificationResult:
    """Vérifie que TRADING_CONFIG est chargé avec les bons paramètres"""
    result = VerificationResult("TRADING_CONFIG (runtime)")
    
    try:
        from config import TRADING_CONFIG
        from utils.config_persistence import apply_config_overrides
        
        # Appliquer les overrides
        apply_config_overrides(TRADING_CONFIG)
        
        # Vérifier les paramètres
        for param in HISTGB_DEFAULT_VALUES.keys():
            value = TRADING_CONFIG.get(param)
            if value is not None:
                result.add_info(f"{param} = {value}")
            else:
                result.add_warning(f"{param} non trouvé dans TRADING_CONFIG")
        
        # Vérifier cohérence avec config_overrides.json
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
            
            mismatches = []
            for param in HISTGB_DEFAULT_VALUES.keys():
                file_value = file_config.get(param)
                runtime_value = TRADING_CONFIG.get(param)
                if file_value != runtime_value:
                    mismatches.append(f"{param}: file={file_value}, runtime={runtime_value}")
            
            if mismatches:
                for m in mismatches:
                    result.add_warning(f"Mismatch: {m}")
            else:
                result.add_info("Config file et runtime synchronisés")
        
    except Exception as e:
        result.add_error(f"Erreur chargement TRADING_CONFIG: {e}")
    
    return result


def verify_model_file() -> VerificationResult:
    """Vérifie le fichier modèle sauvegardé"""
    result = VerificationResult("Modèle sauvegardé")
    
    if not MODEL_FILE.exists():
        result.add_error(f"Modèle non trouvé: {MODEL_FILE}")
        return result
    
    try:
        model_data = joblib.load(MODEL_FILE)
        
        # Vérifier structure
        required_keys = ['model', 'feature_names', 'params', 'n_features']
        for key in required_keys:
            if key not in model_data:
                result.add_error(f"Clé manquante dans modèle: {key}")
            else:
                if key == 'n_features':
                    result.add_info(f"Features: {model_data[key]}")
                elif key == 'params':
                    result.add_info(f"Params: {model_data[key]}")
        
        # Vérifier type du modèle
        model = model_data.get('model')
        if model:
            model_class = type(model).__name__
            if 'HistGradientBoosting' in model_class:
                result.add_info(f"Type modèle: {model_class} ✓")
            else:
                result.add_warning(f"Type modèle inattendu: {model_class}")
        
        # Vérifier les paramètres du modèle
        params = model_data.get('params', {})
        for required_param in HISTGB_REQUIRED_PARAMS:
            if required_param not in params:
                result.add_warning(f"Param manquant dans modèle: {required_param}")
        
    except Exception as e:
        result.add_error(f"Erreur lecture modèle: {e}")
    
    return result


def verify_metadata_file() -> VerificationResult:
    """Vérifie le fichier metadata JSON"""
    result = VerificationResult("Metadata modèle")
    
    if not METADATA_FILE.exists():
        result.add_error(f"Metadata non trouvé: {METADATA_FILE}")
        return result
    
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Vérifier type modèle
        model_type = metadata.get('model_type', '')
        if 'HistGradientBoosting' in model_type:
            result.add_info(f"Type: {model_type}")
        else:
            result.add_warning(f"Type inattendu: {model_type}")
        
        # Vérifier métriques
        metrics = metadata.get('metrics', {})
        if metrics:
            result.add_info(f"Accuracy: {metrics.get('test_accuracy', 0)*100:.1f}%")
            result.add_info(f"F1: {metrics.get('f1_score', 0):.3f}")
            result.add_info(f"Overfitting: {metrics.get('overfitting', 0)*100:.1f}%")
        
        # Vérifier timestamp
        timestamp = metadata.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                age = datetime.now() - dt
                result.add_info(f"Dernière optimisation: {dt.strftime('%Y-%m-%d %H:%M')} ({age.days}j {age.seconds//3600}h)")
            except:
                pass
        
        # Vérifier features
        features = metadata.get('feature_names', [])
        result.add_info(f"Features sauvées: {len(features)}")
        
    except Exception as e:
        result.add_error(f"Erreur lecture metadata: {e}")
    
    return result


def verify_prediction_capability() -> VerificationResult:
    """Vérifie que le modèle peut faire des prédictions"""
    result = VerificationResult("Capacité de prédiction")
    
    if not MODEL_FILE.exists():
        result.add_error("Modèle non trouvé, impossible de tester")
        return result
    
    try:
        model_data = joblib.load(MODEL_FILE)
        model = model_data.get('model')
        feature_names = model_data.get('feature_names', [])
        n_features = len(feature_names)
        
        if model is None:
            result.add_error("Modèle vide dans le fichier")
            return result
        
        # Créer des données de test fictives
        X_test = np.random.randn(10, n_features)
        
        # Tester predict
        try:
            predictions = model.predict(X_test)
            result.add_info(f"predict() OK - {len(predictions)} prédictions")
        except Exception as e:
            result.add_error(f"predict() échoué: {e}")
            return result
        
        # Tester predict_proba
        try:
            probas = model.predict_proba(X_test)
            result.add_info(f"predict_proba() OK - shape {probas.shape}")
        except Exception as e:
            result.add_warning(f"predict_proba() échoué: {e}")
        
        result.add_info("Modèle fonctionnel ✓")
        
    except Exception as e:
        result.add_error(f"Erreur test prédiction: {e}")
    
    return result


def verify_config_model_sync() -> VerificationResult:
    """Vérifie la synchronisation config ↔ modèle"""
    result = VerificationResult("Synchronisation Config ↔ Modèle")
    
    if not CONFIG_FILE.exists() or not METADATA_FILE.exists():
        result.add_warning("Fichiers manquants, sync non vérifiable")
        return result
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        
        model_params = metadata.get('params', {})
        
        # Mapping config -> model param names
        param_mapping = {
            'gb_max_iter': 'max_iter',
            'gb_max_depth': 'max_depth',
            'gb_learning_rate': 'learning_rate',
            'gb_min_samples_leaf': 'min_samples_leaf',
            'gb_l2_regularization': 'l2_regularization'
        }
        
        synced = True
        for config_key, model_key in param_mapping.items():
            config_value = config.get(config_key)
            model_value = model_params.get(model_key)
            
            if config_value != model_value:
                result.add_warning(f"{config_key}: config={config_value}, model={model_value}")
                synced = False
            else:
                result.add_info(f"{config_key} = {config_value} ✓")
        
        if synced:
            result.add_info("Config et modèle parfaitement synchronisés")
        else:
            result.add_warning("ATTENTION: Désynchronisation détectée!")
            result.add_info("Conseil: Relancer une optimisation ou appliquer les params du modèle")
        
    except Exception as e:
        result.add_error(f"Erreur vérification sync: {e}")
    
    return result


def run_all_verifications(auto_fix: bool = False) -> Dict[str, VerificationResult]:
    """Exécute toutes les vérifications"""
    print("=" * 60)
    print("🔬 VÉRIFICATION SYSTÈME HISTGRADIENTBOOSTING")
    print("=" * 60)
    print(f"📁 Projet: {PROJECT_ROOT}")
    print(f"🔧 Mode: {'Auto-repair' if auto_fix else 'Lecture seule'}")
    
    results = {}
    
    # 1. Config overrides
    results['config_overrides'] = verify_config_overrides(auto_fix)
    results['config_overrides'].print_result()
    
    # 2. TRADING_CONFIG runtime
    results['trading_config'] = verify_trading_config()
    results['trading_config'].print_result()
    
    # 3. Model file
    results['model_file'] = verify_model_file()
    results['model_file'].print_result()
    
    # 4. Metadata file
    results['metadata'] = verify_metadata_file()
    results['metadata'].print_result()
    
    # 5. Prediction capability
    results['prediction'] = verify_prediction_capability()
    results['prediction'].print_result()
    
    # 6. Config-Model sync
    results['sync'] = verify_config_model_sync()
    results['sync'].print_result()
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r.passed)
    total = len(results)
    
    print(f"\n   Tests réussis: {passed}/{total}")
    
    if passed == total:
        print("\n   ✅ SYSTÈME OK - Tous les tests passent")
        return results
    
    print("\n   ⚠️  PROBLÈMES DÉTECTÉS:")
    for name, r in results.items():
        if not r.passed:
            print(f"      - {r.name}")
    
    if not auto_fix:
        print("\n   💡 Conseil: Relancer avec --fix pour auto-réparer")
    
    return results


def sync_config_from_model(dry_run: bool = True) -> bool:
    """Synchronise config_overrides.json depuis les params du modèle"""
    print("\n🔄 Synchronisation config depuis modèle...")
    
    if not METADATA_FILE.exists():
        print("❌ Metadata non trouvé")
        return False
    
    try:
        with open(METADATA_FILE, 'r') as f:
            metadata = json.load(f)
        
        model_params = metadata.get('params', {})
        
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        else:
            config = {}
        
        # Mapping
        param_mapping = {
            'max_iter': 'gb_max_iter',
            'max_depth': 'gb_max_depth',
            'learning_rate': 'gb_learning_rate',
            'min_samples_leaf': 'gb_min_samples_leaf',
            'l2_regularization': 'gb_l2_regularization'
        }
        
        changes = []
        for model_key, config_key in param_mapping.items():
            if model_key in model_params:
                old_value = config.get(config_key)
                new_value = model_params[model_key]
                if old_value != new_value:
                    changes.append(f"{config_key}: {old_value} → {new_value}")
                    config[config_key] = new_value
        
        if not changes:
            print("✅ Déjà synchronisé, aucun changement nécessaire")
            return True
        
        print("Changements à appliquer:")
        for c in changes:
            print(f"   - {c}")
        
        if dry_run:
            print("\n[DRY RUN] Utilisez sync_config_from_model(dry_run=False) pour appliquer")
            return True
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Config mise à jour depuis le modèle")
        
        # Recharger TRADING_CONFIG
        try:
            from config import TRADING_CONFIG
            from utils.config_persistence import apply_config_overrides
            apply_config_overrides(TRADING_CONFIG)
            print("✅ TRADING_CONFIG rechargé")
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vérification système HistGradientBoosting")
    parser.add_argument('--fix', action='store_true', help="Auto-réparer les problèmes")
    parser.add_argument('--sync-from-model', action='store_true', help="Sync config depuis modèle")
    args = parser.parse_args()
    
    if args.sync_from_model:
        sync_config_from_model(dry_run=False)
    else:
        results = run_all_verifications(auto_fix=args.fix)
        
        # Exit code basé sur les résultats
        all_passed = all(r.passed for r in results.values())
        sys.exit(0 if all_passed else 1)
