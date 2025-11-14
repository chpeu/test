#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage des placeholders dans VALUES"""

# Comptage ligne par ligne des placeholders dans VALUES (lignes 737-757)
placeholders = [
    10,  # Ligne 737
    10,  # Ligne 738
    8,   # Ligne 739
    4,   # Ligne 740
    8,   # Ligne 741
    10,  # Ligne 742
    4,   # Ligne 743
    6,   # Ligne 744
    6,   # Ligne 745
    4,   # Ligne 746
    8,   # Ligne 747
    4,   # Ligne 748
    2,   # Ligne 749
    6,   # Ligne 750
    6,   # Ligne 751
    2,   # Ligne 752
    4,   # Ligne 753
    2,   # Ligne 754
    4,   # Ligne 755
    2,   # Ligne 756
    1,   # Ligne 757
]

total = sum(placeholders)
print(f"Total placeholders: {total}")

# D'après les logs, il y a 128 paramètres
# Donc 128 - 111 = 17 paramètres en trop

