#!/usr/bin/env python3
"""Script pour vérifier et corriger le nombre de paramètres dans log_trade"""

import re

# Lire le fichier
with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver la section INSERT INTO trades
start_insert = content.find('INSERT INTO trades (', content.find('def log_trade'))
end_insert = content.find('RETURNING id', start_insert)
insert_section = content[start_insert:end_insert]

# Compter les colonnes (en excluant les commentaires)
lines = insert_section.split('\n')
columns = []
for line in lines:
    line = line.strip()
    if not line or line.startswith('--') or line.startswith('INSERT') or line.startswith('VALUES'):
        continue
    # Extraire les noms de colonnes (avant la virgule ou la parenthèse fermante)
    parts = re.split(r'[,)]', line)
    for part in parts:
        part = part.strip()
        if part and not part.startswith('--'):
            # Extraire le nom de colonne (avant le commentaire éventuel)
            col_name = part.split('--')[0].strip()
            if col_name:
                columns.append(col_name)

print(f"Colonnes dans INSERT: {len(columns)}")
print(f"Premières colonnes: {columns[:10]}")
print(f"Dernières colonnes: {columns[-10:]}")

# Compter les %s dans VALUES
start_values = content.find('VALUES (', start_insert)
end_values = content.find('RETURNING id', start_values)
values_section = content[start_values:end_values]
placeholders = len(re.findall(r'%s', values_section))
print(f"\nPlaceholders %s dans VALUES: {placeholders}")

# Compter les paramètres dans le tuple
start_params = content.find('params = (', content.find('config_snapshot = json.dumps'))
end_params = content.find(')\n            \n            result = self._execute_query', start_params)
params_section = content[start_params:end_params]

# Compter les paramètres réels (en excluant les commentaires)
param_lines = params_section.split('\n')
param_count = 0
for line in param_lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Compter les expressions séparées par des virgules
    # Mais attention aux virgules dans les appels de fonction
    # On compte simplement les virgules en fin de ligne ou entre expressions
    if line.endswith(','):
        param_count += 1
    elif ',' in line and not line.startswith('#'):
        # Compter les virgules qui séparent des paramètres
        # (pas celles dans les appels de fonction)
        parts = line.split(',')
        param_count += len(parts)

print(f"Paramètres estimés dans params tuple: {param_count}")

# Différence
diff = placeholders - param_count
print(f"\nDifférence: {diff}")
if diff != 0:
    print(f"⚠️ PROBLÈME: {'Manque' if diff > 0 else 'Trop'} {abs(diff)} paramètres")

