# -*- coding: utf-8 -*-
"""
Analyse qualite des donnees ML - Identifier les sources de bruit
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine
from urllib.parse import quote_plus

print("=" * 70)
print("  ANALYSE QUALITE DES DONNEES ML")
print("=" * 70)

# Connexion DB
env_path = Path('.env')
env_vars = {}
try:
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
except FileNotFoundError:
    print("Fichier .env non trouvé. Ce script nécessite un fichier .env avec les variables PostgreSQL.")
    exit(0)  # Exit gracefully for test environment

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
try:
    engine = create_engine(conn_str)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception as e:
    print(f"Impossible de se connecter à PostgreSQL: {e}")
    print("Ce script nécessite une base de données PostgreSQL active.")
    exit(0)  # Exit gracefully for test environment

# Charger trades
print("\n=== ANALYSE TABLE TRADES ===")
trades_df = pd.read_sql("SELECT * FROM trades", engine)
print(f"Total trades: {len(trades_df)}")

# Colonnes disponibles
print(f"\nColonnes: {trades_df.columns.tolist()[:20]}...")

# Verifier les colonnes pertinentes
if 'close_reason' in trades_df.columns:
    print("\n--- Raisons de fermeture ---")
    close_reasons = trades_df['close_reason'].value_counts()
    print(close_reasons)
    
    manual_count = trades_df[trades_df['close_reason'].str.contains('manual|MANUAL|Manuel', na=False, case=False)].shape[0]
    print(f"\nTrades fermes manuellement: {manual_count} ({manual_count/len(trades_df)*100:.1f}%)")

if 'exit_type' in trades_df.columns:
    print("\n--- Types de sortie ---")
    print(trades_df['exit_type'].value_counts())

# Verifier les parametres TP/SL
tp_cols = [c for c in trades_df.columns if 'tp' in c.lower() or 'take_profit' in c.lower()]
sl_cols = [c for c in trades_df.columns if 'sl' in c.lower() or 'stop_loss' in c.lower()]

print(f"\nColonnes TP trouvees: {tp_cols}")
print(f"Colonnes SL trouvees: {sl_cols}")

if tp_cols:
    for col in tp_cols[:3]:
        if trades_df[col].dtype in ['float64', 'int64']:
            print(f"\n{col}: min={trades_df[col].min()}, max={trades_df[col].max()}, unique={trades_df[col].nunique()}")

# Verifier les dates
if 'created_at' in trades_df.columns or 'timestamp' in trades_df.columns:
    date_col = 'created_at' if 'created_at' in trades_df.columns else 'timestamp'
    trades_df[date_col] = pd.to_datetime(trades_df[date_col])
    
    print(f"\n--- Distribution temporelle ---")
    print(f"Premier trade: {trades_df[date_col].min()}")
    print(f"Dernier trade: {trades_df[date_col].max()}")
    
    # Trades par semaine
    trades_df['week'] = trades_df[date_col].dt.isocalendar().week
    weekly = trades_df.groupby('week').size()
    print(f"\nTrades par semaine (dernieres 5):")
    print(weekly.tail())

# Charger ml_features
print("\n\n=== ANALYSE TABLE ML_FEATURES ===")
ml_df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
print(f"Total samples ML: {len(ml_df)}")

# Distribution target
if 'target_pnl' in ml_df.columns:
    print(f"\n--- Distribution target_pnl ---")
    print(f"Min: {ml_df['target_pnl'].min():.2f}%")
    print(f"Max: {ml_df['target_pnl'].max():.2f}%")
    print(f"Mean: {ml_df['target_pnl'].mean():.2f}%")
    print(f"Positifs: {(ml_df['target_pnl'] > 0).sum()} ({(ml_df['target_pnl'] > 0).sum()/len(ml_df)*100:.1f}%)")
    print(f"Negatifs: {(ml_df['target_pnl'] <= 0).sum()} ({(ml_df['target_pnl'] <= 0).sum()/len(ml_df)*100:.1f}%)")

# Verifier config_* colonnes
config_cols = [c for c in ml_df.columns if c.startswith('config_')]
if config_cols:
    print(f"\n--- Colonnes config detectees ---")
    for col in config_cols[:10]:
        if ml_df[col].dtype in ['float64', 'int64']:
            unique = ml_df[col].nunique()
            if unique > 1:
                print(f"{col}: {unique} valeurs differentes")

engine.dispose()

print("\n" + "=" * 70)
print("  RECOMMANDATIONS")
print("=" * 70)
print("""
1. TRADES MANUELS: Exclure les trades fermes manuellement
   -> Le resultat ne reflete pas la qualite du setup

2. PARAMETRES DIFFERENTS: Filtrer par config similaire
   -> Un meme setup peut etre +/- selon TP/SL

3. DONNEES ANCIENNES: Garder seulement les 30-60 derniers jours
   -> Les conditions de marche changent

4. VERIFICATION: Avant de re-entrainer, nettoyer la table ml_features
""")
