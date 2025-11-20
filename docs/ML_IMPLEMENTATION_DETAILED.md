# 🤖 Documentation Technique ML - Trade Cursor v7.0

## Architecture Complète

### 📁 Structure des Fichiers ML

```
optimization/
├── data/
│   ├── feature_loader.py          # Chargement PostgreSQL → DataFrame
│   ├── feature_engineering.py     # 46 features → 120+ features dérivées
│   └── feature_preprocessor.py    # Imputation + normalisation StandardScaler
├── models/
│   └── xgboost_trainer.py         # Entraînement Optuna + XGBoost
├── saved_models/
│   ├── xgboost_v1.pkl             # Modèle XGBoost sérialisé
│   ├── xgboost_v1_metadata.json   # Métriques (accuracy, F1, confusion matrix)
│   ├── feature_preprocessor.pkl   # Scaler + imputer fitted
│   └── feature_names.json         # Top 30 features sélectionnées
└── predictor/
    └── ml_predictor.py            # Singleton pour prédictions live

api/routes/ml.py                   # Endpoints FastAPI ML
core/postgresql_datalogger.py      # Collecte 46 features par trade

frontend/src/lib/
├── components/ml/
│   ├── MLDashboard.svelte         # Interface principale ML
│   ├── DataQualityCard.svelte     # Qualité données
│   ├── FeatureImportanceCard.svelte
│   └── ModelStatusCard.svelte
└── stores/ml.js                   # Stores Svelte état ML
```

---

## 🔄 Pipeline Complet (Training)

### Étape 1 : Collecte PostgreSQL → DataFrame

**Fichier** : `optimization/data/feature_loader.py`

```python
def load_features_from_postgres(min_trades=50, timeframe_days=30):
    """
    SELECT * FROM ml_features 
    WHERE timestamp_entry >= NOW() - INTERVAL '30 days'
    ORDER BY timestamp_entry DESC
    
    Retourne DataFrame avec:
    - 46 features de base (rsi_1m, macd_hist_1m, adx_1m, etc.)
    - 2 targets (target_win, target_pnl)
    """
```

### Étape 2 : Feature Engineering (46 → 120+ features)

**Fichier** : `optimization/data/feature_engineering.py`

```python
def calculate_derived_features(df):
    """
    Crée 80+ features dérivées:
    - Momentum: momentum_1m, rsi_divergence, macd_momentum_1m
    - Volatility: volatility_ratio, bb_squeeze_1m
    - Trend: trend_strength_1m, strong_trend_1m, ema_aligned
    - Volume: volume_surge, volume_divergence
    - Quality: quality_score_total, high_quality_setup
    - Confluence: bullish_confluence, bearish_confluence
    - Risk: high_volatility_risk, choppy_market
    
    Retourne DataFrame avec 120+ colonnes
    """
```

### Étape 3 : Sélection Top 30 Features

```python
def select_top_features(df, target_col='target_win', n_features=30, method='correlation'):
    """
    Corrélation ou mutual_info pour sélectionner 30 features les plus prédictives
    
    Sauvegarde dans: saved_models/feature_names.json
    """
```

### Étape 4 : Preprocessing (Imputation + Normalisation)

**Fichier** : `optimization/data/feature_preprocessor.py`

```python
class FeaturePreprocessor:
    def __init__(self):
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy='median')
    
    def fit_transform(self, X, feature_names):
        # 1. Imputation médiane pour NaN
        X_imputed = self.imputer.fit_transform(X[feature_names])
        # 2. Normalisation (mean=0, std=1)
        X_scaled = self.scaler.fit_transform(X_imputed)
        return X_scaled
    
    def save(self, path):
        # Sauvegarde dans: saved_models/feature_preprocessor.pkl
```

### Étape 5 : Optimisation Optuna + XGBoost

**Fichier** : `optimization/models/xgboost_trainer.py`

```python
def train_xgboost_with_optuna(X_train, y_train, X_test, y_test, n_trials=50):
    """
    1. Optuna recherche meilleurs hyperparamètres XGBoost:
       - n_estimators, max_depth, learning_rate
       - subsample, colsample_bytree
       - min_child_weight, gamma
       - reg_lambda, reg_alpha
    
    2. Entraîne modèle XGBoost avec meilleurs params
    
    3. Évalue sur test set (accuracy, precision, recall, F1, ROC-AUC)
    
    4. Sauvegarde:
       - saved_models/xgboost_v1.pkl (modèle)
       - saved_models/xgboost_v1_metadata.json (métriques + config)
    
    Retourne: (model, metadata)
    """
```

### Étape 6 : Évaluation & Sauvegarde

```python
metadata = {
    'model_type': 'xgboost',
    'version': 'v1',
    'metrics': {
        'train': {'accuracy': 0.68, 'f1': 0.67, 'roc_auc': 0.72},
        'test': {'accuracy': 0.62, 'precision': 0.61, 'recall': 0.64, 'f1': 0.62, 'roc_auc': 0.66}
    },
    'confusion_matrix': [[TN, FP], [FN, TP]],
    'feature_importance': [{'feature': 'momentum_1m', 'importance': 0.08}, ...],
    'training_info': {
        'total_samples': 150,
        'train_samples': 120,
        'test_samples': 30,
        'timeframe_days': 30,
        'training_time_seconds': 45.2
    }
}
```

---

## 🎯 Pipeline Prédiction Live

**Fichier** : `optimization/predictor/ml_predictor.py`

```python
class MLPredictor:
    """Singleton pour prédictions temps réel"""
    
    def __init__(self):
        self.model = None
        self.preprocessor = None
        self.feature_names = None
        self.loaded = False
    
    def load_model(self, model_path='optimization/saved_models/xgboost_v1.pkl'):
        """
        Charge modèle + preprocessor + feature_names
        """
        self.model = pickle.load(open(model_path, 'rb'))
        self.preprocessor = FeaturePreprocessor.load('optimization/saved_models/feature_preprocessor.pkl')
        self.feature_names = json.load(open('optimization/saved_models/feature_names.json'))
        self.loaded = True
    
    def predict_setup(self, features: Dict[str, float]) -> Dict:
        """
        Prédit probabilité win pour un setup
        
        Args:
            features: Dict avec 46 features de base
                {'rsi_1m': 45.2, 'macd_hist_1m': 0.03, ...}
        
        Returns:
            {
                'prediction': 1,  # 1=win, 0=loss
                'win_probability': 0.67,
                'confidence': 'medium'  # 'low'/'medium'/'high' selon distance à 0.5
            }
        
        Process:
        1. Convertir features dict → DataFrame
        2. calculate_derived_features() → 120+ features
        3. Extraire top 30 features
        4. preprocessor.transform() → normalisation
        5. model.predict_proba() → [prob_loss, prob_win]
        6. Retourner résultat
        """
        if not self.loaded:
            raise RuntimeError("Model not loaded")
        
        # 1. Dict → DataFrame
        df = pd.DataFrame([features])
        
        # 2. Feature engineering
        df_eng = calculate_derived_features(df)
        
        # 3. Extraire top 30
        X = df_eng[self.feature_names]
        
        # 4. Preprocessing
        X_scaled = self.preprocessor.transform(X)
        
        # 5. Prédiction
        proba = self.model.predict_proba(X_scaled)[0]  # [prob_loss, prob_win]
        win_prob = proba[1]
        
        # 6. Déterminer confidence
        if abs(win_prob - 0.5) < 0.1:
            confidence = 'low'
        elif abs(win_prob - 0.5) < 0.2:
            confidence = 'medium'
        else:
            confidence = 'high'
        
        return {
            'prediction': 1 if win_prob > 0.5 else 0,
            'win_probability': float(win_prob),
            'confidence': confidence
        }
```

---

## 📡 API Endpoints

**Fichier** : `api/routes/ml.py`

### GET /api/ml/dashboard/readiness

```python
"""
Vérifie si assez de trades pour chaque modèle
Retourne: {'trades_count': 123, 'xgboost': {'ready': True, ...}, ...}
"""
```

### GET /api/ml/dashboard/data_quality

```python
"""
Analyse qualité données:
- Distribution win/loss
- Valeurs manquantes par feature
- Features à variance nulle
- Score qualité global (0-100)

Retourne: {
    'trades_count': 150,
    'win_loss_distribution': {'wins': 65, 'losses': 85, 'win_rate': 0.43},
    'missing_values': {'high_missing_features': {'rsi_5m': 12.5, ...}},
    'variance': {'low_variance_features': ['const_feature_1', ...]},
    'quality_score': 75,
    'status': 'good'  # 'good'/'acceptable'/'poor'
}
"""
```

### GET /api/ml/features/importance

```python
"""
Top N features + importance

Retourne: {
    'method': 'correlation',
    'trades_count': 150,
    'confidence': 'medium',
    'features': [
        {'rank': 1, 'name': 'momentum_1m', 'importance': 0.12},
        {'rank': 2, 'name': 'rsi_divergence', 'importance': 0.09},
        ...
    ]
}
"""
```

### GET /api/ml/models/status

```python
"""
État modèle actuel

Retourne: {
    'models': {
        'xgboost': {
            'ready': True,
            'trained': True,
            'model_file': 'xgboost_v1.pkl',
            'min_required': 50,
            'confidence': 'medium'
        }
    }
}
"""
```

### GET /api/ml/models/metrics/{model_name}

```python
"""
Métriques détaillées modèle

Retourne: {
    'model_name': 'xgboost_v1',
    'version': 'v1',
    'performance': {
        'train': {'accuracy': 0.68, 'f1': 0.67},
        'test': {'accuracy': 0.62, 'precision': 0.61, 'recall': 0.64, 'f1': 0.62},
        'overfitting_gap': 0.06
    },
    'confusion_matrix': [[TN, FP], [FN, TP]],
    'top_features': [{'feature': 'momentum_1m', 'importance': 12.5}, ...],
    'quality_assessment': {
        'overfitting': 'low',
        'test_performance': 'acceptable',
        'data_sufficiency': 'sufficient'
    },
    'recommendations': [...]
}
"""
```

### POST /api/ml/predict

```python
"""
Prédiction setup unique

Body: {
    'features': {
        'rsi_1m': 45.2,
        'macd_hist_1m': 0.03,
        'adx_1m': 28.5,
        ...  # 46 features de base
    }
}

Retourne: {
    'prediction': 1,
    'win_probability': 0.67,
    'confidence': 'medium',
    'timestamp': '2025-11-16T22:45:00Z'
}
"""
```

### POST /api/ml/predict/batch

```python
"""
Prédiction batch (plusieurs setups)

Body: {
    'features_list': [
        {'rsi_1m': 45.2, ...},
        {'rsi_1m': 52.1, ...},
        ...
    ]
}

Retourne: {
    'predictions': [
        {'prediction': 1, 'win_probability': 0.67, 'confidence': 'medium'},
        {'prediction': 0, 'win_probability': 0.42, 'confidence': 'low'},
        ...
    ]
}
"""
```

### POST /api/ml/retrain

```python
"""
Lance retraining complet

Body: {
    'timeframe_days': 30,
    'n_trials': 50,
    'test_size': 0.2
}

Process:
1. load_features_from_postgres(timeframe_days)
2. calculate_derived_features()
3. select_top_features()
4. FeaturePreprocessor.fit()
5. train_xgboost_with_optuna(n_trials)
6. Sauvegarde model + metadata + preprocessor
7. MLPredictor.reload_model()

Retourne: {
    'status': 'success',
    'model': 'xgboost_v1',
    'metrics': {...},
    'trades_used': 150,
    'training_time_seconds': 45.2
}
"""
```

---

## 🖥️ Frontend ML

### MLDashboard.svelte

Composant principal avec 4 cartes :

1. **ModelStatusCard** : État modèle (chargé/entraîné, version, bouton Réentraîner)
2. **DataQualityCard** : Score qualité (0-100), distribution win/loss, valeurs manquantes
3. **FeatureImportanceCard** : Top 10 features avec importance visuelle (barres)
4. **LivePredictionsCard** : Dernières prédictions en temps réel

### Stores Svelte (ml.js)

```javascript
export const mlReadiness = writable({
    trades_count: 0,
    xgboost: { ready: false, min_required: 50 }
});

export const dataQuality = writable({
    status: 'unknown',
    trades_count: 0,
    quality_score: 0
});

export const featureImportance = writable({
    method: 'correlation',
    features: [],
    confidence: 'low'
});

export const modelsStatus = writable({
    xgboost: { ready: false, trained: false }
});
```

---

## ⚙️ Configuration

### Variables d'Environnement (.env)

```env
# PostgreSQL (requis pour ML)
POSTGRES_ENABLED=true
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trade_cursor_ml
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# ML Settings
ML_MIN_TRADES=50           # Minimum trades pour entraînement
ML_RETRAIN_INTERVAL=7      # Jours entre retrains auto
ML_CONFIDENCE_THRESHOLD=0.65  # Seuil win_prob pour trading
```

### Configuration Training (config.py ou directement dans code)

```python
TRAINING_CONFIG = {
    'timeframe_days': 30,       # Période historique
    'test_size': 0.2,           # 20% pour test set
    'n_features': 30,           # Top N features à garder
    'feature_selection_method': 'correlation',
    'optuna_n_trials': 50,      # Nombre essais Optuna
    'optuna_timeout': 300,      # Timeout Optuna (secondes)
    'random_state': 42
}
```

---

## 📊 Métriques & Monitoring

### Métriques Modèle

- **Accuracy** : % prédictions correctes (train: 68%, test: 62%)
- **Precision** : % vrais wins parmi prédictions win (61%)
- **Recall** : % wins détectés parmi tous les wins (64%)
- **F1-Score** : Moyenne harmonique precision/recall (62%)
- **ROC-AUC** : Aire sous courbe ROC (66%)
- **Overfitting Gap** : train_acc - test_acc (6% = acceptable)

### Monitoring Continu

1. **Dashboard ML** : Vérifier quality_score et trades_count
2. **Feature Importance** : S'assurer que top features restent cohérentes
3. **Model Metrics** : Overfitting gap < 10%, test accuracy > 60%
4. **Data Quality** : < 20% valeurs manquantes, win_rate entre 40-60%

### Quand Relancer Retrain

- Tous les 100-200 nouveaux trades
- Si test accuracy chute < 55%
- Si overfitting gap > 15%
- Si distribution win/loss change drastiquement
- Maximum tous les 7-14 jours

---

## 🔧 Maintenance

### Nettoyage Données

```sql
-- Supprimer trades incomplets ou corrompus
DELETE FROM trades WHERE timestamp_exit IS NULL AND timestamp_entry < NOW() - INTERVAL '7 days';

-- Identifier features avec trop de NaN
SELECT column_name, 
       COUNT(*) FILTER (WHERE column IS NULL) * 100.0 / COUNT(*) as null_pct
FROM ml_features
GROUP BY column_name
HAVING COUNT(*) FILTER (WHERE column IS NULL) * 100.0 / COUNT(*) > 30
ORDER BY null_pct DESC;
```

### Debugging Pipeline

```python
# Tester feature loader
df = load_features_from_postgres(min_trades=10, timeframe_days=30)
print(f"Loaded {len(df)} trades, {len(df.columns)} columns")

# Tester feature engineering
df_eng = calculate_derived_features(df)
print(f"Engineered {len(df_eng.columns)} features")

# Tester preprocessing
top_features = select_top_features(df_eng, n_features=30)
preprocessor = FeaturePreprocessor()
X_scaled = preprocessor.fit_transform(df_eng, top_features)
print(f"Preprocessed shape: {X_scaled.shape}")

# Tester prédiction
predictor = MLPredictor()
predictor.load_model()
result = predictor.predict_setup({'rsi_1m': 45, 'macd_hist_1m': 0.03, ...})
print(result)
```

---

## 📚 Résumé Flux Complets

### Training (Retrain)
