# -*- coding: utf-8 -*-
"""
Test d'intégration du Filtre Négatif ML

Vérifie que:
1. Le modèle se charge correctement
2. Les prédictions fonctionnent
3. La config est bien lue
4. Le filtre rejette les trades à haut risque
"""

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("=" * 70)
print("  TEST INTEGRATION FILTRE NEGATIF ML")
print("=" * 70)

# =============================================================================
# TEST 1: Configuration
# =============================================================================
print("\n" + "-" * 50)
print("TEST 1: Configuration ML")
print("-" * 50)

try:
    from config import ML_CONFIG, TRADING_CONFIG
    
    print(f"   ml_filter_enabled: {ML_CONFIG.get('enabled', False)}")
    print(f"   ml_filter_mode: {ML_CONFIG.get('mode', 'STRICT')}")
    print(f"   ml_loss_threshold: {ML_CONFIG.get('loss_threshold', 0.45)}")
    
    # Vérifier que le mode NEGATIVE est actif
    if ML_CONFIG.get('mode') == 'NEGATIVE':
        print(f"\n   ✅ Mode NEGATIVE actif")
    else:
        print(f"\n   ⚠️  Mode {ML_CONFIG.get('mode')} (pas NEGATIVE)")
    
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# =============================================================================
# TEST 2: Chargement du modèle
# =============================================================================
print("\n" + "-" * 50)
print("TEST 2: Chargement du modele")
print("-" * 50)

try:
    from optimization.predictor_negative import get_negative_predictor
    
    predictor = get_negative_predictor()
    info = predictor.get_info()
    
    print(f"   is_loaded: {info['is_loaded']}")
    print(f"   n_features: {info['n_features']}")
    print(f"   threshold: {info['threshold']}")
    
    if info['is_loaded']:
        print(f"\n   ✅ Modele charge avec succes")
    else:
        print(f"\n   ❌ Modele non charge")
        
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# TEST 3: Prédiction sur données réelles
# =============================================================================
print("\n" + "-" * 50)
print("TEST 3: Prediction sur donnees reelles")
print("-" * 50)

try:
    from optimization.data.feature_loader import load_features_from_postgres
    
    # Charger quelques trades récents
    print("   Chargement des trades recents...")
    df = load_features_from_postgres(timeframe_days=30, min_trades=1)
    
    if len(df) > 0:
        print(f"   {len(df)} trades charges")
        
        # Tester sur 5 trades
        n_tests = min(5, len(df))
        n_rejected = 0
        
        print(f"\n   Test sur {n_tests} trades:")
        
        for i in range(n_tests):
            row = df.iloc[i]
            
            # Construire le dict de features
            features = {}
            for col in df.columns:
                if col not in ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                               'is_opportunity', 'reject_reason_category']:
                    if isinstance(row[col], (int, float)) and not pd.isna(row[col]):
                        features[col] = float(row[col])
            
            # Prédiction
            result = predictor.predict(features)
            
            p_loss = result['p_loss']
            should_reject = result['should_reject']
            actual_win = row.get('target_win', None)
            
            status = "REJETE" if should_reject else "ACCEPTE"
            actual = "WIN" if actual_win == 1 else "LOSS" if actual_win == 0 else "?"
            
            if should_reject:
                n_rejected += 1
            
            print(f"      Trade {i+1}: P(loss)={p_loss*100:.1f}% -> {status} (reel: {actual})")
        
        print(f"\n   Resume: {n_rejected}/{n_tests} trades rejetes ({n_rejected/n_tests*100:.0f}%)")
        print(f"   ✅ Predictions fonctionnent")
        
    else:
        print(f"   ⚠️  Pas de trades disponibles")
        
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# TEST 4: Simulation de filtre sur données test
# =============================================================================
print("\n" + "-" * 50)
print("TEST 4: Simulation filtre sur donnees historiques")
print("-" * 50)

try:
    import pandas as pd
    
    # Charger plus de données pour avoir des stats
    df = load_features_from_postgres(timeframe_days=90, min_trades=1)
    
    if len(df) >= 50:
        print(f"   {len(df)} trades charges")
        
        # Prédire sur tous les trades
        predictions = []
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            features = {}
            for col in df.columns:
                if col not in ['scan_id', 'timestamp', 'symbol', 'target_win', 'target_pnl', 
                               'is_opportunity', 'reject_reason_category']:
                    if isinstance(row[col], (int, float)) and not pd.isna(row[col]):
                        features[col] = float(row[col])
            
            result = predictor.predict(features)
            predictions.append({
                'p_loss': result['p_loss'],
                'should_reject': result['should_reject'],
                'target_win': row.get('target_win', None)
            })
        
        pred_df = pd.DataFrame(predictions)
        
        # Stats globales
        total = len(pred_df)
        rejected = pred_df['should_reject'].sum()
        kept = total - rejected
        
        # Win rate sans filtre
        valid = pred_df[pred_df['target_win'].notna()]
        baseline_wr = valid['target_win'].mean()
        
        # Win rate avec filtre
        kept_df = valid[~valid['should_reject']]
        if len(kept_df) > 0:
            filtered_wr = kept_df['target_win'].mean()
        else:
            filtered_wr = 0
        
        print(f"\n   Resultats:")
        print(f"      Total trades: {total}")
        print(f"      Trades rejetes: {rejected} ({rejected/total*100:.1f}%)")
        print(f"      Trades conserves: {kept} ({kept/total*100:.1f}%)")
        print(f"\n      Win rate SANS filtre: {baseline_wr*100:.1f}%")
        print(f"      Win rate AVEC filtre: {filtered_wr*100:.1f}%")
        print(f"      Amelioration: {(filtered_wr - baseline_wr)*100:+.1f}%")
        
        if filtered_wr > baseline_wr:
            print(f"\n   ✅ Le filtre AMELIORE le win rate!")
        else:
            print(f"\n   ⚠️  Le filtre n'ameliore pas (peut varier selon les donnees)")
            
    else:
        print(f"   ⚠️  Pas assez de trades ({len(df)} < 50)")
        
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# =============================================================================
# RÉSUMÉ
# =============================================================================
print("\n" + "=" * 70)
print("  RESUME")
print("=" * 70)

print(f"""
   Configuration:
   - Mode: NEGATIVE (filtre negatif)
   - Seuil: P(loss) >= 45% -> REJET
   
   Fonctionnement:
   - Charge le modele ml_negative_filter.pkl
   - Predit P(loss) pour chaque trade
   - Rejette si P(loss) >= seuil
   - Laisse passer les autres
   
   Fichiers modifies:
   - config.py: Ajout mode NEGATIVE et loss_threshold
   - config_overrides.json: Active le filtre en mode NEGATIVE
   - scanner_loop.py: Ajout logique mode NEGATIVE
   - predictor_negative.py: Nouveau predicteur
   
   Pour activer/desactiver:
   - Dans l'UI: Variables > ML > ml_filter_enabled
   - ml_filter_mode: STRICT / SOFT / NEGATIVE
   - ml_loss_threshold: 0.30 - 0.80 (defaut 0.45)
""")

print("=" * 70)
print("  FIN DES TESTS")
print("=" * 70)
