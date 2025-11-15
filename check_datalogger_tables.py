#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier les données du DataLogger PostgreSQL
"""

import os
import sys
import argparse

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from database.pg import get_connection
    HAS_APP_POOL = True
except ImportError:
    print("❌ psycopg2 non installé")
    sys.exit(1)
except Exception:
    HAS_APP_POOL = False


def check_tables(password):
    """Vérifier toutes les tables et partitions"""

    conn = None
    conn_ctx = None

    try:
        if HAS_APP_POOL and not password:
            conn_ctx = get_connection()
            conn = conn_ctx.__enter__()
        else:
            conn_string = (
                f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
                f"port={os.getenv('POSTGRES_PORT', '5432')} "
                f"dbname={os.getenv('POSTGRES_DB', 'trade_cursor_ml')} "
                f"user={os.getenv('POSTGRES_USER', 'postgres')} "
                f"password={password}"
            )
            conn = psycopg2.connect(conn_string)

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        print("=" * 70)
        print("📊 DIAGNOSTIC DATALOGGER POSTGRESQL")
        print("=" * 70)
        print()

        # 0. Forcer le flush du datalogger si possible
        print("🔄 Tentative de forcer le flush du datalogger...")
        print("-" * 70)
        try:
            # Importer et forcer le flush
            import sys
            sys.path.insert(0, '.')
            from core.callbacks.scanner_loop import get_pg_datalogger
            pg_datalogger = get_pg_datalogger()
            if pg_datalogger and pg_datalogger.enabled:
                print(f"✅ DataLogger trouvé (buffer: {len(pg_datalogger.scan_buffer)} scans)")
                pg_datalogger._flush_buffers(force=True)
                print("✅ Flush forcé effectué")
            else:
                print("⚠️ DataLogger non disponible ou désactivé")
        except Exception as e:
            print(f"⚠️ Impossible de forcer le flush: {e}")
        print()

        # 1. Vérifier toutes les tables
        print("🔍 Tables principales:")
        print("-" * 70)

        tables = [
            'trading_sessions',
            'config_snapshots',
            'scan_logs',
            'opportunities',
            'trades',
            'market_context',
            'scan_errors',
            'model_predictions',
            'features_engineered'
        ]

        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                result = cursor.fetchone()
                count = result['count']
                status = "✅" if count > 0 else "⚠️"
                print(f"{status} {table:25s} : {count:>10,} lignes")
            except Exception as e:
                print(f"❌ {table:25s} : ERREUR - {e}")

        print()

        # 2. Vérifier les partitions de scan_logs
        print("🔍 Partitions de scan_logs:")
        print("-" * 70)

        cursor.execute("""
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE tablename LIKE 'scan_logs_%'
            ORDER BY tablename
        """)

        partitions = cursor.fetchall()

        if partitions:
            for partition in partitions:
                table_name = partition['tablename']
                size = partition['size']

                # Compter les lignes dans cette partition
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                result = cursor.fetchone()
                count = result['count']

                status = "✅" if count > 0 else "⚠️"
                print(f"{status} {table_name:35s} : {count:>10,} lignes ({size})")
        else:
            print("⚠️ Aucune partition trouvée")

        print()

        # 3. Vérifier les derniers enregistrements
        print("🔍 Derniers enregistrements scan_logs:")
        print("-" * 70)

        cursor.execute("""
            SELECT timestamp, symbol, price, rsi_1m, score_total, is_opportunity, opportunity_direction
            FROM scan_logs
            ORDER BY timestamp DESC
            LIMIT 5
        """)

        recent_scans = cursor.fetchall()

        if recent_scans:
            for scan in recent_scans:
                opp_status = "✅ OPP" if scan['is_opportunity'] else "⚪ SCAN"
                direction = scan['opportunity_direction'] or 'N/A'
                print(f"  {opp_status} | {scan['timestamp']} | {scan['symbol']:15s} | Prix: {scan['price']:.2f} | RSI: {scan['rsi_1m']} | Score: {scan['score_total']} | Dir: {direction}")
        else:
            print("⚠️ Aucun scan trouvé dans scan_logs")

        print()

        # 4. Vérifier les derniers trades
        print("🔍 Derniers trades:")
        print("-" * 70)

        cursor.execute("""
            SELECT timestamp_entry, symbol, direction, entry_price, exit_price, net_pnl_usdt
            FROM trades
            ORDER BY timestamp_entry DESC
            LIMIT 5
        """)

        recent_trades = cursor.fetchall()

        if recent_trades:
            for trade in recent_trades:
                print(f"  {trade['timestamp_entry']} | {trade['symbol']:15s} | {trade['direction']:5s} | Entry: {trade['entry_price']:.2f} | Exit: {trade['exit_price'] or 'N/A'} | PnL: {trade['net_pnl_usdt']:.2f} USDT")
        else:
            print("⚠️ Aucun trade trouvé")

        print()

        # 5. Vérifier les sessions actives
        print("🔍 Sessions de trading:")
        print("-" * 70)

        cursor.execute("""
            SELECT id, start_time, end_time, total_scans, opportunities_detected, trades_executed, total_pnl_usdt
            FROM trading_sessions
            ORDER BY start_time DESC
            LIMIT 5
        """)

        sessions = cursor.fetchall()

        if sessions:
            for session in sessions:
                status = "🟢 ACTIVE" if session['end_time'] is None else "⚪ CLOSED"
                print(f"{status} | Start: {session['start_time']} | Scans: {session['total_scans']:,} | Opps: {session['opportunities_detected']} | Trades: {session['trades_executed']} | PnL: {session['total_pnl_usdt']:.2f}")
        else:
            print("⚠️ Aucune session trouvée")

        print()
        print("=" * 70)

        cursor.close()
        if conn_ctx:
            conn_ctx.__exit__(None, None, None)
        elif conn:
            conn.close()

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        if conn_ctx:
            conn_ctx.__exit__(None, None, None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Diagnostic DataLogger PostgreSQL')
    parser.add_argument('--password', default='', help='PostgreSQL password (facultatif si pool déjà configuré)')

    args = parser.parse_args()
    check_tables(args.password)
