"""
🎬 FILM DES 21 DERNIERS TRADES
Reconstitue la timeline complète des 21 derniers trades
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

def get_last_trades_with_metrics(limit=21):
    """Récupérer les derniers trades avec leurs métriques"""
    cur.execute("""
        SELECT t.*, m.*
        FROM trades t
        JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
        WHERE t.exit_price IS NOT NULL
        ORDER BY t.timestamp_exit DESC
        LIMIT %s
    """, (limit,))
    return cur.fetchall()

def print_trade_summary(trade, index, total):
    """Afficher un résumé d'un trade"""
    symbol = trade.get('symbol', 'N/A')
    direction = trade.get('direction', 'N/A')
    pnl = float(trade.get('pnl_pct', 0))
    pnl_usdt = float(trade.get('pnl_usdt', 0)) if trade.get('pnl_usdt') else 0
    exit_reason = trade.get('exit_reason', 'N/A')
    ts_exit = trade.get('timestamp_exit')
    
    # Métriques
    mfe = trade.get('max_pnl_reached')
    mae = trade.get('min_pnl_reached')
    be_triggered = trade.get('be_triggered', False)
    trailing_activated = trade.get('trailing_activated', False)
    stagnation = trade.get('stagnation_detected', False)
    
    # Durée
    if ts_exit and trade.get('timestamp_entry'):
        duration = (ts_exit - trade.get('timestamp_entry')).total_seconds()
        duration_str = f"{duration/60:.1f}min"
    else:
        duration_str = "?"
    
    # Couleurs et icônes
    pnl_color = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
    
    # Exit reason
    exit_icons = {
        'TS': '🎢',
        'SL': '❌',
        'TP': '✅',
        'SL_EXCHANGE': '🏦',
        'STAGNATION': '⏰',
        'STAGNATION_POSITIVE': '📉',
        'MFE_PROTECT': '🛡️'
    }
    exit_icon = exit_icons.get(exit_reason, '❓')
    
    # Ligne de résumé
    print(f"\n{pnl_color} #{total-index} | {symbol:<15} | {direction:<5} | {pnl:+6.3f}% ({pnl_usdt:+7.4f} USDT) | {exit_icon}{exit_reason:<12} | {duration_str:>6}")
    
    # Métriques détaillées
    details = []
    if mfe is not None:
        details.append(f"MFE:+{mfe:.3f}%")
    if mae is not None:
        details.append(f"MAE:{mae:.3f}%")
    if be_triggered:
        details.append("BE:✅")
    if trailing_activated:
        details.append("Trail:✅")
    if stagnation:
        details.append("Stag:⚠️")
    
    if details:
        print(f"    └─ {' | '.join(details)}")

def print_film_detailed(trade, index):
    """Afficher le film détaillé d'un trade"""
    symbol = trade.get('symbol', 'N/A')
    direction = trade.get('direction', 'N/A')
    entry = float(trade.get('entry_price', 0))
    exit_p = float(trade.get('exit_price', 0))
    sl = float(trade.get('sl_price', 0)) if trade.get('sl_price') else 0
    tp = float(trade.get('tp_price', 0)) if trade.get('tp_price') else 0
    pnl = float(trade.get('pnl_pct', 0))
    exit_reason = trade.get('exit_reason', 'N/A')
    
    ts_entry = trade.get('timestamp_entry')
    ts_exit = trade.get('timestamp_exit')
    duration = (ts_exit - ts_entry).total_seconds() if ts_entry and ts_exit else 0
    
    # Métriques
    mfe = trade.get('max_pnl_reached')
    mae = trade.get('min_pnl_reached')
    max_price = trade.get('max_price_reached')
    min_price = trade.get('min_price_reached')
    time_to_mfe = trade.get('time_to_max_pnl_seconds')
    time_to_mae = trade.get('time_to_min_pnl_seconds')
    
    be_triggered = trade.get('be_triggered', False)
    be_at = trade.get('be_triggered_at')
    be_pnl = trade.get('be_triggered_pnl_pct')
    
    trailing_activated = trade.get('trailing_activated', False)
    trailing_at = trade.get('trailing_activated_at')
    trailing_final_sl = trade.get('trailing_final_sl_price')
    trailing_distance = trade.get('trailing_final_distance_pct')
    
    print(f"\n{'─'*80}")
    print(f"🎬 TRADE #{index} - {symbol} | {direction}")
    print(f"{'─'*80}")
    
    # Infos principales
    print(f"\n📊 Durée: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"   Entry: {entry:.6f} | Exit: {exit_p:.6f}")
    print(f"   SL: {sl:.6f} | TP: {tp:.6f}")
    print(f"   Résultat: {pnl:+.3f}% | Exit: {exit_reason}")
    
    # Timeline
    print(f"\n📽️ Timeline:")
    events = []
    
    # Ouverture
    events.append(('T+0s', '🟢 OUVERTURE', f"{direction} @ {entry:.6f}"))
    
    # MAE
    if time_to_mae and mae is not None:
        events.append((f"T+{time_to_mae:.0f}s", '📉 MAE', f"PnL: {mae:+.3f}%"))
    
    # MFE
    if time_to_mfe and mfe is not None:
        events.append((f"T+{time_to_mfe:.0f}s", '📈 MFE', f"PnL: +{mfe:.3f}%"))
    
    # BE
    if be_triggered:
        events.append(('T+?s', '🛡️ BREAK-EVEN', f"SL → Entry"))
    
    # Trailing
    if trailing_activated:
        events.append(('T+?s', '🎢 TRAILING', f"Distance: {trailing_distance:.2f}%"))
    
    # Fermeture
    events.append((f"T+{duration:.0f}s", '🔴 FERMETURE', f"{exit_reason} @ {exit_p:.6f}"))
    
    for time, icon, detail in events:
        print(f"   {icon} [{time:<8}] {detail}")
    
    # Métriques
    print(f"\n📊 Métriques:")
    print(f"   MFE: +{mfe:.3f}%" if mfe else "   MFE: N/A")
    print(f"   MAE: {mae:.3f}%" if mae else "   MAE: N/A")
    print(f"   Break-Even: {'✅' if be_triggered else '❌'}")
    print(f"   Trailing: {'✅' if trailing_activated else '❌'}")
    
    if mfe and mfe > 0:
        capture = pnl / mfe * 100
        print(f"   Capture MFE: {capture:.1f}%")

# Exécuter
print("="*80)
print("🎬 FILM DES 21 DERNIERS TRADES")
print("="*80)

trades = get_last_trades_with_metrics(21)

if not trades:
    print("❌ Aucun trade trouvé avec métriques")
else:
    print(f"\n📊 {len(trades)} trades trouvés\n")
    
    # Résumé rapide
    print("📋 RÉSUMÉ RAPIDE:")
    print("-"*80)
    
    for i, trade in enumerate(trades):
        print_trade_summary(dict(trade), i, len(trades))
    
    # Stats globales
    print(f"\n{'='*80}")
    print("📈 STATISTIQUES")
    print(f"{'='*80}")
    
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if float(t.get('pnl_pct', 0)) > 0)
    losing_trades = sum(1 for t in trades if float(t.get('pnl_pct', 0)) < 0)
    total_pnl = sum(float(t.get('pnl_pct', 0)) for t in trades)
    total_usdt = sum(float(t.get('pnl_usdt', 0) or 0) for t in trades)
    
    print(f"\n📊 Performance:")
    print(f"   Total trades: {total_trades}")
    print(f"   Gagnants: {winning_trades} ({winning_trades/total_trades*100:.0f}%)")
    print(f"   Perdants: {losing_trades} ({losing_trades/total_trades*100:.0f}%)")
    print(f"   PnL total: {total_pnl:+.3f}% ({total_usdt:+.4f} USDT)")
    
    # Exit reasons
    print(f"\n🏁 Raisons de sortie:")
    exit_counts = {}
    for t in trades:
        reason = t.get('exit_reason', 'N/A')
        exit_counts[reason] = exit_counts.get(reason, 0) + 1
    
    for reason, count in sorted(exit_counts.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_trades * 100
        print(f"   {reason}: {count} ({pct:.0f}%)")
    
    # Métriques moyennes
    print(f"\n📊 Métriques moyennes:")
    mfes = [t.get('max_pnl_reached') for t in trades if t.get('max_pnl_reached') is not None]
    maes = [t.get('min_pnl_reached') for t in trades if t.get('min_pnl_reached') is not None]
    
    if mfes:
        avg_mfe = sum(mfes) / len(mfes)
        print(f"   MFE moyen: +{avg_mfe:.3f}%")
    if maes:
        avg_mae = sum(maes) / len(maes)
        print(f"   MAE moyen: {avg_mae:.3f}%")
    
    be_count = sum(1 for t in trades if t.get('be_triggered', False))
    trail_count = sum(1 for t in trades if t.get('trailing_activated', False))
    stag_count = sum(1 for t in trades if t.get('stagnation_detected', False))
    
    print(f"   Break-even activé: {be_count}/{total_trades} ({be_count/total_trades*100:.0f}%)")
    print(f"   Trailing activé: {trail_count}/{total_trades} ({trail_count/total_trades*100:.0f}%)")
    print(f"   Stagnation détectée: {stag_count}/{total_trades} ({stag_count/total_trades*100:.0f}%)")

cur.close()
conn.close()
print("="*80)
