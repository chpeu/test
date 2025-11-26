# 🎨 Frontend ML - Onglets V1 / V2

**Date** : 24 novembre 2025 - 20h35  
**Status** : ✅ Implémenté

---

## ✅ CE QUI A ÉTÉ FAIT

### **Structure Créée**

```
Machine Learning (onglet principal)
│
├─ 📊 XGBoost V1 (sous-onglet)
│  └─ Composant existant (MLDashboard.svelte)
│     - Dashboard
│     - Prédictions Live
│     - Features
│     - Modèles
│     - Exploratoire
│     - Backtesting
│
└─ 🚀 XGBoost V2 (sous-onglet) ⭐ NOUVEAU
   └─ Nouveau composant (MLDashboardV2.svelte)
      - Entraînement
      - Modèles
      - Analyse
```

---

## 📁 FICHIERS CRÉÉS

### **1. MLVersionTabs.svelte** (Nouveau)
**Chemin** : `frontend/src/lib/components/ml/MLVersionTabs.svelte`

**Fonction** : Composant parent qui gère le switch entre V1 et V2

**Features** :
- Boutons de sélection V1/V2 stylisés
- Badge "Legacy" pour V1
- Badge "Nouveau" animé pour V2
- Design moderne avec gradients

---

### **2. MLDashboardV2.svelte** (Nouveau)
**Chemin** : `frontend/src/lib/components/ml/MLDashboardV2.svelte`

**Fonction** : Dashboard complet pour XGBoost V2

**Features** :

#### **Onglet Entraînement** 🎯
- **Paramètres ajustables** :
  - `timeframe_days` (30-730 jours)
  - `min_trades` (10-500)
  - `max_features` (10-100)
  - `marginal_threshold` (0.10-1.00%)
  - `filter_marginal_trades` (checkbox)

- **Lancement entraînement** :
  - Bouton "Lancer Entraînement"
  - Spinner pendant entraînement
  - Logs en temps réel
  - Désactivation des contrôles pendant training

- **Affichage résultats** :
  - Cards métriques colorées :
    - Train Accuracy (violet)
    - Test Accuracy (vert)
    - Gap Overfitting (orange)
    - ROC-AUC (violet foncé)

#### **Onglet Modèles** 🤖
- **Liste des modèles** depuis PostgreSQL (table `ml_models`)
- **Colonnes affichées** :
  - Nom du modèle
  - Version
  - Test Accuracy (badge coloré : vert/orange/rouge)
  - ROC-AUC
  - Gap (badge coloré)
  - Samples
  - Date entraînement
  - Statut (Actif/Inactif)

- **Bouton refresh** pour recharger

#### **Onglet Analyse** 📊
- Section placeholder pour futures analyses
- Feature importance
- Courbes d'apprentissage
- Métriques détaillées

---

### **3. Modifications +page.svelte**
**Fichier** : `frontend/src/routes/+page.svelte`

**Changements** :
```svelte
// AVANT
import MLDashboard from '$lib/components/ml/MLDashboard.svelte';
<MLDashboard />

// APRÈS
import MLVersionTabs from '$lib/components/ml/MLVersionTabs.svelte';
<MLVersionTabs />
```

---

## 🎨 DESIGN

### **Sélecteur de Version**
```
┌─────────────────────────────────────────────┐
│  📊 XGBoost V1    🚀 XGBoost V2            │
│     [Legacy]          [Nouveau]             │
└─────────────────────────────────────────────┘
```

- Boutons larges et stylisés
- Gradient violet sur bouton actif
- Hover effects avec élévation
- Badge "Nouveau" animé pour V2

### **Dashboard V2**
```
┌──────────────────────────────────────────────────┐
│ 🚀 XGBoost V2 - Enhanced ML Pipeline           │
│ Split temporel • Filtrage qualité • Features   │
├──────────────────────────────────────────────────┤
│ [🎯 Entraînement] [🤖 Modèles] [📊 Analyse]     │
├──────────────────────────────────────────────────┤
│                                                  │
│  ⚙️ Paramètres Entraînement                    │
│  ┌─────────────────────────────────────┐       │
│  │ Timeframe: [270] jours              │       │
│  │ Min Trades: [50]                    │       │
│  │ Max Features: [40]                  │       │
│  │ Marginal Threshold: [0.20] %        │       │
│  │ ☑ Filtrer trades marginaux          │       │
│  └─────────────────────────────────────┘       │
│                                                  │
│  [🎯 Lancer Entraînement]                      │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 🔌 API ENDPOINTS UTILISÉS

### **V2 (Nouveaux)**
```
POST /api/ml/train_v2
  Body: {
    timeframe_days: number,
    min_trades: number,
    filter_marginal_trades: boolean,
    marginal_threshold: number,
    max_features: number,
    test_size: number,
    validation_size: number
  }
  Response: {
    train_accuracy, test_accuracy, val_accuracy,
    train_roc_auc, test_roc_auc, val_roc_auc,
    accuracy_gap, roc_auc_gap, ...
  }

GET /api/ml/models
  Response: {
    models: [
      {
        model_name, version, test_accuracy, test_roc_auc,
        accuracy_gap, total_samples, trained_at, is_active, ...
      }
    ]
  }
```

---

## 🚀 UTILISATION

### **Accès**
1. Démarrer backend : `python main.py`
2. Démarrer frontend : `npm run dev` (dans `frontend/`)
3. Aller sur l'onglet "Machine Learning"
4. Cliquer sur "🚀 XGBoost V2"

### **Entraîner un Modèle**
1. Onglet "Entraînement"
2. Ajuster paramètres :
   - **Timeframe** : 270 jours (9 mois) recommandé
   - **Min Trades** : 50 recommandé
   - **Max Features** : 40 recommandé
   - **Marginal Threshold** : 0.20% recommandé
   - **Filtrer marginaux** : Décoché (filtrage manuel dans script)

3. Cliquer "🎯 Lancer Entraînement"
4. Observer logs en temps réel
5. Voir résultats dans cards métriques

### **Voir les Modèles**
1. Onglet "Modèles"
2. Table avec tous les modèles entraînés
3. Badges colorés pour métriques :
   - **Vert** : Bon (Accuracy >= 65%, Gap < 15%)
   - **Orange** : Moyen
   - **Rouge** : Mauvais

---

## ⚠️ NOTES IMPORTANTES

### **V1 vs V2**
| Aspect | V1 (Legacy) | V2 (Nouveau) |
|--------|-------------|--------------|
| **Split** | Random | Temporel ✅ |
| **Class Weights** | Manuel | Automatique ✅ |
| **Features** | ~80 | ~110 (base + avancées) ✅ |
| **Filtrage** | Basique | Marginal trades ✅ |
| **Logger** | Fichier | PostgreSQL ✅ |
| **Métriques** | Train/Test | Train/Val/Test + Gaps ✅ |

### **Compatibilité**
- V1 et V2 sont **indépendants**
- Modèles V1 et V2 stockés **séparément**
- **Pas de conflit** entre les deux versions
- Possibilité d'utiliser les deux en parallèle

### **Performance Actuelle**
**Selon les tests** :
```
Classification : Test Acc 52.5%, F1=0.000 ❌
Régression     : R²=-0.130, MAE=0.29%   ❌

Problème identifié : Aucun signal prédictif dans features
Recommandation   : Rule-based system ou analyse stratégie
```

---

## 📊 PROCHAINES AMÉLIORATIONS POSSIBLES

### **Frontend V2**
1. ✅ Sélecteur V1/V2 (FAIT)
2. ✅ Dashboard entraînement (FAIT)
3. ✅ Liste modèles (FAIT)
4. ⏳ Graphiques métriques (confusion matrix, courbes ROC)
5. ⏳ Feature importance interactive
6. ⏳ Comparaison modèles côte-à-côte
7. ⏳ Export modèles/métriques
8. ⏳ Prédictions live V2

### **Backend V2**
1. ✅ Endpoint `/api/ml/train_v2` (FAIT)
2. ✅ Table `ml_models` PostgreSQL (FAIT)
3. ✅ Logger PostgreSQL (FAIT)
4. ⏳ Endpoint `/api/ml/predict_v2`
5. ⏳ Endpoint `/api/ml/compare_models`
6. ⏳ WebSocket pour progress en temps réel

---

## 🔧 TROUBLESHOOTING

### **Problème : V2 n'apparaît pas**
**Solution** : Refresh page (Ctrl+R)

### **Problème : Erreur "Cannot fetch models"**
**Solution** : Vérifier que backend est démarré et PostgreSQL accessible

### **Problème : Entraînement ne démarre pas**
**Solution** :
1. Vérifier logs backend
2. Vérifier que table `ml_models` existe
3. Vérifier que données suffisantes dans PostgreSQL

### **Problème : Métriques toutes à 0**
**Solution** : Cela indique que le modèle n'apprend pas (voir CONCLUSION_FINALE.md)

---

## 📖 DOCUMENTATION LIÉE

| Fichier | Contenu |
|---------|---------|
| `CONCLUSION_FINALE.md` | Diagnostic complet échec ML |
| `RESUME_1_PAGE.md` | Résumé rapide session |
| `RAPPORT_FINAL_SESSION.md` | Analyse technique détaillée |
| `README_DEPLOIEMENT.md` | Guide déploiement infrastructure |

---

## ✅ RÉSUMÉ

**Créé** :
- ✅ MLVersionTabs.svelte (sélecteur V1/V2)
- ✅ MLDashboardV2.svelte (dashboard complet V2)
- ✅ 3 onglets V2 : Entraînement, Modèles, Analyse

**Modifié** :
- ✅ +page.svelte (utilise MLVersionTabs)

**Fonctionnalités** :
- ✅ Entraînement XGBoost V2 depuis UI
- ✅ Affichage métriques Train/Val/Test + Gaps
- ✅ Liste modèles depuis PostgreSQL
- ✅ Badges colorés pour métriques
- ✅ Design moderne avec gradients

**Status** :
- ✅ Infrastructure UI prête
- ⚠️ Modèle ML non viable (voir CONCLUSION_FINALE.md)
- 💡 UI peut être réutilisée pour autres stratégies

---

**🎨 Frontend V1/V2 opérationnel - Prêt à utiliser**

**📖 Voir CONCLUSION_FINALE.md pour décision ML**
