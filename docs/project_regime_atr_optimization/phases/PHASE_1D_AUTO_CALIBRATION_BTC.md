# 🎯 PHASE 1D : Auto-Calibration Seuils ATR + BTC Indicateur

> **Date création:** 11/12/2025
> **Status:** 🔄 EN COURS
> **Prérequis:** Phase 1B (Régime V2) - Hystérésis/Médiane
> **Effort estimé:** ~6h
> **Décision:** Brainstorming Option D

---

## 🎯 OBJECTIFS

### 1. Auto-Calibration Seuils ATR
Au lieu de seuils fixes (0.20, 0.40), utiliser les **percentiles historiques** pour s'adapter au marché:

| Seuil | Actuel (fixe) | Nouveau (percentiles) |
|-------|---------------|----------------------|
| CALME max | 0.20% | P33 des 7 derniers jours |
| NORMAL max | 0.40% | P66 des 7 derniers jours |
| VOLATILE | > 0.40% | > P66 |

### 2. BTC comme Indicateur de Régime
Ajouter la tendance/volatilité BTC comme **confirmation** du régime:

| Situation | Impact |
|-----------|--------|
| BTC volatile (>2% 1h) | Force VOLATILE |
| BTC stable + ATR calme | Confirme CALME |
| BTC trend fort (>5% 24h) | Boost confiance régime |

---

## 📊 DONNÉES HISTORIQUES DISPONIBLES

```sql
-- Analyse 11/12/2025
| Date       | Samples | Mean ATR | P25    | P50    | P75    |
|------------|---------|----------|--------|--------|--------|
| 2025-12-11 | 44      | 0.2402   | 0.1524 | 0.2132 | 0.2964 |
| 2025-12-09 | 36      | 0.1922   | 0.1254 | 0.1638 | 0.2167 |
| 2025-12-08 | 17      | 0.2157   | 0.1670 | 0.2069 | 0.2500 |
| 2025-12-07 | 6       | 0.2238   | 0.1705 | 0.2046 | 0.2522 |
```

**Observation:** Les seuils actuels (0.20, 0.40) sont proches des percentiles P50/P75 réels.

---

## 🏗️ ARCHITECTURE D'INTÉGRATION

```
┌─────────────────────────────────────────────────────────────────┐
│                    MarketRegimeSelector                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │ ATR Auto-Calibrator  │    │   BTC Indicator      │           │
│  │ (percentiles 7j)     │    │   (MEXC API)         │           │
│  └──────────┬───────────┘    └──────────┬───────────┘           │
│             │                           │                        │
│             ▼                           ▼                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │           determine_regime_v3()                   │           │
│  │  - Seuils dynamiques (percentiles)               │           │
│  │  - BTC confirmation (optionnel)                  │           │
│  │  - Hystérésis (existant)                         │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 FICHIERS À MODIFIER

| Action | Fichier | Description |
|--------|---------|-------------|
| MODIFY | `core/market_regime_selector.py` | +calibrate_thresholds(), +get_btc_volatility() |
| MODIFY | `config.py` | +toggles auto_calibration, btc_indicator |
| CREATE | `core/btc_indicator.py` | Classe BTCIndicator (MEXC API) |
| MODIFY | `core/postgresql_datalogger.py` | +colonnes calibration dans regime_history |

---

## ⚙️ NOUVELLES VARIABLES DE CONFIGURATION

```python
# config.py - Section MARKET_REGIME_V2_CONFIG
{
    # Auto-calibration (NOUVEAU)
    "auto_calibration_enabled": False,      # Toggle principal
    "calibration_lookback_days": 7,         # Fenêtre historique
    "calibration_percentile_calme": 33,     # P33 = seuil CALME
    "calibration_percentile_volatile": 66,  # P66 = seuil VOLATILE
    "calibration_refresh_hours": 6,         # Recalculer toutes les 6h
    "calibration_min_samples": 50,          # Minimum samples requis
    
    # BTC Indicator (NOUVEAU)
    "btc_indicator_enabled": False,         # Toggle principal
    "btc_volatile_threshold_1h": 2.0,       # % variation 1h = volatile
    "btc_trend_threshold_24h": 5.0,         # % variation 24h = trend fort
    "btc_force_volatile_enabled": True,     # Forcer VOLATILE si BTC volatile
}
```

---

## 🔧 IMPLÉMENTATION

### 1. Auto-Calibration Seuils (market_regime_selector.py)

```python
async def calibrate_thresholds(self) -> Dict[str, float]:
    """
    Calibre les seuils ATR basé sur percentiles historiques.
    
    Returns:
        Dict avec threshold_calme, threshold_volatile
    """
    from utils.config_persistence import get_config_value
    
    if not get_config_value('market_regime_auto_calibration_enabled', False):
        # Retourner seuils fixes si désactivé
        return {
            'threshold_calme': 0.20,
            'threshold_volatile': 0.40
        }
    
    lookback_days = get_config_value('calibration_lookback_days', 7)
    p_calme = get_config_value('calibration_percentile_calme', 33)
    p_volatile = get_config_value('calibration_percentile_volatile', 66)
    min_samples = get_config_value('calibration_min_samples', 50)
    
    # Query PostgreSQL pour percentiles
    # ... (voir implémentation complète)
    
    return calibrated_thresholds
```

### 2. BTC Indicator (core/btc_indicator.py)

```python
class BTCIndicator:
    """
    Récupère et analyse la volatilité/tendance BTC pour confirmer le régime.
    Source: MEXC API (déjà connecté)
    """
    
    async def get_btc_status(self) -> Dict[str, Any]:
        """
        Returns:
            {
                'price': 97500.0,
                'pct_change_1h': 1.5,
                'pct_change_24h': 3.2,
                'is_volatile': False,
                'trend': 'BULLISH'  # BULLISH/BEARISH/RANGING
            }
        """
```

---

## ✅ CHECKLIST IMPLÉMENTATION

### Phase 1D-A: Auto-Calibration (3h)
- [ ] Ajouter méthode `calibrate_thresholds()` dans MarketRegimeSelector
- [ ] Query SQL pour percentiles historiques
- [ ] Cache des seuils calibrés (refresh toutes les 6h)
- [ ] Toggle dans config + frontend
- [ ] Log des seuils calibrés
- [ ] Test: vérifier que seuils changent avec données

### Phase 1D-B: BTC Indicator (3h)
- [ ] Créer `core/btc_indicator.py`
- [ ] Intégrer appel MEXC API (get_ticker BTCUSDT)
- [ ] Calcul pct_change 1h et 24h
- [ ] Intégrer dans `determine_regime()` comme confirmation
- [ ] Toggle dans config + frontend
- [ ] Test: vérifier que BTC volatile force VOLATILE

---

## 🔗 INTÉGRATION AVEC PHASES EXISTANTES

| Phase | Relation | Impact |
|-------|----------|--------|
| Phase 1B (Médiane/Hystérésis) | ✅ Compatible | Utilise même structure |
| Phase 1C (What-If) | ✅ Compatible | What-if peut tester différents seuils |
| Phase 2D (ML Params) | ✅ Synergique | ML optimise params, calibration optimise seuils |
| Phase 3A (ML Régime) | ✅ Prépare | Features BTC utiles pour ML régime |
| Phase 4 (Features) | ✅ Synergique | BTC features déjà planifiées |

---

## 📊 MÉTRIQUES DE SUCCÈS

| Métrique | Avant | Après (cible) |
|----------|-------|---------------|
| Flip-flop régime/jour | ~8 | ~3 |
| Régime "faux" (what-if) | ~20% | ~10% |
| Adaptation au marché | Manuelle | Auto (6h) |

---

## 🚀 PROCHAINES ÉTAPES

1. **Implémenter** `calibrate_thresholds()` dans market_regime_selector.py
2. **Créer** `core/btc_indicator.py`
3. **Ajouter** toggles dans config.py
4. **Tester** avec données live
5. **Documenter** dans 00_PROJECT_TRACKER.md
