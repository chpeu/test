import os
import sys
import math

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text


def _to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _quantile(values, q: float):
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def _summarize(values):
    xs = [x for x in values if x is not None]
    if not xs:
        return None

    n = len(xs)
    mean = sum(xs) / n
    return {
        'count': n,
        'mean': mean,
        'p50': _quantile(xs, 0.50),
        'p75': _quantile(xs, 0.75),
        'p90': _quantile(xs, 0.90),
        'p95': _quantile(xs, 0.95),
        'max': max(xs),
    }


def _fmt_pct(v):
    if v is None:
        return 'n/a'
    return f"{v:.4f}%"


def _fmt_ms(v):
    if v is None:
        return 'n/a'
    return f"{v:.0f}ms"


def _print_metric(title: str, stats: dict, unit: str):
    if not stats:
        print(f"\n{title}: n/a")
        return

    if unit == '%':
        fmt = _fmt_pct
    else:
        fmt = _fmt_ms

    print(f"\n{title} (n={stats['count']}):")
    print(f"  mean: {fmt(stats['mean'])}")
    print(f"  p50:  {fmt(stats['p50'])}")
    print(f"  p75:  {fmt(stats['p75'])}")
    print(f"  p90:  {fmt(stats['p90'])}")
    print(f"  p95:  {fmt(stats['p95'])}")
    print(f"  max:  {fmt(stats['max'])}")


def main():
    load_dotenv()

    lookback_hours = int(os.getenv('LOOKBACK_HOURS', '24'))

    password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
    db_url = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{password}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    engine = create_engine(db_url)

    query = text(f"""
    SELECT
        t.id,
        t.created_at,
        t.symbol,
        t.direction,
        t.entry_price,
        t.exit_price,
        t.net_pnl_usdt,
        t.is_live_trade,
        t.is_dry_run,
        t.entry_slippage_pct,
        t.exit_slippage_pct,
        t.spread_at_entry_pct,
        t.spread_at_exit_pct,
        t.entry_latency_ms,
        t.exit_latency_ms,
        t.signal_to_fill_slippage_pct
    FROM trades t
    WHERE t.created_at > NOW() - INTERVAL '{lookback_hours} hours'
    ORDER BY t.created_at DESC
    """)

    with engine.connect() as conn:
        result = conn.execute(query)
        rows = result.fetchall()
        cols = list(result.keys())

    trades = [dict(zip(cols, row)) for row in rows]

    print("=" * 80)
    print("MARKET EXECUTION COSTS - SLIPPAGE / SPREAD / LATENCY")
    print("=" * 80)
    print(f"Lookback: last {lookback_hours} hours")
    print(f"Trades fetched: {len(trades)}")

    def is_real_live(t):
        return bool(t.get('is_live_trade')) and (t.get('is_dry_run') is False)

    real_live = [t for t in trades if is_real_live(t)]
    all_live = [t for t in trades if bool(t.get('is_live_trade'))]

    if not real_live:
        print("\n⚠️ Aucun trade LIVE RÉEL (is_live_trade=true, is_dry_run=false) trouvé sur la période.")

    def report(group_name: str, group):
        print("\n" + "-" * 80)
        print(f"SCOPE: {group_name}")
        print(f"Trades: {len(group)}")

        exit_slip = [_to_float(t.get('exit_slippage_pct')) for t in group]
        entry_slip = [_to_float(t.get('entry_slippage_pct')) for t in group]
        spread_entry = [_to_float(t.get('spread_at_entry_pct')) for t in group]
        spread_exit = [_to_float(t.get('spread_at_exit_pct')) for t in group]
        sig_to_fill = [_to_float(t.get('signal_to_fill_slippage_pct')) for t in group]

        entry_lat = [_to_float(t.get('entry_latency_ms')) for t in group]
        exit_lat = [_to_float(t.get('exit_latency_ms')) for t in group]

        _print_metric('Exit slippage vs current_price', _summarize(exit_slip), '%')
        _print_metric('Entry slippage vs intended entry_price', _summarize(entry_slip), '%')
        _print_metric('Spread at entry (logged)', _summarize(spread_entry), '%')
        _print_metric('Spread at exit (logged)', _summarize(spread_exit), '%')
        _print_metric('Signal-to-fill slippage (logged)', _summarize(sig_to_fill), '%')

        _print_metric('Entry latency', _summarize(entry_lat), 'ms')
        _print_metric('Exit latency', _summarize(exit_lat), 'ms')

        exit_stats = _summarize(exit_slip)
        if exit_stats:
            print("\nRecommended buffers (for market-only Quick Exit):")
            print(f"  ANALYSIS_SLIPPAGE_PCT (p50): {_fmt_pct(exit_stats['p50'])}")
            print(f"  ANALYSIS_SLIPPAGE_PCT (p90): {_fmt_pct(exit_stats['p90'])}")
            print(f"  ANALYSIS_SLIPPAGE_PCT (p95): {_fmt_pct(exit_stats['p95'])}")

    report('REAL LIVE trades only (is_live_trade=true, is_dry_run=false)', real_live)
    report('ALL LIVE trades (is_live_trade=true)', all_live)
    report('ALL trades (no filter)', trades)


if __name__ == '__main__':
    main()
