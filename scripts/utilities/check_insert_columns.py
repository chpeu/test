#!/usr/bin/env python3
import re

with open('core/analytics_database.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Extraire la section INSERT INTO trades
insert_match = re.search(r'INSERT INTO trades \((.*?)\) VALUES', content, re.DOTALL)

if insert_match:
    cols_text = insert_match.group(1)
    # Supprimer les commentaires
    cols_text = re.sub(r'--[^\n]*', '', cols_text)
    # Split par virgule
    col_list = [c.strip() for c in cols_text.split(',') if c.strip()]
    
    print(f"Colonnes dans INSERT: {len(col_list)}")
    print("\nListe des colonnes:")
    for i, col in enumerate(col_list, 1):
        print(f"{i:3}. {col}")
else:
    print("Pattern INSERT non trouvé")
