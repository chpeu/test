# 🚀 Plan d'Action Parallèle - Live Trading + EDA V2

**Date:** 25 novembre 2025, 20:15  
**Durée:** 7-10 jours  
**Objectifs:** MEXC DRY_RUN + R² V2 > 0.30

---

## 📅 Timeline (Jour par Jour)

### Jour 1-2: SETUP (Aujourd'hui + Demain)

#### 🔴 Piste LIVE TRADING
- [ ] **1.1** Créer API Keys MEXC (15 min)
- [ ] **1.2** Ajouter dans `.env` (2 min)
- [ ] **1.3** Tester connexion API (5 min)
- [ ] **1.4** Activer mode DRY_RUN (2 min)

#### 🔵 Piste EDA V2
- [ ] **1.5** Modifier config: `timeframe_days = 540` (1 min)
- [ ] **1.6** Modifier config: `marginal_threshold = 0.15` (1 min)
- [ ] **1.7** Relancer entraînement V2 (10 min)
- [ ] **1.8** Vérifier dataset > 100 trades (2 min)

**Scripts à exécuter:**
```bash
# Live Trading
python main.py  # Vérifier logs "LiveOrderManager initialisé"

# EDA V2
# Via UI: ML Dashboard V2 → Réentraîner
# Ou API:
curl -X POST http://localhost:8000/api/ml/train_v2
```

---

### Jour 3-5: ANALYSE + TESTS

#### 🔴 Piste LIVE (Mode DRY_RUN)
- [ ] **2.1** Laisser scanner tourner 3 jours
- [ ] **2.2** Vérifier stats ordres (UI Live Panel)
- [ ] **2.3** Mesurer latence API moyenne
- [ ] **2.4** Valider slippage < 0.10%

**Métriques cibles:**
- Ordres simulés: 10-30
- Latence: < 500ms
- Taux succès: 100% (DRY_RUN)

#### 🔵 Piste EDA (Analyse SQL)
- [ ] **2.5** Distribution PNL (Requête SQL 1)
- [ ] **2.6** Corrélation features (Requête SQL 2)
- [ ] **2.7** Détection outliers (Requête SQL 3)
- [ ] **2.8** Analyse drift temporel (Requête SQL 4)

**Requêtes SQL à exécuter:**
```sql
-- 2.5 Distribution PNL
SELECT pnl_pct, COUNT(*) FROM trades 
WHERE created_at > NOW() - INTERVAL '540 days'
GROUP BY pnl_pct ORDER BY pnl_pct;

-- 2.6 Corrélations
SELECT 
    corr(rsi_1m, t.pnl_pct) as rsi_corr,
    corr(adx_1m, t.pnl_pct) as adx_corr,
    corr(score_1m, t.pnl_pct) as score_corr
FROM trades t 
LEFT JOIN scan_logs s ON t.scan_log_id = s.id
WHERE t.created_at > NOW() - INTERVAL '540 days';
```

---

### Jour 6-7: OPTIMISATION

#### 🔴 Piste LIVE
- [ ] **3.1** Analyser résultats DRY_RUN
- [ ] **3.2** Ajuster config si nécessaire
- [ ] **3.3** Décider: continuer DRY ou tester LIVE

**Decision tree:**
- Latence < 500ms + slippage < 0.10% → ✅ Prêt LIVE
- Sinon → Continuer DRY_RUN

#### 🔵 Piste EDA
- [ ] **3.4** Créer 3 nouvelles features SQL
- [ ] **3.5** Tester différents thresholds
- [ ] **3.6** Relancer entraînement avec best config
- [ ] **3.7** Valider R² > 0.28

**Features à créer:**
```sql
ALTER TABLE scan_logs ADD COLUMN volume_ratio_1m_5m DOUBLE PRECISION;
ALTER TABLE scan_logs ADD COLUMN rsi_momentum DOUBLE PRECISION;
ALTER TABLE scan_logs ADD COLUMN confluence_score DOUBLE PRECISION;
```

---

### Jour 8-10: PRODUCTION

#### 🔴 Piste LIVE (Si validation OK)
- [ ] **4.1** 5 trades réels (5 USDT/trade)
- [ ] **4.2** Comparer vs simulation
- [ ] **4.3** Passer à 10-20 USDT/trade

#### 🔵 Piste EDA
- [ ] **4.4** Monitoring drift activé
- [ ] **4.5** Dashboard métriques V2
- [ ] **4.6** Documentation finale

---

## 🎯 Commandes Rapides

### Setup Immédiat (À faire maintenant)

```bash
# 1. Backend + Frontend
cd "c:\Users\sebta\Documents\clone github\test\test"
python main.py  # Terminal 1

cd frontend
npm run dev  # Terminal 2

# 2. Ouvrir http://localhost:5173
```

### Configuration V2 (Via UI ou fichier)

```python
# config.py - Modifier ces lignes:
TRADING_CONFIG = {
    # ... existant ...
    
    # EDA V2 - Augmenter dataset
    'ml_v2_timeframe_days': 540,        # 1.5 ans au lieu de 270
    'ml_v2_marginal_threshold': 0.15,   # Au lieu de 0.20
    
    # Live Trading
    'ml_v2_filter_enabled': False,      # Activer après tests
}
```

### Ajouter API Keys MEXC

```bash
# .env - Ajouter à la fin
MEXC_API_KEY=ton_api_key_ici
MEXC_API_SECRET=ton_api_secret_ici
```

---

## 📊 Tableau de Bord

### Status Piste LIVE

| Métrique | Actuel | Cible | Status |
|----------|--------|-------|--------|
| API Keys | ⚪ | ✅ | À faire |
| Connexion API | ⚪ | ✅ | À tester |
| Mode DRY_RUN | ⚪ | ✅ | À activer |
| Latence API | - | < 500ms | - |
| Ordres simulés | 0 | 10+ | - |

### Status Piste EDA

| Métrique | Actuel | Cible | Status |
|----------|--------|-------|--------|
| Dataset Size | 59 | 150+ | À augmenter |
| R² Test | 0.234 | > 0.30 | À améliorer |
| MAE Test | 0.450% | < 0.40% | À réduire |
| Features | 40 | 43+ | À ajouter |
| Outliers | ? | < 5% | À analyser |

---

## ⚠️ Points de Contrôle

### Checkpoint 1 (Jour 2)
- ✅ API MEXC connectée
- ✅ Dataset V2 > 100 trades
- ✅ R² baseline mesuré

### Checkpoint 2 (Jour 5)
- ✅ 3 jours DRY_RUN sans erreur
- ✅ Analyse SQL complétée
- ✅ Corrélations identifiées

### Checkpoint 3 (Jour 7)
- ✅ Décision LIVE ou continuer DRY
- ✅ R² > 0.28 atteint
- ✅ Nouvelles features créées

### Checkpoint 4 (Jour 10)
- ✅ Production LIVE validée (si GO)
- ✅ Monitoring V2 actif
- ✅ Documentation complète

---

## 🚨 Troubleshooting Rapide

### LIVE: "API Keys invalides"
```bash
# Vérifier format
echo $MEXC_API_KEY  # Doit commencer par mx0
```

### EDA: "Dataset toujours petit"
```sql
-- Vérifier nombre de trades disponibles
SELECT COUNT(*) FROM trades 
WHERE created_at > NOW() - INTERVAL '540 days'
  AND ABS(pnl_pct) >= 0.15;
```

### Backend: "Import error"
```bash
pip install ccxt psycopg2-binary pandas numpy
```

---

## ✅ Checklist Première Heure

**À faire MAINTENANT (60 min):**

- [ ] 1. Créer compte MEXC (si pas déjà fait)
- [ ] 2. Créer API Keys MEXC (15 min)
- [ ] 3. Ajouter dans `.env` (2 min)
- [ ] 4. Modifier `config.py`: timeframe=540, threshold=0.15 (3 min)
- [ ] 5. Démarrer backend `python main.py` (2 min)
- [ ] 6. Démarrer frontend `npm run dev` (2 min)
- [ ] 7. Tester connexion MEXC (UI Live Panel) (5 min)
- [ ] 8. Lancer entraînement V2 (UI ML Dashboard) (10 min)
- [ ] 9. Vérifier logs: dataset size > 100 (2 min)
- [ ] 10. Vérifier logs: "LiveOrderManager initialisé DRY_RUN" (2 min)

**Après ces 10 étapes:** Tout sera configuré et tournera en arrière-plan ! 🎉

---

**Prêt à commencer ?** Ouvre 2 terminaux et lance les commandes ! 🚀
