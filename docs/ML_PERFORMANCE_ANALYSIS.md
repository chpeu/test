# Analyse des Performances ML - Novembre 2024

## Contexte

Après unification du filtrage ML (tous les modèles utilisent les mêmes 1075 trades filtrés sur la config actuelle), les performances sont limitées.

## Résultats Actuels

| Modèle | Accuracy | F1 | Precision | Recall | AUC |
|--------|----------|-----|-----------|--------|-----|
| Ensemble | 43.3% | 0.596 | 42.7% | 98.9% | 0.508 |
| GradientBoosting | 42.8% | 0.594 | 42.5% | 98.9% | 0.486 |
| XGBoost | 42.3% | 0.592 | 42.3% | 98.9% | 0.466 |

## Diagnostic

### Pourquoi les performances sont faibles ?

1. **Win rate proche de 50%** (48.6%)
   - Les trades sont quasi-aléatoires du point de vue des features actuelles
   - Les modèles ne trouvent pas de pattern discriminant

2. **AUC proche de 0.5** (0.466-0.508)
   - AUC = 0.5 signifie "aléatoire"
   - Les modèles ne font pas mieux que le hasard

3. **Recall 98.9% mais Precision 42%**
   - Les modèles prédisent presque tout comme "WIN"
   - Ils apprennent juste la proportion de la classe majoritaire

### Ce n'est PAS un problème de code

Le code fonctionne correctement. Le problème est **fondamental** :
- Soit les features ne capturent pas le signal réel
- Soit le marché est fondamentalement imprévisible à court terme

## Solutions Proposées

### Court Terme (sans modifier la stratégie)

1. **Utiliser le modèle comme FILTRE NÉGATIF**
   - Ne pas prendre les trades que le modèle prédit comme "LOSS" avec haute confiance
   - Seuil inversé : rejeter si proba_win < 0.3 au lieu d'accepter si > 0.5

2. **Combiner avec d'autres signaux**
   - Utiliser le score total existant (min_score_required)
   - Le ML devient un filtre supplémentaire, pas le décideur principal

### Moyen Terme (améliorer les features)

1. **Ajouter des features de contexte marché**
   ```python
   # Volatilité globale du marché (BTC comme proxy)
   market_volatility = btc_atr_24h
   
   # Tendance générale
   market_trend = btc_ema_50 > btc_ema_200
   
   # Corrélation avec BTC
   symbol_btc_correlation = correlation_24h
   ```

2. **Features de momentum avancées**
   ```python
   # Accélération du RSI
   rsi_acceleration = rsi - rsi_prev
   
   # Divergence MACD-Prix
   macd_price_divergence = macd_trend != price_trend
   ```

3. **Features de volume améliorées**
   ```python
   # Volume relatif par heure
   volume_vs_hourly_avg = volume / avg_volume_at_hour
   
   # Accumulation/Distribution
   ad_line = cumsum(volume * (close - open) / (high - low))
   ```

### Long Terme (repenser l'approche)

1. **Passer en classification multi-classe**
   - BIG_WIN (>0.5%)
   - SMALL_WIN (0-0.5%)
   - SMALL_LOSS (0 à -0.3%)
   - BIG_LOSS (<-0.3%)
   
   Se concentrer uniquement sur prédire les BIG_WIN

2. **Régression sur le PNL puis filtrage**
   - Prédire le PNL% attendu
   - Ne prendre que les trades avec PNL prédit > seuil

3. **Reinforcement Learning**
   - Agent qui apprend à optimiser le PNL cumulé
   - Prend en compte les coûts de transaction

## Recommandation Immédiate

**Ne pas utiliser le ML comme filtre principal pour l'instant.**

Configuration suggérée :
```json
{
    "ml_filter_enabled": false,
    "ml_min_confidence": 0.65
}
```

Continuer à collecter des données et réanalyser quand :
- > 2000 trades avec config cohérente
- Nouvelles features de contexte marché ajoutées

## Métriques à Surveiller

Pour que le ML soit utile :
- **AUC > 0.60** (actuellement 0.50)
- **Precision > 55%** quand Recall > 30% (actuellement impossible)
- **F1 > 0.55** (actuellement 0.59 mais trompeur car recall artificiellement haut)

## Conclusion

L'unification du filtrage est **correcte** et les modèles sont **cohérents**. Mais le signal dans les données est **trop faible** pour que le ML soit prédictif. C'est un résultat valide - il vaut mieux le savoir que d'utiliser un modèle qui ne fonctionne pas.
