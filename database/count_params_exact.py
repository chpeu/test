#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comptage exact des paramètres dans log_trade"""

import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver la section params pour log_trade uniquement
start = content.find('params = (', content.find('config_snapshot = json.dumps'))
end = content.find(')\n            \n            # Vérifier', start)
if end == -1:
    end = content.find(')\n            \n            result = self._execute_query', start)
params_section = content[start:end]

# Compter les paramètres en analysant chaque ligne
param_count = 0
lines = params_section.split('\n')
for i, line in enumerate(lines):
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('params'):
        continue
    
    # Compter les virgules qui séparent vraiment des paramètres
    # On compte les virgules en fin de ligne ou entre expressions
    if ',' in line:
        # Séparer par virgule mais attention aux appels de fonction
        # On va compter manuellement en cherchant les patterns
        # Chaque expression avant une virgule = 1 paramètre
        parts = line.split(',')
        for part in parts:
            part = part.strip()
            if part and not part.startswith('#'):
                param_count += 1
                # Afficher les 20 premiers paramètres pour debug
                if param_count <= 20:
                    print(f"Param {param_count}: {part}")
    elif line and not line.startswith('#'):
        param_count += 1
        if param_count <= 20:
            print(f"Param {param_count}: {line}")

print(f"\nTotal paramètres comptés: {param_count}")

# Compter les placeholders
start_v = content.find('VALUES (', content.find('INSERT INTO trades'))
end_v = content.find('RETURNING id', start_v)
values = content[start_v:end_v]
placeholders = values.count('%s')
print(f"Placeholders: {placeholders}")
print(f"Différence: {param_count - placeholders}")
