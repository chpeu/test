"""
Execute ATR metrics migration
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    print("Connexion a PostgreSQL...")
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    print("Execution de la migration...")
    with open('database/migrations/add_trade_atr_metrics.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    cur.execute(sql)
    conn.commit()
    
    # Verify
    cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'trade_atr_metrics'")
    col_count = cur.fetchone()[0]
    print(f"Table trade_atr_metrics creee avec {col_count} colonnes")
    
    # List columns
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics'
        ORDER BY ordinal_position
        LIMIT 15
    """)
    print("\nPremieres colonnes:")
    for row in cur.fetchall():
        print(f"  - {row[0]}: {row[1]}")
    
    cur.close()
    conn.close()
    print("\nMigration terminee!")

if __name__ == "__main__":
    run_migration()
