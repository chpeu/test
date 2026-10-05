#!/usr/bin/env python3
"""
Backfill ml_confidence : convertir les valeurs décimales (0-1) en pourcentage (0-100)
dans les tables trades et scan_logs.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

def _enable_utf8_stdout() -> None:
    if sys.platform != 'win32':
        return
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def _load_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv
        load_dotenv(root_dir / '.env')
    except Exception:
        pass


def _get_db_config() -> Dict[str, Any]:
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }


def _connect():
    import psycopg2
    return psycopg2.connect(**_get_db_config())


def _fetchone(conn, query: str, params: Optional[Tuple[Any, ...]] = None) -> Optional[Dict[str, Any]]:
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None


def _execute(conn, query: str, params: Optional[Tuple[Any, ...]] = None) -> int:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount


def backfill_trades(conn, dry_run: bool = True) -> int:
    """
    Convertir trades.ml_confidence de décimal (0-1) en pourcentage (0-100).
    Critère: ml_confidence <= 1.0
    """
    # Compter les lignes à mettre à jour
    count_query = """
        SELECT COUNT(*) as cnt 
        FROM trades 
        WHERE ml_confidence IS NOT NULL 
          AND ml_confidence <= 1.0
    """
    result = _fetchone(conn, count_query)
    count = result['cnt'] if result else 0
    
    print(f"\n[TRADES] Lignes avec ml_confidence <= 1.0 : {count}")
    
    if count == 0:
        print("[TRADES] Aucune ligne à convertir.")
        return 0
    
    if dry_run:
        print(f"[TRADES] Mode DRY-RUN : {count} lignes seraient converties.")
        # Afficher quelques exemples
        sample_query = """
            SELECT id, symbol, ml_confidence, ml_confidence * 100 as converted
            FROM trades 
            WHERE ml_confidence IS NOT NULL 
              AND ml_confidence <= 1.0
            ORDER BY timestamp_entry DESC
            LIMIT 5
        """
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sample_query)
            rows = cur.fetchall()
            print("\n  Exemples de conversion :")
            for r in rows:
                print(f"    ID={r['id']}, {r['symbol']}: {r['ml_confidence']} -> {r['converted']:.2f}%")
        return count
    
    # Exécuter la mise à jour
    update_query = """
        UPDATE trades 
        SET ml_confidence = ml_confidence * 100 
        WHERE ml_confidence IS NOT NULL 
          AND ml_confidence <= 1.0
    """
    rows_updated = _execute(conn, update_query)
    conn.commit()
    print(f"[TRADES] {rows_updated} lignes converties avec succès.")
    return rows_updated


def backfill_scan_logs(conn, dry_run: bool = True) -> int:
    """
    Convertir scan_logs.ml_confidence de décimal (0-1) en pourcentage (0-100).
    Critère: ml_confidence <= 1.0
    """
    # Compter les lignes à mettre à jour
    count_query = """
        SELECT COUNT(*) as cnt 
        FROM scan_logs 
        WHERE ml_confidence IS NOT NULL 
          AND ml_confidence <= 1.0
    """
    result = _fetchone(conn, count_query)
    count = result['cnt'] if result else 0
    
    print(f"\n[SCAN_LOGS] Lignes avec ml_confidence <= 1.0 : {count}")
    
    if count == 0:
        print("[SCAN_LOGS] Aucune ligne à convertir.")
        return 0
    
    if dry_run:
        print(f"[SCAN_LOGS] Mode DRY-RUN : {count} lignes seraient converties.")
        # Afficher quelques exemples
        sample_query = """
            SELECT id, symbol, ml_confidence, ml_confidence * 100 as converted
            FROM scan_logs 
            WHERE ml_confidence IS NOT NULL 
              AND ml_confidence <= 1.0
            ORDER BY timestamp DESC
            LIMIT 5
        """
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sample_query)
            rows = cur.fetchall()
            print("\n  Exemples de conversion :")
            for r in rows:
                print(f"    ID={r['id']}, {r['symbol']}: {r['ml_confidence']} -> {r['converted']:.2f}%")
        return count
    
    # Exécuter la mise à jour
    update_query = """
        UPDATE scan_logs 
        SET ml_confidence = ml_confidence * 100 
        WHERE ml_confidence IS NOT NULL 
          AND ml_confidence <= 1.0
    """
    rows_updated = _execute(conn, update_query)
    conn.commit()
    print(f"[SCAN_LOGS] {rows_updated} lignes converties avec succès.")
    return rows_updated


def main() -> int:
    _enable_utf8_stdout()
    _load_env()
    
    # Parser les arguments
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--execute':
        dry_run = False
    
    print("=" * 80)
    print("BACKFILL ML_CONFIDENCE : Conversion décimal -> pourcentage")
    print("=" * 80)
    
    if dry_run:
        print("\n⚠️  MODE DRY-RUN (simulation)")
        print("   Pour exécuter réellement, lancez avec : --execute")
    else:
        print("\n🔥 MODE EXECUTION REELLE")
    
    cfg = _get_db_config()
    print(f"\nConnexion: host={cfg['host']} port={cfg['port']} db={cfg['database']}")
    
    try:
        conn = _connect()
    except Exception as e:
        print(f"[ERREUR] Connexion échouée : {type(e).__name__}: {e}")
        return 1
    
    try:
        trades_count = backfill_trades(conn, dry_run=dry_run)
        scan_logs_count = backfill_scan_logs(conn, dry_run=dry_run)
        
        print("\n" + "=" * 80)
        print("RESUME")
        print("=" * 80)
        print(f"  trades       : {trades_count} lignes {'à convertir' if dry_run else 'converties'}")
        print(f"  scan_logs    : {scan_logs_count} lignes {'à convertir' if dry_run else 'converties'}")
        
        if dry_run:
            print("\n💡 Pour appliquer les changements :")
            print("   python scripts/backfill_ml_confidence.py --execute")
        else:
            print("\n✅ Backfill terminé avec succès.")
        
        return 0
        
    except Exception as e:
        print(f"[ERREUR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1
        
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
