# 🚀 Système ML Complet - Guide d'Utilisation

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Installation et Configuration](#installation-et-configuration)
3. [A - Prédictions Live](#a---prédictions-live)
4. [B - Logging et Tracking](#b---logging-et-tracking)
5. [C - Optimisation du Modèle](#c---optimisation-du-modèle)
6. [D - Système d'Alertes](#d---système-dalertes)
7. [API Reference](#api-reference)
8. [Exemples d'Utilisation](#exemples-dutilisation)

---

## 🎯 Vue d'ensemble

Système ML complet pour trading automatisé avec :
- ✅ **Prédictions en temps réel** sur opportunités scannées
- ✅ **Logging automatique** de toutes les prédictions
- ✅ **Tracking performance** (prédictions vs résultats réels)
- ✅ **Feature selection** automatique (top 30 features)
- ✅ **Optimisation modèle** (réduction overfitting)
- ✅ **Auto-retraining** tous les 100 nouveaux trades
- ✅ **Alertes intelligentes** pour prédictions à haute confiance

---

## 🛠️ Installation et Configuration

### 1. Créer la table predictions_log

```bash
cd "c:\Users\sebta\Documents\clone github\test\test"
psql -h localhost -U postgres -d trade_cursor_ml -f database/create_predictions_log.sql
```

Cette commande crée :
- Table `predictions_log` pour logger toutes les prédictions
- Vues `predictions_analytics`, `predictions_by_symbol`, `recent_predictions`
- Index pour performance

### 2. Redémarrer le serveur

```powershell
# Arrêter le serveur actuel (Ctrl+C)
# Puis relancer
npm run dev
```

### 3. Variables d'environnement (optionnel)

Pour activer les webhooks/alertes :

```env
# Webhook pour alertes ML (Discord, Telegram, etc.)
ML_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Configurer canaux d'alertes
ML_ALERT_CHANNELS=console,webhook
```

---

## A - Prédictions Live

### 🔮 Frontend - Interface Prédictions

1. Ouvre http://localhost:3000
2. Va dans **🤖 Machine Learning**
3. Clique sur l'onglet **🔮 Prédictions Live**
4. Clique sur **🔄 Prédire** pour une prédiction
5. Active **▶️ Auto** pour refresh automatique (10s)

**Ce que tu vois :**
- 🟢 Prédiction WIN/LOSS avec confiance
- Probabilités en barres de progression
- Recommandation intelligente :
  - 🚀 **FORTEMENT RECOMMANDÉ** : Win + confidence ≥ 70%
  - ✅ **RECOMMANDÉ** : Win + confidence ≥ 60%
  - 🚫 **À ÉVITER** : Loss + confidence ≥ 70%
  - ❓ **INCERTAIN** : Confidence < 60%
- Top 3 features influentes
- Performance du modèle

### 📊 API - Prédiction sur opportunité

```bash
# Test avec features d'exemple
python test_predict_api.py
```

Ou directement via API :

```bash
curl -X POST http://localhost:5000/api/ml/predict \
  -H "Content-Type: application/json" \
  -d @features.json
```

### 🔧 Scanner Integration

Le système calcule automatiquement les features depuis les klines du scanner :

```python
from optimization.scanner_ml_integration import get_ml_prediction_for_opportunity

# Dans ton scanner
prediction = await get_ml_prediction_for_opportunity(
    klines=opportunity_klines,
    symbol="BTCUSDT",
    scan_id=123
)

if prediction and prediction['confidence'] > 0.7:
    # Haute confiance, considérer le trade
    print(f"✅ {prediction['prediction']} - {prediction['confidence']:.1%}")
```

---

## B - Logging et Tracking

### 📝 Logging Automatique

**Toutes les prédictions sont automatiquement loggées** dans PostgreSQL avec :
- Métadonnées de prédiction (model, version, confidence)
- Features importantes
- Lien avec opportunité (scan_id, symbol)
- Lien avec trade exécuté (si applicable)
- Résultat réel (après fermeture du trade)

### 📊 Analytics des Prédictions

**Via API :**

```bash
# Analytics globales (30 derniers jours)
curl http://localhost:5000/api/ml/predictions/analytics

# Analytics d'un modèle spécifique
curl "http://localhost:5000/api/ml/predictions/analytics?model_name=xgboost_v1&days=60"

# Prédictions récentes
curl "http://localhost:5000/api/ml/predictions/recent?limit=50"
```

**Réponse analytics :**
```json
{
  "analytics": {
    "total_predictions": 245,
    "evaluated": 180,
    "correct": 115,
    "accuracy_pct": 63.89,
    "avg_confidence_pct": 68.5,
    "trades_executed": 98,
    "avg_pnl_pct": 1.23,
    "high_confidence_wins": 45,
    "high_confidence_correct": 32
  },
  "best_symbols": [
    {
      "symbol": "BTCUSDT",
      "total_predictions": 50,
      "accuracy_pct": 72.0,
      "avg_confidence_pct": 71.2
    }
  ]
}
```

### 📈 Vues SQL Directes

```sql
-- Analytics par modèle
SELECT * FROM predictions_analytics;

-- Performance par symbole
SELECT * FROM predictions_by_symbol ORDER BY accuracy_pct DESC;

-- 50 dernières prédictions
SELECT * FROM recent_predictions;

-- Prédictions à vérifier (trade fermé mais pas encore évalué)
SELECT pl.*, t.win as actual_win
FROM predictions_log pl
JOIN trades t ON pl.trade_id = t.id
WHERE pl.actual_result IS NULL 
AND t.timestamp_exit IS NOT NULL;
```

### 🔄 Mettre à jour résultats

Après fermeture d'un trade :

```python
from optimization.prediction_logger import update_prediction_result

# Automatique si trade_id est lié
update_prediction_result(trade_id=456)
```

---

## C - Optimisation du Modèle

### 🎯 Améliorations Implémentées

1. **Feature Selection** : Garde seulement top 30 features
2. **Réduction overfitting** :
   - `max_depth` : 6 → 4
   - `learning_rate` : 0.1 → 0.05
   - `n_estimators` : 100 → 150
3. **Auto-retraining** tous les 100 nouveaux trades

### 🔄 Ré-entraîner avec Optimisations

**Via API :**

```bash
# Vérifier si ré-entraînement nécessaire
curl http://localhost:5000/api/ml/retrain/check

# Déclencher ré-entraînement si critères remplis
curl -X POST http://localhost:5000/api/ml/retrain

# Forcer ré-entraînement
curl -X POST "http://localhost:5000/api/ml/retrain?force=true"
```

**Via Frontend :**
1. Va dans ML Dashboard → Modèles
2. Clique sur "Ré-entraîner" (bouton apparaît si nécessaire)

**Critères auto-retrain :**
- ≥ 100 nouveaux trades depuis dernier training
- OU ≥ 7 jours depuis dernier training

### 📊 Comparaison Avant/Après

**Avant optimisation :**
- Features : 91 (dont 60 inutiles)
- max_depth : 6
- Overfitting gap : 30.1%
- Test accuracy : 64.3%

**Après optimisation :**
- Features : 30 (sélection automatique)
- max_depth : 4
- Overfitting gap : ~15% (attendu)
- Test accuracy : ~68% (attendu avec plus de données)

---

## D - Système d'Alertes

### 🔔 Alertes Automatiques

**Le système envoie automatiquement des alertes** pour :
- Prédictions WIN avec confiance ≥ 75%
- Sur les canaux configurés

### 📱 Canaux d'Alertes

**Console (par défaut) :**
```
============================================================
🚀 **Alerte ML - WIN**

📈 **Symbole**: BTCUSDT
🎯 **Prédiction**: WIN
💯 **Confiance**: 85.3%
📊 **Probabilité Win**: 85.3%
🤖 **Modèle**: xgboost_v1

📊 Top Features:
  1. bb_distance_to_upper_1m
  2. macd_momentum_5m
  3. rsi_divergence

⏰ **Timestamp**: 2025-11-16 17:30:45
============================================================
```

**Webhook (Discord/Telegram) :**
Configure `ML_ALERT_WEBHOOK_URL` dans `.env` pour recevoir sur Discord/Telegram

**Service de Notifications :**
Intégré automatiquement avec `NotificationService` si disponible

### 🧪 Tester les Alertes

```bash
# Test alerte console
curl -X POST "http://localhost:5000/api/ml/alerts/test?symbol=BTCUSDT&channels=console"

# Test avec webhook (si configuré)
curl -X POST "http://localhost:5000/api/ml/alerts/test?symbol=ETHUSDT&channels=console&channels=webhook"

# Historique des alertes
curl http://localhost:5000/api/ml/alerts/history
```

---

## 📡 API Reference

### Prédictions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/predict` | POST | Prédiction sur une opportunité |
| `/api/ml/predict/batch` | POST | Prédictions en batch |
| `/api/ml/predictions/analytics` | GET | Analytics des prédictions |
| `/api/ml/predictions/recent` | GET | Prédictions récentes |

### Modèles

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/models/status` | GET | Statut de tous les modèles |
| `/api/ml/models/metrics/{name}` | GET | Métriques détaillées d'un modèle |

### Training

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/train` | POST | Entraîner un nouveau modèle |
| `/api/ml/retrain/check` | GET | Vérifier si ré-entraînement nécessaire |
| `/api/ml/retrain` | POST | Déclencher ré-entraînement |

### Alertes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ml/alerts/history` | GET | Historique des alertes |
| `/api/ml/alerts/test` | POST | Tester système d'alertes |

---

## 💡 Exemples d'Utilisation

### Exemple 1 : Workflow Complet

```python
# 1. Scanner trouve une opportunité
opportunity = scanner.scan_pair("BTCUSDT")

# 2. Calculer features et obtenir prédiction
from optimization.scanner_ml_integration import get_ml_prediction_for_opportunity

prediction = await get_ml_prediction_for_opportunity(
    klines=opportunity['klines'],
    symbol="BTCUSDT",
    scan_id=opportunity['scan_id']
)

# 3. Décision basée sur ML
if prediction and prediction['confidence'] >= 0.75:
    if prediction['prediction'] == 'win':
        # ✅ Haute confiance WIN → Exécuter trade
        trade = execute_trade("BTCUSDT", "LONG")
        
        # Lier prédiction au trade
        from optimization.prediction_logger import link_prediction_to_trade
        link_prediction_to_trade(
            prediction_id=prediction['prediction_id'],
            trade_id=trade['id']
        )
        
        # 🔔 Alerte automatiquement envoyée par le système
    else:
        # 🚫 Haute confiance LOSS → Éviter
        print(f"❌ Trade évité grâce au ML")
else:
    # ❓ Confiance insuffisante → Décision manuelle ou skip
    print(f"⚠️ Confiance trop faible: {prediction['confidence']:.1%}")

# 4. Après fermeture du trade (automatique)
# Le système met à jour automatiquement le résultat dans predictions_log
```

### Exemple 2 : Monitoring Performance

```python
from optimization.prediction_logger import get_prediction_analytics, get_best_symbols_for_ml

# Analytics globales
analytics = get_prediction_analytics(model_name="xgboost_v1", days=30)
print(f"Accuracy: {analytics['accuracy_pct']}%")
print(f"PnL moyen: {analytics['avg_pnl_pct']}%")

# Meilleurs symboles
best_symbols = get_best_symbols_for_ml(min_predictions=5)
for symbol in best_symbols[:5]:
    print(f"{symbol['symbol']}: {symbol['accuracy_pct']}% accuracy")
```

### Exemple 3 : Auto-Retrain Scheduler

```python
import asyncio
from optimization.auto_retrain import auto_retrain_if_needed

async def daily_retrain_check():
    """Check quotidien pour auto-retrain"""
    while True:
        result = await auto_retrain_if_needed(
            min_new_trades=100,
            min_days_since_training=7
        )
        
        if result['status'] == 'success':
            print("✅ Modèle ré-entraîné!")
        elif result['status'] == 'skipped':
            print(f"ℹ️ {result['message']}")
        
        # Check toutes les 24h
        await asyncio.sleep(86400)

# Lancer en background
asyncio.create_task(daily_retrain_check())
```

---

## 🎯 Workflow Recommandé

### Phase 1 : Collecte de Données (0-100 trades)
- ✅ Scanner actif
- ✅ Prédictions désactivées (pas assez de données)
- ✅ Focus sur accumulation de trades réels

### Phase 2 : Training Initial (100+ trades)
```bash
curl -X POST "http://localhost:5000/api/ml/train?timeframe_days=90&min_trades=100"
```

### Phase 3 : Prédictions Live (modèle entraîné)
- ✅ Activer prédictions sur scanner
- ✅ Filtrer opportunités selon ML (confidence ≥ 70%)
- ✅ Alertes automatiques activées

### Phase 4 : Optimisation Continue
- ✅ Auto-retrain tous les 100 trades
- ✅ Monitoring analytics quotidien
- ✅ Ajuster seuils de confiance selon performance

---

## 📊 Fichiers Créés/Modifiés

### Nouveaux Fichiers
- `database/create_predictions_log.sql` - Table predictions + vues
- `optimization/predictor.py` - Service de prédiction
- `optimization/prediction_logger.py` - Logging prédictions
- `optimization/scanner_ml_integration.py` - Intégration scanner
- `optimization/auto_retrain.py` - Auto-retraining
- `optimization/ml_alerts.py` - Système d'alertes
- `test_predict_api.py` - Script de test
- `frontend/src/lib/components/ml/LivePredictions.svelte` - Interface prédictions
- `frontend/src/lib/components/ml/ModelMetricsCard.svelte` - Métriques modèle

### Fichiers Modifiés
- `api/routes/ml.py` - Nouveaux endpoints (predict, analytics, retrain, alerts)
- `optimization/models/xgboost_trainer.py` - Feature selection + optimisations
- `frontend/src/lib/components/ml/MLDashboard.svelte` - Intégration prédictions
- `frontend/src/lib/components/ml/MLTabs.svelte` - Onglet prédictions
- `frontend/src/lib/components/ml/ModelsOverview.svelte` - Modal métriques

---

## 🚀 Quick Start

```bash
# 1. Setup database
psql -h localhost -U postgres -d trade_cursor_ml -f database/create_predictions_log.sql

# 2. Restart server
npm run dev

# 3. Test prediction
python test_predict_api.py

# 4. View in browser
# http://localhost:3000 → ML → Prédictions Live
```

---

## 📞 Support

En cas de problème :
1. Vérifier logs serveur backend
2. Vérifier table `predictions_log` existe
3. Vérifier modèle `xgboost_v1.pkl` existe
4. Tester endpoint `/api/ml/models/status`

---

**🎉 Système ML Complet Opérationnel !**
