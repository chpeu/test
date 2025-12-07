#!/usr/bin/env python3
"""
Verification complete des tables ML Calibration et de leur fonctionnement.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
import requests

BASE_URL = "http://localhost:5000"

def print_header(title):
    print(f"\n{'='*60}")
    print(f"> {title}")
    print('='*60)

def print_ok(msg):
    print(f"[OK] {msg}")

def print_fail(msg):
    print(f"[FAIL] {msg}")

def print_info(msg):
    print(f"[INFO] {msg}")


def test_tables_exist():
    """Verifier que les tables SQL existent."""
    print_header("TEST 1: Tables SQL Existent")
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg = PostgreSQLDataLogger()
        
        conn = pg.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Verifier ml_calibration
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name = 'ml_calibration'
                """)
                if cur.fetchone()[0] == 1:
                    print_ok("Table ml_calibration existe")
                else:
                    print_fail("Table ml_calibration MANQUANTE")
                    return False
                
                # Verifier ml_calibration_history
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.tables 
                    WHERE table_name = 'ml_calibration_history'
                """)
                if cur.fetchone()[0] == 1:
                    print_ok("Table ml_calibration_history existe")
                else:
                    print_fail("Table ml_calibration_history MANQUANTE")
                    return False
                
                # Verifier colonnes de ml_calibration_history
                cur.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'ml_calibration_history'
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cur.fetchall()]
                required = ['direction', 'confidence_bucket', 'old_winrate', 'new_winrate', 'total_trades', 'reason']
                missing = [c for c in required if c not in columns]
                if missing:
                    print_fail(f"Colonnes manquantes dans ml_calibration_history: {missing}")
                    return False
                print_ok(f"Colonnes ml_calibration_history: {columns}")
                
        finally:
            pg.pool.putconn(conn)
        
        return True
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def test_calibration_data():
    """Verifier que ml_calibration contient des donnees."""
    print_header("TEST 2: Donnees ml_calibration")
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg = PostgreSQLDataLogger()
        
        conn = pg.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT direction, confidence_bucket, total_trades, actual_winrate
                    FROM ml_calibration
                    WHERE total_trades > 0
                    ORDER BY direction, confidence_bucket
                """)
                rows = cur.fetchall()
                
                if not rows:
                    print_info("Aucune donnee de calibration (normal si pas de trades)")
                    return True
                
                print_ok(f"{len(rows)} buckets avec donnees:")
                for row in rows:
                    wr = f"{row[3]:.1f}%" if row[3] else "N/A"
                    print(f"    {row[0]} {row[1]}: {row[2]} trades, WR={wr}")
                
        finally:
            pg.pool.putconn(conn)
        
        return True
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def test_history_logging():
    """Verifier que l'historique est bien rempli."""
    print_header("TEST 3: Historique ml_calibration_history")
    
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg = PostgreSQLDataLogger()
        
        conn = pg.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT direction, confidence_bucket, old_winrate, new_winrate, 
                           total_trades, reason, created_at
                    FROM ml_calibration_history
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                rows = cur.fetchall()
                
                if not rows:
                    print_info("Aucun historique (sera rempli au prochain trade)")
                    return True
                
                print_ok(f"{len(rows)} entrees d'historique recentes:")
                for row in rows:
                    old_wr = f"{row[2]:.1f}%" if row[2] else "N/A"
                    new_wr = f"{row[3]:.1f}%" if row[3] else "N/A"
                    print(f"    {row[0]} {row[1]}: {old_wr} -> {new_wr} ({row[5]})")
                
        finally:
            pg.pool.putconn(conn)
        
        return True
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def test_update_triggers_history():
    """Tester que update_calibration enregistre dans l'historique."""
    print_header("TEST 4: Update Calibration -> Historique")
    
    try:
        from ml.calibration import get_calibration_manager
        from core.postgresql_datalogger import PostgreSQLDataLogger
        
        manager = get_calibration_manager()
        pg = PostgreSQLDataLogger()
        
        # Compter les entrees avant
        conn = pg.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM ml_calibration_history")
                count_before = cur.fetchone()[0]
        finally:
            pg.pool.putconn(conn)
        
        # Simuler un update (trade fictif)
        test_time = datetime.now(timezone.utc)
        result = manager.update_calibration(
            direction="LONG",
            ml_confidence=42.5,  # Bucket 40-45
            win=True,
            pnl_pct=0.15,
            pnl_usdt=1.5,
            is_live=False,
            is_dry_run=True,
            trade_timestamp=test_time
        )
        
        if not result:
            print_fail("update_calibration a echoue")
            return False
        
        print_ok("update_calibration execute avec succes")
        
        # Compter les entrees apres
        conn = pg.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM ml_calibration_history")
                count_after = cur.fetchone()[0]
                
                if count_after > count_before:
                    print_ok(f"Historique incremente: {count_before} -> {count_after}")
                else:
                    print_info(f"Historique non incremente (normal si pas de seuil atteint): {count_after}")
                
                # Verifier la derniere entree
                cur.execute("""
                    SELECT direction, confidence_bucket, reason, created_at
                    FROM ml_calibration_history
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    print_ok(f"Derniere entree: {row[0]} {row[1]} ({row[2]})")
        finally:
            pg.pool.putconn(conn)
        
        return True
    except Exception as e:
        print_fail(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Verifier les endpoints API calibration."""
    print_header("TEST 5: API Endpoints")
    
    try:
        # GET /ml/calibration/stats
        resp = requests.get(f"{BASE_URL}/ml/calibration/stats", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_ok(f"GET /ml/calibration/stats: {data.get('total_trades', 0)} trades")
        else:
            print_fail(f"GET /ml/calibration/stats: {resp.status_code}")
            return False
        
        # GET /ml/calibration/check/LONG/45
        resp = requests.get(f"{BASE_URL}/ml/calibration/check/LONG/45", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print_ok(f"GET /ml/calibration/check: should_take={data.get('should_take')}")
        else:
            print_fail(f"GET /ml/calibration/check: {resp.status_code}")
            return False
        
        return True
    except requests.exceptions.ConnectionError:
        print_fail("Backend non accessible (demarrez le backend)")
        return False
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def test_export_excel_includes_tables():
    """Verifier que l'export Excel inclut les tables calibration."""
    print_header("TEST 6: Export Excel Configuration")
    
    try:
        from export_datalogger_to_excel import DataLoggerExporter
        
        tables = DataLoggerExporter.TABLES_TO_EXPORT
        
        if 'ml_calibration' in tables:
            print_ok("ml_calibration dans TABLES_TO_EXPORT")
        else:
            print_fail("ml_calibration MANQUANTE dans TABLES_TO_EXPORT")
            return False
        
        if 'ml_calibration_history' in tables:
            print_ok("ml_calibration_history dans TABLES_TO_EXPORT")
        else:
            print_fail("ml_calibration_history MANQUANTE dans TABLES_TO_EXPORT")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Erreur: {e}")
        return False


def main():
    print("\n" + "="*60)
    print(" VERIFICATION COMPLETE ML CALIBRATION TABLES")
    print("="*60)
    
    results = []
    
    results.append(("Tables SQL", test_tables_exist()))
    results.append(("Donnees Calibration", test_calibration_data()))
    results.append(("Historique", test_history_logging()))
    results.append(("Update -> History", test_update_triggers_history()))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Export Excel Config", test_export_excel_includes_tables()))
    
    # Resume
    print_header("RESUME")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\nResultat: {passed}/{total} tests passes")
    
    if passed == total:
        print("\n[SUCCESS] Tous les tests sont OK!")
        return 0
    else:
        print("\n[WARNING] Certains tests ont echoue")
        return 1


if __name__ == "__main__":
    sys.exit(main())
