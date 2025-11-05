# 🔧 CORRECTION PARAMÈTRES FONCTIONNELS

**Date**: 2025-11-03  
**Status**: ✅ **EN COURS**

---

## 🐛 PROBLÈMES IDENTIFIÉS

### 1. ❌ **Volume Multiplier non fonctionnel**

**Problème** :
- `scan_pair_for_setup()` appelle `analyze_pair()` **sans** `volume_multiplier`
- Le compteur de validation (`volumeStats`) est calculé côté frontend mais jamais envoyé au backend
- `/api/analyze/{symbol}` n'accepte pas `volume_multiplier` en paramètre

**Impact** :
- Le slider volume multiplier n'a aucun effet
- Le compteur de validation ne sert à rien

---

### 2. ❌ **Confluence hardcodée**

**Problème** :
- `scan_pair_for_setup()` utilise `use_confluence=False` hardcodé
- Ne lit pas depuis `TRADING_CONFIG` ou le frontend

---

### 3. ❌ **TP/SL Mode non synchronisé**

**Problème** :
- `PositionConfig` est initialisé avec valeurs par défaut
- Ne lit pas `TRADING_CONFIG['tp_sl_mode']` au démarrage
- Les modifications de config ne sont pas reflétées dans `PositionConfig`

---

### 4. ❌ **4 Seuils non modifiables à la volée**

**Problème** :
- SNR, breakout, wick ratio, DI gap sont dans `TRADING_CONFIG`
- Mais aucun endpoint pour les modifier à la volée
- Modifications nécessitent redémarrage du serveur

---

### 5. ❌ **Capital et Risk non passés**

**Problème** :
- Frontend calcule `accountSize` et `riskPerTrade`
- Mais ne les passe pas à `/api/position/open`
- Position size est calculé côté frontend, pas backend

---

## ✅ CORRECTIONS APPLIQUÉES

### 1. ✅ Correction Volume Multiplier

**Fichier** : `main.py`

**a) `/api/analyze/{symbol}`** :
```python
@app.get("/api/analyze/{symbol}")
async def api_analyze_symbol(
    symbol: str, 
    tf: str = Query('1m', description="Timeframe (pour compatibilité)"),
    use_confluence: bool = Query(None, description="True = 1m ET 5m, False = 1m OU 5m"),
    volume_multiplier: float = Query(None, description="Multiplicateur de volume 0.1-2.0")
):
    # Récupère depuis TRADING_CONFIG si non fourni
    if volume_multiplier is None:
        volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
    
    # Utilise analyze_pair avec volume_multiplier
    analysis = await analyzer.analyze_pair(
        symbol, 
        volume_multiplier=volume_multiplier,
        use_confluence=use_confluence,
        ...
    )
```

**b) `scan_pair_for_setup()`** :
```python
async def scan_pair_for_setup(symbol: str):
    # Récupère depuis TRADING_CONFIG
    from config import TRADING_CONFIG
    use_confluence = TRADING_CONFIG.get('use_confluence', False)
    volume_multiplier = TRADING_CONFIG.get('volume_multiplier', 1.0)
    
    # Utilise avec les paramètres
    analysis = await analyzer.analyze_pair(
        symbol, 
        volume_multiplier=volume_multiplier,
        use_confluence=use_confluence,
        ...
    )
```

---

### 2. ✅ Correction Confluence

- `scan_pair_for_setup()` lit maintenant depuis `TRADING_CONFIG`
- `/api/analyze/{symbol}` accepte `use_confluence` en paramètre
- Fallback sur `TRADING_CONFIG` si non fourni

---

### 3. ✅ Correction TP/SL Mode

**Fichier** : `main.py` - `init_instances()`

```python
if not position_config and PositionConfig:
    from config import TRADING_CONFIG
    position_config = PositionConfig()
    
    # 🔥 FIX: Configurer depuis TRADING_CONFIG
    tp_sl_mode = TRADING_CONFIG.get('tp_sl_mode', 'FIXE')
    position_config.use_atr = (tp_sl_mode == 'ATR')
    position_config.fixed_tp_pct = TRADING_CONFIG.get('tp_percent', 0.25)
    position_config.fixed_sl_pct = TRADING_CONFIG.get('sl_percent', 0.25)
    # ... etc
```

---

### 4. ✅ Endpoints pour modifier config à la volée

**Nouveaux endpoints** :

**a) GET `/api/config`** : Récupérer la config actuelle
```json
{
  "volume_multiplier": 1.0,
  "use_confluence": false,
  "tp_sl_mode": "FIXE",
  "tp_percent": 0.25,
  "sl_percent": 0.25,
  "snr_threshold": 0.3,
  "breakout_threshold": 0.3,
  "wick_ratio_max": 2.5,
  "di_gap_min": 5,
  "di_gap_adx_threshold": 25
}
```

**b) POST `/api/config`** : Modifier la config
```json
POST /api/config
{
  "volume_multiplier": 0.8,
  "use_confluence": true,
  "snr_threshold": 0.25,
  ...
}
```

**Réponse** :
```json
{
  "status": "updated",
  "updated": {
    "volume_multiplier": 0.8,
    "use_confluence": true,
    ...
  }
}
```

---

### 5. ✅ Capital dans position

**Fichier** : `main.py` - `api_open_position()`

```python
position = position_manager.open_position(...)

# 🔥 FIX: Stocker capital si fourni
if 'capital' in data:
    position.capital = data.get('capital')
```

---

## 🔍 PROBLÈME COMPTEUR DE VALIDATION

**Analyse** :
- Le frontend calcule `volumeStats.validated / volumeStats.total`
- Mais cette valeur n'est jamais envoyée au backend
- Le backend utilise toujours `TRADING_CONFIG['volume_multiplier']` (1.0 par défaut)

**Solution nécessaire** :
- Le frontend doit envoyer le `volume_multiplier` calculé à chaque appel `/api/analyze/{symbol}`
- OU modifier `TRADING_CONFIG['volume_multiplier']` via `/api/config` quand le slider change

---

## 📋 CHECKLIST

- [x] Volume multiplier passé dans `scan_pair_for_setup()`
- [x] Volume multiplier accepté dans `/api/analyze/{symbol}`
- [x] Confluence lu depuis `TRADING_CONFIG`
- [x] TP/SL mode initialisé depuis `TRADING_CONFIG`
- [x] Endpoints GET/POST `/api/config` créés
- [x] Capital stocké dans position si fourni
- [ ] **TODO**: Frontend doit envoyer volume_multiplier calculé à chaque analyse
- [ ] **TODO**: Frontend doit mettre à jour TRADING_CONFIG via `/api/config` quand slider change

---

## 🚀 PROCHAINES ÉTAPES

1. **Modifier frontend** pour envoyer `volume_multiplier` calculé à chaque analyse
2. **OU** modifier frontend pour mettre à jour `/api/config` quand le slider change
3. **Vérifier** que le compteur de validation fonctionne côté frontend

---

## 📝 NOTES

- Les modifications de `TRADING_CONFIG` sont en mémoire (pas persistées)
- Un redémarrage du serveur réinitialise les valeurs
- Pour persistance, il faudrait sauvegarder dans un fichier JSON



