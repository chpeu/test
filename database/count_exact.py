#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage exact des colonnes et paramètres"""

import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver INSERT INTO trades
start = content.find('INSERT INTO trades (', content.find('def log_trade'))
end = content.find(')', start)
insert_cols = content[start:end]

# Extraire les colonnes (en excluant les commentaires)
lines = insert_cols.split('\n')
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
start_v = content.find('VALUES (', start)
end_v = content.find('RETURNING id', start_v)
values = content[start_v:end_v]
placeholders = values.count('%s')
print(f"Placeholders %s: {placeholders}")

# Compter les paramètres dans le tuple params (pour log_trade uniquement)
start_p = content.find('params = (', content.find('config_snapshot = json.dumps'))
end_p = content.find(')\n            \n            # Vérifier le nombre', start_p)
if end_p == -1:
    end_p = content.find(')\n            \n            result = self._execute_query', start_p)
params_section = content[start_p:end_p]

# Compter les paramètres réels
# Chaque ligne avec une virgule = au moins 1 paramètre
# Compter les expressions séparées par des virgules
param_count = 0
lines = params_section.split('\n')
for line in lines:
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('params'):
        continue
    # Compter les virgules qui séparent vraiment des paramètres
    # (pas celles dans les appels de fonction)
    # On compte simplement les virgules en fin de ligne ou entre expressions
    if ',' in line:
        # Séparer par virgule mais attention aux appels de fonction
        # On va compter manuellement en cherchant les patterns
        # Chaque expression avant une virgule (sauf dans parenthèses) = 1 paramètre
        parts = re.split(r',(?![^()]*\))', line)
        for part in parts:
            part = part.strip()
            if part and not part.startswith('#'):
                param_count += 1
    elif line and not line.startswith('#'):
        param_count += 1

print(f"Paramètres comptés: {param_count}")
print(f"Différence: {param_count - placeholders}")

# Afficher les colonnes pour vérification
print(f"\nPremières 10 colonnes: {columns[:10]}")
print(f"Dernières 10 colonnes: {columns[-10:]}")

