#!/usr/bin/env python3
"""Script pour vérifier les indicateurs d'entrée dans PostgreSQL"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def verify_indicators():
    """Vérifie les indicateurs d'entrée dans la table trades"""
    
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Requête pour compter les indicateurs remplis
    query = """
        SELECT 
            COUNT(*) as total_trades,
            COUNT(entry_rsi_1m) FILTER (WHERE entry_rsi_1m IS NOT NULL) as trades_with_rsi_1m,
            COUNT(entry_rsi_5m) FILTER (WHERE entry_rsi_5m IS NOT NULL) as trades_with_rsi_5m,
            COUNT(entry_macd_hist_1m) FILTER (WHERE entry_macd_hist_1m IS NOT NULL) as trades_with_macd_hist_1m,
            COUNT(entry_macd_hist_5m) FILTER (WHERE entry_macd_hist_5m IS NOT NULL) as trades_with_macd_hist_5m,
            COUNT(entry_adx_1m) FILTER (WHERE entry_adx_1m IS NOT NULL) as trades_with_adx_1m,
            COUNT(entry_adx_5m) FILTER (WHERE entry_adx_5m IS NOT NULL) as trades_with_adx_5m,
            COUNT(entry_ema9_1m) FILTER (WHERE entry_ema9_1m IS NOT NULL) as trades_with_ema9_1m,
            COUNT(entry_ema21_1m) FILTER (WHERE entry_ema21_1m IS NOT NULL) as trades_with_ema21_1m,
            COUNT(entry_atr_1m) FILTER (WHERE entry_atr_1m IS NOT NULL) as trades_with_atr_1m,
            COUNT(entry_atr_5m) FILTER (WHERE entry_atr_5m IS NOT NULL) as trades_with_atr_5m,
            COUNT(entry_score) FILTER (WHERE entry_score IS NOT NULL) as trades_with_score
        FROM trades;
    """
    
    cur.execute(query)
    result = cur.fetchone()
    
    print("=" * 60)
    print("VÉRIFICATION DES INDICATEURS D'ENTRÉE")
    print("=" * 60)
    print(f"Total trades: {result['total_trades']}")
    
    if result['total_trades'] == 0:
        print("\n⚠️ Aucun trade trouvé dans la base de données.")
        print("   Attendez qu'un trade soit ouvert et fermé, puis réessayez.")
        cur.close()
        conn.close()
        return
    
    print(f"\nIndicateurs RSI:")
    print(f"  - RSI 1m: {result['trades_with_rsi_1m']}/{result['total_trades']} ({result['trades_with_rsi_1m']/result['total_trades']*100:.1f}%)")
    print(f"  - RSI 5m: {result['trades_with_rsi_5m']}/{result['total_trades']} ({result['trades_with_rsi_5m']/result['total_trades']*100:.1f}%)")
    print(f"\nIndicateurs MACD:")
    print(f"  - MACD Hist 1m: {result['trades_with_macd_hist_1m']}/{result['total_trades']} ({result['trades_with_macd_hist_1m']/result['total_trades']*100:.1f}%)")
    print(f"  - MACD Hist 5m: {result['trades_with_macd_hist_5m']}/{result['total_trades']} ({result['trades_with_macd_hist_5m']/result['total_trades']*100:.1f}%)")
    print(f"\nIndicateurs ADX:")
    print(f"  - ADX 1m: {result['trades_with_adx_1m']}/{result['total_trades']} ({result['trades_with_adx_1m']/result['total_trades']*100:.1f}%)")
    print(f"  - ADX 5m: {result['trades_with_adx_5m']}/{result['total_trades']} ({result['trades_with_adx_5m']/result['total_trades']*100:.1f}%)")
    print(f"\nIndicateurs EMA:")
    print(f"  - EMA9 1m: {result['trades_with_ema9_1m']}/{result['total_trades']} ({result['trades_with_ema9_1m']/result['total_trades']*100:.1f}%)")
    print(f"  - EMA21 1m: {result['trades_with_ema21_1m']}/{result['total_trades']} ({result['trades_with_ema21_1m']/result['total_trades']*100:.1f}%)")
    print(f"\nIndicateurs ATR:")
    print(f"  - ATR 1m: {result['trades_with_atr_1m']}/{result['total_trades']} ({result['trades_with_atr_1m']/result['total_trades']*100:.1f}%)")
    print(f"  - ATR 5m: {result['trades_with_atr_5m']}/{result['total_trades']} ({result['trades_with_atr_5m']/result['total_trades']*100:.1f}%)")
    print(f"\nScore:")
    print(f"  - Score: {result['trades_with_score']}/{result['total_trades']} ({result['trades_with_score']/result['total_trades']*100:.1f}%)")
    
    # Voir le dernier trade
    query_last = """
        SELECT 
            id,
            symbol,
            direction,
            timestamp_entry,
            entry_rsi_1m,
            entry_rsi_5m,
            entry_macd_hist_1m,
            entry_macd_hist_5m,
            entry_adx_1m,
            entry_adx_5m,
            entry_score,
            entry_conditions
        FROM trades
        ORDER BY timestamp_entry DESC
        LIMIT 1;
    """
    
    cur.execute(query_last)
    last_trade = cur.fetchone()
    
    if last_trade:
        print("\n" + "=" * 60)
        print("DERNIER TRADE")
        print("=" * 60)
        print(f"ID: {last_trade['id']}")
        print(f"Symbol: {last_trade['symbol']}")
        print(f"Direction: {last_trade['direction']}")
        print(f"Timestamp: {last_trade['timestamp_entry']}")
        print(f"\nIndicateurs:")
        print(f"  - RSI 1m: {last_trade['entry_rsi_1m']}")
        print(f"  - RSI 5m: {last_trade['entry_rsi_5m']}")
        print(f"  - MACD Hist 1m: {last_trade['entry_macd_hist_1m']}")
        print(f"  - MACD Hist 5m: {last_trade['entry_macd_hist_5m']}")
        print(f"  - ADX 1m: {last_trade['entry_adx_1m']}")
        print(f"  - ADX 5m: {last_trade['entry_adx_5m']}")
        print(f"  - Score: {last_trade['entry_score']}")
        print(f"  - Conditions: {last_trade['entry_conditions']}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    verify_indicators()

