import os
import sys
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def _setup_stdout_utf8() -> None:
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')


def _engine_from_env():
    load_dotenv()
    user = os.getenv('POSTGRES_USER', 'postgres')
    password_raw = os.getenv('POSTGRES_PASSWORD', '')
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    db = os.getenv('POSTGRES_DB', 'trade_cursor_ml')

    password = quote_plus(password_raw)
    conn_str = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return create_engine(conn_str)


def _print_table(title: str, header: list[str], rows: list[tuple]):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)
    print(" | ".join(header))
    print("-" * 80)
    for r in rows:
        print(" | ".join(str(x) for x in r))


def main():
    _setup_stdout_utf8()
    engine = _engine_from_env()

    with engine.connect() as conn:
        # 1) Distribution régime (24h / 7j)
        for label, interval in [("24H", "24 hours"), ("7J", "7 days")]:
            q = text(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN entry_market_regime IS NULL THEN 1 ELSE 0 END) AS regime_null,
                    SUM(CASE WHEN entry_market_regime = 'UNKNOWN' THEN 1 ELSE 0 END) AS regime_unknown
                FROM trades
                WHERE timestamp_entry > NOW() - INTERVAL :interval
                """
            )
            r = conn.execute(q, {"interval": interval}).fetchone()
            total = int(r[0] or 0)
            null_cnt = int(r[1] or 0)
            unk_cnt = int(r[2] or 0)
            unk_pct = (unk_cnt / (total - null_cnt) * 100) if (total - null_cnt) > 0 else 0
            print("\n" + "=" * 80)
            print(f"RÉSUMÉ RÉGIME ({label})")
            print("=" * 80)
            print(f"Total trades: {total}")
            print(f"entry_market_regime NULL: {null_cnt}")
            print(f"entry_market_regime=UNKNOWN: {unk_cnt} (sur non-NULL: {unk_pct:.1f}%)")

            q2 = text(
                """
                SELECT
                    COALESCE(entry_market_regime, 'NULL') AS regime,
                    COUNT(*) AS cnt,
                    ROUND(AVG(CASE WHEN net_pnl_usdt > 0 THEN 1.0 ELSE 0.0 END) * 100, 1) AS winrate
                FROM trades
                WHERE timestamp_entry > NOW() - INTERVAL :interval
                GROUP BY 1
                ORDER BY cnt DESC
                """
            )
            rows = conn.execute(q2, {"interval": interval}).fetchall()
            _print_table(
                f"Distribution entry_market_regime ({label})",
                ["regime", "count", "winrate%"],
                rows,
            )

        # 2) UNKNOWN diagnostics (sur trades non-NULL, 7j)
        q3 = text(
            """
            SELECT
                COUNT(*) AS n,
                ROUND(AVG(COALESCE(entry_market_regime_avg_atr, 0))::numeric, 4) AS avg_atr,
                ROUND(AVG(COALESCE(entry_market_regime_avg_adx, 0))::numeric, 2) AS avg_adx,
                SUM(CASE WHEN entry_market_regime_avg_atr IS NULL OR entry_market_regime_avg_atr = 0 THEN 1 ELSE 0 END) AS atr_zero_or_null,
                SUM(CASE WHEN entry_market_regime_avg_adx IS NULL OR entry_market_regime_avg_adx = 0 THEN 1 ELSE 0 END) AS adx_zero_or_null
            FROM trades
            WHERE timestamp_entry > NOW() - INTERVAL '7 days'
              AND entry_market_regime = 'UNKNOWN'
            """
        )
        r = conn.execute(q3).fetchone()
        n = int(r[0] or 0)
        if n > 0:
            atr_zero_pct = (int(r[3] or 0) / n * 100)
            adx_zero_pct = (int(r[4] or 0) / n * 100)
        else:
            atr_zero_pct = 0
            adx_zero_pct = 0

        _print_table(
            "UNKNOWN - DIAGNOSTIC (7J)",
            ["n", "avg_atr", "avg_adx", "atr_zero_or_null%", "adx_zero_or_null%"],
            [(n, r[1], r[2], f"{atr_zero_pct:.1f}%", f"{adx_zero_pct:.1f}%")],
        )

        # 3) What-If coverage (24h / 7j)
        for label, interval in [("24H", "24 hours"), ("7J", "7 days")]:
            q = text(
                """
                SELECT
                    COUNT(*) AS trades,
                    SUM(CASE WHEN m.trade_id IS NOT NULL THEN 1 ELSE 0 END) AS with_metrics,
                    SUM(CASE WHEN m.pnl_if_calme_params IS NOT NULL THEN 1 ELSE 0 END) AS with_regime_whatif,
                    SUM(CASE WHEN m.pnl_if_no_be IS NOT NULL THEN 1 ELSE 0 END) AS with_classic_whatif
                FROM trades t
                LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
                WHERE t.timestamp_entry > NOW() - INTERVAL :interval
                """
            )
            r = conn.execute(q, {"interval": interval}).fetchone()
            trades = int(r[0] or 0)
            with_metrics = int(r[1] or 0)
            with_regime = int(r[2] or 0)
            with_classic = int(r[3] or 0)

            def pct(a: int, b: int) -> str:
                return f"{(a / b * 100):.1f}%" if b > 0 else "N/A"

            _print_table(
                f"COUVERTURE WHAT-IF ({label})",
                [
                    "trades",
                    "with_metrics",
                    "with_metrics%",
                    "with_regime_whatif",
                    "regime_whatif% (sur metrics)",
                    "with_classic_whatif",
                    "classic_whatif% (sur metrics)",
                ],
                [
                    (
                        trades,
                        with_metrics,
                        pct(with_metrics, trades),
                        with_regime,
                        pct(with_regime, with_metrics),
                        with_classic,
                        pct(with_classic, with_metrics),
                    )
                ],
            )

        # 4) Coverage par regime (sur trades avec metrics uniquement, 7j)
        q = text(
            """
            SELECT
                t.entry_market_regime,
                COUNT(*) AS trades,
                SUM(CASE WHEN m.trade_id IS NOT NULL THEN 1 ELSE 0 END) AS with_metrics,
                SUM(CASE WHEN m.pnl_if_calme_params IS NOT NULL THEN 1 ELSE 0 END) AS with_regime_whatif,
                SUM(CASE WHEN m.pnl_if_no_be IS NOT NULL THEN 1 ELSE 0 END) AS with_classic_whatif
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.timestamp_entry > NOW() - INTERVAL '7 days'
              AND t.entry_market_regime IS NOT NULL
            GROUP BY 1
            ORDER BY trades DESC
            """
        )
        rows = conn.execute(q).fetchall()

        formatted = []
        for r in rows:
            regime = r[0]
            trades = int(r[1] or 0)
            with_metrics = int(r[2] or 0)
            with_regime = int(r[3] or 0)
            with_classic = int(r[4] or 0)

            def pct(a: int, b: int) -> str:
                return f"{(a / b * 100):.1f}%" if b > 0 else "N/A"

            formatted.append(
                (
                    regime,
                    trades,
                    with_metrics,
                    pct(with_metrics, trades),
                    with_regime,
                    pct(with_regime, with_metrics),
                    with_classic,
                    pct(with_classic, with_metrics),
                )
            )

        _print_table(
            "COUVERTURE WHAT-IF PAR RÉGIME (7J, sur trades avec entry_market_regime non-NULL)",
            [
                "regime",
                "trades",
                "with_metrics",
                "metrics%",
                "with_regime_whatif",
                "regime_whatif%",
                "with_classic_whatif",
                "classic_whatif%",
            ],
            formatted,
        )


if __name__ == "__main__":
    main()
