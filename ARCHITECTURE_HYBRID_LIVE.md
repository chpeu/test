# 🏗️ Architecture Hybride : WebSocket Public + API Privée

## 📋 Vue d'Ensemble

**Système actuel conservé à 100%** pour tout ce qui ne nécessite pas de passer d'ordres réels.

**Nouveau module `LiveOrderManager`** utilisé UNIQUEMENT pour les 4 opérations critiques :
1. Ouvrir position
2. Fermer position (partielle/totale)
3. Vérifier résultat post-trade
4. Récupérer balance

---

## 🎯 Séparation des Responsabilités

### ✅ SYSTÈME ACTUEL (Inchangé)

```
┌──────────────────────────────────────────────────────────────────┐
│                   SURVEILLANCE & DÉTECTION                       │
│                   (WebSocket Public MEXC)                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  • WebSocket public MEXC                                         │
│    └─ Connexion permanente                                      │
│    └─ Prix temps réel (50-100ms de latence)                     │
│    └─ Orderbook updates                                         │
│    └─ GRATUIT, pas de rate limit                                │
│                                                                  │
│  • Détection signaux                                            │
│    └─ Analyse technique (ADX, RSI, EMA, etc.)                   │
│    └─ Patterns (breakout, SNR, divergence, etc.)                │
│    └─ Score pondéré                                             │
│    └─ Validation confluence                                     │
│                                                                  │
│  • Monitoring position                                          │
│    └─ Check TP/SL/Break-even                                    │
│    └─ Trailing stop updates                                     │
│    └─ Early invalidation                                        │
│    └─ TP escalier                                               │
│                                                                  │
│  • Calculs en RAM                                               │
│    └─ PnL théorique                                             │
│    └─ Durée position                                            │
│    └─ Conditions de fermeture                                   │
│                                                                  │
│  Fréquence: 100ms (10 checks/seconde) ✅                        │
│  Coût: GRATUIT                                                  │
│  Rate limit: AUCUN                                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 🆕 LIVE ORDER MANAGER (Nouveau)

```
┌──────────────────────────────────────────────────────────────────┐
│                    EXÉCUTION D'ORDRES                            │
│                  (API Privée MEXC - Authentifiée)                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📤 1. OUVERTURE POSITION                                        │
│     └─ createOrder(symbol, side='buy'/'sell', amount)           │
│     └─ Retour: order_id, filled_price, slippage                 │
│     └─ 1 API call                                               │
│                                                                  │
│  📤 2. FERMETURE PARTIELLE (TP partiel)                          │
│     └─ createOrder(symbol, side inverse, amount*partial_pct)    │
│     └─ Retour: order_id, filled_price, pnl_partiel              │
│     └─ 1 API call                                               │
│                                                                  │
│  📤 3. FERMETURE TOTALE (TP/SL/TS)                               │
│     └─ createOrder(symbol, side inverse, amount_remaining)      │
│     └─ Retour: order_id, filled_price, pnl_final                │
│     └─ 1 API call                                               │
│                                                                  │
│  🔍 4. VÉRIFICATION POST-TRADE                                   │
│     └─ fetchOrder(order_id) → détails ordre                     │
│     └─ fetchBalance() → solde USDT actuel                       │
│     └─ Comparaison PnL théorique vs réel                        │
│     └─ 2 API calls                                              │
│                                                                  │
│  TOTAL par trade: 4-6 API calls                                 │
│  Latence: 200-500ms par call                                    │
│  Rate limit MEXC: 10 ordres/s (largement suffisant)            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Flux Complet d'un Trade

### Étape par Étape

```
T = 0s
┌─────────────────────────────────────────────────────────────┐
│ 1. DÉTECTION SIGNAL (Système actuel - WebSocket public)    │
├─────────────────────────────────────────────────────────────┤
│ • WebSocket: Prix BTC = 50,000 USDT                        │
│ • Analyse technique: Score 8.5/10 → Signal LONG validé     │
│ • Calcul: entry=50,000, tp=50,500, sl=49,750               │
│ • Décision: OUVRIR POSITION                                │
│                                                             │
│ Latence: 50ms                                               │
│ API calls: 0                                                │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 0.05s
┌─────────────────────────────────────────────────────────────┐
│ 2. OUVERTURE (LiveOrderManager - API privée)               │
├─────────────────────────────────────────────────────────────┤
│ order_manager.open_position(                                │
│     symbol='BTC/USDT',                                      │
│     direction='LONG',                                       │
│     entry_price=50000.0,    # Prix théorique               │
│     size_usdt=100.0                                         │
│ )                                                           │
│                                                             │
│ ✅ Ordre rempli:                                            │
│    - Order ID: 123456789                                    │
│    - Prix réel: 50,002 USDT (slippage: +0.004%)            │
│    - Quantité: 0.002 BTC                                    │
│                                                             │
│ Latence: 300ms                                              │
│ API calls: 1 (createOrder)                                  │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 0.35s → T = 45s
┌─────────────────────────────────────────────────────────────┐
│ 3. MONITORING (Système actuel - WebSocket public)          │
├─────────────────────────────────────────────────────────────┤
│ Loop toutes les 100ms:                                      │
│ • WebSocket: Prix actuel = 50,350 USDT                     │
│ • Calcul PnL: +0.70%                                        │
│ • Check conditions:                                         │
│   ├─ TP (50,500) ? Non, pas encore atteint                 │
│   ├─ SL (49,750) ? Non, safe                               │
│   ├─ Break-even ? Oui, activé à +0.6%                      │
│   ├─ Trailing stop ? Oui, SL monté à 50,200               │
│   └─ Early invalidation ? Non                              │
│                                                             │
│ ... 450 checks en 45 secondes ...                          │
│                                                             │
│ T = 45s: Prix = 50,450 → TP escalier niveau 1 atteint !   │
│                                                             │
│ Latence: 50ms par check                                    │
│ API calls: 0 (tout en RAM)                                 │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 45.05s
┌─────────────────────────────────────────────────────────────┐
│ 4. FERMETURE PARTIELLE (LiveOrderManager - API privée)     │
├─────────────────────────────────────────────────────────────┤
│ order_manager.close_position(                               │
│     symbol='BTC/USDT',                                      │
│     direction='LONG',                                       │
│     entry_price=50002.0,    # Prix réel d'entrée           │
│     current_price=50450.0,  # Prix théorique               │
│     size_amount=0.002,                                      │
│     partial_pct=50.0        # Fermer 50%                   │
│ )                                                           │
│                                                             │
│ ✅ 50% fermé:                                               │
│    - Order ID: 123456790                                    │
│    - Prix réel: 50,448 USDT (slippage: -0.004%)            │
│    - PnL partiel: +0.446 USDT                              │
│    - Fees: 0.0 USDT (0% fee pairs)                         │
│    - Remaining: 0.001 BTC                                   │
│                                                             │
│ Latence: 350ms                                              │
│ API calls: 1 (createOrder)                                  │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 45.4s → T = 120s
┌─────────────────────────────────────────────────────────────┐
│ 5. MONITORING SUITE (Système actuel)                       │
├─────────────────────────────────────────────────────────────┤
│ • Continue monitoring avec 50% restant                      │
│ • Trailing stop continue de monter                         │
│ • T = 120s: Prix redescend à 50,280 → TS touché !         │
│                                                             │
│ Latence: 50ms par check                                    │
│ API calls: 0                                                │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 120.05s
┌─────────────────────────────────────────────────────────────┐
│ 6. FERMETURE TOTALE (LiveOrderManager - API privée)        │
├─────────────────────────────────────────────────────────────┤
│ order_manager.close_position(                               │
│     symbol='BTC/USDT',                                      │
│     direction='LONG',                                       │
│     entry_price=50002.0,                                    │
│     current_price=50280.0,                                  │
│     size_amount=0.001,      # 50% restant                  │
│     partial_pct=None        # Fermeture totale             │
│ )                                                           │
│                                                             │
│ ✅ Position fermée:                                         │
│    - Order ID: 123456791                                    │
│    - Prix réel: 50,278 USDT                                 │
│    - PnL final: +0.276 USDT                                │
│    - Fees: 0.0 USDT                                        │
│    - PnL TOTAL: +0.722 USDT (+0.72%)                       │
│    - Balance: 1,000.722 USDT                               │
│                                                             │
│ Latence: 320ms                                              │
│ API calls: 1 (createOrder)                                  │
└─────────────────────────────────────────────────────────────┘
                            ⬇️
T = 120.37s
┌─────────────────────────────────────────────────────────────┐
│ 7. VÉRIFICATION (LiveOrderManager - API privée)            │
├─────────────────────────────────────────────────────────────┤
│ order_manager.verify_trade_result(                          │
│     order_id='123456791',                                   │
│     expected_pnl=0.70,      # PnL théorique               │
│     expected_slippage=0.05                                  │
│ )                                                           │
│                                                             │
│ ✅ Vérification:                                            │
│    - PnL théorique: +0.70 USDT                             │
│    - PnL réel: +0.722 USDT                                 │
│    - Écart: +0.022 USDT (+3.1%) → Acceptable ✅            │
│    - Slippage moyen: 0.003%                                │
│    - Balance confirmée: 1,000.722 USDT                     │
│                                                             │
│ Latence: 250ms                                              │
│ API calls: 2 (fetchOrder + fetchBalance)                    │
└─────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÉSUMÉ DU TRADE:

Durée totale:      120 secondes
API calls total:   5 (1 open + 1 close partielle + 1 close totale + 2 verify)
Latence API:       ~300ms par call (1.5s total sur 120s = 1.25%)
WebSocket checks:  ~1200 checks (0% overhead, déjà en place)
PnL théorique:     +0.70 USDT (+0.70%)
PnL réel:          +0.722 USDT (+0.72%)
Écart:             +3.1% (excellent!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 💰 Consommation API

### Par Trade (Exemple ci-dessus)

| Opération | API Calls | Latence | Coût |
|-----------|-----------|---------|------|
| Ouverture position | 1 | 300ms | Gratuit |
| Fermeture partielle | 1 | 350ms | Gratuit |
| Fermeture totale | 1 | 320ms | Gratuit |
| Vérification | 2 | 250ms | Gratuit |
| **TOTAL** | **5 calls** | **1.22s** | **Gratuit** |

### Par Jour (10 trades/jour)

| Métrique | Valeur |
|----------|--------|
| API calls/jour | 50 calls (10 trades × 5 calls) |
| API calls/seconde | 0.0006 calls/s (< 0.001) |
| Rate limit MEXC | 10 ordres/s |
| Marge disponible | **16,666x** (énorme marge !) |

**Conclusion** : Vous êtes à **0.006%** de la limite rate limit !

---

## 🔌 Intégration dans le Code Existant

### Dans `main.py` ou `trading_manager.py`

```python
# Imports
from trading.live_order_manager import LiveOrderManager, OrderResult
from config import MEXC_API_KEY, MEXC_API_SECRET

# Initialisation (au démarrage)
live_order_manager = LiveOrderManager(
    api_key=MEXC_API_KEY,
    api_secret=MEXC_API_SECRET,
    dry_run=False  # True pour tests, False pour live
)

# ========================================================================
# 1. OUVERTURE POSITION (remplace le placement d'ordre fictif)
# ========================================================================

# AVANT (simulation):
# position = {
#     'symbol': symbol,
#     'entry': current_price,  # Prix théorique
#     ...
# }

# APRÈS (live):
result = live_order_manager.open_position(
    symbol=symbol,
    direction='LONG',
    entry_price=current_price,  # Prix théorique
    size_usdt=position_size
)

if result.success:
    # Créer position avec PRIX RÉEL d'entrée
    position = {
        'symbol': symbol,
        'entry': result.filled_price,  # 🔥 Prix réel, pas théorique
        'size': result.filled_amount,
        'order_id': result.order_id,
        'slippage_on_entry': result.actual_slippage_pct,
        ...
    }
    logger.info(f"✅ Position live ouverte | Slippage: {result.actual_slippage_pct:.3f}%")
else:
    logger.error(f"❌ Échec ouverture: {result.error_message}")
    # Ne pas créer la position


# ========================================================================
# 2. FERMETURE PARTIELLE (TP partiel)
# ========================================================================

# AVANT (simulation):
# position['partial_tp_sold'] = True
# position['size_remaining'] = position['size'] * 0.5

# APRÈS (live):
result = live_order_manager.close_position(
    symbol=position['symbol'],
    direction=position['direction'],
    entry_price=position['entry'],  # Prix réel d'entrée
    current_price=current_price,    # Prix théorique actuel
    size_amount=position['size'],
    partial_pct=50.0  # 50% du trade
)

if result.success:
    position['partial_tp_sold'] = True
    position['size_remaining'] = result.filled_amount  # Quantité restante

    # Logger résultat réel
    logger.info(
        f"✅ TP partiel exécuté | "
        f"PnL réel: {result.actual_pnl_usdt:+.2f} USDT | "
        f"Slippage: {result.actual_slippage_pct:.3f}%"
    )


# ========================================================================
# 3. FERMETURE TOTALE (TP/SL/TS)
# ========================================================================

# AVANT (simulation):
# pnl = calculate_pnl(position['entry'], current_price, ...)

# APRÈS (live):
result = live_order_manager.close_position(
    symbol=position['symbol'],
    direction=position['direction'],
    entry_price=position['entry'],
    current_price=current_price,
    size_amount=position.get('size_remaining', position['size']),
    partial_pct=None  # Fermeture totale
)

if result.success:
    # Utiliser PnL RÉEL au lieu de théorique
    trade_result = {
        'symbol': position['symbol'],
        'pnl_theoretical': calculate_pnl(...),      # Pour comparaison
        'pnl_real': result.actual_pnl_usdt,         # 🔥 PnL réel
        'fees_real': result.actual_fees_usdt,       # 🔥 Fees réels
        'slippage_real': result.actual_slippage_pct,# 🔥 Slippage réel
        'balance_after': result.balance_after,      # 🔥 Balance réelle
        'latency_ms': result.latency_ms,
        ...
    }

    # Logger écart
    pnl_discrepancy = abs(result.actual_pnl_usdt - trade_result['pnl_theoretical'])
    logger.info(
        f"✅ Position fermée | "
        f"PnL théo: {trade_result['pnl_theoretical']:+.2f} USDT | "
        f"PnL réel: {result.actual_pnl_usdt:+.2f} USDT | "
        f"Écart: {pnl_discrepancy:.3f} USDT"
    )

    # ⚠️ Alerter si écart trop important
    if pnl_discrepancy > 0.5:  # > 0.50 USDT
        logger.warning(f"⚠️ ÉCART PNL IMPORTANT: {pnl_discrepancy:.2f} USDT")


# ========================================================================
# 4. VÉRIFICATION POST-TRADE (optionnel)
# ========================================================================

verification = live_order_manager.verify_trade_result(
    order_id=result.order_id,
    expected_pnl=trade_result['pnl_theoretical'],
    expected_slippage=0.05
)

if verification['verified']:
    logger.info(f"✅ Trade vérifié | Balance: {verification['balance']:.2f} USDT")
```

---

## 📊 Monitoring & Alertes

### Dashboard Live à Ajouter

```python
# Statistiques à afficher en temps réel
stats = live_order_manager.get_stats()

dashboard_data = {
    'orders_placed': stats['orders_placed'],
    'orders_filled': stats['orders_filled'],
    'success_rate': stats['success_rate'],
    'avg_latency_ms': stats['avg_latency_ms'],

    # Calculer moyennes sur les trades
    'avg_slippage_pct': calculate_avg_slippage(),
    'avg_pnl_discrepancy': calculate_avg_discrepancy(),

    # Health check
    'api_healthy': stats['avg_latency_ms'] < 500,
    'slippage_acceptable': avg_slippage < 0.10,
}

# Afficher dans frontend
return JSONResponse(dashboard_data)
```

### Alertes Automatiques

```python
# Dans la boucle principale
if result.actual_slippage_pct > 0.15:  # > 0.15% slippage
    send_telegram_alert(
        f"⚠️ SLIPPAGE ÉLEVÉ: {result.actual_slippage_pct:.2f}% "
        f"sur {position['symbol']}"
    )

if result.latency_ms > 1000:  # > 1 seconde latence
    send_telegram_alert(
        f"⚠️ LATENCE ÉLEVÉE: {result.latency_ms:.0f}ms"
    )

if pnl_discrepancy > 1.0:  # > 1 USDT écart
    send_telegram_alert(
        f"⚠️ ÉCART PNL: théo={theo:.2f} réel={real:.2f} "
        f"(écart={pnl_discrepancy:.2f} USDT)"
    )
```

---

## ✅ Avantages de Cette Architecture

### 1. **Performances**
- ✅ Latence WebSocket : 50-100ms (inchangé)
- ✅ Pas de ralentissement sur le monitoring
- ✅ API calls minimaux (5 par trade)
- ✅ Rate limits non problématiques (0.006% de la limite)

### 2. **Fiabilité**
- ✅ Prix RÉELS d'exécution (pas de théorique)
- ✅ PnL RÉEL confirmé par l'exchange
- ✅ Slippage RÉEL mesuré
- ✅ Balance vérifiée après chaque trade

### 3. **Sécurité**
- ✅ API privée utilisée uniquement quand nécessaire
- ✅ Moins d'exposition (4-5 calls vs 1000+ si tout en API)
- ✅ Dry-run mode pour tests
- ✅ Statistiques pour monitoring

### 4. **Coût**
- ✅ WebSocket public : GRATUIT
- ✅ API privée : Gratuit aussi (MEXC ne facture pas les API calls)
- ✅ Fees : 0% sur paires sélectionnées

---

## 🚀 Prochaines Étapes

1. **Tester en Dry-Run**
   ```bash
   python trading/live_order_manager.py
   # Vérifier que l'exemple fonctionne
   ```

2. **Intégrer dans main.py**
   - Remplacer les placements d'ordres fictifs
   - Utiliser `LiveOrderManager` pour open/close
   - Logger les PnL réels vs théoriques

3. **Tester 1 semaine en Paper Trading**
   - Mode `dry_run=True`
   - Vérifier latences moyennes
   - Analyser écarts PnL théorique vs simulé

4. **Test Micro-Capital ($100)**
   - Mode `dry_run=False`
   - Paires BTC/ETH/SOL uniquement
   - 5-10 trades maximum
   - Arrêter si slippage > 0.15%

5. **Scale Up Progressivement**
   - Si tests OK : passer à $500
   - Si encore OK : passer à capital réel
   - Monitoring strict 24/7

---

**Cette architecture vous permet de garder la réactivité de votre système actuel tout en ayant la garantie d'exécution réelle et la vérification post-trade ! 🎯**
