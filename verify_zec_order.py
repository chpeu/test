# -*- coding: utf-8 -*-
"""
Script de verification des ordres ZEC/USDT sur MEXC Futures
Verifie les specs du contrat et simule un ordre pour diagnostiquer le probleme
"""

import sys
import os
import asyncio

# Forcer UTF-8 pour Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le chemin du projet
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def verify_zec_contract_specs():
    """Verifier les specs du contrat ZEC sur MEXC"""
    print("\n=== Verification des specs du contrat ZEC ===")
    
    try:
        from trading.mexc_futures_bypass import MexcFuturesBypassClient
        
        # Creer le client bypass
        browser_token = os.environ.get('MEXC_BROWSER_TOKEN')
        if not browser_token:
            # Essayer de le lire depuis config
            try:
                from config import TRADING_CONFIG
                browser_token = TRADING_CONFIG.get('browser_token') or TRADING_CONFIG.get('MEXC_BROWSER_TOKEN')
            except:
                pass
        
        if not browser_token:
            print("[WARN] Pas de browser_token, utilisation de valeurs par defaut")
            # Valeurs typiques pour ZEC
            print("\nSpecs ZEC (valeurs typiques MEXC):")
            print(f"  contract_size: 1.0 (1 contrat = 1 ZEC)")
            print(f"  min_vol: 0.1")
            print(f"  vol_unit: 0.1")
            print(f"  vol_precision: 1")
            print(f"  price_precision: 2")
            
            # Calcul pour 1 contrat a ~460 USDT
            entry_price = 460.0
            contract_size = 1.0
            min_vol = 0.1
            
            print(f"\n=== Calcul pour ZEC @ {entry_price} USDT ===")
            
            # Valeur de 0.1 contrat (min_vol)
            value_min = min_vol * entry_price * contract_size
            print(f"  0.1 contrat (min) = {value_min:.2f} USDT")
            
            # Valeur de 1 contrat
            value_1 = 1.0 * entry_price * contract_size
            print(f"  1 contrat = {value_1:.2f} USDT")
            
            # Minimum pour 6 USDT
            min_contracts = 6.0 / (entry_price * contract_size)
            print(f"\n  Pour atteindre 6 USDT minimum:")
            print(f"    min_contracts = 6 / ({entry_price} * {contract_size}) = {min_contracts:.4f}")
            
            # Arrondi au vol_unit
            import math
            min_contracts_rounded = math.ceil(min_contracts / min_vol) * min_vol
            value_rounded = min_contracts_rounded * entry_price * contract_size
            print(f"    Arrondi a vol_unit={min_vol}: {min_contracts_rounded} contrats = {value_rounded:.2f} USDT")
            
            return True
        
        client = MexcFuturesBypassClient(browser_token=browser_token)
        
        # Recuperer les specs ZEC
        specs = await client.get_contract_spec("ZEC_USDT")
        
        if specs:
            print(f"\nSpecs ZEC_USDT:")
            print(f"  contract_size: {specs.contract_size}")
            print(f"  min_vol: {specs.min_vol}")
            print(f"  max_vol: {specs.max_vol}")
            print(f"  vol_unit: {specs.vol_unit}")
            print(f"  vol_precision: {specs.vol_precision}")
            print(f"  price_unit: {specs.price_unit}")
            print(f"  price_precision: {specs.price_precision}")
            
            # Calcul
            entry_price = 460.0  # Prix approximatif ZEC
            print(f"\n=== Calcul pour ZEC @ {entry_price} USDT ===")
            
            # Valeur de min_vol contrat
            value_min = specs.min_vol * entry_price * specs.contract_size
            print(f"  {specs.min_vol} contrat (min) = {value_min:.2f} USDT")
            
            # Valeur de 1 contrat
            value_1 = 1.0 * entry_price * specs.contract_size
            print(f"  1 contrat = {value_1:.2f} USDT")
            
            # Minimum pour 6 USDT
            min_contracts = 6.0 / (entry_price * specs.contract_size)
            print(f"\n  Pour atteindre 6 USDT minimum:")
            print(f"    min_contracts = 6 / ({entry_price} * {specs.contract_size}) = {min_contracts:.4f}")
            
            # Arrondi au vol_unit
            import math
            if specs.vol_unit > 0:
                min_contracts_rounded = math.ceil(min_contracts / specs.vol_unit) * specs.vol_unit
            else:
                min_contracts_rounded = round(min_contracts, specs.vol_precision)
            value_rounded = min_contracts_rounded * entry_price * specs.contract_size
            print(f"    Arrondi a vol_unit={specs.vol_unit}: {min_contracts_rounded} contrats = {value_rounded:.2f} USDT")
            
            # DIAGNOSTIC: Est-ce que la valeur min est < 5 USDT?
            if value_min < 5:
                print(f"\n  [PROBLEME] La valeur minimum ({value_min:.2f} USDT) est < 5 USDT!")
                print(f"    MEXC refuse les ordres < 5 USDT")
                print(f"    Il faut augmenter le nombre de contrats")
            
            return True
        else:
            print("[ERREUR] Impossible de recuperer les specs ZEC")
            return False
            
    except Exception as e:
        print(f"[ERREUR] {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_order_calculation():
    """Simuler le calcul d'ordre pour ZEC"""
    print("\n=== Simulation du calcul d'ordre ZEC ===")
    
    # Parametres simules
    entry_price = 460.73
    size_usdt = 0.0  # Probleme: size_usdt = 0
    contract_size = 1.0
    min_vol = 0.1
    vol_unit = 0.1
    MIN_ORDER_USDT = 6.0
    
    print(f"\nParametres initiaux:")
    print(f"  entry_price: {entry_price}")
    print(f"  size_usdt: {size_usdt}")
    print(f"  contract_size: {contract_size}")
    print(f"  min_vol: {min_vol}")
    print(f"  vol_unit: {vol_unit}")
    print(f"  MIN_ORDER_USDT: {MIN_ORDER_USDT}")
    
    # Etape 1: Calcul amount initial
    amount = size_usdt / entry_price
    print(f"\nEtape 1: amount = size_usdt / entry_price = {size_usdt} / {entry_price} = {amount}")
    
    # Etape 2: Division par contract_size (si != 1)
    if contract_size != 1.0:
        original_amount = amount
        amount = amount / contract_size
        print(f"Etape 2: amount = {original_amount} / {contract_size} = {amount} contrats")
    else:
        print(f"Etape 2: contract_size = 1, pas de conversion")
    
    # Etape 3: Arrondi
    import math
    amount = round(amount, 1)  # vol_precision = 1
    print(f"Etape 3: amount arrondi = {amount}")
    
    # Etape 4: Calcul valeur USDT
    actual_size_usdt = amount * entry_price * contract_size
    print(f"Etape 4: actual_size_usdt = {amount} * {entry_price} * {contract_size} = {actual_size_usdt:.2f} USDT")
    
    # Etape 5: Verification minimum
    if actual_size_usdt < MIN_ORDER_USDT:
        print(f"\nEtape 5: actual_size_usdt ({actual_size_usdt:.2f}) < MIN_ORDER_USDT ({MIN_ORDER_USDT})")
        print(f"  -> Augmentation automatique necessaire")
        
        # Calcul minimum
        min_amount_needed = MIN_ORDER_USDT / (entry_price * contract_size)
        print(f"  min_amount_needed = {MIN_ORDER_USDT} / ({entry_price} * {contract_size}) = {min_amount_needed:.6f}")
        
        # Arrondi vers le haut
        min_amount_needed = math.ceil(min_amount_needed / vol_unit) * vol_unit
        print(f"  Arrondi au vol_unit ({vol_unit}): {min_amount_needed}")
        
        # Recalcul
        recalc_usdt = min_amount_needed * entry_price * contract_size
        print(f"  Valeur recalculee: {min_amount_needed} * {entry_price} * {contract_size} = {recalc_usdt:.2f} USDT")
        
        amount = min_amount_needed
        actual_size_usdt = recalc_usdt
    
    print(f"\n=== RESULTAT FINAL ===")
    print(f"  amount: {amount} contrats")
    print(f"  valeur: {actual_size_usdt:.2f} USDT")
    print(f"  > 5 USDT minimum MEXC: {'OUI' if actual_size_usdt >= 5 else 'NON'}")
    
    # DIAGNOSTIC: Pourquoi l'ordre echoue?
    print(f"\n=== DIAGNOSTIC ===")
    if amount == 1.0:
        print(f"  Le log montre '1.000000 contrats (460.73 USDT)'")
        print(f"  C'est correct: 1 * 460.73 * 1 = 460.73 USDT > 5 USDT")
        print(f"\n  [HYPOTHESE] Le probleme pourrait etre:")
        print(f"    1. Le format du parametre 'vol' envoye a MEXC")
        print(f"    2. Un arrondi qui donne 0 au lieu de 1")
        print(f"    3. Une confusion entre tokens et contrats")
    
    return True

def check_code_for_issues():
    """Verifier le code pour des problemes potentiels"""
    print("\n=== Verification du code ===")
    
    checks = []
    
    try:
        # Verifier live_order_manager_futures.py
        with open('trading/live_order_manager_futures.py', 'r', encoding='utf-8') as f:
            lom_content = f.read()
        
        # Check 1: Validation amount > 0
        has_amount_check = 'if amount <= 0' in lom_content
        checks.append(("Validation amount > 0 avant envoi", has_amount_check))
        print(f"[{'OK' if has_amount_check else 'MANQUE'}] Validation amount > 0 avant envoi")
        
        # Check 2: Validation valeur finale >= 5 USDT
        has_value_check = 'final_value_usdt < 5.0' in lom_content
        checks.append(("Validation valeur >= 5 USDT", has_value_check))
        print(f"[{'OK' if has_value_check else 'MANQUE'}] Validation valeur finale >= 5 USDT")
        
        # Check 3: Log valeur USDT avant envoi
        has_value_log = 'Valeur:' in lom_content and 'USDT' in lom_content
        checks.append(("Log valeur USDT avant envoi", has_value_log))
        print(f"[{'OK' if has_value_log else 'MANQUE'}] Log valeur USDT avant envoi")
        
        # Verifier position_manager.py
        with open('core/position_manager.py', 'r', encoding='utf-8') as f:
            pm_content = f.read()
        
        # Check 4: Validation size minimum dans open_position
        has_size_check = 'MIN_SIZE_USDT = 7.0' in pm_content
        checks.append(("Validation size >= 7 USDT dans open_position", has_size_check))
        print(f"[{'OK' if has_size_check else 'MANQUE'}] Validation size >= 7 USDT dans open_position")
        
        # Check 5: Log critique size recu
        has_size_log = 'OPEN_POSITION recu' in pm_content or 'OPEN_POSITION reçu' in pm_content
        checks.append(("Log critique size recu", has_size_log))
        print(f"[{'OK' if has_size_log else 'MANQUE'}] Log critique size recu")
        
        # Verifier mexc_futures_bypass.py
        with open('trading/mexc_futures_bypass.py', 'r', encoding='utf-8') as f:
            bypass_content = f.read()
        
        # Check 6: Log SUBMIT ORDER CRITIQUE
        has_submit_log = 'SUBMIT ORDER CRITIQUE' in bypass_content
        checks.append(("Log SUBMIT ORDER CRITIQUE", has_submit_log))
        print(f"[{'OK' if has_submit_log else 'MANQUE'}] Log SUBMIT ORDER CRITIQUE")
        
        # Resume
        ok_count = sum(1 for _, ok in checks if ok)
        total = len(checks)
        print(f"\n=== RESUME: {ok_count}/{total} verifications OK ===")
        
        return ok_count == total
        
    except Exception as e:
        print(f"[ERREUR] {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executer tous les tests"""
    print("=" * 60)
    print("VERIFICATION ORDRES ZEC/USDT MEXC FUTURES")
    print("=" * 60)
    
    # Changer au repertoire du projet
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Test 1: Simulation du calcul
    simulate_order_calculation()
    
    # Test 2: Verification du code
    check_code_for_issues()
    
    # Test 3: Specs reelles (si token disponible)
    print("\n" + "=" * 60)
    asyncio.run(verify_zec_contract_specs())
    
    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("""
Le probleme identifie:
1. size_usdt = 0 passe a open_position
2. Le code calcule amount = 0 / price = 0
3. L'augmentation automatique calcule 0.1 contrats (46 USDT)
   mais le log montre 1.0 contrat (460 USDT)
4. L'ordre est envoye mais MEXC dit "< 5 USDT"

HYPOTHESES:
- Le parametre vol pourrait etre envoye dans le mauvais format
- Il y a peut-etre un arrondi qui donne 0 quelque part
- La valeur size_usdt = 0 vient de calculate_position_size

SOLUTION RECOMMANDEE:
1. Verifier que calculate_position_size retourne >= 7 USDT
2. Ajouter une validation finale avant l'envoi de l'ordre
3. Logger le vol exact envoye a MEXC
""")
    
    return True

if __name__ == "__main__":
    main()
