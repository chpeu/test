#!/usr/bin/env python3
"""
Script de vérification pour les colonnes entry_atr_pct_used et entry_atr_blended.

Vérifie:
1. Présence des colonnes dans trade_atr_metrics
2. Taux de remplissage
3. Cohérence des calculs (blend + clamp)
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', '')
    )


def verify_columns_exist(cur):
    """Vérifie que les colonnes existent."""
    print("\n" + "="*60)
    print("1. VÉRIFICATION PRÉSENCE DES COLONNES")
    print("="*60)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'trade_atr_metrics' 
          AND column_name IN ('entry_atr_pct_used', 'entry_atr_blended')
        ORDER BY column_name
    """)
    
    columns = cur.fetchall()
    
    if len(columns) == 2:
        print("✅ Les 2 colonnes existent:")
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']}")
        return True
    else:
        print("❌ Colonnes manquantes!")
        print(f"   Trouvées: {[c['column_name'] for c in columns]}")
        print("   → Exécutez la migration: database/migrations/add_entry_atr_columns.sql")
        return False


def verify_fill_rates(cur):
    """Vérifie les taux de remplissage."""
    print("\n" + "="*60)
    print("2. TAUX DE REMPLISSAGE")
    print("="*60)
    
    cur.execute("""
        SELECT 
            COUNT(*) AS total,
            COUNT(entry_atr_pct_used) AS filled_pct_used,
            COUNT(entry_atr_blended) AS filled_blended,
            COUNT(entry_atr_1m) AS has_atr_1m
        FROM trade_atr_metrics
    """)
    
    stats = cur.fetchone()
    total = stats['total']
    
    if total == 0:
        print("⚠️ Aucune métrique ATR dans la table")
        return True
    
    pct_used_rate = (stats['filled_pct_used'] / total) * 100
    blended_rate = (stats['filled_blended'] / total) * 100
    has_atr_rate = (stats['has_atr_1m'] / total) * 100
    
    print(f"   Total métriques:        {total}")
    print(f"   entry_atr_pct_used:     {stats['filled_pct_used']:>6} ({pct_used_rate:.1f}%)")
    print(f"   entry_atr_blended:      {stats['filled_blended']:>6} ({blended_rate:.1f}%)")
    print(f"   entry_atr_1m (source):  {stats['has_atr_1m']:>6} ({has_atr_rate:.1f}%)")
    
    # On s'attend à ce que les nouvelles colonnes soient remplies pour toutes les lignes qui ont entry_atr_1m
    expected_fill = stats['has_atr_1m']
    if stats['filled_pct_used'] < expected_fill or stats['filled_blended'] < expected_fill:
        missing = expected_fill - min(stats['filled_pct_used'], stats['filled_blended'])
        print(f"\n⚠️ {missing} métriques pourraient être mises à jour")
        print("   → Exécutez: python scripts/update_atr_metrics_columns.py")
        return False
    
    print("\n✅ Taux de remplissage OK")
    return True


def verify_blend_consistency(cur):
    """Vérifie la cohérence du calcul de blend."""
    print("\n" + "="*60)
    print("3. COHÉRENCE DU BLEND (0.7*ATR1m + 0.3*ATR5m)")
    print("="*60)
    
    cur.execute("""
        SELECT 
            m.id,
            m.entry_atr_1m,
            m.entry_atr_5m,
            m.entry_atr_blended,
            CASE 
                WHEN m.entry_atr_5m IS NOT NULL AND m.entry_atr_5m > 0 
                THEN 0.7 * m.entry_atr_1m + 0.3 * m.entry_atr_5m
                ELSE m.entry_atr_1m
            END AS expected_blended,
            ABS(m.entry_atr_blended - CASE 
                WHEN m.entry_atr_5m IS NOT NULL AND m.entry_atr_5m > 0 
                THEN 0.7 * m.entry_atr_1m + 0.3 * m.entry_atr_5m
                ELSE m.entry_atr_1m
            END) AS diff
        FROM trade_atr_metrics m
        WHERE m.entry_atr_blended IS NOT NULL
          AND m.entry_atr_1m IS NOT NULL
        ORDER BY diff DESC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("⚠️ Aucune donnée à vérifier")
        return True
    
    # Vérifier que les différences sont négligeables (erreurs d'arrondi)
    max_diff = max(r['diff'] for r in rows) if rows else 0
    
    if max_diff < 0.0001:
        print(f"✅ Calcul du blend cohérent (diff max: {max_diff:.8f})")
        return True
    else:
        print(f"❌ Incohérences détectées (diff max: {max_diff:.6f})")
        print("\nTop 5 écarts:")
        for r in rows[:5]:
            print(f"   ID {r['id']}: blended={r['entry_atr_blended']:.6f}, "
                  f"expected={r['expected_blended']:.6f}, diff={r['diff']:.6f}")
        return False


def verify_clamp_consistency(cur):
    """Vérifie la cohérence du clamp entre atr_min et atr_max."""
    print("\n" + "="*60)
    print("4. COHÉRENCE DU CLAMP (atr_min ≤ pct_used ≤ atr_max)")
    print("="*60)
    
    cur.execute("""
        SELECT 
            m.id,
            m.entry_atr_pct_used,
            m.entry_atr_blended,
            t.entry_price,
            COALESCE((t.config_snapshot->>'atr_min')::float, 0.10) AS atr_min,
            COALESCE((t.config_snapshot->>'atr_max')::float, 1.0) AS atr_max,
            (m.entry_atr_blended / t.entry_price) * 100 AS raw_pct
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE m.entry_atr_pct_used IS NOT NULL
          AND m.entry_atr_blended IS NOT NULL
          AND t.entry_price > 0
        ORDER BY m.created_at DESC
        LIMIT 100
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("⚠️ Aucune donnée à vérifier")
        return True
    
    violations = []
    for r in rows:
        pct_used = r['entry_atr_pct_used']
        atr_min = r['atr_min']
        atr_max = r['atr_max']
        
        # Tolérance pour les erreurs d'arrondi
        if pct_used < atr_min - 0.001 or pct_used > atr_max + 0.001:
            violations.append(r)
    
    if not violations:
        print(f"✅ Tous les clamps sont valides ({len(rows)} vérifiés)")
        
        # Afficher quelques exemples
        print("\nExemples de clamp:")
        for r in rows[:3]:
            status = ""
            if r['raw_pct'] < r['atr_min']:
                status = f"(clampé UP de {r['raw_pct']:.3f}%)"
            elif r['raw_pct'] > r['atr_max']:
                status = f"(clampé DOWN de {r['raw_pct']:.3f}%)"
            print(f"   raw={r['raw_pct']:.4f}% → used={r['entry_atr_pct_used']:.4f}% "
                  f"[min={r['atr_min']}, max={r['atr_max']}] {status}")
        return True
    else:
        print(f"❌ {len(violations)} violations de clamp détectées")
        for v in violations[:5]:
            print(f"   ID {v['id']}: pct_used={v['entry_atr_pct_used']:.4f}%, "
                  f"min={v['atr_min']}, max={v['atr_max']}")
        return False


def show_sample_data(cur):
    """Affiche un échantillon des données."""
    print("\n" + "="*60)
    print("5. ÉCHANTILLON DE DONNÉES (10 derniers trades ATR)")
    print("="*60)
    
    cur.execute("""
        SELECT 
            t.symbol,
            m.entry_atr_1m,
            m.entry_atr_5m,
            m.entry_atr_blended,
            m.entry_atr_pct_used,
            m.created_at
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE t.tp_sl_mode = 'ATR'
        ORDER BY m.created_at DESC
        LIMIT 10
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("⚠️ Aucun trade ATR récent")
        return
    
    print(f"{'Symbol':<12} {'ATR 1m':>10} {'ATR 5m':>10} {'Blended':>10} {'% Used':>8}")
    print("-" * 55)
    
    for r in rows:
        atr1m = f"{r['entry_atr_1m']:.4f}" if r['entry_atr_1m'] else "N/A"
        atr5m = f"{r['entry_atr_5m']:.4f}" if r['entry_atr_5m'] else "N/A"
        blended = f"{r['entry_atr_blended']:.4f}" if r['entry_atr_blended'] else "N/A"
        pct_used = f"{r['entry_atr_pct_used']:.3f}%" if r['entry_atr_pct_used'] else "N/A"
        
        print(f"{r['symbol']:<12} {atr1m:>10} {atr5m:>10} {blended:>10} {pct_used:>8}")


def main():
    print("="*60)
    print("VÉRIFICATION entry_atr_pct_used & entry_atr_blended")
    print("="*60)
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("✅ Connexion PostgreSQL OK")
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        return 1
    
    all_ok = True
    
    # 1. Vérifier présence colonnes
    if not verify_columns_exist(cur):
        print("\n⚠️ Migration requise avant de continuer")
        conn.close()
        return 1
    
    # 2. Vérifier taux de remplissage
    all_ok = verify_fill_rates(cur) and all_ok
    
    # 3. Vérifier cohérence blend
    all_ok = verify_blend_consistency(cur) and all_ok
    
    # 4. Vérifier cohérence clamp
    all_ok = verify_clamp_consistency(cur) and all_ok
    
    # 5. Échantillon
    show_sample_data(cur)
    
    conn.close()
    
    print("\n" + "="*60)
    if all_ok:
        print("✅ TOUTES LES VÉRIFICATIONS OK")
    else:
        print("⚠️ CERTAINES VÉRIFICATIONS ONT ÉCHOUÉ")
    print("="*60)
    
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
