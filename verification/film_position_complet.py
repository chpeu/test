"""
🎬 FILM COMPLET D'UNE POSITION - MODE FIXE
Reconstitue la timeline complète d'un trade à partir de la base
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime, timedelta

password = quote_plus("@Cmtr1di12345")
conn = psycopg2.connect(f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml")
cur = conn.cursor(cursor_factory=RealDictCursor)

def get_trade_with_metrics(trade_id=None):
    """Récupérer un trade avec ses métriques"""
    if trade_id:
        cur.execute("""
            SELECT t.*, m.*
            FROM trades t
            JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
            WHERE t.id::text = %s
        """, (trade_id,))
    else:
        # Dernier trade avec métriques
        cur.execute("""
            SELECT t.*, m.*
            FROM trades t
            JOIN trade_atr_metrics m ON t.id = m.trade_id::uuid
            WHERE t.exit_price IS NOT NULL
            ORDER BY t.timestamp_exit DESC
            LIMIT 1
        """)
    return cur.fetchone()

def format_timestamp(ts, start_ts):
    """Formater un timestamp en T+Xs"""
    if not ts or not start_ts:
        return "T+?"
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    delta = (ts - start_ts).total_seconds()
    return f"T+{delta:.0f}s"

def print_film(trade):
    """Afficher le film complet du trade"""
    if not trade:
        print("❌ Aucun trade trouvé avec métriques")
        return
    
    trade = dict(trade)
    
    print("="*80)
    print("🎬 FILM COMPLET DE LA POSITION")
    print("="*80)
    
    # Infos de base
    symbol = trade.get('symbol', 'N/A')
    direction = trade.get('direction', 'N/A')
    entry = float(trade.get('entry_price', 0))
    exit_p = float(trade.get('exit_price', 0))
    sl = float(trade.get('sl_price', 0)) if trade.get('sl_price') else 0
    tp = float(trade.get('tp_price', 0)) if trade.get('tp_price') else 0
    pnl = float(trade.get('pnl_pct', 0))
    pnl_usdt = float(trade.get('pnl_usdt', 0)) if trade.get('pnl_usdt') else 0
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
    be_price = trade.get('be_price_at_trigger')
    
    trailing_activated = trade.get('trailing_activated', False)
    trailing_at = trade.get('trailing_activated_at')
    trailing_final_sl = trade.get('trailing_final_sl_price')
    trailing_distance = trade.get('trailing_final_distance_pct')
    
    stagnation = trade.get('stagnation_detected', False)
    
    session = trade.get('session_market', 'N/A')
    
    # Header
    print(f"\n📊 {symbol} | {direction} | {session}")
    print(f"   Durée: {duration:.0f}s ({duration/60:.1f} min)")
    print(f"   Résultat: {pnl:+.3f}% ({pnl_usdt:+.4f} USDT) | Exit: {exit_reason}")
    
    # Timeline
    print(f"\n{'─'*80}")
    print("📽️ TIMELINE")
    print(f"{'─'*80}")
    
    events = []
    
    # 1. Ouverture
    events.append({
        'time': 0,
        'icon': '🟢',
        'event': 'OUVERTURE',
        'detail': f"{direction} @ {entry:.6f}",
        'extra': f"SL: {sl:.6f} | TP: {tp:.6f}"
    })
    
    # 2. MAE (si avant MFE)
    if time_to_mae and mae is not None:
        events.append({
            'time': time_to_mae,
            'icon': '📉',
            'event': 'MAE (Max Adverse)',
            'detail': f"PnL: {mae:+.3f}%",
            'extra': f"Prix: {min_price}" if min_price else ""
        })
    
    # 3. MFE
    if time_to_mfe and mfe is not None:
        events.append({
            'time': time_to_mfe,
            'icon': '📈',
            'event': 'MFE (Max Favorable)',
            'detail': f"PnL: +{mfe:.3f}%",
            'extra': f"Prix: {max_price}" if max_price else ""
        })
    
    # 4. Break-Even
    if be_triggered and be_at:
        try:
            be_time = datetime.fromisoformat(str(be_at).replace('Z', '+00:00'))
            be_offset = (be_time - ts_entry).total_seconds() if ts_entry else 0
            events.append({
                'time': be_offset,
                'icon': '🛡️',
                'event': 'BREAK-EVEN',
                'detail': f"SL → Entry ({be_price:.6f})" if be_price else "SL → Entry",
                'extra': f"PnL trigger: +{be_pnl:.3f}%" if be_pnl else ""
            })
        except:
            pass
    
    # 5. Trailing Activation
    if trailing_activated and trailing_at:
        try:
            trail_time = datetime.fromisoformat(str(trailing_at).replace('Z', '+00:00'))
            trail_offset = (trail_time - ts_entry).total_seconds() if ts_entry else 0
            events.append({
                'time': trail_offset,
                'icon': '🎢',
                'event': 'TRAILING ACTIVÉ',
                'detail': f"Distance: {trailing_distance:.2f}%" if trailing_distance else "Distance: config",
                'extra': f"SL final: {trailing_final_sl:.6f}" if trailing_final_sl else ""
            })
        except:
            pass
    
    # 6. Stagnation
    if stagnation:
        events.append({
            'time': duration - 10,  # Approximation
            'icon': '⏰',
            'event': 'STAGNATION',
            'detail': "Timeout atteint",
            'extra': ""
        })
    
    # 7. Fermeture
    events.append({
        'time': duration,
        'icon': '🔴',
        'event': f'FERMETURE ({exit_reason})',
        'detail': f"Exit @ {exit_p:.6f}",
        'extra': f"PnL: {pnl:+.3f}% ({pnl_usdt:+.4f} USDT)"
    })
    
    # Trier par temps
    events.sort(key=lambda x: x['time'])
    
    # Afficher
    for e in events:
        time_str = f"T+{e['time']:.0f}s".ljust(8)
        print(f"\n{e['icon']} [{time_str}] {e['event']}")
        print(f"   {e['detail']}")
        if e['extra']:
            print(f"   {e['extra']}")
    
    # Stats finales
    print(f"\n{'─'*80}")
    print("📊 MÉTRIQUES")
    print(f"{'─'*80}")
    
    print(f"\n   MFE: {'+' + str(round(mfe, 3)) + '%' if mfe else 'N/A':>10} | Atteint à T+{time_to_mfe}s" if time_to_mfe else f"   MFE: {'+' + str(round(mfe, 3)) + '%' if mfe else 'N/A':>10}")
    print(f"   MAE: {str(round(mae, 3)) + '%' if mae else 'N/A':>10} | Atteint à T+{time_to_mae}s" if time_to_mae else f"   MAE: {str(round(mae, 3)) + '%' if mae else 'N/A':>10}")
    print(f"   PnL Final: {pnl:+.3f}%")
    
    if mfe and mfe > 0:
        capture = pnl / mfe * 100
        print(f"   Capture MFE: {capture:.1f}%")
        if capture < 50:
            print(f"   ⚠️ Moins de 50% du MFE capturé!")
    
    print(f"\n   Break-Even: {'✅ Activé' if be_triggered else '❌ Non'}")
    print(f"   Trailing: {'✅ Activé' if trailing_activated else '❌ Non'}")
    print(f"   Stagnation: {'⚠️ Détectée' if stagnation else '✅ Non'}")
    
    print("\n" + "="*80)

# Exécuter
print("🔍 Recherche du dernier trade avec métriques complètes...")
trade = get_trade_with_metrics()
print_film(trade)

cur.close()
conn.close()
