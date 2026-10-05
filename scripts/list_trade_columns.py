"""Liste les colonnes pertinentes de la table trades"""
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

load_dotenv()
password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trades' 
        AND (column_name LIKE '%pnl%' OR column_name LIKE '%fee%' 
             OR column_name LIKE '%price%' OR column_name LIKE '%atr%'
             OR column_name LIKE '%size%' OR column_name LIKE '%leverage%')
        ORDER BY column_name
    """))
    print("Colonnes PnL/Fee/Price/ATR:")
    for r in result.fetchall():
        print(f"  {r[0]}")
