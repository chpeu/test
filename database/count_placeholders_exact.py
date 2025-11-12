#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage exact des placeholders dans VALUES"""

# Lire le fichier et extraire la section VALUES
with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Trouver la section VALUES
start = content.find('VALUES (')
end = content.find('RETURNING id', start)
values_section = content[start:end]

# Compter les %s
placeholder_count = values_section.count('%s')
print(f"Total placeholders dans VALUES: {placeholder_count}")

# Compter ligne par ligne
lines = values_section.split('\n')
for i, line in enumerate(lines, 1):
    count = line.count('%s')
    if count > 0:
        print(f"Ligne {i}: {count} placeholders")

