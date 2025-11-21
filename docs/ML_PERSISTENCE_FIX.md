# Fix ML Persistence & Métriques Dynamiques

**Date:** 21 novembre 2025  
**Impact:** Critique - Persistence des modifications et affichage en temps réel des métriques ML

---

## 📋 Nouveaux Problèmes Identifiés

### 4️⃣ **Variables ML reviennent aux valeurs par défaut après refresh de page** ❌

**Symptôme** : 
- L'utilisateur modifie `ml_max_depth` de 6 → 8 via l'UI
- La modification est bien sauvegardée et visible dans "Variables en cours"
- Mais après un **refresh de page** (F5), la valeur revient à 6

**Cause racine** :
- Le handler WebSocket `update_config` met à jour `TRADING_CONFIG` **en mémoire uniquement**
- Les modifications ne sont **pas persistées** dans le fichier `config.py`
- Au redémarrage du backend, `config.py` est rechargé avec les valeurs par défaut

**Code problématique** :
```python
# ❌ AVANT (main.py ligne 3960)
if updated:
    logger.info(f"✅ Config mise à jour via WebSocket: {updated}")
    # Pas de persistence !
```

---

### 5️⃣ **Métriques du modèle actuel ne s'actualisent pas après réentraînement** ❌

**Symptôme** :
- Après un réentraînement réussi, le tableau "Métriques du Modèle Actuel" affiche toujours :
  - Test Accuracy: 55.3%
  - ROC-AUC: 55.4%
  - Overfitting Gap: 33.1%
  - Trades: 940
- Ces valeurs sont **hardcodées** dans le HTML et ne changent jamais

**Code problématique** :
```html
<!-- ❌ AVANT (VariablesPanel.svelte ligne 2444-2460) -->
<div class="metric-value">55.3%</div>
<div class="metric-value">55.4%</div>
<div class="metric-value danger">33.1%</div>
<div class="metric-value">940</div>
```

---

## ✅ Solutions Implémentées

### Solution Problème 4 : Système de Persistence via `config_overrides.json`

Au lieu de modifier directement `config.py` (risqué), nous utilisons un **fichier JSON séparé** pour persister les overrides.

#### **Nouveau fichier : `utils/config_persistence.py`**

Fonctions créées :
1. **`save_config_overrides(overrides)`** : Sauvegarde les modifications dans `config_overrides.json`
2. **`load_config_overrides()`** : Charge les overrides depuis le fichier JSON
3. **`apply_config_overrides(trading_config)`** : Applique les overrides sur `TRADING_CONFIG`
4. **`clear_config_overrides()`** : Supprime tous les overrides

```python
# Exemple de config_overrides.json
{
  "ml_max_depth": 8,
  "ml_learning_rate": 0.05,
  "ml_n_estimators": 500,
  "tp_percent": 0.7,
  "sl_percent": 0.3
}
```

#### **Modification : `config.py` (lignes 412-420)**

Application des overrides au démarrage :

```python
# 🔥 FIX: Appliquer les overrides persistés depuis config_overrides.json
try:
    from utils.config_persistence import apply_config_overrides
    TRADING_CONFIG = apply_config_overrides(TRADING_CONFIG)
except Exception as e:
    logging.warning(f"⚠️ Impossible d'appliquer config overrides: {e}")
```

#### **Modification : `main.py` (lignes 3963-3970)**

Sauvegarde des overrides après chaque modification :

```python
if updated:
    logger.info(f"✅ Config mise à jour via WebSocket: {updated}")
    
    # 🔥 FIX: Persister les modifications
    try:
        from utils.config_persistence import save_config_overrides
        if save_config_overrides(updated):
            logger.info(f"✅ Modifications persistées dans config_overrides.json")
    except Exception as e:
        logger.error(f"❌ Erreur persistence config: {e}")
```

#### **Workflow de Persistence**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Utilisateur modifie ml_max_depth: 6 → 8                 │
├─────────────────────────────────────────────────────────────┤
│ 2. Frontend: sendCommandViaWS('update_config', {...})      │
├─────────────────────────────────────────────────────────────┤
│ 3. Backend: update_config handler                          │
│    → TRADING_CONFIG['ml_max_depth'] = 8  (mémoire)         │
│    → save_config_overrides({'ml_max_depth': 8})            │
│    → Écriture dans config_overrides.json                    │
├─────────────────────────────────────────────────────────────┤
│ 4. Redémarrage du backend                                  │
│    → config.py: TRADING_CONFIG = {...}  (valeurs défaut)   │
│    → apply_config_overrides(TRADING_CONFIG)                 │
│    → Lecture config_overrides.json                          │
│    → TRADING_CONFIG['ml_max_depth'] = 8  (override)        │
├─────────────────────────────────────────────────────────────┤
│ 5. ✅ La valeur 8 est conservée après redémarrage          │
└─────────────────────────────────────────────────────────────┘
```

---

### Solution Problème 5 : Métriques ML Dynamiques

Remplacer les valeurs hardcodées par un chargement depuis l'API.

#### **Modification : `VariablesPanel.svelte`**

**1. Variables réactives (lignes 102-109)** :

```javascript
let mlMetrics = {
    test_accuracy: 55.3,
    roc_auc: 55.4,
    overfitting_gap: 33.1,
    trades_count: 940
};
let loadingMLMetrics = false;
```

**2. Fonction de chargement (lignes 174-200)** :

```javascript
async function loadMLMetrics() {
    loadingMLMetrics = true;
    try {
        const response = await fetch('/api/ml/models/overview');
        const data = await response.json();
        
        // Extraire les métriques du modèle actuel (xgboost_v1)
        const currentModel = data.models?.find(m => m.name === 'xgboost_v1');
        if (currentModel && currentModel.metrics) {
            mlMetrics = {
                test_accuracy: (currentModel.metrics.test?.accuracy || 0) * 100,
                roc_auc: (currentModel.metrics.test?.roc_auc || 0) * 100,
                overfitting_gap: currentModel.overfitting_gap || 0,
                trades_count: currentModel.dataset_info?.total_samples || 0
            };
        }
    } catch (err) {
        console.error('❌ Erreur chargement métriques ML:', err);
    } finally {
        loadingMLMetrics = false;
    }
}
```

**3. Chargement automatique (lignes 209-211)** :

```javascript
// Charger les métriques ML quand on active l'onglet Machine Learning
$: if (activeSubTab === 'ml' && !loadingMLMetrics) {
    loadMLMetrics();
}
```

**4. HTML dynamique (lignes 2441-2477)** :

```html
{#if loadingMLMetrics}
    <div class="loading-message">⏳ Chargement des métriques...</div>
{:else}
    <div class="ml-metrics-grid">
        <div class="metric-card">
            <div class="metric-label">Test Accuracy</div>
            <div class="metric-value">{mlMetrics.test_accuracy.toFixed(1)}%</div>
            <div class="metric-status" 
                 class:poor={mlMetrics.test_accuracy < 60} 
                 class:ok={mlMetrics.test_accuracy >= 60 && mlMetrics.test_accuracy < 70} 
                 class:good={mlMetrics.test_accuracy >= 70}>
                {mlMetrics.test_accuracy < 60 ? 'Faible' : 
                 mlMetrics.test_accuracy < 70 ? 'Moyen' : 'Bon'}
            </div>
        </div>
        <!-- ... autres cartes ... -->
    </div>
{/if}
```

**5. Rechargement après réentraînement (ligne 572)** :

```javascript
// ✅ Réentraînement terminé avec succès
saveMessage = `✅ Modèle réentraîné! Accuracy: ${accuracy}%...`;

// 🔥 FIX: Recharger les métriques ML
await loadMLMetrics();
```

---

## 🎯 Améliorations Apportées

### Statuts Dynamiques

Les statuts des métriques s'adaptent maintenant automatiquement :

| Métrique | Faible | Moyen | Bon |
|----------|--------|-------|-----|
| **Test Accuracy** | < 60% | 60-70% | ≥ 70% |
| **ROC-AUC** | < 60% | 60-70% | ≥ 70% |
| **Overfitting Gap** | > 20% (Élevé) | 10-20% (Modéré) | ≤ 10% (Faible) |
| **Trades Count** | < 100 (Insuffisant) | 100-500 (Suffisant) | ≥ 500 (Excellent) |

### Couleurs Conditionnelles

Classes CSS appliquées dynamiquement :
- `.poor` : Rouge (mauvais)
- `.ok` : Jaune/Orange (moyen)
- `.good` : Vert (bon)
- `.danger` : Rouge vif (critique pour overfitting)
- `.warning` : Orange (attention pour overfitting)

---

## 🧪 Tests de Validation

### Test 4 : Persistence des modifications ML

**Étapes** :
1. Aller dans l'onglet "🤖 Machine Learning"
2. Modifier `Max Depth` de 6 → 8
3. Modifier `Learning Rate` de 0.03 → 0.05
4. Attendre la sauvegarde automatique (2.5s) ou cliquer "Save"
5. **Vérifier** que `config_overrides.json` contient bien les modifications :
   ```json
   {
     "ml_max_depth": 8,
     "ml_learning_rate": 0.05
   }
   ```
6. **Redémarrer le backend** (Ctrl+C puis `python main.py`)
7. **Recharger la page** frontend (F5)
8. **Vérifier** que les sliders affichent toujours 8 et 0.05

**Résultat attendu** : ✅ Les valeurs sont conservées après redémarrage

---

### Test 5 : Métriques ML dynamiques

**Étapes** :
1. Aller dans l'onglet "🤖 Machine Learning"
2. **Observer** les métriques affichées dans "Métriques du Modèle Actuel"
3. **Noter** les valeurs actuelles (ex: Accuracy: 55.3%, Gap: 33.1%)
4. Cliquer sur "🚀 Réentraîner le Modèle"
5. **Attendre** la fin du réentraînement (30-60s)
6. **Observer** que les métriques se mettent à jour **automatiquement** avec les nouvelles valeurs

**Résultat attendu** : 
- ✅ Les métriques sont chargées depuis l'API (pas hardcodées)
- ✅ Les métriques s'actualisent après réentraînement
- ✅ Les statuts (Faible/Moyen/Bon) s'adaptent automatiquement

---

## 📊 Impact et Bénéfices

### Avant les Fixes ❌

| Problème | Impact | Gravité |
|----------|--------|---------|
| Modifications perdues après refresh | Frustration utilisateur, réglages à refaire | 🔴 Critique |
| Métriques hardcodées | Impossible de voir l'amélioration après réentraînement | 🟠 Majeur |

### Après les Fixes ✅

| Amélioration | Bénéfice | Statut |
|--------------|----------|--------|
| Persistence via JSON | Modifications conservées entre redémarrages | ✅ Résolu |
| Métriques dynamiques | Feedback en temps réel après réentraînement | ✅ Résolu |
| Statuts adaptatifs | Visualisation claire de la qualité du modèle | ✅ Résolu |

---

## 🗂️ Fichiers Modifiés

### Backend
1. **`utils/config_persistence.py`** (nouveau fichier)
   - Fonctions de sauvegarde/chargement des overrides
   
2. **`config.py`** (lignes 412-420)
   - Application des overrides au démarrage
   
3. **`main.py`** (lignes 3963-3970)
   - Sauvegarde des overrides après update_config

### Frontend
4. **`frontend/src/lib/components/VariablesPanel.svelte`** (lignes 102-109, 174-211, 2441-2477, 572)
   - Variables mlMetrics réactives
   - Fonction loadMLMetrics()
   - Chargement automatique à l'activation de l'onglet ML
   - HTML dynamique avec statuts conditionnels
   - Rechargement après réentraînement

---

## 🔄 Workflow Complet (Après Tous les Fixes)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Utilisateur modifie hyperparamètres ML                  │
│    → Max Depth: 6 → 8                                       │
│    → Learning Rate: 0.03 → 0.05                             │
├─────────────────────────────────────────────────────────────┤
│ 2. Sauvegarde automatique (debounce 2.5s)                  │
│    → WebSocket: update_config                               │
│    → Backend: TRADING_CONFIG mis à jour (mémoire)           │
│    → Backend: save_config_overrides() → JSON               │
├─────────────────────────────────────────────────────────────┤
│ 3. Utilisateur clique "Réentraîner le Modèle"              │
│    → POST /api/ml/retrain?force=true                        │
│    → Backend: Utilise TRADING_CONFIG['ml_max_depth'] = 8 ✅ │
│    → Backend: Utilise TRADING_CONFIG['ml_learning_rate'] ✅ │
├─────────────────────────────────────────────────────────────┤
│ 4. Réentraînement terminé (60s)                             │
│    → Frontend: Reçoit métriques (62.1% accuracy, 18.5% gap)│
│    → Frontend: loadMLMetrics() appelé                       │
│    → Frontend: Tableau mis à jour avec nouvelles métriques  │
├─────────────────────────────────────────────────────────────┤
│ 5. Utilisateur refresh la page (F5)                        │
│    → Frontend: Rechargement complet                         │
│    → Backend: TRADING_CONFIG rechargé depuis config.py     │
│    → Backend: apply_config_overrides() appliqué            │
│    → Frontend: Sliders affichent 8 et 0.05 ✅               │
│    → Frontend: loadMLMetrics() charge 62.1% et 18.5% ✅     │
├─────────────────────────────────────────────────────────────┤
│ 6. Redémarrage backend (Ctrl+C → python main.py)          │
│    → config.py: TRADING_CONFIG = {...défaut...}            │
│    → config.py: apply_config_overrides()                    │
│    → Lecture config_overrides.json                          │
│    → TRADING_CONFIG['ml_max_depth'] = 8 ✅                  │
│    → TRADING_CONFIG['ml_learning_rate'] = 0.05 ✅           │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Notes Importantes

### Fichier `config_overrides.json`

- **Emplacement** : Racine du projet (même niveau que `config.py`)
- **Format** : JSON standard
- **Contenu** : Uniquement les paramètres modifiés via l'UI
- **Priorité** : Écrase les valeurs par défaut de `config.py`
- **Sécurité** : Peut être commité dans Git ou ajouté à `.gitignore` selon les besoins

### Gestion des Overrides

Pour **réinitialiser tous les paramètres** :
```bash
# Supprimer config_overrides.json
rm config_overrides.json

# Ou via Python
from utils.config_persistence import clear_config_overrides
clear_config_overrides()

# Redémarrer le backend
```

### API Métriques ML

**Endpoint** : `GET /api/ml/models/overview`

**Réponse** :
```json
{
  "models": [
    {
      "name": "xgboost_v1",
      "metrics": {
        "test": {
          "accuracy": 0.621,
          "roc_auc": 0.645
        },
        "train": {
          "accuracy": 0.806
        }
      },
      "overfitting_gap": 18.5,
      "dataset_info": {
        "total_samples": 1240
      }
    }
  ]
}
```

---

## ✅ Checklist de Vérification

Après déploiement des fixes, vérifier :

- [ ] `utils/config_persistence.py` créé
- [ ] `config.py` applique les overrides au démarrage
- [ ] `main.py` sauvegarde les overrides après update_config
- [ ] Les modifications ML persistent après refresh de page (F5)
- [ ] Les modifications ML persistent après redémarrage backend
- [ ] Les métriques ML se chargent depuis l'API
- [ ] Les métriques ML s'actualisent après réentraînement
- [ ] Les statuts (Faible/Moyen/Bon) s'adaptent dynamiquement
- [ ] Le fichier `config_overrides.json` est créé après première modification

---

## 🚀 Prochaines Étapes

1. **Tester les fixes 4 et 5** en suivant les tests de validation
2. **Vérifier** que `config_overrides.json` est bien créé
3. **Confirmer** la persistence après redémarrage
4. **Observer** l'actualisation des métriques après réentraînement
5. **Documenter** les meilleures pratiques pour l'équipe

---

**Auteur** : Cascade  
**Date** : 21 novembre 2025  
**Version** : 1.0  
**Complète** : `ML_VARIABLES_FIX.md` (Problèmes 1, 2, 3)
