#!/usr/bin/env python3
"""
Script pour vérifier le système Post-Exit Analysis
"""

import psycopg2
import os
from datetime import datetime, timedelta

# Configuration - Utiliser connection string pour éviter problèmes d'encodage
def get_connection():
    """Créer connexion PostgreSQL"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        password = os.getenv('POSTGRES_PASSWORD', 'Lipton2019!')
        
        # Utiliser connection string
        conn_str = f"host=localhost port=5432 dbname=trade_cursor_ml user=postgres password={password}"
        return psycopg2.connect(conn_str)
    except Exception as e:
        print(f"❌ Erreur connexion: {e}")
        # Fallback sans password
        return psycopg2.connect("host=localhost port=5432 dbname=trade_cursor_ml user=postgres")

def check_recent_trades():
    """Vérifier les trades récents"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Trades fermés dans les 2 dernières heures
    cur.execute("""
        SELECT 
            id, symbol, direction, exit_reason, 
            net_pnl_pct, timestamp_exit
        FROM trades 
        WHERE timestamp_exit > NOW() - INTERVAL '2 hours'
        ORDER BY timestamp_exit DESC
        LIMIT 10
    """)
    
    trades = cur.fetchall()
    print(f"\n{'='*80}")
    print(f"TRADES FERMÉS (2 dernières heures): {len(trades)}")
    print(f"{'='*80}")
    
    if not trades:
        print("❌ Aucun trade fermé récemment")
        cur.close()
        conn.close()
        return []
    
    for trade in trades:
        trade_id, symbol, direction, exit_reason, pnl_pct, exit_time = trade
        print(f"\n📊 Trade #{trade_id}")
        print(f"   Symbol: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Exit: {exit_reason}")
        print(f"   PnL: {pnl_pct:.2f}%")
        print(f"   Fermé: {exit_time}")
    
    cur.close()
    conn.close()
    return [t[0] for t in trades]

def check_post_exit_analysis(trade_ids):
    """Vérifier les analyses Post-Exit"""
    if not trade_ids:
        return
    
    conn = get_connection()
    cur = conn.cursor()
    
    print(f"\n{'='*80}")
    print(f"POST-EXIT ANALYSIS")
    print(f"{'='*80}")
    
    # D'abord vérifier si la table existe
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name = 'trade_post_exit_analysis'
    """)
    
    if cur.fetchone()[0] == 0:
        print("\n❌ Table trade_post_exit_analysis n'existe pas")
        cur.close()
        conn.close()
        return
    
    # Vérifier les colonnes disponibles
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'trade_post_exit_analysis'
        ORDER BY ordinal_position
    """)
    
    columns = [row[0] for row in cur.fetchall()]
    print(f"\nColonnes disponibles: {', '.join(columns)}")
    
    # Requête simplifiée avec seulement les colonnes de base
    for trade_id in trade_ids:
        cur.execute("""
            SELECT *
            FROM trade_post_exit_analysis
            WHERE trade_id = %s
        """, (trade_id,))
        
        result = cur.fetchone()
        
        if result:
            print(f"\n✅ Trade #{trade_id} - ANALYSE POST-EXIT TROUVÉE")
            print(f"   Données: {result}")
        else:
            print(f"\n❌ Trade #{trade_id} - PAS D'ANALYSE POST-EXIT")
    
    cur.close()
    conn.close()

def check_scan_errors():
    """Vérifier les erreurs loggées"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM scan_errors 
        WHERE timestamp > NOW() - INTERVAL '2 hours'
    """)
    
    error_count = cur.fetchone()[0]
    
    print(f"\n{'='*80}")
    print(f"ERREURS LOGGÉES (2 dernières heures): {error_count}")
    print(f"{'='*80}")
    
    if error_count > 0:
        cur.execute("""
            SELECT timestamp, error_type, error_message, symbol
            FROM scan_errors
            WHERE timestamp > NOW() - INTERVAL '2 hours'
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        errors = cur.fetchall()
        for err in errors:
            ts, err_type, msg, symbol = err
            symbol_str = f" [{symbol}]" if symbol else ""
            print(f"\n{err_type}{symbol_str} - {ts}")
            print(f"  {msg[:100]}...")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("\n🔍 VÉRIFICATION SYSTÈME POST-EXIT")
    print(f"Timestamp: {datetime.now()}")
    
    # 1. Vérifier trades récents
    trade_ids = check_recent_trades()
    
    # 2. Vérifier analyses Post-Exit
    check_post_exit_analysis(trade_ids)
    
    # 3. Vérifier erreurs
    check_scan_errors()
    
    print(f"\n{'='*80}")
    print("✅ VÉRIFICATION TERMINÉE")
    print(f"{'='*80}\n")
