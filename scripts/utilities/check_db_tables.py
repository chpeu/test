# Check database tables
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from pathlib import Path

env_path = Path('.env')
env_vars = {}
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
user = env_vars.get('POSTGRES_USER', 'postgres')
host = env_vars.get('POSTGRES_HOST', 'localhost')
port = env_vars.get('POSTGRES_PORT', '5432')
database = env_vars.get('POSTGRES_DB', 'trade_cursor_ml')

conn_str = f"postgresql://{user}:{password}@{host}:{port}/{database}"
engine = create_engine(conn_str)

# Lister les tables
tables = pd.read_sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'", engine)
print('Tables:', tables['table_name'].tolist())

# Chercher les colonnes avec pnl/profit dans toutes les tables
for table in tables['table_name']:
    cols = pd.read_sql(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'", engine)
    profit_cols = [c for c in cols['column_name'] if 'pnl' in c.lower() or 'profit' in c.lower()]
    if profit_cols:
        print(f'{table}: {profit_cols}')
        # Compter les lignes avec valeur
        for col in profit_cols:
            try:
                count = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table} WHERE {col} IS NOT NULL", engine)
                print(f"  {col}: {count['cnt'].iloc[0]} rows with data")
            except:
                pass

engine.dispose()
