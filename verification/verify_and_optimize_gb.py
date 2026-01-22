# -*- coding: utf-8 -*-
"""
Verification complete et optimisation GradientBoosting
- Verifier features temporelles
- Mesurer impact sur metriques
- Trouver seuil de confiance optimal
- Recommandations d'amelioration
"""

import sys
import warnings
warnings.filterwarnings('ignore')
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import json

print("=" * 70)
print("  VERIFICATION & OPTIMISATION GRADIENTBOOSTING")
print("=" * 70)

# =============================================================================
# 1. CONNEXION DB
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
# 2. CHARGER DONNEES NETTOYEES
# =============================================================================
print("\n" + "=" * 70)
print("  1. CHARGEMENT DES DONNEES")
print("=" * 70)

try:
    df = pd.read_sql("SELECT * FROM ml_features_clean WHERE target_pnl IS NOT NULL", engine)
    print(f"✅ Donnees nettoyees: {len(df)} samples")
except:
    df = pd.read_sql("SELECT * FROM ml_features WHERE target_pnl IS NOT NULL", engine)
    print(f"⚠️ Utilisation ml_features: {len(df)} samples")

engine.dispose()

# =============================================================================
# 3. FEATURE ENGINEERING AVEC TEMPORELLES
# =============================================================================
print("\n" + "=" * 70)
print("  2. FEATURE ENGINEERING (avec temporelles)")
print("=" * 70)

df['target_class'] = (df['target_pnl'] > 0).astype(int)

# Features temporelles
temporal_added = []
if 'timestamp' in df.columns:
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour_utc'] = df['timestamp'].dt.hour
    df['session_asia'] = ((df['hour_utc'] >= 0) & (df['hour_utc'] < 8)).astype(int)
    df['session_europe'] = ((df['hour_utc'] >= 8) & (df['hour_utc'] < 16)).astype(int)
    df['session_usa'] = ((df['hour_utc'] >= 13) & (df['hour_utc'] < 21)).astype(int)
    df['high_activity'] = ((df['hour_utc'] >= 13) & (df['hour_utc'] < 17)).astype(int)
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['week_edge'] = ((df['day_of_week'] == 0) | (df['day_of_week'] == 4)).astype(int)
    df['favorable_hour'] = df['hour_utc'].isin([2, 12, 16]).astype(int)
    df['unfavorable_hour'] = df['hour_utc'].isin([3, 4, 5, 22, 23]).astype(int)
    temporal_added = ['hour_utc', 'session_asia', 'session_europe', 'session_usa', 
                      'high_activity', 'day_of_week', 'is_weekend', 'week_edge',
                      'favorable_hour', 'unfavorable_hour']
    print(f"✅ Features temporelles ajoutees: {len(temporal_added)}")
else:
    print("❌ Colonne timestamp absente!")

# Selectionner features
exclude = ['id', 'timestamp', 'symbol', 'target_pnl', 'target_class', 'scan_id', 
           'is_opportunity', 'target_win', 'reject_reason_category', 'opportunity_direction']
feature_cols = [c for c in df.columns if c not in exclude 
                and df[c].dtype in ['float64', 'int64', 'float32', 'int32']
                and df[c].nunique() > 1 
                and not c.startswith('config_')]

print(f"✅ Features disponibles: {len(feature_cols)}")
print(f"   - Dont temporelles: {len([f for f in temporal_added if f in feature_cols])}")

X = df[feature_cols].fillna(0).values
y = df['target_class'].values

print(f"\n📊 Distribution:")
print(f"   WIN:  {(y==1).sum()} ({(y==1).sum()/len(y)*100:.1f}%)")
print(f"   LOSS: {(y==0).sum()} ({(y==0).sum()/len(y)*100:.1f}%)")

# =============================================================================
# 4. TEST AVEC/SANS FEATURES TEMPORELLES
# =============================================================================
print("\n" + "=" * 70)
print("  3. IMPACT DES FEATURES TEMPORELLES")
print("=" * 70)

def train_and_evaluate(X, y, feature_names, n_features=25):
    """Entrainer et evaluer le modele"""
    # Feature selection
    k = min(n_features, X.shape[1])
    selector = SelectKBest(f_classif, k=k)
    X_sel = selector.fit_transform(X, y)
    selected_mask = selector.get_support()
    selected_features = [feature_names[i] for i in range(len(feature_names)) if selected_mask[i]]
    
    # Cross-validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    train_accs, test_accs, f1s, precs, recalls = [], [], [], [], []
    all_probas = np.zeros(len(y))
    all_preds = np.zeros(len(y))
    
    for train_idx, test_idx in cv.split(X_sel, y):
        X_train, X_test = X_sel[train_idx], X_sel[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        scaler = RobustScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        model = HistGradientBoostingClassifier(
            max_iter=200,
            max_depth=3,
            learning_rate=0.03,
            min_samples_leaf=15,
            l2_regularization=1.0,
            random_state=42
        )
        model.fit(X_train_s, y_train)
        
        y_train_pred = model.predict(X_train_s)
        y_test_pred = model.predict(X_test_s)
        y_test_proba = model.predict_proba(X_test_s)[:, 1]
        
        train_accs.append(accuracy_score(y_train, y_train_pred))
        test_accs.append(accuracy_score(y_test, y_test_pred))
        f1s.append(f1_score(y_test, y_test_pred, zero_division=0))
        precs.append(precision_score(y_test, y_test_pred, zero_division=0))
        recalls.append(recall_score(y_test, y_test_pred, zero_division=0))
        
        all_probas[test_idx] = y_test_proba
        all_preds[test_idx] = y_test_pred
    
    return {
        'accuracy': np.mean(test_accs),
        'f1': np.mean(f1s),
        'precision': np.mean(precs),
        'recall': np.mean(recalls),
        'gap': np.mean(train_accs) - np.mean(test_accs),
        'selected_features': selected_features,
        'probas': all_probas,
        'preds': all_preds
    }

# Test SANS temporelles
feature_cols_no_temp = [c for c in feature_cols if c not in temporal_added]
X_no_temp = df[feature_cols_no_temp].fillna(0).values
results_no_temp = train_and_evaluate(X_no_temp, y, feature_cols_no_temp)

print(f"\n📊 SANS features temporelles ({len(feature_cols_no_temp)} features):")
print(f"   Accuracy:  {results_no_temp['accuracy']*100:.1f}%")
print(f"   F1 Score:  {results_no_temp['f1']:.3f}")
print(f"   Precision: {results_no_temp['precision']:.3f}")
print(f"   Gap:       {results_no_temp['gap']*100:.1f}%")

# Test AVEC temporelles
results_with_temp = train_and_evaluate(X, y, feature_cols)

print(f"\n📊 AVEC features temporelles ({len(feature_cols)} features):")
print(f"   Accuracy:  {results_with_temp['accuracy']*100:.1f}%")
print(f"   F1 Score:  {results_with_temp['f1']:.3f}")
print(f"   Precision: {results_with_temp['precision']:.3f}")
print(f"   Gap:       {results_with_temp['gap']*100:.1f}%")

# Impact
print(f"\n📈 IMPACT des features temporelles:")
acc_diff = (results_with_temp['accuracy'] - results_no_temp['accuracy']) * 100
f1_diff = results_with_temp['f1'] - results_no_temp['f1']
prec_diff = results_with_temp['precision'] - results_no_temp['precision']
print(f"   Accuracy:  {'+' if acc_diff >= 0 else ''}{acc_diff:.1f}%")
print(f"   F1 Score:  {'+' if f1_diff >= 0 else ''}{f1_diff:.3f}")
print(f"   Precision: {'+' if prec_diff >= 0 else ''}{prec_diff:.3f}")

# Features temporelles selectionnees
temp_selected = [f for f in results_with_temp['selected_features'] if f in temporal_added]
print(f"\n   Features temporelles selectionnees: {temp_selected}")

# =============================================================================
# 5. TROUVER SEUIL DE CONFIANCE OPTIMAL
# =============================================================================
print("\n" + "=" * 70)
print("  4. SEUIL DE CONFIANCE OPTIMAL")
print("=" * 70)

probas = results_with_temp['probas']
y_true = y

thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
results_thresholds = []

print(f"\n{'Seuil':<10} {'Acc':<10} {'Prec':<10} {'Recall':<10} {'F1':<10} {'Trades':<10} {'%Filtres':<10}")
print("-" * 70)

for thresh in thresholds:
    y_pred = (probas >= thresh).astype(int)
    
    # Trades filtres = ceux ou proba < thresh
    n_filtered = (probas < thresh).sum()
    pct_filtered = n_filtered / len(probas) * 100
    
    # Accuracy seulement sur trades acceptes (proba >= thresh)
    accepted_mask = probas >= thresh
    if accepted_mask.sum() > 0:
        acc_on_accepted = accuracy_score(y_true[accepted_mask], y_pred[accepted_mask])
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
    else:
        acc_on_accepted = 0
        prec = rec = f1 = 0
    
    # Win rate reel sur trades acceptes
    if accepted_mask.sum() > 0:
        actual_wins = y_true[accepted_mask].sum()
        win_rate = actual_wins / accepted_mask.sum() * 100
    else:
        win_rate = 0
    
    results_thresholds.append({
        'threshold': thresh,
        'accuracy': acc_on_accepted,
        'precision': prec,
        'recall': rec,
        'f1': f1,
        'n_trades': accepted_mask.sum(),
        'pct_filtered': pct_filtered,
        'win_rate': win_rate
    })
    
    print(f"{thresh:<10.2f} {acc_on_accepted*100:<10.1f} {prec:<10.3f} {rec:<10.3f} {f1:<10.3f} {accepted_mask.sum():<10} {pct_filtered:<10.1f}")

# Trouver seuil optimal (meilleur compromis precision/trades)
best_thresh = None
best_score = 0
for r in results_thresholds:
    if r['n_trades'] >= 20:  # Au moins 20 trades acceptes
        # Score = win_rate * 0.7 + (trades_acceptes%) * 0.3
        trades_pct = r['n_trades'] / len(y)
        score = r['win_rate'] * 0.7 + trades_pct * 100 * 0.3
        if score > best_score:
            best_score = score
            best_thresh = r

if best_thresh is None:
    best_thresh = results_thresholds[0]  # Fallback to 0.50

print(f"\n🎯 SEUIL RECOMMANDE: {best_thresh['threshold']:.2f}")
print(f"   Win rate attendu: {best_thresh['win_rate']:.1f}%")
print(f"   Trades acceptes: {best_thresh['n_trades']} ({100-best_thresh['pct_filtered']:.0f}%)")
print(f"   Precision: {best_thresh['precision']:.3f}")

# =============================================================================
# 6. RECOMMANDATIONS D'AMELIORATION
# =============================================================================
print("\n" + "=" * 70)
print("  5. RECOMMANDATIONS POUR AMELIORER ACCURACY")
print("=" * 70)

current_acc = results_with_temp['accuracy']
current_gap = results_with_temp['gap']

recommendations = []

# 1. Plus de donnees
if len(df) < 1000:
    recommendations.append({
        'priority': 'HAUTE',
        'action': 'Collecter plus de donnees',
        'details': f'Actuellement {len(df)} samples. Objectif: 1000+ pour meilleure generalisation',
        'impact': '+3-5% accuracy potentiel'
    })

# 2. Reduire overfitting si gap eleve
if current_gap > 0.15:
    recommendations.append({
        'priority': 'HAUTE',
        'action': 'Reduire overfitting',
        'details': f'Gap actuel: {current_gap*100:.1f}%. Augmenter regularisation ou reduire complexite',
        'impact': '+2-4% accuracy test'
    })

# 3. Feature engineering supplementaire
recommendations.append({
    'priority': 'MOYENNE',
    'action': 'Ajouter features de contexte marche',
    'details': 'BTC dominance, volatilite globale, correlation inter-assets',
    'impact': '+1-3% accuracy potentiel'
})

# 4. Equilibrage classes
win_rate = (y == 1).sum() / len(y)
if win_rate < 0.45 or win_rate > 0.55:
    recommendations.append({
        'priority': 'MOYENNE',
        'action': 'Equilibrer les classes',
        'details': f'Win rate actuel: {win_rate*100:.1f}%. Utiliser SMOTE ou class_weight',
        'impact': '+1-2% F1 score'
    })

# 5. Hyperparameter tuning
recommendations.append({
    'priority': 'MOYENNE',
    'action': 'Optuna hyperparameter tuning',
    'details': 'Optimiser n_estimators, max_depth, learning_rate, min_samples_leaf',
    'impact': '+1-3% accuracy potentiel'
})

# 6. Ensemble
recommendations.append({
    'priority': 'BASSE',
    'action': 'Ensemble de modeles',
    'details': 'Combiner GradientBoosting + RandomForest + LogisticRegression',
    'impact': '+1-2% accuracy avec meilleure stabilite'
})

print()
for i, rec in enumerate(recommendations, 1):
    print(f"{i}. [{rec['priority']}] {rec['action']}")
    print(f"   📋 {rec['details']}")
    print(f"   📈 Impact estime: {rec['impact']}")
    print()

# =============================================================================
# 7. RESUME FINAL
# =============================================================================
print("=" * 70)
print("  RESUME FINAL")
print("=" * 70)

print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│  METRIQUES ACTUELLES (avec features temporelles)                    │
├─────────────────────────────────────────────────────────────────────┤
│  Accuracy:     {results_with_temp['accuracy']*100:>6.1f}%  {'✅' if results_with_temp['accuracy'] >= 0.55 else '⚠️'}                                      │
│  F1 Score:     {results_with_temp['f1']:>6.3f}   {'✅' if results_with_temp['f1'] >= 0.50 else '⚠️'}                                      │
│  Precision:    {results_with_temp['precision']:>6.3f}   {'✅' if results_with_temp['precision'] >= 0.55 else '⚠️'}                                      │
│  Gap:          {results_with_temp['gap']*100:>6.1f}%  {'✅' if results_with_temp['gap'] <= 0.15 else '⚠️'}                                      │
├─────────────────────────────────────────────────────────────────────┤
│  SEUIL RECOMMANDE: {best_thresh['threshold']:.2f}                                          │
│  Win rate attendu: {best_thresh['win_rate']:.1f}%                                         │
│  Trades filtres:   {best_thresh['pct_filtered']:.0f}%                                           │
└─────────────────────────────────────────────────────────────────────┘
""")

# Sauvegarder recommandation
config_path = 'config_overrides.json'
with open(config_path) as f:
    config = json.load(f)

current_conf = config.get('gb_min_confidence', 0.5)
print(f"📝 Seuil actuel dans config: {current_conf}")
print(f"📝 Seuil recommande: {best_thresh['threshold']}")

if abs(current_conf - best_thresh['threshold']) > 0.05:
    print(f"\n⚠️  Conseil: Modifier gb_min_confidence de {current_conf} vers {best_thresh['threshold']}")
else:
    print(f"\n✅ Seuil actuel proche de l'optimal")

print("\n" + "=" * 70)
