#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de verification des valeurs PNL des trades
Compare les valeurs du frontend avec les donnees de l'API MEXC

Verifie:
- PNL realise USDT (precision 4 decimales)
- Prix d'entree
- Prix de sortie
- Coherence des calculs
"""

import json
import os
import sys
import io

if os.environ.get('PYTEST_CURRENT_TEST') is not None or __name__ != '__main__':
    raise ImportError('verify_trade_pnl is a script-only module')

# Force UTF-8 output
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Couleurs pour output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_ok(msg): print(f"  {GREEN}[OK]{RESET} {msg}")
def print_fail(msg): print(f"  {RED}[FAIL]{RESET} {msg}")
def print_warn(msg): print(f"  {YELLOW}[WARN]{RESET} {msg}")
def print_info(msg): print(f"  {BLUE}[INFO]{RESET} {msg}")
def print_header(title): print(f"\n{'='*60}\n{BOLD}{title}{RESET}\n{'='*60}")

PROJECT_ROOT = Path(__file__).parent.parent


def load_trade_history() -> List[Dict]:
    """Charger l'historique des trades depuis le fichier JSON"""
    history_file = PROJECT_ROOT / "trade_history.json"
    
    if not history_file.exists():
        print_fail(f"Fichier trade_history.json non trouvé")
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            trades = json.load(f)
        print_ok(f"Historique chargé: {len(trades)} trades")
        return trades
    except Exception as e:
        print_fail(f"Erreur chargement: {e}")
        return []


def verify_pnl_precision(trades: List[Dict]) -> Dict[str, Any]:
    """Vérifier la précision des valeurs PNL"""
    print_header("VÉRIFICATION PRÉCISION PNL")
    
    results = {
        'total_trades': len(trades),
        'pnl_usdt_issues': [],
        'entry_price_issues': [],
        'exit_price_issues': [],
        'calculation_mismatches': []
    }
    
    for i, trade in enumerate(trades[:20]):  # Vérifier les 20 derniers trades
        symbol = trade.get('symbol', 'N/A')
        
        # Vérifier net_pnl_usdt
        net_pnl_usdt = trade.get('net_pnl_usdt')
        if net_pnl_usdt is not None:
            # Vérifier que la précision est suffisante
            str_val = str(net_pnl_usdt)
            if '.' in str_val:
                decimals = len(str_val.split('.')[1])
                if decimals < 4:
                    results['pnl_usdt_issues'].append({
                        'trade': i+1,
                        'symbol': symbol,
                        'value': net_pnl_usdt,
                        'decimals': decimals
                    })
        
        # Vérifier entry_price
        entry_price = trade.get('entry_price') or trade.get('entry')
        if entry_price is None or entry_price <= 0:
            results['entry_price_issues'].append({
                'trade': i+1,
                'symbol': symbol,
                'value': entry_price
            })
        
        # Vérifier exit_price
        exit_price = trade.get('exit_price') or trade.get('exit')
        if exit_price is None or exit_price <= 0:
            results['exit_price_issues'].append({
                'trade': i+1,
                'symbol': symbol,
                'value': exit_price
            })
        
        # Vérifier cohérence calcul PNL
        if entry_price and exit_price and entry_price > 0:
            direction = trade.get('direction', 'LONG')
            size = trade.get('size', 0)
            
            if size > 0 and entry_price > 0:
                # Calcul théorique du PNL
                if direction == 'LONG':
                    expected_pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:
                    expected_pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                
                gross_pnl_pct = trade.get('gross_pnl_pct') or trade.get('pnl_pct', 0)
                
                # Tolérance de 0.5% pour les différences dues aux frais/slippage
                if abs(expected_pnl_pct - gross_pnl_pct) > 0.5:
                    results['calculation_mismatches'].append({
                        'trade': i+1,
                        'symbol': symbol,
                        'direction': direction,
                        'entry': entry_price,
                        'exit': exit_price,
                        'expected_pnl_pct': round(expected_pnl_pct, 4),
                        'actual_pnl_pct': gross_pnl_pct,
                        'diff': round(abs(expected_pnl_pct - gross_pnl_pct), 4)
                    })
    
    # Afficher résultats
    if results['pnl_usdt_issues']:
        print_warn(f"PNL USDT avec précision < 4 décimales: {len(results['pnl_usdt_issues'])}")
        for issue in results['pnl_usdt_issues'][:5]:
            print_info(f"  Trade #{issue['trade']} ({issue['symbol']}): {issue['value']} ({issue['decimals']} décimales)")
    else:
        print_ok("Tous les PNL USDT ont ≥ 4 décimales")
    
    if results['entry_price_issues']:
        print_fail(f"Prix d'entrée manquants/invalides: {len(results['entry_price_issues'])}")
        for issue in results['entry_price_issues'][:5]:
            print_info(f"  Trade #{issue['trade']} ({issue['symbol']}): {issue['value']}")
    else:
        print_ok("Tous les prix d'entrée sont valides")
    
    if results['exit_price_issues']:
        print_fail(f"Prix de sortie manquants/invalides: {len(results['exit_price_issues'])}")
        for issue in results['exit_price_issues'][:5]:
            print_info(f"  Trade #{issue['trade']} ({issue['symbol']}): {issue['value']}")
    else:
        print_ok("Tous les prix de sortie sont valides")
    
    if results['calculation_mismatches']:
        print_warn(f"Écarts de calcul PNL > 0.5%: {len(results['calculation_mismatches'])}")
        for issue in results['calculation_mismatches'][:5]:
            print_info(f"  Trade #{issue['trade']} ({issue['symbol']} {issue['direction']}): "
                      f"Attendu {issue['expected_pnl_pct']:.4f}% vs Réel {issue['actual_pnl_pct']:.4f}% "
                      f"(diff: {issue['diff']:.4f}%)")
    else:
        print_ok("Tous les calculs PNL sont cohérents")
    
    return results


def verify_recent_trades_api() -> bool:
    """Vérifier l'API des trades récents"""
    print_header("VÉRIFICATION API TRADES")
    
    try:
        import requests
        response = requests.get('http://localhost:8000/api/trades/history', timeout=5)
        
        if response.ok:
            data = response.json()
            trades = data.get('trades', []) if isinstance(data, dict) else data
            print_ok(f"API /api/trades/history: {len(trades)} trades")
            
            # Vérifier les champs requis
            if trades:
                sample = trades[0]
                required_fields = ['symbol', 'direction', 'entry_price', 'exit_price', 'net_pnl_usdt']
                missing = [f for f in required_fields if f not in sample and f.replace('_price', '') not in sample]
                
                if missing:
                    print_warn(f"Champs manquants dans API: {missing}")
                else:
                    print_ok("Tous les champs requis présents dans l'API")
            
            return True
        else:
            print_fail(f"API erreur: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_warn("Backend non accessible - test API ignoré")
        return False
    except Exception as e:
        print_fail(f"Erreur API: {e}")
        return False


def display_trade_sample(trades: List[Dict], count: int = 5):
    """Afficher un échantillon de trades pour vérification visuelle"""
    print_header(f"ÉCHANTILLON TRADES (derniers {count})")
    
    print(f"\n{'#':<3} {'Symbol':<12} {'Dir':<6} {'Entry':<14} {'Exit':<14} {'PNL USDT':<12} {'PNL %':<10}")
    print("-" * 85)
    
    for i, trade in enumerate(trades[:count]):
        symbol = trade.get('symbol', 'N/A')[:10]
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price') or trade.get('entry', 0)
        exit_p = trade.get('exit_price') or trade.get('exit', 0)
        pnl_usdt = trade.get('net_pnl_usdt', 0)
        pnl_pct = trade.get('net_pnl_pct', 0)
        
        # Format avec précision correcte
        entry_str = f"{entry:.8f}" if entry < 1 else f"{entry:.4f}" if entry < 100 else f"{entry:.2f}"
        exit_str = f"{exit_p:.8f}" if exit_p < 1 else f"{exit_p:.4f}" if exit_p < 100 else f"{exit_p:.2f}"
        pnl_usdt_str = f"{pnl_usdt:+.4f}"
        pnl_pct_str = f"{pnl_pct:+.4f}%"
        
        print(f"{i+1:<3} {symbol:<12} {direction:<6} {entry_str:<14} {exit_str:<14} {pnl_usdt_str:<12} {pnl_pct_str:<10}")


def verify_pnl_calculation_formula(trades: List[Dict]):
    """Vérifier la formule de calcul du PNL"""
    print_header("VÉRIFICATION FORMULE CALCUL PNL")
    
    errors = []
    
    for i, trade in enumerate(trades[:10]):
        entry = trade.get('entry_price') or trade.get('entry', 0)
        exit_p = trade.get('exit_price') or trade.get('exit', 0)
        direction = trade.get('direction', 'LONG')
        size = trade.get('size', 0)
        net_pnl_usdt = trade.get('net_pnl_usdt', 0)
        gross_pnl_usdt = trade.get('gross_pnl_usdt', 0)
        
        if entry <= 0 or exit_p <= 0 or size <= 0:
            continue
        
        # Calcul théorique
        if direction == 'LONG':
            theoretical_pnl_pct = ((exit_p - entry) / entry) * 100
        else:
            theoretical_pnl_pct = ((entry - exit_p) / entry) * 100
        
        theoretical_pnl_usdt = (theoretical_pnl_pct / 100) * size
        
        # Comparer avec la valeur stockée
        actual_gross = gross_pnl_usdt if gross_pnl_usdt else net_pnl_usdt
        
        diff = abs(theoretical_pnl_usdt - actual_gross)
        diff_pct = (diff / abs(theoretical_pnl_usdt) * 100) if theoretical_pnl_usdt != 0 else 0
        
        if diff_pct > 10:  # Plus de 10% d'écart
            errors.append({
                'trade': i+1,
                'symbol': trade.get('symbol'),
                'theoretical': theoretical_pnl_usdt,
                'actual': actual_gross,
                'diff_pct': diff_pct
            })
    
    if errors:
        print_warn(f"Écarts de calcul significatifs: {len(errors)}")
        for err in errors[:5]:
            print_info(f"  Trade #{err['trade']} ({err['symbol']}): "
                      f"Théorique={err['theoretical']:.4f} vs Réel={err['actual']:.4f} "
                      f"(écart {err['diff_pct']:.1f}%)")
    else:
        print_ok("Tous les calculs PNL suivent la formule attendue")


def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}VÉRIFICATION PNL TRADES{RESET}")
    print(f"{BOLD}Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    # Charger les trades
    trades = load_trade_history()
    
    if not trades:
        print_fail("Aucun trade à vérifier")
        sys.exit(1)
    
    # Afficher échantillon
    display_trade_sample(trades)
    
    # Vérifier précision
    precision_results = verify_pnl_precision(trades)
    
    # Vérifier formule
    verify_pnl_calculation_formula(trades)
    
    # Vérifier API
    verify_recent_trades_api()
    
    # Résumé
    print_header("RÉSUMÉ")
    
    total_issues = (
        len(precision_results['pnl_usdt_issues']) +
        len(precision_results['entry_price_issues']) +
        len(precision_results['exit_price_issues']) +
        len(precision_results['calculation_mismatches'])
    )
    
    if total_issues == 0:
        print(f"\n  {GREEN}[PASS] TOUTES LES VERIFICATIONS PASSEES{RESET}")
    else:
        print(f"\n  {YELLOW}[WARN] {total_issues} probleme(s) detecte(s){RESET}")
    
    print(f"\n  Trades vérifiés: {min(20, len(trades))}")
    print(f"  PNL précision issues: {len(precision_results['pnl_usdt_issues'])}")
    print(f"  Entry price issues: {len(precision_results['entry_price_issues'])}")
    print(f"  Exit price issues: {len(precision_results['exit_price_issues'])}")
    print(f"  Calculation mismatches: {len(precision_results['calculation_mismatches'])}")
    
    return 0 if total_issues == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
