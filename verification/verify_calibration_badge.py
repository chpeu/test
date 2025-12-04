#!/usr/bin/env python3
"""
Verification du badge ml_calibrated_winrate dans le flux complet.
Verifie que le badge s'affiche quand la calibration a ete le decideur.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_calibration_decision():
    """Verifie que should_take_trade retourne bien calibrated_wr pour un bucket actif"""
    print("\n" + "="*60)
    print(" VERIFICATION BADGE ML_CALIBRATED_WINRATE")
    print("="*60)
    
    from ml.calibration import get_calibration_manager
    from config import TRADING_CONFIG
    
    manager = get_calibration_manager()
    
    # 1. Verifier la config
    print("\n>>> ETAPE 1: Configuration Calibration")
    config = manager._get_config()
    print(f"   Enabled: {config['enabled']}")
    print(f"   Min trades: {config['min_trades']}")
    print(f"   Min winrate: {config['min_winrate']}%")
    print(f"   Bucket size: {config['bucket_size']}")
    
    if not config['enabled']:
        print("\n[WARN] Calibration DESACTIVEE - Le badge ne s'affichera jamais!")
        return False
    
    # 2. Lister les buckets actifs (>= min_trades)
    print("\n>>> ETAPE 2: Buckets Actifs (>= min_trades)")
    all_stats = manager.get_all_stats()
    active_buckets = []
    
    for direction in ['LONG', 'SHORT']:
        for bucket, stats in all_stats.get(direction, {}).items():
            if stats.weighted_total >= config['min_trades']:
                active_buckets.append({
                    'direction': direction,
                    'bucket': bucket,
                    'total': stats.total_trades,
                    'weighted': stats.weighted_total,
                    'winrate': stats.actual_winrate
                })
                print(f"   [ACTIF] {direction} {bucket}: {stats.total_trades} trades, WR={stats.actual_winrate:.1f}%")
    
    if not active_buckets:
        print("\n[WARN] Aucun bucket actif! La calibration est en phase d'apprentissage pour tous les buckets.")
        print("       Le badge ne s'affichera pas tant qu'un bucket n'a pas >= min_trades.")
        return False
    
    # 3. Tester should_take_trade pour chaque bucket actif
    print("\n>>> ETAPE 3: Test should_take_trade() pour buckets actifs")
    all_ok = True
    
    for b in active_buckets:
        # Calculer une confiance au milieu du bucket
        if b['bucket'] == '50+':
            test_conf = 55.0
        else:
            parts = b['bucket'].split('-')
            test_conf = (float(parts[0]) + float(parts[1])) / 2
        
        should, wr, reason = manager.should_take_trade(b['direction'], test_conf)
        
        if wr is None:
            print(f"   [FAIL] {b['direction']} {test_conf}% -> calibrated_wr=None (Raison: {reason})")
            all_ok = False
        else:
            status = "OK" if should else "REJETE"
            print(f"   [{status}] {b['direction']} {test_conf}% -> calibrated_wr={wr:.1f}% (Raison: {reason})")
    
    # 4. Simuler Position.to_dict()
    print("\n>>> ETAPE 4: Simulation Position.to_dict()")
    from core.position_manager import Position
    
    # Creer une position de test avec calibrated_winrate
    test_position = Position(
        symbol="TEST/USDT:USDT",
        direction="SHORT",
        entry=1.0,
        size=10.0,
        sl=1.01,
        tp=0.99
    )
    test_position.ml_confidence = 38.5
    test_position.ml_calibrated_winrate = 45.2  # Valeur de test
    
    pos_dict = test_position.to_dict()
    
    if 'ml_calibrated_winrate' in pos_dict:
        print(f"   [OK] ml_calibrated_winrate present dans to_dict(): {pos_dict['ml_calibrated_winrate']}")
    else:
        print("   [FAIL] ml_calibrated_winrate ABSENT de to_dict()!")
        all_ok = False
    
    # 5. Verifier le bucket SHORT 35-40 specifiquement (cas de l'utilisateur)
    print("\n>>> ETAPE 5: Verification specifique SHORT 35-40 (cas utilisateur)")
    
    stats_short_35_40 = manager._get_stats('SHORT', '35-40')
    if stats_short_35_40:
        print(f"   Bucket SHORT 35-40 trouve:")
        print(f"   - Total trades: {stats_short_35_40.total_trades}")
        print(f"   - Weighted total: {stats_short_35_40.weighted_total:.2f}")
        print(f"   - Actual winrate: {stats_short_35_40.actual_winrate:.1f}%")
        
        if stats_short_35_40.weighted_total >= config['min_trades']:
            should, wr, reason = manager.should_take_trade('SHORT', 38.5)
            if wr is not None:
                print(f"   [OK] should_take_trade('SHORT', 38.5) -> calibrated_wr={wr:.1f}%")
            else:
                print(f"   [FAIL] should_take_trade('SHORT', 38.5) -> calibrated_wr=None (Raison: {reason})")
                all_ok = False
        else:
            print(f"   [WARN] Bucket pas encore actif: {stats_short_35_40.weighted_total:.2f} < {config['min_trades']}")
    else:
        print("   [WARN] Bucket SHORT 35-40 non trouve en cache")
        # Forcer refresh du cache
        manager._cache_timestamp = None
        manager._refresh_cache_if_needed()
        stats_short_35_40 = manager._get_stats('SHORT', '35-40')
        if stats_short_35_40:
            print(f"   [OK] Apres refresh: {stats_short_35_40.total_trades} trades, WR={stats_short_35_40.actual_winrate:.1f}%")
        else:
            print("   [FAIL] Bucket SHORT 35-40 toujours absent apres refresh!")
    
    # Resume
    print("\n" + "="*60)
    if all_ok:
        print(" [SUCCESS] Le badge devrait s'afficher correctement!")
        print(" Si vous ne le voyez pas:")
        print("   1. Verifiez que le backend a bien ete redemarre")
        print("   2. Rechargez la page frontend (F5)")
        print("   3. Ouvrez un NOUVEAU trade (les anciens n'ont pas la valeur)")
    else:
        print(" [ISSUES] Des problemes ont ete detectes!")
    print("="*60)
    
    return all_ok

def check_frontend_condition():
    """Verifie que la condition Svelte est correcte"""
    print("\n>>> ETAPE 6: Verification condition Frontend")
    
    frontend_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'frontend', 'src', 'lib', 'components', 'PositionCard.svelte'
    )
    
    with open(frontend_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chercher la condition du badge
    if 'ml_calibrated_winrate !== undefined && $activePosition.ml_calibrated_winrate !== null' in content:
        print("   [OK] Condition Frontend correcte (affiche meme si 0%)")
    elif 'ml_calibrated_winrate > 0' in content:
        print("   [WARN] Condition Frontend trop stricte (n'affiche pas si WR=0%)")
    else:
        print("   [INFO] Condition Frontend non trouvee ou differente")
    
    # Chercher le CSS
    if '.calib-badge' in content:
        print("   [OK] Style .calib-badge present")
    else:
        print("   [FAIL] Style .calib-badge ABSENT!")

if __name__ == "__main__":
    check_calibration_decision()
    check_frontend_condition()
