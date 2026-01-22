#!/usr/bin/env python3
"""cleanup_trade_duplicates.py

Nettoie les doublons dans la table PostgreSQL `trades` quand un trade est loggé:
- une fois a l'ouverture (exit_reason NULL)
- une seconde fois a la fermeture (exit_reason non-NULL)

Mode par defaut: DRY-RUN (aucune modification)
Pour appliquer: python cleanup_trade_duplicates.py --apply

Options utiles:
- --hours N : fenetre d'analyse (defaut 48h)
- --bucket-minutes N : regrouper les trades par timestamp_entry tronque a N minutes (defaut 2)

Strategie:
- on groupe par (symbol, direction, entry_price, bucket(timestamp_entry))
- si un groupe contient au moins:
  - 1 ligne avec exit_reason NULL (ouverture)
  - 1 ligne avec exit_reason non-NULL (fermeture)
  alors on fusionne:
  - UPDATE de la ligne d'ouverture avec les champs de sortie de la ligne de fermeture
  - DELETE de la ligne de fermeture

Notes:
- on ne touche pas aux groupes sans pattern clair ouverture/fermeture
- on garde toujours la ligne "ouverture" la plus ancienne du groupe
- on utilise la ligne "fermeture" la plus recente du groupe
"""

import argparse
import sys
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple


def _print(msg: str) -> None:
    # Evite les problemes d'encodage console Windows (emojis, etc.)
    try:
        print(msg)
    except Exception:
        print(msg.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore'))


def _fetch_one_dict(cur, query: str, params: Tuple[Any, ...]) -> Optional[Dict[str, Any]]:
    cur.execute(query, params)
    row = cur.fetchone()
    if not row:
        return None
    cols = []
    for d in cur.description:
        if hasattr(d, 'name'):
            cols.append(d.name)
        elif isinstance(d, (tuple, list)) and len(d) > 0:
            cols.append(d[0])
        else:
            cols.append(str(d))
    return dict(zip(cols, row))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Appliquer les changements (sinon dry-run)')
    parser.add_argument('--hours', type=int, default=48, help='Fenetre notee en heures (defaut 48)')
    parser.add_argument('--bucket-minutes', type=int, default=2, help='Taille du bucket sur timestamp_entry (defaut 2)')
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    hours = int(args.hours)
    bucket_minutes = int(args.bucket_minutes)

    _print('==============================')
    _print('CLEANUP TRADE DUPLICATES')
    _print('==============================')
    mode_label = 'APPLY' if apply_changes else 'DRY-RUN'
    _print(f'Mode: {mode_label}')
    _print(f'Fenetre: {hours}h | Bucket: {bucket_minutes} minutes')

    try:
        try:
            from dotenv import load_dotenv  # type: ignore
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            if os.path.exists(env_path):
                load_dotenv(env_path)
        except Exception:
            pass

        import psycopg2  # type: ignore

        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = int(os.getenv('POSTGRES_PORT', '5432'))
        database = os.getenv('POSTGRES_DB') or os.getenv('POSTGRES_DATABASE') or 'trade_cursor_ml'
        user = os.getenv('POSTGRES_USER', 'postgres')
        password = os.getenv('POSTGRES_PASSWORD', '')

        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=database,
            user=user,
            password=password
        )

        try:
            with conn.cursor() as cur:
                # 1) detecter les groupes suspects
                query_groups = f"""
                    WITH grouped AS (
                        SELECT
                            symbol,
                            direction,
                            entry_price,
                            DATE_TRUNC('minute', timestamp_entry)
                              - MOD(EXTRACT(MINUTE FROM timestamp_entry)::int, {bucket_minutes}) * INTERVAL '1 minute'
                              AS bucket,
                            COUNT(*) AS cnt,
                            array_agg(id ORDER BY timestamp_entry ASC) AS ids,
                            array_agg(exit_reason ORDER BY timestamp_entry ASC) AS reasons
                        FROM trades
                        WHERE timestamp_entry > NOW() - (INTERVAL '1 hour' * %s)
                          AND entry_price IS NOT NULL
                        GROUP BY symbol, direction, entry_price, bucket
                        HAVING COUNT(*) > 1
                    )
                    SELECT symbol, direction, entry_price, bucket, cnt, ids, reasons
                    FROM grouped
                    ORDER BY bucket DESC
                """
                cur.execute(query_groups, (hours,))
                groups = cur.fetchall() or []

                _print(f'Groupes suspects trouves: {len(groups)}')

                merged_groups = 0
                deleted_rows = 0
                skipped_groups = 0
                errors = 0

                def _is_null_reason(val: Any) -> bool:
                    if val is None:
                        return True
                    if isinstance(val, str):
                        v = val.strip().lower()
                        return v in ('', 'n/a', 'na', 'none', 'null')
                    return False

                skipped_debug_budget = 8

                for (symbol, direction, entry_price, bucket, cnt, ids, reasons) in groups:
                    # identifier opening/closing
                    opening_indexes = [i for i, r in enumerate(reasons) if _is_null_reason(r)]
                    closing_indexes = [i for i, r in enumerate(reasons) if not _is_null_reason(r)]

                    if not opening_indexes or not closing_indexes:
                        skipped_groups += 1
                        if skipped_debug_budget > 0:
                            skipped_debug_budget -= 1
                            try:
                                reasons_preview = list(reasons)[:8]
                                _print(
                                    f"SKIP groupe: {symbol} {direction} entry={entry_price} bucket={bucket} cnt={cnt} reasons={reasons_preview}"
                                )
                            except Exception:
                                pass
                        continue

                    opening_id = ids[min(opening_indexes)]
                    closing_id = ids[max(closing_indexes)]

                    if opening_id == closing_id:
                        skipped_groups += 1
                        continue

                    # charger details de la ligne fermeture
                    closing = _fetch_one_dict(
                        cur,
                        """
                        SELECT
                            id,
                            exit_reason,
                            exit_price,
                            timestamp_exit,
                            gross_pnl_usdt,
                            pnl_pct,
                            pnl_usdt,
                            net_pnl_usdt,
                            net_pnl_pct,
                            fees_usdt,
                            slippage_pct,
                            slippage_usdt,
                            duration_seconds,
                            win
                        FROM trades
                        WHERE id = %s
                        """,
                        (closing_id,)
                    )

                    if not closing:
                        skipped_groups += 1
                        continue

                    # sanity: si fermeture n'a pas de raison, on skip
                    if closing.get('exit_reason') is None:
                        skipped_groups += 1
                        continue

                    _print(
                        f"Groupe: {symbol} {direction} entry={entry_price} bucket={bucket} cnt={cnt} -> merge open={str(opening_id)[:8]} close={str(closing_id)[:8]}"
                    )

                    if not apply_changes:
                        merged_groups += 1
                        deleted_rows += 1
                        continue

                    try:
                        # UPDATE ouverture avec les champs de sortie
                        cur.execute(
                            """
                            UPDATE trades
                            SET
                                exit_reason = COALESCE(%s, exit_reason),
                                exit_price = COALESCE(%s, exit_price),
                                timestamp_exit = COALESCE(%s, timestamp_exit),
                                gross_pnl_usdt = COALESCE(%s, gross_pnl_usdt),
                                pnl_pct = COALESCE(%s, pnl_pct),
                                pnl_usdt = COALESCE(%s, pnl_usdt),
                                net_pnl_usdt = COALESCE(%s, net_pnl_usdt),
                                net_pnl_pct = COALESCE(%s, net_pnl_pct),
                                fees_usdt = COALESCE(%s, fees_usdt),
                                slippage_pct = COALESCE(%s, slippage_pct),
                                slippage_usdt = COALESCE(%s, slippage_usdt),
                                duration_seconds = COALESCE(%s, duration_seconds),
                                win = COALESCE(%s, win),
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                closing.get('exit_reason'),
                                closing.get('exit_price'),
                                closing.get('timestamp_exit'),
                                closing.get('gross_pnl_usdt'),
                                closing.get('pnl_pct'),
                                closing.get('pnl_usdt'),
                                closing.get('net_pnl_usdt'),
                                closing.get('net_pnl_pct'),
                                closing.get('fees_usdt'),
                                closing.get('slippage_pct'),
                                closing.get('slippage_usdt'),
                                closing.get('duration_seconds'),
                                closing.get('win'),
                                opening_id,
                            )
                        )

                        # DELETE ligne fermeture
                        cur.execute('DELETE FROM trades WHERE id = %s', (closing_id,))
                        conn.commit()

                        merged_groups += 1
                        deleted_rows += 1

                    except Exception as e:
                        conn.rollback()
                        errors += 1
                        _print(f'ERREUR merge {symbol}: {e}')

                _print('------------------------------')
                _print('RESULTATS')
                _print('------------------------------')
                _print(f'Groupes merges: {merged_groups}')
                _print(f'Lignes supprimees: {deleted_rows}')
                _print(f'Groupes ignores: {skipped_groups}')
                _print(f'Erreurs: {errors}')

                if not apply_changes:
                    _print('DRY-RUN termine. Relance avec --apply pour appliquer.')

                return 0 if errors == 0 else 1

        finally:
            try:
                conn.close()
            except Exception:
                pass

    except Exception as e:
        _print(f'ERREUR FATALE: {e}')
        try:
            tb = traceback.format_exc()
            _print(tb)
        except Exception:
            pass
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
