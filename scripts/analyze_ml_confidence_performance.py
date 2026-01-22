#!/usr/bin/env python3
"""
Analyse de la performance des trades par buckets de ml_confidence.
Corrélation entre confiance ML et taux de réussite / PnL.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

def _enable_utf8_stdout() -> None:
    if sys.platform != 'win32':
        return
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def _load_env() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv
        load_dotenv(root_dir / '.env')
    except Exception:
        pass


def _get_db_config() -> Dict[str, Any]:
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }


def _connect():
    import psycopg2
    return psycopg2.connect(**_get_db_config())


def _fetchall(conn, query: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    from psycopg2.extras import RealDictCursor
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else []


def get_bucket(ml_conf: float) -> str:
    """Retourne le bucket de confiance ML."""
    if ml_conf < 40:
        return "< 40%"
    elif ml_conf < 45:
        return "40-45%"
    elif ml_conf < 50:
        return "45-50%"
    elif ml_conf < 55:
        return "50-55%"
    elif ml_conf < 60:
        return "55-60%"
    else:
        return ">= 60%"


def analyze_trades(conn, limit: int = 500) -> Dict[str, Any]:
    """Analyse les derniers trades par bucket de ml_confidence."""
    
    query = f"""
        SELECT
            t.id,
            t.symbol,
            t.direction,
            t.timestamp_entry,
            t.exit_reason,
            t.net_pnl_usdt,
            t.net_pnl_pct,
            t.duration_seconds,
            COALESCE(t.ml_confidence, s.ml_confidence) AS ml_confidence
        FROM trades t
        LEFT JOIN scan_logs s ON t.scan_log_id = s.id
        WHERE t.timestamp_entry IS NOT NULL
          AND t.net_pnl_usdt IS NOT NULL
        ORDER BY t.timestamp_entry DESC
        LIMIT {int(limit)}
    """
    
    rows = _fetchall(conn, query)
    
    # Statistiques par bucket
    buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        'count': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl_usdt': 0.0,
        'total_pnl_pct': 0.0,
        'pnl_list': [],
        'durations': []
    })
    
    # Stats globales
    total_trades = 0
    total_with_ml = 0
    total_without_ml = 0
    
    for r in rows:
        total_trades += 1
        ml_conf = r.get('ml_confidence')
        
        if ml_conf is None:
            total_without_ml += 1
            continue
        
        total_with_ml += 1
        
        try:
            ml_conf = float(ml_conf)
        except:
            continue
        
        bucket = get_bucket(ml_conf)
        pnl_usdt = float(r.get('net_pnl_usdt') or 0)
        pnl_pct = float(r.get('net_pnl_pct') or 0)
        duration = r.get('duration_seconds')
        
        buckets[bucket]['count'] += 1
        buckets[bucket]['total_pnl_usdt'] += pnl_usdt
        buckets[bucket]['total_pnl_pct'] += pnl_pct
        buckets[bucket]['pnl_list'].append(pnl_usdt)
        
        if duration:
            buckets[bucket]['durations'].append(duration)
        
        if pnl_usdt > 0:
            buckets[bucket]['wins'] += 1
        else:
            buckets[bucket]['losses'] += 1
    
    return {
        'total_trades': total_trades,
        'total_with_ml': total_with_ml,
        'total_without_ml': total_without_ml,
        'buckets': dict(buckets)
    }


def print_analysis(analysis: Dict[str, Any]) -> None:
    """Affiche l'analyse formatée."""
    
    print("\n" + "=" * 90)
    print("ANALYSE PERFORMANCE PAR BUCKET ML_CONFIDENCE")
    print("=" * 90)
    
    print(f"\nTotal trades analysés : {analysis['total_trades']}")
    print(f"  - Avec ml_confidence : {analysis['total_with_ml']}")
    print(f"  - Sans ml_confidence : {analysis['total_without_ml']}")
    
    buckets = analysis['buckets']
    
    # Ordre des buckets
    bucket_order = ["< 40%", "40-45%", "45-50%", "50-55%", "55-60%", ">= 60%"]
    
    print("\n" + "-" * 90)
    print(f"{'Bucket':<12} | {'Trades':>7} | {'Wins':>5} | {'Losses':>6} | {'Win Rate':>8} | {'PnL USDT':>12} | {'PnL Moy':>10} | {'Durée Moy':>10}")
    print("-" * 90)
    
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    
    for bucket in bucket_order:
        if bucket not in buckets:
            continue
        
        b = buckets[bucket]
        count = b['count']
        wins = b['wins']
        losses = b['losses']
        total_pnl_usdt = b['total_pnl_usdt']
        durations = b['durations']
        
        win_rate = (wins / count * 100) if count > 0 else 0
        avg_pnl = (total_pnl_usdt / count) if count > 0 else 0
        avg_duration = (sum(durations) / len(durations) / 60) if durations else 0  # en minutes
        
        total_wins += wins
        total_losses += losses
        total_pnl += total_pnl_usdt
        
        print(f"{bucket:<12} | {count:>7} | {wins:>5} | {losses:>6} | {win_rate:>7.1f}% | {total_pnl_usdt:>+11.2f}$ | {avg_pnl:>+9.2f}$ | {avg_duration:>8.1f}min")
    
    print("-" * 90)
    
    total_count = total_wins + total_losses
    overall_win_rate = (total_wins / total_count * 100) if total_count > 0 else 0
    overall_avg_pnl = (total_pnl / total_count) if total_count > 0 else 0
    
    print(f"{'TOTAL':<12} | {total_count:>7} | {total_wins:>5} | {total_losses:>6} | {overall_win_rate:>7.1f}% | {total_pnl:>+11.2f}$ | {overall_avg_pnl:>+9.2f}$ |")
    
    # Recommandations
    print("\n" + "=" * 90)
    print("RECOMMANDATIONS")
    print("=" * 90)
    
    # Trouver le meilleur et pire bucket
    best_bucket = None
    best_win_rate = 0
    worst_bucket = None
    worst_win_rate = 100
    
    for bucket in bucket_order:
        if bucket not in buckets or buckets[bucket]['count'] < 5:
            continue
        b = buckets[bucket]
        wr = (b['wins'] / b['count'] * 100) if b['count'] > 0 else 0
        if wr > best_win_rate:
            best_win_rate = wr
            best_bucket = bucket
        if wr < worst_win_rate:
            worst_win_rate = wr
            worst_bucket = bucket
    
    if best_bucket:
        print(f"\n✅ Meilleur bucket : {best_bucket} (win rate: {best_win_rate:.1f}%)")
    if worst_bucket:
        print(f"❌ Pire bucket : {worst_bucket} (win rate: {worst_win_rate:.1f}%)")
    
    # Seuil actuel
    current_threshold = 47  # gb_min_confidence actuel
    
    # Calculer performance au-dessus et en-dessous du seuil
    above_threshold = {'wins': 0, 'losses': 0, 'pnl': 0.0}
    below_threshold = {'wins': 0, 'losses': 0, 'pnl': 0.0}
    
    threshold_map = {
        "< 40%": 35,
        "40-45%": 42.5,
        "45-50%": 47.5,
        "50-55%": 52.5,
        "55-60%": 57.5,
        ">= 60%": 65
    }
    
    for bucket, midpoint in threshold_map.items():
        if bucket not in buckets:
            continue
        b = buckets[bucket]
        if midpoint >= current_threshold:
            above_threshold['wins'] += b['wins']
            above_threshold['losses'] += b['losses']
            above_threshold['pnl'] += b['total_pnl_usdt']
        else:
            below_threshold['wins'] += b['wins']
            below_threshold['losses'] += b['losses']
            below_threshold['pnl'] += b['total_pnl_usdt']
    
    above_total = above_threshold['wins'] + above_threshold['losses']
    below_total = below_threshold['wins'] + below_threshold['losses']
    
    above_wr = (above_threshold['wins'] / above_total * 100) if above_total > 0 else 0
    below_wr = (below_threshold['wins'] / below_total * 100) if below_total > 0 else 0
    
    print(f"\n📊 Performance par rapport au seuil actuel ({current_threshold}%) :")
    print(f"   - Au-dessus : {above_total} trades, win rate {above_wr:.1f}%, PnL {above_threshold['pnl']:+.2f}$")
    print(f"   - En-dessous : {below_total} trades, win rate {below_wr:.1f}%, PnL {below_threshold['pnl']:+.2f}$")
    
    # Suggestion de seuil optimal
    if above_wr > below_wr + 5:
        print(f"\n💡 Suggestion : Le seuil actuel de {current_threshold}% semble approprié.")
        print(f"   Les trades au-dessus du seuil performent mieux ({above_wr:.1f}% vs {below_wr:.1f}%).")
    elif below_wr > above_wr:
        print(f"\n⚠️ Attention : Les trades en-dessous du seuil performent mieux !")
        print(f"   Considérez baisser le seuil ou recalibrer le modèle ML.")
    else:
        print(f"\n🔍 Le seuil actuel ne semble pas discriminant.")
        print(f"   Considérez une recalibration du modèle ML.")


def main() -> int:
    _enable_utf8_stdout()
    _load_env()
    
    limit = 500
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            pass
    
    print("=" * 90)
    print(f"ANALYSE ML_CONFIDENCE vs PERFORMANCE ({limit} derniers trades)")
    print("=" * 90)
    
    cfg = _get_db_config()
    print(f"Connexion: host={cfg['host']} port={cfg['port']} db={cfg['database']}")
    
    try:
        conn = _connect()
    except Exception as e:
        print(f"[ERREUR] Connexion échouée : {type(e).__name__}: {e}")
        return 1
    
    try:
        analysis = analyze_trades(conn, limit=limit)
        print_analysis(analysis)
        return 0
        
    except Exception as e:
        print(f"[ERREUR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
