"""Diagnostic des tables post-exit et opportunities"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2

def main():
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=5432,
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    cur = conn.cursor()
    
    print("=" * 60)
    print("DIAGNOSTIC TABLES POST-EXIT & OPPORTUNITIES")
    print("=" * 60)
    
    # 1. Tables post-exit
    print("\n📊 TABLES POST-EXIT:")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '%post_exit%'")
    tables = [r[0] for r in cur.fetchall()]
    if tables:
        for t in tables:
            print(f"  ✅ {t}")
    else:
        print("  ❌ Aucune table post-exit trouvée!")
    
    # 2. Structure trade_post_exit_analysis
    print("\n📋 STRUCTURE trade_post_exit_analysis:")
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_analysis' 
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    if cols:
        for c in cols:
            print(f"  - {c[0]}: {c[1]} {'(nullable)' if c[2] == 'YES' else ''}")
    else:
        print("  ❌ Table non trouvée!")
    
    # 3. Structure trade_post_exit_samples
    print("\n📋 STRUCTURE trade_post_exit_samples:")
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_samples' 
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    if cols:
        for c in cols:
            print(f"  - {c[0]}: {c[1]} {'(nullable)' if c[2] == 'YES' else ''}")
    else:
        print("  ❌ Table non trouvée!")
    
    # 4. Structure opportunities
    print("\n📋 STRUCTURE opportunities:")
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'opportunities' 
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    if cols:
        for c in cols:
            print(f"  - {c[0]}: {c[1]} {'(nullable)' if c[2] == 'YES' else ''}")
    else:
        print("  ❌ Table non trouvée!")
    
    # 5. Stats
    print("\n📈 STATISTIQUES:")
    
    try:
        cur.execute("SELECT COUNT(*) FROM trade_post_exit_analysis")
        count = cur.fetchone()[0]
        print(f"  - trade_post_exit_analysis: {count} lignes")
        
        if count > 0:
            cur.execute("SELECT trade_id, exit_reason, realized_pnl_pct, direction FROM trade_post_exit_analysis ORDER BY created_at DESC LIMIT 3")
            print("    Dernières entrées:")
            for row in cur.fetchall():
                print(f"      trade_id={row[0]}, reason={row[1]}, pnl={row[2]}%, dir={row[3]}")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur trade_post_exit_analysis: {e}")
    
    try:
        cur.execute("SELECT COUNT(*) FROM trade_post_exit_samples")
        count = cur.fetchone()[0]
        print(f"  - trade_post_exit_samples: {count} lignes")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur trade_post_exit_samples: {e}")
    
    try:
        cur.execute("SELECT COUNT(*) FROM opportunities")
        count = cur.fetchone()[0]
        print(f"  - opportunities: {count} lignes")
        
        if count > 0:
            cur.execute("SELECT id, symbol, direction, created_at FROM opportunities ORDER BY created_at DESC LIMIT 3")
            print("    Dernières entrées:")
            for row in cur.fetchall():
                print(f"      id={row[0]}, symbol={row[1]}, direction={row[2]}, date={row[3]}")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur opportunities: {e}")
    
    # 6. Vérifier les trades avec opportunity_id
    print("\n🔗 LIEN TRADES <-> OPPORTUNITIES:")
    try:
        cur.execute("SELECT COUNT(*) FROM trades WHERE opportunity_id IS NOT NULL")
        linked = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM trades")
        total = cur.fetchone()[0]
        print(f"  - Trades avec opportunity_id: {linked}/{total}")
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
    
    # 7. Vérifier les trades avec post-exit
    print("\n🔗 LIEN TRADES <-> POST-EXIT:")
    try:
        cur.execute("""
            SELECT COUNT(*) FROM trades t 
            JOIN trade_post_exit_analysis p ON t.id::text = p.trade_id::text
        """)
        linked = cur.fetchone()[0]
        print(f"  - Trades avec post-exit analysis: {linked}/{total}")
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
    
    # 8. Vérifier structure trades et derniers trades
    print("\n📋 COLONNES TRADES (first 15):")
    try:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trades' ORDER BY ordinal_position LIMIT 15
        """)
        cols = [r[0] for r in cur.fetchall()]
        print(f"  {cols}")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur: {e}")
    
    print("\n📅 DERNIERS TRADES:")
    try:
        cur.execute("""
            SELECT id, symbol, exit_reason, created_at 
            FROM trades 
            WHERE exit_reason IS NOT NULL 
            ORDER BY created_at DESC LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  - {row[0]} | {row[1]} | {row[2]} | {row[3]}")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur: {e}")
    
    # 9. Trades récents sans post-exit
    print("\n⚠️ TRADES RÉCENTS SANS POST-EXIT:")
    try:
        cur.execute("""
            SELECT t.id, t.symbol, t.exit_reason, t.created_at
            FROM trades t
            LEFT JOIN trade_post_exit_analysis p ON t.id::text = p.trade_id::text
            WHERE t.exit_reason IS NOT NULL AND p.id IS NULL
            ORDER BY t.created_at DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  - {row[0]} | {row[1]} | {row[2]} | {row[3]}")
    except Exception as e:
        conn.rollback()
        print(f"  ❌ Erreur: {e}")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
