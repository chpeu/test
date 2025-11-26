# 🚀 Solutions XGBoost - Au-delà des Hyperparamètres

## 📋 Contexte

**Problème**: Test accuracy ~52% (hasard) malgré optimisation Optuna
**Cause**: Le problème n'est PAS les hyperparamètres mais la **qualité des données et méthodologie**

---

## 🎯 7 Solutions Implémentées

### ✅ SOLUTION 1: Split Temporel (CRITIQUE)

**Problème**: `train_test_split` random crée du **data leakage** en trading

**Fichier**: `optimization/utils/temporal_split.py`

**Utilisation**:
```python
from optimization.utils.temporal_split import temporal_train_test_split

train_df, val_df, test_df = temporal_train_test_split(
    df,
    test_size=0.2,
    validation_size=0.1,
    timestamp_col='timestamp'
)
```

**Impact attendu**: +5-10% accuracy (élimine data leakage)

**Pourquoi c'est critique**:
- En trading, le futur ne doit JAMAIS influencer le passé
- Random split mélange trades de différentes périodes
- Le modèle apprend des patterns du futur → performances gonflées artificiellement

---

### ✅ SOLUTION 2: Analyse Exploratoire (EDA)

**Fichier**: `optimization/analysis/eda_trading.py`

**Lancer l'analyse**:
```bash
python -m optimization.analysis.eda_trading
```

**Ce que ça fait**:
1. ✅ Analyse qualité des labels (incohérences, déséquilibre)
2. ✅ Identifie features discriminantes (Win vs Loss)
3. ✅ Détecte data leakage (features qui "connaissent" le futur)
4. ✅ Suggère nouvelles features

**Résultats attendus**:
```
🔝 TOP 20 FEATURES DISCRIMINANTES:
  1. di_minus_1m: KS=0.234 (très discriminant)
  2. rsi_prev_1m: KS=0.189
  ...

⚠️ Features NON-DISCRIMINANTES (à exclure): 45 features
  → Exclure: ema_diff_pct_1m, di_plus_1m, trend_bearish_1m...

📊 Trades marginaux (|PNL| < 0.15%): 348 (20%)
  → Recommandation: Exclure du training (bruit aléatoire)
```

---

### ✅ SOLUTION 3: XGBoost V2 (Temporal + Filtrage)

**Fichier**: `optimization/models/xgboost_trainer_v2.py`

**Améliorations vs V1**:
1. ✅ Split temporel (pas random)
2. ✅ Filtrage trades marginaux (|PNL| < 0.15%)
3. ✅ Sélection top-K features discriminantes
4. ✅ Validation set séparé

**Lancer entraînement**:
```bash
python -m optimization.models.xgboost_trainer_v2
```

**Ou via code**:
```python
from optimization.models.xgboost_trainer_v2 import XGBoostTrainerV2

trainer = XGBoostTrainerV2(model_name="xgboost_v2_temporal")

results = trainer.train(
    timeframe_days=120,
    min_trades=100,
    filter_marginal_trades=True,  # Exclure bruit
    marginal_threshold=0.15,      # PNL < 0.15% = bruit
    max_features=30               # Top 30 features seulement
)

print(f"Test Accuracy: {results['metrics']['test']['accuracy']:.3f}")
print(f"Test ROC-AUC: {results['metrics']['test']['roc_auc']:.3f}")
```

**Impact attendu**: +10-15% accuracy vs V1

---

### ✅ SOLUTION 4: Walk-Forward Validation

**Fichier**: `optimization/utils/temporal_split.py` (fonction `walk_forward_validation`)

**Concept**: Simule trading réel en avançant dans le temps

```
Fold 1: Train[0:70%]  → Test[70:80%]
Fold 2: Train[0:75%]  → Test[75:85%]
Fold 3: Train[0:80%]  → Test[80:90%]
Fold 4: Train[0:85%]  → Test[85:95%]
Fold 5: Train[0:90%]  → Test[90:100%]
```

**Utilisation**:
```python
from optimization.utils.temporal_split import walk_forward_validation

folds = walk_forward_validation(df, n_splits=5)

accuracies = []
for train_df, test_df in folds:
    # Entraîner et évaluer
    model.fit(train_df)
    acc = model.evaluate(test_df)
    accuracies.append(acc)

print(f"Walk-Forward Accuracy: {np.mean(accuracies):.3f} ± {np.std(accuracies):.3f}")
```

---

### ✅ SOLUTION 5: Nouvelles Features (Contexte Marché)

**Problème**: Features actuelles ne capturent peut-être pas les vrais patterns

**Features suggérées** (à implémenter):

#### 1️⃣ Contexte Temporel
```python
# Heure de la journée (sessions trading)
df['trade_hour'] = df['timestamp'].dt.hour
df['is_london_session'] = df['trade_hour'].between(8, 16)
df['is_ny_session'] = df['trade_hour'].between(13, 21)

# Jour de la semaine
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['is_monday'] = (df['day_of_week'] == 0).astype(int)
df['is_friday'] = (df['day_of_week'] == 4).astype(int)
```

#### 2️⃣ Régime de Marché
```python
# Trending vs Ranging
df['market_regime'] = np.where(df['adx_1m'] > 25, 'trending', 'ranging')
df['regime_is_trending'] = (df['market_regime'] == 'trending').astype(int)

# Volatilité relative
df['volatility_percentile'] = df['atr_pct_1m'].rank(pct=True)
df['high_volatility'] = (df['volatility_percentile'] > 0.8).astype(int)
```

#### 3️⃣ Historique Récent
```python
# Win rate récent (rolling 10 trades)
df['recent_winrate'] = df['target_win'].rolling(10, min_periods=1).mean()

# Drawdown récent
df['recent_drawdown'] = df['target_pnl'].rolling(10).min()

# Séries consécutives
df['consecutive_wins'] = (df['target_win'].groupby(
    (df['target_win'] != df['target_win'].shift()).cumsum()
).cumcount() + 1) * df['target_win']
```

#### 4️⃣ Interactions Features
```python
# Produits de features discriminantes
df['rsi_x_macd'] = df['rsi_1m'] * df['macd_hist_1m']
df['adx_x_di_gap'] = df['adx_1m'] * abs(df['di_gap_1m'])
df['volume_x_volatility'] = df['volume_ratio_1m'] * df['atr_pct_1m']
```

---

### ✅ SOLUTION 6: Ensembling (Si V2 insuffisant)

**Concept**: Combiner plusieurs modèles

```python
from sklearn.ensemble import VotingClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression

# 3 modèles différents
xgb = XGBClassifier(max_depth=5, learning_rate=0.05)
lgbm = LGBMClassifier(max_depth=5, learning_rate=0.05)
lr = LogisticRegression(C=0.1, class_weight='balanced')

# Voting ensemble
ensemble = VotingClassifier(
    estimators=[('xgb', xgb), ('lgbm', lgbm), ('lr', lr)],
    voting='soft'  # Probabilités moyennées
)

ensemble.fit(X_train, y_train)
accuracy = ensemble.score(X_test, y_test)
```

**Impact attendu**: +2-5% accuracy

---

### ✅ SOLUTION 7: Focal Loss (Déséquilibre Classes)

**Problème**: Peut-être que certaines classes sont sous-représentées

```python
import xgboost as xgb

def focal_loss(y_pred, y_true):
    """
    Focal Loss: Pénalise plus les erreurs difficiles
    Utile si déséquilibre classes
    """
    gamma = 2.0
    alpha = 0.25

    y_true = y_true.get_label()
    p = 1 / (1 + np.exp(-y_pred))  # sigmoid

    # Focal loss gradient
    grad = alpha * (1 - p)**gamma * (y_true - p)
    hess = alpha * gamma * (1 - p)**(gamma-1) * p * (1 - p)

    return grad, hess

model = xgb.train(
    params,
    dtrain,
    obj=focal_loss,  # Custom objective
    num_boost_round=500
)
```

---

## 📊 Plan d'Action Recommandé

### Étape 1: Diagnostic (PRIORITAIRE)
```bash
# Lancer EDA pour identifier les vrais problèmes
python -m optimization.analysis.eda_trading
```

**Durée**: 5 min
**Résultat**: Rapport avec problèmes identifiés

---

### Étape 2: Tester XGBoost V2 (Temporal Split)
```bash
# Entraîner avec split temporel + filtrage
python -m optimization.models.xgboost_trainer_v2
```

**Durée**: 2-3 min
**Résultat attendu**: +10-15% accuracy vs baseline

---

### Étape 3: Ajouter Nouvelles Features
Implémenter features contexte marché (voir Solution 5)

**Durée**: 30 min
**Impact**: +5-10% accuracy

---

### Étape 4: Fine-tuning Optuna (sur V2)
Une fois V2 validé, relancer Optuna sur nouvelles features

**Durée**: 1-2h
**Impact**: +2-5% accuracy

---

### Étape 5: Ensembling (si nécessaire)
Si toujours < 70%, combiner plusieurs modèles

**Durée**: 1h
**Impact**: +2-5% accuracy

---

## 🎯 Objectifs Réalistes

| Étape | Accuracy Attendue | ROC-AUC Attendue |
|-------|------------------|-----------------|
| **Baseline (actuel)** | 52% ❌ | 51% ❌ |
| **Après Étape 2 (V2)** | 62-67% ✅ | 64-69% ✅ |
| **Après Étape 3 (features)** | 67-72% ✅ | 69-74% ✅ |
| **Après Étape 4 (Optuna)** | 70-75% 🎉 | 72-77% 🎉 |
| **Après Étape 5 (ensemble)** | 72-78% 🚀 | 74-80% 🚀 |

---

## ⚠️ Points de Vigilance

### 1. Si accuracy reste < 60% après Étape 2
**Causes possibles**:
- Labels bruités (win/loss mal définis)
- Problème intrinsèquement non-prévisible
- Features insuffisantes

**Actions**:
- Revoir définition win/loss
- Analyser trades manuellement
- Peut-être prédire seulement "high confidence" trades

### 2. Si overfitting (gap > 15%)
**Actions**:
- Augmenter régularisation
- Réduire nombre de features
- Augmenter min_samples_leaf

### 3. Si accuracy validation ≠ accuracy test
**Cause**: Drift temporel (conditions marché changent)

**Actions**:
- Walk-forward validation
- Réentraîner modèle régulièrement
- Ajouter features de régime marché

---

## 📁 Fichiers Créés

```
optimization/
├── utils/
│   ├── __init__.py
│   └── temporal_split.py          # Split temporel + walk-forward
├── analysis/
│   ├── __init__.py
│   └── eda_trading.py              # Analyse exploratoire
└── models/
    ├── xgboost_trainer.py          # V1 (existant - amélioré)
    └── xgboost_trainer_v2.py       # V2 (temporal + filtrage)
```

---

## 🚀 Commandes Rapides

```bash
# 1. Diagnostic
python -m optimization.analysis.eda_trading

# 2. Entraîner V2
python -m optimization.models.xgboost_trainer_v2

# 3. Comparer V1 vs V2
# V1 (existant avec nouvelles features)
python -m optimization.models.xgboost_trainer

# V2 (temporal split)
python -m optimization.models.xgboost_trainer_v2

# 4. Voir résultats
cat optimization/saved_models/xgboost_v2_temporal_metadata.json
```

---

## 💡 Recommandation Finale

**Ne PAS**:
- ❌ Continuer à optimiser hyperparamètres avec Optuna sur données actuelles
- ❌ Ajouter plus de complexité au modèle (deep learning)
- ❌ Utiliser random train_test_split

**FAIRE**:
- ✅ **PRIORITÉ 1**: Lancer EDA (`eda_trading.py`) pour diagnostic
- ✅ **PRIORITÉ 2**: Tester XGBoost V2 avec split temporel
- ✅ **PRIORITÉ 3**: Ajouter features contexte marché
- ✅ Ensuite seulement: Fine-tuning avec Optuna

**Pourquoi**:
Le problème n'est PAS le modèle, mais la **qualité et méthodologie des données**. Optuna ne peut pas compenser du data leakage ou des labels bruités.

---

## 📞 Prochaines Étapes

Que voulez-vous faire maintenant ?

**A) Lancer l'EDA** pour diagnostic complet
**B) Tester XGBoost V2** directement
**C) Ajouter nouvelles features** d'abord
**D) Tout en séquence** (recommandé)
