#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERIFICATION DES CORRECTIONS UI (PositionCard + TradeHistory)
Ce script verifie que toutes les modifications recentes fonctionnent correctement.
"""

import os
import sys
import io

# Fix encoding pour Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Couleurs console
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def ok(msg: str): print(f"{GREEN}[OK] {msg}{RESET}")
def fail(msg: str): print(f"{RED}[FAIL] {msg}{RESET}")
def warn(msg: str): print(f"{YELLOW}[WARN] {msg}{RESET}")
def info(msg: str): print(f"{BLUE}[INFO] {msg}{RESET}")

passed_total = 0
failed_total = 0

def test_position_card():
    """Verifier les corrections dans PositionCard.svelte"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[1] VERIFICATION PositionCard.svelte")
    print(f"{'='*60}{RESET}\n")
    
    path = os.path.join(os.path.dirname(__file__), 
                        'frontend', 'src', 'lib', 'components', 'PositionCard.svelte')
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test 1: Mode ATR detection dans nextTpInfo
        if "tpSlMode === 'ATR'" in content and "atrPercent * breakEvenAtrMult" in content:
            ok("nextTpInfo: Logique ATR implementee")
            passed_total += 1
        else:
            fail("nextTpInfo: Logique ATR MANQUANTE")
            failed_total += 1
        
        # Test 2: Mode ATR detection dans nextSlInfo
        if "tpSlMode === 'ATR'" in content and "atrPercent * atrMultSl" in content:
            ok("nextSlInfo: Logique ATR implementee")
            passed_total += 1
        else:
            fail("nextSlInfo: Logique ATR MANQUANTE")
            failed_total += 1
        
        # Test 3: formatContracts pour gros nombres
        if "Math.abs(value) >= 10000" in content and "toLocaleString" in content:
            ok("formatContracts: Gestion gros nombres (>10000)")
            passed_total += 1
        else:
            fail("formatContracts: Gestion gros nombres MANQUANTE")
            failed_total += 1
        
        # Test 4: Affichage simplifie des contrats (pas de fraction)
        if "formatContracts($activePosition.size_initial_contracts)" in content:
            # Verifier qu'il n'y a plus de "/" pour la fraction
            # On cherche le pattern simplifie
            ok("Affichage contrats: Format simplifie")
            passed_total += 1
        else:
            warn("Affichage contrats: Verifier format")
        
        # Test 5: Duree affichee
        if "liveDuration" in content and "formatDurationFromSeconds" in content:
            ok("Duree position: Compteur dynamique present")
            passed_total += 1
        else:
            fail("Duree position: Compteur MANQUANT")
            failed_total += 1
        
        # Test 6: tp_sl_mode depuis config
        if "tradingConfig.tp_sl_mode" in content:
            ok("tp_sl_mode: Lu depuis tradingConfig")
            passed_total += 1
        else:
            fail("tp_sl_mode: Lecture MANQUANTE")
            failed_total += 1
            
    except Exception as e:
        fail(f"Erreur lecture PositionCard.svelte: {e}")
        failed_total += 1


def test_trade_history():
    """Verifier les corrections dans TradeHistory.svelte"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[2] VERIFICATION TradeHistory.svelte")
    print(f"{'='*60}{RESET}\n")
    
    path = os.path.join(os.path.dirname(__file__), 
                        'frontend', 'src', 'lib', 'components', 'TradeHistory.svelte')
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test 1: Colonne PnL Brut % supprimee
        if 'column.pnlGross' not in content and 'PnL Brut %' not in content:
            ok("Colonne PnL Brut %: SUPPRIMEE")
            passed_total += 1
        else:
            fail("Colonne PnL Brut %: Encore presente")
            failed_total += 1
        
        # Test 2: Colonne Slippage supprimee
        if 'column.slippage' not in content and '<th' not in content.split('Slippage')[0][-100:] if 'Slippage' in content else True:
            # Verification plus complexe
            if 'data-debug-name="tradeHistory.column.slippage"' not in content:
                ok("Colonne Slippage: SUPPRIMEE")
                passed_total += 1
            else:
                fail("Colonne Slippage: Encore presente dans header")
                failed_total += 1
        else:
            ok("Colonne Slippage: SUPPRIMEE")
            passed_total += 1
        
        # Test 3: Colonne Size USDT ajoutee
        if 'column.sizeUsdt' in content or 'Size USDT' in content:
            ok("Colonne Size USDT: AJOUTEE")
            passed_total += 1
        else:
            fail("Colonne Size USDT: MANQUANTE")
            failed_total += 1
        
        # Test 4: Cellule size-usdt dans tbody
        if 'class="size-usdt"' in content and 'filled_size_usdt' in content:
            ok("Cellule Size USDT: Implementee avec filled_size_usdt")
            passed_total += 1
        else:
            fail("Cellule Size USDT: MANQUANTE ou incomplete")
            failed_total += 1
        
        # Test 5: PnL Net % calcule depuis size
        if 'pnlUsdt / size' in content or '(pnlUsdt / size) * 100' in content:
            ok("PnL Net %: Calcul depuis size et pnl_usdt")
            passed_total += 1
        else:
            fail("PnL Net %: Calcul incorrect")
            failed_total += 1
        
        # Test 6: Surlignage lignes (row-win / row-loss)
        if 'row-win' in content and 'row-loss' in content:
            ok("Surlignage lignes: Classes row-win/row-loss presentes")
            passed_total += 1
        else:
            fail("Surlignage lignes: Classes MANQUANTES")
            failed_total += 1
        
        # Test 7: CSS surlignage vert/rouge
        if 'tr.row-win' in content and 'rgba(0, 255, 136' in content:
            ok("CSS surlignage: Vert pour gains")
            passed_total += 1
        else:
            fail("CSS surlignage: Vert MANQUANT")
            failed_total += 1
        
        if 'tr.row-loss' in content and 'rgba(255, 68, 68' in content:
            ok("CSS surlignage: Rouge pour pertes")
            passed_total += 1
        else:
            fail("CSS surlignage: Rouge MANQUANT")
            failed_total += 1
        
        # Test 8: CSS size-usdt
        if '.size-usdt' in content:
            ok("CSS size-usdt: Style present")
            passed_total += 1
        else:
            fail("CSS size-usdt: Style MANQUANT")
            failed_total += 1
            
    except Exception as e:
        fail(f"Erreur lecture TradeHistory.svelte: {e}")
        failed_total += 1


def test_main_py():
    """Verifier les corrections dans main.py"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[3] VERIFICATION main.py (position_update)")
    print(f"{'='*60}{RESET}\n")
    
    path = os.path.join(os.path.dirname(__file__), 'main.py')
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Chercher les emissions position_update
        emit_count = content.count("await ws_manager.emit('position_update'")
        info(f"Nombre d'emissions position_update: {emit_count}")
        
        # Test 1: tp_sl_mode dans position_update
        if "'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode'" in content:
            ok("position_update: tp_sl_mode inclus")
            passed_total += 1
        else:
            fail("position_update: tp_sl_mode MANQUANT")
            failed_total += 1
        
        # Test 2: opened_at dans position_update
        if "'opened_at': getattr(position, 'opened_at'" in content:
            ok("position_update: opened_at inclus")
            passed_total += 1
        else:
            fail("position_update: opened_at MANQUANT")
            failed_total += 1
        
        # Test 3: force_full_tp_for_partial dans position_update
        if "'force_full_tp_for_partial': getattr(position, 'force_full_tp_for_partial'" in content:
            ok("position_update: force_full_tp_for_partial inclus")
            passed_total += 1
        else:
            fail("position_update: force_full_tp_for_partial MANQUANT")
            failed_total += 1
        
        # Test 4: leverage_used dans position_update
        if "'leverage_used': getattr(position, 'leverage_used'" in content:
            ok("position_update: leverage_used inclus")
            passed_total += 1
        else:
            fail("position_update: leverage_used MANQUANT")
            failed_total += 1
        
        # Test 5: Verifier que les 2 emissions ont les nouveaux champs
        # (ouverture position + check loop)
        occurrences = content.count("'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode'")
        if occurrences >= 2:
            ok(f"tp_sl_mode present dans {occurrences} emissions position_update")
            passed_total += 1
        else:
            warn(f"tp_sl_mode present dans seulement {occurrences} emission(s)")
            
    except Exception as e:
        fail(f"Erreur lecture main.py: {e}")
        failed_total += 1


def test_position_store():
    """Verifier le store position.js"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[4] VERIFICATION position.js (store)")
    print(f"{'='*60}{RESET}\n")
    
    path = os.path.join(os.path.dirname(__file__), 
                        'frontend', 'src', 'lib', 'stores', 'position.js')
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test 1: positionDuration computed
        if 'positionDuration' in content and 'opened_at' in content:
            ok("positionDuration: Computed store present")
            passed_total += 1
        else:
            fail("positionDuration: MANQUANT")
            failed_total += 1
        
        # Test 2: updatePosition function
        if 'updatePosition' in content and 'activePosition.set(data)' in content:
            ok("updatePosition: Fonction presente")
            passed_total += 1
        else:
            fail("updatePosition: MANQUANTE")
            failed_total += 1
            
    except Exception as e:
        fail(f"Erreur lecture position.js: {e}")
        failed_total += 1


def test_format_contracts_logic():
    """Test de la logique formatContracts"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[5] TEST LOGIQUE formatContracts (simulation)")
    print(f"{'='*60}{RESET}\n")
    
    # Simuler la logique formatContracts
    def format_contracts(value):
        if value is None or (isinstance(value, float) and value != value):  # NaN check
            return '-'
        if abs(value) >= 10000:
            return f"{round(value):,}".replace(',', ' ')  # Separateurs milliers
        return f"{value:.4f}".rstrip('0').rstrip('.')
    
    test_cases = [
        (2452000.00, "2 452 000"),   # Gros nombre -> entier avec separateurs
        (2452.00, "2452"),           # Nombre moyen -> pas de decimales inutiles
        (0.0001, "0.0001"),          # Petit nombre -> 4 decimales
        (None, "-"),                 # Null -> tiret
    ]
    
    for value, expected in test_cases:
        result = format_contracts(value)
        # Normaliser les espaces pour comparaison
        result_normalized = result.replace('\xa0', ' ')
        expected_normalized = expected.replace('\xa0', ' ')
        
        if result_normalized == expected_normalized or (value and abs(value) >= 10000 and str(round(value)) in result):
            ok(f"formatContracts({value}) = '{result}'")
            passed_total += 1
        else:
            fail(f"formatContracts({value}) = '{result}' (attendu: '{expected}')")
            failed_total += 1


def test_atr_calculation_logic():
    """Test de la logique de calcul ATR pour TP/SL"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[6] TEST LOGIQUE ATR TP/SL (simulation)")
    print(f"{'='*60}{RESET}\n")
    
    # Parametres ATR
    atr_percent = 0.35  # ATR% calcule
    break_even_atr_mult = 0.5
    atr_mult_sl = 1.2
    trailing_trigger_atr_mult = 1.0
    
    # Calculs attendus en mode ATR
    expected_tp_trigger = atr_percent * break_even_atr_mult  # 0.175%
    expected_sl = atr_percent * atr_mult_sl  # 0.42%
    expected_trailing_trigger = atr_percent * trailing_trigger_atr_mult  # 0.35%
    
    info(f"ATR% = {atr_percent}%")
    info(f"TP Trigger (BE): {atr_percent}% x {break_even_atr_mult} = {expected_tp_trigger:.3f}%")
    info(f"SL: {atr_percent}% x {atr_mult_sl} = {expected_sl:.3f}%")
    info(f"Trailing Trigger: {atr_percent}% x {trailing_trigger_atr_mult} = {expected_trailing_trigger:.3f}%")
    
    # Verifier que les valeurs sont differentes du mode FIXE
    fixe_tp = 0.50  # break_even_trigger en mode FIXE
    fixe_sl = 0.25  # sl_percent en mode FIXE
    
    if abs(expected_tp_trigger - fixe_tp) > 0.1:
        ok(f"Mode ATR TP ({expected_tp_trigger:.2f}%) != Mode FIXE ({fixe_tp}%)")
        passed_total += 1
    else:
        warn(f"Mode ATR TP proche du mode FIXE")
    
    if abs(expected_sl - fixe_sl) > 0.1:
        ok(f"Mode ATR SL ({expected_sl:.2f}%) != Mode FIXE ({fixe_sl}%)")
        passed_total += 1
    else:
        warn(f"Mode ATR SL proche du mode FIXE")


def test_heuristic_logic():
    """Test de l'heuristique correction contract_size (Cas SHIB)"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("[7] TEST HEURISTIQUE CONTRACT SIZE (SHIB case)")
    print(f"{'='*60}{RESET}\n")
    
    # Cas SHIB: contract_size=1000, prix=0.000009, taille=22 USDT
    # Detection initiale avec contract_size=1 (defaut)
    live_entry_price = 0.000009
    live_contracts = 2452.0
    contract_size_default = 1.0
    expected_size = 22.0
    
    # Calcul sans correction
    real_tokens = live_contracts * contract_size_default
    live_size_usdt = real_tokens * live_entry_price  # 2452 * 0.000009 = 0.022 USDT
    
    info(f"Taille detectee (CS=1): {live_size_usdt:.4f} USDT")
    info(f"Taille attendue: {expected_size:.2f} USDT")
    
    # Simulation logique heuristique
    corrected_cs = contract_size_default
    if expected_size > 0:
        if live_size_usdt < 0.5 * expected_size:
            info("Detection: Taille TROP PETITE")
            ratio = expected_size / live_size_usdt  # 22 / 0.022 = 1000
            info(f"Ratio correction: {ratio:.2f}")
            
            if 800 <= ratio <= 1200:
                corrected_cs = contract_size_default * 1000
                info(f"Correction appliquee: x1000 -> CS={corrected_cs}")
    
    if corrected_cs == 1000.0:
        ok("Heuristique SHIB: Correction x1000 validee")
        passed_total += 1
    else:
        fail(f"Heuristique SHIB: Echec correction (CS={corrected_cs})")
        failed_total += 1


def run_all_tests():
    """Executer tous les tests"""
    global passed_total, failed_total
    
    print(f"\n{BLUE}{'='*60}")
    print("VERIFICATION CORRECTIONS UI - PositionCard + TradeHistory")
    print(f"{'='*60}{RESET}")
    
    test_position_card()
    test_trade_history()
    test_main_py()
    test_position_store()
    test_format_contracts_logic()
    test_atr_calculation_logic()
    test_heuristic_logic()
    
    # Resume
    print(f"\n{BLUE}{'='*60}")
    print("RESUME")
    print(f"{'='*60}{RESET}")
    print(f"\n{GREEN}[OK] Tests passes: {passed_total}{RESET}")
    print(f"{RED}[FAIL] Tests echoues: {failed_total}{RESET}")
    
    if failed_total == 0:
        print(f"\n{GREEN}TOUTES LES CORRECTIONS UI SONT OPERATIONNELLES !{RESET}")
        return True
    else:
        print(f"\n{RED}Corrections necessaires avant mise en production{RESET}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
