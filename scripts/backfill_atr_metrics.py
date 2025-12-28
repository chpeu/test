#!/usr/bin/env python3
"""
Script de backfill pour rétro-remplir les métriques ATR manquantes
dans la table trade_atr_metrics à partir des données existantes dans trades.
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


def backfill_trade_atr_metrics(limit: int = None, dry_run: bool = False):
    """
    Backfill les métriques ATR pour les trades qui n'en ont pas.
    
    Args:
        limit: Nombre max de trades à traiter (None = tous)
        dry_run: Si True, ne fait que simuler sans insérer
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Trouver les trades sans métriques ATR
    query = """
        SELECT 
            t.id,
            t.symbol,
            t.direction,
            t.entry_price,
            t.exit_price,
            t.sl_price,
            t.tp_price,
            t.exit_reason,
            t.net_pnl_pct,
            t.break_even_set,
            t.trailing_stop_activated,
            t.stagnation_positive_triggered,
            t.stagnation_mfe_at_exit,
            t.stagnation_pullback_at_exit,
            t.config_snapshot,
            t.config_stagnation_positive_exit_enabled,
            t.config_stagnation_positive_threshold,
            t.config_stagnation_positive_timeout_seconds,
            t.entry_atr_1m,
            t.entry_atr_5m,
            t.entry_atr_pct_1m,
            t.entry_atr_pct_5m,
            t.entry_adx_1m,
            t.created_at
        FROM trades t
        LEFT JOIN trade_atr_metrics m ON t.id = m.trade_id
        WHERE m.id IS NULL
          AND t.tp_sl_mode = 'ATR'
          AND t.timestamp_exit IS NOT NULL
        ORDER BY t.created_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cur.execute(query)
    trades = cur.fetchall()
    
    print(f"[INFO] Trades sans metriques ATR: {len(trades)}")
    
    if not trades:
        print("[OK] Aucun trade a backfiller")
        return
    
    inserted = 0
    errors = 0
    
    for trade in trades:
        trade_id = trade['id']
        
        try:
            # Extraire config_snapshot
            config_snapshot = trade['config_snapshot'] or {}
            if isinstance(config_snapshot, str):
                config_snapshot = json.loads(config_snapshot)
            
            # Paramètres ATR
            param_atr_mult_sl = extract_numeric(config_snapshot.get('atr_mult_sl'))
            param_atr_mult_tp = extract_numeric(config_snapshot.get('atr_mult_tp'))
            param_trailing_trigger_mult = extract_numeric(config_snapshot.get('trailing_trigger_atr_mult'))
            param_trailing_distance_mult = extract_numeric(
                config_snapshot.get('trailing_distance_atr_mult') or 
                config_snapshot.get('trailing_atr_multiplier')
            )
            param_be_atr_mult = extract_numeric(config_snapshot.get('break_even_atr_mult'))
            param_stagnation_timeout = config_snapshot.get('stagnation_exit_timeout_seconds')
            param_stagnation_min_pnl = extract_numeric(config_snapshot.get('stagnation_exit_min_pnl_to_stay'))
            
            # Stagnation Positive config
            param_stagnation_positive_enabled = (
                trade['config_stagnation_positive_exit_enabled'] or
                config_snapshot.get('stagnation_positive_exit_enabled', False)
            )
            param_stagnation_positive_threshold = (
                extract_numeric(trade['config_stagnation_positive_threshold']) or
                extract_numeric(config_snapshot.get('stagnation_positive_threshold'))
            )
            param_stagnation_positive_timeout = (
                trade['config_stagnation_positive_timeout_seconds'] or
                config_snapshot.get('stagnation_positive_timeout_seconds')
            )
            
            # Trailing MFE config
            param_trailing_mfe_enabled = config_snapshot.get('trailing_mfe_enabled', False)
            param_trailing_mfe_trigger_pct = extract_numeric(config_snapshot.get('trailing_mfe_trigger_pct'))
            
            # Stagnation MFE Protection config
            param_stagnation_mfe_tracking = config_snapshot.get('stagnation_use_mfe_tracking', False)
            param_stagnation_mfe_pullback_pct = extract_numeric(config_snapshot.get('stagnation_mfe_pullback_pct'))
            
            # ATR a l'entree (directement depuis colonnes trades)
            entry_atr_1m = extract_numeric(trade['entry_atr_1m'])
            entry_atr_5m = extract_numeric(trade['entry_atr_5m'])
            entry_atr_pct_1m = extract_numeric(trade['entry_atr_pct_1m'])
            entry_atr_pct_5m = extract_numeric(trade['entry_atr_pct_5m'])
            entry_adx = extract_numeric(trade['entry_adx_1m'])
            
            # Régime de volatilité
            market_volatility_state = None
            if entry_atr_pct_1m is not None:
                if entry_atr_pct_1m < 0.2:
                    market_volatility_state = 'LOW'
                elif entry_atr_pct_1m < 0.5:
                    market_volatility_state = 'MEDIUM'
                else:
                    market_volatility_state = 'HIGH'
            
            # Régime de trend
            market_trend_state = None
            if entry_adx is not None:
                if entry_adx < 20:
                    market_trend_state = 'RANGING'
                elif entry_adx < 30:
                    market_trend_state = 'TRENDING_WEAK'
                else:
                    market_trend_state = 'TRENDING_STRONG'
            
            # Niveaux calculés
            entry_price = extract_numeric(trade['entry_price'])
            sl_price = extract_numeric(trade['sl_price'])
            tp_price = extract_numeric(trade['tp_price'])
            
            calculated_sl_pct = None
            calculated_tp_pct = None
            if entry_price and sl_price:
                calculated_sl_pct = abs(entry_price - sl_price) / entry_price * 100
                if calculated_sl_pct < 0.001:
                    calculated_sl_pct = None
            if entry_price and tp_price:
                calculated_tp_pct = abs(tp_price - entry_price) / entry_price * 100
                if calculated_tp_pct < 0.001:
                    calculated_tp_pct = None
            
            # BE/Trailing triggers calculés
            calculated_be_trigger_pnl_pct = None
            if param_be_atr_mult and entry_atr_pct_1m:
                calculated_be_trigger_pnl_pct = param_be_atr_mult * entry_atr_pct_1m
            
            calculated_trailing_trigger_pnl_pct = None
            if param_trailing_trigger_mult and entry_atr_pct_1m:
                calculated_trailing_trigger_pnl_pct = param_trailing_trigger_mult * entry_atr_pct_1m
            
            # Événements
            be_triggered = trade['break_even_set'] or False
            trailing_activated = trade['trailing_stop_activated'] or False
            
            # Stagnation metrics
            stagnation_positive_triggered = trade['stagnation_positive_triggered'] or False
            stagnation_mfe_at_exit = extract_numeric(trade['stagnation_mfe_at_exit'])
            stagnation_pullback_at_exit = extract_numeric(trade['stagnation_pullback_at_exit'])
            
            # Déduire stagnation_detected si exit_reason contient STAGNATION
            exit_reason = trade['exit_reason'] or ''
            stagnation_detected = 'STAGNATION' in exit_reason.upper()
            
            # Si exit_reason = STAGNATION_POSITIVE mais flag pas set, le corriger
            if exit_reason == 'STAGNATION_POSITIVE' and not stagnation_positive_triggered:
                stagnation_positive_triggered = True
            
            # SL MEXC calculé
            sl_mexc_margin = 1.1
            sl_mexc_pct = None
            sl_mexc_price = None
            if entry_atr_pct_1m and param_atr_mult_sl and entry_price:
                sl_atr_pct = entry_atr_pct_1m * param_atr_mult_sl
                sl_mexc_pct = sl_atr_pct * sl_mexc_margin
                direction = trade['direction'] or 'LONG'
                if direction == 'LONG':
                    sl_mexc_price = entry_price * (1 - sl_mexc_pct / 100)
                else:
                    sl_mexc_price = entry_price * (1 + sl_mexc_pct / 100)
            
            sl_mexc_touched = exit_reason == 'SL_EXCHANGE'
            
            # Session/Heure (approximé depuis created_at)
            created_at = trade['created_at']
            hour_utc = created_at.hour if created_at else None
            day_of_week = created_at.weekday() if created_at else None
            is_weekend = day_of_week in [5, 6] if day_of_week is not None else None
            
            # Déterminer la session approximative
            session_market = None
            if hour_utc is not None:
                if 0 <= hour_utc < 8:
                    session_market = 'ASIA'
                elif 8 <= hour_utc < 14:
                    session_market = 'EUROPE'
                elif 14 <= hour_utc < 21:
                    session_market = 'US'
                else:
                    session_market = 'ASIA'
            
            if dry_run:
                print(f"  [DRY-RUN] Trade {trade_id[:8]}... ({trade['symbol']}) - "
                      f"stag_pos={stagnation_positive_triggered}, mfe={stagnation_mfe_at_exit}, reason={exit_reason}")
                inserted += 1
                continue
            
            # INSERT
            insert_query = """
                INSERT INTO trade_atr_metrics (
                    trade_id,
                    entry_atr_1m, entry_atr_5m, entry_atr_pct_1m, entry_atr_pct_5m,
                    param_atr_mult_sl, param_atr_mult_tp,
                    param_trailing_trigger_mult, param_trailing_distance_mult,
                    param_be_atr_mult, param_stagnation_timeout, param_stagnation_min_pnl,
                    market_volatility_state, market_trend_state, entry_adx,
                    calculated_sl_price, calculated_tp_price,
                    calculated_sl_pct, calculated_tp_pct,
                    calculated_be_trigger_pnl_pct, calculated_trailing_trigger_pnl_pct,
                    be_triggered, trailing_activated,
                    stagnation_detected,
                    param_stagnation_positive_enabled, param_stagnation_positive_threshold, param_stagnation_positive_timeout,
                    param_trailing_mfe_enabled, param_trailing_mfe_trigger_pct,
                    param_stagnation_mfe_tracking, param_stagnation_mfe_pullback_pct,
                    stagnation_positive_triggered, stagnation_mfe_at_exit, stagnation_pullback_at_exit,
                    sl_mexc_price, sl_mexc_pct, sl_mexc_margin_used,
                    sl_mexc_touched,
                    session_market, hour_utc, day_of_week, is_weekend
                ) VALUES (
                    %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s, %s
                )
            """
            
            params = (
                trade_id,
                entry_atr_1m, entry_atr_5m, entry_atr_pct_1m, entry_atr_pct_5m,
                param_atr_mult_sl, param_atr_mult_tp,
                param_trailing_trigger_mult, param_trailing_distance_mult,
                param_be_atr_mult, param_stagnation_timeout, param_stagnation_min_pnl,
                market_volatility_state, market_trend_state, entry_adx,
                sl_price, tp_price,
                calculated_sl_pct, calculated_tp_pct,
                calculated_be_trigger_pnl_pct, calculated_trailing_trigger_pnl_pct,
                be_triggered, trailing_activated,
                stagnation_detected,
                param_stagnation_positive_enabled, param_stagnation_positive_threshold, param_stagnation_positive_timeout,
                param_trailing_mfe_enabled, param_trailing_mfe_trigger_pct,
                param_stagnation_mfe_tracking, param_stagnation_mfe_pullback_pct,
                stagnation_positive_triggered, stagnation_mfe_at_exit, stagnation_pullback_at_exit,
                sl_mexc_price, sl_mexc_pct, sl_mexc_margin,
                sl_mexc_touched,
                session_market, hour_utc, day_of_week, is_weekend
            )
            
            cur.execute(insert_query, params)
            inserted += 1
            
            if inserted % 100 == 0:
                conn.commit()
                print(f"  [OK] {inserted} metriques inserees...")
        
        except Exception as e:
            errors += 1
            print(f"  [ERR] Erreur trade {trade_id[:8]}...: {e}")
            continue
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"RESULTAT BACKFILL")
    print(f"{'='*60}")
    print(f"  Trades traités: {len(trades)}")
    print(f"  Métriques insérées: {inserted}")
    print(f"  Erreurs: {errors}")
    if dry_run:
        print(f"  [!] MODE DRY-RUN - Aucune insertion reelle")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill trade_atr_metrics manquantes')
    parser.add_argument('--limit', type=int, default=None, help='Nombre max de trades à traiter')
    parser.add_argument('--dry-run', action='store_true', help='Simuler sans insérer')
    
    args = parser.parse_args()
    
    print("BACKFILL TRADE_ATR_METRICS")
    print("="*60)
    
    backfill_trade_atr_metrics(limit=args.limit, dry_run=args.dry_run)
