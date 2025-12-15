# Plan de Réorganisation - Onglet Machine Learning

## Structure Actuelle
1. Filtrage ML des trades (✅)
2. Hyperparamètres XGBoost
3. Métriques du Modèle Actuel
4. Section Optimisation Automatique (Panel + History)

## Structure Cible
1. Filtrage ML des trades (✅ garder)
2. **Métriques du Modèle Actuel** (déplacer ici)
3. **Historique des optimisations** (version simplifiée, sans trials détaillés)
4. Hyperparamètres XGBoost (+ 3 nouveaux params)
   - colsample_bylevel
   - gamma  
   - scale_pos_weight
5. Panel d'optimisation (sans History)

## Changements à Appliquer

### 1. Ajouter 3 nouveaux contrôles dans Hyperparamètres
- `ml_colsample_bylevel`: slider 0.5-1.0, step 0.05
- `ml_gamma`: slider 0.0-5.0, step 0.5
- `ml_scale_pos_weight`: slider 0.5-2.0, step 0.1

### 2. Déplacer Métriques
Section "Métriques du Modèle Actuel" → après "Filtrage ML"

### 3. Créer Historique Simplifié
- Afficher seulement : meilleur trial, total trials, completed/pruned
- Sans la liste détaillée des 20 derniers trials

### 4. Repositionner Panel Optimisation
- Garder uniquement OptimizationPanel (sans OptimizationHistory)
