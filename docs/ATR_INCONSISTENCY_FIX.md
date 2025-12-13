# ATR Inconsistency Fix - Root Cause Analysis & Resolution

## Problem Statement
`scan_logs.params_snapshot` (and derived `config_atr_*` columns) were logging **base** `TRADING_CONFIG` values (from `config_overrides.json`), while `reject_reason` strings were using **effective_config** values (regime-adjusted). This caused confusion when analyzing ATR filter rejections.

**Example Inconsistency (CALME regime):**
- `config_atr_min_5m`: 0.3 (from config_overrides.json)
- `config_atr_max_5m`: 0.6 (from config_overrides.json)  
- `reject_reason`: "ATR sous-optimal: 0.087% (trop bas, optimal: **0.1-0.35%**)" ← regime values

## Root Cause

### Two Scan Paths
The system has two `scan_pair_for_setup` implementations:

1. **`main.py::scan_pair_for_setup()`** - Used for single-pair scans via API
2. **`scanner_loop.py::scan_pair_for_setup()`** - Used for batch scanner loop

Both paths log to PostgreSQL, but `main.py` was using `TRADING_CONFIG.get()` directly for `params_snapshot`, ignoring regime adjustments.

### Config Flow
```
config_overrides.json → TRADING_CONFIG (base)
                              ↓
                    set_regime_adjustments()
                              ↓
                    effective_config (runtime)
                              ↓
                    get_effective_value() → actual thresholds used
```

The `check_atr_filter()` function correctly uses `get_effective_value()`, but `main.py` logging bypassed this.

## Fix Applied

### 1. `main.py` - Use effective_config for logging (lines 2166-2184)
```python
eff_volume_multiplier = get_effective_value('volume_multiplier', symbol=symbol)
if eff_volume_multiplier is None:
    eff_volume_multiplier = volume_multiplier
eff_min_score_required = get_effective_value('min_score_required', symbol=symbol)
if eff_min_score_required is None:
    eff_min_score_required = TRADING_CONFIG.get('min_score_required', 7.5)
eff_optimal_atr_min_1m = get_effective_value('optimal_atr_min_1m', symbol=symbol)
# ... same pattern for all ATR thresholds
```

**Note:** Using `is None` check instead of `or` to preserve valid `0.0` values (e.g., `optimal_atr_min_1m=0.0` in CALME regime).

### 2. `filters.py` - DEBUG instrumentation (lines 234-240)
```python
if DEBUG_ENABLED:
    logger.debug(
        f"🔍 {symbol} {timeframe}: ATR filter thresholds | "
        f"atr={atr_percent:.3f}% | "
        f"effective={optimal_atr_min}-{optimal_atr_max}% | "
        f"base={base_atr_min}-{base_atr_max}%"
    )
```

## Verification SQL Queries

### 1. Check new scans have consistent ATR values
```sql
-- After fix: config_atr_* should match reject_reason ATR range
SELECT 
    id,
    symbol,
    created_at,
    market_regime,
    config_atr_min_5m,
    config_atr_max_5m,
    SUBSTRING(reject_reason FROM 'optimal: ([0-9.]+-[0-9.]+)%') AS reject_atr_range,
    reject_reason
FROM scan_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND reject_reason LIKE '%ATR%'
ORDER BY created_at DESC
LIMIT 20;
```

### 2. Compare before/after fix
```sql
-- Scans BEFORE fix (config_atr != reject_reason ATR)
SELECT 
    id, symbol, market_regime,
    config_atr_min_5m || '-' || config_atr_max_5m AS config_range,
    SUBSTRING(reject_reason FROM 'optimal: ([0-9.]+-[0-9.]+)%') AS reject_range
FROM scan_logs
WHERE created_at < '2024-12-13 18:30:00'  -- Before fix timestamp
  AND market_regime = 'CALME'
  AND reject_reason LIKE '%ATR%5m%'
LIMIT 5;

-- Scans AFTER fix (config_atr = reject_reason ATR)
SELECT 
    id, symbol, market_regime,
    config_atr_min_5m || '-' || config_atr_max_5m AS config_range,
    SUBSTRING(reject_reason FROM 'optimal: ([0-9.]+-[0-9.]+)%') AS reject_range
FROM scan_logs
WHERE created_at > '2024-12-13 18:35:00'  -- After fix timestamp
  AND market_regime = 'CALME'
  AND reject_reason LIKE '%ATR%5m%'
LIMIT 5;
```

### 3. Verify regime config values
```sql
-- Check market_regime_history for CALME config
SELECT 
    id,
    created_at,
    regime_name,
    config_snapshot->'optimal_atr_min_5m' AS atr_min_5m,
    config_snapshot->'optimal_atr_max_5m' AS atr_max_5m
FROM market_regime_history
WHERE regime_name = 'CALME'
ORDER BY created_at DESC
LIMIT 5;
```

## Expected Results After Fix

| Regime | config_atr_min_5m | config_atr_max_5m | reject_reason ATR range |
|--------|-------------------|-------------------|-------------------------|
| CALME  | 0.1               | 0.35              | 0.1-0.35%               |
| NORMAL | 0.2               | 0.6               | 0.2-0.6%                |
| VOLATILE | (from regime config) | (from regime config) | (matches) |

## Files Modified
- `main.py`: Lines 28, 2166-2184, 2343-2356
- `core/analyzer/filters.py`: Lines 217-218, 227-228, 234-240

## Observability Recommendations

1. **Single Source of Truth**: Always use `get_effective_value()` for logging config values
2. **Log Both Values**: Consider logging `base_config` AND `effective_config` separately for debugging
3. **Regime Change Alerts**: `market_regime_history` already logs regime changes with config snapshots
4. **DEBUG Mode**: Enable `DEBUG_ENABLED=True` to see ATR filter threshold logs in real-time
