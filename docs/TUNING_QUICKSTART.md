# ⚡ Quick Start: Optimisation Hyperparamètres

Guide rapide pour lancer ta première optimisation d'hyperparamètres ML.

---

## 🚀 Installation (1 minute)

```bash
# Installer nouvelle dépendance
pip install optuna-dashboard

# Vérifier que tout fonctionne
python -m ml.tune --help
```

---

## 🎯 Première optimisation (5 minutes)

### Étape 1: Vérifier les données

Assure-toi d'avoir **au moins 1000 trades** en base de données:

```bash
# Via Python
python -c "from optimization.data.feature_loader import get_trades_count; print(f'{get_trades_count()} trades disponibles')"
```

**Si < 1000 trades:** Lance le bot en mode scan pendant quelques jours pour collecter plus de données.

### Étape 2: Lancer optimisation rapide (CPU)

```bash
# 50 trials, tous les CPU, ~15-20 minutes
python -m ml.tune optimize --trials 50
```

**Output attendu:**
```
[10:30:15] INFO - Demarrage optimisation hyperparametres...
[10:30:15] INFO - Dataset: 2847 samples, 30 features
[10:30:15] INFO - Distribution: 1623 wins (57.0%), 1224 losses
[10:30:18] INFO - [Trial 1/50] trading_composite=0.5821 | max_depth=4, lr=0.0120
[10:30:21] INFO - Trial 1/50 complete | Best score: 0.5821
...
[10:45:32] INFO - OPTIMISATION TERMINEE EN 15.3 minutes
[10:45:32] INFO - MEILLEURS HYPERPARAMETRES:
[10:45:32] INFO -   - max_depth: 3
[10:45:32] INFO -   - min_child_weight: 10
[10:45:32] INFO -   - learning_rate: 0.01
[10:45:32] INFO - Best trading_composite: 0.6274
[10:45:32] INFO - Meilleurs parametres sauvegardes dans config_overrides.json
```

### Étape 3: Voir les résultats

```bash
# Afficher meilleurs params trouvés
python -m ml.tune show-best
```

### Étape 4: Réentraîner le modèle

**IMPORTANT:** Les nouveaux hyperparamètres ne s'appliquent qu'après réentraînement !

```bash
# Réentraîner avec nouveaux params
python -m optimization.train

# Ou via API si bot en cours
curl -X POST http://localhost:8000/api/ml/train
```

### Étape 5: Vérifier les gains

Compare les métriques avant/après dans le dashboard ML.

---

## 🎮 Optimisation GPU (plus rapide)

Si tu as un **GPU NVIDIA** (RTX 2060+, 3060+, 4060+):

```bash
# Auto-détection GPU
python -m ml.tune optimize --trials 100 --auto-gpu

# Ou spécifier GPU manuellement
python -m ml.tune optimize --trials 100 --gpu-id 0
```

**Gains de vitesse:**
- CPU 1-core: ~45s/trial
- CPU 8-cores: ~12s/trial
- **GPU RTX 3060: ~3s/trial** ⚡ (15x plus rapide)
- **GPU RTX 4090: ~1.5s/trial** ⚡⚡ (30x plus rapide)

---

## 📊 Commandes utiles

```bash
# Voir historique (top 20 meilleurs trials)
python -m ml.tune history --limit 20

# Dashboard web interactif
python -m ml.tune dashboard
# Accès: http://localhost:8080

# Appliquer meilleurs params sans réoptimiser
python -m ml.tune apply-best
```

---

## ⚙️ Options avancées

### Optimisation intensive (nuit/weekend)

```bash
# 500 trials, timeout 12h, tous les CPU
python -m ml.tune optimize \
    --trials 500 \
    --timeout 43200 \
    --n-jobs -1
```

### Optimisation rapide (test)

```bash
# 20 trials, limitation 1000 samples
python -m ml.tune optimize \
    --trials 20 \
    --max-samples 1000
```

### Optimiser métrique spécifique

```bash
# Optimiser F1-score uniquement
python -m ml.tune optimize --trials 100 --metric f1_score

# Autres métriques: accuracy, roc_auc, trading_composite
```

---

## 🔧 Troubleshooting

### Erreur: "Pas assez de données"

```
ValueError: Pas assez de données: 234 < 1000
```

**Solution:** Collecte plus de trades ou réduis le minimum dans le code.

### GPU non détecté

```
Pas de GPU détecté, utilisation CPU multi-core
```

**Solutions:**
1. Vérifier CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
2. Installer XGBoost GPU: `pip install xgboost[gpu]`
3. Forcer GPU: `--gpu-id 0`

### Trials très lents

**Cause:** Dataset trop grand ou CPU lent.

**Solutions:**
- Limiter données: `--max-samples 5000`
- Utiliser GPU: `--auto-gpu`
- Réduire trials: `--trials 20` pour test

---

## 📈 Workflow recommandé

```
1️⃣ Collecte données (1000+ trades)
   → Lance bot en mode scan

2️⃣ Optimisation initiale
   → python -m ml.tune optimize --trials 50

3️⃣ Vérifier gains
   → python -m ml.tune show-best

4️⃣ Réentraîner
   → python -m optimization.train

5️⃣ Backtester
   → Vérifier performance en backtest

6️⃣ Déployer
   → Lance bot avec nouveaux params

7️⃣ Ré-optimiser tous les 7-14 jours
```

---

## 💡 Bonnes pratiques

✅ **DO:**
- Lance optimisations après 1000+ nouveaux trades
- Utilise GPU si disponible (30x plus rapide)
- Réentraîne le modèle après optimisation
- Vérifie gains en backtest avant production
- Ré-optimise régulièrement (hebdo/bi-hebdo)

❌ **DON'T:**
- N'optimise pas sur < 1000 trades (overfitting)
- N'oublie pas de réentraîner après optimisation
- Ne déploie pas sans backtest préalable
- N'optimise pas trop souvent (< 7 jours)

---

## 📚 Documentation complète

Pour aller plus loin: `docs/HYPERPARAMETER_TUNING.md`

---

**Prêt ? Lance ta première optimisation !**

```bash
python -m ml.tune optimize --trials 50 --auto-gpu
```
