# 🎯 Patterns Actifs - Sous-onglet Setups

## Vue d'ensemble

Les **4 patterns actifs** sont des types de configurations de prix (setups) que le scanner peut détecter pour identifier des opportunités de trading. Vous pouvez activer/désactiver chaque pattern individuellement.

---

## 📊 Les 4 Patterns

### 1️⃣ **Breakout Pattern** (Cassure)

**Définition :** Détecte les cassures de niveaux clés (support/résistance).

**Comment ça fonctionne :**
- Le prix casse un niveau de résistance (LONG) ou support (SHORT)
- La cassure est confirmée par un volume élevé
- L'ATR valide la force du mouvement

**Conditions détectées :**
- Breakout confirmé par volume
- Distance de cassure > `breakout_threshold × ATR`
- Momentum haussier/baissier

**Exemple :**
```
Prix: 100 USDT
Résistance: 101 USDT
Le prix passe à 101.5 USDT avec volume x2
→ BREAKOUT détecté (signal LONG)
```

**Quand l'activer :**
- ✅ Marchés tendanciels forts
- ✅ Après une consolidation
- ❌ Éviter en range étroit

---

### 2️⃣ **SNR Pattern** (Support & Resistance)

**Définition :** Détecte les rebonds sur support ou résistance.

**Comment ça fonctionne :**
- Le prix touche un support (LONG) ou résistance (SHORT)
- Le niveau est validé par des tests précédents
- Le rebond est confirmé par les indicateurs

**Conditions détectées :**
- Prix proche d'un SNR validé
- Signal-to-Noise Ratio > `snr_threshold`
- RSI en zone de survente/surachat

**Exemple :**
```
Prix: 100 USDT
Support: 99.5 USDT (testé 3x)
Le prix touche 99.6 et rebondit avec RSI=30
→ SNR SUPPORT détecté (signal LONG)
```

**Quand l'activer :**
- ✅ Marchés en range
- ✅ Niveaux clés bien définis
- ❌ Éviter en forte tendance

---

### 3️⃣ **Wick Pattern** (Rejet de Bougie)

**Définition :** Détecte les rejets de prix par de longues mèches (wicks).

**Comment ça fonctionne :**
- Une bougie a une longue mèche (rejet de prix)
- Le corps de la bougie est petit
- Le ratio mèche/corps dépasse un seuil

**Conditions détectées :**
- Wick ratio > `wick_ratio_max`
- Rejet à un niveau clé (SNR)
- Volume de confirmation

**Exemple :**
```
Bougie:
- Open: 100
- High: 102 (longue mèche haute)
- Close: 100.2
- Low: 99.8

Wick ratio = (102 - 100.2) / (100.2 - 99.8) = 4.5
→ WICK REJECTION détecté (signal SHORT si à résistance)
```

**Quand l'activer :**
- ✅ Retournements de tendance
- ✅ Zones de rejet (SNR)
- ❌ Éviter en consolidation

---

### 4️⃣ **Divergence Pattern** (Divergence RSI/MACD)

**Définition :** Détecte les divergences entre prix et indicateurs.

**Comment ça fonctionne :**
- Le prix fait un nouveau high/low
- Le RSI ou MACD ne confirme PAS
- Signale un affaiblissement de la tendance

**Conditions détectées :**
- **Divergence Haussière** : Prix baisse mais RSI monte
- **Divergence Baissière** : Prix monte mais RSI baisse
- MACD confirme la divergence

**Exemple :**
```
Divergence Haussière (LONG):
- Prix: 100 → 98 → 96 (bas descendants)
- RSI: 25 → 28 → 32 (bas ascendants)
→ DIVERGENCE détectée (retournement probable)
```

**Quand l'activer :**
- ✅ Fin de tendance
- ✅ Retournements
- ❌ Éviter en range

---

## 🎛️ Configuration des Patterns

### Activé/Désactivé

Chaque pattern peut être activé ou désactivé individuellement :

```javascript
// Frontend - VariablesPanel
use_breakout: true    // Activer Breakout
use_snr: true         // Activer SNR
use_wick: true        // Activer Wick
use_divergence: true  // Activer Divergence
```

**Impact :**
- Si **désactivé** : Le scanner ignore ce type de setup
- Si **activé** : Le scanner détecte et signale ce pattern

### Seuils Associés

Chaque pattern a des seuils configurables :

| Pattern | Seuil | Description |
|---------|-------|-------------|
| **Breakout** | `breakout_threshold` | Distance min de cassure (× ATR) |
| **SNR** | `snr_threshold` | Signal-to-Noise Ratio min |
| **Wick** | `wick_ratio_max` | Ratio max mèche/corps |
| **Divergence** | `di_gap_min` | Gap min DI+/DI- |

---

## 🎯 Combinaison de Patterns

Le bot peut détecter **plusieurs patterns simultanément** sur la même paire.

**Exemple :**
```
BTCUSDT:
- Breakout détecté (cassure résistance)
- SNR détecté (rebond support)
- Divergence détectée (RSI diverge)

Score total = Somme des patterns validés
→ Signal TRÈS FORT si 3+ patterns
```

**Confluence :**
Si `use_confluence = true`, le bot exige au moins 2 patterns différents pour valider un signal.

---

## 💡 Recommandations

### Tous Activés (Défaut)
```javascript
use_breakout: true
use_snr: true
use_wick: true
use_divergence: true
```

**Avantage :** Capture tous les types d'opportunités
**Inconvénient :** Plus de signaux (dont certains faibles)

### Sélectif (Tendance)
```javascript
use_breakout: true     // ✅
use_snr: false         // ❌ (inutile en tendance)
use_wick: false        // ❌
use_divergence: true   // ✅ (retournements)
```

**Avantage :** Signaux de qualité en tendance
**Inconvénient :** Manque les rebonds SNR

### Sélectif (Range)
```javascript
use_breakout: false    // ❌ (peu de cassures)
use_snr: true          // ✅ (rebonds)
use_wick: true         // ✅ (rejets)
use_divergence: false  // ❌
```

**Avantage :** Optimisé pour marchés latéraux
**Inconvénient :** Manque les breakouts

---

## 🔍 Détection dans le Code

**Note :** Actuellement, ces patterns sont des **checkboxes d'activation** dans le frontend. L'implémentation backend complète nécessite :

1. Ajouter les variables dans `config.py` :
```python
"use_breakout": True,
"use_snr": True,
"use_wick": True,
"use_divergence": True
```

2. Modifier le scanner pour vérifier ces flags avant de scorer un pattern.

3. Filtrer les conditions selon les patterns activés.

---

## 📋 Résumé

| Pattern | Type de Marché | Signal | Force |
|---------|----------------|--------|-------|
| **Breakout** | Tendance | Cassure niveau | Forte |
| **SNR** | Range | Rebond support/résistance | Moyenne |
| **Wick** | Retournement | Rejet de prix | Forte |
| **Divergence** | Retournement | Affaiblissement tendance | Forte |

**Conseil :** Commencez avec tous activés, puis désactivez selon votre style de trading et les conditions de marché.

---

**Dernière mise à jour :** 2025-01-09
**Version :** Trade Cursor v7.0
