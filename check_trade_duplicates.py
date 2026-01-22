#!/usr/bin/env python3
"""
Script de vérification des doublons de trades
Exécuter périodiquement pour détecter les nouveaux doublons
"""
import sys
sys.path.append('.')
from datetime import datetime

def check_duplicates():
    """Vérifier les doublons de trades récents"""
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg = PostgreSQLDataLogger()
        conn = pg.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # Rechercher doublons récents (dernière heure)
                cur.execute("""
                    WITH dupes AS (
                        SELECT 
                            symbol, 
                            entry_price, 
                            COUNT(*) as count,
                            array_agg(exit_reason) as reasons
                        FROM trades
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                        AND entry_price IS NOT NULL
                        GROUP BY symbol, entry_price
                        HAVING COUNT(*) > 1
                    )
                    SELECT COUNT(*) as groups, COALESCE(SUM(count), 0) as total
                    FROM dupes
                """)
                
                result = cur.fetchone()
                groups, total = result or (0, 0)
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if groups > 0:
                    print(f"[{timestamp}] ALERTE: {groups} groupes de doublons detectes ({total} trades)")
                    
                    # Détail des doublons
                    cur.execute("""
                        WITH dupes AS (
                            SELECT 
                                symbol, 
                                entry_price, 
                                COUNT(*) as count,
                                array_agg(exit_reason) as reasons
                            FROM trades
                            WHERE created_at > NOW() - INTERVAL '1 hour'
                            AND entry_price IS NOT NULL
                            GROUP BY symbol, entry_price
                            HAVING COUNT(*) > 1
                        )
                        SELECT * FROM dupes ORDER BY count DESC LIMIT 5
                    """)
                    
                    details = cur.fetchall()
                    for symbol, entry, count, reasons in details:
                        print(f"  - {symbol} entry={entry}: {count} trades (reasons: {reasons})")
                    
                    return False
                else:
                    print(f"[{timestamp}] OK: Aucun doublon detecte")
                    return True
                    
        finally:
            pg.pool.putconn(conn)
            
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] ERREUR verification: {e}")
        return False

if __name__ == "__main__":
    success = check_duplicates()
    sys.exit(0 if success else 1)
