# 📖 GUIDE D'UTILISATION DES OUTILS

**Trade Cursor v7.0** - Outils d'analyse et d'optimisation  
**Date**: 2025-11-06

---

## 🎯 VUE D'ENSEMBLE

Vous disposez de **4 outils puissants** pour optimiser et analyser votre bot de trading :

| Outil | Fichier | Usage |
|-------|---------|-------|
| 🧪 **Tests Fonctionnalités** | `test_features.py` | Valider les améliorations Phase 6-8 |
| 📊 **Analyseur de Logs** | `analyze_logs.py` | Comprendre les rejets de setups |
| 🎯 **Optimiseur de Seuils** | `optimize_thresholds.py` | Ajuster spread/orderbook/invalidation |
| 🪜 **TP Escalier** | `test_tp_escalier.py` | Tester le TP multi-level |

---

## 🧪 1. TESTER LES FONCTIONNALITÉS

### Quand l'utiliser ?
- ✅ Après une mise à jour du code
- ✅ Pour valider que tout fonctionne
- ✅ Avant de déployer en production

### Commande
```bash
cd C:\Users\sebta\Documents\code scalp\trade_cursor_py
python test_features.py
```

### Ce qui est testé
1. **Recovery Mode Progressif** (3 niveaux)
2. **Seuils Adaptatifs ATR** (volatilité variable)
3. **Position Sizing Adaptatif** (score + loss streak)
4. **Correlation Filter** (SOFT/HARD)
5. **Database SQLite** (CRUD)
6. **Métriques par Condition** (winrates)

### Sortie attendue
```
============================================================
🧪 DÉBUT DES TESTS DES FONCTIONNALITÉS
============================================================

TEST 1: RECOVERY MODE PROGRESSIF
============================================================
✅ PASS | Recovery Mode | Mode SIMPLE (loss_streak=3)
✅ PASS | Recovery Mode | PROGRESSIVE Niveau 1 (loss_streak=2)
✅ PASS | Recovery Mode | PROGRESSIVE Niveau 2 (loss_streak=3)
✅ PASS | Recovery Mode | PROGRESSIVE Niveau 3 (loss_streak=5)

TEST 2: SEUILS ADAPTATIFS ATR
============================================================
✅ PASS | Seuils Adaptatifs | ATR faible (0.2%)
✅ PASS | Seuils Adaptatifs | ATR élevé (1.0%)
✅ PASS | Seuils Adaptatifs | ATR normal (0.5%)

RAPPORT DE TEST
============================================================
Total tests: 18
✅ Passed: 18 (100.0%)
❌ Failed: 0 (0.0%)

✅ Résultats sauvegardés dans test_results.json
```

### Fichier généré
- `test_results.json`: Détails de chaque test

---

## 📊 2. ANALYSER LES LOGS

### Quand l'utiliser ?
- ❌ Trop peu de setups détectés
- ❌ Beaucoup de rejets
- ❓ Comprendre pourquoi les paires sont rejetées

### Commande
```bash
# Auto-détection du dernier fichier .log
python analyze_logs.py

# Ou spécifier un fichier
python analyze_logs.py trade_bot_2025_11_06.log
```

### Ce qui est analysé
1. **Stats globales**: Paires analysées, setups valides/rejetés, erreurs
2. **Top raisons de rejet**: Spread, orderbook, corrélation, score, etc.
3. **Patterns de rejet**: Fréquence par catégorie
4. **Symboles problématiques**: Top 10 paires les plus rejetées
5. **Recommandations automatiques**: Suggestions d'ajustement

### Exemple de sortie
```
📊 RAPPORT D'ANALYSE DES LOGS
============================================================
📈 STATISTIQUES GLOBALES
  Paires analysées: 250
  ✅ Setups valides: 18 (7.2%)
  ❌ Rejets: 232 (92.8%)
  Taux validation: 7.2%
  Taux rejet: 92.8%

🔴 TOP 10 RAISONS DE REJET
  1. spread: 0.05% (75×, 32.3%)
  2. orderbook: 1.05 (52×, 22.4%)
  3. score_insuffisant: 7.3 (38×, 16.4%)
  4. correlation: BTC_GROUP (28×, 12.1%)
  5. price_action: incohérence (22×, 9.5%)

📊 PATTERNS DE REJET
  SPREAD: 75× (32.3%)
  ORDERBOOK: 52× (22.4%)
  SCORE_INSUFFISANT: 38× (16.4%)
  CORRELATION: 28× (12.1%)

🔴 TOP 10 SYMBOLES LES PLUS REJETÉS
  1. BTC: 45× rejets (principale: spread)
  2. ETH: 38× rejets (principale: orderbook)
  3. SOL: 32× rejets (principale: score_insuffisant)

💡 RECOMMANDATIONS
  ⚠️ Filtre 'spread' très restrictif (32.3%)
     → Augmenter les seuils de spread (FIXE: 0.03%→0.04%, ATR: 0.06%→0.08%)
```

### Fichiers générés
- `log_analysis_report.json`: Rapport complet JSON
- Console: Rapport détaillé

### Interprétation

**Si taux rejet > 90%** → Seuils trop restrictifs
- Identifier le filtre le plus restrictif (ex: spread 32%)
- Appliquer les recommandations

**Si taux validation > 15%** → Seuils trop tolérants
- Risque de faux signaux
- Augmenter `min_score_required`

**Cible idéale** : 5-10% de taux validation

---

## 🎯 3. OPTIMISER LES SEUILS

### Quand l'utiliser ?
- 📉 Winrate faible (<65%)
- 📊 Après analyse des logs
- 🔧 Pour affiner les paramètres

### Commande
```bash
# Utiliser l'historique par défaut (instance 5000)
python optimize_thresholds.py

# Ou spécifier un historique
python optimize_thresholds.py --history trade_history_instance_5000.json -o report.json
```

### Ce qui est analysé
1. **Impact Spread**: Simulation avec différents seuils
2. **Impact Orderbook**: LONG (1.05-1.2) et SHORT (0.90-0.98)
3. **Early Invalidation**: Stats trades invalidés + PnL moyen
4. **Score Minimum**: Corrélation avec winrate

### Exemple de sortie
```
📊 ANALYSE IMPACT SPREAD
============================================================
💡 RECOMMANDATIONS SPREAD
  Actuel FIXE: 0.03%
  Actuel ATR:  0.06%

  Si trop de rejets:
    → FIXE: 0.03% → 0.04%
    → ATR:  0.06% → 0.08%

📊 ANALYSE INVALIDATION PRÉCOCE
============================================================
📈 STATISTIQUES
  Trades invalidés: 15
  PnL moyen: -0.18%
  Durée moyenne: 18s

💡 RECOMMANDATIONS
  Actuel 15s: -0.12%
  Actuel 30s: -0.08%
  ⚠️ PnL très négatif → Seuils trop tolérants
    → Réduire: -0.12% → -0.10% (15s)
    → Réduire: -0.08% → -0.06% (30s)

📊 ANALYSE SCORE MINIMUM
============================================================
📈 STATISTIQUES GLOBALES
  Total trades: 85
  Winrate: 62.4%

💡 RECOMMANDATIONS SCORE
  Actuel: 7.5
  ADX > 30: 7.0
  ADX < 25: 8.0
  ⚠️ Winrate bas → Augmenter score minimum
    → 7.5 → 8.0
    → ADX > 30: 7.0 → 7.5

🎯 RAPPORT D'OPTIMISATION
============================================================
💡 RÉSUMÉ DES RECOMMANDATIONS

1. [HAUTE] SCORE
   Action: Augmenter min_score_required: 7.5 → 8.0
   Raison: Winrate bas (62.4%)

2. [MOYENNE] EARLY_INVALIDATION
   Action: Réduire seuils invalidation: -0.12% → -0.10%
   Raison: PnL moyen invalidations trop négatif (-0.18%)

📝 CONFIGURATION SUGGÉRÉE
============================================================
📋 Modifications suggérées dans config.py:
  TRADING_CONFIG['min_score_required'] = 8.0  # Augmenté de 7.5
  TRADING_CONFIG['early_invalidation']['threshold_15s'] = -0.10  # Réduit de -0.12
  TRADING_CONFIG['early_invalidation']['threshold_30s'] = -0.06  # Réduit de -0.08

✅ Suggestions sauvegardées dans: config_suggestions.txt
✅ Rapport sauvegardé dans: threshold_optimization_report.json
```

### Fichiers générés
1. `threshold_optimization_report.json`: Rapport complet
2. `config_suggestions.txt`: Modifications à copier dans `config.py`

### Application des recommandations

**1. Lire le fichier de suggestions**
```bash
notepad config_suggestions.txt
```

**2. Copier les modifications dans `config.py`**
```python
# Dans config.py
TRADING_CONFIG = {
    # ... autres paramètres ...
    
    'min_score_required': 8.0,  # ← Augmenté de 7.5
    
    'early_invalidation': {
        'enabled': True,
        'threshold_15s': -0.10,  # ← Réduit de -0.12
        'threshold_30s': -0.06,  # ← Réduit de -0.08
    },
}
```

**3. Relancer le bot**
```bash
python main.py
```

**4. Monitorer les résultats**
- Dashboard: http://localhost:5000
- Vérifier le winrate après 20-30 trades
- Réitérer si nécessaire

---

## 🪜 4. TESTER LE TP ESCALIER

### Quand l'utiliser ?
- ✅ Avant d'activer le TP Escalier en production
- ✅ Pour valider la logique multi-level
- ✅ Après modification de `config.py`

### Commande
```bash
python test_tp_escalier.py
```

### Ce qui est testé
1. **Test LONG**: 4 niveaux atteints séquentiellement
2. **Test SHORT**: 4 niveaux (prix descendant)
3. **Test Breakeven**: SL après niveau 2 (conservation profits)

### Sortie attendue
```
============================================================
🧪 DÉBUT DES TESTS TP ESCALIER
============================================================

🧪 TEST TP ESCALIER LONG
============================================================
✅ Initialisation OK
   Niveaux configurés: 4
   Niveau 1: 0.2% (25%) → entry
   Niveau 2: 0.35% (25%) → breakeven
   Niveau 3: 0.5% (25%) → trailing
   Niveau 4: 0.8% (25%) → trailing

🎯 TP Escalier Niveau 1/4 atteint ! Prix: 10020.0 | Vendu: 25.00 USDT (25%) | Profit: +0.05 USDT
🛡️ TP Escalier Niveau 1: SL → Entry (10000.0)

🎯 TP Escalier Niveau 2/4 atteint ! Prix: 10035.0 | Vendu: 25.00 USDT (25%) | Profit: +0.09 USDT
🛡️ TP Escalier Niveau 2: SL → Breakeven (10000.0)

🎯 TP Escalier Niveau 3/4 atteint ! Prix: 10050.0 | Vendu: 25.00 USDT (25%) | Profit: +0.12 USDT
📈 TP Escalier Niveau 3: Trailing stop activé

🎯 TP Escalier Niveau 4/4 atteint ! Prix: 10080.0 | Vendu: 25.00 USDT (25%) | Profit: +0.20 USDT
🎉 TP Escalier: Tous les 4 niveaux atteints ! Profit total cumulé: +0.46 USDT

✅ TEST TP ESCALIER LONG RÉUSSI

============================================================
✅ TOUS LES TESTS TP ESCALIER ONT RÉUSSI
============================================================
```

### Activation en production

**Dans `config.py`**:
```python
TRADING_CONFIG = {
    # ... autres paramètres ...
    
    'tp_sl_mode': 'TP_MULTI',  # ← Activer TP Escalier
    
    'tp_escalier': {
        'enabled': True,
        'levels': [
            {"pnl": 0.20, "size_pct": 0.25, "move_sl": "entry"},
            {"pnl": 0.35, "size_pct": 0.25, "move_sl": "breakeven"},
            {"pnl": 0.50, "size_pct": 0.25, "move_sl": "trailing"},
            {"pnl": 0.80, "size_pct": 0.25, "move_sl": "trailing"},
        ]
    },
}
```

**Personnalisation des niveaux**:
```python
# Exemple : 3 niveaux au lieu de 4
'levels': [
    {"pnl": 0.25, "size_pct": 0.33, "move_sl": "entry"},      # 33% @ +0.25%
    {"pnl": 0.45, "size_pct": 0.33, "move_sl": "breakeven"},  # 33% @ +0.45%
    {"pnl": 0.70, "size_pct": 0.34, "move_sl": "trailing"},   # 34% @ +0.70%
]

# Exemple : 5 niveaux pour plus de granularité
'levels': [
    {"pnl": 0.15, "size_pct": 0.20, "move_sl": "entry"},      # 20% @ +0.15%
    {"pnl": 0.30, "size_pct": 0.20, "move_sl": "breakeven"},  # 20% @ +0.30%
    {"pnl": 0.45, "size_pct": 0.20, "move_sl": "trailing"},   # 20% @ +0.45%
    {"pnl": 0.65, "size_pct": 0.20, "move_sl": "trailing"},   # 20% @ +0.65%
    {"pnl": 0.90, "size_pct": 0.20, "move_sl": "trailing"},   # 20% @ +0.90%
]
```

---

## 📊 WORKFLOW RECOMMANDÉ

### 🔄 Cycle d'optimisation

```
1. LANCER LE BOT
   python main.py
   ↓
2. TRADER PENDANT 1-2 JOURS
   Accumuler 50-100 trades
   ↓
3. ANALYSER LES LOGS
   python analyze_logs.py
   → Identifier les filtres restrictifs
   ↓
4. OPTIMISER LES SEUILS
   python optimize_thresholds.py
   → Appliquer recommandations dans config.py
   ↓
5. TESTER LES FONCTIONNALITÉS
   python test_features.py
   → Valider que tout fonctionne
   ↓
6. RELANCER LE BOT
   python main.py
   ↓
7. MONITORER LES RÉSULTATS
   Dashboard: http://localhost:5000
   → Winrate amélioré ?
   ↓
8. RÉPÉTER (si nécessaire)
```

### 📅 Planning suggéré

| Jour | Action | Outil |
|------|--------|-------|
| J1-J2 | Trading initial | `main.py` |
| J3 | Analyse logs | `analyze_logs.py` |
| J3 | Optimisation seuils | `optimize_thresholds.py` |
| J4 | Application modifications | Éditer `config.py` |
| J4 | Tests validation | `test_features.py` |
| J5-J6 | Trading avec nouveaux seuils | `main.py` |
| J7 | Analyse résultats | Dashboard + logs |
| J7 | Décision : Continuer / Réajuster | |

---

## 🎯 INDICATEURS DE PERFORMANCE

### Cibles à atteindre

| Métrique | Valeur cible | Action si hors cible |
|----------|--------------|----------------------|
| **Winrate** | 65-80% | Ajuster `min_score_required` |
| **Taux validation** | 5-10% | Assouplir/Durcir filtres |
| **Profit Factor** | > 1.5 | Optimiser TP/SL |
| **Drawdown max** | < 5% | Réduire position size |
| **Trades invalidés** | < 10% | Ajuster early invalidation |

### Dashboard metrics (http://localhost:5000)

Surveiller :
- 📊 **Total trades** : > 50 pour stats significatives
- 💰 **PnL net** : Trend positif
- 📈 **Winrate** : 65-80% idéal
- 📉 **Max Drawdown** : < 5%
- 🔴 **Loss streak** : < 3 (sinon Recovery Mode activé)

---

## 🆘 DÉPANNAGE

### Problème : Aucun setup détecté

**Symptôme** : 0 setup en 1 heure

**Diagnostic**:
```bash
python analyze_logs.py
# Regarder "Top raisons de rejet"
```

**Solutions possibles**:
1. Spread trop restrictif → Augmenter seuils
2. Score trop élevé → Réduire `min_score_required`
3. Orderbook trop strict → Assouplir ratios

---

### Problème : Winrate faible (<60%)

**Symptôme** : Beaucoup de trades perdants

**Diagnostic**:
```bash
python optimize_thresholds.py
# Regarder recommandations SCORE
```

**Solutions possibles**:
1. Augmenter `min_score_required` (7.5 → 8.0)
2. Activer Recovery Mode
3. Réduire position size

---

### Problème : Trop d'invalidations précoces

**Symptôme** : >15% trades fermés EARLY_INVALIDATION

**Diagnostic**:
```bash
python optimize_thresholds.py
# Regarder "Analyse Invalidation Précoce"
```

**Solutions possibles**:
1. Si PnL moyen < -0.15% → Seuils trop tolérants → Réduire (-0.12% → -0.10%)
2. Si PnL moyen > 0% → Seuils trop stricts → Augmenter (-0.12% → -0.15%)

---

### Problème : TP Escalier ne se déclenche pas

**Symptôme** : Mode TP_MULTI activé mais pas de niveaux

**Diagnostic**:
```bash
python test_tp_escalier.py
# Vérifier si tests passent
```

**Solutions possibles**:
1. Vérifier `config.py`: `'tp_sl_mode': 'TP_MULTI'`
2. Vérifier `config.py`: `'tp_escalier': {'enabled': True}`
3. Relancer le bot : `python main.py`

---

## 📚 RESSOURCES

### Documentation
- `README.md`: Vue d'ensemble du projet
- `IMPLEMENTATION_TP_ESCALIER.md`: Détails TP Escalier
- `RESUME_SESSION_2025_11_06.md`: Résumé session
- `GUIDE_UTILISATION_OUTILS.md`: Ce fichier

### Code source
- `main.py`: Point d'entrée bot
- `config.py`: Configuration centrale
- `core/position_manager.py`: Gestion positions + TP Escalier
- `core/analyzer.py`: Analyse technique + filtres

### Tests
- `test_features.py`: Tests fonctionnalités
- `test_tp_escalier.py`: Tests TP Escalier
- `test_position_manager.py`: Tests position manager

---

## ✅ CHECKLIST DE DÉMARRAGE

Avant de trader en réel :

- [ ] Tests fonctionnalités réussis (`python test_features.py`)
- [ ] Tests TP Escalier réussis (`python test_tp_escalier.py`)
- [ ] Configuration vérifiée (`config.py`)
- [ ] Logs analysés (au moins 50 trades en simulation)
- [ ] Seuils optimisés (winrate > 65% en simulation)
- [ ] Dashboard accessible (http://localhost:5000)
- [ ] Mode TP/SL choisi (FIXE / ATR / TP_MULTI)
- [ ] Position size adaptée au capital

---

**Bon trading ! 🚀**

**Questions ?** Consultez `README.md` ou les fichiers de documentation.

---

**Date**: 2025-11-06  
**Version**: Trade Cursor v7.0  
**Auteur**: Assistant AI

