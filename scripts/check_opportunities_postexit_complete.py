"""Diagnostic complet des tables opportunities et post-exit"""
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
    
    print("=" * 80)
    print("DIAGNOSTIC COMPLET - OPPORTUNITIES & POST-EXIT")
    print("=" * 80)
    
    # ========== OPPORTUNITIES ==========
    print("\n" + "=" * 40)
    print("📊 TABLE OPPORTUNITIES")
    print("=" * 40)
    
    # Colonnes
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'opportunities' 
        ORDER BY ordinal_position
    """)
    cols_info = cur.fetchall()
    col_names = [c[0] for c in cols_info]
    print(f"\n📋 {len(col_names)} colonnes:")
    for c in cols_info:
        print(f"  - {c[0]}: {c[1]} {'(nullable)' if c[2]=='YES' else '(required)'}")
    
    # Stats
    cur.execute("SELECT COUNT(*) FROM opportunities")
    total = cur.fetchone()[0]
    print(f"\n📈 Total: {total} entrées")
    
    # Dernière entrée avec toutes les valeurs
    if total > 0:
        print("\n🔍 DERNIÈRE ENTRÉE (vérification remplissage):")
        cur.execute("SELECT * FROM opportunities ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        
        filled = 0
        null_cols = []
        for i, col in enumerate(col_names):
            val = row[i]
            if val is not None:
                filled += 1
                # Tronquer les valeurs longues
                val_str = str(val)[:60] + "..." if len(str(val)) > 60 else str(val)
                print(f"  ✅ {col}: {val_str}")
            else:
                null_cols.append(col)
                print(f"  ❌ {col}: NULL")
        
        print(f"\n📊 Remplissage: {filled}/{len(col_names)} colonnes ({100*filled/len(col_names):.1f}%)")
        if null_cols:
            print(f"⚠️ Colonnes NULL: {null_cols}")
        
        # Vérifier les colonnes importantes
        print("\n🔍 VÉRIFICATION COLONNES CRITIQUES (5 dernières):")
        cur.execute("""
            SELECT id, symbol, direction, setup_score, market_regime, 
                   session_id, conditions_matched, created_at
            FROM opportunities 
            ORDER BY created_at DESC LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"  {row[1]} | {row[2]} | score={row[3]} | regime={row[4]} | session={row[5] is not None} | conds={row[6] is not None}")
    
    # ========== POST-EXIT ANALYSIS ==========
    print("\n" + "=" * 40)
    print("📊 TABLE TRADE_POST_EXIT_ANALYSIS")
    print("=" * 40)
    
    # Colonnes
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_analysis' 
        ORDER BY ordinal_position
    """)
    cols_info = cur.fetchall()
    col_names_pea = [c[0] for c in cols_info]
    print(f"\n📋 {len(col_names_pea)} colonnes:")
    for c in cols_info:
        print(f"  - {c[0]}: {c[1]} {'(nullable)' if c[2]=='YES' else '(required)'}")
    
    # Stats
    cur.execute("SELECT COUNT(*) FROM trade_post_exit_analysis")
    total_pea = cur.fetchone()[0]
    print(f"\n📈 Total: {total_pea} entrées")
    
    if total_pea > 0:
        print("\n🔍 DERNIÈRE ENTRÉE POST-EXIT:")
        cur.execute("SELECT * FROM trade_post_exit_analysis ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        
        filled = 0
        null_cols = []
        for i, col in enumerate(col_names_pea):
            val = row[i]
            if val is not None:
                filled += 1
                val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                print(f"  ✅ {col}: {val_str}")
            else:
                null_cols.append(col)
        
        print(f"\n📊 Remplissage: {filled}/{len(col_names_pea)} colonnes")
        if null_cols:
            print(f"⚠️ Colonnes NULL: {null_cols}")
        
        # Jointure avec trades pour avoir le symbol
        print("\n🔗 POST-EXIT AVEC SYMBOL (via JOIN trades):")
        cur.execute("""
            SELECT p.trade_id, t.symbol, p.direction, p.exit_reason, 
                   p.realized_pnl_pct, p.post_exit_mfe_pct, p.regret_pct,
                   p.created_at
            FROM trade_post_exit_analysis p
            JOIN trades t ON t.id::text = p.trade_id::text
            ORDER BY p.created_at DESC
            LIMIT 5
        """)
        rows = cur.fetchall()
        if rows:
            for row in rows:
                print(f"  {row[1]} | {row[2]} | {row[3]} | pnl={row[4]}% | MFE={row[5]}% | regret={row[6]}%")
        else:
            print("  ❌ Aucun résultat (jointure échoue?)")
    
    # ========== POST-EXIT SAMPLES ==========
    print("\n" + "=" * 40)
    print("📊 TABLE TRADE_POST_EXIT_SAMPLES")
    print("=" * 40)
    
    cur.execute("SELECT COUNT(*) FROM trade_post_exit_samples")
    total_samples = cur.fetchone()[0]
    print(f"\n📈 Total: {total_samples} samples")
    
    if total_samples > 0:
        cur.execute("""
            SELECT trade_id, COUNT(*) as cnt, 
                   MIN(timestamp) as first_sample, MAX(timestamp) as last_sample
            FROM trade_post_exit_samples 
            GROUP BY trade_id
            ORDER BY MAX(timestamp) DESC
            LIMIT 3
        """)
        print("\n🔍 SAMPLES PAR TRADE:")
        for row in cur.fetchall():
            print(f"  trade_id={row[0][:8]}... | {row[1]} samples | {row[2]} → {row[3]}")
    
    # ========== PROBLÈME: PAS DE SYMBOL DANS POST-EXIT ==========
    print("\n" + "=" * 40)
    print("⚠️ ANALYSE: COLONNE SYMBOL MANQUANTE")
    print("=" * 40)
    
    # Vérifier si symbol existe dans post-exit
    cur.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_analysis' AND column_name = 'symbol'
    """)
    has_symbol = cur.fetchone()
    
    if has_symbol:
        print("✅ Colonne 'symbol' existe dans trade_post_exit_analysis")
    else:
        print("❌ Colonne 'symbol' N'EXISTE PAS dans trade_post_exit_analysis")
        print("   → Le symbol est récupérable via JOIN avec la table 'trades'")
        print("   → Alternative: Ajouter colonne symbol à la table")
    
    conn.close()
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
