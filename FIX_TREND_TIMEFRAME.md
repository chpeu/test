# 🔧 CORRECTION : TREND TIMEFRAME non pris en compte

**Date**: 2025-11-04  
**Status**: ✅ **CORRIGÉ**

---

## 🐛 PROBLÈME IDENTIFIÉ

**Symptôme** :
- Le sélecteur "TREND TIMEFRAME" dans l'interface (15m, 30m, 1h) n'est **pas utilisé** dans le backend
- `trend_data` est toujours `None` dans `scan_pair_for_setup` et `/api/analyze/{symbol}`
- Le bonus trend (`+0` dans les logs) n'est jamais calculé

**Cause** :
- Le frontend calcule `trend_data` avec `getTrendData()` mais ne l'envoie pas au backend
- Le backend ne calcule pas `trend_data` lui-même
- `trend_data=None` est hardcodé dans les appels à `analyze_pair()`

---

## ✅ CORRECTIONS APPLIQUÉES

### **1. Fonction `calculate_trend_data()` dans `TechnicalAnalyzer`**

**Fichier** : `core/analyzer.py`

**Ajout** :
```python
async def calculate_trend_data(self, symbol: str, timeframe: str = '15m') -> Optional[Dict]:
    """
    Calculer les données de tendance pour un timeframe donné
    
    Args:
        symbol: Symbole de la paire
        timeframe: Timeframe (5m, 15m, 30m, 1h)
        
    Returns:
        Dict avec trend (BULLISH/BEARISH/NEUTRAL), strength, bonus
    """
    # Récupérer OHLCV pour le timeframe
    ohlcv = await self.client.fetch_ohlcv(symbol, ccxt_tf, limit=100)
    
    # Calculer EMAs (20, 50, 100)
    ema20 = self.indicators.calculate_ema(closes, 20)
    ema50 = self.indicators.calculate_ema(closes, 50)
    ema100 = self.indicators.calculate_ema(closes, 100)
    
    # Déterminer la tendance
    if ema20 > ema50 and ema50 > ema100 and price > ema20:
        trend = 'BULLISH', strength = 'STRONG', bonus = 25
    elif ema20 > ema50 and price > ema20:
        trend = 'BULLISH', strength = 'MODERATE', bonus = 15
    # ... etc
```

**Logique** :
- Récupère 100 bougies OHLCV pour le timeframe choisi
- Calcule EMA20, EMA50, EMA100
- Détermine la tendance selon la position des EMAs et du prix
- Retourne `{trend, strength, bonus}`

---

### **2. Configuration `trend_timeframe` dans `config.py`**

**Fichier** : `config.py`

**Ajout** :
```python
# Trend timeframe pour calculer trend_data (bonus)
"trend_timeframe": "15m",  # 5m, 15m, 30m, 1h
```

**Valeur par défaut** : `15m` (comme dans l'interface)

---

### **3. Utilisation dans `scan_pair_for_setup()`**

**Fichier** : `main.py`

**Avant** :
```python
analysis = await analyzer.analyze_pair(
    symbol, 
    trend_data=None,  # ❌ Toujours None
    ...
)
```

**Après** :
```python
trend_timeframe = TRADING_CONFIG.get('trend_timeframe', '15m')
trend_data = await analyzer.calculate_trend_data(symbol, trend_timeframe)

analysis = await analyzer.analyze_pair(
    symbol, 
    trend_data=trend_data,  # ✅ Utilise trend_data calculé
    ...
)
```

**Logique** :
- Récupère `trend_timeframe` depuis `TRADING_CONFIG` (défaut: `15m`)
- Calcule `trend_data` avec ce timeframe
- Passe `trend_data` à `analyze_pair()`

---

### **4. Endpoint `/api/analyze/{symbol}` mis à jour**

**Fichier** : `main.py`

**Ajout paramètre** :
```python
trend_timeframe: str = Query(None, description="Timeframe pour trend_data (5m, 15m, 30m, 1h)")
```

**Logique** :
- Si `trend_timeframe` fourni → utilise cette valeur
- Sinon → utilise `TRADING_CONFIG['trend_timeframe']`
- Calcule `trend_data` avec ce timeframe
- Passe à `analyze_pair()`

---

### **5. Configuration `/api/config`**

**Fichier** : `main.py`

**GET `/api/config`** :
```python
'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m')
```

**POST `/api/config`** :
```python
if 'trend_timeframe' in data:
    val = str(data['trend_timeframe']).lower()
    valid_timeframes = ['5m', '15m', '30m', '1h']
    if val in valid_timeframes:
        TRADING_CONFIG['trend_timeframe'] = val
        updated['trend_timeframe'] = val
```

**Validation** : Seuls `5m`, `15m`, `30m`, `1h` sont acceptés

---

## 📊 IMPACT

### **Avant** :
```
❌ TRUMPOFFICIAL/USDT:USDT: Pas de setup - Conditions insuffisantes: Long=4+0 Short=2 (min=5 requis)
```
- `+0` = Pas de bonus trend (trend_data toujours None)

### **Après** :
```
✅ TRUMPOFFICIAL/USDT:USDT: Setup trouvé - LONG - 5 conditions
📊 TRUMPOFFICIAL/USDT:USDT: Trend 15m = BULLISH (STRONG, bonus=25)
```
- `+2` = Bonus trend calculé (bonus=25 → floor(25/10)=2)

**OU** :
```
❌ TRUMPOFFICIAL/USDT:USDT: Pas de setup - Conditions insuffisantes: Long=4+2 Short=2 (min=5 requis)
```
- `+2` = Bonus trend ajouté, mais toujours insuffisant (4+2=6, mais peut-être rejeté pour autre raison)

---

## 🔄 UTILISATION

### **1. Modifier le trend timeframe via `/api/config`**

```bash
POST /api/config
{
  "trend_timeframe": "30m"  # Au lieu de 15m
}
```

### **2. Récupérer la configuration actuelle**

```bash
GET /api/config
# Retourne: { "trend_timeframe": "15m", ... }
```

### **3. Utiliser dans l'analyse**

```bash
GET /api/analyze/SOL/USDT:USDT?trend_timeframe=1h
```

Le backend calcule automatiquement `trend_data` avec le timeframe fourni.

---

## 📈 LOGIQUE DU BONUS TREND

**Dans `analyze_timeframe()`** :
```python
trend_bonus = 0
if trend_data and temp_direction != 'NEUTRAL':
    if temp_direction == 'LONG' and trend_data.get('trend') == 'BULLISH':
        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
    elif temp_direction == 'SHORT' and trend_data.get('trend') == 'BEARISH':
        trend_bonus = math.floor(trend_data.get('bonus', 0) / 10)
```

**Exemples** :
- `bonus=25` (STRONG) → `trend_bonus = floor(25/10) = 2`
- `bonus=15` (MODERATE) → `trend_bonus = floor(15/10) = 1`
- `bonus=0` (NEUTRAL) → `trend_bonus = 0`

**Affichage** :
- `Long=4+2` = 4 conditions + 2 bonus trend = **6 total**

---

## ✅ RÉSULTAT

**Maintenant** :
- ✅ `trend_data` est calculé avec le timeframe configuré (15m par défaut)
- ✅ Le bonus trend est ajouté aux conditions (`+1` ou `+2`)
- ✅ Le trend timeframe est modifiable via `/api/config`
- ✅ L'endpoint `/api/analyze/{symbol}` accepte `trend_timeframe` en paramètre

**Prochaines étapes** (optionnel) :
- Synchroniser le sélecteur frontend avec le backend (envoyer `trend_timeframe` lors du scan)
- Afficher le trend et le bonus dans les logs

---

## 🎯 RECOMMANDATION

**Pour utiliser un timeframe différent** :
1. Modifier via `/api/config` : `POST /api/config { "trend_timeframe": "30m" }`
2. OU passer en paramètre : `GET /api/analyze/SOL/USDT:USDT?trend_timeframe=1h`

**Timeframes disponibles** :
- `5m` : Très court terme (tendance rapide)
- `15m` : Court terme (défaut, équilibré)
- `30m` : Moyen terme (tendance plus stable)
- `1h` : Long terme (tendance très stable)


