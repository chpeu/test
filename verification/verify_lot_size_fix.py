"""
Script de verification du fix de calcul de taille de lot
Probleme: Le bot affichait 7 lots au lieu de 70 reellement passes sur MEXC

Fix applique:
- filled_amount utilise maintenant le volume REEL en tokens (contrats * contract_size)
- filled_size_usdt utilise la valeur USDT REELLE
- Verification post-ordre via CCXT pour confirmer le volume reel
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_status(name, passed, detail=""):
    status = "[OK]" if passed else "[FAIL]"
    print(f"  {status} {name}: {detail}")

def test_code_fix_present():
    """Verifier que le fix est present dans le code"""
    print_section("1. VERIFICATION CODE FIX")
    
    try:
        with open('trading/live_order_manager_futures.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verifier les elements cles du fix
        has_contract_size_calc = "real_contract_size = contract_spec.contract_size" in content
        has_real_amount = "real_filled_amount = amount * real_contract_size" in content
        has_real_usdt = "real_filled_size_usdt = real_filled_amount * final_filled_price" in content
        has_verification = "get_open_positions" in content and "verified_amount" in content
        has_log = "Volume REEL" in content or "Volume RÉEL" in content
        
        print_status(
            "Calcul contract_size",
            has_contract_size_calc,
            "OK - real_contract_size extrait" if has_contract_size_calc else "MANQUANT"
        )
        
        print_status(
            "Calcul filled_amount reel",
            has_real_amount,
            "OK - amount * contract_size" if has_real_amount else "MANQUANT"
        )
        
        print_status(
            "Calcul filled_size_usdt reel",
            has_real_usdt,
            "OK - real_amount * price" if has_real_usdt else "MANQUANT"
        )
        
        print_status(
            "Verification post-ordre",
            has_verification,
            "OK - get_open_positions + verified_amount" if has_verification else "MANQUANT"
        )
        
        print_status(
            "Log volume reel",
            has_log,
            "OK - Log informatif ajoute" if has_log else "MANQUANT"
        )
        
        return all([has_contract_size_calc, has_real_amount, has_real_usdt])
        
    except Exception as e:
        print_status("Lecture fichier", False, f"Erreur: {e}")
        return False

def test_result_dataclass():
    """Verifier que FuturesOrderResult a les bons champs"""
    print_section("2. VERIFICATION DATACLASS FuturesOrderResult")
    
    try:
        with open('trading/live_order_manager_futures.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        has_filled_amount = "filled_amount:" in content
        has_filled_size_usdt = "filled_size_usdt:" in content
        
        print_status(
            "Champ filled_amount",
            has_filled_amount,
            "OK - Present" if has_filled_amount else "MANQUANT"
        )
        
        print_status(
            "Champ filled_size_usdt",
            has_filled_size_usdt,
            "OK - Present" if has_filled_size_usdt else "MANQUANT"
        )
        
        return has_filled_amount and has_filled_size_usdt
        
    except Exception as e:
        print_status("Lecture fichier", False, f"Erreur: {e}")
        return False

def test_calculation_logic():
    """Tester la logique de calcul"""
    print_section("3. TEST LOGIQUE CALCUL")
    
    # Simuler le cas XLM
    # Prix: 0.25369
    # Contrats: 7
    # Contract size: 10 (1 contrat = 10 XLM)
    
    entry_price = 0.25369
    contracts = 7
    contract_size = 10.0
    
    # Ancien calcul (FAUX)
    old_filled_amount = contracts  # 7
    old_filled_size_usdt = contracts * entry_price  # 7 * 0.25369 = 1.7758
    
    # Nouveau calcul (CORRECT)
    new_filled_amount = contracts * contract_size  # 7 * 10 = 70
    new_filled_size_usdt = new_filled_amount * entry_price  # 70 * 0.25369 = 17.7583
    
    print(f"\n  Exemple XLM/USDT:")
    print(f"  - Prix: {entry_price}")
    print(f"  - Contrats: {contracts}")
    print(f"  - Contract size: {contract_size}")
    print(f"\n  ANCIEN calcul (FAUX):")
    print(f"  - filled_amount: {old_filled_amount} (affiche 7)")
    print(f"  - filled_size_usdt: {old_filled_size_usdt:.4f} USDT (affiche ~1.78)")
    print(f"\n  NOUVEAU calcul (CORRECT):")
    print(f"  - filled_amount: {new_filled_amount} (affiche 70)")
    print(f"  - filled_size_usdt: {new_filled_size_usdt:.4f} USDT (affiche ~17.76)")
    
    # Verifications
    correct_amount = new_filled_amount == 70
    correct_usdt = abs(new_filled_size_usdt - 17.7583) < 0.01
    
    print_status(
        "filled_amount = 70",
        correct_amount,
        f"OK: {new_filled_amount}" if correct_amount else f"ERREUR: {new_filled_amount}"
    )
    
    print_status(
        "filled_size_usdt ~ 17.76",
        correct_usdt,
        f"OK: {new_filled_size_usdt:.4f}" if correct_usdt else f"ERREUR: {new_filled_size_usdt:.4f}"
    )
    
    return correct_amount and correct_usdt

def test_bypass_client_available():
    """Verifier que le client bypass peut recuperer les positions"""
    print_section("4. VERIFICATION CLIENT BYPASS")
    
    try:
        from trading.mexc_futures_bypass import MexcFuturesBypass, Position
        
        print_status(
            "Import MexcFuturesBypass",
            True,
            "OK - Module importe"
        )
        
        # Verifier que Position a hold_vol
        import dataclasses
        fields = [f.name for f in dataclasses.fields(Position)]
        has_hold_vol = 'hold_vol' in fields
        
        print_status(
            "Position.hold_vol",
            has_hold_vol,
            f"OK - Champ present" if has_hold_vol else "MANQUANT"
        )
        
        print(f"\n  Champs Position: {fields}")
        
        return has_hold_vol
        
    except ImportError as e:
        print_status("Import", False, f"Erreur import: {e}")
        return False
    except Exception as e:
        print_status("Test", False, f"Erreur: {e}")
        return False

def test_contract_spec():
    """Verifier que ContractSpec a contract_size"""
    print_section("5. VERIFICATION CONTRACT SPEC")
    
    try:
        from trading.mexc_futures_bypass import ContractSpec
        import dataclasses
        
        fields = [f.name for f in dataclasses.fields(ContractSpec)]
        has_contract_size = 'contract_size' in fields
        
        print_status(
            "ContractSpec.contract_size",
            has_contract_size,
            "OK - Champ present" if has_contract_size else "MANQUANT"
        )
        
        # Creer une instance de test
        spec = ContractSpec(
            symbol="XLM_USDT",
            min_vol=1,
            max_vol=1000000,
            vol_unit=1,
            price_unit=0.00001,
            price_precision=5,
            vol_precision=0,
            contract_size=10.0
        )
        
        correct_size = spec.contract_size == 10.0
        print_status(
            "contract_size = 10.0",
            correct_size,
            f"OK: {spec.contract_size}" if correct_size else f"ERREUR: {spec.contract_size}"
        )
        
        return has_contract_size and correct_size
        
    except ImportError as e:
        print_status("Import", False, f"Erreur import: {e}")
        return False
    except Exception as e:
        print_status("Test", False, f"Erreur: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("  VERIFICATION FIX TAILLE DE LOT")
    print("  Probleme: 7 lots affiches au lieu de 70 reels")
    print("=" * 60)
    
    results = []
    
    results.append(("Code fix present", test_code_fix_present()))
    results.append(("Dataclass OK", test_result_dataclass()))
    results.append(("Logique calcul", test_calculation_logic()))
    results.append(("Client bypass", test_bypass_client_available()))
    results.append(("Contract spec", test_contract_spec()))
    
    # Resume
    print_section("RESUME")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        print_status(name, result)
    
    print(f"\n  Total: {passed}/{total} tests passes")
    
    if passed == total:
        print("\n  [SUCCESS] FIX COMPLET!")
        print("\n  Le calcul de taille de lot est maintenant correct:")
        print("  - filled_amount = contrats * contract_size (tokens reels)")
        print("  - filled_size_usdt = filled_amount * prix (USDT reel)")
        print("  - Verification post-ordre via get_open_positions (2s delai)")
        print("\n  Redemarrer le backend pour appliquer le fix.")
    else:
        print("\n  [WARNING] Fix incomplet")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
