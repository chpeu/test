# 🚀 Guide Complet - Live Trading MEXC

**Date:** 25 novembre 2025, 20:00 UTC+01:00  
**Status:** Prêt pour tests en mode DRY_RUN

---

## 📋 Vue d'Ensemble

Ton système de live trading MEXC est **déjà implémenté** ! Voici ce qui existe :

### ✅ Code Existant

1. **`trading/live_order_manager.py`** (534 lignes)
   - Gestion ordres via API MEXC (ccxt)
   - Modes: DRY_RUN (simulation) + LIVE (réel)
   - Fonctions: open_position(), close_position()
   
2. **`api/live_trading_endpoints.py`** (351 lignes)
   - Endpoints REST pour configuration
   - GET `/api/live/stats` - Stats live
   - GET `/api/live/config` - Config actuelle
   - POST `/api/live/config` - Modifier config
   
3. **`api/mexc.py`** (143 lignes)
   - Client API MEXC avec retry/circuit breaker
   - fetch_ticker(), fetch_ohlcv(), fetch_order_book()
   
4. **`config_live_trading.py`** (226 lignes)
   - Configuration recommandée pour live
   - TP/SL ajustés pour latence API
   - Filtres qualité plus stricts
   
5. **`frontend/src/lib/components/LiveTradingPanel.svelte`**
   - Interface UI pour configuration
   - Activation mode PAPER/LIVE
   - Saisie API keys
   - Monitoring stats

---

## 🔧 Configuration Initiale

### Étape 1: Obtenir Clés API MEXC

1. **Se connecter à MEXC:**
   - URL: https://www.mexc.com/
   - Aller dans: **Account → API Management**

2. **Créer une API Key:**
   - Nom: `trade_cursor_bot`
   - Permissions requises:
     - ✅ **Spot Trading** (Enable Trading)
     - ⚠️ **PAS** Withdraw (sécurité)
   
3. **Sauvegarder immédiatement:**
   - ✅ **API Key** (commence par `mx0...`)
   - ✅ **Secret Key** (affiché une seule fois)
   
4. **Whitelist IP (Optionnel mais recommandé):**
   - Ajouter ton IP publique
   - Ou laisser "Unrestricted" pour démarrer

### Étape 2: Ajouter Clés dans `.env`

Édite le fichier `.env` à la racine du projet :

```bash
# Telegram Configuration (existant)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# PostgreSQL (existant)
POSTGRES_HOST=localhost
...

# ========== MEXC API KEYS ==========
MEXC_API_KEY=ton_api_key_ici
MEXC_API_SECRET=ton_api_secret_ici
MEXC_TESTNET=false
```

**⚠️ IMPORTANT:** Le fichier `.env` est dans `.gitignore`, tes clés ne seront JAMAIS commitées.

### Étape 3: Créer Fichier Config Live

Le fichier `config_live_persistent.json` sera créé automatiquement au premier démarrage, mais tu peux le créer manuellement :

```json
{
  "trading_mode": "PAPER",
  "dry_run": true,
  "api_key_mexc": "",
  "api_secret_mexc": "",
  "max_slippage_pct": 0.15,
  "max_latency_ms": 1000,
  "max_pnl_discrepancy_pct": 20,
  "alerts_enabled": true,
  "telegram_notify_live_trades": true
}
```

---

## 🚀 Démarrage Mode DRY_RUN (Tests)

### 1. Vérifier Installation

```bash
# Vérifier que ccxt est installé
pip show ccxt

# Si pas installé
pip install ccxt
```

### 2. Démarrer Backend

```bash
# Terminal 1 - Backend
cd "c:\Users\sebta\Documents\clone github\test\test"
python main.py
```

**Logs attendus:**
```
✅ LiveOrderManager initialisé | Mode: DRY_RUN | Testnet: False
🔄 Live Trading: Mode PAPER activé
```

### 3. Démarrer Frontend

```bash
# Terminal 2 - Frontend
cd frontend
npm run dev
```

### 4. Ouvrir Interface

```
http://localhost:5173
```

Aller dans le panneau **Live Trading** (menu latéral).

---

## 🎮 Interface Live Trading

### Section 1: Mode Trading

```
┌─────────────────────────────────────┐
│ Mode de Trading Actuel              │
├─────────────────────────────────────┤
│  🟢 PAPER TRADING (Simulation)      │
│  ⚪ LIVE TRADING (Réel)              │
└─────────────────────────────────────┘
```

**Actions:**
- **PAPER:** Simulation complète (pas de connexion API)
- **LIVE:** Trading réel avec API MEXC

### Section 2: Dry-Run (Mode Simulation)

```
┌─────────────────────────────────────┐
│ Dry-Run (Simulation Ordres)         │
├─────────────────────────────────────┤
│  ✅ Activé (recommandé pour tests)  │
│  Simuler ordres sans exécution      │
└─────────────────────────────────────┘
```

**Recommandation:** Laisser activé pendant tests (minimum 1 semaine).

### Section 3: API Keys MEXC

```
┌─────────────────────────────────────┐
│ Clés API MEXC                        │
├─────────────────────────────────────┤
│ API Key:    mx0vDqyH...  [👁️ Masqué] │
│ API Secret: ********     [👁️ Masqué] │
│                                      │
│ [Tester Connexion API]               │
│ Status: ⚠️ Non testé                 │
└─────────────────────────────────────┘
```

**Actions:**
1. Saisir API Key
2. Saisir API Secret
3. Cliquer **Tester Connexion API**
4. Vérifier: ✅ **Connexion réussie**

### Section 4: Alertes & Limites

```
┌─────────────────────────────────────┐
│ Alertes & Limites                    │
├─────────────────────────────────────┤
│ Max Slippage:      0.15%             │
│ Max Latence:       1000ms            │
│ Max Discrepancy:   20%               │
│                                      │
│ ✅ Alertes Telegram activées         │
└─────────────────────────────────────┘
```

### Section 5: Statistiques Live

```
┌─────────────────────────────────────┐
│ Statistiques Live                    │
├─────────────────────────────────────┤
│ Ordres Placés:    0                  │
│ Ordres Réussis:   0                  │
│ Ordres Échoués:   0                  │
│ Taux Succès:      0%                 │
│ Latence Moyenne:  0ms                │
│                                      │
│ API Status: 🟢 Healthy               │
└─────────────────────────────────────┘
```

---

## 🧪 Tests Recommandés (Mode DRY_RUN)

### Phase 1: Test Connexion API (5 minutes)

```bash
# Via Frontend
1. Ouvrir Live Trading Panel
2. Saisir API keys
3. Cliquer "Tester Connexion API"

# Ou via curl
curl http://localhost:8000/api/live/config
curl http://localhost:8000/api/live/stats
```

**Résultat attendu:**
```json
{
  "mode": "PAPER",
  "live_enabled": false,
  "api_healthy": true
}
```

### Phase 2: Test Simulation Ordres (1 semaine)

```bash
# Configuration
1. Mode: LIVE
2. Dry-Run: ✅ ACTIVÉ
3. API keys: Renseignées

# Lancer scanner
python main.py
```

**Ce qui va se passer:**
1. Scanner détecte setups normalement
2. Quand setup détecté → `LiveOrderManager.open_position()` est appelé
3. **Dry-Run:** Ordre simulé (PAS envoyé à MEXC)
4. Logs: `✅ [DRY_RUN] Ordre simulé | Latence: 5ms`

**Logs attendus:**
```
📤 OUVERTURE POSITION: BTC/USDT LONG | Prix: 42500 | Taille: 10 USDT | Mode: DRY_RUN
✅ [DRY_RUN] Ordre simulé | Latence: 5ms
💰 Balance simulée: 1000.00 USDT

📤 FERMETURE POSITION: BTC/USDT | PNL: +2.34% | Mode: DRY_RUN
✅ [DRY_RUN] Fermeture simulée | PNL: +0.23 USDT
```

**Métriques à surveiller:**
- ✅ Latence moyenne < 100ms (simulation)
- ✅ Aucune erreur API
- ✅ PNL simulé cohérent
- ✅ Durée trades >= 5 secondes (voir `config_live_trading.py`)

### Phase 3: Test Connexion API Réelle (1 jour)

```bash
# Configuration
1. Mode: LIVE
2. Dry-Run: ❌ DÉSACTIVÉ (DANGER!)
3. Size: 5 USDT (MINIMUM pour tests réels)

# ⚠️ ATTENTION: Trades réels avec argent réel!
```

**Recommandation:** Faire seulement 5-10 trades pour valider, puis repasser en DRY_RUN.

---

## 📊 Workflow Complet

### 1. Scanner Détecte Setup

```python
# core/scanner.py
setup = analyze_pair(symbol)

if setup['is_opportunity']:
    # Signal détecté
    logger.info(f"🎯 Setup détecté: {symbol} {setup['direction']}")
```

### 2. Vérification ML (Optionnel V2)

```python
# Si ml_v2_filter_enabled = True
from optimization.scanner_ml_integration import should_filter_setup_with_ml_v2

should_reject, reason = should_filter_setup_with_ml_v2(
    klines=klines,
    symbol=symbol,
    min_expected_pnl=0.5
)

if should_reject:
    logger.info(f"🚫 ML V2: {reason}")
    return  # Ne pas ouvrir position
```

### 3. Ouvrir Position via LiveOrderManager

```python
# main.py (ou position_manager.py)
from main import live_order_manager

if live_order_manager:
    # Mode LIVE avec API MEXC
    result = live_order_manager.open_position(
        symbol='BTC/USDT',
        direction='LONG',
        entry_price=42500,
        size_usdt=10,
        leverage=1  # Spot = 1
    )
    
    if result.success:
        logger.info(f"✅ Position ouverte: {result.order_id}")
        logger.info(f"   Prix rempli: {result.filled_price}")
        logger.info(f"   Slippage: {result.actual_slippage_pct:.3f}%")
        logger.info(f"   Latence: {result.latency_ms:.0f}ms")
    else:
        logger.error(f"❌ Erreur: {result.error_message}")
else:
    # Mode PAPER (simulation locale)
    logger.info("📄 Mode PAPER: Position simulée localement")
```

### 4. Monitoring Position

```python
# Le système actuel (WebSocket) continue de monitorer
# Position suivie normalement avec TP/SL
```

### 5. Fermer Position

```python
if live_order_manager:
    result = live_order_manager.close_position(
        symbol='BTC/USDT',
        direction='LONG',
        exit_price=43500,
        size_usdt=10
    )
    
    logger.info(f"💰 PNL réel: {result.actual_pnl_usdt:.2f} USDT")
    logger.info(f"💸 Fees: {result.actual_fees_usdt:.4f} USDT")
```

---

## 🔐 Sécurité

### Protection API Keys

1. **`.env` dans `.gitignore`:** ✅ Déjà fait
2. **Masquage dans logs:** ✅ API keys masquées dans logs
3. **Masquage dans frontend:** ✅ `***{last_4_chars}`

### Rate Limits MEXC

**Limites officielles:**
- **20 requêtes/seconde** (général)
- **10 ordres/seconde** (trading)

**Protection implémentée:**
```python
# config_live_trading.py
"max_orders_per_second": 5,    # Sécurité 50%
"max_requests_per_second": 10,  # Sécurité 50%
```

### Emergency Stop

```bash
# Via Frontend
Bouton "🚨 EMERGENCY STOP"
→ Ferme toutes positions immédiatement
→ Désactive live trading

# Via Code
from main import live_order_manager
live_order_manager.emergency_stop()
```

---

## 📁 Fichiers Importants

```
trade-cursor/
├── .env                              # ⚠️ API KEYS (jamais commit!)
├── config_live_trading.py            # Config recommandée live
├── config_live_persistent.json       # Config UI (créé auto)
│
├── trading/
│   ├── live_order_manager.py         # ✅ Gestion ordres MEXC
│   └── paper_trading_manager.py      # Simulation paper
│
├── api/
│   ├── mexc.py                       # ✅ Client API MEXC
│   └── live_trading_endpoints.py    # ✅ Endpoints REST
│
└── frontend/src/lib/components/
    └── LiveTradingPanel.svelte       # ✅ UI Configuration
```

---

## 🐛 Debugging

### Problème 1: "API Keys invalides"

**Symptôme:**
```
❌ Erreur API MEXC: Invalid API key
```

**Solution:**
1. Vérifier API Key commence par `mx0`
2. Vérifier Secret Key (64 caractères)
3. Vérifier permissions: **Spot Trading** activé
4. Vérifier IP whitelist (ou unrestricted)

### Problème 2: "Rate limit exceeded"

**Symptôme:**
```
❌ Rate limit exceeded: 429
```

**Solution:**
```python
# Réduire dans config_live_trading.py
"max_orders_per_second": 3,  # Au lieu de 5
```

### Problème 3: "Ordre rejeté"

**Symptôme:**
```
❌ Ordre rejeté: Insufficient balance
```

**Solution:**
1. Vérifier balance USDT: `curl https://api.mexc.com/api/v3/account`
2. Réduire `size_usdt` dans config
3. Vérifier min notional (minimum 5 USDT sur MEXC)

### Problème 4: "Slippage trop élevé"

**Symptôme:**
```
⚠️ Slippage 0.25% > max 0.15%
```

**Solution:**
```python
# Augmenter tolérance dans .env ou UI
"max_slippage_pct": 0.25  # Au lieu de 0.15
```

---

## 📊 Métriques de Succès

### Phase DRY_RUN (Validation)

| Métrique | Objectif | Seuil Critique |
|----------|----------|----------------|
| **Latence API** | < 500ms | < 1000ms |
| **Taux Succès Ordres** | > 95% | > 90% |
| **Slippage Moyen** | < 0.10% | < 0.15% |
| **Durée Trade Moyenne** | > 30s | > 5s |
| **PNL Discrepancy** | < 10% | < 20% |

### Phase LIVE (Production)

| Métrique | Objectif | Seuil Critique |
|----------|----------|----------------|
| **Win Rate** | > 55% | > 50% |
| **Profit Factor** | > 1.5 | > 1.2 |
| **Max Drawdown** | < 15% | < 25% |
| **Sharpe Ratio** | > 1.0 | > 0.5 |

---

## ✅ Checklist Avant Live

- [ ] API Keys MEXC créées et testées
- [ ] `.env` configuré avec keys
- [ ] Mode DRY_RUN testé pendant 1 semaine minimum
- [ ] Latence API < 500ms moyenne
- [ ] Taux succès ordres > 95%
- [ ] Slippage moyen < 0.10%
- [ ] Balance MEXC >= 100 USDT minimum
- [ ] Telegram alertes configurées
- [ ] Emergency stop testé
- [ ] Backup de la config

---

## 🎯 Prochaines Étapes

### Aujourd'hui
1. ✅ Créer API keys MEXC
2. ✅ Ajouter dans `.env`
3. ✅ Tester connexion API (UI)
4. ✅ Vérifier logs backend

### Cette Semaine (DRY_RUN)
5. Lancer en mode DRY_RUN
6. Surveiller métriques (latence, slippage)
7. Valider que durée trades >= 5s
8. Ajuster `config_live_trading.py` si besoin

### Semaine Prochaine (LIVE Tests)
9. 5-10 trades réels avec 5 USDT
10. Analyser résultats vs simulation
11. Ajuster configuration finale
12. Passer en production (10-20 USDT par trade)

---

## 💡 Conseils Importants

### 1. Commencer Petit
- **DRY_RUN:** 1-2 semaines minimum
- **Premier LIVE:** 5 USDT par trade max
- **Après validation:** 10-20 USDT par trade
- **Production:** 30-50 USDT par trade

### 2. Surveiller Métriques
- Latence API (< 500ms)
- Slippage (< 0.10%)
- Win Rate (> 55%)
- Durée trades (> 30 secondes)

### 3. Configuration Conservatrice
```python
# config_live_trading.py - RECOMMANDÉ
"tp_percent": 1.0,   # +1.0% (ne pas réduire)
"sl_percent": 0.5,   # -0.5% (ne pas réduire)
"min_score_required": 8.0,  # Filtrer trades faibles
```

### 4. Ne PAS
- ❌ Passer en LIVE sans tester DRY_RUN
- ❌ Commencer avec > 10 USDT par trade
- ❌ Désactiver emergency stop
- ❌ Ignorer alertes latence/slippage
- ❌ Trader sans stop-loss

---

## 📞 Support

### Logs à Vérifier

```bash
# Backend
tail -f logs/backend.log | grep LIVE

# Ordres
tail -f logs/backend.log | grep "OUVERTURE POSITION"
tail -f logs/backend.log | grep "FERMETURE POSITION"

# Erreurs API
tail -f logs/backend.log | grep "❌"
```

### Debug Mode

```python
# main.py
DEBUG_ENABLED = True  # Activer logs détaillés
```

---

**Dernière mise à jour:** 25 novembre 2025, 20:00 UTC+01:00  
**Auteur:** Cascade AI  
**Version:** 1.0  
**Status:** ✅ PRÊT POUR TESTS DRY_RUN

---

## 🎓 Ressources

- **Documentation MEXC API:** https://mexcdevelop.github.io/apidocs/spot_v3_en/
- **CCXT Documentation:** https://docs.ccxt.com/
- **Telegram Bot Setup:** Déjà configuré dans `.env`
- **Support MEXC:** https://www.mexc.com/support

---

Tu peux maintenant commencer les tests ! Commence par ajouter tes API keys dans `.env`, puis teste la connexion via l'UI. 🚀
