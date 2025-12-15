# 🔌 Intégration LiveOrderManager dans le Code Existant

## 📋 Vue d'Ensemble

Ce guide montre comment intégrer le `LiveOrderManager` dans votre code existant pour permettre le trading live avec MEXC.

**Modifications requises :**
1. Ajouter `LiveOrderManager` à `main.py`
2. Modifier `position_manager.py` pour utiliser `LiveOrderManager`
3. Ajouter configuration `LIVE_TRADING_MODE`
4. Logger comparaisons PnL théorique vs réel

---

## 🔧 Étape 1 : Configuration (`config.py`)

### Ajouter au début de `config.py` :

```python
# ============================================================================
# LIVE TRADING CONFIGURATION
# ============================================================================

# Mode de trading
# 'PAPER' = Simulation complète (sessions actuelles)
# 'LIVE' = Trading réel avec MEXC API
TRADING_MODE = 'PAPER'  # 🔥 Changer à 'LIVE' pour trading réel

# Mode dry-run du LiveOrderManager
# True = Simule les ordres (latence + slippage) sans passer d'ordres réels
# False = Passe les ordres réels sur MEXC
LIVE_DRY_RUN = True  # 🔥 Mettre False UNIQUEMENT quand prêt pour le live

# API Keys MEXC (requises si TRADING_MODE='LIVE')
MEXC_API_KEY = os.getenv('MEXC_API_KEY', '')
MEXC_API_SECRET = os.getenv('MEXC_API_SECRET', '')

# Charger config adaptée selon le mode
if TRADING_MODE == 'LIVE':
    # Charger config live (TP/SL plus larges, min 5s par trade, etc.)
    try:
        from config_live_trading import LIVE_TRADING_CONFIG
        # Merger avec TRADING_CONFIG
        TRADING_CONFIG.update(LIVE_TRADING_CONFIG)
        logger.info("✅ Configuration LIVE chargée")
    except ImportError:
        logger.warning("⚠️ config_live_trading.py introuvable, utilisation config standard")
```

---

## 🔧 Étape 2 : Initialisation dans `main.py`

### Au début de `main.py`, après les imports :

```python
# Imports existants...
from core.position_manager import PositionManager

# 🔥 NOUVEAU: Import LiveOrderManager
from trading.live_order_manager import LiveOrderManager

# Variables globales existantes...
position_manager: Optional[PositionManager] = None

# 🔥 NOUVEAU: Variable globale LiveOrderManager
live_order_manager: Optional[LiveOrderManager] = None


def init_instances():
    """Initialiser les instances (existant)"""
    global position_manager, live_order_manager  # 🔥 Ajouter live_order_manager

    # Initialisation existante...
    if not position_manager:
        position_manager = PositionManager(...)

    # 🔥 NOUVEAU: Initialiser LiveOrderManager si mode LIVE
    if not live_order_manager and TRADING_MODE == 'LIVE':
        if not MEXC_API_KEY or not MEXC_API_SECRET:
            logger.error("❌ API Keys MEXC manquantes ! Définir MEXC_API_KEY et MEXC_API_SECRET")
            raise ValueError("API Keys MEXC requises pour TRADING_MODE='LIVE'")

        live_order_manager = LiveOrderManager(
            api_key=MEXC_API_KEY,
            api_secret=MEXC_API_SECRET,
            dry_run=LIVE_DRY_RUN
        )

        logger.info(
            f"✅ LiveOrderManager initialisé | "
            f"Mode: {'DRY_RUN' if LIVE_DRY_RUN else 'LIVE RÉEL'} | "
            f"⚠️ ATTENTION: Ordres {'SIMULÉS' if LIVE_DRY_RUN else 'RÉELS'}"
        )
```

---

## 🔧 Étape 3 : Modification de `PositionManager`

### Dans `core/position_manager.py` :

#### 3.1 Ajouter `live_order_manager` au constructeur

```python
class PositionManager:
    def __init__(
        self,
        config: Optional[PositionConfig] = None,
        live_order_manager: Optional['LiveOrderManager'] = None  # 🔥 NOUVEAU
    ):
        """
        Args:
            config: Configuration position
            live_order_manager: Gestionnaire ordres live (None = paper trading)
        """
        self.config = config or PositionConfig()
        self.live_order_manager = live_order_manager  # 🔥 NOUVEAU
        # ... reste du code existant
```

#### 3.2 Modifier `open_position()` pour utiliser LiveOrderManager

```python
def open_position(
    self,
    symbol: str,
    direction: str,
    entry: float,
    size: float,
    atr: float = 0.5,
    atr5m: Optional[float] = None,
    confirmed_by: str = "System",
    scalability_data: Optional[Dict[str, Any]] = None,
    condition_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Ouvrir une position"""

    if self.active_position:
        raise ValueError("Une position est déjà active")

    # Calculer TP/SL (code existant)
    # ... (votre code actuel)

    # 🔥 NOUVEAU: Si mode LIVE, passer ordre réel via LiveOrderManager
    entry_price_actual = entry  # Par défaut, prix théorique
    slippage_on_entry = 0.0
    order_id_entry = None
    latency_entry_ms = None

    if self.live_order_manager:
        logger.info(
            f"📤 LIVE: Ouverture position {symbol} {direction} | "
            f"Prix théorique: {entry} | "
            f"Taille: {size} USDT"
        )

        # Passer ordre réel (ou simulé si dry_run=True)
        result = self.live_order_manager.open_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry,
            size_usdt=size
        )

        if not result.success:
            logger.error(f"❌ Échec ouverture position: {result.error_message}")
            raise ValueError(f"Échec ouverture: {result.error_message}")

        # Utiliser prix RÉEL d'exécution
        entry_price_actual = result.filled_price
        slippage_on_entry = result.actual_slippage_pct
        order_id_entry = result.order_id
        latency_entry_ms = result.latency_ms

        logger.info(
            f"✅ LIVE: Position ouverte | "
            f"Prix réel: {entry_price_actual} | "
            f"Slippage: {slippage_on_entry:.3f}% | "
            f"Order ID: {order_id_entry} | "
            f"Latence: {latency_entry_ms:.0f}ms"
        )
    else:
        logger.info(f"📝 PAPER: Position simulée {symbol} {direction}")

    # Créer position avec prix réel (ou théorique si paper)
    self.active_position = Position(
        symbol=symbol,
        direction=direction,
        entry=entry_price_actual,  # 🔥 Prix réel, pas théorique
        size=size,
        sl=sl,
        tp=tp,
        atr=atr,
        atr5m=atr5m,
        confirmed_by=confirmed_by,
        scalability_data=scalability_data,
        condition_types=condition_types or [],
        # 🔥 NOUVEAU: Infos live trading
        order_id=order_id_entry,
        slippage_on_entry=slippage_on_entry,
        latency_entry_ms=latency_entry_ms
    )

    # ... reste du code existant (TP escalier, etc.)

    return self.active_position.to_dict()
```

#### 3.3 Modifier `close_position()` pour utiliser LiveOrderManager

```python
def close_position(self, exit_price: float, reason: str) -> Dict[str, Any]:
    """Fermer la position active"""

    if not self.active_position:
        raise ValueError("Aucune position active à fermer")

    # Calculer durée
    duration = int(time.time() - self.active_position.start_time)

    # 🔥 NOUVEAU: Si mode LIVE, passer ordre de fermeture
    exit_price_actual = exit_price
    pnl_usdt_actual = None
    fees_actual = None
    slippage_on_exit = None
    balance_after = None
    order_id_close = None
    latency_close_ms = None

    if self.live_order_manager:
        # Déterminer si fermeture partielle ou totale
        partial_pct = None
        size_to_close = self.active_position.size

        if self.active_position.partial_tp_sold and self.active_position.size_remaining:
            # Fermeture après TP partiel
            size_to_close = self.active_position.size_remaining
            logger.info(f"📤 LIVE: Fermeture position restante (après TP partiel)")
        elif reason == 'TP_PARTIAL':
            # Fermeture partielle
            from config import TRADING_CONFIG
            partial_pct = TRADING_CONFIG.get('partial_tp_percent', 50.0)
            logger.info(f"📤 LIVE: Fermeture partielle {partial_pct}%")
        else:
            # Fermeture totale
            logger.info(f"📤 LIVE: Fermeture totale ({reason})")

        # Calculer quantité en unités de l'actif
        # Note: size est en USDT, on doit convertir en unités de l'actif
        amount = size_to_close / self.active_position.entry

        # Passer ordre de fermeture
        result = self.live_order_manager.close_position(
            symbol=self.active_position.symbol,
            direction=self.active_position.direction,
            entry_price=self.active_position.entry,
            current_price=exit_price,  # Prix théorique
            size_amount=amount,
            partial_pct=partial_pct
        )

        if not result.success:
            logger.error(f"❌ Échec fermeture position: {result.error_message}")
            # Ne pas raise, utiliser prix théorique en fallback
        else:
            # Utiliser données RÉELLES de l'exchange
            exit_price_actual = result.filled_price
            pnl_usdt_actual = result.actual_pnl_usdt
            fees_actual = result.actual_fees_usdt
            slippage_on_exit = result.actual_slippage_pct
            balance_after = result.balance_after
            order_id_close = result.order_id
            latency_close_ms = result.latency_ms

            logger.info(
                f"✅ LIVE: Position fermée | "
                f"Prix réel: {exit_price_actual} | "
                f"PnL réel: {pnl_usdt_actual:+.2f} USDT | "
                f"Fees: {fees_actual:.4f} USDT | "
                f"Slippage: {slippage_on_exit:.3f}% | "
                f"Balance: {balance_after:.2f} USDT | "
                f"Latence: {latency_close_ms:.0f}ms"
            )

    # Calculer PnL théorique (pour comparaison)
    pnl_data_theoretical = self.pnl_calculator.calculate_realized_pnl(
        position=self.active_position.to_dict(),
        exit_price=exit_price,  # Prix théorique
        fees_percent=0.0
    )

    # Utiliser PnL réel si disponible, sinon théorique
    if pnl_usdt_actual is not None:
        net_pnl_usdt = pnl_usdt_actual - (fees_actual or 0.0)
        net_pnl_pct = (net_pnl_usdt / self.active_position.size) * 100

        # Calculer écart théorique vs réel
        pnl_discrepancy = abs(pnl_usdt_actual - pnl_data_theoretical['pnl_usdt_gross'])
        pnl_discrepancy_pct = (pnl_discrepancy / abs(pnl_data_theoretical['pnl_usdt_gross'])) * 100 if pnl_data_theoretical['pnl_usdt_gross'] != 0 else 0

        # ⚠️ Logger si écart important
        if pnl_discrepancy_pct > 10:  # > 10%
            logger.warning(
                f"⚠️ ÉCART PNL IMPORTANT: {pnl_discrepancy_pct:.1f}% | "
                f"Théorique: {pnl_data_theoretical['pnl_usdt_gross']:+.2f} USDT | "
                f"Réel: {pnl_usdt_actual:+.2f} USDT | "
                f"Écart: {pnl_discrepancy:+.2f} USDT"
            )
    else:
        # Mode paper trading
        net_pnl_usdt = pnl_data_theoretical['net_pnl']
        net_pnl_pct = pnl_data_theoretical['pnl_pct']
        pnl_discrepancy = 0.0
        pnl_discrepancy_pct = 0.0

    # Construire résultat
    result = {
        'symbol': self.active_position.symbol,
        'direction': self.active_position.direction,
        'entry': self.active_position.entry,
        'exit': exit_price_actual,  # 🔥 Prix réel
        'exit_price': exit_price_actual,

        # PnL
        'pnl_theoretical': pnl_data_theoretical['pnl_usdt_gross'],  # Pour comparaison
        'pnl_real': pnl_usdt_actual,  # None si paper
        'net_pnl_usdt': net_pnl_usdt,  # 🔥 PnL réel si live, théorique si paper
        'net_pnl_pct': net_pnl_pct,
        'pnl_discrepancy': pnl_discrepancy,
        'pnl_discrepancy_pct': pnl_discrepancy_pct,

        # Coûts
        'fees': fees_actual if fees_actual is not None else 0.0,
        'slippage_entry': self.active_position.slippage_on_entry or 0.0,
        'slippage_exit': slippage_on_exit or 0.0,
        'slippage_total': (self.active_position.slippage_on_entry or 0.0) + (slippage_on_exit or 0.0),

        # Infos live
        'order_id_entry': getattr(self.active_position, 'order_id', None),
        'order_id_close': order_id_close,
        'balance_after': balance_after,
        'latency_entry_ms': getattr(self.active_position, 'latency_entry_ms', None),
        'latency_close_ms': latency_close_ms,

        # Autres
        'duration': duration,
        'duration_seconds': duration,
        'reason': reason,
        'close_reason': reason,
        'timestamp': self.active_position.timestamp,
        'opened_at': datetime.fromtimestamp(self.active_position.start_time).isoformat(),
        'closed_at': datetime.now(timezone.utc).isoformat(),

        # Mode
        'trading_mode': 'LIVE' if self.live_order_manager else 'PAPER',
        'dry_run': self.live_order_manager.dry_run if self.live_order_manager else None,
    }

    # ... reste du code existant (analytics, telegram, etc.)

    # Reset position
    self.active_position = None

    return result
```

---

## 🔧 Étape 4 : Passer LiveOrderManager à PositionManager

### Dans `main.py`, modifier `init_instances()` :

```python
def init_instances():
    """Initialiser les instances"""
    global position_manager, live_order_manager

    # Initialiser LiveOrderManager AVANT PositionManager
    if not live_order_manager and TRADING_MODE == 'LIVE':
        # ... (code d'init déjà montré ci-dessus)
        pass

    # Initialiser PositionManager avec LiveOrderManager
    if not position_manager:
        position_manager = PositionManager(
            config=position_config,
            live_order_manager=live_order_manager  # 🔥 Passer LiveOrderManager
        )
```

---

## 🔧 Étape 5 : Modifier `Position` Dataclass

### Dans `core/position_manager.py`, ajouter champs live :

```python
@dataclass
class Position:
    """Position de trading"""
    symbol: str
    direction: str
    entry: float
    size: float
    sl: float
    tp: float
    atr: float
    atr5m: Optional[float] = None
    # ... champs existants ...

    # 🔥 NOUVEAUX champs pour live trading
    order_id: Optional[str] = None  # Order ID exchange
    slippage_on_entry: float = 0.0  # Slippage à l'ouverture
    latency_entry_ms: Optional[float] = None  # Latence ouverture
```

---

## 📊 Étape 6 : Dashboard Live Trading

### Ajouter endpoint dans `main.py` :

```python
@app.get("/api/live/stats")
async def get_live_stats():
    """Statistiques live trading"""
    if not live_order_manager:
        return JSONResponse({
            'mode': 'PAPER',
            'live_enabled': False
        })

    stats = live_order_manager.get_stats()

    return JSONResponse({
        'mode': 'LIVE' if not live_order_manager.dry_run else 'DRY_RUN',
        'live_enabled': True,
        'dry_run': live_order_manager.dry_run,

        # Statistiques ordres
        'orders_placed': stats['orders_placed'],
        'orders_filled': stats['orders_filled'],
        'orders_failed': stats['orders_failed'],
        'success_rate': stats['success_rate'],

        # Latences
        'avg_latency_ms': stats['avg_latency_ms'],

        # Health check
        'api_healthy': stats['avg_latency_ms'] < 500,
        'warnings': []
    })
```

---

## 🎯 Étape 7 : Test Progressif

### 7.1 Phase Paper Trading (Actuel)

```python
# config.py
TRADING_MODE = 'PAPER'
# live_order_manager reste None
```

**Résultat** : Comportement actuel inchangé

### 7.2 Phase Dry-Run (Validation)

```python
# config.py
TRADING_MODE = 'LIVE'
LIVE_DRY_RUN = True
MEXC_API_KEY = 'your_key'
MEXC_API_SECRET = 'your_secret'
```

**Résultat** :
- Prix d'entrée/sortie avec slippage simulé
- Latence simulée (300ms)
- Logs "comme en live"
- **Aucun ordre réel placé**
- Comparaison PnL théorique vs simulé

### 7.3 Phase Live Réel

```python
# config.py
TRADING_MODE = 'LIVE'
LIVE_DRY_RUN = False  # ⚠️ ORDRES RÉELS
MEXC_API_KEY = 'your_real_key'
MEXC_API_SECRET = 'your_real_secret'

# Charger config live
from config_live_trading import LIVE_TRADING_CONFIG
TRADING_CONFIG.update(LIVE_TRADING_CONFIG)
```

**Résultat** :
- **Ordres RÉELS placés sur MEXC**
- Prix réels d'exécution
- PnL réel confirmé
- Balance vérifiée
- **Argent réel risqué**

---

## ✅ Checklist Avant de Passer en Live

- [ ] Code intégré (PositionManager + LiveOrderManager)
- [ ] Tests dry-run réussis (1-2 semaines)
- [ ] Config live chargée (`config_live_trading.py`)
- [ ] API keys créées (permissions limitées)
- [ ] IP whitelist activée
- [ ] 2FA activé
- [ ] Capital test limité ($100-200)
- [ ] Dashboard monitoring prêt
- [ ] Alertes configurées
- [ ] Plan d'arrêt d'urgence défini

---

## 🚨 Alertes à Implémenter

```python
# Dans close_position(), après calcul du résultat

# Alerte slippage élevé
if result.get('slippage_exit', 0) > 0.15:  # > 0.15%
    send_telegram_alert(
        f"⚠️ SLIPPAGE ÉLEVÉ: {result['slippage_exit']:.2f}% "
        f"sur {result['symbol']}"
    )

# Alerte latence élevée
if result.get('latency_close_ms', 0) > 1000:  # > 1s
    send_telegram_alert(
        f"⚠️ LATENCE ÉLEVÉE: {result['latency_close_ms']:.0f}ms"
    )

# Alerte écart PnL important
if result.get('pnl_discrepancy_pct', 0) > 20:  # > 20%
    send_telegram_alert(
        f"⚠️ ÉCART PNL: théo={result['pnl_theoretical']:+.2f} "
        f"réel={result['pnl_real']:+.2f} "
        f"(écart={result['pnl_discrepancy_pct']:.1f}%)"
    )

# Alerte ordre échoué
if not result.get('order_id_close'):
    send_telegram_alert(
        f"❌ ORDRE ÉCHOUÉ: Fermeture {result['symbol']} "
        f"(fallback prix théorique utilisé)"
    )
```

---

## 💡 Résumé

**Modifications minimales requises :**
1. ✅ Ajouter config `TRADING_MODE` et `LIVE_DRY_RUN`
2. ✅ Initialiser `LiveOrderManager` dans `init_instances()`
3. ✅ Passer `live_order_manager` à `PositionManager`
4. ✅ Modifier `open_position()` et `close_position()`
5. ✅ Ajouter champs live à `Position` dataclass
6. ✅ Ajouter endpoint `/api/live/stats`

**Comportement selon configuration :**

| Config | Ordres Réels | Slippage | Latence | Argent Risqué |
|--------|--------------|----------|---------|---------------|
| `TRADING_MODE='PAPER'` | ❌ | 0% | 0ms | Non |
| `TRADING_MODE='LIVE'` + `DRY_RUN=True` | ❌ | Simulé | Simulé | Non |
| `TRADING_MODE='LIVE'` + `DRY_RUN=False` | ✅ | Réel | Réel | **OUI** |

**Transition recommandée :**
1. Actuellement : `PAPER` (développement)
2. Validation : `LIVE` + `DRY_RUN=True` (1-2 semaines)
3. Production : `LIVE` + `DRY_RUN=False` ($100 test puis scale)

Voulez-vous que je crée les fichiers de code prêts à l'emploi avec ces modifications ? 🚀
