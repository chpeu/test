# ⏭️ PROCHAINES ÉTAPES - XGBoost V2

**Date**: 24 novembre 2025 - 20h20  
**Status Actuel**: Infrastructure 100% ✅ | Modèle ML 45.9% accuracy ❌

---

## 🎯 3 ACTIONS PRIORITAIRES

### **1️⃣ Feature Engineering Approfondi (2-3h)**

**Problème** : Features actuelles non discriminantes (RSI, MACD, BB seuls insuffisants)

**Solution** : Ajouter dans `optimization/data/feature_engineering.py`

```python
def add_advanced_features(df):
    """Ajouter features avancées discriminantes"""
    
    # A. Temporelles
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_market_hours'] = df['hour'].between(8, 22).astype(int)
    
    # B. Market Regime
    df['atr_1m_ma20'] = df['atr_1m'].rolling(20).mean()
    df['high_volatility'] = (df['atr_1m'] > df['atr_1m_ma20']).astype(int)
    
    df['ema9'] = df['price'].ewm(span=9).mean()
    df['ema21'] = df['price'].ewm(span=21).mean()
    df['uptrend'] = (df['ema9'] > df['ema21']).astype(int)
    
    # C. Confluence
    df['bullish_setup'] = (
        (df['rsi_1m'] < 30) & 
        (df['macd_1m'] > df['macd_signal_1m']) &
        (df['bb_position_1m'] < 0.2)
    ).astype(int)
    
    df['bearish_setup'] = (
        (df['rsi_1m'] > 70) & 
        (df['macd_1m'] < df['macd_signal_1m']) &
        (df['bb_position_1m'] > 0.8)
    ).astype(int)
    
    # D. Interactions
    df['rsi_macd_product'] = df['rsi_1m'] * df['macd_1m']
    df['volume_price_ratio'] = df['volume_1m'] / (df['price'] + 1e-6)
    
    return df
```

**Tester** :
```bash
python train_final_optimized.py
```

**Objectif** : Test Accuracy >= 60%, F1 > 0.30

---

### **2️⃣ Augmenter Dataset (1h)**

**Problème** : 1150 trades après filtrage trop peu

**Solution** : Dans `train_final_optimized.py`

```python
# Ligne 17-18 : Augmenter timeframe
base_df = load_features_from_postgres(
    timeframe_days=365,  # 1 an au lieu de 270
    min_trades=30        # Moins restrictif
)

# Ligne 44 : Élargir filtrage
df = df[abs(df['target_pnl']) >= 0.15].copy()  # 0.15% au lieu de 0.20%
```

**Objectif** : 2000+ trades après filtrage

---

### **3️⃣ Tester Régression (1h)**

**Problème** : Classification binaire WIN/LOSS trop simpliste

**Solution** : Créer `train_regression.py`

```python
from xgboost import XGBRegressor

# Prédire PNL directement (régression)
model = XGBRegressor(
    n_estimators=600,
    max_depth=4,
    learning_rate=0.03,
    ...
)

model.fit(X_train, y_train_pnl)  # target_pnl au lieu de target_win

# Prédiction
predictions = model.predict(X_test)

# Classer : si prediction > 0.20% → Trade
trades_predicted = predictions > 0.20

# Métriques
from sklearn.metrics import mean_absolute_error
mae = mean_absolute_error(y_test_pnl, predictions)
print(f"MAE: {mae:.3f}%")
```

**Avantages** :
- Capture nuances (petit WIN vs gros WIN)
- Permet optimiser seuil de décision
- Régression souvent plus stable

---

## 📊 INDICATEURS DE SUCCÈS

| Métrique | Actuel | Après Fix 1 | Après Fix 2 | Après Fix 3 |
|----------|--------|-------------|-------------|-------------|
| **Test Accuracy** | 45.9% | 60%+ | 65%+ | 70%+ |
| **F1 Score** | 0.000 | 0.30+ | 0.40+ | 0.50+ |
| **Test ROC-AUC** | 45.1% | 60%+ | 65%+ | 70%+ |

---

## ⏱️ TEMPS TOTAL ESTIMÉ

```
Fix 1: Feature Engineering     [████████░░] 2-3h
Fix 2: Augmentation Dataset    [███░░░░░░░] 1h
Fix 3: Test Régression         [███░░░░░░░] 1h
                               ─────────────────
                               TOTAL: 4-5h
```

---

## 🔧 CORRECTIF MINEUR (5 min)

**Avant de réentraîner**, corriger dans `optimization/models/model_logger.py` :

```python
# Ligne 132 : Remplacer
result = pg.execute_query(insert_query, params, fetch=True)

# Par
result = pg._execute_query(insert_query, params, fetch=True)
```

---

## 📁 DOCUMENTS CRÉÉS AUJOURD'HUI

1. ✅ `SYNTHESE_FINALE_COMPLETE.md` - Résumé complet travail
2. ✅ `FIX_PRIX_MANQUANTS.md` - Fix price_provider
3. ✅ `FINAL_SUMMARY_V2.md` - Infrastructure V2
4. ✅ `train_final_optimized.py` - Script entraînement optimisé
5. ✅ `analyze_win_loss.py` - Analyse distribution
6. ✅ `fix_db_simple.py` - Correction DB auto
7. ✅ `NEXT_STEPS.md` - Ce fichier

---

## 🚀 COMMENCER MAINTENANT

```bash
# 1. Modifier feature_engineering.py (ajouter add_advanced_features)
# 2. Modifier calculate_derived_features pour appeler add_advanced_features
# 3. Lancer
python train_final_optimized.py
```

**Si accuracy >= 60% → Succès !**  
**Si accuracy < 60% → Passer à Fix 2 (augmenter dataset)**

---

**📌 Priorité absolue : Feature Engineering**
