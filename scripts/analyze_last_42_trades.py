import os
from datetime import datetime
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def _pct(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=5,
    )

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Introspect columns (trades)
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'trades'
            ORDER BY ordinal_position
            """
        )
        trade_cols = [r["column_name"] for r in cur.fetchall()]

        # Pick best timestamp column for ordering
        ts_candidates = [
            "timestamp_exit",
            "timestamp_entry",
            "exit_timestamp",
            "closed_at",
            "close_time",
            "closed_time",
            "updated_at",
            "created_at",
            "timestamp",
        ]
        ts_col = next((c for c in ts_candidates if c in trade_cols), None)
        if not ts_col:
            raise RuntimeError(
                f"Impossible de trouver une colonne temps dans trades. Candidates={ts_candidates}"
            )

        pnl_candidates = [
            "pnl_pct",
            "realized_pnl_pct",
            "net_pnl_pct",
            "pnl_percent",
        ]
        pnl_col = next((c for c in pnl_candidates if c in trade_cols), None)
        if not pnl_col:
            raise RuntimeError(
                f"Impossible de trouver une colonne pnl_pct dans trades. Candidates={pnl_candidates}"
            )

        symbol_col = "symbol" if "symbol" in trade_cols else None
        direction_col = "direction" if "direction" in trade_cols else None
        entry_price_col = "entry_price" if "entry_price" in trade_cols else None

        # Fetch last 42 trades
        select_cols = ["id", ts_col, pnl_col]
        if symbol_col:
            select_cols.append(symbol_col)
        if direction_col:
            select_cols.append(direction_col)
        if entry_price_col:
            select_cols.append(entry_price_col)

        cur.execute(
            f"""
            SELECT {', '.join(select_cols)}
            FROM trades
            WHERE {pnl_col} IS NOT NULL
                AND {ts_col} IS NOT NULL
            ORDER BY {ts_col} DESC
            LIMIT 42
            """
        )
        trades = cur.fetchall()

        trade_ids = [t["id"] for t in trades]

        # Join with post-exit analysis if available
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'trade_post_exit_analysis'
            ORDER BY ordinal_position
            """
        )
        pea_cols = [r["column_name"] for r in cur.fetchall()]

        pea_by_id = {}
        if "trade_id" in pea_cols:
            # trade_post_exit_analysis.trade_id est UUID dans certaines DB, et nos ids
            # peuvent être passés comme strings (text[]). On compare en text pour éviter
            # les erreurs uuid = text.
            trade_id_texts = [str(tid) for tid in trade_ids]
            cur.execute(
                """
                SELECT *
                FROM trade_post_exit_analysis
                WHERE trade_id::text = ANY(%s)
                """,
                (trade_id_texts,),
            )
            for r in cur.fetchall():
                pea_by_id[str(r["trade_id"])] = r

        # Compute stats
        pnls = [_pct(t[pnl_col]) for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        total = len(pnls)
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / total if total else 0

        sorted_pnls = sorted(pnls)
        median_pnl = (
            sorted_pnls[total // 2]
            if total % 2 == 1
            else (sorted_pnls[total // 2 - 1] + sorted_pnls[total // 2]) / 2
            if total
            else 0
        )

        gross_win = sum(p for p in pnls if p > 0)
        gross_loss = sum(p for p in pnls if p < 0)
        profit_factor = (gross_win / abs(gross_loss)) if gross_loss < 0 else None

        print("=" * 100)
        print("📊 ANALYSE DES 42 DERNIERS TRADES")
        print("=" * 100)
        print(f"Timestamp column: {ts_col} | PnL column: {pnl_col}")
        print(f"Total trades: {total}")
        print(f"Winrate: {wins}/{total} = {wins/total*100:.1f}%")
        print(f"Total PnL%: {total_pnl:.3f}%")
        print(f"Avg PnL%:   {avg_pnl:.4f}%")
        print(f"Median PnL%:{median_pnl:.4f}%")
        if profit_factor is not None:
            print(f"Profit Factor: {profit_factor:.3f}")
        else:
            print("Profit Factor: N/A (no losses or missing)")

        # Post-exit coverage
        pea_coverage = sum(1 for t in trades if str(t["id"]) in pea_by_id)
        print("-" * 100)
        print(f"Post-exit rows found for last 42: {pea_coverage}/42")

        # Optimal coverage
        optimal_fields = [
            "ml_optimal_sl_pct",
            "ml_optimal_trailing_trigger",
            "ml_optimal_be_trigger",
            "ml_optimal_trailing_distance",
            "ml_should_use_partial",
        ]
        optimal_coverage = 0
        for t in trades:
            pea = pea_by_id.get(str(t["id"]))
            if not pea:
                continue
            if any(pea.get(f) is not None for f in optimal_fields):
                optimal_coverage += 1
        print(f"Trades (sur 42) avec au moins un ml_optimal_* non NULL: {optimal_coverage}/42")

        # Distribution rapide (pour identifier un pattern: beaucoup de -0.20%, wins trop petits, etc.)
        losses = [p for p in pnls if p < 0]
        wins_p = [p for p in pnls if p > 0]
        near_sl_hits = sum(1 for p in pnls if p <= -0.19)
        small_wins = sum(1 for p in pnls if 0 < p <= 0.06)
        mid_wins = sum(1 for p in pnls if 0.06 < p <= 0.15)
        big_wins = sum(1 for p in pnls if p > 0.15)
        small_losses = sum(1 for p in pnls if -0.06 <= p < 0)
        mid_losses = sum(1 for p in pnls if -0.19 < p < -0.06)

        avg_win = sum(wins_p) / len(wins_p) if wins_p else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        expectancy = (wins / total) * avg_win + ((total - wins) / total) * avg_loss if total else 0.0

        print("-" * 100)
        print("📌 Distribution PnL% (approx)")
        print(f"-0.19% ou pire (≈ SL hit): {near_sl_hits}/{total}")
        print(f"Pertes petites (0 à -0.06): {small_losses}/{total}")
        print(f"Pertes moyennes (-0.19 à -0.06): {mid_losses}/{total}")
        print(f"Gains petits (0 à +0.06): {small_wins}/{total}")
        print(f"Gains moyens (+0.06 à +0.15): {mid_wins}/{total}")
        print(f"Gains grands (> +0.15): {big_wins}/{total}")
        print("-" * 100)
        print(f"Avg win%:  {avg_win:.4f}%")
        print(f"Avg loss%: {avg_loss:.4f}%")
        print(f"Expectancy% (moyenne par trade): {expectancy:.4f}%")

        # Post-exit quick insight: proportion d'optimaux manquants
        missing_targets = 0
        missing_targets_sc_gt_10 = 0
        missing_examples = []
        target_fields = [
            "ml_optimal_sl_pct",
            "ml_optimal_trailing_trigger",
            "ml_optimal_be_trigger",
            "ml_optimal_trailing_distance",
            "ml_should_use_partial",
        ]
        for t in trades:
            pea = pea_by_id.get(str(t["id"]))
            if not pea:
                continue
            realized_pnl = _pct(pea.get("realized_pnl_pct"))
            missing = []
            for f in target_fields:
                if f == "ml_optimal_trailing_trigger" and realized_pnl <= 0:
                    continue
                if pea.get(f) is None:
                    missing.append(f)
            if missing:
                missing_targets += 1
                sc = pea.get("sample_count") or 0
                if sc > 10:
                    missing_targets_sc_gt_10 += 1
                if len(missing_examples) < 15:
                    missing_examples.append((t, pea, missing))
        if pea_coverage:
            print(
                f"Post-exit: trades avec cibles ml_optimal_* incomplètes: {missing_targets}/{pea_coverage} "
                f"(sample_count>10: {missing_targets_sc_gt_10}/{pea_coverage})"
            )
            if missing_examples:
                print("-" * 100)
                print("Exemples trades incomplets (max 15)")
                for t, pea, missing in missing_examples:
                    sym = t.get(symbol_col) if symbol_col else None
                    d = t.get(direction_col) if direction_col else None
                    p = _pct(t[pnl_col])
                    sc = pea.get("sample_count")
                    print(
                        f"{str(t['id'])[:8]} | sc={sc} | pnl={p:+.3f}% | "
                        f"{(sym or ''):16} | {(d or ''):5} | missing={','.join(missing)}"
                    )

        # Breakdown direction (si colonne dispo)
        if direction_col:
            by_dir = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0})
            for t in trades:
                d = (t.get(direction_col) or "N/A")
                p = _pct(t[pnl_col])
                by_dir[d]["n"] += 1
                by_dir[d]["pnl"] += p
                if p > 0:
                    by_dir[d]["wins"] += 1

            print("-" * 100)
            print("🧭 Breakdown par direction")
            for d, s in sorted(by_dir.items(), key=lambda x: -x[1]["n"]):
                wr = (s["wins"] / s["n"] * 100) if s["n"] else 0
                print(f"{d:6} | n={s['n']:2d} | WR={wr:5.1f}% | PnL={s['pnl']:+.3f}%")

        # Breakdown symbol (si colonne dispo) - top 10 par volume de trades
        if symbol_col:
            by_sym = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0})
            for t in trades:
                sym = (t.get(symbol_col) or "N/A")
                p = _pct(t[pnl_col])
                by_sym[sym]["n"] += 1
                by_sym[sym]["pnl"] += p
                if p > 0:
                    by_sym[sym]["wins"] += 1

            top_syms = sorted(by_sym.items(), key=lambda x: (-x[1]["n"], x[1]["pnl"]))[:10]
            print("-" * 100)
            print("🧩 Top symboles (top 10 par nombre de trades, puis PnL)")
            for sym, s in top_syms:
                wr = (s["wins"] / s["n"] * 100) if s["n"] else 0
                print(f"{sym:16} | n={s['n']:2d} | WR={wr:5.1f}% | PnL={s['pnl']:+.3f}%")

        print("=" * 100)
        print("✅ Fin rapport")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
