#!/usr/bin/env python3
"""
TEST EXPORT ORDER FLOW
======================
Test direct de l'export Excel pour vérifier les colonnes order flow.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import psycopg2
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'trade_cursor_ml'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def test_scan_logs_export():
    """Test export scan_logs avec colonnes order flow"""
    conn = get_conn()
    
    query = """
    SELECT * FROM scan_logs 
    ORDER BY timestamp DESC LIMIT 5
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("📋 SCAN_LOGS EXPORT TEST")
    print(f"Colonnes totales: {len(df.columns)}")
    print(f"Lignes: {len(df)}")
    
    orderflow_cols = [
        'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
        'book_depth_ratio', 'volume_acceleration', 'price_momentum_5'
    ]
    
    print("\n🎯 Colonnes Order Flow:")
    for col in orderflow_cols:
        if col in df.columns:
            non_null = df[col].notna().sum()
            print(f"  ✅ {col}: {non_null}/{len(df)} non-null")
        else:
            print(f"  ❌ {col}: MANQUANTE")
    
    return df

def test_trades_export():
    """Test export trades avec colonnes order flow"""
    conn = get_conn()
    
    query = """
    SELECT * FROM trades 
    ORDER BY timestamp_entry DESC LIMIT 5
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print("\n📋 TRADES EXPORT TEST")
    print(f"Colonnes totales: {len(df.columns)}")
    print(f"Lignes: {len(df)}")
    
    orderflow_cols = [
        'delta_volume', 'imbalance_normalized', 'book_depth_ratio'
    ]
    
    print("\n🎯 Colonnes Order Flow:")
    for col in orderflow_cols:
        if col in df.columns:
            non_null = df[col].notna().sum()
            print(f"  ✅ {col}: {non_null}/{len(df)} non-null")
        else:
            print(f"  ❌ {col}: MANQUANTE")
    
    return df

def test_api_export():
    """Test l'API export directement"""
    import requests
    
    print("\n🌐 API EXPORT TEST")
    try:
        response = requests.get('http://localhost:8000/api/datalogger/export/excel')
        if response.status_code == 200:
            print("✅ API export répond OK")
            # Sauvegarder pour inspection manuelle
            with open('test_export_orderflow.xlsx', 'wb') as f:
                f.write(response.content)
            print("📁 Fichier sauvegardé: test_export_orderflow.xlsx")
        else:
            print(f"❌ Erreur API: {response.status_code}")
            print(response.text[:500])
    except Exception as e:
        print(f"❌ Erreur connexion API: {e}")

def main():
    print("=" * 60)
    print("  TEST EXPORT ORDER FLOW")
    print("=" * 60)
    
    # Test direct SQL
    scan_df = test_scan_logs_export()
    trades_df = test_trades_export()
    
    # Test API
    test_api_export()
    
    print("\n" + "=" * 60)
    print("  ANALYSE:")
    print("=" * 60)
    
    scan_orderflow = [c for c in scan_df.columns if c in [
        'delta_volume', 'imbalance_normalized', 'spread_volatility_5',
        'book_depth_ratio', 'volume_acceleration', 'price_momentum_5'
    ]]
    
    trades_orderflow = [c for c in trades_df.columns if c in [
        'delta_volume', 'imbalance_normalized', 'book_depth_ratio'
    ]]
    
    print(f"scan_logs order flow columns: {len(scan_orderflow)}/6")
    print(f"trades order flow columns: {len(trades_orderflow)}/3")
    
    if len(scan_orderflow) == 6 and len(trades_orderflow) == 3:
        print("\n✅ Toutes les colonnes order flow sont présentes en SQL")
        print("🔍 Vérifiez le fichier Excel généré manuellement")
    else:
        print("\n❌ Colonnes manquantes - problème de schéma")

if __name__ == "__main__":
    main()
