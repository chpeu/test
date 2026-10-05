# 🚀 PLAN D'IMPLÉMENTATION - Bot ML Adaptatif

> **Date:** 07/12/2025  
> **Status:** VALIDÉ - Prêt pour implémentation  
> **Objectif:** Bot qui s'adapte au marché en temps réel avec données LIVE

---

## 📍 DÉCISION ARCHITECTURE

### Architecture Retenue: 100% LIVE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURE 100% LIVE                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  📊 DONNÉES LIVE (Existant)                                          │   │
│  │  • Trades réels → PostgreSQL (table trades)                         │   │
│  │  • Scans réels → PostgreSQL (table scan_logs)                       │   │
│  │  • Slippage RÉEL, Spread RÉEL, PnL RÉEL                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  🎯 SÉLECTEUR DE RÉGIME (Runtime - toutes les heures)                │   │
│  │  → Calcule ATR/ADX live → Détermine régime → Charge config          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  📡 SCANNER + 🤖 ML JUGE (Existant + améliorations)                  │   │
│  │  → Filtres dynamiques selon régime + GradientBoosting               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                           │
│                                 ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  🔄 OPTIMISATION CONTINUE (Background - chaque nuit)                 │   │
│  │  → Analyse trades 7j → Met à jour configs régime → Ré-entraîne ML   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Modules NON retenus (simulation)
- ❌ Shadow Trading L2 → Pas besoin, on a les vrais trades
- ❌ Multi-Config Grid Search → Remplacé par analyse SQL sur données réelles

---

## 📋 FONCTIONNALITÉS À IMPLÉMENTER

### Vue d'ensemble

| # | Fonctionnalité | Sprint | Temps | Priorité | Dépendances |
|---|----------------|--------|-------|----------|-------------|
| 1 | **Sélecteur de Régime** | 1 | 3-4h | ⭐⭐⭐ CRITIQUE | Aucune |
| 2 | **Circuit Breaker Amélioré** | 1 | 2h | ⭐⭐⭐ CRITIQUE | Aucune |
| 3 | **Filtre Horaire Intelligent** | 2 | 2h | ⭐⭐ HAUTE | Aucune |
| 4 | **Score Pair Dynamique** | 2 | 2h | ⭐⭐ HAUTE | Aucune |
| 5 | **Momentum BTC** | 3 | 3h | ⭐ MOYENNE | Sélecteur Régime |
| 6 | **Optimiseur Nocturne** | 3 | 3h | ⭐⭐ HAUTE | Sélecteur Régime |
| 7 | **Régime CHOPPY (4ème)** | 3 | 2h | ⭐ MOYENNE | Sélecteur Régime |
| 8 | **Config Blending** | 4 | 3h | ⭐ OPTIONNEL | Sélecteur Régime |
| 9 | **Voting Ensemble ML** | 4 | 4h | ⭐ OPTIONNEL | Aucune |
| 10 | **Drift Detector** | 4 | 4h | ⭐ OPTIONNEL | Aucune |

**Total estimé:** 28-32h sur 4-6 semaines

---

## 🗓️ PLANNING DÉTAILLÉ

---

### SPRINT 1 (Semaine 1) - Fondations
**Objectif:** Bot s'adapte automatiquement au régime de marché

---

#### 1.1 Sélecteur de Régime de Marché ⭐ CRITIQUE

**Fichier:** `core/market_regime_selector.py` (CRÉER)

```python
"""
Market Regime Selector - Détecte le régime et charge la config appropriée
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from config import TRADING_CONFIG
from utils.logger import get_logger

logger = get_logger()


class MarketRegimeSelector:
    """
    Sélecteur de régime de marché.
    Analyse l'ATR moyen des top paires pour déterminer le régime actuel.
    """
    
    REGIMES = {
        'CALME': {'atr_max': 0.20, 'description': 'Marché calme avec tendance'},
        'NORMAL': {'atr_max': 0.50, 'description': 'Volatilité normale'},
        'VOLATILE': {'atr_max': float('inf'), 'description': 'Haute volatilité'}
    }
    
    def __init__(self, exchange, config_manager, db_connection=None):
        self.exchange = exchange
        self.config_manager = config_manager
        self.db = db_connection
        
        self.current_regime = None
        self.last_check = None
        self.check_interval = timedelta(hours=1)  # Vérifier toutes les heures
        
        # Configs par régime (chargées depuis fichiers JSON)
        self.regime_configs = {}
        self._load_regime_configs()
        
    def _load_regime_configs(self):
        """Charge les configurations pour chaque régime"""
        import json
        from pathlib import Path
        
        config_dir = Path('config/regimes')
        config_dir.mkdir(parents=True, exist_ok=True)
        
        for regime in self.REGIMES.keys():
            config_file = config_dir / f'config_{regime.lower()}.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.regime_configs[regime] = json.load(f)
                logger.info(f"✅ Config régime {regime} chargée")
            else:
                logger.warning(f"⚠️ Config régime {regime} non trouvée, utilisation défauts")
                self.regime_configs[regime] = self._get_default_config(regime)
                # Sauvegarder le défaut
                with open(config_file, 'w') as f:
                    json.dump(self.regime_configs[regime], f, indent=2)
                    
    def _get_default_config(self, regime: str) -> dict:
        """Retourne la configuration par défaut pour un régime"""
        defaults = {
            'CALME': {
                'optimal_atr_max_1m': 0.26,
                'optimal_atr_max_5m': 0.60,
                'min_score_required': 9.0,
                'volume_multiplier': 0.8,
                'adx_min': 20,
                'description': 'Config optimisée pour marchés calmes'
            },
            'NORMAL': {
                'optimal_atr_max_1m': 0.50,
                'optimal_atr_max_5m': 1.0,
                'min_score_required': 7.5,
                'volume_multiplier': 1.0,
                'adx_min': 18,
                'description': 'Config standard'
            },
            'VOLATILE': {
                'optimal_atr_max_1m': 1.0,
                'optimal_atr_max_5m': 1.5,
                'min_score_required': 6.0,
                'volume_multiplier': 1.2,
                'adx_min': 25,
                'description': 'Config pour haute volatilité'
            }
        }
        return defaults.get(regime, defaults['NORMAL'])
        
    async def check_and_update_regime(self, force: bool = False) -> Optional[str]:
        """
        Vérifie le régime actuel et met à jour la config si nécessaire.
        Appelé périodiquement depuis main.py
        
        Returns:
            Le régime actuel ou None si pas de changement
        """
        now = datetime.now()
        
        # Ne pas vérifier trop souvent sauf si forcé
        if not force and self.last_check:
            if now - self.last_check < self.check_interval:
                return None
                
        self.last_check = now
        
        # Calculer ATR moyen du marché
        avg_atr = await self._calculate_market_atr()
        
        if avg_atr is None:
            logger.warning("⚠️ Impossible de calculer ATR marché")
            return None
            
        # Déterminer le régime
        new_regime = self._detect_regime(avg_atr)
        
        # Si changement de régime
        if new_regime != self.current_regime:
            old_regime = self.current_regime or "NONE"
            logger.info(f"🔄 CHANGEMENT RÉGIME: {old_regime} → {new_regime} (ATR: {avg_atr:.3f}%)")
            
            # Charger la nouvelle config
            self._apply_regime_config(new_regime)
            self.current_regime = new_regime
            
            # Notification optionnelle
            await self._notify_regime_change(old_regime, new_regime, avg_atr)
            
            return new_regime
            
        return None
        
    async def _calculate_market_atr(self) -> Optional[float]:
        """Calcule l'ATR moyen des 10 top paires"""
        try:
            # Option 1: Depuis les scans récents (PostgreSQL)
            if self.db:
                return await self._get_atr_from_db()
                
            # Option 2: Calculer en temps réel depuis l'exchange
            return await self._get_atr_from_exchange()
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul ATR marché: {e}")
            return None
            
    async def _get_atr_from_db(self) -> Optional[float]:
        """Récupère ATR moyen depuis les scans récents"""
        query = """
            SELECT AVG(atr_pct_1m) as avg_atr
            FROM scan_logs
            WHERE created_at > NOW() - INTERVAL '1 hour'
            AND atr_pct_1m IS NOT NULL
            AND atr_pct_1m > 0
        """
        # Exécuter query...
        # return result['avg_atr']
        pass
        
    async def _get_atr_from_exchange(self) -> Optional[float]:
        """Calcule ATR depuis les données exchange en temps réel"""
        top_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 
                       'BNB/USDT:USDT', 'XRP/USDT:USDT']
        atrs = []
        
        for symbol in top_symbols:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, '1h', limit=14)
                if ohlcv and len(ohlcv) >= 14:
                    # Calcul ATR simplifié
                    highs = [c[2] for c in ohlcv]
                    lows = [c[3] for c in ohlcv]
                    closes = [c[4] for c in ohlcv]
                    
                    tr_list = []
                    for i in range(1, len(ohlcv)):
                        tr = max(
                            highs[i] - lows[i],
                            abs(highs[i] - closes[i-1]),
                            abs(lows[i] - closes[i-1])
                        )
                        tr_list.append(tr)
                    
                    atr = sum(tr_list) / len(tr_list)
                    atr_pct = (atr / closes[-1]) * 100
                    atrs.append(atr_pct)
            except Exception as e:
                logger.debug(f"Erreur ATR {symbol}: {e}")
                continue
                
        if atrs:
            return sum(atrs) / len(atrs)
        return None
        
    def _detect_regime(self, avg_atr: float) -> str:
        """Détermine le régime basé sur l'ATR moyen"""
        if avg_atr < 0.20:
            return 'CALME'
        elif avg_atr < 0.50:
            return 'NORMAL'
        else:
            return 'VOLATILE'
            
    def _apply_regime_config(self, regime: str):
        """Applique la configuration du régime à TRADING_CONFIG"""
        config = self.regime_configs.get(regime, {})
        
        for key, value in config.items():
            if key != 'description':
                TRADING_CONFIG[key] = value
                logger.debug(f"  → {key} = {value}")
                
        # Sauvegarder dans config_overrides.json
        if self.config_manager:
            self.config_manager.save_config_overrides(config)
            
        logger.info(f"✅ Config régime {regime} appliquée")
        
    async def _notify_regime_change(self, old: str, new: str, atr: float):
        """Envoie notification Telegram si configuré"""
        # À implémenter: notification optionnelle
        pass
        
    def get_current_regime(self) -> dict:
        """Retourne l'état actuel du sélecteur"""
        return {
            'current_regime': self.current_regime,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'config': self.regime_configs.get(self.current_regime, {}),
            'available_regimes': list(self.REGIMES.keys())
        }
```

**Fichiers configs régime:** `config/regimes/` (CRÉER)

```json
// config/regimes/config_calme.json
{
  "optimal_atr_max_1m": 0.26,
  "optimal_atr_max_5m": 0.60,
  "optimal_atr_min_1m": 0.05,
  "optimal_atr_min_5m": 0.10,
  "min_score_required": 9.0,
  "volume_multiplier": 0.8,
  "adx_min": 20,
  "description": "Config optimisée marchés calmes - Winrate prioritaire"
}
```

```json
// config/regimes/config_normal.json
{
  "optimal_atr_max_1m": 0.50,
  "optimal_atr_max_5m": 1.0,
  "optimal_atr_min_1m": 0.10,
  "optimal_atr_min_5m": 0.20,
  "min_score_required": 7.5,
  "volume_multiplier": 1.0,
  "adx_min": 18,
  "description": "Config standard - Équilibre winrate/fréquence"
}
```

```json
// config/regimes/config_volatile.json
{
  "optimal_atr_max_1m": 1.0,
  "optimal_atr_max_5m": 1.5,
  "optimal_atr_min_1m": 0.20,
  "optimal_atr_min_5m": 0.35,
  "min_score_required": 6.0,
  "volume_multiplier": 1.2,
  "adx_min": 25,
  "description": "Config haute volatilité - Opportunités rapides"
}
```

**Intégration main.py:**

```python
# Dans main.py - Après initialisation exchange

from core.market_regime_selector import MarketRegimeSelector

# Initialiser le sélecteur de régime
regime_selector = MarketRegimeSelector(
    exchange=exchange,
    config_manager=config_manager,
    db_connection=pg_logger.pool if pg_logger else None
)

# Tâche périodique (toutes les heures)
async def regime_check_task():
    while True:
        try:
            await regime_selector.check_and_update_regime()
        except Exception as e:
            logger.error(f"Erreur regime check: {e}")
        await asyncio.sleep(3600)  # 1 heure

# Lancer la tâche
asyncio.create_task(regime_check_task())
```

---

#### 1.2 Circuit Breaker Amélioré ⭐ CRITIQUE

**Fichier:** `core/circuit_breaker.py` (CRÉER)

```python
"""
Circuit Breaker Trading - Protection contre séries perdantes
"""

from datetime import datetime, timedelta
from typing import Optional
from utils.logger import get_logger

logger = get_logger()


class TradingCircuitBreaker:
    """
    Circuit Breaker pour protéger le capital.
    Se déclenche sur séries perdantes ou drawdown excessif.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # Compteurs
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.session_start = datetime.now().replace(hour=0, minute=0, second=0)
        
        # État
        self.paused_until: Optional[datetime] = None
        self.score_boost = 0  # Ajouté au score minimum requis
        self.pause_reason: Optional[str] = None
        
        # Seuils (configurables)
        self.max_consecutive_losses = self.config.get('max_consecutive_losses', 5)
        self.losses_for_prudent = self.config.get('losses_for_prudent', 3)
        self.daily_drawdown_pause = self.config.get('daily_drawdown_pause', -2.0)  # %
        self.daily_drawdown_stop = self.config.get('daily_drawdown_stop', -5.0)  # %
        self.pause_duration_losses = self.config.get('pause_duration_losses', 30)  # minutes
        self.pause_duration_drawdown = self.config.get('pause_duration_drawdown', 120)  # minutes
        
    def on_trade_closed(self, trade_result: dict):
        """
        Appelé après chaque trade fermé.
        Met à jour les compteurs et vérifie les triggers.
        """
        pnl_pct = trade_result.get('pnl_pct', 0.0)
        win = trade_result.get('win', pnl_pct > 0)
        
        self.daily_pnl += pnl_pct
        self.daily_trades += 1
        
        if win:
            # Reset sur victoire
            self.consecutive_losses = 0
            self.score_boost = max(0, self.score_boost - 1)
            logger.info(f"✅ Trade WIN - Consecutive losses reset, score_boost: {self.score_boost}")
        else:
            # Incrémenter sur défaite
            self.consecutive_losses += 1
            self._check_loss_triggers()
            
        # Vérifier drawdown journalier
        self._check_drawdown_triggers()
        
    def _check_loss_triggers(self):
        """Vérifie les triggers basés sur losses consécutives"""
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._activate_pause(
                duration_minutes=self.pause_duration_losses,
                reason=f"{self.consecutive_losses} losses consécutives"
            )
        elif self.consecutive_losses >= self.losses_for_prudent:
            self.score_boost = 1
            logger.warning(
                f"⚠️ Circuit Breaker: Mode PRUDENT activé "
                f"({self.consecutive_losses} losses) - Score min +{self.score_boost}"
            )
            
    def _check_drawdown_triggers(self):
        """Vérifie les triggers basés sur drawdown journalier"""
        if self.daily_pnl <= self.daily_drawdown_stop:
            self._activate_pause(
                duration_minutes=60*24,  # Jusqu'au lendemain
                reason=f"Drawdown journalier {self.daily_pnl:.2f}% (stop)"
            )
        elif self.daily_pnl <= self.daily_drawdown_pause:
            self._activate_pause(
                duration_minutes=self.pause_duration_drawdown,
                reason=f"Drawdown journalier {self.daily_pnl:.2f}%"
            )
            
    def _activate_pause(self, duration_minutes: int, reason: str):
        """Active une pause du trading"""
        self.paused_until = datetime.now() + timedelta(minutes=duration_minutes)
        self.pause_reason = reason
        logger.warning(
            f"🛑 Circuit Breaker ACTIVÉ: {reason} | "
            f"Pause jusqu'à {self.paused_until.strftime('%H:%M:%S')}"
        )
        
    def can_trade(self) -> bool:
        """Vérifie si le trading est autorisé"""
        # Reset journalier
        now = datetime.now()
        if now.date() > self.session_start.date():
            self._reset_daily()
            
        # Vérifier pause
        if self.paused_until:
            if now < self.paused_until:
                return False
            else:
                # Pause terminée
                logger.info(f"✅ Circuit Breaker: Pause terminée, trading autorisé")
                self.paused_until = None
                self.pause_reason = None
                # Garder score_boost après pause (mode prudent)
                self.score_boost = 2  # Plus strict après pause
                
        return True
        
    def get_adjusted_min_score(self, base_min_score: float) -> float:
        """Retourne le score minimum ajusté"""
        return base_min_score + self.score_boost
        
    def _reset_daily(self):
        """Reset des compteurs journaliers"""
        logger.info(f"🔄 Circuit Breaker: Reset journalier (PnL hier: {self.daily_pnl:.2f}%)")
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.session_start = datetime.now().replace(hour=0, minute=0, second=0)
        self.score_boost = 0
        self.paused_until = None
        self.pause_reason = None
        # NE PAS reset consecutive_losses (peut traverser minuit)
        
    def reset(self):
        """Reset manuel complet"""
        self.consecutive_losses = 0
        self.score_boost = 0
        self.paused_until = None
        self.pause_reason = None
        logger.warning("🔄 Circuit Breaker: RESET MANUEL")
        
    def get_status(self) -> dict:
        """Retourne l'état actuel"""
        return {
            'can_trade': self.can_trade(),
            'consecutive_losses': self.consecutive_losses,
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'score_boost': self.score_boost,
            'paused_until': self.paused_until.isoformat() if self.paused_until else None,
            'pause_reason': self.pause_reason
        }
```

**Intégration scanner_loop.py:**

```python
# Au début du scan, vérifier si trading autorisé
if not circuit_breaker.can_trade():
    logger.info(f"⏸️ Trading en pause: {circuit_breaker.pause_reason}")
    return None
    
# Ajuster le score minimum
base_min_score = TRADING_CONFIG.get('min_score_required', 7.5)
adjusted_min_score = circuit_breaker.get_adjusted_min_score(base_min_score)

# Après fermeture de position
circuit_breaker.on_trade_closed({
    'pnl_pct': result['pnl_pct'],
    'win': result['win'],
    'symbol': result['symbol']
})
```

---

### SPRINT 2 (Semaine 2) - Filtres Intelligents
**Objectif:** Éviter les trades à faible probabilité

---

#### 2.1 Filtre Horaire Intelligent

**Fichier:** `core/hourly_filter.py` (CRÉER)

```python
"""
Filtre Horaire Intelligent - Blacklist heures perdantes
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger()


class HourlyFilter:
    """
    Filtre les heures de trading basé sur performance historique.
    """
    
    def __init__(self, stats_file: str = 'data/hourly_stats.json'):
        self.stats_file = Path(stats_file)
        self.hourly_stats: Dict[int, dict] = {}
        self.blacklist_threshold = 35.0  # Winrate < 35% = blacklist
        self.prudent_threshold = 45.0    # Winrate < 45% = score +2
        
        self._load_stats()
        
    def _load_stats(self):
        """Charge les statistiques horaires"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                data = json.load(f)
                self.hourly_stats = {int(k): v for k, v in data.get('hours', {}).items()}
                logger.info(f"✅ Stats horaires chargées ({len(self.hourly_stats)} heures)")
        else:
            logger.warning("⚠️ Stats horaires non trouvées, filtre désactivé")
            
    def can_trade_now(self) -> tuple[bool, Optional[str], int]:
        """
        Vérifie si l'heure actuelle permet le trading.
        
        Returns:
            (can_trade, reason, score_adjustment)
        """
        hour = datetime.now().hour
        stats = self.hourly_stats.get(hour)
        
        if not stats or stats.get('trades', 0) < 10:
            return True, None, 0  # Pas assez de données
            
        winrate = stats.get('winrate', 50.0)
        
        if winrate < self.blacklist_threshold:
            return False, f"Heure {hour}h blacklistée (WR: {winrate:.1f}%)", 0
            
        if winrate < self.prudent_threshold:
            return True, f"Heure {hour}h prudente (WR: {winrate:.1f}%)", 2
            
        return True, None, 0
        
    def update_stats(self, hour: int, win: bool, pnl: float):
        """Met à jour les stats pour une heure donnée"""
        if hour not in self.hourly_stats:
            self.hourly_stats[hour] = {'trades': 0, 'wins': 0, 'pnl_total': 0.0}
            
        stats = self.hourly_stats[hour]
        stats['trades'] += 1
        if win:
            stats['wins'] += 1
        stats['pnl_total'] += pnl
        stats['winrate'] = (stats['wins'] / stats['trades']) * 100
        stats['pnl_avg'] = stats['pnl_total'] / stats['trades']
        
        # Déterminer status
        if stats['winrate'] < self.blacklist_threshold:
            stats['status'] = 'BLACKLIST'
        elif stats['winrate'] < self.prudent_threshold:
            stats['status'] = 'PRUDENT'
        else:
            stats['status'] = 'OK'
            
    def save_stats(self):
        """Sauvegarde les statistiques"""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, 'w') as f:
            json.dump({
                'last_updated': datetime.now().isoformat(),
                'hours': self.hourly_stats
            }, f, indent=2)
```

---

#### 2.2 Score Pair Dynamique

**Fichier:** `core/pair_scorer.py` (CRÉER)

```python
"""
Score Pair Dynamique - Bonus/Malus par paire selon performance
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict
from utils.logger import get_logger

logger = get_logger()


class PairScorer:
    """
    Calcule un bonus/malus de score par paire basé sur performance historique.
    """
    
    def __init__(self, stats_file: str = 'data/pair_scores.json'):
        self.stats_file = Path(stats_file)
        self.pair_stats: Dict[str, dict] = {}
        self.min_trades = 10  # Minimum trades pour calculer bonus
        
        self._load_stats()
        
    def _load_stats(self):
        """Charge les statistiques par paire"""
        if self.stats_file.exists():
            with open(self.stats_file, 'r') as f:
                data = json.load(f)
                self.pair_stats = data.get('pairs', {})
                logger.info(f"✅ Stats paires chargées ({len(self.pair_stats)} paires)")
                
    def get_pair_bonus(self, symbol: str) -> float:
        """
        Retourne le bonus/malus pour une paire.
        
        Returns:
            Bonus: [-2.0, +2.0]
        """
        stats = self.pair_stats.get(symbol)
        
        if not stats or stats.get('trades', 0) < self.min_trades:
            return 0.0  # Pas assez de données
            
        return stats.get('bonus', 0.0)
        
    def calculate_bonus(self, winrate: float, pnl_avg: float, trades: int) -> float:
        """
        Calcule le bonus basé sur winrate et PnL moyen.
        
        winrate: en % (ex: 52.3)
        pnl_avg: en % (ex: 0.12)
        """
        if trades < self.min_trades:
            return 0.0
            
        # Bonus basé sur winrate (vs moyenne 45%)
        wr_bonus = (winrate - 45) / 15  # +1 pour chaque 15% au-dessus de 45%
        
        # Bonus basé sur PnL moyen (vs moyenne 0.05%)
        pnl_bonus = (pnl_avg - 0.05) / 0.15  # +1 pour chaque 0.15% au-dessus
        
        # Combiné et borné
        total = (wr_bonus + pnl_bonus) / 2
        return max(-2.0, min(2.0, total))
        
    def update_pair(self, symbol: str, win: bool, pnl: float):
        """Met à jour les stats d'une paire"""
        if symbol not in self.pair_stats:
            self.pair_stats[symbol] = {
                'trades': 0, 'wins': 0, 'pnl_total': 0.0
            }
            
        stats = self.pair_stats[symbol]
        stats['trades'] += 1
        if win:
            stats['wins'] += 1
        stats['pnl_total'] += pnl
        
        # Recalculer métriques
        stats['winrate'] = (stats['wins'] / stats['trades']) * 100
        stats['pnl_avg'] = stats['pnl_total'] / stats['trades']
        stats['bonus'] = self.calculate_bonus(
            stats['winrate'], stats['pnl_avg'], stats['trades']
        )
        
    def save_stats(self):
        """Sauvegarde les statistiques"""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, 'w') as f:
            json.dump({
                'last_updated': datetime.now().isoformat(),
                'pairs': self.pair_stats
            }, f, indent=2)
```

---

### SPRINT 3 (Semaines 3-4) - Optimisation Continue
**Objectif:** Bot s'améliore automatiquement chaque nuit

---

#### 3.1 Momentum BTC

**Fichier:** `core/btc_momentum.py` (CRÉER)

```python
"""
BTC Momentum - Adapte stratégie selon mouvement BTC
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from utils.logger import get_logger

logger = get_logger()


class BTCMomentum:
    """
    Surveille le momentum BTC et ajuste la stratégie.
    """
    
    def __init__(self, exchange):
        self.exchange = exchange
        self.btc_symbol = 'BTC/USDT:USDT'
        self.price_cache: Dict[str, float] = {}
        self.last_update = None
        
    async def get_momentum(self) -> dict:
        """
        Calcule le momentum BTC.
        
        Returns:
            dict avec delta_1h, delta_4h, mode, direction_filter
        """
        try:
            # Récupérer prix historiques
            ohlcv = await self.exchange.fetch_ohlcv(self.btc_symbol, '1h', limit=5)
            
            if not ohlcv or len(ohlcv) < 5:
                return {'mode': 'UNKNOWN', 'direction_filter': None}
                
            current_price = ohlcv[-1][4]
            price_1h_ago = ohlcv[-2][4]
            price_4h_ago = ohlcv[-5][4] if len(ohlcv) >= 5 else price_1h_ago
            
            delta_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100
            delta_4h = ((current_price - price_4h_ago) / price_4h_ago) * 100
            
            mode = self._determine_mode(delta_1h)
            direction_filter = self._get_direction_filter(delta_1h)
            
            return {
                'current_price': current_price,
                'delta_1h': delta_1h,
                'delta_4h': delta_4h,
                'mode': mode,
                'direction_filter': direction_filter
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur BTC momentum: {e}")
            return {'mode': 'ERROR', 'direction_filter': None}
            
    def _determine_mode(self, delta_1h: float) -> str:
        """Détermine le mode selon delta 1h"""
        if delta_1h > 3.0:
            return 'PUMP'
        elif delta_1h < -3.0:
            return 'DUMP'
        elif abs(delta_1h) > 1.0:
            return 'TRENDING'
        return 'FLAT'
        
    def _get_direction_filter(self, delta_1h: float) -> Optional[str]:
        """Retourne filtre de direction si nécessaire"""
        if delta_1h > 3.0:
            return 'LONG_ONLY'
        elif delta_1h < -3.0:
            return 'SHORT_ONLY'  # Ou 'PAUSE' selon stratégie
        return None
```

---

#### 3.2 Optimiseur Nocturne

**Fichier:** `scripts/nightly_optimizer.py` (CRÉER)

```python
"""
Optimiseur Nocturne - Met à jour configs régime chaque nuit
Exécuter via cron: 0 3 * * * python scripts/nightly_optimizer.py
"""

import asyncio
import json
import psycopg2
from pathlib import Path
from datetime import datetime, timedelta
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger()


async def run_nightly_optimization():
    """Optimisation nocturne des configs par régime"""
    logger.info("🌙 Début optimisation nocturne")
    
    # Connexion DB
    conn = psycopg2.connect(
        host="localhost",
        database="trading_bot",
        user="postgres",
        password="password"
    )
    
    try:
        for regime in ['CALME', 'NORMAL', 'VOLATILE']:
            logger.info(f"📊 Analyse régime {regime}...")
            
            # Récupérer trades du régime (7 derniers jours)
            trades = get_trades_by_regime(conn, regime, days=7)
            
            if len(trades) < 20:
                logger.info(f"  → Pas assez de trades ({len(trades)}) pour {regime}")
                continue
                
            # Trouver meilleure config
            best_config = find_optimal_config(trades, regime)
            
            if best_config:
                save_regime_config(regime, best_config)
                logger.info(f"  ✅ Config {regime} mise à jour")
            else:
                logger.info(f"  → Pas d'amélioration trouvée pour {regime}")
                
        # Mettre à jour stats horaires
        update_hourly_stats(conn)
        
        # Mettre à jour stats paires
        update_pair_stats(conn)
        
        logger.info("✅ Optimisation nocturne terminée")
        
    finally:
        conn.close()


def get_trades_by_regime(conn, regime: str, days: int = 7) -> list:
    """Récupère les trades d'un régime donné"""
    atr_ranges = {
        'CALME': (0, 0.20),
        'NORMAL': (0.20, 0.50),
        'VOLATILE': (0.50, 100)
    }
    atr_min, atr_max = atr_ranges[regime]
    
    query = """
        SELECT *
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '%s days'
        AND atr_pct_1m >= %s AND atr_pct_1m < %s
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (days, atr_min, atr_max))
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def find_optimal_config(trades: list, regime: str) -> dict:
    """
    Grid search simple pour trouver la meilleure config.
    Retourne la config avec meilleur Sharpe ratio.
    """
    # Grid de paramètres à tester
    param_grid = {
        'min_score_required': [6.0, 7.0, 7.5, 8.0, 9.0],
        'volume_multiplier': [0.6, 0.8, 1.0, 1.2],
        'adx_min': [15, 18, 20, 25]
    }
    
    best_config = None
    best_sharpe = -float('inf')
    
    # Grid search
    for min_score in param_grid['min_score_required']:
        for vol_mult in param_grid['volume_multiplier']:
            for adx_min in param_grid['adx_min']:
                # Filtrer trades selon ces paramètres
                filtered = [t for t in trades 
                           if t.get('score_1m', 0) >= min_score
                           and t.get('volume_ratio', 0) >= vol_mult
                           and t.get('adx_1m', 0) >= adx_min]
                
                if len(filtered) < 10:
                    continue
                    
                # Calculer métriques
                winrate = sum(1 for t in filtered if t.get('win')) / len(filtered)
                pnl_list = [t.get('pnl_pct', 0) for t in filtered]
                avg_pnl = sum(pnl_list) / len(pnl_list)
                std_pnl = (sum((p - avg_pnl)**2 for p in pnl_list) / len(pnl_list)) ** 0.5
                
                # Sharpe simplifié
                sharpe = avg_pnl / std_pnl if std_pnl > 0 else 0
                
                if sharpe > best_sharpe and winrate > 0.50:
                    best_sharpe = sharpe
                    best_config = {
                        'min_score_required': min_score,
                        'volume_multiplier': vol_mult,
                        'adx_min': adx_min,
                        'metrics': {
                            'trades': len(filtered),
                            'winrate': winrate * 100,
                            'avg_pnl': avg_pnl,
                            'sharpe': sharpe
                        }
                    }
                    
    return best_config


def save_regime_config(regime: str, config: dict):
    """Sauvegarde la config optimisée pour un régime"""
    config_dir = Path('config/regimes')
    config_file = config_dir / f'config_{regime.lower()}.json'
    
    # Charger config existante
    existing = {}
    if config_file.exists():
        with open(config_file, 'r') as f:
            existing = json.load(f)
            
    # Mettre à jour avec nouvelles valeurs
    existing.update({
        'min_score_required': config['min_score_required'],
        'volume_multiplier': config['volume_multiplier'],
        'adx_min': config['adx_min'],
        'last_optimized': datetime.now().isoformat(),
        'optimization_metrics': config['metrics']
    })
    
    with open(config_file, 'w') as f:
        json.dump(existing, f, indent=2)


def update_hourly_stats(conn):
    """Met à jour les statistiques horaires"""
    query = """
        SELECT 
            EXTRACT(HOUR FROM timestamp_entry) as hour,
            COUNT(*) as trades,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '7 days'
        GROUP BY 1
        ORDER BY 1
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        
    hourly_stats = {}
    for hour, trades, wins, avg_pnl in rows:
        winrate = (wins / trades * 100) if trades > 0 else 0
        status = 'BLACKLIST' if winrate < 35 else ('PRUDENT' if winrate < 45 else 'OK')
        hourly_stats[int(hour)] = {
            'trades': trades,
            'wins': wins,
            'winrate': round(winrate, 1),
            'avg_pnl': round(avg_pnl or 0, 4),
            'status': status
        }
        
    # Sauvegarder
    stats_file = Path('data/hourly_stats.json')
    stats_file.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_file, 'w') as f:
        json.dump({
            'last_updated': datetime.now().isoformat(),
            'hours': hourly_stats
        }, f, indent=2)
        
    logger.info(f"✅ Stats horaires mises à jour ({len(hourly_stats)} heures)")


def update_pair_stats(conn):
    """Met à jour les statistiques par paire"""
    query = """
        SELECT 
            symbol,
            COUNT(*) as trades,
            SUM(CASE WHEN win THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl
        FROM trades
        WHERE timestamp_entry > NOW() - INTERVAL '7 days'
        GROUP BY 1
        HAVING COUNT(*) >= 5
        ORDER BY 2 DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        
    pair_stats = {}
    for symbol, trades, wins, avg_pnl in rows:
        winrate = (wins / trades * 100) if trades > 0 else 0
        
        # Calcul bonus
        wr_bonus = (winrate - 45) / 15
        pnl_bonus = (avg_pnl - 0.05) / 0.15
        bonus = max(-2.0, min(2.0, (wr_bonus + pnl_bonus) / 2))
        
        pair_stats[symbol] = {
            'trades': trades,
            'wins': wins,
            'winrate': round(winrate, 1),
            'pnl_avg': round(avg_pnl or 0, 4),
            'bonus': round(bonus, 2)
        }
        
    # Sauvegarder
    stats_file = Path('data/pair_scores.json')
    with open(stats_file, 'w') as f:
        json.dump({
            'last_updated': datetime.now().isoformat(),
            'pairs': pair_stats
        }, f, indent=2)
        
    logger.info(f"✅ Stats paires mises à jour ({len(pair_stats)} paires)")


if __name__ == '__main__':
    asyncio.run(run_nightly_optimization())
```

---

#### 3.3 Régime CHOPPY (4ème régime)

**Modification:** `core/market_regime_selector.py`

```python
# Ajouter le 4ème régime dans REGIMES
REGIMES = {
    'CALME': {'atr_max': 0.20, 'adx_min': 20, 'description': 'Marché calme AVEC tendance'},
    'CHOPPY': {'atr_max': 0.20, 'adx_max': 20, 'description': 'Marché calme SANS tendance (range)'},
    'NORMAL': {'atr_max': 0.50, 'description': 'Volatilité normale'},
    'VOLATILE': {'atr_max': float('inf'), 'description': 'Haute volatilité'}
}

def _detect_regime(self, avg_atr: float, avg_adx: float = None) -> str:
    """Détermine le régime basé sur ATR et ADX"""
    if avg_atr < 0.20:
        # Marché calme - distinguer tendance vs range
        if avg_adx and avg_adx < 20:
            return 'CHOPPY'  # Pas de tendance = dangereux
        return 'CALME'
    elif avg_atr < 0.50:
        return 'NORMAL'
    else:
        return 'VOLATILE'
```

**Fichier config:** `config/regimes/config_choppy.json`

```json
{
  "optimal_atr_max_1m": 0.20,
  "optimal_atr_max_5m": 0.40,
  "min_score_required": 10.0,
  "volume_multiplier": 1.5,
  "adx_min": 15,
  "position_size_multiplier": 0.5,
  "trading_enabled": true,
  "description": "Config CHOPPY - Très sélectif, taille réduite 50%"
}
```

---

### SPRINT 4 (Semaines 5-6) - Améliorations Avancées (Optionnel)
**Objectif:** Robustesse et performance maximales

---

#### 4.1 Config Blending (Optionnel)

**Si oscillations détectées entre régimes**, implémenter interpolation:

```python
def _apply_blended_config(self, regime_probs: dict):
    """Applique config interpolée selon probabilités régime"""
    blended = {}
    
    for param in ['min_score_required', 'volume_multiplier', 'adx_min']:
        blended[param] = sum(
            regime_probs[regime] * self.regime_configs[regime].get(param, 0)
            for regime in regime_probs
        )
        
    # Appliquer
    for key, value in blended.items():
        TRADING_CONFIG[key] = value
```

---

#### 4.2 Voting Ensemble ML (Optionnel)

**Fichier:** `optimization/models/ensemble_predictor.py`

Si GradientBoosting seul montre ses limites, implémenter voting:
- GradientBoosting (30%)
- XGBoost (40%)
- CatBoost (30%)

---

#### 4.3 Drift Detector (Optionnel)

**Fichier:** `monitoring/drift_detector.py`

Alertes si écart prédiction vs réalité > 10%

---

## 📊 MÉTRIQUES DE SUCCÈS

### KPIs à Suivre

| Métrique | Baseline (Actuel) | Sprint 1 | Sprint 2 | Sprint 3 | Final |
|----------|-------------------|----------|----------|----------|-------|
| **Winrate** | 58% | 61% | 63% | 66% | 68%+ |
| **Trades/jour** | 5 | 12 | 15 | 18 | 20 |
| **Drawdown max** | -3% | -2.5% | -2.2% | -2% | -1.8% |
| **PnL/semaine** | +2% | +3% | +4% | +5% | +6% |

### Critères Validation

#### Sprint 1 → Sprint 2
- ✅ Winrate +3% minimum
- ✅ Pas d'augmentation drawdown
- ✅ 2 semaines sans bug critique

#### Sprint 2 → Sprint 3
- ✅ Winrate +5% cumulé
- ✅ Trades/jour doublés
- ✅ Heures blacklistées respectées

#### Sprint 3 → Sprint 4
- ✅ Optimisation nocturne fonctionne
- ✅ Régime CHOPPY détecté correctement
- ✅ Winrate +8% cumulé

---

## 📋 CHECKLIST IMPLÉMENTATION

### Sprint 1 - Semaine 1
```
[ ] Créer core/market_regime_selector.py
[ ] Créer config/regimes/ avec 3 configs JSON
[ ] Créer core/circuit_breaker.py
[ ] Intégrer dans main.py (tâche périodique régime)
[ ] Intégrer dans scanner_loop.py (circuit breaker)
[ ] Tests unitaires basiques
[ ] Test live 3 jours
[ ] Valider métriques Sprint 1
```

### Sprint 2 - Semaine 2
```
[ ] Créer core/hourly_filter.py
[ ] Créer core/pair_scorer.py
[ ] Intégrer filtres dans scanner_loop.py
[ ] Créer scripts/update_stats.py (quotidien)
[ ] Configurer cron job stats
[ ] Test live 1 semaine
[ ] Valider métriques Sprint 2
```

### Sprint 3 - Semaines 3-4
```
[ ] Créer core/btc_momentum.py
[ ] Créer scripts/nightly_optimizer.py
[ ] Ajouter régime CHOPPY
[ ] Créer config/regimes/config_choppy.json
[ ] Configurer cron job nocturne
[ ] Test live 2 semaines
[ ] Valider métriques Sprint 3
```

### Sprint 4 - Semaines 5-6 (Si besoin)
```
[ ] Implémenter Config Blending si oscillations
[ ] Implémenter Voting Ensemble si winrate stagne
[ ] Implémenter Drift Detector
[ ] Test live 2 semaines
[ ] Valider métriques finales
```

---

## 🚀 COMMANDES UTILES

```bash
# Lancer optimisation nocturne manuellement
python scripts/nightly_optimizer.py

# Vérifier régime actuel
curl http://localhost:5555/api/regime/status

# Reset circuit breaker
curl -X POST http://localhost:5555/api/live/reset-circuit-breaker

# Voir stats horaires
cat data/hourly_stats.json | jq .

# Voir stats paires
cat data/pair_scores.json | jq '.pairs | to_entries | sort_by(-.value.bonus) | .[0:10]'

# Configurer cron nocturne (Linux)
crontab -e
# 0 3 * * * cd /path/to/bot && python scripts/nightly_optimizer.py >> logs/nightly.log 2>&1
```

---

## 📚 FICHIERS À CRÉER

```
NOUVEAUX FICHIERS:
├── core/
│   ├── market_regime_selector.py    # Sélecteur régime (Sprint 1)
│   ├── circuit_breaker.py           # Protection capital (Sprint 1)
│   ├── hourly_filter.py             # Filtre heures (Sprint 2)
│   ├── pair_scorer.py               # Score paires (Sprint 2)
│   └── btc_momentum.py              # Momentum BTC (Sprint 3)
├── config/
│   └── regimes/
│       ├── config_calme.json        # Config marché calme
│       ├── config_normal.json       # Config standard
│       ├── config_volatile.json     # Config haute volatilité
│       └── config_choppy.json       # Config range (Sprint 3)
├── scripts/
│   └── nightly_optimizer.py         # Optimisation nocturne (Sprint 3)
├── data/
│   ├── hourly_stats.json            # Stats horaires (auto-généré)
│   └── pair_scores.json             # Scores paires (auto-généré)
└── monitoring/
    └── drift_detector.py            # Détection drift (Sprint 4, optionnel)

FICHIERS À MODIFIER:
├── main.py                          # Intégration régime + circuit breaker
├── core/callbacks/scanner_loop.py   # Intégration filtres
└── core/position_manager.py         # Notification circuit breaker
```

---

**Document créé:** 07/12/2025  
**Status:** ✅ PRÊT POUR IMPLÉMENTATION  
**Prochaine action:** Commencer Sprint 1 - Sélecteur de Régime

---
