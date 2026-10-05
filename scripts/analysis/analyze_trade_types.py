# Analyze trade types to find manual/paper trades
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus

env_vars = {}
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env_vars[k.strip()] = v.strip()
except FileNotFoundError:
    print("Fichier .env non trouvé. Ce script nécessite un fichier .env avec les variables PostgreSQL.")
    exit(0)  # Exit gracefully for test environment

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
try:
    engine = create_engine(conn)
    # Test connection
    with engine.connect() as test_conn:
        pass
except Exception as e:
    print(f"Impossible de se connecter à PostgreSQL: {e}")
    print("Ce script nécessite une base de données PostgreSQL active.")
    exit(0)  # Exit gracefully for test environment

# Charger trades
trades = pd.read_sql('SELECT * FROM trades', engine)
print(f"Total trades: {len(trades)}")

# Chercher colonnes paper/live/manual
for col in trades.columns:
    if any(x in col.lower() for x in ['paper', 'live', 'manual', 'mode', 'type', 'execution']):
        print(f"\n{col}:")
        print(trades[col].value_counts().head(10))

# Analyser par presence de exit_api_response (trades LIVE fermes ont une reponse)
if 'exit_api_response' in trades.columns:
    has_exit_api = trades['exit_api_response'].notna()
    print(f"\n--- Trades avec exit_api_response ---")
    print(f"Avec reponse API (LIVE ferme): {has_exit_api.sum()}")
    print(f"Sans reponse API (paper/non ferme): {(~has_exit_api).sum()}")

# Analyser par presence de entry_api_response
if 'entry_api_response' in trades.columns:
    has_entry_api = trades['entry_api_response'].notna()
    print(f"\n--- Trades avec entry_api_response ---")
    print(f"Avec reponse API entree: {has_entry_api.sum()}")
    print(f"Sans reponse API entree: {(~has_entry_api).sum()}")

# Analyser exit_fee_usdt (trades LIVE ont des frais)
if 'exit_fee_usdt' in trades.columns:
    has_exit_fee = trades['exit_fee_usdt'].notna() & (trades['exit_fee_usdt'] != 0)
    print(f"\n--- Trades avec exit_fee_usdt ---")
    print(f"Avec frais sortie: {has_exit_fee.sum()}")
    print(f"Sans frais sortie: {(~has_exit_fee).sum()}")

# Chercher execution_mode ou similaire
exec_cols = [c for c in trades.columns if 'exec' in c.lower() or 'mode' in c.lower()]
print(f"\n--- Colonnes execution/mode: {exec_cols}")
for col in exec_cols:
    print(f"\n{col}:")
    print(trades[col].value_counts())

# Afficher quelques exemples
print("\n--- Exemples de trades ---")
sample_cols = ['id', 'symbol', 'direction', 'pnl_pct', 'exit_api_response', 'exit_fee_usdt']
sample_cols = [c for c in sample_cols if c in trades.columns]
print(trades[sample_cols].head(10))

engine.dispose()
