#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage manuel des paramètres dans log_trade"""

# D'après le code, en comptant ligne par ligne :
# Ligne 916: 5 paramètres (entry_timestamp, exit_timestamp, session_id, opportunity_id, scan_log_id)
# Ligne 917-923: 7 paramètres (symbol, direction, entry_price, exit_price, size_usdt, tp_price, sl_price)
# Ligne 924-931: 8 paramètres (gross_pnl_usdt, gross_pnl_pct, gross_pnl_usdt DOUBLON, net_pnl_usdt, net_pnl_pct, fees, slippage, slippage_usdt)
# ... etc

# Total attendu: 111 paramètres (pour 111 placeholders)
# Total actuel: 128 paramètres (d'après les logs)

# Différence: 17 paramètres en trop

# D'après les logs:
# - Paramètre 15 est un doublon de gross_pnl_usdt (paramètre 13)
# - Il reste 16 autres paramètres en trop

print("Analyse des paramètres:")
print("Paramètre 13: gross_pnl_usdt")
print("Paramètre 14: pnl_pct (gross_pnl_pct)")
print("Paramètre 15: pnl_usdt (gross_pnl_usdt) - DOUBLON!")
print("")
print("Il faut supprimer le paramètre 15 (doublon de gross_pnl_usdt)")
print("Mais il reste encore 16 paramètres en trop à identifier...")

