#!/usr/bin/env python3
"""
Script pour analyser le bug de calcul PnL dans live_order_manager_futures.py
"""

# Exemple SHIBUSDT
entry_price = 6.617e-06  # Prix d'entrée
exit_price = 6.632e-06   # Prix de sortie (monté!)
direction = "SHORT"

# Simulons le calcul actuel dans live_order_manager_futures.py ligne 2089-2092:
# if direction == 'LONG':
#     pnl_usdt = (filled_price - entry_price) * filled_amount
# else:
#     pnl_usdt = (entry_price - filled_price) * filled_amount

# Supposons filled_amount = 37000 contrats (valeur typique pour SHIB)
filled_amount = 37000  # contrats

if direction == 'LONG':
    pnl_usdt_bug = (exit_price - entry_price) * filled_amount
else:
    pnl_usdt_bug = (entry_price - exit_price) * filled_amount

print("="*70)
print("ANALYSE DU BUG PnL - SHIBUSDT SHORT")
print("="*70)
print(f"\nParamètres:")
print(f"  Entry price: {entry_price:.10f}")
print(f"  Exit price:  {exit_price:.10f}")
print(f"  Direction:   {direction}")
print(f"  Filled amount (contrats): {filled_amount}")

print(f"\nCalcul ACTUEL (buggy):")
print(f"  PnL = (entry - exit) * filled_amount")
print(f"  PnL = ({entry_price:.10f} - {exit_price:.10f}) * {filled_amount}")
print(f"  PnL = {entry_price - exit_price:.10f} * {filled_amount}")
print(f"  PnL = {pnl_usdt_bug:.4f} USDT")

print(f"\nAttendu pour SHORT quand prix monte:")
print(f"  Le PnL devrait être NEGATIF (perte)")
print(f"  Mais le calcul donne: {pnl_usdt_bug:.4f}")

# Maintenant avec contract_size
contract_size = 100  # SHIB a 100 tokens par contrat sur MEXC
real_tokens = filled_amount * contract_size
pnl_correct = (entry_price - exit_price) * real_tokens

print(f"\nCalcul CORRECT (avec contract_size):")
print(f"  Contract size: {contract_size} tokens/contrat")
print(f"  Real tokens: {filled_amount} * {contract_size} = {real_tokens}")
print(f"  PnL = (entry - exit) * real_tokens")
print(f"  PnL = ({entry_price:.10f} - {exit_price:.10f}) * {real_tokens}")
print(f"  PnL = {entry_price - exit_price:.10f} * {real_tokens}")
print(f"  PnL = {pnl_correct:.4f} USDT")

print(f"\n" + "="*70)
print("PROBLÈME IDENTIFIÉ:")
print("="*70)
print("""
Dans live_order_manager_futures.py ligne 2089-2092:

    if direction == 'LONG':
        pnl_usdt = (filled_price - entry_price) * filled_amount
    else:
        pnl_usdt = (entry_price - filled_price) * filled_amount

BUG #1: filled_amount est en CONTRATS, pas en tokens
BUG #2: Le calcul ne multiplie pas par contract_size

Résultat: Le PnL calculé est ~100x trop petit (selon contract_size)
         et est ensuite écrasé par le PnL calculé par le bot qui est faux.
""")

# Vérifions aussi le signe
print("\nVérification du signe:")
print(f"  Entry → Exit: {entry_price:.10f} → {exit_price:.10f}")
print(f"  Prix est monté: {exit_price > entry_price}")
print(f"  Direction: {direction}")
print(f"  Pour SHORT, si prix monte → Perte (PnL négatif)")
print(f"  PnL calculé: {pnl_usdt_bug:.4f}")
print(f"  Signe correct? {'OUI' if pnl_usdt_bug < 0 else 'NON - C EST LE BUG!'}")
