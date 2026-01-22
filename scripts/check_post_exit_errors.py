#!/usr/bin/env python3
"""
Script pour vérifier les erreurs PostExit détaillées
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    """Créer connexion PostgreSQL"""
    password = os.getenv('POSTGRES_PASSWORD', 'Lipton2019!')
    conn_str = f"host=localhost port=5432 dbname=trade_cursor_ml user=postgres password={password}"
    return psycopg2.connect(conn_str)

def check_post_exit_errors():
    """Vérifier les erreurs PostExit"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT timestamp, error_message, error_stack
        FROM scan_errors
        WHERE error_message LIKE '%PostExit%'
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    rows = cur.fetchall()
    
    print(f"\n{'='*80}")
    print(f"ERREURS POST-EXIT: {len(rows)}")
    print(f"{'='*80}")
    
    for ts, msg, stack in rows:
        print(f"\n⏰ {ts}")
        print(f"📝 {msg}")
        if stack:
            print(f"\n📚 Stack trace:")
            print(stack[:1000])
            print("..." if len(stack) > 1000 else "")
        print("-" * 80)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_post_exit_errors()
