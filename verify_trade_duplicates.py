#!/usr/bin/env python3
"""
Boucle de vérification automatique des doublons de trades
À exécuter périodiquement (ex: cron job toutes les heures)
"""
import sys
sys.path.append('.')
from datetime import datetime, timedelta

def check_and_alert_duplicates():
    """Vérifier les doublons et alerter si nécessaire"""
    try:
        from core.postgresql_datalogger import PostgreSQLDataLogger
        pg_logger = PostgreSQLDataLogger()
        conn = pg_logger.pool.getconn()
        
        try:
            with conn.cursor() as cur:
                # Recherche doublons récents (dernière heure)
                query1 = """
                    WITH potential_dupes AS (
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
                    SELECT COUNT(*) as dupe_groups, SUM(count) as total_dupes
                    FROM potential_dupes
                """
                cur.execute(query1)
                
                result = cur.fetchone()
                dupe_groups, total_dupes = result or (0, 0)
                
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if dupe_groups > 0:
                    print(f'[{timestamp}] ALERTE: {dupe_groups} groupes de doublons détectés ({total_dupes} trades)')
                    
                    # Log détaillé des doublons
                    query2 = """
                        WITH potential_dupes AS (
                            SELECT 
                                symbol,
                                entry_price,
                                COUNT(*) as count,
                                array_agg(id ORDER BY created_at) as trade_ids,
                                array_agg(exit_reason ORDER BY created_at) as reasons
                            FROM trades
                            WHERE created_at > NOW() - INTERVAL '1 hour'
                            AND entry_price IS NOT NULL
                            GROUP BY symbol, entry_price
                            HAVING COUNT(*) > 1
                        )
                        SELECT * FROM potential_dupes
                        ORDER BY count DESC
                        LIMIT 5
                    """
                    cur.execute(query2)
                    
                    dupes = cur.fetchall()
                    for symbol, entry, count, ids, reasons in dupes:
                        print(f'  - {symbol} entry={entry}: {count} trades (reasons: {reasons})')
                    
                    return False  # Échec détection doublons
                else:
                    print(f'[{timestamp}] Aucun doublon détecté')
                    return True  # Succès
                    
        finally:
            pg_logger.pool.putconn(conn)
            
    except Exception as e:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{timestamp}] ERREUR vérification: {e}')
        return False

if __name__ == "__main__":
    success = check_and_alert_duplicates()
    sys.exit(0 if success else 1)
