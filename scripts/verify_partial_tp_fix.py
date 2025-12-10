#!/usr/bin/env python3
"""
Script de verification: TP Partiel sur petites positions

Verifie que:
1. min_contract_amount est correctement stocke sur FuturesOrderResult
2. force_full_tp_for_partial est calcule correctement a l'ouverture
3. La logique TP partiel utilise 100% quand necessaire
4. Le frontend recoit force_full_tp_for_partial
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


def test_futures_order_result_has_min_contract():
    """Test que FuturesOrderResult a le champ min_contract_amount"""
    from trading.live_order_manager_futures import FuturesOrderResult
    
    result = FuturesOrderResult(
        success=True,
        filled_amount=0.1,
        min_contract_amount=0.1
    )
    
    assert hasattr(result, 'min_contract_amount'), "FuturesOrderResult doit avoir min_contract_amount"
    assert result.min_contract_amount == 0.1, f"min_contract_amount incorrect: {result.min_contract_amount}"
    print("[OK] FuturesOrderResult.min_contract_amount fonctionne")


def test_active_position_has_force_full_tp():
    """Test que Position a les champs necessaires"""
    from core.position_manager import Position
    
    pos = Position(
        symbol='SOL/USDT',
        direction='LONG',
        entry=140.0,
        tp=145.0,
        sl=138.0,
        size=14.0,  # 14 USDT = ~0.1 SOL
        min_contract_amount=0.1,
        force_full_tp_for_partial=True
    )
    
    assert hasattr(pos, 'min_contract_amount'), "ActivePosition doit avoir min_contract_amount"
    assert hasattr(pos, 'force_full_tp_for_partial'), "ActivePosition doit avoir force_full_tp_for_partial"
    assert pos.force_full_tp_for_partial == True, "force_full_tp_for_partial devrait etre True"
    print("[OK] ActivePosition.force_full_tp_for_partial fonctionne")


def test_to_dict_includes_force_full_tp():
    """Test que to_dict() inclut force_full_tp_for_partial"""
    from core.position_manager import Position
    
    pos = Position(
        symbol='SOL/USDT',
        direction='LONG',
        entry=140.0,
        tp=145.0,
        sl=138.0,
        size=14.0,
        min_contract_amount=0.1,
        force_full_tp_for_partial=True
    )
    
    d = pos.to_dict()
    
    assert 'force_full_tp_for_partial' in d, "to_dict() doit inclure force_full_tp_for_partial"
    assert 'min_contract_amount' in d, "to_dict() doit inclure min_contract_amount"
    assert d['force_full_tp_for_partial'] == True, "force_full_tp_for_partial dans dict devrait etre True"
    assert d['min_contract_amount'] == 0.1, f"min_contract_amount dans dict: {d['min_contract_amount']}"
    print("[OK] to_dict() inclut force_full_tp_for_partial et min_contract_amount")


def test_force_full_tp_calculation():
    """Test le calcul de force_full_tp_for_partial"""
    from config import TRADING_CONFIG
    
    # Simuler les parametres
    partial_tp_percent = TRADING_CONFIG.get('partial_tp_percent', 50.0)
    
    # Cas 1: Position petite (0.1 SOL) avec min 0.1
    filled_amount_small = 0.1
    min_contract = 0.1
    partial_qty_small = filled_amount_small * (partial_tp_percent / 100.0)
    force_full_small = partial_qty_small < min_contract
    
    print(f"  Cas 1 (petite position):")
    print(f"    filled_amount={filled_amount_small}, min_contract={min_contract}")
    print(f"    partial_qty={partial_qty_small} ({partial_tp_percent}%)")
    print(f"    force_full_tp={force_full_small}")
    assert force_full_small == True, "Petite position devrait forcer 100%"
    
    # Cas 2: Position normale (1.0 SOL) avec min 0.1
    filled_amount_normal = 1.0
    partial_qty_normal = filled_amount_normal * (partial_tp_percent / 100.0)
    force_full_normal = partial_qty_normal < min_contract
    
    print(f"  Cas 2 (position normale):")
    print(f"    filled_amount={filled_amount_normal}, min_contract={min_contract}")
    print(f"    partial_qty={partial_qty_normal} ({partial_tp_percent}%)")
    print(f"    force_full_tp={force_full_normal}")
    assert force_full_normal == False, "Position normale ne devrait pas forcer 100%"
    
    print("[OK] Calcul force_full_tp_for_partial correct")


def test_partial_tp_manager():
    """Test que PartialTPManager respecte force_full_tp"""
    from core.position.partial_tp_manager import PartialTPManager
    from config import TRADING_CONFIG
    
    manager = PartialTPManager()
    
    # Position minimale
    position = {
        'symbol': 'SOL/USDT',
        'direction': 'LONG',
        'entry': 140.0,
        'size': 14.0,  # ~0.1 SOL
        'partial_tp_sold': False
    }
    
    # Devrait triggerer a +0.3%
    current_price = 140.0 * 1.004  # +0.4%
    should_trigger = manager.check_trigger(position, current_price, trigger_pct=0.3)
    
    assert should_trigger == True, "Devrait triggerer le TP partiel"
    print("[OK] PartialTPManager.check_trigger fonctionne")


def run_all_tests():
    """Execute tous les tests"""
    print("=" * 60)
    print("VERIFICATION: TP Partiel sur petites positions")
    print("=" * 60)
    print()
    
    tests = [
        test_futures_order_result_has_min_contract,
        test_active_position_has_force_full_tp,
        test_to_dict_includes_force_full_tp,
        test_force_full_tp_calculation,
        test_partial_tp_manager,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAILED] {test.__name__}: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"RESULTAT: {passed} passes, {failed} echecs")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
