#!/usr/bin/env python3
"""
Analyse des trades recents depuis PostgreSQL
"""
import os
import sys

# Fix Windows UTF-8 output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Ajouter le dossier racine au path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

# Charger .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
except ImportError:
    pass

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration PostgreSQL
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': int(os.getenv('POSTGRES_PORT', 5432)),
    'database': os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres')
}

def get_table_columns():
    """Lister les colonnes de la table trades"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'trades' ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return columns
    except Exception as e:
        print(f"Erreur: {e}")
        return []

def get_recent_trades(days=7, limit=None):
    """Recuperer les trades des N derniers jours ou les N derniers trades"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Recuperer les trades recents - utiliser timestamp_entry comme reference
        if limit:
            # Mode limite: récupérer les N derniers trades
            query = """
            SELECT * FROM trades 
            ORDER BY timestamp_entry DESC
            LIMIT %s
            """
            cur.execute(query, (limit,))
        else:
            # Mode jours: récupérer les trades des N derniers jours
            query = """
            SELECT * FROM trades 
            WHERE timestamp_entry >= NOW() - INTERVAL '%s days'
            ORDER BY timestamp_entry DESC
            """
            cur.execute(query, (days,))
        trades = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return trades
    except Exception as e:
        print(f"Erreur connexion PostgreSQL: {e}")
        return []

def get_field(trade, *fields, default=None):
    """Recuperer un champ avec plusieurs noms possibles"""
    for f in fields:
        if f in trade and trade[f] is not None:
            return trade[f]
    return default

def analyze_trades(trades):
    """Analyser les trades pour identifier les problemes"""
    if not trades:
        print("Aucun trade trouve dans la base de donnees.")
        # Afficher les colonnes disponibles
        cols = get_table_columns()
        if cols:
            print(f"\nColonnes disponibles: {cols[:20]}...")
        return
    
    # Afficher un exemple de trade pour debug
    print(f"\nExemple de trade (cles): {list(trades[0].keys())[:15]}...")
    
    print(f"\n{'='*80}")
    print(f"ANALYSE DES {len(trades)} DERNIERS TRADES")
    print(f"{'='*80}\n")
    
    # Statistiques globales - utiliser plusieurs noms de colonnes possibles
    def get_pnl(t):
        return get_field(t, 'pnl_pct', 'pnl', 'gross_pnl_pct', 'net_pnl_pct', default=0)
    
    def get_pnl_usdt(t):
        return get_field(t, 'pnl_usdt', 'gross_pnl_usdt', 'net_pnl_usdt', default=0)
    
    wins = [t for t in trades if get_pnl(t) > 0]
    losses = [t for t in trades if get_pnl(t) < 0]
    breakeven = [t for t in trades if get_pnl(t) == 0]
    
    total_pnl = sum(get_pnl_usdt(t) for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    
    print(f"Win Rate: {win_rate:.1f}% ({len(wins)} wins / {len(losses)} losses / {len(breakeven)} BE)")
    print(f"PnL Total: {total_pnl:.2f} USDT")
    print(f"PnL Moyen: {total_pnl/len(trades):.4f} USDT" if trades else "N/A")
    
    # Analyse par raison de sortie
    print(f"\n{'='*50}")
    print("ANALYSE PAR RAISON DE SORTIE")
    print(f"{'='*50}")
    
    def get_reason(t):
        return get_field(t, 'close_reason', 'reason', 'exit_reason', default='UNKNOWN')
    
    def get_duration(t):
        return get_field(t, 'duration_seconds', 'duration', 'trade_duration', default=0)
    
    by_reason = defaultdict(list)
    for t in trades:
        reason = get_reason(t)
        by_reason[reason].append(t)
    
    for reason, group in sorted(by_reason.items(), key=lambda x: len(x[1]), reverse=True):
        group_pnl = sum(get_pnl_usdt(t) for t in group)
        group_wins = len([t for t in group if get_pnl(t) > 0])
        group_wr = group_wins / len(group) * 100 if group else 0
        avg_duration = sum(get_duration(t) for t in group) / len(group) if group else 0
        
        print(f"\n{reason}:")
        print(f"  - Count: {len(group)} trades ({len(group)/len(trades)*100:.1f}%)")
        print(f"  - WR: {group_wr:.1f}%")
        print(f"  - PnL Total: {group_pnl:.2f} USDT")
        print(f"  - Duree moyenne: {avg_duration:.0f}s")
    
    # Analyse MFE vs MAE (setup quality vs management)
    print(f"\n{'='*50}")
    print("ANALYSE SETUP vs GESTION")
    print(f"{'='*50}")
    
    trades_with_mfe = [t for t in trades if t.get('max_favorable_excursion') is not None]
    trades_with_mae = [t for t in trades if t.get('max_adverse_excursion') is not None]
    
    if trades_with_mfe:
        avg_mfe = sum(t['max_favorable_excursion'] for t in trades_with_mfe) / len(trades_with_mfe)
        print(f"MFE Moyen (Max Profit Atteint): {avg_mfe:.2f}%")
    
    if trades_with_mae:
        avg_mae = sum(t['max_adverse_excursion'] for t in trades_with_mae) / len(trades_with_mae)
        print(f"MAE Moyen (Max Drawdown Subi): {avg_mae:.2f}%")
    
    # Trades perdants avec MFE positif = MAUVAISE GESTION
    bad_management = []
    for t in losses:
        mfe = t.get('max_favorable_excursion')
        if mfe and mfe > 0.1:  # Avait + de 0.1% de profit potentiel
            bad_management.append(t)
    
    # Trades perdants avec MFE negatif = MAUVAIS SETUP
    bad_setup = []
    for t in losses:
        mfe = t.get('max_favorable_excursion')
        if mfe is not None and mfe <= 0:  # Jamais ete en profit
            bad_setup.append(t)
    
    print(f"\n--- DIAGNOSTIC ---")
    print(f"Trades perdants avec MFE > 0.1% (mauvaise gestion): {len(bad_management)}")
    print(f"Trades perdants avec MFE <= 0% (mauvais setup): {len(bad_setup)}")
    
    if len(bad_management) > len(bad_setup):
        print(f"\n>>> VERDICT: La mauvaise performance vient principalement de la GESTION DU TRADE")
        print(f"    - Les setups atteignent des profits mais sont mal geres")
        print(f"    - Solutions: Ajuster trailing stop, BE, TP partiels")
    elif len(bad_setup) > len(bad_management):
        print(f"\n>>> VERDICT: La mauvaise performance vient principalement des SETUPS")
        print(f"    - Les trades n'atteignent jamais de profit significatif")
        print(f"    - Solutions: Ameliorer les conditions d'entree, filtres ML")
    else:
        print(f"\n>>> VERDICT: Mix des deux problemes (setup + gestion)")
    
    # Analyse GAP MFE - PnL (profit laisse sur la table)
    print(f"\n{'='*50}")
    print("ANALYSE GAP MFE vs PNL (Profit laisse sur table)")
    print(f"{'='*50}")
    
    def get_mfe(t):
        return get_field(t, 'max_favorable_excursion', 'mfe', 'max_pnl_reached', default=None)
    
    def get_mae(t):
        return get_field(t, 'max_adverse_excursion', 'mae', 'max_drawdown', default=None)
    
    # Calculer les gaps pour tous les trades
    gaps = []
    for t in trades:
        mfe = get_mfe(t)
        pnl = get_pnl(t)
        if mfe is not None:
            gap = mfe - pnl  # Positif = profit perdu
            gaps.append({
                'trade': t,
                'mfe': mfe,
                'pnl': pnl,
                'gap': gap,
                'gap_usdt': gap * get_field(t, 'size_usdt', 'size', default=25) / 100
            })
    
    if gaps:
        avg_gap = sum(g['gap'] for g in gaps) / len(gaps)
        total_gap_usdt = sum(g['gap_usdt'] for g in gaps)
        max_gap = max(gaps, key=lambda x: x['gap'])
        
        print(f"\nGap moyen (MFE - PnL): {avg_gap:.3f}%")
        print(f"Profit total laisse sur table: {total_gap_usdt:.2f} USDT")
        print(f"Pire gap: {max_gap['gap']:.2f}% sur {get_field(max_gap['trade'], 'symbol', default='?')}")
        
        # Repartition des gaps
        small_gaps = [g for g in gaps if g['gap'] < 0.1]
        medium_gaps = [g for g in gaps if 0.1 <= g['gap'] < 0.3]
        large_gaps = [g for g in gaps if g['gap'] >= 0.3]
        
        print(f"\nRepartition des gaps:")
        print(f"  - Gap < 0.1%: {len(small_gaps)} trades (bonne gestion)")
        print(f"  - Gap 0.1-0.3%: {len(medium_gaps)} trades (ameliorable)")
        print(f"  - Gap >= 0.3%: {len(large_gaps)} trades (profit perdu significatif)")
        
        # Top 10 des trades avec le plus gros gap
        print(f"\n--- TOP 10 TRADES AVEC PLUS GROS GAP ---")
        sorted_gaps = sorted(gaps, key=lambda x: x['gap'], reverse=True)[:10]
        for i, g in enumerate(sorted_gaps, 1):
            t = g['trade']
            symbol = get_field(t, 'symbol', default='?')
            direction = get_field(t, 'direction', default='?')
            reason = get_reason(t)
            print(f"{i:2}. {symbol:20} {direction:5} | MFE: {g['mfe']:+.2f}% -> PnL: {g['pnl']:+.2f}% | Gap: {g['gap']:.2f}% ({g['gap_usdt']:.3f} USDT) | {reason}")
    
    # Detail des trades recents
    print(f"\n{'='*50}")
    print("FILM DES 15 DERNIERS TRADES")
    print(f"{'='*50}")
    
    for i, t in enumerate(trades[:15], 1):
        mfe = get_mfe(t)
        mae = get_mae(t)
        mfe_str = f"{mfe:.2f}%" if mfe is not None else "N/A"
        mae_str = f"{mae:.2f}%" if mae is not None else "N/A"
        
        pnl = get_pnl(t)
        pnl_usdt = get_pnl_usdt(t)
        
        # Emoji selon resultat
        if pnl > 0:
            emoji = "WIN"
        elif pnl < 0:
            emoji = "LOSS"
        else:
            emoji = "BE"
        
        # Analyse qualitative
        analysis = ""
        if pnl < 0:
            if mfe and mfe > 0.15:
                analysis = ">> GESTION (avait +{:.2f}%)".format(mfe)
            elif mfe is not None and mfe <= 0:
                analysis = ">> SETUP (jamais positif)"
            elif mfe and mfe > 0:
                analysis = ">> MIXTE (MFE faible)"
        
        duration = get_duration(t)
        regime = get_field(t, 'market_regime', 'regime', default='N/A')
        symbol = get_field(t, 'symbol', 'pair', default='?')
        direction = get_field(t, 'direction', 'side', default='?')
        entry = get_field(t, 'entry_price', 'entry', default=0)
        exit_p = get_field(t, 'exit_price', 'exit', default=0)
        reason = get_reason(t)
        be_set = get_field(t, 'break_even_set', 'be_triggered', default=False)
        trail = get_field(t, 'trailing_stop_activated', 'trailing_activated', default=False)
        
        print(f"\n{i}. [{emoji}] {symbol} {direction}")
        print(f"   Entry: {entry} -> Exit: {exit_p}")
        # Calculer le gap
        gap = (mfe - pnl) if mfe is not None else None
        gap_str = f"{gap:.2f}%" if gap is not None else "N/A"
        
        print(f"   PnL: {pnl:.2f}% ({pnl_usdt:.4f} USDT)")
        print(f"   MFE: {mfe_str} | MAE: {mae_str} | Gap: {gap_str}")
        print(f"   Duree: {duration}s | Raison: {reason}")
        print(f"   Regime: {regime} | BE: {be_set} | Trail: {trail}")
        if analysis:
            print(f"   {analysis}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Analyse des trades récents')
    parser.add_argument('--limit', type=int, default=None, help='Nombre de trades à analyser')
    parser.add_argument('--days', type=int, default=7, help='Nombre de jours à analyser')
    args = parser.parse_args()
    
    print("Connexion a PostgreSQL...")
    trades = get_recent_trades(days=args.days, limit=args.limit)
    analyze_trades(trades)
