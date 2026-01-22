#!/usr/bin/env python3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
Script de nettoyage du doublon trade_atr_metrics + application contrainte unique.

1. Merge des colonnes What-If de id=845 vers id=846 (sans écraser)
2. Suppression de la ligne id=845
3. Application de l'index UNIQUE sur trade_id
4. Vérification finale
"""

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def main():
    conn = get_connection()
    cur = conn.cursor()
    
    print("=" * 60)
    print("NETTOYAGE DOUBLON trade_atr_metrics")
    print("=" * 60)
    
    # 1. Vérifier le doublon
    print("\n[1/5] Vérification du doublon...")
    cur.execute("""
        SELECT id, trade_id, created_at, 
               pnl_if_calme_params, pnl_if_normal_params, pnl_if_volatile_params,
               optimal_regime_retrospective,
               pnl_if_no_be, pnl_if_no_trailing, pnl_if_fixed_tp
        FROM trade_atr_metrics 
        WHERE trade_id = 'ab089a78-7755-4425-b645-c7cf32571ba4'
        ORDER BY id
    """)
    rows = cur.fetchall()
    
    if len(rows) < 2:
        print(f"   ✅ Pas de doublon trouvé ({len(rows)} ligne(s)). Rien à faire.")
        if len(rows) == 0:
            print("   ⚠️  Aucune ligne pour ce trade_id.")
    else:
        print(f"   ⚠️  {len(rows)} lignes trouvées (doublon confirmé)")
        for r in rows:
            print(f"      id={r[0]}, created={r[2]}, calme={r[3]}, normal={r[4]}, volatile={r[5]}")
        
        # 2. Merge des colonnes What-If de 845 vers 846
        print("\n[2/5] Merge des colonnes What-If de id=845 vers id=846...")
        merge_sql = """
            UPDATE trade_atr_metrics AS dst
            SET
                pnl_if_calme_params = COALESCE(dst.pnl_if_calme_params, src.pnl_if_calme_params),
                pnl_if_normal_params = COALESCE(dst.pnl_if_normal_params, src.pnl_if_normal_params),
                pnl_if_volatile_params = COALESCE(dst.pnl_if_volatile_params, src.pnl_if_volatile_params),
                optimal_regime_retrospective = COALESCE(dst.optimal_regime_retrospective, src.optimal_regime_retrospective),
                pnl_if_no_be = COALESCE(dst.pnl_if_no_be, src.pnl_if_no_be),
                pnl_if_no_trailing = COALESCE(dst.pnl_if_no_trailing, src.pnl_if_no_trailing),
                pnl_if_fixed_tp = COALESCE(dst.pnl_if_fixed_tp, src.pnl_if_fixed_tp),
                pnl_if_wider_sl = COALESCE(dst.pnl_if_wider_sl, src.pnl_if_wider_sl),
                pnl_if_tighter_sl = COALESCE(dst.pnl_if_tighter_sl, src.pnl_if_tighter_sl),
                pnl_if_wider_trailing = COALESCE(dst.pnl_if_wider_trailing, src.pnl_if_wider_trailing),
                pnl_if_tighter_trailing = COALESCE(dst.pnl_if_tighter_trailing, src.pnl_if_tighter_trailing),
                sl_efficiency = COALESCE(dst.sl_efficiency, src.sl_efficiency),
                tp_efficiency = COALESCE(dst.tp_efficiency, src.tp_efficiency),
                be_efficiency = COALESCE(dst.be_efficiency, src.be_efficiency),
                trailing_capture_pct = COALESCE(dst.trailing_capture_pct, src.trailing_capture_pct),
                updated_at = NOW()
            FROM trade_atr_metrics AS src
            WHERE dst.id = 846 AND src.id = 845
        """
        cur.execute(merge_sql)
        print(f"   ✅ Merge effectué ({cur.rowcount} ligne mise à jour)")
        
        # 3. Supprimer la ligne 845
        print("\n[3/5] Suppression de la ligne id=845...")
        cur.execute("DELETE FROM trade_atr_metrics WHERE id = 845")
        print(f"   ✅ Suppression effectuée ({cur.rowcount} ligne supprimée)")
        
        conn.commit()
    
    # 4. Appliquer l'index UNIQUE
    print("\n[4/5] Application de l'index UNIQUE sur trade_id...")
    try:
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_atr_metrics_trade_id_unique
            ON trade_atr_metrics(trade_id)
        """)
        conn.commit()
        print("   ✅ Index UNIQUE créé/vérifié")
    except psycopg2.errors.UniqueViolation as e:
        conn.rollback()
        print(f"   ❌ Erreur: doublons restants empêchent la création de l'index")
        print(f"      {e}")
        return
    
    # 5. Vérification finale
    print("\n[5/5] Vérification finale...")
    cur.execute("""
        SELECT trade_id, COUNT(*) as cnt 
        FROM trade_atr_metrics 
        GROUP BY trade_id 
        HAVING COUNT(*) > 1
    """)
    duplicates = cur.fetchall()
    
    if duplicates:
        print(f"   ❌ {len(duplicates)} trade_id(s) en doublon restant(s):")
        for d in duplicates[:5]:
            print(f"      {d[0]}: {d[1]} lignes")
    else:
        print("   ✅ Aucun doublon - table propre!")
    
    # Stats finales
    cur.execute("SELECT COUNT(*) FROM trade_atr_metrics")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_atr_metrics")
    distinct = cur.fetchone()[0]
    print(f"\n   📊 Stats: {total} lignes, {distinct} trade_id distincts")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ NETTOYAGE TERMINÉ")
    print("=" * 60)

if __name__ == "__main__":
    main()
