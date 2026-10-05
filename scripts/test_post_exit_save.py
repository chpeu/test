#!/usr/bin/env python3
"""
Test Post-Exit DB Save - Teste la sauvegarde directement
"""
import sys
import os

# Fix encoding Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from datetime import datetime, timezone
import uuid

def main():
    print("=" * 60)
    print("🧪 Test Post-Exit DB Save")
    print("=" * 60)
    
    # 1. Récupérer un trade_id existant
    import psycopg2
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    with conn.cursor() as cur:
        cur.execute("SELECT id, symbol, direction FROM trades ORDER BY created_at DESC LIMIT 1")
        result = cur.fetchone()
        if not result:
            print("❌ Aucun trade trouvé en DB")
            return
        trade_id, symbol, direction = result
        print(f"📊 Trade sélectionné: {trade_id} ({symbol}, {direction})")
    conn.close()
    
    # 2. Créer un tracker de test
    from core.post_exit.tracker import PostExitTracker
    
    tracker = PostExitTracker(
        trade_id=str(trade_id),  # Convertir en string
        symbol=symbol,
        direction=direction,
        exit_price=100.0,
        exit_timestamp=datetime.now(timezone.utc),
        exit_reason="TEST",
        realized_pnl_pct=0.5,
        realized_pnl_usdt=5.0,
        original_sl=99.0,
        original_tp=101.0,
        entry_price=99.5,
        tracking_duration_sec=60,
        sample_interval_ms=1000
    )
    
    # Ajouter quelques samples
    for i in range(10):
        price = 100.0 + (i * 0.1)  # Prix qui monte
        tracker.add_sample(price)
        import time
        time.sleep(0.1)  # Petit délai pour éviter le rate limit
    
    print(f"✅ Tracker créé avec {len(tracker.samples)} samples")
    
    # 3. Calculer les métriques
    metrics = tracker.compute_final_metrics()
    print(f"📊 Métriques calculées:")
    print(f"   - trade_id: {metrics.get('trade_id')} (type: {type(metrics.get('trade_id')).__name__})")
    print(f"   - exit_efficiency: {metrics.get('exit_efficiency_pct')}%")
    print(f"   - post_exit_mfe: {metrics.get('post_exit_mfe_pct')}%")
    print(f"   - sample_count: {metrics.get('sample_count')}")
    
    # 4. Tester la sauvegarde directement
    print("\n🔄 Test sauvegarde DB...")
    
    # Configurer logging pour voir les messages
    import logging
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s:%(name)s:%(message)s')
    
    # Test direct via psycopg2 d'abord
    print("\n🔍 Test INSERT direct...")
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trade_post_exit_analysis (
                    trade_id, exit_price, exit_timestamp, exit_reason, direction,
                    realized_pnl_pct, realized_pnl_usdt,
                    tracking_duration_sec, sample_count, sample_interval_ms,
                    post_exit_mfe_pct, post_exit_mae_pct, post_exit_final_pct,
                    exit_efficiency_pct, regret_pct, regret_usdt, exit_timing_grade,
                    would_have_hit_original_tp, would_have_hit_original_sl, price_returned_to_entry
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ON CONFLICT (trade_id) DO UPDATE SET sample_count = EXCLUDED.sample_count
                RETURNING id
            """, (
                str(trade_id),
                metrics['exit_price'],
                tracker.exit_timestamp,
                metrics['exit_reason'],
                metrics['direction'],
                metrics['realized_pnl_pct'],
                metrics['realized_pnl_usdt'],
                metrics['tracking_duration_sec'],
                metrics['sample_count'],
                metrics['sample_interval_ms'],
                metrics['post_exit_mfe_pct'],
                metrics['post_exit_mae_pct'],
                metrics['post_exit_final_pct'],
                metrics['exit_efficiency_pct'],
                metrics['regret_pct'],
                metrics['regret_usdt'],
                metrics['exit_timing_grade'],
                metrics['would_have_hit_original_tp'],
                metrics['would_have_hit_original_sl'],
                metrics['price_returned_to_entry'],
            ))
            result = cur.fetchone()
            conn.commit()
            print(f"✅ INSERT direct réussi! ID={result[0]}")
    except Exception as e:
        print(f"❌ INSERT direct échoué: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
    
    print("\n🔄 Test via PostExitManager...")
    from core.post_exit.manager import PostExitManager
    manager = PostExitManager()
    
    # Debug: vérifier le datalogger
    from core.postgresql_datalogger import get_pg_datalogger
    datalogger = get_pg_datalogger()
    print(f"   - DataLogger instance: {datalogger}")
    print(f"   - DataLogger enabled: {datalogger.enabled if datalogger else 'N/A'}")
    if datalogger:
        conn = datalogger._get_connection()
        print(f"   - Connexion: {conn}")
        if conn:
            datalogger._return_connection(conn)
    
    # Test async
    async def test_save():
        result = await manager._save_to_database(tracker, metrics)
        return result
    
    try:
        result = asyncio.run(test_save())
        if result:
            print("✅ Sauvegarde réussie!")
            
            # Vérifier en DB
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', 5432)),
                database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT trade_id, exit_efficiency_pct, sample_count 
                    FROM trade_post_exit_analysis 
                    WHERE trade_id = %s
                """, (str(trade_id),))
                row = cur.fetchone()
                if row:
                    print(f"✅ Vérifié en DB: trade_id={row[0]}, efficiency={row[1]}, samples={row[2]}")
                else:
                    print("⚠️ Row non trouvée après INSERT")
            conn.close()
        else:
            print("❌ Sauvegarde échouée (retourne False)")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
