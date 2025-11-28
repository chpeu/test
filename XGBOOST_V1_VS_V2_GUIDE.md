# 🎯 Guide Complet : XGBoost V1 vs V2

## 📋 Vue d'ensemble

Votre application dispose maintenant de **deux systèmes ML parallèles** pour prédire la performance des trades :

- **XGBoost V1** : Prédiction binaire WIN/LOSS (Classification)
- **XGBoost V2** : Prédiction du PNL% exact (Régression)

---

## 🔄 Différences Fondamentales

### **XGBoost V1 - Classification Binaire**

#### **Objectif**
Prédire si un trade sera **gagnant** (WIN) ou **perdant** (LOSS).

#### **Type de problème**
- **Classification binaire** : 2 classes (0 = Loss, 1 = Win)
- Utilise `XGBClassifier` de XGBoost
- Objective : `binary:logistic`

#### **Target (Variable cible)**
```python
target_win = 1 si PNL > 0, sinon 0
```
→ Variable binaire (0 ou 1)

#### **Split des données**
- **Split stratifié aléatoire** (`train_test_split` de sklearn)
- Garantit la même distribution Win/Loss dans train et test
- Test size : 20% par défaut
- Pas de validation set séparé

#### **Métriques d'évaluation**

##### **1. Accuracy (Précision)**
```
Accuracy = (Vrais Positifs + Vrais Négatifs) / Total
```
- Mesure le % de prédictions correctes
- **Exemple** : 65% accuracy = le modèle prédit correctement 65% des trades
- ⚠️ Peut être trompeur si classes déséquilibrées (ex: 90% WIN → modèle naïf à 90%)

##### **2. F1 Score**
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```
- **Precision** : % de trades prédits WIN qui sont vraiment WIN
- **Recall** : % de vrais WIN qui sont détectés
- **Balance** entre précision et rappel
- **Exemple** : F1 = 0.70 → bon équilibre précision/rappel
- ⚠️ Idéal pour classes déséquilibrées

##### **3. AUC-ROC (Area Under Curve)**
- Mesure la capacité du modèle à séparer WIN et LOSS
- **Valeurs** : 0.5 (random) à 1.0 (parfait)
- **Exemple** : AUC = 0.75 → le modèle classe correctement 75% du temps
- ✅ Indépendant du seuil de décision

#### **Output du modèle**
```python
prediction = model.predict(X)  # [0, 1, 1, 0, ...]
probabilities = model.predict_proba(X)  # [[0.3, 0.7], [0.8, 0.2], ...]
```
- **predict()** : Classe binaire (0 ou 1)
- **predict_proba()** : Probabilités [P(Loss), P(Win)]

#### **Usage en production**
```python
if ml_v1_filter_enabled:
    prob_win = model.predict_proba(features)[0][1]  # Proba WIN
    if prob_win < ml_v1_min_confidence:  # Ex: 0.60 (60%)
        reject_trade("Proba WIN trop faible")
```

---

### **XGBoost V2 - Régression PNL%**

#### **Objectif**
Prédire le **PNL% exact** d'un trade (ex: +2.5%, -0.8%).

#### **Type de problème**
- **Régression continue** : Valeur numérique continue
- Utilise `XGBRegressor` de XGBoost
- Objective : `reg:squarederror` (minimize MSE)

#### **Target (Variable cible)**
```python
target_pnl = (exit_price - entry_price) / entry_price * 100
```
→ Valeur continue (ex: -5.23%, +3.14%)

#### **Split des données**

##### **Split temporel (CRITIQUE pour trading)**
```
├── Train set (70%) : Données les plus anciennes
├── Validation set (10%) : Données intermédiaires
└── Test set (20%) : Données les plus récentes
```
- **Pourquoi ?** Reproduit la réalité : on prédit le futur avec le passé
- **Risque split aléatoire** : Data leakage (futur → passé) = fausses métriques
- Utilise `temporal_train_test_split()` sur colonne `timestamp`

##### **Filtrage qualité**
- Exclut les trades **marginaux** (|PNL| < 0.20% par défaut)
- **Pourquoi ?** Ces trades sont du **bruit** (spreads, slippage) et polluent l'apprentissage
- Exemple : 1000 trades → 700 après filtrage (30% noise)

#### **Métriques d'évaluation**

##### **1. R² Score (Coefficient de détermination)**
```
R² = 1 - (SS_res / SS_tot)
```
- **SS_res** : Somme des erreurs au carré du modèle
- **SS_tot** : Somme des erreurs au carré du modèle naïf (moyenne)

**Interprétation :**
- **R² = 1.0** : Prédictions parfaites
- **R² = 0.0** : Modèle = moyenne (inutile)
- **R² < 0.0** : Modèle pire que la moyenne (très mauvais)

**Exemple :**
- **R² = 0.25** → Le modèle explique **25% de la variance** du PNL%
- Signifie : Le modèle est 25% meilleur qu'un modèle naïf qui prédit toujours la moyenne
- ⚠️ Pour le trading, **R² > 0.20** est déjà très bon (marchés chaotiques)

##### **2. MAE (Mean Absolute Error)**
```
MAE = moyenne(|y_vrai - y_prédit|)
```
**Exemple :**
- **MAE = 0.30%** → En moyenne, les prédictions sont **décalées de ±0.30%**
- Si le modèle prédit +2.0% et le vrai PNL est +2.5% → erreur = 0.5%
- Si le modèle prédit -1.0% et le vrai PNL est -0.5% → erreur = 0.5%

**Pourquoi MAE et pas MSE ?**
- MAE est plus **robuste aux outliers** (gros trades exceptionnels)
- MAE a la **même unité** que la target (% dans notre cas)

##### **3. F1 Score (pour classification secondaire)**
Même si V2 est une régression, on calcule aussi un **F1 score** en convertissant en classification :
```python
threshold = 0.0  # Seuil PNL%
y_test_class = (y_test > threshold).astype(int)  # 1 si PNL > 0%, sinon 0
y_pred_class = (y_pred > threshold).astype(int)
f1 = f1_score(y_test_class, y_pred_class)
```
- Permet de comparer avec V1
- **Exemple** : F1 = 0.65 → le modèle détecte correctement 65% des trades positifs

#### **Output du modèle**
```python
prediction = model.predict(X)  # [+2.34, -0.78, +1.12, ...]
```
- **Valeur continue** : PNL% prédit pour chaque trade

#### **Usage en production**
```python
if ml_v2_filter_enabled:
    predicted_pnl = model.predict(features)[0]  # Ex: +1.5%
    if predicted_pnl < ml_v2_min_expected_pnl:  # Ex: +0.5%
        reject_trade("PNL prédit trop faible")
```

---

## 📊 Comparaison des Architectures

| Aspect | XGBoost V1 | XGBoost V2 |
|--------|------------|------------|
| **Type** | Classification binaire | Régression continue |
| **Classe XGBoost** | `XGBClassifier` | `XGBRegressor` |
| **Objective** | `binary:logistic` | `reg:squarederror` |
| **Target** | `target_win` (0/1) | `target_pnl` (-5.0% à +10.0%) |
| **Split** | Stratifié aléatoire | **Temporel** (critique!) |
| **Filtrage** | Aucun | Exclut trades marginaux |
| **Validation set** | Non (juste train/test) | Oui (train/val/test) |
| **Métrique principale** | F1 Score / AUC | **R² Score / MAE** |
| **Output** | Probabilité WIN | PNL% exact |
| **Use case** | "Ce trade va-t-il gagner?" | "Quel profit vais-je faire?" |

---

## 🎛️ Hyperparamètres Expliqués

### **Paramètres Communs V1 et V2**

#### **n_estimators** (Nombre d'arbres)
- **Définition** : Nombre d'arbres de décision dans l'ensemble
- **Impact** : Plus d'arbres = meilleure précision mais plus lent
- **Valeurs typiques** : 300-600
- **V1** : 300 (default), **V2** : 450-600 (optimisé)

#### **max_depth** (Profondeur max)
- **Définition** : Profondeur maximale de chaque arbre
- **Impact** : Profondeur élevée = overfitting, profondeur faible = underfitting
- **Valeurs typiques** : 3-6
- **V1** : 6, **V2** : 4-5 (plus conservateur)

#### **learning_rate** (Taux d'apprentissage)
- **Définition** : Facteur de réduction de chaque arbre (shrinkage)
- **Impact** : Plus faible = apprentissage lent mais plus stable
- **Valeurs typiques** : 0.01-0.1
- **V1** : 0.03, **V2** : 0.03-0.05

#### **min_child_weight**
- **Définition** : Poids minimum requis pour créer une feuille
- **Impact** : Plus élevé = moins d'overfitting (généralisation)
- **Valeurs typiques** : 1-10
- **V1** : 3, **V2** : 3-5

#### **reg_alpha** (Régularisation L1)
- **Définition** : Régularisation Lasso sur les poids des feuilles
- **Impact** : Pousse certains poids vers 0 (sélection features)
- **Valeurs typiques** : 0.0-5.0
- **V1** : 0.5, **V2** : 0.5-1.0

#### **reg_lambda** (Régularisation L2)
- **Définition** : Régularisation Ridge sur les poids des feuilles
- **Impact** : Pénalise les poids élevés (lisse le modèle)
- **Valeurs typiques** : 1.0-5.0
- **V1** : 2.0, **V2** : 2.0-3.0

#### **subsample** (Sous-échantillonnage lignes)
- **Définition** : Fraction des données utilisée pour chaque arbre
- **Impact** : Prévient overfitting (bagging)
- **Valeurs typiques** : 0.6-0.9
- **V1** : 0.8, **V2** : 0.7

#### **colsample_bytree** (Sous-échantillonnage colonnes par arbre)
- **Définition** : Fraction des features utilisée pour chaque arbre
- **Impact** : Diversifie les arbres (random forest-like)
- **Valeurs typiques** : 0.6-0.9
- **V1** : 0.8, **V2** : 0.7

#### **gamma** (Min split gain)
- **Définition** : Gain minimum requis pour créer un nouveau split
- **Impact** : Plus élevé = moins de splits = moins d'overfitting
- **Valeurs typiques** : 0.0-1.0
- **V1** : 0.1, **V2** : 0.3-0.5

### **Paramètres Spécifiques V1**

#### **scale_pos_weight**
- **Définition** : Poids de la classe positive (WIN) vs négative (LOSS)
- **Impact** : Compense le déséquilibre de classes
- **Calcul** : `count(LOSS) / count(WIN)`
- **Exemple** : Si 60% WIN et 40% LOSS → scale_pos_weight = 0.67

### **Paramètres Spécifiques V2**

#### **timeframe_days**
- **Définition** : Fenêtre temporelle des données d'entraînement
- **Impact** : Plus long = plus de données mais risque de staleness
- **Valeurs** : 180-365 jours

#### **filter_marginal_trades**
- **Définition** : Exclure les trades avec |PNL| faible
- **Impact** : Améliore signal/noise ratio
- **Seuil** : `marginal_threshold` (0.15%-0.25%)

#### **max_features**
- **Définition** : Nombre max de features après sélection
- **Impact** : Réduit overfitting et accélère training
- **V1** : 50, **V2** : 30-40 (plus sélectif)

---

## 🔧 Workflow Complet

### **XGBoost V1**

```
1. Charger trades (timeframe_days, min_trades)
2. Feature engineering (81 features dérivées)
3. Split stratifié aléatoire (80% train / 20% test)
4. Feature selection (top 50 features par importance)
5. Train XGBClassifier avec early stopping
6. Évaluation : Accuracy, F1, Precision, Recall, AUC
7. Sauvegarde modèle + preprocessor
8. Rechargement predictor en production
```

### **XGBoost V2**

```
1. Charger trades (timeframe_days, min_trades)
2. Feature engineering (81 features dérivées)
3. Filtrer trades marginaux (|PNL| < marginal_threshold)
4. Split TEMPOREL (70% train / 10% val / 20% test)
5. Feature selection (top 30 features par mutual information)
6. Preprocessing (RobustScaler)
7. Train XGBRegressor avec early stopping sur validation
8. Évaluation : R², MAE, F1 (classification secondaire)
9. Sauvegarde modèle (TODO: PostgreSQL ml_models table)
```

---

## 📈 Interprétation des Métriques

### **Résultats V1 (Classification)**

```
✅ Entraînement terminé
📊 Test Metrics:
   - Accuracy: 0.673 (67.3%)
   - F1 Score: 0.698
   - Precision: 0.712
   - Recall: 0.685
   - AUC-ROC: 0.741
```

**Interprétation :**
- **67.3% des prédictions sont correctes**
- **F1 = 0.698** → Bon équilibre précision/rappel
- **AUC = 0.741** → Le modèle sépare bien WIN et LOSS (74.1% du temps)
- **Conclusion** : Modèle décent mais perfectible

### **Résultats V2 (Régression)**

```
✅ Entraînement terminé
📊 Test Metrics:
   - R² Test: 0.266
   - MAE Test: 0.291%
   - F1 Score: 0.634
   - Accuracy: 0.622
```

**Interprétation :**

#### **R² = 0.266**
- Le modèle explique **26.6% de la variance** du PNL%
- **C'est très respectable pour du trading !** (marchés chaotiques)
- Le modèle est 26.6% meilleur qu'un modèle naïf qui prédit toujours la moyenne
- **Si R² > 0.20** dans le trading, c'est exploitable

#### **MAE = 0.291%**
- Erreur moyenne de **±0.29%** sur les prédictions
- Si le vrai PNL est +2.0%, le modèle prédit entre +1.71% et +2.29% (en moyenne)
- **Contexte** : Les trades ont typiquement des PNL entre -5% et +10%
- **0.29% d'erreur est acceptable** pour ce range

#### **F1 = 0.634**
- En convertissant en classification (PNL > 0%), le F1 est de 63.4%
- **Plus faible que V1** (69.8%) car la régression est plus difficile
- Mais donne une **information quantitative** (combien) en plus du binaire (gagner/perdre)

#### **Accuracy = 0.622**
- 62.2% des prédictions de signe sont correctes (positif/négatif)
- Comparable à V1 mais avec bonus de prédire l'amplitude

**Conclusion :**
- **V2 est plus informatif** : il prédit non seulement si le trade gagne, mais **combien**
- **Les métriques absolues sont plus faibles** (R² vs AUC) car problème plus difficile
- **Mais la valeur business est supérieure** : filtrer les trades avec PNL faible prédit

---

## 🚀 Utilisation en Production

### **Activation Filtrage V1**

```
Machine Learning → XGBoost V1 → Variables en cours
├── Activer Filtrage ML V1 : ✅
└── Seuil Confiance Minimum : 65%
```
→ Bloque les trades avec `P(WIN) < 0.65`

### **Activation Filtrage V2**

```
Machine Learning → XGBoost V2 → Variables en cours
├── Activer Filtrage ML V2 : ✅
└── Seuil R² Minimum : 60%
```
→ Bloque les trades avec prédiction PNL% trop faible

### **Combinaison V1 + V2 (Recommandé)**

```python
# Les deux filtres peuvent coexister !
if ml_v1_filter_enabled:
    if prob_win < ml_v1_min_confidence:
        reject("Proba WIN insuffisante")

if ml_v2_filter_enabled:
    if predicted_pnl < ml_v2_min_expected_pnl:
        reject("PNL prédit insuffisant")

# Si les deux passent → Trade validé
execute_trade()
```

**Avantage :** Couches de validation complémentaires
- **V1** : Évite les trades perdants
- **V2** : Évite les trades marginaux (même gagnants mais trop faibles)

---

## 🔄 Cycle d'Optimisation

### **V1 : Optuna sur métriques de classification**

```
Machine Learning → XGBoost V1 → Optimisation
1. Lancer optimisation (100 trials)
2. Optuna teste différentes combinaisons de hyperparams
3. Métrique objectif : F1 score (ou trading_composite)
4. Appliquer meilleurs params
5. Réentraîner modèle
```

### **V2 : Optuna sur métriques de régression**

```
Machine Learning → XGBoost V2 → Optimisation
1. Lancer optimisation (100 trials)
2. Optuna teste différentes combinaisons de hyperparams
3. Métrique objectif : R² score (à MAXIMISER)
4. Appliquer meilleurs params
5. Réentraîner modèle
```

**Note :** V2 optimise pour **maximiser R²**, pas minimiser MAE (même si les deux sont liés)

---

## 💡 Recommandations

### **Quand utiliser V1 ?**
- ✅ Vous voulez **juste savoir si le trade va gagner**
- ✅ Vous avez des **classes déséquilibrées** (beaucoup plus de WIN ou LOSS)
- ✅ Vous voulez des **probabilités** pour risk management
- ✅ **Interprétation simple** : "65% de chance de gagner"

### **Quand utiliser V2 ?**
- ✅ Vous voulez **savoir combien vous allez gagner/perdre**
- ✅ Vous voulez **filtrer les trades marginaux** (gains trop faibles)
- ✅ Vous avez besoin d'**estimations quantitatives** pour sizing
- ✅ Vous voulez **un modèle plus réaliste** du marché (split temporel)

### **Quand utiliser les deux ?**
- ✅ **Toujours !** Ils sont complémentaires
- ✅ V1 filtre les trades perdants
- ✅ V2 filtre les trades marginaux
- ✅ **Double validation** = qualité supérieure des setups

---

## 🎓 Conclusion

### **V1 (Classification)**
**Force :** Simple, robuste, probabilités interprétables
**Faiblesse :** Ne distingue pas un petit gain d'un gros gain

### **V2 (Régression)**
**Force :** Prédictions quantitatives, split temporel réaliste
**Faiblesse :** Plus difficile (R² plus faible), nécessite plus de données

### **Ensemble**
**Force :** Complémentaires, validation multi-niveaux, meilleure qualité
**Faiblesse :** Plus complexe à gérer (2 modèles à maintenir)

**🎯 Objectif final :** Maximiser le **Profit Factor** en combinant les forces des deux approches !

---

## 📚 Références

- **XGBoost Documentation** : https://xgboost.readthedocs.io/
- **Sklearn Metrics** : https://scikit-learn.org/stable/modules/model_evaluation.html
- **Optuna** : https://optuna.readthedocs.io/
- **Temporal Split for Trading** : https://www.quantstart.com/articles/Avoiding-Look-Ahead-Bias-in-Time-Series-Modelling/

---

*Généré automatiquement - Version 1.0*
