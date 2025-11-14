#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage exact des paramètres et placeholders"""

import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver INSERT INTO trades
start_insert = content.find('INSERT INTO trades (', content.find('def log_trade'))
end_insert = content.find(')', start_insert)
insert_section = content[start_insert:end_insert]

# Compter les colonnes (en excluant les commentaires)
lines = insert_section.split('\n')
columns = []
for line in lines:
    line = line.strip()
    if not line or line.startswith('--') or line.startswith('INSERT'):
        continue
    # Extraire les noms de colonnes
    parts = line.split(',')
    for part in parts:
        part = part.strip()
        if part and not part.startswith('--'):
            col = part.split('--')[0].strip()
            if col:
                columns.append(col)

print(f"Colonnes dans INSERT: {len(columns)}")

# Compter les %s dans VALUES
start_values = content.find('VALUES (', start_insert)
end_values = content.find('RETURNING id', start_values)
values_section = content[start_values:end_values]
placeholders = values_section.count('%s')
print(f"Placeholders %s dans VALUES: {placeholders}")

# Trouver params tuple (pour log_trade uniquement)
start_params = content.find('params = (', content.find('config_snapshot = json.dumps'))
end_params = content.find(')\n            \n            # Vérifier', start_params)
if end_params == -1:
    end_params = content.find(')\n            \n            result = self._execute_query', start_params)
params_section = content[start_params:end_params]

# Compter les paramètres réels
# On va compter chaque expression séparée par une virgule
param_count = 0
lines = params_section.split('\n')
for line in lines:
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('params'):
        continue
    # Compter les virgules qui séparent vraiment des paramètres
    # On compte les virgules en fin de ligne ou entre expressions
    if ',' in line:
        # Séparer par virgule mais attention aux appels de fonction
        # On va compter manuellement en cherchant les patterns
        # Chaque expression avant une virgule (sauf dans parenthèses) = 1 paramètre
        # Compter les virgules qui sont vraiment des séparateurs
        parts = re.split(r',(?![^()]*\))', line)  # Ne pas split sur virgules dans parenthèses
        for part in parts:
            part = part.strip()
            if part and not part.startswith('#'):
                param_count += 1
    elif line and not line.startswith('#'):
        param_count += 1

print(f"Paramètres comptés dans params tuple: {param_count}")
print(f"Différence: {param_count - placeholders}")

if param_count != placeholders:
    print(f"\n⚠️ PROBLÈME: {'Trop' if param_count > placeholders else 'Pas assez'} {abs(param_count - placeholders)} paramètres")
else:
    print("\n✅ Nombre de paramètres correspond")

