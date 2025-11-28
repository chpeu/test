# 🤖 Module ML - Optimisation Hyperparamètres

Système d'optimisation automatique des hyperparamètres XGBoost avec support **multi-CPU/GPU**.

---

## 📂 Structure

```
ml/
├── hyperparameter_tuning.py   # Module principal Optuna
├── tune.py                     # CLI pour lancer optimisations
└── README.md                   # Ce fichier
```

---

## 🚀 Quick Start

```bash
# Lancer optimisation (50 trials, auto-GPU)
python -m ml.tune optimize --trials 50 --auto-gpu

# Voir meilleurs paramètres
python -m ml.tune show-best

# Appliquer à config
python -m ml.tune apply-best

# Dashboard web
python -m ml.tune dashboard
```

---

## 📊 Fonctionnalités

### ✨ Optimisation intelligente
- **Optuna TPE Sampler**: Optimisation bayésienne (apprend des essais précédents)
- **Pruning automatique**: Arrête les mauvais essais tôt (HyperbandPruner)
- **Validation croisée**: 5-fold stratified pour éviter overfitting
- **Métrique custom trading**: Combine F1, win rate, ROC AUC, recall

### 🚀 Performance
- **Multi-CPU**: Parallélisation automatique (-1 = tous les cores)
- **Support GPU**: CUDA/ROCm (30x plus rapide qu'un seul CPU)
- **Stockage**: PostgreSQL ou SQLite pour persistance

### 🎯 Hyperparamètres optimisés (12)
- `max_depth`, `min_child_weight`
- `reg_alpha`, `reg_lambda`
- `subsample`, `colsample_bytree`, `colsample_bylevel`
- `learning_rate`, `n_estimators`
- `gamma`, `scale_pos_weight`

---

## 📖 Documentation

- **Quick Start**: `../docs/TUNING_QUICKSTART.md`
- **Guide complet**: `../docs/HYPERPARAMETER_TUNING.md`

---

## 🔧 Configuration

### Modifier espace de recherche

Éditer `hyperparameter_tuning.py` → `_suggest_hyperparameters()`:

```python
params = {
    'max_depth': trial.suggest_int('max_depth', 2, 8),  # Changer plage
    'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
}
```

### Changer métrique

```bash
# trading_composite (recommandé pour trading)
python -m ml.tune optimize --metric trading_composite

# f1_score (benchmark ML)
python -m ml.tune optimize --metric f1_score

# accuracy, roc_auc
```

---

## 💻 Commandes CLI

### `optimize`
Lancer nouvelle optimisation

```bash
python -m ml.tune optimize [OPTIONS]

Options:
  --trials INT          Nombre de trials (défaut: 100)
  --timeout INT         Timeout en secondes
  --n-jobs INT          Nombre de CPU (-1 = tous)
  --gpu-id INT          ID du GPU (0, 1, ...)
  --auto-gpu            Détecter GPU automatiquement
  --metric STR          Métrique (trading_composite, f1_score, ...)
  --max-samples INT     Limiter données pour rapidité
  --no-save             Ne pas sauvegarder résultats
```

### `show-best`
Afficher meilleurs paramètres

```bash
python -m ml.tune show-best [--study-name NAME]
```

### `apply-best`
Appliquer à config_overrides.json

```bash
python -m ml.tune apply-best [--config-file PATH]
```

### `history`
Voir historique trials

```bash
python -m ml.tune history [--limit N]
```

### `dashboard`
Lancer dashboard web Optuna

```bash
python -m ml.tune dashboard [--port 8080]
```

---

## 🎯 Métriques

### `trading_composite` (recommandé)

Métrique custom pour trading:

```
score = 0.40 * F1-score +
        0.30 * Win rate +
        0.20 * ROC AUC +
        0.10 * Recall
```

**Pourquoi ?**
- F1: Équilibre precision/recall
- Win rate: Taux de victoires (profit)
- ROC AUC: Capacité discrimination
- Recall: Ne pas manquer des wins

### Autres métriques

- `f1_score`: Standard ML
- `accuracy`: Taux global
- `roc_auc`: Discrimination

---

## ⚡ Performance

### Benchmarks (100 trials)

| Config | Temps |
|--------|-------|
| CPU 1-core | 75 min |
| CPU 8-cores | 20 min |
| GPU RTX 3060 | **5 min** ⚡ |
| GPU RTX 4090 | **2.5 min** ⚡⚡ |

**GPU = 30x plus rapide !**

---

## 🔄 Workflow

1. **Collecte** → 1000+ trades en DB
2. **Optimise** → `python -m ml.tune optimize --trials 50`
3. **Vérifie** → `python -m ml.tune show-best`
4. **Applique** → `python -m ml.tune apply-best`
5. **Réentraîne** → `python -m optimization.train`
6. **Backtest** → Vérifier gains
7. **Déploie** → Production
8. **Répète** → Tous les 7-14 jours

---

## 🐛 Troubleshooting

### "Pas assez de données"
→ Collecte plus de trades (min 1000)

### GPU non détecté
→ `pip install xgboost[gpu]`

### Trials trop lents
→ `--max-samples 5000` ou `--auto-gpu`

---

## 📚 Exemples

### Optimisation rapide (test)
```bash
python -m ml.tune optimize --trials 20 --max-samples 1000
```

### Optimisation standard
```bash
python -m ml.tune optimize --trials 100 --auto-gpu
```

### Optimisation intensive (nuit)
```bash
python -m ml.tune optimize --trials 500 --timeout 28800 --n-jobs -1
```

### Parallélisme multi-GPU
```bash
# Terminal 1
python -m ml.tune optimize --trials 100 --gpu-id 0

# Terminal 2
python -m ml.tune optimize --trials 100 --gpu-id 1
```

---

## 💡 Bonnes pratiques

✅ **DO:**
- Optimise après 1000+ trades
- Utilise GPU si disponible
- Réentraîne après optimisation
- Backtest avant production
- Ré-optimise régulièrement

❌ **DON'T:**
- < 1000 trades (overfitting)
- Oublier de réentraîner
- Déployer sans backtest
- Optimiser trop souvent

---

**Prêt ? Lance ta première optimisation !**

```bash
python -m ml.tune optimize --trials 50 --auto-gpu
```

Pour plus de détails: `../docs/TUNING_QUICKSTART.md`
