# 🤖 Trade Cursor ML System - Guide Complet

> **Version**: 1.0  
> **Date**: Novembre 2025  
> **Auteur**: Trade Cursor Team

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture du système](#-architecture-du-système)
3. [Pipeline de données](#-pipeline-de-données)
4. [Feature Engineering](#-feature-engineering)
5. [Entraînement du modèle](#-entraînement-du-modèle)
6. [Système de prédiction](#-système-de-prédiction)
7. [Interface utilisateur](#-interface-utilisateur)
8. [Guide d'utilisation](#-guide-dutilisation)
9. [Troubleshooting](#-troubleshooting)
10. [Optimisations futures](#-optimisations-futures)

---

## 🎯 Vue d'ensemble

### Objectif du système

Le système ML de Trade Cursor prédit la **probabilité de succès (win/loss)** d'une opportunité de trading en temps réel en utilisant :

- **XGBoost** : Algorithme de gradient boosting pour classification binaire
- **81 features engineered** : Dérivées de 46 features de base
- **Feature selection automatique** : Top 30 features les plus importantes
- **Pipeline bout-en-bout** : De la collecte à la prédiction en temps réel

### Flux de données global

```mermaid
graph LR
    A[Scanner Binance] --> B[PostgreSQL]
    B --> C[Feature Engineering]
    C --> D[Preprocessing]
    D --> E[XGBoost Model]
    E --> F[Prédiction win/loss]
    F --> G[Dashboard UI]
```

### Technologies utilisées

| Composant | Technologies |
|-----------|-------------|
| **Backend** | Python 3.12, FastAPI, asyncio |
| **ML/AI** | XGBoost, scikit-learn, pandas, numpy |
| **Base de données** | PostgreSQL (features + historique) |
| **Frontend** | Svelte, TailwindCSS, Vite |
| **Storage** | Pickle (modèles), JSON (metadata) |

### Métriques actuelles

- **Accuracy test**: 61.9%
- **F1 Score**: 60.0%
- **ROC-AUC**: 59.1%
- **Features utilisées**: 30 (sélectionnées sur 81)
- **Temps d'entraînement**: ~0.2s (103 trades)
- **Temps de prédiction**: ~20ms

---

## 🏗️ Architecture du système

### Structure des fichiers

```
optimization/
├── data/
│   ├── feature_loader.py          # Chargement features depuis PostgreSQL
│   ├── feature_engineering.py     # Création 81 features dérivées
│   ├── preprocessor.py            # Imputation + RobustScaler
│   └── feature_importance.py      # Analyse importance features
├── models/
│   └── xgboost_trainer.py         # Training + feature selection
├── saved_models/
│   ├── xgboost_v1.pkl             # Modèle entraîné
│   ├── xgboost_v1_preprocessor.pkl # Pipeline (selector + scaler)
│   └── xgboost_v1_metadata.json   # Metrics, features, params
├── ml_pipeline.py                  # Pipeline complet
├── predictor.py                    # Service prédiction
└── prediction_logger.py            # Logging PostgreSQL

api/routes/
└── ml.py                           # Endpoints FastAPI ML

frontend/src/lib/components/ml/
├── MLDashboard.svelte             # Dashboard principal
├── ModelsOverview.svelte          # Vue modèles + training
├── FeatureImportance.svelte       # Viz importance features
└── LivePredictions.svelte         # Prédictions temps réel
```

### Composants clés

#### 1. **Feature Loader** (`feature_loader.py`)

```python
def load_features_from_db(timeframe_days: int = 60) -> pd.DataFrame:
    """
    Charge les features depuis PostgreSQL
    
    Returns:
        DataFrame avec 46 features de base:
        - RSI, MACD, ADX, Bollinger Bands (1m et 5m)
        - Volume ratios, ATR, EMA trends
        - Filter flags (SNR, breakout, wick, etc.)
    """
```

#### 2. **Feature Engineering** (`feature_engineering.py`)

```python
def calculate_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Génère 81 features à partir de 46 features de base
    
    Catégories:
    - Momentum composites (momentum_1m, momentum_5m, divergence)
    - Volatility features (ratio, expansion, squeeze)
    - Trend strength (ADX-based, EMA-based)
    - Volume anomalies (surge, spike strength)
    - Quality scores (setup quality, confluence)
    """
```

#### 3. **Preprocessor** (`preprocessor.py`)

```python
class FeaturePreprocessor:
    """
    Pipeline de preprocessing:
    1. Imputation (SimpleImputer, strategy='median')
    2. Scaling (RobustScaler pour robustesse aux outliers)
    
    Attributs:
        - imputer: SimpleImputer fitted
        - scaler: RobustScaler fitted
        - feature_names: Liste des features
        - is_fitted: Bool validation
    """
```

#### 4. **XGBoost Trainer** (`xgboost_trainer.py`)

```python
class XGBoostTrainer:
    """
    Entraînement XGBoost avec feature selection
    
    Pipeline:
    1. Load data (fetch_training_dataframe)
    2. Feature engineering (81 features)
    3. Preprocessing (impute + scale)
    4. Feature selection (top 30 by importance)
    5. Re-fit preprocessor sur features sélectionnées
    6. Train final model
    7. Evaluate (accuracy, F1, ROC-AUC)
    8. Save model + preprocessor + metadata
    """
```

#### 5. **Predictor** (`predictor.py`)

```python
class MLPredictor:
    """
    Service de prédiction singleton
    
    Méthodes:
    - load_model(): Charge model + preprocessor + metadata
    - predict(features): Fait une prédiction
    - batch_predict(): Prédictions multiples
    
    Workflow prédiction:
    1. Feature engineering (81 features)
    2. Feature selection (30 features)
    3. Preprocessing (scale)
    4. Prédiction XGBoost
    5. Retour: {prediction, win_probability, confidence}
    """
```

---

## 📊 Pipeline de données

### Collecte des données

Les features sont collectées **en temps réel** par le scanner et stockées dans PostgreSQL :

```sql
CREATE TABLE ml_features (
    scan_id INTEGER PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- RSI features
    rsi_1m FLOAT, rsi_prev_1m FLOAT,
    rsi_5m FLOAT, rsi_prev_5m FLOAT,
    
    -- MACD features
    macd_hist_1m FLOAT, macd_hist_prev_1m FLOAT,
    macd_hist_5m FLOAT, macd_hist_prev_5m FLOAT,
    
    -- ADX features
    adx_1m FLOAT, di_plus_1m FLOAT, di_minus_1m FLOAT,
    adx_5m FLOAT, di_plus_5m FLOAT, di_minus_5m FLOAT,
    
    -- ... 46 features au total
    
    -- Target
    target_win BOOLEAN,
    target_pnl FLOAT
);
```

### Workflow complet

```
1. SCANNER BINANCE (temps réel)
   ↓
2. CALCUL INDICATEURS (RSI, MACD, BB, etc.)
   ↓
3. STOCKAGE PostgreSQL (ml_features table)
   ↓
4. TRIGGER ENTRAÎNEMENT (si > min_trades)
   ↓
5. CHARGEMENT DONNÉES (feature_loader)
   ↓
6. FEATURE ENGINEERING (81 features)
   ↓
7. PREPROCESSING (impute + scale)
   ↓
8. FEATURE SELECTION (top 30)
   ↓
9. TRAINING XGBoost
   ↓
10. SAVE MODEL + METADATA
    ↓
11. AUTO-RELOAD PREDICTOR
    ↓
12. PRÉDICTIONS TEMPS RÉEL
```

### Gestion du cache

Le système utilise un **singleton pattern** pour le predictor :

```python
_predictor_instance: Optional[MLPredictor] = None

def get_predictor(model_name: str = "xgboost_v1") -> MLPredictor:
    """
    Récupère ou crée l'instance singleton du predictor
    - Évite de recharger le modèle à chaque prédiction
    - Reload automatique après training
    """
    global _predictor_instance
    
    if _predictor_instance is None or _predictor_instance.model_name != model_name:
        _predictor_instance = MLPredictor(model_name)
        _predictor_instance.load_model()
    
    return _predictor_instance
```

---

## 🔧 Feature Engineering

### Features de base (46)

Les **46 features de base** sont calculées directement depuis les données de marché :

#### Timeframe 1 minute (18 features)

| Feature | Description | Type |
|---------|-------------|------|
| `rsi_1m` | RSI actuel | Float (0-100) |
| `rsi_prev_1m` | RSI précédent | Float (0-100) |
| `macd_hist_1m` | MACD histogram | Float |
| `macd_hist_prev_1m` | MACD histogram précédent | Float |
| `adx_1m` | Average Directional Index | Float (0-100) |
| `di_plus_1m` | Directional Indicator + | Float |
| `di_minus_1m` | Directional Indicator - | Float |
| `di_gap_1m` | Écart DI+ et DI- | Float |
| `atr_pct_1m` | ATR en % du prix | Float |
| `ema_diff_pct_1m` | EMA 9-21 diff en % | Float |
| `volume_ratio_1m` | Volume / MA volume | Float |
| `volume_spike_1m` | Spike volume (0/1) | Binary |
| `bb_width_1m` | Bollinger Bands width | Float |
| `bb_distance_to_lower_1m` | Distance à BB inférieure | Float |
| `bb_distance_to_upper_1m` | Distance à BB supérieure | Float |
| `snr_passed_1m` | SNR filter passed | Binary |
| `breakout_passed_1m` | Breakout filter passed | Binary |
| `wick_passed_1m` | Wick filter passed | Binary |

#### Timeframe 5 minutes (18 features)

Mêmes features que 1m mais sur timeframe 5m.

#### Features additionnelles (10 features)

- `atr_optimal_passed_1m/5m` : ATR optimal range
- `volume_filter_passed_1m/5m` : Volume sufficient
- `is_opportunity` : Opportunité validée
- `target_win` : **Label** (win/loss)
- `target_pnl` : PnL réalisé

### Features dérivées (81 features au total)

Le **feature engineering** génère **41 features supplémentaires** :

#### 1. Momentum Composites

```python
# Momentum 1m (RSI * MACD normalized)
momentum_1m = (rsi_1m / 100) * np.tanh(macd_hist_1m)

# Momentum 5m
momentum_5m = (rsi_5m / 100) * np.tanh(macd_hist_5m)

# Divergence cross-timeframe
momentum_divergence = momentum_1m - momentum_5m

# RSI changes
rsi_change_1m = rsi_1m - rsi_prev_1m
rsi_change_5m = rsi_5m - rsi_prev_5m
rsi_divergence = rsi_change_1m - rsi_change_5m

# MACD momentum
macd_momentum_1m = macd_hist_1m - macd_hist_prev_1m
macd_momentum_5m = macd_hist_5m - macd_hist_prev_5m
```

#### 2. Volatility Features

```python
# Volatility ratio (1m vs 5m)
volatility_ratio = atr_pct_1m / (atr_pct_5m + 1e-8)

# Volatility expansion
volatility_expanding = (volatility_ratio > 1.5).astype(int)

# Bollinger squeeze
bb_squeeze_1m = (bb_width_1m < 2.0).astype(int)
bb_squeeze_5m = (bb_width_5m < 2.0).astype(int)
```

#### 3. Trend Strength

```python
# Trend strength from DI gap
trend_strength_1m = di_gap_1m * (adx_1m / 100)
trend_strength_5m = di_gap_5m * (adx_5m / 100)

# Strong trend detection
strong_trend_1m = (adx_1m > 25) & (abs(di_gap_1m) > 10)
strong_trend_5m = (adx_5m > 25) & (abs(di_gap_5m) > 10)

# EMA trend strength
ema_trend_strength_1m = abs(ema_diff_pct_1m)
ema_trend_strength_5m = abs(ema_diff_pct_5m)

# Bullish/Bearish signals
ema_bullish_1m = (ema_diff_pct_1m > 0).astype(int)
trend_bullish_1m = (di_plus_1m > di_minus_1m).astype(int)
```

#### 4. Volume Anomalies

```python
# Volume surge (both timeframes aligned)
volume_surge = (volume_ratio_1m > 1.5) & (volume_ratio_5m > 1.2)

# Volume spike strength
volume_spike_strong = (volume_spike_1m == 1) & (volume_ratio_1m > 2.0)
```

#### 5. Quality Scores

```python
# Quality score 1m (filters passed)
quality_score_1m = (
    snr_passed_1m + 
    breakout_passed_1m + 
    wick_passed_1m + 
    atr_optimal_passed_1m + 
    volume_filter_passed_1m
)

# Quality score 5m
quality_score_5m = (
    snr_passed_5m + 
    breakout_passed_5m + 
    wick_passed_5m + 
    atr_optimal_passed_5m + 
    volume_filter_passed_5m
)

# Total quality
quality_score_total = quality_score_1m + quality_score_5m

# High quality setup
high_quality_setup = (quality_score_total >= 7).astype(int)
low_quality_risk = (quality_score_total <= 3).astype(int)
```

#### 6. Confluence Patterns

```python
# Bullish confluence
bullish_confluence = (
    (rsi_1m > 50) & 
    (macd_hist_1m > 0) & 
    (di_plus_1m > di_minus_1m) & 
    (ema_diff_pct_1m > 0)
).astype(int)

# Bearish confluence
bearish_confluence = (
    (rsi_1m < 50) & 
    (macd_hist_1m < 0) & 
    (di_plus_1m < di_minus_1m) & 
    (ema_diff_pct_1m < 0)
).astype(int)
```

### Importance des features

Les **top 10 features** sélectionnées par XGBoost :

1. `ema_diff_pct_5m` - Trend EMA 5m
2. `bb_distance_to_upper_1m` - Proximité BB supérieure
3. `volatility_ratio` - Ratio volatilité 1m/5m
4. `macd_hist_5m` - MACD histogram 5m
5. `atr_pct_1m` - Volatilité ATR 1m
6. `bb_width_1m` - Largeur Bollinger Bands
7. `momentum_1m` - Momentum composite
8. `trend_strength_5m` - Force trend 5m
9. `quality_score_total` - Score qualité setup
10. `rsi_divergence` - Divergence RSI cross-TF

---

## 🎓 Entraînement du modèle

### Configuration XGBoost

```python
model_params = {
    'n_estimators': 150,        # Nombre d'arbres
    'max_depth': 4,             # Profondeur max (évite overfitting)
    'learning_rate': 0.05,      # Taux d'apprentissage conservateur
    'scale_pos_weight': 1.05,   # Balance classes win/loss
    'random_state': 42,         # Reproductibilité
    'eval_metric': 'logloss',   # Métrique d'évaluation
    'use_label_encoder': False  # sklearn compat
}
```

### Pipeline d'entraînement

```python
def train(self, timeframe_days=60, min_trades=50, feature_selection=True, max_features=30):
    """
    Pipeline complet d'entraînement
    
    Args:
        timeframe_days: Fenêtre temporelle des données
        min_trades: Minimum de trades requis
        feature_selection: Activer feature selection
        max_features: Nombre de features à sélectionner
    
    Returns:
        dict: Résultats (metrics, features, paths)
    """
    
    # 1. Chargement données
    dataset = prepare_training_dataset(timeframe_days, min_trades)
    # dataset.X: 103 samples × 81 features
    # dataset.y: target_win (0/1)
    
    # 2. Split train/test (80/20, stratified)
    X_train, X_test, y_train, y_test = split_training_dataset(dataset)
    # X_train: 82 samples
    # X_test: 21 samples
    
    # 3. Feature selection (optionnel)
    if feature_selection:
        # Train modèle initial pour feature importance
        initial_model = XGBClassifier(**model_params)
        initial_model.fit(X_train, y_train)
        
        # Sélection top N features
        importances = initial_model.feature_importances_
        indices = np.argsort(importances)[::-1][:max_features]
        selected_features = X_train.columns[indices].tolist()
        
        # Re-filtrage datasets
        X_train = X_train[selected_features]
        X_test = X_test[selected_features]
        
        # Re-fit preprocessor sur features sélectionnées
        imputer = SimpleImputer(strategy='median')
        scaler = RobustScaler()
        
        X_train_scaled = scaler.fit_transform(imputer.fit_transform(X_train))
        X_test_scaled = scaler.transform(imputer.transform(X_test))
        
        # Créer preprocessor wrapper
        selected_preprocessor = FeaturePreprocessor(scaler_type="robust")
        selected_preprocessor.imputer = imputer
        selected_preprocessor.scaler = scaler
        selected_preprocessor.feature_names = selected_features
        selected_preprocessor.is_fitted = True
        
        # Pipeline: FeatureSelector → Preprocessor
        new_preprocessor = Pipeline([
            ('feature_selector', FeatureSelector(selected_features)),
            ('scaler', selected_preprocessor)
        ])
        
        # Save preprocessor
        joblib.dump(new_preprocessor, f"{model_dir}/{model_name}_preprocessor.pkl")
    
    # 4. Entraînement modèle final
    self.model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        early_stopping_rounds=10,
        verbose=False
    )
    
    # 5. Évaluation
    y_pred = self.model.predict(X_test)
    y_proba = self.model.predict_proba(X_test)
    
    metrics = {
        'test_accuracy': accuracy_score(y_test, y_pred),
        'test_precision': precision_score(y_test, y_pred),
        'test_recall': recall_score(y_test, y_pred),
        'test_f1': f1_score(y_test, y_pred),
        'test_roc_auc': roc_auc_score(y_test, y_proba[:, 1])
    }
    
    # 6. Sauvegarde
    pickle.dump(self.model, open(f"{model_dir}/{model_name}.pkl", 'wb'))
    
    # 7. Metadata
    metadata = {
        'version': 1,
        'model_type': 'xgboost',
        'trained_at': datetime.now().isoformat(),
        'params': model_params,
        'metrics': metrics,
        'feature_names': selected_features,
        'n_features': len(selected_features),
        'n_samples': len(X_train) + len(X_test)
    }
    
    json.dump(metadata, open(f"{model_dir}/{model_name}_metadata.json", 'w'))
    
    return metrics
```

### Métriques d'évaluation

| Métrique | Valeur | Description |
|----------|--------|-------------|
| **Accuracy** | 61.9% | Proportion prédictions correctes |
| **Precision** | ~60% | Proportion wins prédits corrects |
| **Recall** | ~60% | Proportion wins réels détectés |
| **F1 Score** | 60.0% | Harmonic mean precision/recall |
| **ROC-AUC** | 59.1% | Aire sous courbe ROC |

### Class balancing

```python
# Calcul weights pour équilibrer les classes
class_weights = compute_class_weight(
    class_weight='balanced',
    classes=np.unique(y_train),
    y=y_train
)
# Win: 1.025, Loss: 0.976
```

---

## 🔮 Système de prédiction

### MLPredictor Class

```python
class MLPredictor:
    def __init__(self, model_name: str = "xgboost_v1"):
        self.model_name = model_name
        self.model = None
        self.preprocessor = None  # Pipeline (selector + scaler)
        self.metadata = None
        self.feature_names = None
        self.loaded = False
    
    def load_model(self) -> bool:
        """Charge modèle + preprocessor + metadata"""
        # 1. Charger modèle XGBoost
        with open(f"{models_dir}/{self.model_name}.pkl", 'rb') as f:
            self.model = pickle.load(f)
        
        # 2. Charger preprocessor pipeline
        self.preprocessor = joblib.load(
            f"{models_dir}/{self.model_name}_preprocessor.pkl"
        )
        
        # 3. Charger metadata
        with open(f"{models_dir}/{self.model_name}_metadata.json", 'r') as f:
            self.metadata = json.load(f)
        
        # 4. Extraire feature names
        self.feature_names = self.metadata['training_info']['feature_names']
        
        self.loaded = True
        return True
    
    def predict(self, features: Dict) -> Optional[Dict]:
        """
        Fait une prédiction sur une opportunité
        
        Args:
            features: Dict avec 46 features de base
        
        Returns:
            {
                'prediction': 'win' | 'loss',
                'win_probability': float (0-1),
                'confidence': float (0-1),
                'model_name': str,
                'top_features': List[{feature, importance}]
            }
        """
        # 1. Feature engineering (46 → 81 features)
        df_features = pd.DataFrame([features])
        df_engineered = calculate_derived_features(df_features)
        engineered_features = df_engineered.iloc[0].to_dict()
        
        # 2. Convertir en DataFrame
        df = pd.DataFrame([engineered_features])
        
        # 3. Vérifier features manquantes
        missing_features = set(self.feature_names) - set(df.columns)
        if missing_features:
            for feat in missing_features:
                df[feat] = 0  # Imputation par défaut
        
        # 4. Garder ordre correct des features
        df = df[self.feature_names]
        
        # 5. Remplacer NaN/inf
        df = df.replace([np.inf, -np.inf], 0).fillna(0)
        
        # 6. Preprocessing (selector + scaler)
        X = self.preprocessor.transform(df)
        
        # 7. Prédiction XGBoost
        prediction = int(self.model.predict(X)[0])
        proba = self.model.predict_proba(X)[0]
        
        # 8. Construire résultat
        result = {
            'prediction': 'win' if prediction == 1 else 'loss',
            'prediction_value': prediction,
            'win_probability': float(proba[1]),
            'loss_probability': float(proba[0]),
            'confidence': float(max(proba)),
            'model_name': self.model_name,
            'predicted_at': datetime.now().isoformat()
        }
        
        return result
```

### Workflow de prédiction

```
1. Recevoir features de base (46)
   ↓
2. Feature engineering (→ 81 features)
   ↓
3. Sélection features (→ 30 features)
   ↓
4. Preprocessing (impute + scale)
   ↓
5. Prédiction XGBoost
   ↓
6. Probabilités (win/loss)
   ↓
7. Retour résultat
```

### Exemple d'utilisation

```python
# Créer features de base
features = {
    'rsi_1m': 65.5,
    'rsi_prev_1m': 63.2,
    'macd_hist_1m': 0.0012,
    'macd_hist_prev_1m': 0.0008,
    'adx_1m': 25.0,
    # ... 41 autres features
}

# Prédiction
from optimization.predictor import predict_opportunity

prediction = predict_opportunity(
    features=features,
    model_name='xgboost_v1',
    symbol='BTCUSDT',
    log_to_db=True
)

# Résultat
{
    'prediction': 'win',
    'win_probability': 0.5959,
    'confidence': 0.5959,
    'model_name': 'xgboost_v1',
    'predicted_at': '2025-11-16T19:00:17'
}
```

### Logging des prédictions

```python
def log_prediction(
    prediction_data: Dict,
    symbol: str,
    scan_id: Optional[int],
    opportunity_timestamp: datetime,
    metadata: Dict
) -> Optional[int]:
    """
    Log prédiction dans PostgreSQL
    
    Table: ml_predictions
    Colonnes:
    - prediction_id (auto)
    - symbol, scan_id
    - win_probability, loss_probability
    - confidence, model_name
    - predicted_at, actual_result (NULL initialement)
    """
```

---

## 🎨 Interface utilisateur

### Dashboard ML

Le dashboard ML est accessible via **ML** dans le menu principal.

#### 1. Vue Dashboard

**Composant**: `MLDashboard.svelte`

```svelte
<script>
  import { mlStats, dataQuality, loadAllMLData } from '$lib/stores/ml';
  import ModelsOverview from './ModelsOverview.svelte';
  import FeatureImportance from './FeatureImportance.svelte';
  
  // Tabs
  let activeSubTab = 'dashboard'; // dashboard | features | models
</script>

<div class="ml-container">
  <MLTabs bind:activeSubTab />
  
  {#if activeSubTab === 'dashboard'}
    <DataProgressCard stats={$mlStats} />
    <DataQualityCard quality={$dataQuality} />
  {:else if activeSubTab === 'features'}
    <FeatureImportance />
  {:else if activeSubTab === 'models'}
    <ModelsOverview />
  {/if}
</div>
```

#### 2. Vue Modèles

**Composant**: `ModelsOverview.svelte`

Affiche :
- **Status** : Ready / Locked / Trained
- **Minimum requis** : 50 trades (XGBoost)
- **Optimal** : 200 trades
- **Confiance** : "Medium" / "High"
- **Bouton training** : Déclenche entraînement
- **Status training** : Spinner + polling toutes les 10s

```svelte
<div class="model-card">
  <h3>🌲 XGBoost</h3>
  
  {#if model.trained}
    <span class="badge trained">✓ Entraîné</span>
  {:else if model.ready}
    <span class="badge ready">Prêt</span>
    <button on:click={startTraining}>
      🚀 Entraîner le Modèle
    </button>
  {:else}
    <span class="badge locked">🔒 Verrouillé</span>
    <div class="progress-bar">
      <div class="progress-fill" style="width: {progress}%"></div>
    </div>
    <p>{tradesCount} / {minRequired} trades</p>
  {/if}
  
  {#if trainingStatus === 'running'}
    <div class="training-status">
      <Spinner />
      <p>Entraînement en cours...</p>
    </div>
  {/if}
</div>
```

#### 3. Feature Importance

**Composant**: `FeatureImportance.svelte`

Affiche les **top 20 features** par importance (corrélation ou XGBoost importance).

```svelte
<div class="feature-importance">
  <select bind:value={method}>
    <option value="correlation">Corrélation</option>
    <option value="xgboost">XGBoost Importance</option>
  </select>
  
  <div class="features-list">
    {#each features as feature}
      <div class="feature-bar">
        <span class="feature-name">{feature.name}</span>
        <div class="bar" style="width: {feature.importance * 100}%"></div>
        <span class="score">{feature.importance.toFixed(3)}</span>
      </div>
    {/each}
  </div>
</div>
```

#### 4. Live Predictions

**Composant**: `LivePredictions.svelte`

Permet de tester le modèle avec des features démo.

```svelte
<button on:click={fetchPrediction}>
  Nouvelle Prédiction
</button>

{#if prediction}
  <div class="prediction-card">
    <h4>
      {prediction.prediction === 'win' ? '✅ WIN' : '❌ LOSS'}
    </h4>
    <p>Confiance: {(prediction.confidence * 100).toFixed(1)}%</p>
    <p>Win probability: {(prediction.win_probability * 100).toFixed(1)}%</p>
  </div>
{/if}
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/dashboard/stats` | GET | Stats dashboard ML |
| `/api/ml/models/status` | GET | Status tous modèles |
| `/api/ml/features/importance` | GET | Importance features |
| `/api/ml/train` | POST | Lancer entraînement |
| `/api/ml/tasks/{task_id}` | GET | Status tâche training |
| `/api/ml/predict` | POST | Faire prédiction |
| `/api/ml/predictor/reload` | POST | Recharger predictor |

---

## 📖 Guide d'utilisation

### Étape 1 : Collecte de données

**Pré-requis** : Scanner actif avec **minimum 50 trades** complétés.

1. Lancer le scanner via l'UI
2. Attendre accumulation de trades
3. Vérifier dans **ML → Dashboard** :
   - Trades collectés : > 50
   - Quality score : > 70%

```bash
# Via terminal
curl http://localhost:5000/api/ml/dashboard/stats
```

### Étape 2 : Entraînement du modèle

**Via UI** :

1. Aller dans **ML → Modèles**
2. Vérifier que XGBoost affiche **"Prêt"**
3. Cliquer sur **"🚀 Entraîner le Modèle"**
4. Attendre fin entraînement (~10-30s)
5. Status passe à **"✓ Entraîné"**

**Via API** :

```bash
curl -X POST "http://localhost:5000/api/ml/train?model_type=xgboost&timeframe_days=30&min_trades=50"
```

**Résultat** :

```json
{
  "task_id": "fcd563f2-3245-48d8-9f85-3fdc5c63cf70",
  "status": "pending",
  "message": "Entraînement xgboost démarré"
}
```

**Vérifier status** :

```bash
curl http://localhost:5000/api/ml/tasks/{task_id}
```

### Étape 3 : Faire une prédiction

**Via UI** :

1. Aller dans **ML → Prédictions**
2. Cliquer **"Nouvelle Prédiction"** (utilise features démo)
3. Voir résultat : WIN/LOSS + confiance

**Via API** :

```bash
curl -X POST http://localhost:5000/api/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "rsi_1m": 65.5,
    "rsi_prev_1m": 63.2,
    "macd_hist_1m": 0.0012,
    ... (46 features de base)
  }'
```

**Résultat** :

```json
{
  "prediction": "win",
  "win_probability": 0.5959,
  "confidence": 0.5959,
  "model_name": "xgboost_v1",
  "predicted_at": "2025-11-16T19:00:17"
}
```

### Étape 4 : Réentraînement

Le modèle doit être **réentraîné périodiquement** avec de nouvelles données :

- **Recommandé** : Tous les 100-200 nouveaux trades
- **Automatique** : Reload predictor après training (implémenté)

```bash
# Réentraîner
curl -X POST http://localhost:5000/api/ml/train?model_type=xgboost

# Le predictor se recharge automatiquement ✅
```

### Étape 5 : Monitoring

**Vérifier performances** :

```bash
# Metadata du modèle
cat optimization/saved_models/xgboost_v1_metadata.json

# Logs training
grep "Entraînement XGBoost" logs/app.log

# Logs prédictions
grep "Prédiction:" logs/app.log
```

**Dashboard** :

- Accuracy test : > 55%
- F1 Score : > 50%
- Confiance moyenne : > 55%

---

## 🔧 Troubleshooting

### Erreur : "The feature names should match those that were passed during fit"

**Cause** : Mismatch entre features utilisées pendant training et prédiction.

**Solution** :

1. Vérifier que le preprocessor est bien rechargé après training
2. S'assurer que le feature engineering est appliqué avant prédiction
3. Vérifier `is_fitted = True` sur le preprocessor

```python
# Dans predictor.py
def predict_opportunity(features, ...):
    # ✅ Appliquer feature engineering
    df_engineered = calculate_derived_features(pd.DataFrame([features]))
    engineered_features = df_engineered.iloc[0].to_dict()
    
    # ✅ Passer au predictor
    prediction = predictor.predict(engineered_features)
```

### Erreur : "Preprocessor not fitted"

**Cause** : Le preprocessor n'a pas l'attribut `is_fitted = True`.

**Solution** :

```python
# Dans xgboost_trainer.py, après avoir créé selected_preprocessor
selected_preprocessor.is_fitted = True  # ✅ Ajouter cet attribut
```

### Erreur : "ValueError: Target column 'target_win' not found"

**Cause** : `fit_transform` appelé sur des features sans la colonne target.

**Solution** : Utiliser directement le scaler sans appeler `fit_transform` du `FeaturePreprocessor` :

```python
# ✅ Correct
imputer = SimpleImputer(strategy='median')
scaler = RobustScaler()

X_train_imputed = imputer.fit_transform(X_train)
X_train_scaled = scaler.fit_transform(X_train_imputed)

# ❌ Incorrect
preprocessor.fit_transform(X_train)  # Cherche target_win
```

### Erreur : "Model file not found"

**Cause** : Modèle pas encore entraîné ou fichier supprimé.

**Solution** :

```bash
# Vérifier existence
ls optimization/saved_models/xgboost_v1*

# Si absent, réentraîner
curl -X POST http://localhost:5000/api/ml/train?model_type=xgboost
```

### Warning : "X has feature names, but RobustScaler was fitted without feature names"

**Cause** : Le scaler a été fit avec un numpy array au lieu d'un DataFrame.

**Impact** : Aucun (warning seulement, les prédictions fonctionnent)

**Solution (optionnel)** : Passer numpy array au lieu de DataFrame au transform :

```python
# Au lieu de
X = preprocessor.transform(df)

# Utiliser
X = preprocessor.transform(df.values)  # numpy array
```

### Erreur 404 sur `/api/ml/predict`

**Cause** : Predictor pas chargé ou endpoint mal configuré.

**Solution** :

```python
# Vérifier dans api/routes/ml.py
@router.post("/predict")
async def predict_opportunity(...):  # ✅ Présent
    from optimization.predictor import predict_opportunity as predict_opp
    return predict_opp(features, model_name)
```

```bash
# Recharger predictor manuellement
curl -X POST http://localhost:5000/api/ml/predictor/reload
```

### Logs vides ou erreurs silencieuses

**Solution** :

```python
# Augmenter niveau logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Ou dans les modules
logger.setLevel(logging.DEBUG)
```

### Performances dégradées

**Causes possibles** :

1. **Trop peu de données** : < 50 trades → Accuracy faible
2. **Class imbalance** : Trop de wins ou trop de losses
3. **Features non informatives** : Quality score trop bas

**Solutions** :

```python
# 1. Vérifier nombre de trades
SELECT COUNT(*) FROM ml_features WHERE target_win IS NOT NULL;

# 2. Vérifier balance
SELECT target_win, COUNT(*) FROM ml_features GROUP BY target_win;
# Idéal: 40-60% wins

# 3. Augmenter quality filters dans scanner
```

---

## 🚀 Optimisations futures

### 1. Feature Engineering avancé

**Objectif** : Améliorer les features pour meilleures prédictions.

```python
# Nouvelles features à implémenter:

# Patterns de chandeliers
def candlestick_patterns(df):
    df['hammer'] = detect_hammer(df)
    df['doji'] = detect_doji(df)
    df['engulfing'] = detect_engulfing(df)

# Multi-timeframe aggregation
def multi_tf_features(df):
    df['rsi_15m'] = calculate_rsi(df, timeframe='15m')
    df['volume_1h'] = aggregate_volume(df, timeframe='1h')

# Sentiment features
def market_sentiment(df):
    df['fear_greed_index'] = get_fear_greed()
    df['funding_rate'] = get_funding_rate()
```

### 2. Hyperparameter Tuning

**Objectif** : Optimiser les paramètres XGBoost avec GridSearch ou Optuna.

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [100, 150, 200],
    'max_depth': [3, 4, 5],
    'learning_rate': [0.01, 0.05, 0.1],
    'min_child_weight': [1, 3, 5]
}

grid_search = GridSearchCV(
    XGBClassifier(),
    param_grid,
    cv=5,
    scoring='f1',
    n_jobs=-1
)

grid_search.fit(X_train, y_train)
best_params = grid_search.best_params_
```

### 3. Ensemble de modèles

**Objectif** : Combiner plusieurs modèles pour améliorer robustesse.

```python
from sklearn.ensemble import VotingClassifier

# XGBoost + RandomForest + LightGBM
ensemble = VotingClassifier(
    estimators=[
        ('xgb', XGBClassifier(...)),
        ('rf', RandomForestClassifier(...)),
        ('lgbm', LGBMClassifier(...))
    ],
    voting='soft'  # Vote pondéré par probabilités
)

ensemble.fit(X_train, y_train)
```

### 4. Deep Learning (LSTM/Transformer)

**Objectif** : Utiliser réseaux de neurones pour capturer dépendances temporelles.

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

# Architecture LSTM
model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(sequence_length, n_features)),
    Dropout(0.2),
    LSTM(64),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(1, activation='sigmoid')
])

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy', 'AUC']
)
```

### 5. Online Learning

**Objectif** : Mise à jour incrémentale du modèle sans réentraînement complet.

```python
from river import tree, ensemble

# Modèle online learning
model = ensemble.AdaptiveRandomForestClassifier(
    n_models=10,
    max_features=30,
    seed=42
)

# Update incrémental
for features, label in new_data_stream:
    prediction = model.predict_one(features)
    model.learn_one(features, label)
```

### 6. Feature Store

**Objectif** : Centraliser et versionner les features.

```python
# Utiliser Feast ou custom solution
from feast import FeatureStore

store = FeatureStore(repo_path=".")

# Récupérer features online
features = store.get_online_features(
    entity_rows=[{"symbol": "BTCUSDT", "timestamp": now()}],
    features=["ml_features:rsi_1m", "ml_features:macd_hist_1m"]
).to_dict()
```

### 7. Model Monitoring & Drift Detection

**Objectif** : Détecter dégradation des performances en production.

```python
from evidently import Report
from evidently.metrics import DataDriftPreset

# Comparer distribution features training vs production
report = Report(metrics=[DataDriftPreset()])
report.run(reference_data=train_df, current_data=production_df)

if report.as_dict()['drift_detected']:
    trigger_retraining()
```

### 8. A/B Testing

**Objectif** : Tester plusieurs versions de modèles simultanément.

```python
# Router 50% vers model_v1, 50% vers model_v2
import random

def get_model_version():
    return "xgboost_v1" if random.random() < 0.5 else "xgboost_v2"

prediction = predict_opportunity(features, model_name=get_model_version())

# Comparer métriques
compare_model_performance("xgboost_v1", "xgboost_v2")
```

### 9. Automated Retraining Pipeline

**Objectif** : Réentraînement automatique quand conditions remplies.

```python
# Cron job ou Airflow DAG
def auto_retrain_check():
    new_trades = count_new_trades_since_last_training()
    
    if new_trades >= 100:
        # Assez de nouvelles données
        trigger_training()
        
    current_accuracy = get_current_accuracy()
    if current_accuracy < 0.55:
        # Performance dégradée
        trigger_training()
```

### 10. Explainability (SHAP)

**Objectif** : Comprendre pourquoi le modèle fait certaines prédictions.

```python
import shap

# Calculer SHAP values
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Visualiser importance locale
shap.force_plot(
    explainer.expected_value,
    shap_values[0],
    X_test.iloc[0]
)

# Feature importance globale
shap.summary_plot(shap_values, X_test)
```

---

## 📚 Ressources additionnelles

### Documentation technique

- **XGBoost** : https://xgboost.readthedocs.io/
- **scikit-learn** : https://scikit-learn.org/
- **Pandas** : https://pandas.pydata.org/
- **FastAPI** : https://fastapi.tiangolo.com/

### Papers & Articles

- [XGBoost: A Scalable Tree Boosting System](https://arxiv.org/abs/1603.02754)
- [Feature Engineering for Machine Learning](https://www.oreilly.com/library/view/feature-engineering-for/9781491953235/)
- [Interpretable Machine Learning](https://christophm.github.io/interpretable-ml-book/)

### Best Practices ML

1. **Toujours valider sur données hors-sample** (test set)
2. **Monitorer drift des features** en production
3. **Versionner les modèles** (MLflow, DVC)
4. **Documenter les expérimentations** (Weights & Biases)
5. **Tester en production** avant déploiement full

---

## 🎓 Conclusion

Le système ML de Trade Cursor est maintenant **100% fonctionnel** avec :

✅ **Pipeline complet** de bout en bout  
✅ **Feature engineering** automatique (81 features)  
✅ **Feature selection** intelligente (top 30)  
✅ **Training** optimisé avec early stopping  
✅ **Prédictions** temps réel (< 20ms)  
✅ **Interface UI** intuitive et complète  
✅ **Auto-reload** après training  
✅ **Logging & Monitoring** PostgreSQL  

### Métriques actuelles

- **Accuracy**: 61.9%
- **F1 Score**: 60.0%
- **ROC-AUC**: 59.1%
- **Temps training**: ~0.2s (103 trades)
- **Temps prédiction**: ~20ms

### Prochaines étapes recommandées

1. **Collecter plus de données** (objectif: 500+ trades)
2. **Réentraîner régulièrement** (tous les 100-200 trades)
3. **Monitorer performances** en production
4. **Expérimenter** avec nouvelles features
5. **A/B tester** différentes configurations

---

**Version**: 1.0  
**Date**: Novembre 2025  
**Auteur**: Trade Cursor Team  

*Pour toute question ou amélioration, consulter le code source ou ouvrir une issue.*

