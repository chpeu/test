# -*- coding: utf-8 -*-
"""
Nettoyer les donnees ML - Filtrer trades LIVE/DRYRUN avec configs identiques, exclure manuels
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

print("=" * 70)
print("  NETTOYAGE DONNEES ML - FINAL")
print("=" * 70)

# Connexion DB
env_path = Path('.env')
env_vars = {}
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn_str)

# =============================================================================
# ETAPE 1: Analyser les trades
# =============================================================================
print("\n=== ETAPE 1: ANALYSE DES TRADES ===")

trades_df = pd.read_sql("SELECT * FROM trades", engine)
print(f"Total trades: {len(trades_df)}")

# Distribution is_live_trade
print("\n--- is_live_trade ---")
print(trades_df['is_live_trade'].value_counts(dropna=False))

# Distribution live_execution_mode
print("\n--- live_execution_mode ---")
print(trades_df['live_execution_mode'].value_counts(dropna=False))

# Distribution exit_reason
print("\n--- exit_reason ---")
print(trades_df['exit_reason'].value_counts(dropna=False).head(15))

# =============================================================================
# ETAPE 2: Identifier les trades a exclure
# =============================================================================
print("\n=== ETAPE 2: CRITERES D'EXCLUSION ===")

initial_count = len(trades_df)

# 1. Garder TOUS les trades (paper, dryrun, live)
live_mask = pd.Series([True] * len(trades_df))  # Garder tous
excluded_paper = 0
print(f"1. Paper trades exclus: {excluded_paper} (on garde TOUS les trades)")

# 2. Exclure trades fermes manuellement
manual_keywords = ['manual', 'manu', 'user', 'forced', 'cancelled', 'cancel']
if 'exit_reason' in trades_df.columns:
    manual_mask = trades_df['exit_reason'].str.lower().str.contains('|'.join(manual_keywords), na=False)
    excluded_manual = manual_mask.sum()
    print(f"2. Trades fermes manuellement: {excluded_manual} ({excluded_manual/initial_count*100:.1f}%)")
else:
    manual_mask = pd.Series([False] * len(trades_df))
    excluded_manual = 0
    print("2. Colonne exit_reason non trouvee")

# 3. Analyser les configs TP/SL des trades LIVE/DRYRUN
live_trades = trades_df[live_mask & ~manual_mask]
print(f"\nTrades LIVE/DRYRUN non-manuels: {len(live_trades)}")

# Colonnes de config a verifier
config_cols = ['config_min_score_required', 'config_snr_threshold', 'config_volume_multiplier']
tp_sl_cols = ['tp_sl_mode']

print("\n--- Distribution des configs (trades LIVE/DRYRUN) ---")
for col in config_cols + tp_sl_cols:
    if col in live_trades.columns:
        print(f"\n{col}:")
        print(live_trades[col].value_counts(dropna=False))

# =============================================================================
# ETAPE 3: Choisir la config majoritaire
# =============================================================================
print("\n=== ETAPE 3: CONFIG MAJORITAIRE ===")

# Trouver la combinaison de config la plus frequente
config_majority = {}
for col in config_cols:
    if col in live_trades.columns and live_trades[col].notna().any():
        majority_val = live_trades[col].mode()
        if len(majority_val) > 0:
            config_majority[col] = majority_val.iloc[0]
            count = (live_trades[col] == config_majority[col]).sum()
            pct = count / len(live_trades) * 100
            print(f"  {col}: {config_majority[col]} ({pct:.1f}%)")

# =============================================================================
# ETAPE 4: Appliquer les filtres
# =============================================================================
print("\n=== ETAPE 4: FILTRAGE ===")

# Commencer avec les trades LIVE/DRYRUN non-manuels
filtered_trades = trades_df[live_mask & ~manual_mask].copy()
print(f"Apres exclusion paper + manual: {len(filtered_trades)}")

# Filtrer par config majoritaire
for col, value in config_majority.items():
    if col in filtered_trades.columns:
        before = len(filtered_trades)
        # Tolerance pour les floats
        if pd.isna(value):
            filtered_trades = filtered_trades[filtered_trades[col].isna()]
        elif isinstance(value, (float, np.floating)):
            filtered_trades = filtered_trades[
                (abs(filtered_trades[col] - value) < 0.01) | 
                (filtered_trades[col].isna() & pd.isna(value))
            ]
        else:
            filtered_trades = filtered_trades[filtered_trades[col] == value]
        excluded = before - len(filtered_trades)
        if excluded > 0:
            print(f"  Exclus ({col} != {value}): {excluded}")

print(f"\nTrades apres filtrage config: {len(filtered_trades)}")

# =============================================================================
# ETAPE 5: Mettre a jour ml_features
# =============================================================================
print("\n=== ETAPE 5: MISE A JOUR ML_FEATURES ===")

# Obtenir les scan_log_ids des trades filtres
valid_scan_ids = filtered_trades['scan_log_id'].dropna().unique()
print(f"Scan IDs valides: {len(valid_scan_ids)}")

# Charger ml_features
ml_df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
print(f"Total samples ml_features: {len(ml_df)}")

# Filtrer ml_features par scan_id
if 'scan_id' in ml_df.columns:
    ml_clean = ml_df[ml_df['scan_id'].isin(valid_scan_ids)].copy()
    print(f"Samples apres filtrage par scan_id: {len(ml_clean)}")
else:
    print("⚠️ Colonne scan_id non trouvee dans ml_features")
    ml_clean = ml_df.copy()

# Si pas assez de samples, garder tous les trades LIVE/DRYRUN non-manuels
if len(ml_clean) < 200:
    print(f"\n⚠️ Seulement {len(ml_clean)} samples - relaxation des criteres")
    # Utiliser tous les scan_ids des trades LIVE/DRYRUN non-manuels (sans filtrer par config)
    all_valid_scan_ids = trades_df[live_mask & ~manual_mask]['scan_log_id'].dropna().unique()
    ml_clean = ml_df[ml_df['scan_id'].isin(all_valid_scan_ids)].copy()
    print(f"Samples avec criteres relaxes: {len(ml_clean)}")

# Distribution finale
if 'target_pnl' in ml_clean.columns and len(ml_clean) > 0:
    positifs = (ml_clean['target_pnl'] > 0).sum()
    negatifs = (ml_clean['target_pnl'] <= 0).sum()
    print(f"\nDistribution finale:")
    print(f"  Positifs: {positifs} ({positifs/len(ml_clean)*100:.1f}%)")
    print(f"  Negatifs: {negatifs} ({negatifs/len(ml_clean)*100:.1f}%)")

# =============================================================================
# ETAPE 6: Sauvegarder
# =============================================================================
print("\n=== ETAPE 6: SAUVEGARDE ===")

if len(ml_clean) >= 100:
    # Sauvegarder dans nouvelle table
    table_name = 'ml_features_clean'
    
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        conn.commit()
    
    ml_clean.to_sql(table_name, engine, index=False, if_exists='replace')
    print(f"✅ Table {table_name} creee: {len(ml_clean)} samples")
    
    # Aussi en CSV
    csv_path = Path('data/ml_features_clean.csv')
    csv_path.parent.mkdir(exist_ok=True)
    ml_clean.to_csv(csv_path, index=False)
    print(f"✅ CSV sauvegarde: {csv_path}")
    
else:
    print(f"⚠️ Pas assez de samples ({len(ml_clean)})")

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)
print(f"""
  Trades initiaux:           {initial_count}
  - Paper trades exclus:     {excluded_paper}
  - Trades manuels exclus:   {excluded_manual}
  - Configs differentes:     {len(trades_df[live_mask & ~manual_mask]) - len(filtered_trades)}
  
  Trades finaux:             {len(filtered_trades)}
  Samples ML:                {len(ml_clean)}
  
  Pour utiliser les donnees nettoyees:
    1. Redemarrer le backend
    2. Modifier la requete SQL dans ml.py:
       FROM ml_features_clean WHERE target_pnl IS NOT NULL
    3. Ou lancer: python retrain_model.py
""")

engine.dispose()
print("=" * 70)
