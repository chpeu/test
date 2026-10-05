#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyser les configurations TP/SL actuelles
"""
import psycopg2

def analyze_tp_sl_config():
    """Vérifier les configurations TP/SL dans les trades récents"""
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="trade_cursor_ml",
        user="postgres",
        password="@Cmtr1di12345"
    )
    
    cursor = conn.cursor()
    
    # Récupérer les configs des derniers trades
    query = """
        SELECT 
            tp_sl_mode,
            AVG(net_pnl_pct) as avg_pnl,
            COUNT(*) as count,
            -- Extraire du config_snapshot
            (config_snapshot::json->>'atr_mult_tp')::float as atr_tp,
            (config_snapshot::json->>'atr_mult_sl')::float as atr_sl,
            (config_snapshot::json->>'tp_percent')::float as tp_pct,
            (config_snapshot::json->>'sl_percent')::float as sl_pct
        FROM trades 
        WHERE timestamp_exit >= NOW() - INTERVAL '24 hours'
        AND tp_sl_mode IS NOT NULL
        GROUP BY tp_sl_mode, atr_tp, atr_sl, tp_pct, sl_pct
        ORDER BY count DESC
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    print("⚙️  CONFIGURATIONS TP/SL ACTUELLES")
    print("=" * 60)
    
    for row in results:
        mode, avg_pnl, count, atr_tp, atr_sl, tp_pct, sl_pct = row
        print(f"\nMode: {mode}")
        print(f"  Trades: {count}")
        print(f"  PnL moyen: {avg_pnl:.3f}%")
        if mode == "ATR":
            print(f"  ATR TP: {atr_tp}x | ATR SL: {atr_sl}x")
            ratio = atr_tp / atr_sl if atr_sl else 0
            print(f"  Ratio TP/SL: {ratio:.2f}")
        else:
            print(f"  TP: {tp_pct:.1%} | SL: {sl_pct:.1%}")
            ratio = tp_pct / sl_pct if sl_pct else 0
            print(f"  Ratio TP/SL: {ratio:.2f}")
    
    # Vérifier la config actuelle dans config.py
    print("\n📋 CONFIGURATION ACTUELLE (config.py):")
    try:
        import sys
        sys.path.append('c:\\Users\\sebta\\Documents\\clone github\\test\\test')
        from config import TRADING_CONFIG
        
        print(f"  Mode: {TRADING_CONFIG.get('tp_sl_mode')}")
        if TRADING_CONFIG.get('tp_sl_mode') == 'ATR':
            print(f"  ATR TP: {TRADING_CONFIG.get('atr_mult_tp')}x")
            print(f"  ATR SL: {TRADING_CONFIG.get('atr_mult_sl')}x")
            ratio = TRADING_CONFIG.get('atr_mult_tp') / TRADING_CONFIG.get('atr_mult_sl')
            print(f"  Ratio théorique: {ratio:.2f}")
        else:
            print(f"  TP: {TRADING_CONFIG.get('tp_percent'):.1%}")
            print(f"  SL: {TRADING_CONFIG.get('sl_percent'):.1%}")
            ratio = TRADING_CONFIG.get('tp_percent') / TRADING_CONFIG.get('sl_percent')
            print(f"  Ratio théorique: {ratio:.2f}")
    except Exception as e:
        print(f"  Erreur lecture config: {e}")
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        analyze_tp_sl_config()
    except Exception as e:
        print(f"Erreur: {e}")
