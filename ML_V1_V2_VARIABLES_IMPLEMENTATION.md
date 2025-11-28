# 🎨 ML V1/V2 dans Variables Panel

**Date** : 24 novembre 2025 - 20h45  
**Status** : ✅ En cours d'implémentation

---

## 📋 OBJECTIF

Créer deux sous-onglets **V1** et **V2** dans la section **Machine Learning** de l'onglet **Variables**.

---

## 🏗️ STRUCTURE ACTUELLE

```
Variables (onglet principal)
├─ Setups & Validation
├─ TP/SL & Position
├─ Machine Learning ← ICI
│  ├─ Filtrage ML
│  ├─ Métriques Modèle
│  ├─ Optimisation Optuna
│  └─ Hyperparamètres XGBoost
└─ Variables en cours
```

---

## 🎯 STRUCTURE CIBLE

```
Variables (onglet principal)
├─ Setups & Validation
├─ TP/SL & Position
├─ Machine Learning
│  ├─ [📊 V1] [🚀 V2] ← NOUVEAUX SÉLECTEURS
│  │
│  ├─ SI V1 :
│  │  ├─ Filtrage ML
│  │  ├─ Métriques Modèle
│  │  ├─ Optimisation Optuna
│  │  └─ Hyperparamètres XGBoost (11 params)
│  │
│  └─ SI V2 :
│     ├─ Informations V2
│     ├─ Paramètres Entraînement
│     ├─ Métriques Modèles V2
│     └─ Diagnostic (F1=0, R²=-0.13)
│
└─ Variables en cours
```

---

## 📝 MODIFICATIONS À FAIRE

### **1. Ajouter variable `mlVersion`**
```javascript
let mlVersion = 'v1'; // 'v1' ou 'v2'
```

### **2. Ajouter sélecteurs V1/V2**
```html
{#if activeSubTab === 'ml'}
  <!-- Sélecteurs V1/V2 -->
  <div class="ml-version-selector">
    <button class:active={mlVersion === 'v1'} on:click={() => mlVersion = 'v1'}>
      📊 XGBoost V1
    </button>
    <button class:active={mlVersion === 'v2'} on:click={() => mlVersion = 'v2'}>
      🚀 XGBoost V2
    </button>
  </div>
  
  <!-- Contenu V1 ou V2 -->
  {#if mlVersion === 'v1'}
    <!-- Contenu ML actuel -->
  {:else if mlVersion === 'v2'}
    <!-- Nouveau contenu V2 -->
  {/if}
{/if}
```

---

## 🎨 CONTENU V1 (Existant)

- ✅ **Filtrage ML** : Toggle + seuil confiance
- ✅ **Métriques** : Test Accuracy, ROC-AUC, Gap, Trades
- ✅ **Optimisation** : Optuna + Apply params
- ✅ **Hyperparamètres** : 11 sliders XGBoost

---

## 🚀 CONTENU V2 (Nouveau)

### **Section 1 : Informations V2**
```html
<section class="variable-section">
  <h3>🚀 XGBoost V2 - Enhanced Pipeline</h3>
  <div class="info-box">
    <p>✅ Split temporel (évite data leakage)</p>
    <p>✅ Class weights automatiques</p>
    <p>✅ Features avancées (110 features)</p>
    <p>✅ Filtrage trades marginaux</p>
    <p>✅ Logger PostgreSQL</p>
  </div>
  
  <div class="warning-box">
    <h4>⚠️ Status Actuel</h4>
    <p>❌ Test Accuracy: 52.5%</p>
    <p>❌ F1 Score: 0.000</p>
    <p>❌ R²: -0.130 (régression)</p>
    <p>
      <strong>Problème</strong> : Aucun signal prédictif dans features
    </p>
    <p>
      <strong>Recommandation</strong> : Voir CONCLUSION_FINALE.md
    </p>
  </div>
</section>
```

### **Section 2 : Paramètres Entraînement**
```html
<section class="variable-section">
  <h3>⚙️ Paramètres Entraînement V2</h3>
  
  <!-- Timeframe Days -->
  <div class="variable-item">
    <label>Timeframe (jours)</label>
    <input type="number" min="30" max="730" value="270" />
  </div>
  
  <!-- Min Trades -->
  <div class="variable-item">
    <label>Min Trades</label>
    <input type="number" min="10" max="500" value="50" />
  </div>
  
  <!-- Max Features -->
  <div class="variable-item">
    <label>Max Features</label>
    <input type="number" min="10" max="100" value="40" />
  </div>
  
  <!-- Marginal Threshold -->
  <div class="variable-item">
    <label>Marginal Threshold (%)</label>
    <input type="number" step="0.05" min="0.10" max="1.00" value="0.20" />
  </div>
  
  <!-- Filter Marginal Trades -->
  <div class="variable-item">
    <label>
      <input type="checkbox" />
      Filtrer trades marginaux
    </label>
  </div>
</section>
```

### **Section 3 : Métriques Modèles V2**
```html
<section class="variable-section">
  <h3>📊 Modèles Entraînés V2</h3>
  
  <div class="models-list">
    <p>Charger depuis <code>/api/ml/models</code></p>
    <table>
      <thead>
        <tr>
          <th>Nom</th>
          <th>Version</th>
          <th>Test Acc</th>
          <th>ROC-AUC</th>
          <th>Gap</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        <!-- Données dynamiques -->
      </tbody>
    </table>
  </div>
</section>
```

### **Section 4 : Liens Documentation**
```html
<section class="variable-section">
  <h3>📖 Documentation</h3>
  
  <div class="doc-links">
    <a href="#" class="doc-link">📄 CONCLUSION_FINALE.md</a>
    <a href="#" class="doc-link">📄 RESUME_1_PAGE.md</a>
    <a href="#" class="doc-link">📄 RAPPORT_FINAL_SESSION.md</a>
    <a href="#" class="doc-link">📄 FRONTEND_ML_V2.md</a>
  </div>
  
  <div class="recommendation-box">
    <h4>💡 Recommandations</h4>
    <ol>
      <li>❌ Arrêter ML sur cette stratégie</li>
      <li>✅ Passer à rule-based system (70% recommandé)</li>
      <li>✅ Ou analyser stratégie approfondie (30%)</li>
    </ol>
  </div>
</section>
```

---

## 🎨 CSS À AJOUTER

```css
/* Sélecteur de version ML */
.ml-version-selector {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 12px;
}

.ml-version-selector button {
  flex: 1;
  padding: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  background: white;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.ml-version-selector button:hover {
  border-color: #667eea;
  transform: translateY(-2px);
}

.ml-version-selector button.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: #667eea;
}

/* Boxes d'information V2 */
.info-box, .warning-box, .recommendation-box {
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.info-box {
  background: #eff6ff;
  border-left: 4px solid #3b82f6;
}

.warning-box {
  background: #fef3c7;
  border-left: 4px solid #f59e0b;
}

.recommendation-box {
  background: #d1fae5;
  border-left: 4px solid #10b981;
}

/* Liste de modèles V2 */
.models-list table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.models-list th,
.models-list td {
  padding: 0.75rem;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}

.models-list th {
  background: #f9fafb;
  font-weight: 600;
}

/* Liens documentation */
.doc-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.doc-link {
  padding: 1rem;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  text-decoration: none;
  color: #667eea;
  font-weight: 600;
  text-align: center;
  transition: all 0.2s;
}

.doc-link:hover {
  border-color: #667eea;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
}
```

---

## ✅ FICHIERS À MODIFIER

1. **`frontend/src/lib/components/VariablesPanel.svelte`**
   - Ajouter `let mlVersion = 'v1';`
   - Modifier section HTML `{#if activeSubTab === 'ml'}`
   - Ajouter sélecteurs V1/V2
   - Dupliquer contenu pour V2
   - Ajouter CSS

---

## 📊 AVANTAGES

- ✅ V1 et V2 séparés visuellement
- ✅ Pas de confusion entre versions
- ✅ V1 garde toute sa fonctionnalité
- ✅ V2 explique status actuel (échec ML)
- ✅ Recommandations visibles dans UI
- ✅ Documentation accessible

---

## 🚀 PROCHAINES ÉTAPES

1. ✅ Créer variable `mlVersion`
2. ⏳ Modifier HTML section ML
3. ⏳ Ajouter contenu V2
4. ⏳ Ajouter CSS
5. ⏳ Tester dans navigateur

---

**📌 Objectif : Interface claire montrant V1 (opérationnel) vs V2 (diagnostic échec)**
