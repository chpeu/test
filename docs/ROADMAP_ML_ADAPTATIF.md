# 🗺️ ROADMAP ML ADAPTATIF

> **Mise à jour:** 07/12/2025 | **Objectif:** Bot auto-adaptatif

---

## ✅ SPRINT 1 - TERMINÉ

### 1.1 Market Regime Selector ✅
- Détection auto: CALME/NORMAL/VOLATILE/CHOPPY
- Ajustement params selon régime
- Widget frontend temps réel

### 1.2 Trading Circuit Breaker ✅
- Pause auto après 5 pertes consécutives
- Drawdown protection (-2% pause, -5% stop)
- Score boost progressif

---

## ⏳ SPRINT 2 - EN COURS (50%)

### 2.1 Filtre Horaire ❌ À FAIRE (~2h)
- Blacklist heures WR < 35%
- Mode prudent WR < 45% (+2 score)
- Fichier: `core/hourly_filter.py`

### 2.2 Pair Scorer ✅ TERMINÉ
- Bonus/malus ±2.0 pts par paire
- Basé sur winrate + PnL moyen
- Table `pair_performance_stats`
- Onglet frontend "Adaptations ML"

---

## ❌ SPRINT 3 - À FAIRE

### 3.1 Momentum BTC (~3h)
| Mode | Δ BTC 1h | Action |
|------|----------|--------|
| PUMP | > +3% | LONG_ONLY |
| DUMP | < -3% | SHORT_ONLY/PAUSE |
| FLAT | < ±1% | Normal |

### 3.2 Optimiseur Nocturne (~3h)
- Cron 3h: analyse trades 7j
- Grid search configs par régime
- Auto-update `config/regimes/*.json`

---

## ❌ SPRINT 4 - OPTIONNEL

| Feature | Description | Temps |
|---------|-------------|-------|
| Config Blending | Transition douce entre régimes | 3h |
| Voting Ensemble | XGBoost + GradientBoost + RF | 4h |
| Drift Detector | Alerte changement distribution | 4h |

---

## 💡 IDÉES BONUS

### Session Filter
| Session | Heures UTC | Action |
|---------|------------|--------|
| ASIA | 00-08h | Score +1 |
| OVERLAP EU/US | 14-17h | Bonus -1 |
| NIGHT | 21-00h | Score +2 |

### Correlation Filter
- Si >3 setups LONG simultanés → Réduire exposure
- Évite sur-exposition à mouvement BTC

### News Calendar
- Pause auto avant CPI/FOMC
- Fichier JSON événements macro

### Liquidation Heatmap
- Éviter zones liquidation massives
- Source: Coinglass API

---

## 📅 PLANNING

| Semaine | Tâche | Temps |
|---------|-------|-------|
| S1 | Filtre Horaire + BTC Momentum | 5h |
| S2 | Optimiseur Nocturne | 3h |
| S3 | Config Blending + Ensemble | 7h |
| S4 | Extras (Session/Correlation) | 4h |

**Total:** ~19h sur 4 semaines

---

## 📁 FICHIERS

```
core/
├── market_regime_selector.py  ✅
├── trading_circuit_breaker.py ✅
├── pair_scorer.py             ✅
├── hourly_filter.py           ❌
├── btc_momentum.py            ❌
└── session_filter.py          ❌

scripts/
└── nightly_optimizer.py       ❌

data/
├── hourly_stats.json          ❌
└── pair_scores.json           ✅ (via PostgreSQL)
```
