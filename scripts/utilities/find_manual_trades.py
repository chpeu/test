# Find manual trades columns
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from pathlib import Path

env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k.strip()] = v.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn)

# Colonnes trades
trades = pd.read_sql('SELECT * FROM trades LIMIT 5', engine)
print('Colonnes trades:')
for col in sorted(trades.columns):
    print(f'  - {col}')

# Chercher exit_type ou similaire
exit_cols = [c for c in trades.columns if 'exit' in c.lower() or 'close' in c.lower() or 'reason' in c.lower() or 'manual' in c.lower() or 'status' in c.lower()]
print(f'\nColonnes exit/close/reason/status: {exit_cols}')

# Analyser ces colonnes
if exit_cols:
    for col in exit_cols:
        vals = pd.read_sql(f'SELECT {col}, COUNT(*) as cnt FROM trades GROUP BY {col} ORDER BY cnt DESC LIMIT 20', engine)
        print(f'\n{col}:')
        print(vals)

# Aussi checker early_invalidation qui pourrait indiquer fermeture speciale
special_cols = ['early_invalidation', 'is_manual', 'forced_close', 'paper_trade']
for col in special_cols:
    if col in trades.columns:
        vals = pd.read_sql(f'SELECT {col}, COUNT(*) as cnt FROM trades GROUP BY {col} ORDER BY cnt DESC', engine)
        print(f'\n{col}:')
        print(vals)

engine.dispose()
