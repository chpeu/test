"""
🎬 Analyse complète du 1er trade de l'instance en cours
Reconstitue le film de la position avec tous les événements
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import quote_plus
from datetime import datetime, timedelta
import json

def get_db_connection():
    """Connexion PostgreSQL"""
    password = quote_plus("@Cmtr1di12345")
    dsn = f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml"
    return psycopg2.connect(dsn)


def get_first_trade_of_session():
    """Récupérer le premier trade de la session actuelle (depuis minuit ou dernière heure)"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Récupérer le trade le plus récent avec exit
    query = """
        SELECT 
            t.*,
            m.entry_atr_pct_1m, m.entry_atr_pct_5m,
            m.param_atr_mult_sl, m.param_atr_mult_tp,
            m.param_trailing_trigger, m.param_trailing_distance,
            m.param_be_trigger, m.param_partial_tp_trigger,
            m.max_pnl_reached as mfe, m.min_pnl_reached as mae,
            m.max_price_reached, m.min_price_reached,
            m.time_to_max_pnl_seconds, m.time_to_min_pnl_seconds,
            m.be_triggered, m.be_triggered_at, m.be_triggered_pnl_pct,
            m.trailing_activated, m.trailing_activated_at,
            m.trailing_final_sl_price, m.trailing_final_distance_pct,
            m.stagnation_detected, m.stagnation_detected_at,
            m.stagnation_duration_seconds, m.stagnation_pnl_at_exit
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE t.exit_price IS NOT NULL
        ORDER BY t.timestamp_exit DESC
        LIMIT 1
    """
    
    cursor.execute(query)
    trade = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return dict(trade) if trade else None


def get_trade_events(trade_id):
    """Récupérer les événements du trade depuis trade_events"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT *
        FROM trade_events
        WHERE trade_id = %s
        ORDER BY timestamp ASC
    """
    
    cursor.execute(query, (str(trade_id),))
    events = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return [dict(e) for e in events]


def analyze_trade(trade):
    """Analyser et reconstituer le film du trade"""
    print("="*80)
    print("🎬 FILM DU TRADE - ANALYSE COMPLÈTE")
    print("="*80)
    
    # Infos de base
    symbol = trade.get('symbol', 'N/A')
    direction = trade.get('direction', 'N/A')
    entry_price = trade.get('entry_price', 0)
    exit_price = trade.get('exit_price', 0)
    sl_price = trade.get('sl_price', 0)
    tp_price = trade.get('tp_price', 0)
    pnl_pct = trade.get('pnl_pct', 0)
    pnl_usdt = trade.get('pnl_usdt', 0)
    exit_reason = trade.get('exit_reason', 'N/A')
    
    ts_entry = trade.get('timestamp_entry')
    ts_exit = trade.get('timestamp_exit')
    
    print(f"\n📊 INFORMATIONS DE BASE")
    print("-"*40)
    print(f"   Symbol: {symbol}")
    print(f"   Direction: {direction}")
    print(f"   Entry: {entry_price}")
    print(f"   Exit: {exit_price}")
    print(f"   SL: {sl_price}")
    print(f"   TP: {tp_price}")
    
    if ts_entry and ts_exit:
        if isinstance(ts_entry, str):
            ts_entry = datetime.fromisoformat(ts_entry.replace('Z', '+00:00'))
        if isinstance(ts_exit, str):
            ts_exit = datetime.fromisoformat(ts_exit.replace('Z', '+00:00'))
        duration = (ts_exit - ts_entry).total_seconds()
        print(f"   Durée: {duration:.0f}s ({duration/60:.1f} min)")
        print(f"   Entrée: {ts_entry}")
        print(f"   Sortie: {ts_exit}")
    
    print(f"\n💰 RÉSULTAT")
    print("-"*40)
    print(f"   PnL: {pnl_pct:+.3f}%")
    print(f"   PnL USDT: {pnl_usdt:+.4f} USDT")
    print(f"   Exit Reason: {exit_reason}")
    
    # Métriques ATR
    print(f"\n📈 MÉTRIQUES ATR")
    print("-"*40)
    print(f"   ATR 1m: {trade.get('entry_atr_pct_1m', 'N/A')}%")
    print(f"   ATR 5m: {trade.get('entry_atr_pct_5m', 'N/A')}%")
    print(f"   Mult SL: {trade.get('param_atr_mult_sl', 'N/A')}")
    print(f"   Mult TP: {trade.get('param_atr_mult_tp', 'N/A')}")
    
    # MFE/MAE
    print(f"\n🎯 MFE / MAE (Excursions)")
    print("-"*40)
    mfe = trade.get('mfe')
    mae = trade.get('mae')
    max_price = trade.get('max_price_reached')
    min_price = trade.get('min_price_reached')
    time_to_max = trade.get('time_to_max_pnl_seconds')
    time_to_min = trade.get('time_to_min_pnl_seconds')
    
    if mfe is not None:
        print(f"   MFE (Max Favorable): +{mfe:.3f}%")
        if time_to_max:
            print(f"      → Atteint après {time_to_max:.0f}s")
        if max_price:
            print(f"      → Prix max: {max_price}")
    else:
        print(f"   MFE: ❌ NON ENREGISTRÉ")
    
    if mae is not None:
        print(f"   MAE (Max Adverse): {mae:.3f}%")
        if time_to_min:
            print(f"      → Atteint après {time_to_min:.0f}s")
        if min_price:
            print(f"      → Prix min: {min_price}")
    else:
        print(f"   MAE: ❌ NON ENREGISTRÉ")
    
    # Efficacité capture
    if mfe and pnl_pct and mfe > 0:
        capture_rate = (pnl_pct / mfe * 100)
        print(f"   📊 Capture MFE: {capture_rate:.1f}%")
        if capture_rate < 50:
            print(f"      ⚠️ Moins de 50% du MFE capturé!")
    
    # Break-Even
    print(f"\n🛡️ BREAK-EVEN")
    print("-"*40)
    be_triggered = trade.get('be_triggered', False)
    be_at = trade.get('be_triggered_at')
    be_pnl = trade.get('be_triggered_pnl_pct')
    param_be = trade.get('param_be_trigger')
    
    print(f"   Config trigger: {param_be}%")
    if be_triggered:
        print(f"   ✅ BE ACTIVÉ")
        if be_at:
            print(f"      → À: {be_at}")
        if be_pnl:
            print(f"      → PnL au moment: +{be_pnl:.3f}%")
    else:
        print(f"   ❌ BE NON ACTIVÉ")
        if mfe and param_be:
            if mfe >= param_be:
                print(f"      ⚠️ ANOMALIE: MFE {mfe:.3f}% >= trigger {param_be}% mais BE non activé!")
    
    # Trailing Stop
    print(f"\n🎢 TRAILING STOP")
    print("-"*40)
    trailing_activated = trade.get('trailing_activated', False)
    trailing_at = trade.get('trailing_activated_at')
    trailing_final_sl = trade.get('trailing_final_sl_price')
    trailing_distance = trade.get('trailing_final_distance_pct')
    param_trailing_trigger = trade.get('param_trailing_trigger')
    param_trailing_distance = trade.get('param_trailing_distance')
    
    print(f"   Config trigger: {param_trailing_trigger}%")
    print(f"   Config distance: {param_trailing_distance}%")
    
    if trailing_activated:
        print(f"   ✅ TRAILING ACTIVÉ")
        if trailing_at:
            print(f"      → À: {trailing_at}")
        if trailing_final_sl:
            print(f"      → SL final: {trailing_final_sl}")
        if trailing_distance:
            print(f"      → Distance finale: {trailing_distance}%")
    else:
        print(f"   ❌ TRAILING NON ACTIVÉ")
        if mfe and param_trailing_trigger:
            if mfe >= param_trailing_trigger:
                print(f"      ⚠️ ANOMALIE: MFE {mfe:.3f}% >= trigger {param_trailing_trigger}% mais trailing non activé!")
    
    # TP Partiel
    print(f"\n💰 TP PARTIEL")
    print("-"*40)
    partial_tp = trade.get('partial_tp_percent')
    param_partial = trade.get('param_partial_tp_trigger')
    
    print(f"   Config trigger: {param_partial}%")
    if partial_tp:
        print(f"   ✅ TP PARTIEL EXÉCUTÉ: {partial_tp}%")
    else:
        print(f"   ❌ Pas de TP partiel")
    
    # Stagnation
    print(f"\n⏰ STAGNATION")
    print("-"*40)
    stagnation = trade.get('stagnation_detected', False)
    stagnation_at = trade.get('stagnation_detected_at')
    stagnation_duration = trade.get('stagnation_duration_seconds')
    stagnation_pnl = trade.get('stagnation_pnl_at_exit')
    
    if stagnation:
        print(f"   ⚠️ STAGNATION DÉTECTÉE")
        if stagnation_at:
            print(f"      → À: {stagnation_at}")
        if stagnation_duration:
            print(f"      → Durée: {stagnation_duration}s")
        if stagnation_pnl:
            print(f"      → PnL à la sortie: {stagnation_pnl:.3f}%")
    else:
        print(f"   ✅ Pas de stagnation")
    
    # Reconstitution du film
    print(f"\n🎬 RECONSTITUTION DU FILM")
    print("="*80)
    
    events = []
    
    # Événement 1: Ouverture
    events.append({
        'time': 0,
        'type': 'OPEN',
        'desc': f"Position ouverte: {direction} @ {entry_price}",
        'details': f"SL initial: {sl_price} | TP: {tp_price}"
    })
    
    # Événement 2: MFE atteint
    if mfe and time_to_max:
        events.append({
            'time': time_to_max,
            'type': 'MFE',
            'desc': f"MFE atteint: +{mfe:.3f}%",
            'details': f"Prix max: {max_price}" if max_price else ""
        })
    
    # Événement 3: MAE atteint
    if mae and time_to_min:
        events.append({
            'time': time_to_min,
            'type': 'MAE',
            'desc': f"MAE atteint: {mae:.3f}%",
            'details': f"Prix min: {min_price}" if min_price else ""
        })
    
    # Événement 4: BE
    if be_triggered and be_at:
        try:
            be_time = datetime.fromisoformat(str(be_at).replace('Z', '+00:00'))
            if ts_entry:
                be_offset = (be_time - ts_entry).total_seconds()
            else:
                be_offset = 0
            events.append({
                'time': be_offset,
                'type': 'BE',
                'desc': f"Break-Even activé @ +{be_pnl:.3f}%",
                'details': f"SL → Entry ({entry_price})"
            })
        except:
            pass
    
    # Événement 5: Trailing
    if trailing_activated and trailing_at:
        try:
            trailing_time = datetime.fromisoformat(str(trailing_at).replace('Z', '+00:00'))
            if ts_entry:
                trailing_offset = (trailing_time - ts_entry).total_seconds()
            else:
                trailing_offset = 0
            events.append({
                'time': trailing_offset,
                'type': 'TRAILING',
                'desc': f"Trailing activé",
                'details': f"SL final: {trailing_final_sl}" if trailing_final_sl else ""
            })
        except:
            pass
    
    # Événement 6: Fermeture
    if ts_entry and ts_exit:
        close_offset = (ts_exit - ts_entry).total_seconds()
    else:
        close_offset = 9999
    
    events.append({
        'time': close_offset,
        'type': 'CLOSE',
        'desc': f"Position fermée: {exit_reason}",
        'details': f"Exit @ {exit_price} | PnL: {pnl_pct:+.3f}% ({pnl_usdt:+.4f} USDT)"
    })
    
    # Trier par temps
    events.sort(key=lambda x: x['time'])
    
    # Afficher timeline
    for i, event in enumerate(events):
        time_str = f"{event['time']:.0f}s" if event['time'] < 9999 else "?"
        icon = {
            'OPEN': '🟢',
            'MFE': '📈',
            'MAE': '📉',
            'BE': '🛡️',
            'TRAILING': '🎢',
            'PARTIAL_TP': '💰',
            'CLOSE': '🔴'
        }.get(event['type'], '•')
        
        print(f"\n{icon} [{time_str}] {event['type']}")
        print(f"   {event['desc']}")
        if event['details']:
            print(f"   {event['details']}")
    
    # Diagnostic
    print(f"\n\n🔍 DIAGNOSTIC")
    print("="*80)
    
    issues = []
    
    # Check 1: MFE non enregistré
    if mfe is None:
        issues.append("❌ MFE non enregistré - le tracking max_pnl_reached ne fonctionne pas")
    
    # Check 2: Trailing non activé malgré MFE
    if mfe and param_trailing_trigger and mfe >= param_trailing_trigger and not trailing_activated:
        issues.append(f"❌ Trailing non activé malgré MFE {mfe:.3f}% >= trigger {param_trailing_trigger}%")
    
    # Check 3: BE non activé malgré MFE
    if mfe and param_be and mfe >= param_be and not be_triggered:
        issues.append(f"❌ BE non activé malgré MFE {mfe:.3f}% >= trigger {param_be}%")
    
    # Check 4: Capture MFE faible
    if mfe and pnl_pct and mfe > 0:
        capture = pnl_pct / mfe * 100
        if capture < 50:
            issues.append(f"⚠️ Capture MFE faible: {capture:.1f}% (moins de 50%)")
    
    # Check 5: Exit reason TS mais trailing non activé
    if exit_reason == 'TS' and not trailing_activated:
        issues.append("❌ Exit reason = TS mais trailing_activated = False")
    
    if issues:
        for issue in issues:
            print(f"   {issue}")
    else:
        print("   ✅ Aucun problème détecté")
    
    print("\n" + "="*80)
    
    return trade


def main():
    print("🔍 Récupération du dernier trade fermé...")
    
    trade = get_first_trade_of_session()
    
    if trade:
        analyze_trade(trade)
        
        # Essayer de récupérer les événements
        trade_id = trade.get('id')
        if trade_id:
            events = get_trade_events(trade_id)
            if events:
                print(f"\n📋 ÉVÉNEMENTS ENREGISTRÉS ({len(events)})")
                print("-"*40)
                for e in events:
                    print(f"   [{e.get('event_type')}] {e.get('timestamp')} - {e.get('details')}")
    else:
        print("❌ Aucun trade trouvé")


if __name__ == '__main__':
    main()
