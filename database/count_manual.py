#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage manuel des paramètres"""

# Comptage manuel ligne par ligne du tuple params (lignes 915-1017)
# Ligne 916: 5 paramètres
# Ligne 917-923: 7 paramètres
# Ligne 924-931: 8 paramètres
# Ligne 932-933: 2 paramètres
# Ligne 934-942: 9 paramètres
# Ligne 943-944: 2 paramètres
# Ligne 946-951: 6 paramètres
# Ligne 953-954: 4 paramètres
# Ligne 956-959: 8 paramètres
# Ligne 961-963: 8 paramètres
# Ligne 965-966: 6 paramètres
# Ligne 968-969: 4 paramètres
# Ligne 971-974: 12 paramètres
# Ligne 976-979: 8 paramètres
# Ligne 981-985: 5 paramètres
# Ligne 987: 2 paramètres
# Ligne 989-996: 12 paramètres
# Ligne 997: 1 paramètre
# Ligne 999: 2 paramètres
# Ligne 1001-1002: 4 paramètres
# Ligne 1004-1005: 2 paramètres
# Ligne 1007-1008: 4 paramètres
# Ligne 1010-1013: 4 paramètres
# Ligne 1015-1016: 2 paramètres

total = 5+7+8+2+9+2+6+4+8+8+6+4+12+8+5+2+12+1+2+4+2+4+4+2
print(f"Total paramètres comptés manuellement: {total}")

# Mais d'après les logs, il y a 128 paramètres
# Donc il y a 128 - 111 = 17 paramètres en trop
# Le paramètre 15 est un doublon de gross_pnl_usdt
# Il reste 16 autres paramètres en trop à identifier

