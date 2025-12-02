#!/usr/bin/env python3
import re

with open('core/analytics_database.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Trouver la ligne de départ des valeurs
start_idx = None
for i, line in enumerate(lines):
    if "''', (" in line and i > 740:
        start_idx = i + 1
        break

if not start_idx:
    print("Ligne de départ non trouvée")
    exit(1)

# Compter les lignes avec trade.get(...) ou des valeurs
value_count = 0
value_lines = []

for i in range(start_idx, len(lines)):
    line = lines[i].strip()
    
    # Arrêter si on atteint la fermeture du tuple
    if line.startswith('))'):
        break
    
    # Ignorer les lignes de commentaires
    if line.startswith('#') or line.startswith('//'):
        continue
    
    # Compter les virgules (chaque virgule = une valeur)
    if ',' in line:
        # Extraire la partie avant le commentaire
        code_part = line.split('#')[0].split('//')[0]
        # Compter les virgules
        commas = code_part.count(',')
        value_count += commas
        value_lines.append((i+1, line[:80]))

# Ajouter 1 pour la dernière valeur sans virgule
value_count += 1

print(f"Valeurs dans VALUES tuple: {value_count}")
print(f"\nPremières lignes de valeurs:")
for line_no, content in value_lines[:10]:
    print(f"Ligne {line_no}: {content}")

print(f"\nDernières lignes de valeurs:")
for line_no, content in value_lines[-10:]:
    print(f"Ligne {line_no}: {content}")
