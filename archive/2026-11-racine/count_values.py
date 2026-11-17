#!/usr/bin/env python3

with open('core/analytics_database.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Extraire les lignes 781-895
values = []
for i in range(780, 896):  # 781-1 car 0-indexed
    line = lines[i].strip()
    # Ignorer les commentaires purs
    if line.startswith('#') or not line:
        continue
    # Enlever le commentaire final si présent
    if '#' in line:
        line = line.split('#')[0].strip()
    # Enlever la virgule finale
    if line.endswith(','):
        line = line[:-1]
    if line and line != '(' and line != ')' and line != '))':
        values.append(line)

print(f"Nombre de valeurs: {len(values)}")
print("\nValeurs extraites:")
for i, v in enumerate(values, 1):
    print(f"{i:3}. {v}")
