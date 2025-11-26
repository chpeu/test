# ✅ CHECKLIST DEPLOIEMENT PRODUCTION

**Date**: 2025-11-24 20:15:12

---

## 📋 INFRASTRUCTURE

- [x] PostgreSQL accessible
- [x] Table `ml_models` creee
- [x] Colonnes `config_*` presentes (scan_logs + trades)
- [x] Vue `ml_features` fonctionnelle
- [x] Fonction `get_pg_datalogger()` ajoutee
- [x] Fallback prix implemente (price_provider)

## 💻 CODE

- [x] API endpoint `/api/ml/train_v2` cree
- [x] Import `Request` ajoute dans `api/routes/ml.py`
- [x] `XGBoostTrainerV2` avec split temporel
- [x] Class weights automatiques
- [x] Feature selection top-K
- [x] Model logger PostgreSQL integre

## 🚀 DEPLOIEMENT

- [ ] **Backend redemarre** (avec nouveaux endpoints)
  ```bash
  # Arreter: Ctrl+C
  # Redemarrer:
  python main.py
  ```

- [ ] **Tester API** (optionnel)
  ```bash
  curl http://localhost:5000/api/ml/models
  ```

- [ ] **Verifier logs** (optionnel)
  - Aucune erreur au demarrage
  - Endpoint /train_v2 charge

## 🔧 AMELIORATION MODELE (PRIORITAIRE)

- [ ] **Lire** `NEXT_STEPS.md` (5 min)
- [ ] **Feature engineering** (2-3h)
  - Ajouter features temporelles
  - Ajouter market regime
  - Ajouter confluence avancee
- [ ] **Augmenter dataset** (1h)
  - timeframe_days=365
  - Filtrage moins strict
- [ ] **Tester regression** (1h)
  - XGBRegressor au lieu de classifier

## 📊 VALIDATION

- [ ] **Entrainer modele ameliore**
  ```bash
  python train_final_optimized.py
  ```

- [ ] **Verifier metriques**
  - Test Accuracy >= 60%
  - F1 Score > 0.30
  - Gap < 20%

- [ ] **Si succes**: Activer en production
- [ ] **Si echec**: Continuer feature engineering

---

## 🎯 OBJECTIFS

| Metrique | Actuel | Objectif |
|----------|--------|----------|
| Test Accuracy | 45.9% | 60%+ |
| F1 Score | 0.000 | 0.30+ |
| ROC-AUC | 45.1% | 60%+ |

---

**Status**: Infrastructure prete, modele necessite feature engineering
