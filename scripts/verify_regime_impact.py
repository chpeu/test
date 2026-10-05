#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
Vérifie l'impact réel des paramètres de régime sur les performances.
Analyse les deux niveaux: MarketRegime (CALME/NORMAL/VOLATILE) et LocalRegime (LOW/MEDIUM/HIGH)
"""

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "trade_cursor_ml"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

def analyze_regime_usage():
    """Analyse comment les régimes sont utilisés et leur impact"""
    conn = get_connection()
    
    print("="*70)
    print("VERIFICATION REGIME - IMPACT SUR PERFORMANCE")
    print("="*70)
    
    # 1. Vérifier les régimes stockés dans trades
    print("\n[1] Régimes stockés dans trades (entry_market_regime):")
    query1 = """
    SELECT 
        entry_market_regime,
        COUNT(*) as n,
        ROUND(AVG(net_pnl_usdt)::numeric, 4) as avg_pnl_usdt,
        ROUND(AVG(pnl_pct)::numeric, 4) as avg_pnl_pct,
        ROUND(100.0 * SUM(CASE WHEN net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
    FROM trades 
    WHERE tp_sl_mode = 'ATR' AND timestamp_exit IS NOT NULL
    GROUP BY entry_market_regime
    ORDER BY n DESC
    """
    df1 = pd.read_sql(query1, conn)
    print(df1.to_string(index=False))
    
    # 2. Vérifier market_volatility_state dans trade_atr_metrics
    print("\n[2] Régimes dans trade_atr_metrics (market_volatility_state):")
    query2 = """
    SELECT 
        m.market_volatility_state,
        COUNT(*) as n,
        ROUND(AVG(t.net_pnl_usdt)::numeric, 4) as avg_pnl_usdt,
        ROUND(AVG(t.pnl_pct)::numeric, 4) as avg_pnl_pct,
        ROUND(100.0 * SUM(CASE WHEN t.net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' AND t.timestamp_exit IS NOT NULL
    GROUP BY m.market_volatility_state
    ORDER BY n DESC
    """
    df2 = pd.read_sql(query2, conn)
    print(df2.to_string(index=False))
    
    # 3. Analyse des paramètres effectivement utilisés par régime
    print("\n[3] Paramètres ATR effectivement utilisés par régime:")
    query3 = """
    SELECT 
        m.market_volatility_state as regime,
        COUNT(*) as n,
        ROUND(AVG(m.param_atr_mult_sl)::numeric, 3) as avg_sl_mult,
        ROUND(AVG(m.param_atr_mult_tp)::numeric, 3) as avg_tp_mult,
        ROUND(AVG(m.param_be_atr_mult)::numeric, 3) as avg_be_mult,
        ROUND(AVG(m.param_trailing_trigger_mult)::numeric, 3) as avg_trail_mult,
        ROUND(AVG(m.calculated_sl_pct)::numeric, 3) as avg_sl_pct,
        ROUND(AVG(m.calculated_tp_pct)::numeric, 3) as avg_tp_pct
    FROM trade_atr_metrics m
    JOIN trades t ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' AND t.timestamp_exit IS NOT NULL
    GROUP BY m.market_volatility_state
    ORDER BY n DESC
    """
    df3 = pd.read_sql(query3, conn)
    print(df3.to_string(index=False))
    
    # 4. Croisement régime global vs local
    print("\n[4] Croisement entry_market_regime (global) vs market_volatility_state (local):")
    query4 = """
    SELECT 
        t.entry_market_regime as global_regime,
        m.market_volatility_state as local_regime,
        COUNT(*) as n,
        ROUND(AVG(t.net_pnl_usdt)::numeric, 4) as avg_pnl
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' AND t.timestamp_exit IS NOT NULL
      AND t.entry_market_regime IS NOT NULL
    GROUP BY t.entry_market_regime, m.market_volatility_state
    ORDER BY n DESC
    LIMIT 15
    """
    df4 = pd.read_sql(query4, conn)
    print(df4.to_string(index=False))
    
    # 5. Performance par exit_reason et régime
    print("\n[5] Performance par exit_reason et régime (top combinaisons):")
    query5 = """
    SELECT 
        m.market_volatility_state as regime,
        t.exit_reason,
        COUNT(*) as n,
        ROUND(AVG(t.net_pnl_usdt)::numeric, 4) as avg_pnl,
        ROUND(100.0 * SUM(CASE WHEN t.net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' AND t.timestamp_exit IS NOT NULL
    GROUP BY m.market_volatility_state, t.exit_reason
    HAVING COUNT(*) >= 20
    ORDER BY regime, n DESC
    """
    df5 = pd.read_sql(query5, conn)
    print(df5.to_string(index=False))
    
    # 6. Simulation: impact si on change le TP mult
    print("\n[6] Simulation impact TP (basé sur max_pnl_reached):")
    query6 = """
    SELECT 
        m.market_volatility_state as regime,
        COUNT(*) as n,
        ROUND(AVG(t.pnl_pct)::numeric, 4) as actual_pnl_pct,
        ROUND(AVG(m.max_pnl_reached)::numeric, 4) as avg_mfe,
        ROUND(AVG(m.max_pnl_reached - t.pnl_pct)::numeric, 4) as missed_opportunity,
        ROUND(AVG(m.calculated_tp_pct)::numeric, 4) as avg_tp_target,
        -- Trades qui auraient atteint un TP plus élevé
        ROUND(100.0 * SUM(CASE WHEN m.max_pnl_reached > m.calculated_tp_pct * 1.5 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as pct_would_hit_tp_x1_5
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' 
      AND t.timestamp_exit IS NOT NULL
      AND m.max_pnl_reached IS NOT NULL
      AND m.calculated_tp_pct > 0
    GROUP BY m.market_volatility_state
    ORDER BY n DESC
    """
    df6 = pd.read_sql(query6, conn)
    print(df6.to_string(index=False))
    
    # 7. Vérifier si les ajustements régime sont bien appliqués
    print("\n[7] Vérification: paramètres varient-ils selon le régime?")
    query7 = """
    SELECT 
        m.market_volatility_state as regime,
        ROUND(MIN(m.param_atr_mult_sl)::numeric, 2) as min_sl,
        ROUND(MAX(m.param_atr_mult_sl)::numeric, 2) as max_sl,
        ROUND(STDDEV(m.param_atr_mult_sl)::numeric, 3) as std_sl,
        ROUND(MIN(m.param_atr_mult_tp)::numeric, 2) as min_tp,
        ROUND(MAX(m.param_atr_mult_tp)::numeric, 2) as max_tp,
        ROUND(STDDEV(m.param_atr_mult_tp)::numeric, 3) as std_tp
    FROM trade_atr_metrics m
    JOIN trades t ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' AND t.timestamp_exit IS NOT NULL
      AND m.param_atr_mult_sl IS NOT NULL
    GROUP BY m.market_volatility_state
    ORDER BY regime
    """
    df7 = pd.read_sql(query7, conn)
    print(df7.to_string(index=False))
    
    # 8. Tendance récente (derniers 7 jours)
    print("\n[8] Performance récente (7 derniers jours) par régime:")
    query8 = """
    SELECT 
        m.market_volatility_state as regime,
        COUNT(*) as n,
        ROUND(AVG(t.net_pnl_usdt)::numeric, 4) as avg_pnl,
        ROUND(100.0 * SUM(CASE WHEN t.net_pnl_usdt > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate,
        ROUND(AVG(m.param_atr_mult_tp)::numeric, 2) as avg_tp_mult
    FROM trades t
    JOIN trade_atr_metrics m ON t.id = m.trade_id
    WHERE t.tp_sl_mode = 'ATR' 
      AND t.timestamp_exit IS NOT NULL
      AND t.timestamp_exit > NOW() - INTERVAL '7 days'
    GROUP BY m.market_volatility_state
    ORDER BY n DESC
    """
    df8 = pd.read_sql(query8, conn)
    print(df8.to_string(index=False))
    
    conn.close()
    
    print("\n" + "="*70)
    print("ANALYSE TERMINEE")
    print("="*70)

if __name__ == "__main__":
    analyze_regime_usage()
