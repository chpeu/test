import argparse
import sys
import os
import pandas as pd
import numpy as np
from typing import Optional, Tuple, List

# Force UTF-8 for stdout
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le dossier racine au path pour les imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optimization.data.feature_loader import get_sqlalchemy_engine, build_config_filter_conditions


def _profit_factor(net_pnl_series: pd.Series) -> float:
    gains = net_pnl_series[net_pnl_series > 0].sum()
    losses = net_pnl_series[net_pnl_series < 0].sum()
    if losses == 0:
        return float('inf') if gains > 0 else 0.0
    return float(gains / abs(losses))


def _compute_metrics(df: pd.DataFrame) -> dict:
    count = int(len(df))
    if count == 0:
        return {
            'count': 0,
            'winrate': 0.0,
            'total_pnl_usdt': 0.0,
            'avg_pnl_usdt': 0.0,
            'avg_pnl_pct': 0.0,
            'profit_factor': 0.0,
        }

    wins = int((df['net_pnl_usdt'] > 0).sum())
    return {
        'count': count,
        'winrate': (wins / count) * 100.0,
        'total_pnl_usdt': float(df['net_pnl_usdt'].sum()),
        'avg_pnl_usdt': float(df['net_pnl_usdt'].mean()),
        'avg_pnl_pct': float(df['net_pnl_pct'].mean()),
        'profit_factor': _profit_factor(df['net_pnl_usdt']),
    }


def _format_pf(pf: float) -> str:
    if pf == float('inf'):
        return "inf"
    return f"{pf:.2f}"


def load_trades(timeframe_days: int, use_training_filter: bool) -> pd.DataFrame:
    engine = get_sqlalchemy_engine()

    where_clauses = [
        "t.timestamp_entry IS NOT NULL",
        "t.net_pnl_usdt IS NOT NULL",
        "t.timestamp_entry > NOW() - INTERVAL '%(days)s days'",
    ]

    if use_training_filter:
        where_clauses.extend(build_config_filter_conditions(for_trades_table=True, use_alias=True))

    query = f"""
        SELECT
            t.id AS trade_id,
            t.timestamp_entry AS opened_at,
            t.timestamp_exit AS closed_at,
            t.symbol,
            t.direction,
            t.scan_log_id,
            COALESCE(t.ml_confidence, s.ml_confidence) AS ml_confidence,
            t.net_pnl_usdt,
            t.net_pnl_pct,
            t.is_live_trade,
            t.tp_sl_mode,
            t.exit_reason,
            s.session_market,
            t.entry_market_regime
        FROM trades t
        LEFT JOIN scan_logs s ON t.scan_log_id = s.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY t.timestamp_entry ASC
    """

    df = pd.read_sql(query, engine, params={'days': timeframe_days})

    if df.empty:
        return df

    df['opened_at'] = pd.to_datetime(df['opened_at'])
    df['ml_confidence'] = pd.to_numeric(df['ml_confidence'], errors='coerce').fillna(0.0)
    df['net_pnl_usdt'] = pd.to_numeric(df['net_pnl_usdt'], errors='coerce').fillna(0.0)
    df['net_pnl_pct'] = pd.to_numeric(df['net_pnl_pct'], errors='coerce').fillna(0.0)

    return df


def split_train_test(df: pd.DataFrame, test_ratio: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df

    df_sorted = df.sort_values('opened_at')
    test_size = int(max(1, round(len(df_sorted) * test_ratio)))
    if test_size >= len(df_sorted):
        return df_sorted.iloc[:0].copy(), df_sorted.copy()

    return df_sorted.iloc[:-test_size].copy(), df_sorted.iloc[-test_size:].copy()


def build_threshold_grid(step: int) -> List[int]:
    step = max(1, int(step))
    thresholds = list(range(0, 101, step))
    if thresholds[-1] != 100:
        thresholds.append(100)
    return thresholds


def run_ev_analysis(timeframe_days: int, test_ratio: float, step: int, use_training_filter: bool) -> dict:
    """
    Run EV analysis and return structured data (for API consumption).
    Returns dict with all analysis results.
    """
    df = load_trades(timeframe_days=timeframe_days, use_training_filter=use_training_filter)
    if df.empty:
        return {'error': 'Aucun trade trouvé (dataset vide)', 'trades_count': 0}

    total_trades = len(df)
    with_ml = int((df['ml_confidence'] > 0).sum())

    df_train, df_test = split_train_test(df, test_ratio=test_ratio)
    thresholds = build_threshold_grid(step)

    rows = []
    for thr in thresholds:
        train_subset = df_train[df_train['ml_confidence'] >= thr]
        test_subset = df_test[df_test['ml_confidence'] >= thr]

        m_train = _compute_metrics(train_subset)
        m_test = _compute_metrics(test_subset)

        rows.append({
            'threshold_pct': thr,
            'train_count': m_train['count'],
            'train_retention_pct': round((m_train['count'] / len(df_train) * 100.0) if len(df_train) else 0.0, 1),
            'train_wr': round(m_train['winrate'], 1),
            'train_avg_pnl_pct': round(m_train['avg_pnl_pct'], 3),
            'train_total_pnl_usdt': round(m_train['total_pnl_usdt'], 2),
            'train_pf': round(m_train['profit_factor'], 2) if m_train['profit_factor'] != float('inf') else 999.0,
            'test_count': m_test['count'],
            'test_retention_pct': round((m_test['count'] / len(df_test) * 100.0) if len(df_test) else 0.0, 1),
            'test_wr': round(m_test['winrate'], 1),
            'test_avg_pnl_pct': round(m_test['avg_pnl_pct'], 3),
            'test_total_pnl_usdt': round(m_test['total_pnl_usdt'], 2),
            'test_pf': round(m_test['profit_factor'], 2) if m_test['profit_factor'] != float('inf') else 999.0,
        })

    results_df = pd.DataFrame(rows)

    def _pick_best(min_retention_pct: Optional[float]) -> Optional[dict]:
        dfc = results_df.copy()
        dfc = dfc[dfc['train_count'] >= 20]
        if min_retention_pct is not None:
            dfc = dfc[dfc['train_retention_pct'] >= float(min_retention_pct)]
        if dfc.empty:
            return None
        best_row = dfc.sort_values('train_total_pnl_usdt', ascending=False).iloc[0]
        return best_row.to_dict()

    best_unconstrained = _pick_best(None)
    best_keep_80 = _pick_best(80.0)
    best_keep_90 = _pick_best(90.0)

    # Buckets analysis
    bucket_size = 5
    df_b = df.copy()
    df_b['bucket_floor'] = (np.floor(df_b['ml_confidence'] / bucket_size) * bucket_size).clip(0, 100 - bucket_size)
    df_b['bucket'] = df_b['bucket_floor'].astype(int).astype(str) + "-" + (df_b['bucket_floor'] + bucket_size).astype(int).astype(str)
    bucket_stats = (
        df_b.groupby('bucket', as_index=False)
        .agg(
            trades=('trade_id', 'count'),
            winrate=('net_pnl_usdt', lambda s: (s > 0).mean() * 100.0),
            avg_pnl_pct=('net_pnl_pct', 'mean'),
            total_pnl_usdt=('net_pnl_usdt', 'sum'),
            profit_factor=('net_pnl_usdt', _profit_factor),
        )
        .sort_values('bucket')
    )
    buckets_list = []
    for _, r in bucket_stats.iterrows():
        pf_val = float(r['profit_factor'])
        buckets_list.append({
            'bucket': r['bucket'],
            'trades': int(r['trades']),
            'winrate': round(float(r['winrate']), 1),
            'avg_pnl_pct': round(float(r['avg_pnl_pct']), 3),
            'total_pnl_usdt': round(float(r['total_pnl_usdt']), 2),
            'profit_factor': round(pf_val, 2) if pf_val != float('inf') else 999.0,
        })

    return {
        'period': {
            'start': df['opened_at'].min().isoformat() if not df.empty else None,
            'end': df['opened_at'].max().isoformat() if not df.empty else None,
            'days': timeframe_days,
        },
        'trades_count': total_trades,
        'trades_with_ml': with_ml,
        'trades_with_ml_pct': round(with_ml / total_trades * 100, 1) if total_trades else 0,
        'training_filter': use_training_filter,
        'split': {
            'train_count': len(df_train),
            'test_count': len(df_test),
            'test_ratio': test_ratio,
        },
        'best_thresholds': {
            'unconstrained': best_unconstrained,
            'keep_80pct': best_keep_80,
            'keep_90pct': best_keep_90,
        },
        'thresholds_table': rows,
        'buckets': buckets_list,
    }


def analyze_ml_thresholds(timeframe_days: int, test_ratio: float, step: int, use_training_filter: bool):
    """Print-based analysis (CLI usage)."""
    result = run_ev_analysis(timeframe_days, test_ratio, step, use_training_filter)
    if 'error' in result:
        print(f"[ERREUR] {result['error']}")
        return

    print("ANALYSE EV PAR ML_CONFIDENCE (net)")
    print("=" * 100)
    print(f"Période: {result['period']['start']} → {result['period']['end']} | Trades: {result['trades_count']} | Avec ML: {result['trades_with_ml']} ({result['trades_with_ml_pct']:.1f}%)")
    print(f"Filtre training (LIVE+ATR+exit_reason): {'ON' if result['training_filter'] else 'OFF'}")
    print("=" * 100)
    print(f"Split temporel: TRAIN={result['split']['train_count']} trades | TEST={result['split']['test_count']} trades | test_ratio={result['split']['test_ratio']:.2f}")

    print("\nMEILLEURS SEUILS (optimisés sur TRAIN, reportés sur TEST)")
    print("-" * 100)
    best_thresholds = result['best_thresholds']
    for title, key in [
        ("Max PnL (sans contrainte)", 'unconstrained'),
        ("Max PnL (>=80% trades conservés)", 'keep_80pct'),
        ("Max PnL (>=90% trades conservés)", 'keep_90pct'),
    ]:
        best = best_thresholds.get(key)
        if not best:
            print(f"- {title}: N/A (pas assez de données)")
            continue
        thr = int(best['threshold_pct'])
        print(
            f"- {title}: seuil >= {thr}% (cfg gb_min_confidence ~= {thr/100:.2f}) | "
            f"TRAIN pnl={best['train_total_pnl_usdt']:.2f}$ ({best['train_retention_pct']:.1f}% trades) | "
            f"TEST pnl={best['test_total_pnl_usdt']:.2f}$ ({best['test_retention_pct']:.1f}% trades)"
        )

    print("\nTABLE TEST (par seuil) - ordre = total_pnl_usdt desc")
    print("-" * 100)
    thresholds_table = result['thresholds_table']
    sorted_table = sorted(thresholds_table, key=lambda x: x['test_total_pnl_usdt'], reverse=True)[:25]

    print(f"{'SEUIL':>6} | {'KEEP%':>6} | {'N':>5} | {'WR%':>6} | {'EV%':>7} | {'PF':>6} | {'PNL$':>10}")
    print("-" * 100)
    for r in sorted_table:
        print(
            f"{int(r['threshold_pct']):>6} | "
            f"{r['test_retention_pct']:>6.1f} | "
            f"{int(r['test_count']):>5} | "
            f"{r['test_wr']:>6.1f} | "
            f"{r['test_avg_pnl_pct']:>7.3f} | "
            f"{_format_pf(float(r['test_pf'])):>6} | "
            f"{r['test_total_pnl_usdt']:>10.2f}"
        )

    print("\nBUCKETS (tous trades) - EV net par bucket 5%")
    print("-" * 100)
    print(f"{'BUCKET':>10} | {'N':>5} | {'WR%':>6} | {'EV%':>7} | {'PF':>6} | {'PNL$':>10}")
    print("-" * 100)
    for r in result['buckets']:
        print(
            f"{r['bucket']:>10} | "
            f"{int(r['trades']):>5} | "
            f"{float(r['winrate']):>6.1f} | "
            f"{float(r['avg_pnl_pct']):>7.3f} | "
            f"{_format_pf(float(r['profit_factor'])):>6} | "
            f"{float(r['total_pnl_usdt']):>10.2f}"
        )

    print("=" * 100)
    print("Note: cette analyse utilise un lien déterministe trades.scan_log_id -> scan_logs.id (COALESCE avec trades.ml_confidence).")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyse EV net par ml_confidence (choix seuils)")
    parser.add_argument('--days', type=int, default=180, help='Fenêtre en jours à analyser')
    parser.add_argument('--test-ratio', type=float, default=0.30, help='Ratio de trades pour le test (split temporel)')
    parser.add_argument('--step', type=int, default=5, help='Pas des seuils en % (ex: 5 = 0,5,10...)')
    parser.add_argument('--no-training-filter', action='store_true', help='Désactiver filtre training (LIVE+ATR+exit_reason)')
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    analyze_ml_thresholds(
        timeframe_days=int(args.days),
        test_ratio=float(args.test_ratio),
        step=int(args.step),
        use_training_filter=not bool(args.no_training_filter),
    )
