#!/usr/bin/env python3
"""Regime-aware analysis for the last 39 trades.

Goal:
- Understand performance through the lens of the MarketRegimeSelector + effective_config.
- Verify that the regime adjustments (min_score_required, atr_mult_sl/tp, etc.) actually reached trade entries.
- Use trade_atr_metrics regime what-if columns to estimate potential uplift.

No emojis / unicode to keep Windows console happy.
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


def _connect():
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
    )


def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def main():
    # Import regime defaults from code to compare with DB
    from core.market_regime_selector import DEFAULT_REGIME_CONFIGS

    expected_by_regime = {}
    for name, cfg in DEFAULT_REGIME_CONFIGS.items():
        expected_by_regime[name] = {
            'min_score_required': float(cfg.min_score_required),
            'atr_mult_sl': float(cfg.atr_mult_sl),
            'atr_mult_tp': float(cfg.atr_mult_tp),
            'break_even_atr_mult': float(cfg.break_even_atr_mult),
            'trailing_trigger_atr_mult': float(cfg.trailing_trigger_atr_mult),
            'position_timeout': float(cfg.max_position_time),
            'sl_exchange_percent': float(cfg.sl_exchange_percent),
        }

    conn = _connect()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pull last 39 trades with regime + effective params stored on entry
    cur.execute(
        """
        SELECT
            t.id,
            t.created_at,
            t.symbol,
            t.direction,
            t.net_pnl_pct,
            t.exit_reason,
            t.ml_confidence,
            t.entry_market_regime,
            t.entry_market_regime_avg_atr,
            t.entry_market_regime_avg_adx,
            t.entry_min_score_required,
            t.entry_atr_mult_sl,
            t.entry_atr_mult_tp,
            t.entry_cb_state,
            t.entry_consecutive_losses,
            t.entry_daily_pnl_pct,
            t.entry_cb_score_boost,
            -- what-if regime columns
            m.session_market,
            m.market_volatility_state,
            m.market_trend_state,
            m.regime_detection_method,
            m.regime_confidence,
            m.regime_ml_predicted,
            m.regime_ml_confidence,
            m.regime_ml_vs_rule_match,
            m.optimal_regime_retrospective,
            m.pnl_if_calme_params,
            m.pnl_if_normal_params,
            m.pnl_if_volatile_params,
            m.max_pnl_reached,
            m.min_pnl_reached,
            m.be_triggered,
            m.trailing_activated
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON m.trade_id = t.id
        ORDER BY t.created_at DESC
        LIMIT 39
        """
    )
    rows = cur.fetchall()

    print("=" * 80)
    print("REGIME-AWARE ANALYSIS - LAST 39 TRADES")
    print("=" * 80)
    print(f"Trades fetched: {len(rows)}")

    # Global stats
    total_pnl = sum((_safe_float(r.get('net_pnl_pct')) or 0.0) for r in rows)
    wins = [r for r in rows if (_safe_float(r.get('net_pnl_pct')) or 0.0) > 0]
    losses = [r for r in rows if (_safe_float(r.get('net_pnl_pct')) or 0.0) < 0]
    print("\nGLOBAL")
    print(f"  total_pnl_pct: {total_pnl:+.2f}%")
    print(f"  wins: {len(wins)}/{len(rows)} ({(len(wins)/len(rows)*100 if rows else 0):.1f}%)")

    # Distribution of entry_market_regime
    by_regime = defaultdict(lambda: {'n': 0, 'pnl': 0.0, 'wins': 0, 'long_n': 0, 'short_n': 0, 'exit': defaultdict(int)})
    missing_regime = 0
    for r in rows:
        regime = r.get('entry_market_regime')
        if regime is None:
            regime = 'NULL'
            missing_regime += 1
        pnl = _safe_float(r.get('net_pnl_pct')) or 0.0
        d = r.get('direction') or 'N/A'
        by_regime[regime]['n'] += 1
        by_regime[regime]['pnl'] += pnl
        if pnl > 0:
            by_regime[regime]['wins'] += 1
        if d == 'LONG':
            by_regime[regime]['long_n'] += 1
        elif d == 'SHORT':
            by_regime[regime]['short_n'] += 1
        by_regime[regime]['exit'][r.get('exit_reason') or 'UNKNOWN'] += 1

    print("\nBY entry_market_regime")
    for regime, stats in sorted(by_regime.items(), key=lambda kv: -kv[1]['n']):
        n = stats['n']
        wr = stats['wins'] / n * 100 if n else 0
        print(f"  {regime:10} | n={n:2} | WR={wr:5.1f}% | pnl={stats['pnl']:+.2f}% | long={stats['long_n']:2} short={stats['short_n']:2}")
        # top exit reasons per regime (up to 3)
        top_exits = sorted(stats['exit'].items(), key=lambda kv: -kv[1])[:3]
        exits_str = ', '.join([f"{k}:{v}" for k, v in top_exits])
        print(f"    exits: {exits_str}")

    # Verify regime adjustments actually applied (compare entry_* params to defaults)
    print("\nCHECK: entry params vs DEFAULT_REGIME_CONFIGS")
    mismatch_counts = defaultdict(int)
    checked = 0
    for r in rows:
        regime = r.get('entry_market_regime')
        if not regime or regime not in expected_by_regime:
            continue
        checked += 1
        exp = expected_by_regime[regime]

        # Compare a few key fields
        def _cmp(field, tol=1e-6):
            got = _safe_float(r.get(field))
            expv = exp.get(field)
            if got is None or expv is None:
                return None
            return abs(got - expv) <= tol

        for f in ('min_score_required', 'atr_mult_sl', 'atr_mult_tp'):
            ok = _cmp('entry_' + f if f != 'min_score_required' else 'entry_min_score_required', tol=0.05)
            if ok is False:
                mismatch_counts[f] += 1

    if checked == 0:
        print("  No trades with entry_market_regime in known regimes to compare.")
    else:
        print(f"  Trades comparable: {checked}")
        for f, c in mismatch_counts.items():
            print(f"  mismatches {f}: {c}/{checked}")

    # What-if regime uplift
    uplifts = []
    have_whatif = 0
    mismatch_ml_vs_opt = 0
    have_opt = 0
    for r in rows:
        actual = _safe_float(r.get('net_pnl_pct')) or 0.0
        cands = []
        for k in ('pnl_if_calme_params', 'pnl_if_normal_params', 'pnl_if_volatile_params'):
            v = _safe_float(r.get(k))
            if v is not None:
                cands.append(v)
        if cands:
            have_whatif += 1
            best = max(cands)
            uplifts.append(best - actual)

        opt = r.get('optimal_regime_retrospective')
        ml = r.get('regime_ml_predicted')
        if opt is not None:
            have_opt += 1
            if ml is not None and ml != opt:
                mismatch_ml_vs_opt += 1

    print("\nREGIME WHAT-IF (trade_atr_metrics columns)")
    print(f"  with pnl_if_* values: {have_whatif}/{len(rows)}")
    if uplifts:
        uplifts_sorted = sorted(uplifts)
        avg_u = sum(uplifts) / len(uplifts)
        med_u = uplifts_sorted[len(uplifts_sorted) // 2]
        p90_u = uplifts_sorted[int(len(uplifts_sorted) * 0.90)]
        print(f"  uplift(best_regime - actual): avg={avg_u:+.3f}% median={med_u:+.3f}% p90={p90_u:+.3f}%")

    print(f"  with optimal_regime_retrospective: {have_opt}/{len(rows)}")
    if have_opt:
        print(f"  mismatch regime_ml_predicted vs optimal: {mismatch_ml_vs_opt}/{have_opt}")

    # Directional problem inside each regime (fast signal)
    print("\nDIRECTIONAL PERFORMANCE by entry_market_regime")
    by_regime_dir = defaultdict(lambda: {'n': 0, 'pnl': 0.0, 'wins': 0})
    for r in rows:
        regime = r.get('entry_market_regime') or 'NULL'
        d = r.get('direction') or 'N/A'
        key = (regime, d)
        pnl = _safe_float(r.get('net_pnl_pct')) or 0.0
        by_regime_dir[key]['n'] += 1
        by_regime_dir[key]['pnl'] += pnl
        if pnl > 0:
            by_regime_dir[key]['wins'] += 1

    for (regime, d), stats in sorted(by_regime_dir.items(), key=lambda kv: -kv[1]['n']):
        n = stats['n']
        wr = stats['wins'] / n * 100 if n else 0
        print(f"  {regime:10} {d:5} | n={n:2} | WR={wr:5.1f}% | pnl={stats['pnl']:+.2f}%")

    # Circuit breaker visibility
    cb_present = sum(1 for r in rows if r.get('entry_cb_state') is not None)
    print("\nCIRCUIT BREAKER (entry_*)")
    print(f"  trades with entry_cb_state filled: {cb_present}/{len(rows)}")
    if cb_present:
        by_cb = defaultdict(lambda: {'n': 0, 'pnl': 0.0})
        for r in rows:
            cb = r.get('entry_cb_state')
            if cb is None:
                continue
            by_cb[str(cb)]['n'] += 1
            by_cb[str(cb)]['pnl'] += (_safe_float(r.get('net_pnl_pct')) or 0.0)
        for cb, stats in sorted(by_cb.items(), key=lambda kv: -kv[1]['n']):
            print(f"  cb_state={cb:10} | n={stats['n']:2} | pnl={stats['pnl']:+.2f}%")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
