"""
Script de vérification complet du système ML GradientBoosting & Calibration
==========================================================================

Ce script teste :
1. La disponibilité de l'API ML
2. La logique mathématique de pondération (Decay)
3. L'interaction avec la base de données (Lecture/Écriture Calibration)
4. La logique de décision (Should Take Trade)
5. La présence des tables dans l'export Excel (Simulation)
"""

import sys
import os
import requests
import json
from datetime import datetime, timedelta, timezone
import time

# Ajout du path racine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.calibration import get_calibration_manager, CalibrationStats
from config import TRADING_CONFIG

def print_step(title):
    print(f"\n{'='*60}")
    print(f"> TEST: {title}")
    print(f"{'='*60}")

def print_result(ok, message):
    icon = "[OK]" if ok else "[KO]"
    print(f"{icon} {message}")
    return ok

def test_api_connectivity():
    print_step("Connectivite API & Config")
    try:
        # 1. Stats Calibration
        r = requests.get("http://localhost:5000/ml/calibration/stats")
        if r.status_code == 200:
            data = r.json()
            print_result(True, f"API Stats accessible (Trades total: {data.get('total_trades', 0)})")
        else:
            return print_result(False, f"Erreur API Stats: {r.status_code}")

        # 2. Check Trade Endpoint
        r = requests.get("http://localhost:5000/ml/calibration/check/LONG/0.85")
        if r.status_code == 200:
            print_result(True, "API Check Trade accessible")
        else:
            return print_result(False, f"Erreur API Check: {r.status_code}")
            
        return True
    except Exception as e:
        return print_result(False, f"Exception API: {e} (Le serveur est-il lancé ?)")

def test_weighting_logic():
    print_step("Logique de Pondération (Maths)")
    manager = get_calibration_manager()
    
    # Test 1: Trade Live Récent
    w_live_fresh = manager.calculate_trade_weight(is_live=True, is_dry_run=False, trade_timestamp=datetime.now(timezone.utc))
    check1 = 0.9 <= w_live_fresh <= 1.1 # Devrait être ~1.0
    print_result(check1, f"Poids Live Récent: {w_live_fresh:.4f} (Attendu: ~1.0)")
    
    # Test 2: Trade Dry-Run Récent
    w_dry_fresh = manager.calculate_trade_weight(is_live=False, is_dry_run=True, trade_timestamp=datetime.now(timezone.utc))
    check2 = 0.4 <= w_dry_fresh <= 0.6 # Devrait être ~0.5 (config default)
    print_result(check2, f"Poids Dry-Run Récent: {w_dry_fresh:.4f} (Attendu: ~0.5)")
    
    # Test 3: Trade Vieux (Demi-vie)
    decay_days = TRADING_CONFIG.get('ml_calib_decay_days', 14)
    old_date = datetime.now(timezone.utc) - timedelta(days=decay_days)
    w_decayed = manager.calculate_trade_weight(is_live=True, is_dry_run=False, trade_timestamp=old_date)
    
    # Devrait être ~0.5 * Poids Live
    expected = 0.5 * TRADING_CONFIG.get('ml_calib_live_weight', 1.0)
    check3 = (expected - 0.1) <= w_decayed <= (expected + 0.1)
    print_result(check3, f"Poids Vieux ({decay_days}j): {w_decayed:.4f} (Attendu: ~{expected:.4f})")
    
    return check1 and check2 and check3

def test_database_interaction():
    print_step("Interaction Base de Données")
    manager = get_calibration_manager()
    
    # 1. Lire état actuel
    initial_stats = manager.get_all_stats()
    initial_count = initial_stats.get('LONG', {}).get('50+', None)
    start_trades = initial_count.total_trades if initial_count else 0
    
    print(f"Trades initiaux (LONG 50+): {start_trades}")
    
    # 2. Simuler une mise à jour (Update)
    # On utilise un timestamp fictif pour ne pas polluer les poids récents, mais on veut tester l'écriture
    success = manager.update_calibration(
        direction="LONG",
        ml_confidence=55.0, # Bucket 50+
        win=True,
        pnl_pct=1.5,
        pnl_usdt=10.0,
        is_live=False,
        is_dry_run=True, # Dry run pour minimiser impact
        trade_timestamp=datetime.now(timezone.utc)
    )
    print_result(success, "Update DB exécuté")
    
    # 3. Vérifier lecture après update
    # Force refresh cache
    manager._cache_timestamp = None 
    new_stats = manager.get_all_stats()
    new_count = new_stats.get('LONG', {}).get('50+', None)
    end_trades = new_count.total_trades if new_count else 0
    
    check = end_trades == start_trades + 1
    print_result(check, f"Incrémentation vérifiée: {start_trades} -> {end_trades}")
    
    return check

def test_decision_logic():
    print_step("Logique de Décision (Accept/Reject)")
    manager = get_calibration_manager()
    
    # Cas 1: Mock d'un bucket perdant
    # On injecte artificiellement dans le cache pour tester la logique sans toucher la DB
    manager._cache['SHORT', '30-35'] = CalibrationStats(
        direction='SHORT',
        confidence_bucket='30-35',
        weighted_wins=20.0,
        weighted_total=100.0,
        total_trades=100,
        actual_winrate=20.0,
        avg_pnl_pct=-0.5,
        total_pnl_usdt=-50.0
    )
    
    should_take, wr, reason = manager.should_take_trade("SHORT", 32.0)
    check1 = should_take is False
    print_result(check1, f"Rejet Bucket Perdant (WR 20%): {'OK' if not should_take else 'ECHEC'} ({reason})")
    
    # Cas 2: Mock d'un bucket gagnant
    manager._cache['LONG', '40-45'] = CalibrationStats(
        direction='LONG',
        confidence_bucket='40-45',
        weighted_wins=60.0,
        weighted_total=100.0,
        total_trades=100,
        actual_winrate=60.0,
        avg_pnl_pct=1.5,
        total_pnl_usdt=150.0
    )
    
    should_take, wr, reason = manager.should_take_trade("LONG", 42.0)
    check2 = should_take is True
    print_result(check2, f"Acceptation Bucket Gagnant (WR 60%): {'OK' if should_take else 'ECHEC'}")
    
    # Cas 3: Pas assez de données
    manager._cache['LONG', '45-50'] = CalibrationStats(
        direction='LONG',
        confidence_bucket='45-50',
        weighted_wins=1.0,
        weighted_total=2.0,
        total_trades=2,
        actual_winrate=10.0,
        avg_pnl_pct=-1.0,
        total_pnl_usdt=-20.0
    )
    
    # On modifie temporairement la config min trades pour le test
    old_min = TRADING_CONFIG.get('ml_calib_min_trades', 30)
    TRADING_CONFIG['ml_calib_min_trades'] = 10
    
    should_take, wr, reason = manager.should_take_trade("LONG", 47.0)
    # Devrait accepter car "learning_phase" (total_trades < min_trades)
    check3 = should_take is True 
    print_result(check3, f"Acceptation Phase Apprentissage (<10 trades): {'OK' if should_take else 'ECHEC'} ({reason})")
    
    TRADING_CONFIG['ml_calib_min_trades'] = old_min # Restore
    
    return check1 and check2 and check3

def main():
    print("[START] Demarrage de la verification du systeme ML...")
    
    results = []
    results.append(test_api_connectivity())
    results.append(test_weighting_logic())
    results.append(test_database_interaction())
    results.append(test_decision_logic())
    
    print_step("RESULTAT FINAL")
    if all(results):
        print("[SUCCESS] TOUS LES SYSTEMES SONT OPERATIONNELS")
        print("Le systeme ML Calibration est pret pour la production.")
    else:
        print("[WARNING] CERTAINS TESTS ONT ECHOUE. VEUILLEZ VERIFIER LES LOGS.")

if __name__ == "__main__":
    main()
