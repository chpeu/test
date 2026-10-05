# Analyse Sprint 3 - Local Regime Adaptation (10/12/2025)

> **Dernière mise à jour:** 10/12/2025 19:15

---

## 1. Validation Technique ✅
Les ajustements dynamiques sont opérationnels en prod.

### Paramètres Actuels (après ajustement agressif 19:00)

| Régime | TP | SL | BE | Trail Trigger | Trail Dist | Stag Timeout |
|--------|-----|-----|-----|---------------|------------|--------------|
| **LOW** | ×1.0 | ×1.0 | ×1.0 | ×1.0 | ×1.0 | ×1.0 |
| **MEDIUM** | **×0.6** | **×0.8** | **×0.5** | **×0.6** | **×0.7** | **×0.7** |
| **HIGH** | ×1.0 | ×1.2 | ×1.2 | ×1.2 | ×1.5 | ×1.5 |

---

## 2. Performance Observée (45+ trades)

| Régime | Trades | Winrate | Avg PnL | Observations |
|--------|--------|---------|---------|--------------|
| **LOW** | 31 | **52%** | +0.10% | Sweet spot - garder valeurs base |
| **MEDIUM** | 13 | **15%** | -0.10% | Problématique → ajustement agressif |
| **HIGH** | 1 | 100% | +0.11% | Trop peu de données |

---

## 3. Diagnostic MEDIUM

### Pourquoi 15% de winrate ?
- ATR% entre 0.2-0.5% = volatilité "intermédiaire"
- Souvent des marchés en consolidation sans direction claire
- Les paramètres initiaux (TP ×0.8) étaient trop larges

### Actions Appliquées (19:00)
1. **TP très court (×0.6)** : Viser des gains plus petits mais plus fréquents
2. **BE très tôt (×0.5)** : Sécuriser dès que possible
3. **Trailing trigger tôt (×0.6)** : Capturer les mouvements courts
4. **Stagnation rapide (×0.7)** : Couper plus vite si pas de momentum

---

## 4. Prochaines Étapes

### Court terme (24h)
- Laisser tourner avec les nouveaux paramètres agressifs
- Surveiller le winrate MEDIUM (objectif: >35%)

### Moyen terme (Phase 1.4)
- Distinguer **MEDIUM TRENDING** vs **MEDIUM RANGING** via ADX
- Si ADX < 20 en MEDIUM → peut-être ne pas trader du tout

### Métriques à Surveiller
```sql
-- Ratio PnL max atteint vs ATR%
SELECT 
    market_volatility_state,
    ROUND(AVG(max_pnl_reached / entry_atr_pct_1m)::numeric, 2) as ratio_pnl_atr
FROM trade_atr_metrics tam
JOIN trades t ON tam.trade_id = t.id
WHERE t.created_at > NOW() - INTERVAL '24 hours'
GROUP BY market_volatility_state;
```
