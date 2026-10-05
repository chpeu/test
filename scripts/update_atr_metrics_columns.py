#!/usr/bin/env python3
"""
Script pour mettre à jour les colonnes entry_atr_pct_used et entry_atr_blended
sur les lignes trade_atr_metrics existantes.

Ce script complémente backfill_atr_metrics.py:
- backfill_atr_metrics.py: crée les lignes manquantes
- update_atr_metrics_columns.py: met à jour les colonnes NULL sur les lignes existantes
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
import json


def get_connection():
    return psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', 'localhost'),
        port=os.environ.get('POSTGRES_PORT', '5432'),
        database=os.environ.get('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', '')
    )


def extract_numeric(value):
    """Extraire une valeur numérique de manière sûre."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def update_existing_atr_metrics(limit: int = None, dry_run: bool = False):
    """
    Met à jour entry_atr_pct_used et entry_atr_blended sur les lignes existantes.
    
    Args:
        limit: Nombre max de lignes à traiter (None = toutes)
        dry_run: Si True, ne fait que simuler sans modifier
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Trouver les métriques avec colonnes NULL
    query = """
        SELECT 
            m.id,
            m.trade_id,
            m.entry_atr_1m,
            m.entry_atr_5m,
            t.entry_price,
            t.config_snapshot,
            t.symbol
        FROM trade_atr_metrics m
        JOIN trades t ON t.id = m.trade_id
        WHERE (m.entry_atr_pct_used IS NULL OR m.entry_atr_blended IS NULL)
          AND m.entry_atr_1m IS NOT NULL
        ORDER BY m.created_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    metrics = cur.fetchall()
    
    print(f"[INFO] Métriques ATR à mettre à jour: {len(metrics)}")
    
    if not metrics:
        print("[OK] Aucune métrique à mettre à jour")
        return
    
    updated = 0
    errors = 0
    
    for metric in metrics:
        metric_id = metric['id']
        trade_id = metric['trade_id']
        
        try:
            # Extraire config_snapshot
            config_snapshot = metric['config_snapshot'] or {}
            if isinstance(config_snapshot, str):
                config_snapshot = json.loads(config_snapshot)
            
            # ATR à l'entrée
            entry_atr_1m = extract_numeric(metric['entry_atr_1m'])
            entry_atr_5m = extract_numeric(metric['entry_atr_5m'])
            entry_price = extract_numeric(metric['entry_price'])
            
            # Calculer entry_atr_blended (70% ATR_1m + 30% ATR_5m)
            entry_atr_blended = None
            if entry_atr_1m is not None:
                if entry_atr_5m is not None and entry_atr_5m > 0:
                    entry_atr_blended = 0.7 * entry_atr_1m + 0.3 * entry_atr_5m
                else:
                    entry_atr_blended = entry_atr_1m
            
            # Calculer entry_atr_pct_used (après clamp)
            entry_atr_pct_used = None
            if entry_atr_blended is not None and entry_price and entry_price > 0:
                raw_pct = (entry_atr_blended / entry_price) * 100
                # Clamp entre atr_min et atr_max
                atr_min = extract_numeric(config_snapshot.get('atr_min')) or 0.10
                atr_max = extract_numeric(config_snapshot.get('atr_max')) or 1.0
                entry_atr_pct_used = max(atr_min, min(raw_pct, atr_max))
            
            if dry_run:
                print(f"  [DRY-RUN] Metric {metric_id} ({metric['symbol']}) - "
                      f"blended={entry_atr_blended:.6f if entry_atr_blended else 'N/A'}, "
                      f"pct_used={entry_atr_pct_used:.4f if entry_atr_pct_used else 'N/A'}%")
                updated += 1
                continue
            
            # UPDATE
            update_query = """
                UPDATE trade_atr_metrics
                SET entry_atr_pct_used = %s,
                    entry_atr_blended = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            
            cur.execute(update_query, (entry_atr_pct_used, entry_atr_blended, metric_id))
            updated += 1
            
            if updated % 100 == 0:
                conn.commit()
                print(f"  [OK] {updated} métriques mises à jour...")
        
        except Exception as e:
            errors += 1
            print(f"  [ERR] Erreur metric {metric_id}: {e}")
            continue
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"RESULTAT UPDATE")
    print(f"{'='*60}")
    print(f"  Métriques traitées: {len(metrics)}")
    print(f"  Mises à jour: {updated}")
    print(f"  Erreurs: {errors}")
    if dry_run:
        print(f"  [!] MODE DRY-RUN - Aucune modification réelle")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Update entry_atr_pct_used/blended sur trade_atr_metrics existantes')
    parser.add_argument('--limit', type=int, default=None, help='Nombre max de métriques à traiter')
    parser.add_argument('--dry-run', action='store_true', help='Simuler sans modifier')
    
    args = parser.parse_args()
    
    print("UPDATE TRADE_ATR_METRICS - COLONNES ATR USED/BLENDED")
    print("="*60)
    
    update_existing_atr_metrics(limit=args.limit, dry_run=args.dry_run)
