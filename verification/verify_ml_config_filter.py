# -*- coding: utf-8 -*-
"""
Verification que le filtrage ML par config actuelle fonctionne correctement
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import requests

print("=" * 70)
print("  VERIFICATION FILTRAGE ML PAR CONFIG ACTUELLE")
print("=" * 70)

# =============================================================================
# 1. LIRE CONFIG ACTUELLE
# =============================================================================
print("\n" + "-" * 50)
print("1. CONFIG ACTUELLE (depuis config_overrides.json)")
print("-" * 50)

with open('config_overrides.json') as f:
    config = json.load(f)

current_config = {
    'min_score': config.get('min_score_required', 6.5),
    'snr_threshold': config.get('snr_threshold', 0.15),
    'volume_mult': config.get('volume_multiplier', 0.95)
}

print(f"   min_score_required: {current_config['min_score']}")
print(f"   snr_threshold:      {current_config['snr_threshold']}")
print(f"   volume_multiplier:  {current_config['volume_mult']}")

# =============================================================================
# 2. CONNEXION DB
# =============================================================================
env_vars = {}
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            env_vars[k.strip()] = v.strip()

password = quote_plus(env_vars.get('POSTGRES_PASSWORD', ''))
conn_str = f"postgresql://{env_vars.get('POSTGRES_USER')}:{password}@{env_vars.get('POSTGRES_HOST')}:{env_vars.get('POSTGRES_PORT')}/{env_vars.get('POSTGRES_DB')}"
engine = create_engine(conn_str)

# =============================================================================
# 3. COMPTER TRADES DIRECTEMENT EN SQL
# =============================================================================
print("\n" + "-" * 50)
print("2. VERIFICATION DIRECTE EN BASE DE DONNEES")
print("-" * 50)

# Total trades
total = pd.read_sql("SELECT COUNT(*) as cnt FROM trades", engine).iloc[0]['cnt']
print(f"   Total trades: {total}")

# Non-manuels
non_manual = pd.read_sql("""
    SELECT COUNT(*) as cnt FROM trades 
    WHERE exit_reason IS NULL OR exit_reason != 'MANUAL'
""", engine).iloc[0]['cnt']
print(f"   Non-manuels: {non_manual}")

# Avec config actuelle
conditions = ["(exit_reason IS NULL OR exit_reason != 'MANUAL')"]
conditions.append(f"ABS(COALESCE(config_min_score_required, 0) - {current_config['min_score']}) < 0.01")
conditions.append(f"ABS(COALESCE(config_snr_threshold, 0) - {current_config['snr_threshold']}) < 0.01")
conditions.append(f"ABS(COALESCE(config_volume_multiplier, 0) - {current_config['volume_mult']}) < 0.01")

query = f"SELECT COUNT(*) as cnt FROM trades WHERE {' AND '.join(conditions)}"
with_current_config = pd.read_sql(query, engine).iloc[0]['cnt']
print(f"   Avec config actuelle: {with_current_config}")

# =============================================================================
# 4. TESTER AVEC DIFFERENTES CONFIGS
# =============================================================================
print("\n" + "-" * 50)
print("3. TEST AVEC DIFFERENTES CONFIGS")
print("-" * 50)

test_configs = [
    {'min_score': 6.5, 'snr': 0.15, 'vol': 0.95},
    {'min_score': 6.0, 'snr': 0.15, 'vol': 0.95},
    {'min_score': 7.0, 'snr': 0.15, 'vol': 0.95},
    {'min_score': 6.5, 'snr': 0.20, 'vol': 0.95},
    {'min_score': 6.5, 'snr': 0.15, 'vol': 1.00},
]

print(f"\n{'Config':<35} {'Trades':<10}")
print("-" * 50)

for cfg in test_configs:
    conditions = ["(exit_reason IS NULL OR exit_reason != 'MANUAL')"]
    conditions.append(f"ABS(COALESCE(config_min_score_required, 0) - {cfg['min_score']}) < 0.01")
    conditions.append(f"ABS(COALESCE(config_snr_threshold, 0) - {cfg['snr']}) < 0.01")
    conditions.append(f"ABS(COALESCE(config_volume_multiplier, 0) - {cfg['vol']}) < 0.01")
    
    query = f"SELECT COUNT(*) as cnt FROM trades WHERE {' AND '.join(conditions)}"
    count = pd.read_sql(query, engine).iloc[0]['cnt']
    
    marker = " <-- ACTUELLE" if (
        abs(cfg['min_score'] - current_config['min_score']) < 0.01 and
        abs(cfg['snr'] - current_config['snr_threshold']) < 0.01 and
        abs(cfg['vol'] - current_config['volume_mult']) < 0.01
    ) else ""
    
    print(f"min={cfg['min_score']}, snr={cfg['snr']}, vol={cfg['vol']:<5} {count:<10}{marker}")

# =============================================================================
# 5. TESTER L'ENDPOINT API
# =============================================================================
print("\n" + "-" * 50)
print("4. TEST ENDPOINT API /api/ml/dashboard/ml_trades_count")
print("-" * 50)

try:
    resp = requests.get("http://localhost:5000/api/ml/dashboard/ml_trades_count", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Status: OK")
        print(f"   Total trades: {data.get('total_trades')}")
        print(f"   Manual exclus: {data.get('manual_excluded')}")
        print(f"   Config differentes exclus: {data.get('different_config_excluded')}")
        print(f"   Trades ML utilisables: {data.get('config_filtered_trades')}")
        
        if 'current_config' in data:
            cc = data['current_config']
            print(f"\n   Config actuelle (depuis API):")
            print(f"      min_score: {cc.get('min_score')}")
            print(f"      snr_threshold: {cc.get('snr_threshold')}")
            print(f"      volume_mult: {cc.get('volume_mult')}")
            
            # Verifier coherence
            if (abs(cc.get('min_score', 0) - current_config['min_score']) < 0.01 and
                abs(cc.get('snr_threshold', 0) - current_config['snr_threshold']) < 0.01 and
                abs(cc.get('volume_mult', 0) - current_config['volume_mult']) < 0.01):
                print(f"\n   ✅ COHERENT avec config_overrides.json")
            else:
                print(f"\n   ❌ INCOHERENT! Backend utilise une config differente")
                print(f"      config_overrides.json: {current_config}")
                print(f"      API retourne: {cc}")
        else:
            print(f"\n   ⚠️  'current_config' absent de la reponse - backend pas mis a jour?")
            
        if data.get('config_filtered_trades') == with_current_config:
            print(f"\n   ✅ Nombre de trades COHERENT avec query directe")
        else:
            print(f"\n   ❌ INCOHERENT!")
            print(f"      API: {data.get('config_filtered_trades')}")
            print(f"      Query directe: {with_current_config}")
    else:
        print(f"   ❌ Erreur HTTP {resp.status_code}")
        print(f"   {resp.text[:200]}")
except requests.exceptions.ConnectionError:
    print(f"   ⚠️  Backend non accessible (redemarrage necessaire)")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# =============================================================================
# 6. VERIFIER QUE LE MODELE UTILISE LES BONNES DONNEES
# =============================================================================
print("\n" + "-" * 50)
print("5. VERIFICATION MODELE ML")
print("-" * 50)

try:
    with open('optimization/saved_models/best_classifier_metadata.json') as f:
        meta = json.load(f)
    
    model_samples = meta.get('n_samples', 0)
    print(f"   Samples utilises pour entrainer: {model_samples}")
    
    # Comparer avec ml_features_clean
    try:
        ml_clean = pd.read_sql("SELECT COUNT(*) as cnt FROM ml_features_clean", engine).iloc[0]['cnt']
        print(f"   Samples dans ml_features_clean: {ml_clean}")
        
        if model_samples == ml_clean:
            print(f"   ✅ COHERENT - Modele entraine sur donnees nettoyees")
        else:
            print(f"   ⚠️  Difference: modele peut necessiter re-entrainement")
    except:
        print(f"   ⚠️  Table ml_features_clean non trouvee")
        
except Exception as e:
    print(f"   ❌ Erreur lecture metadata: {e}")

engine.dispose()

# =============================================================================
# RESUME
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"""
  Config actuelle: min_score={current_config['min_score']}, snr={current_config['snr_threshold']}, vol={current_config['volume_mult']}
  
  Trades correspondants: {with_current_config} / {total} total
  
  Actions recommandees:
  1. Redemarrer le backend si pas fait
  2. Cliquer "Rafraichir" dans le frontend
  3. Verifier que les nombres changent quand on modifie la config
""")

print("=" * 70)
