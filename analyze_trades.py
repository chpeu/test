#!/usr/bin/env python3
"""Analyse des trades du jour"""
import json
from datetime import datetime



def main():
    with open('trade_history_instance_5000.json', 'r') as f:
        trades = json.load(f)

    # Filtrer les trades du 4 décembre 2025
    today_trades = [t for t in trades if '2025-12-04' in t.get('timestamp', '')]

    print("=" * 60)
    print("TRADES DU 4 DECEMBRE 2025")
    print("=" * 60)
    print(f"Total: {len(today_trades)} trades\n")

    # Stats
    wins = [t for t in today_trades if t.get('net_pnl_usdt', 0) > 0]
    losses = [t for t in today_trades if t.get('net_pnl_usdt', 0) <= 0]

    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    winrate = len(wins) / len(today_trades) * 100 if today_trades else 0
    print(f"Winrate: {winrate:.1f}%\n")

    # PnL total
    total_pnl = sum(t.get('net_pnl_usdt', 0) for t in today_trades)
    print(f"PnL Total: {total_pnl:.4f} USDT\n")

    # Par raison de cloture
    print("=" * 60)
    print("PAR RAISON DE CLOTURE")
    print("=" * 60)
    reasons = {}
    for t in today_trades:
        r = t.get('reason', 'UNKNOWN')
        if r not in reasons:
            reasons[r] = {'count': 0, 'pnl': 0, 'wins': 0}
        reasons[r]['count'] += 1
        reasons[r]['pnl'] += t.get('net_pnl_usdt', 0)
        if t.get('net_pnl_usdt', 0) > 0:
            reasons[r]['wins'] += 1

    for r, data in sorted(reasons.items(), key=lambda x: -x[1]['count']):
        wr = data['wins'] / data['count'] * 100 if data['count'] > 0 else 0
        print(f"{r:20} | {data['count']:3} trades | WR: {wr:5.1f}% | PnL: {data['pnl']:+.4f} USDT")

    # Chercher LINK trades
    print("\n" + "=" * 60)
    print("TRADES LINK")
    print("=" * 60)
    link_trades = [t for t in today_trades if 'LINK' in t.get('symbol', '')]
    for t in link_trades:
        ts = t.get('timestamp', '')
        time_part = ts.split('T')[1][:8] if 'T' in ts else ''
        pnl_pct = t.get('net_pnl_pct', 0)
        pnl_usdt = t.get('net_pnl_usdt', 0)
        print(f"{time_part} | {t.get('direction'):5} | Entry: {t.get('entry'):8} | Exit: {t.get('exit'):8} | PnL: {pnl_pct:+.4f}% ({pnl_usdt:+.4f} USDT) | {t.get('reason')}")

    # Chercher trades avec PnL > 0.5% (gros trades)
    print("\n" + "=" * 60)
    print("TRADES AVEC PNL > 0.5% (absolue)")
    print("=" * 60)
    big_trades = [t for t in today_trades if abs(t.get('net_pnl_pct', 0)) > 0.5]
    for t in sorted(big_trades, key=lambda x: x.get('timestamp', '')):
        ts = t.get('timestamp', '')
        time_part = ts.split('T')[1][:8] if 'T' in ts else ''
        pnl_pct = t.get('net_pnl_pct', 0)
        pnl_usdt = t.get('net_pnl_usdt', 0)
        symbol = t.get('symbol', '').replace('/USDT:USDT', '')
        print(f"{time_part} | {symbol:6} | {t.get('direction'):5} | PnL: {pnl_pct:+.4f}% ({pnl_usdt:+.4f} USDT) | {t.get('reason')}")

    # Chercher trades autour de 16h
    print("\n" + "=" * 60)
    print("TRADES AUTOUR DE 16H")
    print("=" * 60)
    for t in today_trades:
        ts = t.get('timestamp', '')
        if 'T16:' in ts or 'T15:' in ts or 'T17:' in ts:
            time_part = ts.split('T')[1][:8] if 'T' in ts else ''
            pnl_pct = t.get('net_pnl_pct', 0)
            pnl_usdt = t.get('net_pnl_usdt', 0)
            symbol = t.get('symbol', '').replace('/USDT:USDT', '')
            print(f"{time_part} | {symbol:6} | {t.get('direction'):5} | Entry: {t.get('entry')} | Exit: {t.get('exit')} | PnL: {pnl_pct:+.4f}% ({pnl_usdt:+.4f} USDT) | {t.get('reason')}")

    # Analyser les incohérences potentielles
    print("\n" + "=" * 60)
    print("VERIFICATION COHERENCE PNL")
    print("=" * 60)
    issues = []
    for t in today_trades:
        entry = t.get('entry', 0)
        exit_price = t.get('exit', 0)
        direction = t.get('direction', '')
        pnl_pct_recorded = t.get('net_pnl_pct', 0)
        size_usdt = t.get('size_initial_usdt', t.get('size', 25))
        
        if entry and exit_price and entry > 0:
            # Calculer le PnL theorique
            if direction == 'LONG':
                expected_pnl_pct = ((exit_price - entry) / entry) * 100
            else:
                expected_pnl_pct = ((entry - exit_price) / entry) * 100
            
            # Comparer (avec tolerance pour slippage/fees)
            diff = abs(pnl_pct_recorded - expected_pnl_pct)
            if diff > 0.5:  # Plus de 0.5% de difference
                ts = t.get('timestamp', '')
                time_part = ts.split('T')[1][:8] if 'T' in ts else ''
                symbol = t.get('symbol', '').replace('/USDT:USDT', '')
                issues.append({
                    'time': time_part,
                    'symbol': symbol,
                    'direction': direction,
                    'entry': entry,
                    'exit': exit_price,
                    'recorded_pnl': pnl_pct_recorded,
                    'expected_pnl': expected_pnl_pct,
                    'diff': diff,
                    'reason': t.get('reason')
                })

    if issues:
        print(f"Trouvé {len(issues)} trades avec incohérence PnL:")
        for i in issues:
            print(f"  {i['time']} | {i['symbol']:6} | {i['direction']:5} | Entry: {i['entry']} | Exit: {i['exit']}")
            print(f"           PnL enregistré: {i['recorded_pnl']:+.4f}% | PnL attendu: {i['expected_pnl']:+.4f}% | Diff: {i['diff']:.4f}%")
    else:
        print("Aucune incohérence majeure détectée")


if __name__ == '__main__':
    main()
