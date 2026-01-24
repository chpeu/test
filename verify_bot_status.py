"""
Script de verification du bot:
1. Verifie que le bot ferme correctement les trades
2. Verifie que les scans continuent
3. Analyse le trade BAS pour comprendre le SL de -1.34%
"""

import sys
import os

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        if sys.stdout is sys.__stdout__ and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

def get_connection():
    """Use simple connection without encoding issues"""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='trade_cursor_ml',
        user='postgres',
        password='Goldorak69!'
    )

def check_recent_trades():
    """Vérifier les trades récents et leur état de clôture"""
    print("\n" + "="*60)
    print("📊 VÉRIFICATION DES TRADES RÉCENTS")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Trades des dernières 24h
    query = """
        SELECT 
            id, symbol, direction, 
            timestamp_entry, timestamp_exit,
            entry_price, exit_price,
            pnl_pct, net_pnl_pct,
            exit_reason,
            sl_price, tp_price,
            is_live_trade
        FROM trades 
        WHERE timestamp_entry >= NOW() - INTERVAL '24 hours'
        ORDER BY timestamp_entry DESC
        LIMIT 20;
    """
    
    cur.execute(query)
    trades = cur.fetchall()
    
    print(f"\n📋 {len(trades)} trades trouvés dans les dernières 24h:\n")
    
    open_trades = 0
    closed_trades = 0
    
    for t in trades:
        status = "✅ FERMÉ" if t['timestamp_exit'] else "⚠️ OUVERT"
        if not t['timestamp_exit']:
            open_trades += 1
        else:
            closed_trades += 1
            
        pnl = t.get('net_pnl_pct') or t.get('pnl_pct') or 0
        pnl_emoji = "🟢" if pnl > 0 else "🔴"
        
        print(f"  {status} | {t['symbol'][:15]:15} | {t['direction']:5} | "
              f"{t['exit_reason'] or 'N/A':12} | {pnl_emoji} {pnl:+.2f}%")
    
    print(f"\n📈 Résumé: {closed_trades} fermés, {open_trades} ouverts")
    
    cur.close()
    conn.close()
    
    return open_trades == 0

def check_recent_scans():
    """Vérifier que les scans continuent"""
    print("\n" + "="*60)
    print("🔍 VÉRIFICATION DES SCANS RÉCENTS")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Scans des dernières 10 minutes
    query = """
        SELECT 
            COUNT(*) as scan_count,
            MAX(timestamp) as last_scan,
            AVG(scan_duration_ms) as avg_duration_ms
        FROM scan_logs 
        WHERE timestamp >= NOW() - INTERVAL '10 minutes';
    """
    
    cur.execute(query)
    result = cur.fetchone()
    
    scan_count = result['scan_count'] or 0
    last_scan = result['last_scan']
    avg_duration = result['avg_duration_ms'] or 0
    
    print(f"\n📊 Scans dans les 10 dernières minutes: {scan_count}")
    print(f"⏱️ Dernier scan: {last_scan}")
    print(f"⚡ Durée moyenne: {avg_duration:.0f}ms")
    
    # Vérifier si les scans sont récents (moins de 2 minutes)
    if last_scan:
        time_since_last = datetime.now(last_scan.tzinfo) - last_scan
        if time_since_last.total_seconds() < 120:
            print(f"✅ Bot actif (dernier scan il y a {time_since_last.total_seconds():.0f}s)")
            scans_ok = True
        else:
            print(f"⚠️ Bot potentiellement bloqué (dernier scan il y a {time_since_last.total_seconds():.0f}s)")
            scans_ok = False
    else:
        print("⚠️ Aucun scan récent trouvé")
        scans_ok = False
    
    cur.close()
    conn.close()
    
    return scans_ok

def analyze_bas_trade():
    """Analyser le trade BAS avec SL de -1.34%"""
    print("\n" + "="*60)
    print("🔬 ANALYSE DU TRADE BAS (SL -1.34%)")
    print("="*60)
    
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Chercher le trade BAS récent
    query = """
        SELECT 
            t.*,
            m.atr_1m, m.atr_5m, m.atr_15m,
            m.calculated_sl_pct, m.calculated_tp_pct,
            m.sl_mexc_touched, m.sl_mexc_touched_at,
            m.max_pnl_reached, m.min_pnl_reached
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE t.symbol ILIKE '%BAS%'
        AND t.timestamp_entry >= NOW() - INTERVAL '24 hours'
        ORDER BY t.timestamp_entry DESC
        LIMIT 1;
    """
    
    cur.execute(query)
    trade = cur.fetchone()
    
    if not trade:
        print("❌ Trade BAS non trouvé")
        cur.close()
        conn.close()
        return
    
    print(f"\n📋 DÉTAILS DU TRADE:")
    print(f"  Symbol: {trade['symbol']}")
    print(f"  Direction: {trade['direction']}")
    print(f"  Entry: {trade['entry_price']}")
    print(f"  Exit: {trade['exit_price']}")
    print(f"  SL configuré: {trade.get('sl_price')}")
    print(f"  TP configuré: {trade.get('tp_price')}")
    print(f"  Exit reason: {trade['exit_reason']}")
    print(f"  PnL%: {trade.get('pnl_pct')}%")
    print(f"  Net PnL%: {trade.get('net_pnl_pct')}%")
    print(f"  Durée: {trade.get('duration_seconds')}s")
    
    print(f"\n📊 MÉTRIQUES ATR:")
    print(f"  ATR 1m: {trade.get('atr_1m')}")
    print(f"  ATR 5m: {trade.get('atr_5m')}")
    print(f"  ATR 15m: {trade.get('atr_15m')}")
    print(f"  SL calculé%: {trade.get('calculated_sl_pct')}")
    print(f"  TP calculé%: {trade.get('calculated_tp_pct')}")
    
    print(f"\n📈 EXCURSIONS:")
    print(f"  Max PnL atteint: {trade.get('max_pnl_reached')}%")
    print(f"  Min PnL atteint: {trade.get('min_pnl_reached')}%")
    print(f"  SL MEXC touched: {trade.get('sl_mexc_touched')}")
    
    # Calculer pourquoi le SL était si large
    entry = float(trade['entry_price']) if trade['entry_price'] else 0
    sl = float(trade.get('sl_price') or 0)
    
    if entry > 0 and sl > 0:
        sl_distance_pct = abs(entry - sl) / entry * 100
        print(f"\n🎯 ANALYSE SL:")
        print(f"  Distance SL calculée: {sl_distance_pct:.4f}%")
        
        # Vérifier si c'est lié à l'ATR
        atr_1m = float(trade.get('atr_1m') or 0)
        if atr_1m > 0 and entry > 0:
            atr_pct = atr_1m / entry * 100
            print(f"  ATR% (1m): {atr_pct:.4f}%")
            print(f"  Multiplicateur SL apparent: {sl_distance_pct / atr_pct:.2f}x ATR" if atr_pct > 0 else "")
    
    cur.close()
    conn.close()

def main():
    print("\n" + "🤖 VÉRIFICATION COMPLÈTE DU BOT " + "="*30)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Vérifier les trades
    trades_ok = check_recent_trades()
    
    # 2. Vérifier les scans
    scans_ok = check_recent_scans()
    
    # 3. Analyser le trade BAS
    analyze_bas_trade()
    
    # Résumé final
    print("\n" + "="*60)
    print("📋 RÉSUMÉ FINAL")
    print("="*60)
    print(f"  Trades fermés correctement: {'✅ OUI' if trades_ok else '⚠️ NON (trades ouverts)'}")
    print(f"  Scans actifs: {'✅ OUI' if scans_ok else '⚠️ NON'}")
    
    if trades_ok and scans_ok:
        print("\n✅ BOT FONCTIONNEL")
    else:
        print("\n⚠️ VÉRIFIER LE BOT")

if __name__ == "__main__":
    main()
