#!/usr/bin/env python3
"""
Analyse detaillee de la performance des trades recents.
Identifie les causes principales des pertes.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def analyze():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Recuperer les 39 trades les plus recents
    cur.execute("""
        SELECT 
            t.id,
            t.symbol,
            t.direction,
            t.entry_price,
            t.exit_price,
            t.net_pnl_pct,
            t.net_pnl_usdt,
            t.exit_reason,
            t.duration_seconds,
            t.created_at,
            t.ml_confidence,
            tam.entry_atr_pct_1m,
            tam.entry_atr_pct_5m,
            tam.param_atr_mult_sl,
            tam.param_atr_mult_tp,
            tam.param_be_atr_mult,
            tam.param_trailing_trigger_mult,
            tam.calculated_sl_pct,
            tam.calculated_tp_pct,
            tam.be_triggered,
            tam.trailing_activated,
            tam.stagnation_detected,
            tam.max_pnl_reached,
            tam.min_pnl_reached,
            tam.market_volatility_state,
            tam.market_trend_state,
            tam.session_market,
            tam.hour_utc
        FROM trades t
        LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
        ORDER BY t.created_at DESC
        LIMIT 39
    """)
    
    trades = cur.fetchall()
    cur.close()
    conn.close()
    
    print("=" * 80)
    print("ANALYSE PERFORMANCE - 39 TRADES RECENTS")
    print("=" * 80)
    
    # Stats globales
    total_pnl = sum(t['net_pnl_pct'] or 0 for t in trades)
    total_usdt = sum(t['net_pnl_usdt'] or 0 for t in trades)
    wins = [t for t in trades if (t['net_pnl_pct'] or 0) > 0]
    losses = [t for t in trades if (t['net_pnl_pct'] or 0) < 0]
    breakeven = [t for t in trades if (t['net_pnl_pct'] or 0) == 0]
    
    print(f"\n{'='*40}")
    print("STATS GLOBALES")
    print(f"{'='*40}")
    print(f"Total trades:     {len(trades)}")
    print(f"Wins:             {len(wins)} ({len(wins)/len(trades)*100:.1f}%)")
    print(f"Losses:           {len(losses)} ({len(losses)/len(trades)*100:.1f}%)")
    print(f"Breakeven:        {len(breakeven)}")
    print(f"PnL total:        {total_pnl:+.2f}%")
    print(f"PnL USDT:         {total_usdt:+.2f} USDT")
    print(f"PnL moyen/trade:  {total_pnl/len(trades):+.3f}%")
    
    if wins:
        avg_win = sum(t['net_pnl_pct'] for t in wins) / len(wins)
        print(f"Gain moyen:       +{avg_win:.3f}%")
    if losses:
        avg_loss = sum(t['net_pnl_pct'] for t in losses) / len(losses)
        print(f"Perte moyenne:    {avg_loss:.3f}%")
    
    # Profit Factor
    gross_profit = sum(t['net_pnl_pct'] for t in wins) if wins else 0
    gross_loss = abs(sum(t['net_pnl_pct'] for t in losses)) if losses else 1
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    print(f"Profit Factor:    {pf:.2f}")
    
    # Exit reasons
    print(f"\n{'='*40}")
    print("CAUSES DE SORTIE")
    print(f"{'='*40}")
    exit_stats = defaultdict(lambda: {'count': 0, 'pnl': 0})
    for t in trades:
        reason = t['exit_reason'] or 'UNKNOWN'
        exit_stats[reason]['count'] += 1
        exit_stats[reason]['pnl'] += t['net_pnl_pct'] or 0
    
    for reason, stats in sorted(exit_stats.items(), key=lambda x: -x[1]['count']):
        avg_pnl = stats['pnl'] / stats['count']
        print(f"  {reason:25} | {stats['count']:3} trades | PnL: {stats['pnl']:+.2f}% | Avg: {avg_pnl:+.3f}%")
    
    # Direction
    print(f"\n{'='*40}")
    print("PAR DIRECTION")
    print(f"{'='*40}")
    for direction in ['LONG', 'SHORT']:
        dir_trades = [t for t in trades if t['direction'] == direction]
        if dir_trades:
            dir_pnl = sum(t['net_pnl_pct'] or 0 for t in dir_trades)
            dir_wins = len([t for t in dir_trades if (t['net_pnl_pct'] or 0) > 0])
            print(f"  {direction:6} | {len(dir_trades):3} trades | WR: {dir_wins/len(dir_trades)*100:.1f}% | PnL: {dir_pnl:+.2f}%")
    
    # Volatilite
    print(f"\n{'='*40}")
    print("PAR REGIME VOLATILITE")
    print(f"{'='*40}")
    for regime in ['LOW', 'MEDIUM', 'HIGH', None]:
        reg_trades = [t for t in trades if t['market_volatility_state'] == regime]
        if reg_trades:
            reg_pnl = sum(t['net_pnl_pct'] or 0 for t in reg_trades)
            reg_wins = len([t for t in reg_trades if (t['net_pnl_pct'] or 0) > 0])
            label = regime or 'N/A'
            print(f"  {label:8} | {len(reg_trades):3} trades | WR: {reg_wins/len(reg_trades)*100:.1f}% | PnL: {reg_pnl:+.2f}%")
    
    # Session
    print(f"\n{'='*40}")
    print("PAR SESSION MARCHE")
    print(f"{'='*40}")
    session_stats = defaultdict(lambda: {'count': 0, 'pnl': 0, 'wins': 0})
    for t in trades:
        session = t['session_market'] or 'UNKNOWN'
        session_stats[session]['count'] += 1
        session_stats[session]['pnl'] += t['net_pnl_pct'] or 0
        if (t['net_pnl_pct'] or 0) > 0:
            session_stats[session]['wins'] += 1
    
    for session, stats in sorted(session_stats.items(), key=lambda x: -x[1]['count']):
        wr = stats['wins'] / stats['count'] * 100 if stats['count'] > 0 else 0
        print(f"  {session:12} | {stats['count']:3} trades | WR: {wr:.1f}% | PnL: {stats['pnl']:+.2f}%")
    
    # Duree des trades
    print(f"\n{'='*40}")
    print("DUREE DES TRADES")
    print(f"{'='*40}")
    durations = [t['duration_seconds'] for t in trades if t['duration_seconds']]
    if durations:
        avg_duration = sum(durations) / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        print(f"  Duree moyenne:  {avg_duration:.0f}s ({avg_duration/60:.1f}min)")
        print(f"  Duree min:      {min_duration}s")
        print(f"  Duree max:      {max_duration}s ({max_duration/60:.1f}min)")
        
        # Duree par resultat
        win_dur = [t['duration_seconds'] for t in wins if t['duration_seconds']]
        loss_dur = [t['duration_seconds'] for t in losses if t['duration_seconds']]
        if win_dur:
            print(f"  Duree wins:     {sum(win_dur)/len(win_dur):.0f}s")
        if loss_dur:
            print(f"  Duree losses:   {sum(loss_dur)/len(loss_dur):.0f}s")
    
    # ML Confidence
    print(f"\n{'='*40}")
    print("ML CONFIDENCE")
    print(f"{'='*40}")
    ml_trades = [t for t in trades if t['ml_confidence'] is not None]
    if ml_trades:
        avg_ml = sum(t['ml_confidence'] for t in ml_trades) / len(ml_trades)
        print(f"  ML Confidence moyenne: {avg_ml:.1f}%")
        
        # Par bucket
        for bucket_min in [0, 50, 60, 70, 80]:
            bucket_max = bucket_min + 10 if bucket_min < 80 else 100
            bucket_trades = [t for t in ml_trades if bucket_min <= (t['ml_confidence'] or 0) < bucket_max]
            if bucket_trades:
                bucket_pnl = sum(t['net_pnl_pct'] or 0 for t in bucket_trades)
                bucket_wins = len([t for t in bucket_trades if (t['net_pnl_pct'] or 0) > 0])
                wr = bucket_wins / len(bucket_trades) * 100
                print(f"  [{bucket_min}-{bucket_max}%]: {len(bucket_trades):3} trades | WR: {wr:.1f}% | PnL: {bucket_pnl:+.2f}%")
    
    # Symbols
    print(f"\n{'='*40}")
    print("TOP 5 PIRES SYMBOLS")
    print(f"{'='*40}")
    symbol_stats = defaultdict(lambda: {'count': 0, 'pnl': 0})
    for t in trades:
        symbol_stats[t['symbol']]['count'] += 1
        symbol_stats[t['symbol']]['pnl'] += t['net_pnl_pct'] or 0
    
    worst_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'])[:5]
    for symbol, stats in worst_symbols:
        print(f"  {symbol:20} | {stats['count']} trades | PnL: {stats['pnl']:+.2f}%")
    
    # Stagnation / BE / Trailing
    print(f"\n{'='*40}")
    print("MECANISMES DE SORTIE")
    print(f"{'='*40}")
    be_trades = [t for t in trades if t['be_triggered']]
    trail_trades = [t for t in trades if t['trailing_activated']]
    stag_trades = [t for t in trades if t['stagnation_detected']]
    
    print(f"  Break-Even declenche:   {len(be_trades):3} trades")
    if be_trades:
        be_pnl = sum(t['net_pnl_pct'] or 0 for t in be_trades)
        print(f"    -> PnL apres BE: {be_pnl:+.2f}%")
    
    print(f"  Trailing active:        {len(trail_trades):3} trades")
    if trail_trades:
        trail_pnl = sum(t['net_pnl_pct'] or 0 for t in trail_trades)
        print(f"    -> PnL apres Trail: {trail_pnl:+.2f}%")
    
    print(f"  Stagnation detectee:    {len(stag_trades):3} trades")
    if stag_trades:
        stag_pnl = sum(t['net_pnl_pct'] or 0 for t in stag_trades)
        print(f"    -> PnL apres Stag: {stag_pnl:+.2f}%")
    
    # Max PnL atteint vs PnL final
    print(f"\n{'='*40}")
    print("ANALYSE MFE (Max Favorable Excursion)")
    print(f"{'='*40}")
    mfe_trades = [t for t in trades if t['max_pnl_reached'] is not None]
    if mfe_trades:
        total_mfe = sum(t['max_pnl_reached'] or 0 for t in mfe_trades)
        total_final = sum(t['net_pnl_pct'] or 0 for t in mfe_trades)
        lost_profit = total_mfe - total_final
        
        print(f"  Max PnL cumule atteint: +{total_mfe:.2f}%")
        print(f"  PnL final cumule:       {total_final:+.2f}%")
        print(f"  Profit PERDU (slippage): {lost_profit:.2f}%")
        
        # Trades ou on a perdu le plus de profit
        profit_lost = [(t, (t['max_pnl_reached'] or 0) - (t['net_pnl_pct'] or 0)) for t in mfe_trades]
        profit_lost.sort(key=lambda x: -x[1])
        
        print(f"\n  TOP 5 trades avec le plus de profit perdu:")
        for t, lost in profit_lost[:5]:
            print(f"    {t['symbol']:20} | MaxPnL: +{t['max_pnl_reached']:.2f}% -> Final: {t['net_pnl_pct']:+.2f}% | Perdu: {lost:.2f}%")

if __name__ == '__main__':
    analyze()
