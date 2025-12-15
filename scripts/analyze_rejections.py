#!/usr/bin/env python3
"""Analyse des causes de rejet des trades"""

from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

conn = psycopg2.connect(
    host=os.environ.get('POSTGRES_HOST', 'localhost'),
    port=os.environ.get('POSTGRES_PORT', '5432'),
    database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
    user=os.environ.get('POSTGRES_USER', 'postgres'),
    password=os.environ.get('POSTGRES_PASSWORD', '')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print('='*70)
print('ANALYSE DES CAUSES DE REJET - OPPORTUNITIES')
print('='*70)

# Verifier la structure de la table opportunities
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'opportunities'
    ORDER BY ordinal_position
""")
cols = [r['column_name'] for r in cur.fetchall()]
print(f"\nColonnes opportunities: {len(cols)}")

# Chercher les colonnes liees au rejet
reject_cols = [c for c in cols if 'reject' in c or 'reason' in c or 'valid' in c or 'filter' in c or 'skip' in c]
print(f"Colonnes de rejet: {reject_cols}")

# Analyser les opportunites recentes
cur.execute("""
    SELECT * FROM opportunities
    ORDER BY created_at DESC
    LIMIT 50
""")
opps = cur.fetchall()
print(f"\nOpportunites recentes: {len(opps)}")

if opps:
    # Compter par action_taken ou status
    actions = {}
    for opp in opps:
        action = opp.get('action_taken') or opp.get('status') or 'unknown'
        if action not in actions:
            actions[action] = 0
        actions[action] += 1
    
    print("\nPar action/status:")
    for action, count in sorted(actions.items(), key=lambda x: -x[1]):
        print(f"  {action}: {count}")

# Verifier scan_logs
print('\n' + '='*70)
print('ANALYSE SCAN_LOGS')
print('='*70)

cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'scan_logs'
    ORDER BY ordinal_position
""")
scan_cols = [r['column_name'] for r in cur.fetchall()]
print(f"Colonnes scan_logs: {scan_cols[:15]}...")

# Regarder les scans recents
cur.execute("""
    SELECT * FROM scan_logs
    ORDER BY id DESC
    LIMIT 20
""")
scans = cur.fetchall()

if scans:
    print(f"\nScans recents: {len(scans)}")
    
    # Analyser setups_found vs trades
    setups_counts = {}
    for scan in scans:
        found = scan.get('setups_found', 0) or 0
        if found not in setups_counts:
            setups_counts[found] = 0
        setups_counts[found] += 1
    
    print("\nSetups trouves par scan:")
    for count, nb in sorted(setups_counts.items()):
        print(f"  {count} setups: {nb} scans")

# Lire les logs recents pour trouver les raisons de rejet
print('\n' + '='*70)
print('LOGS APP.LOG - RECHERCHE REJETS')
print('='*70)

try:
    with open('logs/app.log', 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()[-500:]  # 500 dernieres lignes
    
    reject_reasons = {}
    skip_reasons = {}
    
    for line in lines:
        line_lower = line.lower()
        
        # Chercher les patterns de rejet
        if 'skip' in line_lower or 'reject' in line_lower or 'ignored' in line_lower:
            # Extraire la raison
            if 'score' in line_lower:
                key = 'score_too_low'
            elif 'cooldown' in line_lower:
                key = 'cooldown'
            elif 'position' in line_lower and 'active' in line_lower:
                key = 'position_active'
            elif 'volume' in line_lower:
                key = 'volume_filter'
            elif 'spread' in line_lower:
                key = 'spread_filter'
            elif 'rsi' in line_lower:
                key = 'rsi_filter'
            elif 'atr' in line_lower:
                key = 'atr_filter'
            elif 'regime' in line_lower:
                key = 'regime_filter'
            elif 'whipsaw' in line_lower:
                key = 'whipsaw_filter'
            elif 'retest' in line_lower:
                key = 'retest_filter'
            else:
                key = 'other'
            
            if key not in reject_reasons:
                reject_reasons[key] = 0
            reject_reasons[key] += 1
    
    print("\nRaisons de rejet detectees dans les logs:")
    for reason, count in sorted(reject_reasons.items(), key=lambda x: -x[1]):
        print(f"  {reason}: {count}")
        
except Exception as e:
    print(f"Erreur lecture logs: {e}")

conn.close()
