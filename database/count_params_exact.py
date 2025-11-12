#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Script pour compter exactement les paramètres"""

import re
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver VALUES
start = content.find('VALUES (', content.find('INSERT INTO trades'))
end = content.find('RETURNING id', start)
values = content[start:end]
placeholders = values.count('%s')
print(f"Placeholders %s: {placeholders}")

# Trouver params tuple
start_p = content.find('params = (', content.find('config_snapshot = json.dumps'))
end_p = content.find(')\n            \n            result = self._execute_query', start_p)
params_section = content[start_p:end_p]

# Compter les paramètres réels (chaque ligne avec une virgule = au moins 1 paramètre)
lines = params_section.split('\n')
param_count = 0
for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Compter les virgules qui séparent des paramètres
    # Attention: ne pas compter les virgules dans les appels de fonction
    # On compte les virgules en fin de ligne ou entre expressions simples
    if ',' in line:
        # Séparer par virgule mais attention aux appels de fonction
        # Compter les virgules qui sont vraiment des séparateurs de paramètres
        # (pas celles dans .get('key', default))
        parts = re.split(r',(?![^()]*\))', line)  # Ne pas split sur virgules dans parenthèses
        param_count += len([p for p in parts if p.strip() and not p.strip().startswith('#')])
    elif line and not line.startswith('#'):
        param_count += 1

print(f"Paramètres comptés: {param_count}")
print(f"Différence: {placeholders - param_count}")

# Afficher les 20 premières lignes de params pour debug
print("\nPremières lignes de params:")
for i, line in enumerate(lines[:20]):
    if line.strip() and not line.strip().startswith('#'):
        print(f"  {i}: {line.strip()}")

