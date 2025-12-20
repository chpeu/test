# 📊 DATA BACKFILL STRATEGY - Coherence-First Approach
## Backfill Only If Data Is Coherent

> **Version:** 1.0.0 | **Date:** 14/12/2025 | **Statut:** 📋 SPÉCIFIÉ
> 
> **Décision:** Backfill seulement si les données sont cohérentes avec le régime calculé, sinon exclure.

---

## 🎯 PRINCIPE FONDAMENTAL

> **"Better no data than wrong data"**
> 
> Un trade avec un régime backfillé mais des paramètres incohérents 
> pollue le dataset ML plus qu'il ne l'enrichit.

---

## 📐 ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKFILL DECISION TREE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Trade avec entry_market_regime = UNKNOWN ou NULL               │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STEP 1: Peut-on calculer un régime?                     │   │
│  │  ────────────────────────────────────────────────────    │   │
│  │  Requiert: entry_atr_1m OU entry_atr_5m présent         │   │
│  │            entry_adx présent (optionnel)                 │   │
│  │                                                          │   │
│  │  NON → Mark as EXCLUDED (reason: no_atr_data)           │   │
│  │  OUI → Continue                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STEP 2: Calculer le régime                              │   │
│  │  ────────────────────────────────────────────────────    │   │
│  │  Utiliser la même logique que MarketRegimeSelector:     │   │
│  │  - ATR < 0.20% → CALME                                   │   │
│  │  - ATR 0.20-0.50% → NORMAL                               │   │
│  │  - ATR > 0.50% → VOLATILE                                │   │
│  │  - ADX < 20 → override to CHOPPY                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STEP 3: Vérifier cohérence ATR                          │   │
│  │  ────────────────────────────────────────────────────    │   │
│  │  L'ATR du trade doit être dans la plage du régime       │   │
│  │  calculé (±50% tolérance)                                │   │
│  │                                                          │   │
│  │  Exemple: régime CALME → ATR doit être < 0.30%          │   │
│  │           (0.20 × 1.5 = 0.30)                           │   │
│  │                                                          │   │
│  │  NON → Mark as EXCLUDED (reason: atr_mismatch)          │   │
│  │  OUI → Continue                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STEP 4: Vérifier cohérence paramètres                   │   │
│  │  ────────────────────────────────────────────────────    │   │
│  │  Les SL/TP utilisés doivent être compatibles avec       │   │
│  │  le régime (pas strictement égaux, mais dans la plage)  │   │
│  │                                                          │   │
│  │  CALME: SL 0.5-1.2x, TP 1.0-2.5x                        │   │
│  │  NORMAL: SL 0.8-1.5x, TP 1.5-3.0x                       │   │
│  │  VOLATILE: SL 1.0-2.0x, TP 2.0-4.0x                     │   │
│  │                                                          │   │
│  │  NON → Mark as EXCLUDED (reason: params_mismatch)       │   │
│  │  OUI → Continue                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  STEP 5: Vérifier données What-If                        │   │
│  │  ────────────────────────────────────────────────────    │   │
│  │  Pour calculer What-If, il faut:                        │   │
│  │  - max_price_reached                                     │   │
│  │  - min_price_reached                                     │   │
│  │                                                          │   │
│  │  NON → Mark as EXCLUDED (reason: no_mfe_mae)            │   │
│  │  OUI → BACKFILL APPROVED ✅                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 CRITÈRES DE COHÉRENCE

### 1. ATR Ranges par Régime

| Régime | ATR Min | ATR Max | Tolérance |
|--------|---------|---------|-----------|
| CALME | 0% | 0.20% | +50% → 0.30% |
| NORMAL | 0.20% | 0.50% | ±50% → 0.10%-0.75% |
| VOLATILE | 0.50% | ∞ | -50% → 0.25% min |
| CHOPPY | Any | Any | ADX < 20 |

### 2. Paramètres SL/TP par Régime

| Régime | SL Mult Range | TP Mult Range |
|--------|---------------|---------------|
| CALME | 0.5x - 1.2x | 1.0x - 2.5x |
| NORMAL | 0.8x - 1.5x | 1.5x - 3.0x |
| VOLATILE | 1.0x - 2.0x | 2.0x - 4.0x |

**Note:** Tolérance étendue (×1.5 sur les ranges) car les paramètres peuvent avoir été ajustés dynamiquement.

### 3. Données requises pour What-If

| Colonne | Requis | Usage |
|---------|--------|-------|
| `max_price_reached` | ✅ OUI | Calcul MFE |
| `min_price_reached` | ✅ OUI | Calcul MAE |
| `entry_price` | ✅ OUI | Base calcul |
| `exit_price` | ✅ OUI | PnL réel |

---

## 🔧 IMPLÉMENTATION

### Fichier: `core/ml/data_quality_checker.py`

```python
"""
Data Quality Checker - Coherence validation for backfill
"""
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExclusionReason(Enum):
    NO_ATR_DATA = "no_atr_data"
    ATR_MISMATCH = "atr_mismatch"
    PARAMS_MISMATCH = "params_mismatch"
    NO_MFE_MAE = "no_mfe_mae"
    NONE = "none"


@dataclass
class CoherenceResult:
    is_coherent: bool
    calculated_regime: Optional[str]
    exclusion_reason: ExclusionReason
    details: Dict


class DataQualityChecker:
    """
    Validates trade data coherence for backfill operations.
    """
    
    # ATR thresholds for regime calculation
    ATR_THRESHOLDS = {
        'calme_max': 0.20,
        'normal_max': 0.50,
    }
    
    # ATR ranges per regime (with tolerance)
    ATR_RANGES = {
        'CALME': (0, 0.30),      # 0.20 × 1.5
        'NORMAL': (0.10, 0.75),  # 0.20×0.5 to 0.50×1.5
        'VOLATILE': (0.25, float('inf')),  # 0.50×0.5
        'CHOPPY': (0, float('inf')),  # Any ATR
    }
    
    # SL/TP ranges per regime (with tolerance ×1.5)
    PARAM_RANGES = {
        'CALME': {
            'sl': (0.33, 1.8),   # 0.5-1.2 × 1.5 tolerance
            'tp': (0.67, 3.75),  # 1.0-2.5 × 1.5 tolerance
        },
        'NORMAL': {
            'sl': (0.53, 2.25),  # 0.8-1.5 × 1.5 tolerance
            'tp': (1.0, 4.5),    # 1.5-3.0 × 1.5 tolerance
        },
        'VOLATILE': {
            'sl': (0.67, 3.0),   # 1.0-2.0 × 1.5 tolerance
            'tp': (1.33, 6.0),   # 2.0-4.0 × 1.5 tolerance
        },
        'CHOPPY': {
            'sl': (0.33, 3.0),   # Wide range
            'tp': (0.67, 6.0),   # Wide range
        },
    }
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.atr_tolerance = self.config.get('backfill_atr_tolerance_pct', 50) / 100
        self.require_mfe_mae = self.config.get('backfill_require_mfe_mae', True)
    
    def check_coherence(self, trade: dict) -> CoherenceResult:
        """
        Check if a trade with UNKNOWN regime can be coherently backfilled.
        
        Returns CoherenceResult with:
        - is_coherent: True if trade can be backfilled
        - calculated_regime: The regime that would be assigned
        - exclusion_reason: Why trade was excluded (if not coherent)
        - details: Additional info for debugging
        """
        
        # STEP 1: Can we calculate a regime?
        atr_1m = trade.get('entry_atr_1m')
        atr_5m = trade.get('entry_atr_5m')
        adx = trade.get('entry_adx')
        
        atr = atr_1m or atr_5m
        if atr is None or atr == 0:
            return CoherenceResult(
                is_coherent=False,
                calculated_regime=None,
                exclusion_reason=ExclusionReason.NO_ATR_DATA,
                details={'atr_1m': atr_1m, 'atr_5m': atr_5m}
            )
        
        # STEP 2: Calculate regime
        calculated_regime = self._calculate_regime(atr, adx)
        
        # STEP 3: Check ATR coherence
        atr_range = self.ATR_RANGES.get(calculated_regime, (0, float('inf')))
        if not (atr_range[0] <= atr <= atr_range[1]):
            return CoherenceResult(
                is_coherent=False,
                calculated_regime=calculated_regime,
                exclusion_reason=ExclusionReason.ATR_MISMATCH,
                details={
                    'atr': atr,
                    'expected_range': atr_range,
                    'regime': calculated_regime
                }
            )
        
        # STEP 4: Check params coherence
        sl_mult = trade.get('entry_atr_mult_sl', 0)
        tp_mult = trade.get('entry_atr_mult_tp', 0)
        
        if sl_mult > 0 and tp_mult > 0:
            param_ranges = self.PARAM_RANGES.get(calculated_regime, {})
            sl_range = param_ranges.get('sl', (0, float('inf')))
            tp_range = param_ranges.get('tp', (0, float('inf')))
            
            sl_ok = sl_range[0] <= sl_mult <= sl_range[1]
            tp_ok = tp_range[0] <= tp_mult <= tp_range[1]
            
            if not (sl_ok and tp_ok):
                return CoherenceResult(
                    is_coherent=False,
                    calculated_regime=calculated_regime,
                    exclusion_reason=ExclusionReason.PARAMS_MISMATCH,
                    details={
                        'sl_mult': sl_mult,
                        'sl_range': sl_range,
                        'sl_ok': sl_ok,
                        'tp_mult': tp_mult,
                        'tp_range': tp_range,
                        'tp_ok': tp_ok,
                        'regime': calculated_regime
                    }
                )
        
        # STEP 5: Check MFE/MAE for What-If
        if self.require_mfe_mae:
            max_price = trade.get('max_price_reached')
            min_price = trade.get('min_price_reached')
            
            if max_price is None or min_price is None:
                return CoherenceResult(
                    is_coherent=False,
                    calculated_regime=calculated_regime,
                    exclusion_reason=ExclusionReason.NO_MFE_MAE,
                    details={
                        'max_price_reached': max_price,
                        'min_price_reached': min_price
                    }
                )
        
        # ALL CHECKS PASSED
        return CoherenceResult(
            is_coherent=True,
            calculated_regime=calculated_regime,
            exclusion_reason=ExclusionReason.NONE,
            details={
                'atr': atr,
                'adx': adx,
                'regime': calculated_regime
            }
        )
    
    def _calculate_regime(self, atr: float, adx: Optional[float]) -> str:
        """Calculate regime from ATR and ADX."""
        # Check CHOPPY first (ADX based)
        if adx is not None and adx < 20:
            return 'CHOPPY'
        
        # ATR based
        if atr < self.ATR_THRESHOLDS['calme_max']:
            return 'CALME'
        elif atr < self.ATR_THRESHOLDS['normal_max']:
            return 'NORMAL'
        else:
            return 'VOLATILE'
    
    def analyze_backfill_candidates(
        self, 
        trades: List[dict]
    ) -> Dict:
        """
        Analyze a list of trades to determine backfill eligibility.
        
        Returns summary with counts and details.
        """
        results = {
            'total': len(trades),
            'coherent': 0,
            'excluded': 0,
            'by_regime': {},
            'by_exclusion_reason': {},
            'details': []
        }
        
        for trade in trades:
            result = self.check_coherence(trade)
            
            if result.is_coherent:
                results['coherent'] += 1
                regime = result.calculated_regime
                results['by_regime'][regime] = results['by_regime'].get(regime, 0) + 1
            else:
                results['excluded'] += 1
                reason = result.exclusion_reason.value
                results['by_exclusion_reason'][reason] = \
                    results['by_exclusion_reason'].get(reason, 0) + 1
            
            results['details'].append({
                'trade_id': trade.get('id'),
                'is_coherent': result.is_coherent,
                'calculated_regime': result.calculated_regime,
                'exclusion_reason': result.exclusion_reason.value,
            })
        
        return results


# Singleton
_data_quality_checker: Optional[DataQualityChecker] = None


def get_data_quality_checker() -> DataQualityChecker:
    """Get or create the data quality checker singleton."""
    global _data_quality_checker
    if _data_quality_checker is None:
        from config import TRADING_CONFIG
        config = TRADING_CONFIG.get('backfill', {})
        _data_quality_checker = DataQualityChecker(config)
    return _data_quality_checker
```

---

## 📜 SCRIPT BACKFILL

### Fichier: `verification/smart_backfill_regime.py`

```python
"""
Smart Backfill Script - Backfill regimes only if coherent
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ml.data_quality_checker import DataQualityChecker, ExclusionReason

load_dotenv()


def main():
    # Database connection
    password = quote_plus(os.getenv('POSTGRES_PASSWORD', ''))
    db_url = f"postgresql://{os.getenv('POSTGRES_USER')}:{password}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    engine = create_engine(db_url)
    
    checker = DataQualityChecker()
    
    print("=" * 60)
    print("SMART BACKFILL - Coherence-First Approach")
    print("=" * 60)
    print()
    
    # Fetch trades with UNKNOWN or NULL regime
    query = text("""
        SELECT 
            t.id,
            t.entry_market_regime,
            tam.entry_atr_1m,
            tam.entry_atr_5m,
            tam.entry_adx,
            tam.entry_atr_mult_sl,
            tam.entry_atr_mult_tp,
            t.max_price_reached,
            t.min_price_reached,
            t.entry_price,
            t.exit_price
        FROM trades t
        LEFT JOIN trade_atr_metrics tam ON t.id = tam.trade_id
        WHERE t.entry_market_regime IS NULL 
           OR t.entry_market_regime = 'UNKNOWN'
        ORDER BY t.created_at DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        trades = [dict(row._mapping) for row in result]
    
    print(f"Found {len(trades)} trades with UNKNOWN/NULL regime")
    print()
    
    # Analyze coherence
    analysis = checker.analyze_backfill_candidates(trades)
    
    print("=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Total:     {analysis['total']}")
    print(f"Coherent:  {analysis['coherent']} ({analysis['coherent']/analysis['total']*100:.1f}%)")
    print(f"Excluded:  {analysis['excluded']} ({analysis['excluded']/analysis['total']*100:.1f}%)")
    print()
    
    print("By Calculated Regime:")
    for regime, count in sorted(analysis['by_regime'].items()):
        print(f"  {regime}: {count}")
    print()
    
    print("Exclusion Reasons:")
    for reason, count in sorted(analysis['by_exclusion_reason'].items()):
        print(f"  {reason}: {count}")
    print()
    
    # Ask for confirmation
    if analysis['coherent'] > 0:
        confirm = input(f"Backfill {analysis['coherent']} coherent trades? [y/N]: ")
        if confirm.lower() == 'y':
            backfill_trades(engine, checker, trades)
        else:
            print("Backfill cancelled.")
    else:
        print("No coherent trades to backfill.")


def backfill_trades(engine, checker, trades):
    """Actually perform the backfill."""
    updated = 0
    excluded = 0
    
    with engine.begin() as conn:
        for trade in trades:
            result = checker.check_coherence(trade)
            
            if result.is_coherent:
                # Update trade
                update_query = text("""
                    UPDATE trades 
                    SET entry_market_regime = :regime,
                        is_backfilled = TRUE,
                        backfill_timestamp = :timestamp
                    WHERE id = :trade_id
                """)
                conn.execute(update_query, {
                    'regime': result.calculated_regime,
                    'trade_id': trade['id'],
                    'timestamp': datetime.utcnow()
                })
                updated += 1
            else:
                # Mark as excluded
                update_query = text("""
                    UPDATE trades 
                    SET backfill_excluded = TRUE,
                        backfill_excluded_reason = :reason
                    WHERE id = :trade_id
                """)
                conn.execute(update_query, {
                    'reason': result.exclusion_reason.value,
                    'trade_id': trade['id']
                })
                excluded += 1
    
    print()
    print("=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    print(f"Updated:  {updated} trades")
    print(f"Excluded: {excluded} trades")


if __name__ == '__main__':
    main()
```

---

## 🗄️ COLONNES SQL À AJOUTER

### Migration

```sql
-- Add backfill tracking columns to trades table
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS is_backfilled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS backfill_timestamp TIMESTAMP,
ADD COLUMN IF NOT EXISTS backfill_excluded BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS backfill_excluded_reason VARCHAR(50);

-- Index for filtering
CREATE INDEX IF NOT EXISTS idx_trades_backfill 
ON trades (is_backfilled, backfill_excluded);

-- Comment
COMMENT ON COLUMN trades.is_backfilled IS 'True if entry_market_regime was calculated post-hoc';
COMMENT ON COLUMN trades.backfill_excluded IS 'True if trade was excluded from ML dataset due to incoherent data';
COMMENT ON COLUMN trades.backfill_excluded_reason IS 'Reason for exclusion: no_atr_data, atr_mismatch, params_mismatch, no_mfe_mae';
```

---

## 🔧 CONFIGURATION

### config.py

```python
BACKFILL_CONFIG = {
    # Enable/disable backfill
    'backfill_enabled': True,
    
    # Coherence checking
    'backfill_coherence_check_enabled': True,
    'backfill_atr_tolerance_pct': 50,  # ±50% tolerance on ATR ranges
    
    # What-If requirements
    'backfill_require_mfe_mae': True,
    
    # Tracking
    'backfill_flag_column': True,  # Add is_backfilled flag
    'backfill_exclude_flag_column': True,  # Add backfill_excluded flag
    
    # ATR thresholds (same as MarketRegimeSelector)
    'backfill_atr_calme_max': 0.20,
    'backfill_atr_normal_max': 0.50,
    'backfill_adx_choppy_max': 20,
}
```

---

## 📊 IMPACT SUR LE DATASET ML

### Avant backfill

| Régime | Trades | % Dataset |
|--------|--------|-----------|
| CALME | 234 | 45% |
| NORMAL | 167 | 32% |
| VOLATILE | 78 | 15% |
| CHOPPY | 26 | 5% |
| UNKNOWN | 15 | 3% ❌ |
| **Total ML** | 505 | 97% |

### Après backfill cohérent

| Régime | Trades | % Dataset | Gain |
|--------|--------|-----------|------|
| CALME | 242 | 46% | +8 |
| NORMAL | 171 | 33% | +4 |
| VOLATILE | 80 | 15% | +2 |
| CHOPPY | 27 | 5% | +1 |
| Excluded | 5 | - | - |
| **Total ML** | 520 | 100% | +15 |

---

## ✅ CHECKLIST

- [ ] Créer `core/ml/data_quality_checker.py`
- [ ] Créer `verification/smart_backfill_regime.py`
- [ ] Migration SQL (colonnes backfill tracking)
- [ ] Ajouter BACKFILL_CONFIG dans `config.py`
- [ ] Intégrer dans ML Monitor (Data Health section)
- [ ] Tests unitaires
- [ ] Documentation utilisateur

---

## 📝 NOTES

- Le backfill ne modifie que `entry_market_regime`, pas les autres colonnes
- Les trades exclus restent dans la DB mais sont flaggés
- Le filtre ML peut utiliser `WHERE NOT backfill_excluded`
- Traçabilité complète: on sait quels trades sont backfillés

---

**Ce document définit la stratégie de backfill cohérent. Exécuter le script après validation.**
