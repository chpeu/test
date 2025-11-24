# 🎨 Guide Utilisateur - Optimisation Hyperparamètres Frontend

Guide complet pour utiliser l'optimisation d'hyperparamètres depuis l'interface web.

---

## 🚀 Accès

### Étape 1: Ouvrir l'onglet Machine Learning

1. Lance le bot: `python main.py`
2. Ouvre l'interface web: `http://localhost:3000`
3. Clique sur l'onglet **"Machine Learning"** dans la navigation

### Étape 2: Accéder à l'optimisation

L'onglet **"⚡ Optimisation"** apparaît **seulement si tu as 1000+ trades** en base de données.

**Si onglet verrouillé (🔒):**
- Survole l'onglet pour voir combien de trades manquent
- Lance le bot en mode scan pour collecter plus de données
- L'onglet se déverrouille automatiquement à 1000 trades

---

## 📊 Interface Optimisation

L'interface est divisée en **2 sections**:

### 1️⃣ OptimizationPanel (gauche)
- Configuration de l'optimisation
- Lancement et suivi en temps réel
- Résultats et application des paramètres

### 2️⃣ OptimizationHistory (droite)
- Historique des 20 meilleurs trials
- Classement par score (podium 🥇🥈🥉)
- Détails de chaque trial au clic

---

## ⚙️ Configuration de l'optimisation

### Paramètres disponibles

| Paramètre | Description | Valeur par défaut | Recommandé |
|-----------|-------------|-------------------|------------|
| **Nombre de trials** | Combien d'essais de paramètres | 100 | 50-200 |
| **Métrique** | Objectif à optimiser | Trading Composite | Trading Composite |
| **Timeout** | Durée max (secondes) | Illimité | 3600 (1h) |
| **Limite samples** | Limiter données pour rapidité | Tous | Optionnel |
| **Utiliser GPU** | Accélération GPU (30x plus rapide) | Non | Oui si GPU disponible |

### Métriques disponibles

#### 🎯 **Trading Composite** (Recommandé)
Métrique custom pour trading qui combine:
- 40% F1-score (équilibre precision/recall)
- 30% Win rate (taux de victoires)
- 20% ROC AUC (discrimination)
- 10% Recall (ne pas manquer des wins)

**Quand utiliser:** Pour maximiser profit réel en trading

#### 📊 **F1-Score**
Équilibre entre precision et recall
**Quand utiliser:** Pour benchmark ML standard

#### 📈 **Accuracy**
Taux global de bonnes prédictions
**Quand utiliser:** Si classes bien équilibrées

#### 🎲 **ROC AUC**
Capacité du modèle à discriminer wins/losses
**Quand utiliser:** Pour analyse de discrimination

---

## 🚀 Lancer une optimisation

### Quick Start (recommandé)

1. **Configurer:**
   - Trials: `100`
   - Métrique: `Trading Composite`
   - GPU: ✅ (si disponible)

2. **Cliquer:** `⚡ Lancer optimisation`

3. **Attendre:** 5-20 min selon config

### Configuration rapide (test)

Pour tester le système rapidement:
- Trials: `20`
- Limite samples: `1000`
- Métrique: `Trading Composite`

**Temps estimé:** 2-5 minutes

### Configuration intensive (nuit)

Pour optimisation complète:
- Trials: `500`
- Timeout: `28800` (8h)
- GPU: ✅
- Pas de limite samples

**Temps estimé:** 2-8h

---

## 📈 Suivi en temps réel

Pendant l'optimisation, tu vois:

### Barre de progression
- Pourcentage global d'avancement

### Détails
- **Trial:** X / Y (essai en cours)
- **Progress:** Pourcentage exact
- **Stage:** Étape actuelle (loading_data, optimizing, etc.)

### Meilleur score actuel
- Affiche le meilleur score trouvé jusqu'à présent
- Se met à jour après chaque trial complété

### Exemple d'affichage

```
Progression
━━━━━━━━━━━━━━━━━━━━━━━ 68%

Trial: 68 / 100
Progress: 68%
Stage: trial_68/100

Meilleur score actuel: 62.74%
```

---

## ✅ Résultats de l'optimisation

### Une fois terminé, tu vois:

#### 📊 Statistiques
- **Meilleur score:** Score maximal atteint
- **Trials complétés:** Nombre d'essais terminés
- **Trials pruned:** Essais arrêtés tôt (mauvais)

#### 🎯 Meilleurs hyperparamètres

Liste complète des paramètres optimaux trouvés:
```
max_depth: 3
min_child_weight: 10
reg_alpha: 4.5
reg_lambda: 9.0
subsample: 0.7
colsample_bytree: 0.6
learning_rate: 0.01
n_estimators: 500
...
```

---

## 💾 Appliquer les paramètres

### Méthode 1: Depuis les résultats

1. Optimisation terminée
2. Clic sur `✓ Appliquer ces paramètres`
3. Confirmation affichée
4. **Relancer entraînement** (voir ci-dessous)

### Méthode 2: Depuis meilleurs params actuels

Si tu as déjà des optimisations passées:
1. Section **"📊 Meilleurs paramètres actuels"**
2. Clic sur `✓ Appliquer ces paramètres`
3. Confirmation affichée
4. **Relancer entraînement** (voir ci-dessous)

### ⚠️ Important: Réentraîner le modèle

**Les nouveaux paramètres ne s'appliquent qu'après réentraînement !**

#### Via interface web:
1. Onglet **"🤖 Modèles"**
2. Clic sur `🚀 Entraîner modèle`

#### Via API:
```bash
curl -X POST http://localhost:8000/api/ml/train
```

#### Via CLI:
```bash
python -m optimization.train
```

---

## 📜 Historique des optimisations

### Vue d'ensemble

Section droite affiche **top 20 meilleurs trials** de toutes les optimisations.

### Statistiques globales
- Total trials effectués
- Trials complétés
- Trials pruned
- Meilleur score all-time

### Liste des trials

Chaque trial affiche:
- **Rang:** 🥇 🥈 🥉 ou #4, #5...
- **Numéro du trial**
- **Date et heure**
- **Score obtenu**

#### 🥇 Podium

Les 3 meilleurs trials sont mis en évidence:
- 🥇 **Or:** Meilleur score
- 🥈 **Argent:** 2ème meilleur
- 🥉 **Bronze:** 3ème meilleur

### Voir les détails

**Clic sur un trial** pour voir:
- Tous les hyperparamètres utilisés
- Valeur exacte de chaque paramètre

### Filtrage

Menu déroulant pour choisir combien afficher:
- 10 trials
- 20 trials (défaut)
- 50 trials
- 100 trials

---

## 🔄 Workflow recommandé

### Cycle complet d'optimisation

```
1️⃣ Collecte données (1000+ trades)
   → Lance bot en mode scan

2️⃣ Première optimisation
   → 100 trials, Trading Composite, GPU

3️⃣ Vérifie gains
   → Compare score avec anciennes optimisations

4️⃣ Applique paramètres
   → Clic "Appliquer ces paramètres"

5️⃣ Réentraîne modèle
   → Onglet Modèles → Entraîner

6️⃣ Vérifie performances
   → Onglet Prédictions Live

7️⃣ Backteste (optionnel)
   → Vérifie winrate sur données historiques

8️⃣ Déploie
   → Lance bot avec nouveaux params

9️⃣ Ré-optimise
   → Tous les 7-14 jours ou après 1000+ nouveaux trades
```

---

## 💡 Bonnes pratiques

### ✅ DO

- ✅ **Utilise GPU** si disponible (30x plus rapide)
- ✅ **Commence avec 50-100 trials** pour test
- ✅ **Optimise Trading Composite** pour trading réel
- ✅ **Réentraîne TOUJOURS** après application
- ✅ **Vérifie historique** avant de réoptimiser
- ✅ **Note les gains** pour suivre progression
- ✅ **Ré-optimise régulièrement** (hebdo/bi-hebdo)

### ❌ DON'T

- ❌ **< 1000 trades** → Overfitting garanti
- ❌ **Oublier de réentraîner** → Params non appliqués
- ❌ **Optimiser trop souvent** → Perte de temps
- ❌ **Trials illimités sans timeout** → Peut bloquer des heures
- ❌ **Ignorer l'historique** → Peut dégrader performance
- ❌ **Déployer sans backtest** → Risque de perte

---

## 🐛 Résolution de problèmes

### Onglet verrouillé 🔒

**Problème:** L'onglet Optimisation est grisé avec cadenas

**Cause:** Moins de 1000 trades en base

**Solution:**
1. Survole l'onglet pour voir combien manque
2. Lance bot en mode scan pour collecter
3. Attendre que compteur atteigne 1000

### Erreur "Pas assez de données"

**Message:** `Pas assez de données: X/1000 trades minimum requis`

**Solution:**
- Collecte plus de trades (lance bot quelques jours)
- Minimum absolu: 1000 trades

### GPU non détecté

**Message:** Optimisation lente malgré GPU coché

**Vérification:**
1. Ouvre console navigateur (F12)
2. Regarde logs backend
3. Cherche "🎮 GPU détecté"

**Solutions:**
- Installe drivers CUDA
- Installe XGBoost GPU: `pip install xgboost[gpu]`
- Vérifie: `python -c "import torch; print(torch.cuda.is_available())"`

### Optimisation très lente

**Cause possible:**
- Trop de trials
- Dataset trop grand
- CPU lent

**Solutions:**
- Réduis trials: 50 au lieu de 500
- Limite samples: 5000 dans config
- Active GPU si disponible
- Augmente timeout pour éviter frustration

### Progression bloquée

**Problème:** Barre de progression ne bouge plus

**Solutions:**
1. Attendre 2-3 minutes (trial peut être long)
2. Rafraîchir page (progression reprend)
3. Vérifier logs backend pour erreurs
4. Relancer optimisation si échec

### Erreur application params

**Message:** Erreur lors de `Appliquer ces paramètres`

**Solutions:**
- Vérifie que fichier `config_overrides.json` existe
- Vérifie permissions en écriture
- Regarde logs backend pour détails

---

## 📊 Exemples de gains

### Avant optimisation

```
Hyperparams par défaut:
- max_depth: 4
- learning_rate: 0.02

Résultats:
- F1-score: 58%
- Win rate: 55%
- Trading composite: 57%
```

### Après optimisation (100 trials)

```
Hyperparams optimisés:
- max_depth: 3
- min_child_weight: 10
- learning_rate: 0.01
- reg_alpha: 4.5
- reg_lambda: 9.0

Résultats:
- F1-score: 63% (+8.6%)
- Win rate: 61% (+6 pts)
- Trading composite: 62.7% (+10%)

Impact profit estimé: +15-25%
```

---

## ⚡ Raccourcis clavier

| Touche | Action |
|--------|--------|
| `Échap` | Fermer détails trial |
| `F5` | Rafraîchir historique |

---

## 🎯 Métriques à surveiller

### Pendant optimisation

- **Progress %:** Avancement global
- **Current trial:** Pour estimer temps restant
- **Best score:** Pour voir si amélioration

### Après optimisation

- **Trials completed vs pruned:** Ratio doit être ~70/30
- **Meilleur score:** Doit être > score précédent
- **Amélioration:** Comparer avec historique

---

## 📚 Ressources

- **Guide CLI:** `docs/TUNING_QUICKSTART.md`
- **Guide complet:** `docs/HYPERPARAMETER_TUNING.md`
- **Module code:** `ml/hyperparameter_tuning.py`

---

## ❓ FAQ

**Q: Combien de temps prend une optimisation ?**
- 50 trials CPU: 15-20 min
- 100 trials CPU: 30-40 min
- 100 trials GPU: 5-10 min
- 500 trials GPU: 30-60 min

**Q: Faut-il réoptimiser souvent ?**
- Tous les 7-14 jours
- Ou après 1000+ nouveaux trades
- Pas plus souvent (perte de temps)

**Q: Quelle métrique choisir ?**
- **Trading réel:** Trading Composite
- **Benchmark ML:** F1-Score
- **Analyse:** ROC AUC

**Q: GPU vraiment utile ?**
- OUI ! 30x plus rapide
- 100 trials: 5 min au lieu de 30 min
- Économie temps énorme

**Q: Puis-je interrompre une optimisation ?**
- Non, actuellement pas d'arrêt manuel
- Utilise timeout pour limiter durée
- Ou rafraîchis page (perd progression)

**Q: Les anciennes optimisations sont perdues ?**
- Non, tout est sauvegardé dans base Optuna
- Historique accessible à tout moment
- Peut réappliquer anciens params

---

**Prêt ? Lance ta première optimisation ! 🚀**

1. Ouvre `http://localhost:3000`
2. Onglet **Machine Learning**
3. Onglet **⚡ Optimisation**
4. Configure et lance !
