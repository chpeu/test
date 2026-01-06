"""
🔍 Monitoring temps réel du Trailing Stop
Surveille les trades en cours et vérifie que le trailing fonctionne correctement
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
from datetime import datetime
from pathlib import Path
import psycopg2
from urllib.parse import quote_plus

# Configuration attendue MODE FIXE
EXPECTED_CONFIG = {
    'trailing_trigger_pnl': 0.15,
    'trailing_distance': 0.1,
    'break_even_trigger': 0.15,
}


def get_db_connection():
    """Connexion PostgreSQL"""
    password = quote_plus("@Cmtr1di12345")
    dsn = f"postgresql://postgres:{password}@localhost:5432/trade_cursor_ml"
    return psycopg2.connect(dsn)


def get_active_position():
    """Récupérer la position active depuis state.json"""
    state_paths = [
        Path(__file__).parent.parent / 'state.json',
        Path(__file__).parent.parent / 'data' / 'state.json',
    ]
    
    for path in state_paths:
        if path.exists():
            try:
                with open(path, 'r') as f:
                    state = json.load(f)
                    if state.get('active_position'):
                        return state['active_position']
            except:
                pass
    return None


def get_recent_trades(limit=5):
    """Récupérer les trades récents depuis PostgreSQL"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT 
                t.id, t.symbol, t.direction, 
                t.entry_price, t.exit_price, t.pnl_pct,
                t.exit_reason, t.sl_price, t.tp_price,
                t.timestamp_exit,
                m.max_pnl_reached, m.trailing_activated, m.be_triggered
            FROM trades t
            LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
            WHERE t.exit_price IS NOT NULL
            ORDER BY t.timestamp_exit DESC
            LIMIT %s
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return rows
    except Exception as e:
        print(f"❌ Erreur DB: {e}")
        return []


def analyze_trailing_performance(trades):
    """Analyser la performance du trailing sur les trades récents"""
    issues = []
    stats = {
        'total': len(trades),
        'trailing_activated': 0,
        'be_triggered': 0,
        'mfe_captured': [],
        'potential_lost': [],
    }
    
    for trade in trades:
        (trade_id, symbol, direction, entry, exit_price, pnl_pct,
         exit_reason, sl_price, tp_price, ts_exit,
         max_pnl, trailing_activated, be_triggered) = trade
        
        if trailing_activated:
            stats['trailing_activated'] += 1
        if be_triggered:
            stats['be_triggered'] += 1
        
        # Analyser MFE vs PnL final
        if max_pnl is not None and pnl_pct is not None:
            capture_rate = (pnl_pct / max_pnl * 100) if max_pnl > 0 else 0
            stats['mfe_captured'].append(capture_rate)
            
            # Problème: MFE > trigger mais trailing non activé
            if max_pnl > EXPECTED_CONFIG['trailing_trigger_pnl'] and not trailing_activated:
                issues.append({
                    'type': 'TRAILING_NOT_ACTIVATED',
                    'symbol': symbol,
                    'mfe': max_pnl,
                    'trigger': EXPECTED_CONFIG['trailing_trigger_pnl'],
                    'detail': f"MFE {max_pnl:.3f}% > trigger {EXPECTED_CONFIG['trailing_trigger_pnl']}% mais trailing non activé"
                })
            
            # Problème: Grande perte de MFE
            if max_pnl > 0.2 and pnl_pct < max_pnl * 0.5:
                lost = max_pnl - pnl_pct
                stats['potential_lost'].append(lost)
                issues.append({
                    'type': 'MFE_LOST',
                    'symbol': symbol,
                    'mfe': max_pnl,
                    'final_pnl': pnl_pct,
                    'lost': lost,
                    'detail': f"MFE {max_pnl:.3f}% → PnL {pnl_pct:.3f}% (perdu {lost:.3f}%)"
                })
        
        # Problème: MFE non tracké
        if max_pnl is None and exit_reason == 'TS':
            issues.append({
                'type': 'MFE_NOT_TRACKED',
                'symbol': symbol,
                'detail': f"Exit reason = TS mais MFE non enregistré"
            })
    
    return stats, issues


def check_trailing_logic():
    """Vérifier la cohérence de la logique trailing dans le code"""
    checks = []
    
    # Vérifier position_manager.py
    pm_path = Path(__file__).parent.parent / 'core' / 'position_manager.py'
    
    if pm_path.exists():
        with open(pm_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check 1: Trailing update après activation (pas seulement si pnl >= trigger)
        if 'if pnl >= trailing_trigger:' in content and 'tp_sl_mode == \'FIXE\'' in content:
            # Vérifier si c'est DANS le bloc trailing_should_activate
            if 'trailing_should_activate' in content:
                checks.append(('Trailing update conditionnel', True, 'Logique correcte'))
        
        # Check 2: Mode FIXE utilise trailing_distance directement
        if 'trailing_distance = TRADING_CONFIG.get(\'trailing_distance\'' in content:
            checks.append(('Distance FIXE depuis config', True, 'OK'))
        else:
            checks.append(('Distance FIXE depuis config', False, 'Non trouvé'))
        
        # Check 3: Logger les mouvements de SL
        if '🎢 Trailing FIXE' in content or 'TRAILING_SL_MOVED' in content:
            checks.append(('Logging trailing moves', True, 'OK'))
        else:
            checks.append(('Logging trailing moves', False, 'Pas de log visible'))
    
    return checks


def monitor_once():
    """Exécuter une vérification complète"""
    print("="*80)
    print(f"🔍 MONITORING TRAILING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 1. Vérifier position active
    print("\n📊 Position Active:")
    active_pos = get_active_position()
    
    if active_pos:
        symbol = active_pos.get('symbol', 'N/A')
        entry = active_pos.get('entry', 0)
        sl = active_pos.get('sl', 0)
        direction = active_pos.get('direction', 'N/A')
        trailing_activated = active_pos.get('trailing_activated', False)
        be_set = active_pos.get('break_even_set', False)
        max_pnl = active_pos.get('max_pnl_reached')
        
        print(f"   Symbol: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {entry}")
        print(f"   SL actuel: {sl}")
        print(f"   BE activé: {'✅' if be_set else '❌'}")
        print(f"   Trailing activé: {'✅' if trailing_activated else '❌'}")
        print(f"   MFE: {max_pnl:.3f}%" if max_pnl else "   MFE: N/A")
        
        # Calculer SL attendu si trailing activé
        if trailing_activated and entry and sl:
            if direction == 'LONG':
                sl_pct_from_entry = ((sl - entry) / entry * 100)
            else:
                sl_pct_from_entry = ((entry - sl) / entry * 100)
            print(f"   SL depuis entry: {sl_pct_from_entry:+.3f}%")
    else:
        print("   Aucune position active")
    
    # 2. Analyser trades récents
    print("\n📈 Trades Récents:")
    trades = get_recent_trades(5)
    
    if trades:
        stats, issues = analyze_trailing_performance(trades)
        
        print(f"   Total: {stats['total']}")
        print(f"   Trailing activé: {stats['trailing_activated']}/{stats['total']}")
        print(f"   BE activé: {stats['be_triggered']}/{stats['total']}")
        
        if stats['mfe_captured']:
            avg_capture = sum(stats['mfe_captured']) / len(stats['mfe_captured'])
            print(f"   Capture MFE moyenne: {avg_capture:.1f}%")
        
        if stats['potential_lost']:
            total_lost = sum(stats['potential_lost'])
            print(f"   ⚠️ Potentiel perdu total: {total_lost:.3f}%")
        
        # Afficher les problèmes
        if issues:
            print(f"\n⚠️ PROBLÈMES DÉTECTÉS ({len(issues)}):")
            for issue in issues:
                print(f"   ❌ [{issue['type']}] {issue['symbol']}: {issue['detail']}")
        else:
            print("\n   ✅ Aucun problème détecté")
    else:
        print("   Aucun trade récent")
    
    # 3. Vérifier la logique du code
    print("\n🔧 Vérification Code:")
    checks = check_trailing_logic()
    
    for name, passed, detail in checks:
        status = "✅" if passed else "❌"
        print(f"   {status} {name}: {detail}")
    
    print("\n" + "="*80)


def monitor_continuous(interval=30):
    """Monitoring continu"""
    print("🔄 Démarrage monitoring continu (Ctrl+C pour arrêter)")
    print(f"   Intervalle: {interval}s")
    
    try:
        while True:
            monitor_once()
            print(f"\n⏳ Prochaine vérification dans {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring arrêté")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Monitoring Trailing Stop')
    parser.add_argument('--continuous', '-c', action='store_true', 
                        help='Mode continu')
    parser.add_argument('--interval', '-i', type=int, default=30,
                        help='Intervalle en secondes (défaut: 30)')
    
    args = parser.parse_args()
    
    if args.continuous:
        monitor_continuous(args.interval)
    else:
        monitor_once()


if __name__ == '__main__':
    main()
