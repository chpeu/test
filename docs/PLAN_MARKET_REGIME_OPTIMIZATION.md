# PLAN DIRECTEUR: Market Regime & ATR Optimization

> **Version:** 1.0
> **Date:** 09/12/2025
> **Statut:** Planification Architecturale
> **Objectif:** Unifier la détection de contexte (Régime/Saisonnalité) avec l'exécution optimisée (ATR) et le Machine Learning.

---

## 1. 🏗️ Architecture Unifiée

Le système évolue d'une logique purement réactive ("Si ATR < X") vers une architecture en couches contextuelles.

```ascii
┌───────────────────────────────────────────────────────────────────────────┐
│                           NIVEAU 1: CONTEXTE (MACRO)                      │
│                                                                           │
│  ┌──────────────────────┐      ┌──────────────────────────────────────┐   │
│  │ DATA COLLECTOR       │      │ MARKET REGIME ENGINE                 │   │
│  │ - ATR 1m/5m (Médian) │─────▶│ 1. Saisonnalité (Time-based)         │   │
│  │ - ADX Trend          │      │ 2. Rule-Based V2 (Hystérésis/Lissé)  │   │
│  │ - Volume Flows       │      │ 3. ML Classifier (Prédictif)         │   │
│  └──────────────────────┘      └──────────────────────────────────────┘   │
│                                                   │                       │
│                                                   ▼                       │
│                                        [CONTEXTE DÉFINI]                  │
│                                   (Régime + Session + Score Confiance)    │
└───────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           NIVEAU 2: SIGNAL (MICRO)                        │
│                                                                           │
│  ┌──────────────────────┐      ┌──────────────────────────────────────┐   │
│  │ SCANNER PROACTIF     │      │ SCORING ML (GradientBoosting)        │   │
│  │ - Filtres adaptatifs │─────▶│ - Reçoit Context comme Feature       │   │
│  │   selon Régime       │      │ - Poids ajustés selon confiance      │   │
│  └──────────────────────┘      └──────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           NIVEAU 3: EXÉCUTION (OPTIMISATION)              │
│                                                                           │
│  ┌──────────────────────┐      ┌──────────────────────────────────────┐   │
│  │ POSITION MANAGER     │      │ DYNAMIC PARAMETERS                   │   │
│  │ - Exécution Trade    │◀─────│ - SL/TP Multipliers par Régime       │   │
│  │                      │      │ - Trailing Aggressivity              │   │
│  └──────────────────────┘      └──────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           NIVEAU 4: FEEDBACK LOOP                         │
│                                                                           │
│  ┌──────────────────────┐      ┌──────────────────────────────────────┐   │
│  │ ANALYSE POST-TRADE   │      │ OPTIMIZER (Continuous)               │   │
│  │ - What-If Simulator  │─────▶│ - Corrélations Régime ↔ Performance  │   │
│  │ - Logger Enrichi     │      │ - Auto-tuning des seuils             │   │
│  └──────────────────────┘      └──────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 🧠 Composants Détaillés

### 2.1 Market Regime Engine (Le Cerveau)

Ce module détermine les "règles du jeu" actuelles.

#### A. Saisonnalité (Time-Awareness)
Découpe la journée en sessions de liquidité distinctes (Heure Paris/CET).

| Session | Horaire | Caractéristique | Impact Paramètres |
|---------|---------|-----------------|-------------------|
| **ASIA** | 01:00-08:00 | Range, faible vol. | Seuils ATR réduits, TP serrés |
| **EU OPEN**| 08:00-10:00 | Breakouts, faux départs | Filtres volatilité stricts |
| **EU SESSION**| 10:00-14:00 | Tendance modérée | Paramètres standards |
| **US PRE** | 14:00-15:30 | Anticipation, pièges | Attente confirmation |
| **US OPEN** | 15:30-17:00 | **MAX Volatilité** | SL larges, TP ambitieux |
| **US CLOSE**| 21:00-22:00 | Pic liquidité fin | Scalping agressif |

#### B. Logique Anti-Bruit (Quick Wins)
Pour stabiliser la détection et éviter le "Flip-Flop" entre régimes.

1.  **Médiane Robuste:** `ATR_Moyen = Median(Top20_Paires)` au lieu de Moyenne (élimine les outliers type pump).
2.  **Lissage Temporel (EMA):** `Regime_Score = 0.3 * Actuel + 0.7 * Précédent`.
3.  **Hystérésis 10%:**
    *   Passage CALME → NORMAL requiert `ATR > Seuil_Base * 1.10`
    *   Retour NORMAL → CALME requiert `ATR < Seuil_Base * 0.90`

#### C. ML-Driven Layer (Futur)
Au lieu de seuils fixes (0.20, 0.40), le ML apprend les frontières optimales.
*   **Input:** ATR 1m/5m, ADX, Volume, Heure, BTC Volatility.
*   **Target:** Quel régime aurait maximisé le PnL sur les 60 dernières minutes?
*   **Output:** `Predicted_Regime` (ex: VOLATILE avec 85% confiance).

---

### 2.2 Synergie avec GradientBoosting

Le modèle de scoring (GB) actuel évalue la qualité d'un setup, mais manque de contexte macro.

**Nouvelles Features pour GB:**
1.  `regime_current` (Categorical: 0, 1, 2)
2.  `session_market` (Categorical: ASIA, EU, US)
3.  `regime_stability` (Temps depuis dernier changement de régime)
4.  `btc_correlation` (Corrélation 1h avec BTC)

**Résultat:** Le modèle apprendra que *"Un setup Engulfing (GB) est très puissant en US OPEN (Session) mais dangereux en ASIA (Session)"*.

---

## 3. 💾 Structure de Données (SQL)

Mise à jour du schéma pour supporter ces analyses.

### Table `trade_atr_metrics` (Enrichissement)

```sql
ALTER TABLE trade_atr_metrics 
ADD COLUMN IF NOT EXISTS session_market VARCHAR(20),       -- ASIA, EU, US
ADD COLUMN IF NOT EXISTS hour_utc INT,                     -- Heure du trade
ADD COLUMN IF NOT EXISTS day_of_week INT,                  -- Jour (0-6)
ADD COLUMN IF NOT EXISTS regime_method VARCHAR(20),        -- 'RULE_BASED' ou 'ML'
ADD COLUMN IF NOT EXISTS regime_ml_confidence FLOAT,       -- Confiance si ML
ADD COLUMN IF NOT EXISTS pnl_if_different_regime FLOAT;    -- Simulation What-If
```

### Table `market_regime_history` (Enrichissement)

```sql
ALTER TABLE market_regime_history
ADD COLUMN IF NOT EXISTS atr_median_1m FLOAT,              -- Valeur médiane
ADD COLUMN IF NOT EXISTS atr_median_5m FLOAT,              -- Valeur médiane 5m
ADD COLUMN IF NOT EXISTS outliers_count INT,               -- Nb paires exclues
ADD COLUMN IF NOT EXISTS session_market VARCHAR(20);       -- Session active
```

---

## 4. 📅 Plan d'Implémentation (Roadmap)

### PHASE 1: Quick Wins (Cette Semaine)
*Objectif: Stabiliser la détection actuelle et logger le contexte.*

1.  **Code:** Implémenter Médiane + Hystérésis dans `MarketRegimeSelector`.
2.  **Code:** Ajouter la détection de `session_market` (horaires).
3.  **DB:** Migrer SQL pour ajouter les colonnes contextuelles.
4.  **Logger:** Capturer ces nouvelles métriques pour chaque futur trade.

### PHASE 2: Accumulation & Clustering (Semaine prochaine)
*Objectif: Comprendre les données accumulées.*

1.  **Analyse:** Grouper les trades par `(Régime × Session)`.
2.  **Corrélation:** Script pour répondre à "Est-ce que US OPEN est vraiment plus rentable?".
3.  **Dashboard:** Visualiser la performance par Session.

### PHASE 3: Optimisation Dynamique (Mois prochain)
*Objectif: Adapter le trading automatiquement.*

1.  **Continuous Optimizer:** Suggérer des paramètres SL/TP différents pour ASIA vs US.
2.  **ML Training:** Entraîner un classifier pour prédire le régime optimal.
3.  **Auto-Switch:** Le bot change de profil de risque selon l'heure et la volatilité prédite.

---

## 5. 🎯 Variables de Configuration (Nouvelles)

À ajouter dans `config.py` ou `config_overrides.json`:

```json
{
  "market_regime": {
    "method": "median_hysteresis", 
    "hysteresis_percent": 0.10,
    "use_median": true,
    "smoothing_period": 3,
    "seasonality_enabled": true,
    "sessions": {
      "asia": {"start": 1, "end": 8, "atr_multiplier": 0.8},
      "eu":   {"start": 8, "end": 14, "atr_multiplier": 1.0},
      "us":   {"start": 14, "end": 22, "atr_multiplier": 1.2}
    }
  }
}
```

---

## 6. 📝 Cas d'Usage Illustratif

**Scénario:** Lundi, 15h45 (US Open). BTC pompe soudainement.

1.  **Regime Selector:**
    *   Detecte `US_OPEN` (+20% tolérance volatilité).
    *   Detecte ATR médian qui explose.
    *   Passe en mode **VOLATILE**.

2.  **Scanner:**
    *   Active les filtres "VOLATILE" (cherche gros mouvements).
    *   Trouve `SOL/USDT`.

3.  **Scoring (GB):**
    *   Voit feature `session=US_OPEN` + `regime=VOLATILE`.
    *   Sait que *Breakout* marche bien ici.
    *   Donne score **85%**.

4.  **Exécution:**
    *   Position Manager applique `SL = 1.5x ATR` (large pour éviter mèches).
    *   Position Manager applique `TP = 3.0x ATR` (ambitieux).

5.  **Résultat:**
    *   Le trade survit à la volatilité initiale grâce au SL large.
    *   Capture le gros mouvement grâce au TP ambitieux.
    *   (Sans ce système, le SL standard "NORMAL" aurait été touché).
