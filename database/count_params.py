#!/usr/bin/env python3
"""Script pour compter les paramètres dans la requête SQL"""

import re

# Lire le fichier
with open('core/postgresql_datalogger.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Trouver la section VALUES
start = content.find('VALUES (', content.find('INSERT INTO trades'))
end = content.find('RETURNING id', start)
values_section = content[start:end]

# Compter les %s
placeholders = len(re.findall(r'%s', values_section))
print(f"Placeholders %s dans VALUES: {placeholders}")

# Trouver la section params
start_params = content.find('params = (', content.find('config_snapshot = json.dumps'))
end_params = content.find(')\n            \n            result = self._execute_query', start_params)
params_section = content[start_params:end_params]

# Compter les paramètres (en comptant les virgules et les lignes)
lines = params_section.split('\n')
param_count = 0
for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Compter les virgules dans chaque ligne
    commas = line.count(',')
    param_count += commas
    # Si la ligne se termine par une virgule, c'est qu'il y a un paramètre après
    if line.endswith(','):
        param_count += 1
    # Si la ligne ne se termine pas par une virgule mais contient des virgules, ajouter 1
    elif commas > 0 and not line.endswith(','):
        param_count += 1

print(f"Paramètres estimés dans params tuple: {param_count}")

# Afficher la différence
diff = placeholders - param_count
if diff > 0:
    print(f"⚠️ Il manque {diff} paramètres")
elif diff < 0:
    print(f"⚠️ Il y a {abs(diff)} paramètres en trop")
else:
    print("✅ Nombre de paramètres correspond")

