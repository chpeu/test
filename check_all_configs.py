# -*- coding: utf-8 -*-
"""
Analyser toutes les colonnes de configuration dans trades
"""
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# Connexion
env_vars = {}
with open('.env') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k.strip()] = v.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn_str)

# Lister TOUTES les colonnes config_ dans trades
with engine.connect() as conn:
    cols = pd.read_sql(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'trades' AND column_name LIKE 'config_%' ORDER BY column_name"), conn)
print('=' * 70)
print('  COLONNES CONFIG_ DANS TABLE TRADES')
print('=' * 70)
for c in cols['column_name'].values:
    print(f'  - {c}')
print(f'\nTotal: {len(cols)} colonnes de config')

# Voir les valeurs uniques pour chaque colonne
print('\n' + '=' * 70)
print('  VALEURS UNIQUES PAR COLONNE')
print('=' * 70)

with engine.connect() as conn:
    for col in cols['column_name'].values:
        try:
            query = text(f"SELECT {col}, COUNT(*) as cnt FROM trades WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY cnt DESC LIMIT 5")
            uniq = pd.read_sql(query, conn)
            if len(uniq) > 0:
                vals = [f"{row[col]}({row['cnt']})" for _, row in uniq.iterrows()]
                print(f'{col}:')
                for v in vals:
                    print(f'    {v}')
            else:
                print(f'{col}: (vide)')
        except Exception as e:
            print(f'{col}: erreur - {e}')

# Compter combinaisons uniques
print('\n' + '=' * 70)
print('  COMBINAISONS DE CONFIGS UNIQUES')
print('=' * 70)

combo_query = text("""
SELECT 
    config_min_score_required as score,
    config_snr_threshold as snr,
    config_volume_multiplier as vol,
    config_use_confluence as confluence,
    COUNT(*) as cnt
FROM trades
WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
GROUP BY 
    config_min_score_required,
    config_snr_threshold,
    config_volume_multiplier,
    config_use_confluence
ORDER BY cnt DESC
LIMIT 15
""")

try:
    with engine.connect() as conn:
        combos = pd.read_sql(combo_query, conn)
    print(f"\nTop 15 combinaisons (score/snr/vol/confluence):\n")
    print(combos.to_string(index=False))
except Exception as e:
    print(f"Erreur: {e}")

engine.dispose()
