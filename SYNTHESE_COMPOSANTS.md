# SYNTHÈSE COMPOSANTS FRONTEND & USAGE WEBSOCKET/REST

| Composant | Fichier | WebSocket | REST | Paramètres Modifiés | Fallback | Status |
|-----------|---------|-----------|------|-------------------|----------|--------|
| BotControls | BotControls.svelte | `sendCommand()` start/stop | /api/scanner/start, /api/scanner/stop | - | ✅ (REST) | ✅ Migré |
| SettingsPanel | SettingsPanel.svelte | `sendCommandViaWS('update_config')` | /api/config/update | sl_percent, tp_percent, trailing_trigger_pnl | ✅ (REST) | ✅ Migré |
| VariablesPanel | VariablesPanel.svelte | `sendCommandViaWS('update_config')` | /api/config/save | 40+ paramètres (patterns, TP/SL, escalier, trailing) | ✅ (REST) | ✅ Migré |
| PositionCard | PositionCard.svelte | `sendCommandViaWS('close_position')` | /api/position/close | - | ✅ (REST) | ✅ Migré |
| NotificationSettings | NotificationSettings.svelte | ❌ Non utilisé | /api/config, /api/settings | Telegram settings | ❌ (N/A) | ⚠️ REST only |
| ExportPanel | ExportPanel.svelte | ❌ Non utilisé | /api/export | - | ❌ (N/A) | ⚠️ REST only |
| TradeHistory | TradeHistory.svelte | ❌ Non utilisé | /api/trades | - | ❌ (N/A) | ⚠️ REST only |
| GlobalStats | GlobalStats.svelte | ❌ Non utilisé | /api/stats | - | ❌ (N/A) | ⚠️ REST only |
| StatsPanel | StatsPanel.svelte | ❌ Non utilisé | /api/stats | - | ❌ (N/A) | ⚠️ REST only |
| ScannerPanel | ScannerPanel.svelte | ❌ Non utilisé | /api/scanner/status | - | ❌ (N/A) | ⚠️ REST only |
| ConnectionStatus | ConnectionStatus.svelte | ✅ (listener) | ❌ Non utilisé | - | ❌ (N/A) | ✅ Migré |
| LogViewer | LogViewer.svelte | ✅ (listener) | ❌ Non utilisé | - | ❌ (N/A) | ✅ Migré |

---

## Détail des Paramètres WebSocket (update_config)

### Sauvegardés via WebSocket ✅

#### 1. Validation Setups (VariablesPanel)
```
- use_confluence: boolean
- volume_multiplier: float (0.1-2.0)
- min_score_required: float
```

#### 2. TP/SL Mode (VariablesPanel)
```
- tp_sl_mode: FIXE | ATR | TP_MULTI
- tp_percent: float (%)
- sl_percent: float (%)
- atr_mult_tp: float
- atr_mult_sl: float
- atr_min: float
- atr_max: float
```

#### 3. Escalier TP_MULTI (VariablesPanel)
```
- escalier_level1_pnl: float
- escalier_level1_size: int (%)
- escalier_level2_pnl: float
- escalier_level2_size: int (%)
- escalier_level3_pnl: float
- escalier_level3_size: int (%)
- escalier_level4_pnl: float
- escalier_level4_size: int (%)
```

#### 4. Trailing Stop (VariablesPanel)
```
- trailing_enabled: boolean
- trailing_trigger_pnl: float
- trailing_atr_multiplier: float
- trailing_min_distance: float
- trailing_max_distance: float
```

#### 5. Patterns Techniques (VariablesPanel)
```
- use_breakout: boolean
- use_snr: boolean
- use_wick: boolean
- use_divergence: boolean
- snr_threshold: float
- breakout_threshold: float
- wick_ratio_max: float
- di_gap_min: float
- di_gap_adx_threshold: float
```

#### 6. Candlestick Patterns (VariablesPanel)
```
- use_engulfing: boolean
- use_hammer: boolean
- use_shooting_star: boolean
- use_doji: boolean
- use_marubozu: boolean
- use_morning_star: boolean
- use_evening_star: boolean
```

#### 7. Money Management (VariablesPanel)
```
- account_size: float
- risk_per_trade: float
```

#### 8. Indicateurs (VariablesPanel)
```
- trend_timeframe: string ('15m', '1h', etc)
- optimal_atr_min_1m: float
- optimal_atr_max_1m: float
- optimal_atr_min_5m: float
- optimal_atr_max_5m: float
```

#### 9. Stop Loss Simple (SettingsPanel)
```
- stopLossPercent: float (frontend)
  → Backend: sl_percent
- takeProfitPercent: float (frontend)
  → Backend: tp_percent
- trailingStopPercent: float (frontend)
  → Backend: trailing_trigger_pnl
```

### NON SAUVEGARDÉS (En mémoire)

```
❌ Toutes les configurations - CRITIQUE!
   - Perdues au redémarrage
   - Pas de persistance BD
   - Pas de versionning
   - Pas d'historique
```

---

## Analyse des Endpoints REST

### Endpoints Lisez-Seul (Read)
```
GET /api/trades              - Historique trades
GET /api/stats               - Statistiques
GET /api/setups/rejected     - Setups rejetés
GET /api/setups/validated    - Setups validés
GET /api/export              - Exporter données (CSV/JSON)
GET /api/settings            - Lire paramètres Telegram
GET /api/config              - Lire configuration
GET /api/health              - Health check
```

### Endpoints Écritur (Write)
```
POST /api/backtest           - Lancer backtest
POST /api/optimize           - Lancer optimisation ML
POST /api/settings           - Sauver paramètres Telegram
POST /api/config/update      - Mettre à jour config (LEGACY)
POST /api/config/save        - Sauver config (LEGACY)
POST /api/scanner/start      - Démarrer scanner (LEGACY)
POST /api/scanner/stop       - Arrêter scanner (LEGACY)
POST /api/position/close     - Clôturer position (LEGACY)
DELETE /api/trades/{id}      - Supprimer trade
```

### Problème Identifié
```
⚠️ 2 systèmes parallèles:
   1. WebSocket: Préféré, fallback REST
   2. REST: Endpoints legacy encore présents
   
❌ Confusion possible:
   - /api/config/update vs /api/config/save
   - sendCommandViaWS vs fetch REST
   - Deux chemins pour même action
```

---

## Fichiers à Modifier/Supprimer

### SUPPRIMER (Nettoyage Socket.IO)
```
❌ frontend/src/lib/utils/socket.js (246 lignes - LEGACY)
   - Import Socket.IO non utilisé
   - Événements legacy
   - Remplacé par websocket.ts

❌ frontend/package.json
   - "socket.io-client": "^4.7.4"
   - Supprimer cette dépendance

❌ requirements.txt (Backend)
   - python-socketio==5.11.0
   - Supprimer après vérifier migrations
```

### MODIFIER (Migration WebSocket)
```
✅ frontend/src/lib/components/VariablesPanel.svelte
   - Ajouter écoute événement 'config_change' via websocket.ts
   - Supprimer références socket.js (ligne 250)
   - Implémenter multi-client sync

✅ frontend/src/lib/components/SettingsPanel.svelte
   - Ajouter écoute événement 'config_change'
   - Synchroniser avec backend en temps réel

✅ main.py (Backend)
   - Implémenter sauvegarde config en BD
   - Ajouter persistance TRADING_CONFIG
   - Charger au démarrage depuis BD

✅ frontend/src/lib/utils/websocket.ts
   - Ajouter support 'config_change' event
   - Implémenter brodcaster config_change
```

### CRÉER (Nouveaux Fichiers)
```
✅ core/config_database.py
   - Classe ConfigDatabase (CRUD)
   - Table: TRADING_CONFIG
   - Champs: key, value, updated_at, version

✅ Tests
   - test_websocket_config.py
   - test_config_persistence.py
   - test_multi_client_sync.py
```

---

## Commandes WebSocket Implémentées

### Status: Implémentées ✅

```python
Command: 'start_scanner'
Response: {'status': 'started', 'is_scanning': True}

Command: 'stop_scanner'
Response: {'status': 'stopped', 'is_scanning': False}

Command: 'close_position'
Params: {reason: str, exit_price: float}
Response: {'status': 'closed', ...trade_result}

Command: 'update_config'
Params: {key1: value1, key2: value2, ...}
Response: {'updated': {key1: value1, ...}, 'success': True}

Command: 'set_log_level'
Params: {level: 'DEBUG'|'INFO'|'WARNING'|'ERROR'}
Response: {'level': 'INFO', 'success': True}

Command: 'export_state'
Params: {}
Response: {bot_state_dict}
```

### Status: À Implémenter ⚠️

```python
Command: 'save_config' (Persistance)
Params: {all config}
Response: {'saved': True, 'timestamp': ..., 'version': ...}

Command: 'load_config' (Charger version)
Params: {version: int}
Response: {loaded_config}

Command: 'list_config_versions'
Params: {}
Response: [{version, timestamp, changes}, ...]

Command: 'config_rollback'
Params: {version: int}
Response: {'rolled_back': True, 'to_version': ...}
```

---

## Recommandations Immédiates

### Urgent (Jour 1-2)
```
1. Retirer Socket.IO complètement
   - Supprimer socket.js
   - Supprimer package.json entry
   - Vérifier plus d'imports

2. Implémenter persistance config basique
   - Créer table TRADING_CONFIG
   - Sauver à chaque update_config
   - Charger au démarrage

3. Ajouter 'config_change' broadcast
   - Implémenter dans websocket.ts
   - Recevoir dans VariablesPanel
   - Update stores
```

### Important (Jour 3-4)
```
4. Nettoyer fallbacks REST
   - Décider: WebSocket primary ou REST?
   - Supprimer code inutile
   - Tester tous les chemins

5. Ajouter validation
   - Frontend: min/max inputs
   - Backend: validation complète
   - Error messages clairs
```

### Nice-to-have (Semaine 2)
```
6. Versionning config
   - Historique changements
   - Rollback versions
   - Export/import configs

7. Documentation
   - Tous les paramètres
   - Exemples WebSocket
   - Architecture WebSocket
```

