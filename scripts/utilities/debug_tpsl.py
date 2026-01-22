#!/usr/bin/env python3
"""
Script de diagnostic TP/SL
Teste le calcul des niveaux FIXE et ATR
"""

from core.position.tp_sl_calculator import calculate_fixed_levels, TPSLConfig
from config import TRADING_CONFIG

def test_fixed_sl_calculation():
    """Test calcul SL en mode FIXE"""
    print("\n" + "="*60)
    print("TEST CALCUL SL MODE FIXE")
    print("="*60)

    # Configuration depuis config.py
    config = TPSLConfig(
        fixed_tp_pct=TRADING_CONFIG['tp_percent'],
        fixed_sl_pct=TRADING_CONFIG['sl_percent']
    )

    print(f"\n📋 Configuration:")
    print(f"  - fixed_sl_pct: {config.fixed_sl_pct}%")
    print(f"  - fixed_tp_pct: {config.fixed_tp_pct}%")

    # Test cas réels
    test_cases = [
        ("SOL/USDT:USDT", 200.0, "LONG"),
        ("SOL/USDT:USDT", 200.0, "SHORT"),
        ("BTC/USDT:USDT", 60000.0, "LONG"),
        ("DOGE/USDT:USDT", 0.15, "LONG"),
    ]

    for symbol, entry, direction in test_cases:
        sl, tp = calculate_fixed_levels(entry, direction, config)

        # Calculer le % réel
        if direction == "LONG":
            sl_pct = ((sl - entry) / entry) * 100
            tp_pct = ((tp - entry) / entry) * 100
        else:
            sl_pct = ((entry - sl) / entry) * 100
            tp_pct = ((entry - tp) / entry) * 100

        print(f"\n🧪 Test: {symbol} {direction}")
        print(f"  Entry:  {entry:.8f}")
        print(f"  SL:     {sl:.8f}  ({sl_pct:+.4f}%)  [attendu: {-config.fixed_sl_pct:.2f}%]")
        print(f"  TP:     {tp:.8f}  ({tp_pct:+.4f}%)  [attendu: {+config.fixed_tp_pct:.2f}%]")

        # Vérifier si ça matche
        tolerance = 0.01  # 0.01% de tolérance
        sl_ok = abs(abs(sl_pct) - config.fixed_sl_pct) < tolerance
        tp_ok = abs(abs(tp_pct) - config.fixed_tp_pct) < tolerance

        if not sl_ok:
            print(f"  ❌ SL INCORRECT! Attendu: {-config.fixed_sl_pct:.2f}%, Reçu: {sl_pct:+.4f}%")
            print(f"     Différence: {abs(abs(sl_pct) - config.fixed_sl_pct):.4f}%")
        else:
            print(f"  ✅ SL correct")

        if not tp_ok:
            print(f"  ❌ TP INCORRECT! Attendu: {+config.fixed_tp_pct:.2f}%, Reçu: {tp_pct:+.4f}%")
        else:
            print(f"  ✅ TP correct")

if __name__ == "__main__":
    test_fixed_sl_calculation()
    print("\n" + "="*60)
    print("DIAGNOSTIC TERMINÉ")
    print("="*60 + "\n")
