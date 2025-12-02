# -*- coding: utf-8 -*-
"""
Nettoyer les donnees ML - Exclure trades avec parametres differents et clotures manuelles
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
print("  NETTOYAGE DONNEES ML")
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

# Identifier les colonnes de config/parametres
config_cols = [c for c in trades_df.columns if 'config' in c.lower() or 'tp' in c.lower() or 'sl' in c.lower()]
print(f"\nColonnes config/TP/SL: {config_cols[:10]}...")

# Verifier les raisons de fermeture
if 'close_reason' in trades_df.columns:
    print("\n--- Distribution close_reason ---")
    print(trades_df['close_reason'].value_counts().head(10))
    
    # Identifier les trades manuels
    manual_keywords = ['manual', 'manu', 'user', 'forced', 'cancelled', 'cancel']
    manual_mask = trades_df['close_reason'].str.lower().str.contains('|'.join(manual_keywords), na=False)
    manual_count = manual_mask.sum()
    print(f"\nTrades fermes manuellement: {manual_count} ({manual_count/len(trades_df)*100:.1f}%)")
else:
    manual_mask = pd.Series([False] * len(trades_df))
    print("\n⚠️ Colonne close_reason non trouvee")

# Verifier exit_type si disponible
if 'exit_type' in trades_df.columns:
    print("\n--- Distribution exit_type ---")
    print(trades_df['exit_type'].value_counts())

# =============================================================================
# ETAPE 2: Identifier les parametres majoritaires
# =============================================================================
print("\n=== ETAPE 2: PARAMETRES MAJORITAIRES ===")

# Charger ml_features pour voir les configs
ml_df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
print(f"Total samples ML: {len(ml_df)}")

# Colonnes config dans ml_features
config_cols_ml = [c for c in ml_df.columns if c.startswith('config_')]
print(f"\nColonnes config dans ml_features: {config_cols_ml}")

# Analyser les valeurs uniques de chaque config
config_stats = {}
for col in config_cols_ml:
    if ml_df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
        values = ml_df[col].value_counts()
        if len(values) > 1:
            print(f"\n{col}:")
            for val, count in values.items():
                pct = count / len(ml_df) * 100
                print(f"  {val}: {count} ({pct:.1f}%)")
            
            # Garder la valeur majoritaire
            majority_val = values.idxmax()
            majority_pct = values.max() / len(ml_df) * 100
            config_stats[col] = {
                'majority_value': majority_val,
                'majority_pct': majority_pct,
                'n_unique': len(values)
            }

# =============================================================================
# ETAPE 3: Definir les criteres de filtrage
# =============================================================================
print("\n=== ETAPE 3: CRITERES DE FILTRAGE ===")

# Criteres de config majoritaires (garder seulement si > 60% des donnees)
filters = {}
for col, stats in config_stats.items():
    if stats['majority_pct'] >= 60:
        filters[col] = stats['majority_value']
        print(f"✓ {col} = {stats['majority_value']} (utilisé par {stats['majority_pct']:.1f}% des trades)")
    else:
        print(f"✗ {col}: pas de valeur majoritaire claire ({stats['majority_pct']:.1f}%)")

# =============================================================================
# ETAPE 4: Filtrer les donnees
# =============================================================================
print("\n=== ETAPE 4: FILTRAGE DES DONNEES ===")

# Copie du dataframe
ml_clean = ml_df.copy()
initial_count = len(ml_clean)

# 1. Exclure les trades manuels (via join avec trades)
if 'scan_id' in ml_clean.columns and 'scan_log_id' in trades_df.columns:
    # Trouver les scan_ids des trades manuels
    manual_scan_ids = trades_df[manual_mask]['scan_log_id'].dropna().unique()
    
    before = len(ml_clean)
    ml_clean = ml_clean[~ml_clean['scan_id'].isin(manual_scan_ids)]
    excluded_manual = before - len(ml_clean)
    print(f"Exclus (trades manuels): {excluded_manual} ({excluded_manual/initial_count*100:.1f}%)")

# 2. Filtrer par config majoritaire
for col, value in filters.items():
    if col in ml_clean.columns:
        before = len(ml_clean)
        # Tolerance pour les floats
        if isinstance(value, float):
            ml_clean = ml_clean[abs(ml_clean[col] - value) < 0.001]
        else:
            ml_clean = ml_clean[ml_clean[col] == value]
        excluded = before - len(ml_clean)
        if excluded > 0:
            print(f"Exclus ({col} != {value}): {excluded} ({excluded/initial_count*100:.1f}%)")

final_count = len(ml_clean)
total_excluded = initial_count - final_count

print(f"\n--- RESUME ---")
print(f"Initial: {initial_count}")
print(f"Final: {final_count}")
print(f"Exclus total: {total_excluded} ({total_excluded/initial_count*100:.1f}%)")

# Distribution finale
if 'target_pnl' in ml_clean.columns:
    positifs = (ml_clean['target_pnl'] > 0).sum()
    negatifs = (ml_clean['target_pnl'] <= 0).sum()
    print(f"\nDistribution finale:")
    print(f"  Positifs: {positifs} ({positifs/final_count*100:.1f}%)")
    print(f"  Negatifs: {negatifs} ({negatifs/final_count*100:.1f}%)")

# =============================================================================
# ETAPE 5: Sauvegarder les donnees nettoyees
# =============================================================================
print("\n=== ETAPE 5: SAUVEGARDE ===")

if final_count >= 500:  # Minimum 500 samples
    # Option 1: Creer une nouvelle table
    table_name = 'ml_features_clean'
    
    # Supprimer l'ancienne table si existe
    with engine.connect() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        conn.commit()
    
    # Sauvegarder
    ml_clean.to_sql(table_name, engine, index=False, if_exists='replace')
    print(f"✅ Donnees nettoyees sauvegardees dans table: {table_name}")
    print(f"   {final_count} samples")
    
    # Option 2: Aussi sauvegarder en CSV
    csv_path = Path('data/ml_features_clean.csv')
    csv_path.parent.mkdir(exist_ok=True)
    ml_clean.to_csv(csv_path, index=False)
    print(f"✅ Aussi sauvegarde en CSV: {csv_path}")
    
else:
    print(f"⚠️ Seulement {final_count} samples apres filtrage (< 500 minimum)")
    print("   Les donnees ne sont pas sauvegardees")
    print("   Suggestion: relaxer les criteres de filtrage")

# =============================================================================
# ETAPE 6: Mise a jour du code de training
# =============================================================================
print("\n=== ETAPE 6: INSTRUCTIONS ===")
print("""
Pour utiliser les donnees nettoyees, modifier le code de training:

Option A: Utiliser la nouvelle table
  Dans api/routes/ml.py, changer:
    FROM ml_features WHERE target_pnl IS NOT NULL
  En:
    FROM ml_features_clean WHERE target_pnl IS NOT NULL

Option B: Ajouter un filtre dans la requete
  Ajouter les filtres de config dans la requete SQL

Puis re-entrainer le modele:
  python retrain_model.py
""")

engine.dispose()
print("\n" + "=" * 70)
print("  NETTOYAGE TERMINE")
print("=" * 70)
