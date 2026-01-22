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
except ImportError:
    print("❌ psycopg2 non installé")
    sys.exit(1)


def check_tables(password, days_scan: int = 7, days_trades: int = 30, top: int = 40):
    """Vérifier toutes les tables et partitions"""

    # Connection
    conn_string = f"host=localhost port=5432 dbname=trade_cursor_ml user=postgres password={password}"

    try:
        conn = psycopg2.connect(conn_string)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        print("=" * 70)
        print("📊 DIAGNOSTIC DATALOGGER POSTGRESQL")
        print("=" * 70)
        print()

        def get_columns(table_name: str):
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,)
            )
            return [row['column_name'] for row in cursor.fetchall()]

        def audit_nulls(table_name: str, ts_column: str, days: int, top: int):
            columns = get_columns(table_name)
            if not columns:
                print(f"⚠️ Aucune colonne trouvée pour {table_name}")
                return

            if ts_column not in columns:
                print(f"⚠️ Colonne timestamp '{ts_column}' absente de {table_name} (audit NULL complet)")
                where_sql = ""
                where_params = ()
            else:
                where_sql = f"WHERE {ts_column} >= NOW() - INTERVAL %s"
                where_params = (f"{days} days",)

            count_exprs = [f"COUNT({c}) AS filled__{c}" for c in columns]
            query = f"SELECT COUNT(*) AS total, {', '.join(count_exprs)} FROM {table_name} {where_sql}"
            cursor.execute(query, where_params)
            row = cursor.fetchone() or {}
            total = int(row.get('total') or 0)
            if total <= 0:
                print(f"⚠️ {table_name}: 0 lignes dans la fenêtre (days={days})")
                return

            stats = []
            for c in columns:
                filled = int(row.get(f"filled__{c}") or 0)
                nulls = total - filled
                null_pct = (nulls / total) * 100.0
                if nulls > 0:
                    stats.append((null_pct, nulls, c))

            stats.sort(reverse=True)
            print(f"🔍 Colonnes avec NULL (table={table_name}, total={total}, days={days})")
            for null_pct, nulls, c in stats[:top]:
                print(f"  - {c:40s} : {nulls:>10,} NULL ({null_pct:6.2f}%)")

        print("🔎 Audit NULL (scan_logs / trades)")
        print("-" * 70)
        audit_nulls('scan_logs', 'timestamp', days_scan, top)
        print()
        audit_nulls('trades', 'timestamp_entry', days_trades, top)
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
        conn.close()

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Diagnostic DataLogger PostgreSQL')
    parser.add_argument('--password', required=True, help='PostgreSQL password')

    parser.add_argument('--days-scan', type=int, default=7, help='Fenêtre (jours) pour audit scan_logs')
    parser.add_argument('--days-trades', type=int, default=30, help='Fenêtre (jours) pour audit trades')
    parser.add_argument('--top', type=int, default=40, help='Nombre de colonnes affichées (triées par % NULL)')

    args = parser.parse_args()
    check_tables(args.password, days_scan=args.days_scan, days_trades=args.days_trades, top=args.top)
