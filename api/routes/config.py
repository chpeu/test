"""
API Routes pour la configuration - Inclut endpoint token MEXC
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import json
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config", tags=["config"])

# Variables globales injectées par main.py
_app_state = None

def set_app_state(as_):
    global _app_state
    _app_state = as_

# Chemin du fichier de credentials
CREDENTIALS_FILE = "credentials.json"


@router.get("")
async def api_get_config():
    """Récupérer la configuration actuelle (tous les paramètres)"""
    from config import TRADING_CONFIG
    return JSONResponse({
        'volume_multiplier': TRADING_CONFIG.get('volume_multiplier', 0.95),
        'min_score_required': TRADING_CONFIG.get('min_score_required', 7.5),
        'use_confluence': TRADING_CONFIG.get('use_confluence', False),
        'tp_sl_mode': TRADING_CONFIG.get('tp_sl_mode', 'FIXE'),
        'tp_percent': TRADING_CONFIG.get('tp_percent', 0.25),
        'sl_percent': TRADING_CONFIG.get('sl_percent', 0.25),
        'trailing_mfe_enabled': TRADING_CONFIG.get('trailing_mfe_enabled', False),
        'trailing_mfe_trigger_pct': TRADING_CONFIG.get('trailing_mfe_trigger_pct', 0.10),
        'trailing_mfe_lock_in_pct': TRADING_CONFIG.get('trailing_mfe_lock_in_pct', 0.0),
        'partial_tp_be_lock_in_pct': TRADING_CONFIG.get('partial_tp_be_lock_in_pct', 0.0),
        'snr_threshold': TRADING_CONFIG.get('snr_threshold', 0.25),
        'breakout_threshold': TRADING_CONFIG.get('breakout_threshold', 0.35),
        'wick_ratio_max': TRADING_CONFIG.get('wick_ratio_max', 2.8),
        'di_gap_min': TRADING_CONFIG.get('di_gap_min', 4.0),
        'di_gap_adx_threshold': TRADING_CONFIG.get('di_gap_adx_threshold', 25),
        'optimal_atr_min_1m': TRADING_CONFIG.get('optimal_atr_min_1m', 0.12),
        'optimal_atr_max_1m': TRADING_CONFIG.get('optimal_atr_max_1m', 0.75),
        'optimal_atr_min_5m': TRADING_CONFIG.get('optimal_atr_min_5m', 0.22),
        'optimal_atr_max_5m': TRADING_CONFIG.get('optimal_atr_max_5m', 1.4),
        'trend_timeframe': TRADING_CONFIG.get('trend_timeframe', '15m'),
        'account_size': TRADING_CONFIG.get('account_size', 1000.0),
        'risk_per_trade': TRADING_CONFIG.get('risk_per_trade', 2.0),
        'gb_filter_enabled': TRADING_CONFIG.get('gb_filter_enabled', True),
        'gb_min_confidence': TRADING_CONFIG.get('gb_min_confidence', 0.55),
        'ml_calibration_enabled': TRADING_CONFIG.get('ml_calibration_enabled', False),
        'ml_calib_min_winrate': TRADING_CONFIG.get('ml_calib_min_winrate', 45),
        'ml_calib_live_weight': TRADING_CONFIG.get('ml_calib_live_weight', 1.0),
        'ml_calib_dryrun_weight': TRADING_CONFIG.get('ml_calib_dryrun_weight', 0.5),
        'ml_calib_decay_days': TRADING_CONFIG.get('ml_calib_decay_days', 30),
        'ml_calib_min_trades': TRADING_CONFIG.get('ml_calib_min_trades', 50),
        'threshold_optimizer_enabled': TRADING_CONFIG.get('threshold_optimizer_enabled', False),
        'threshold_min': TRADING_CONFIG.get('threshold_min', 0.45),
        'threshold_max': TRADING_CONFIG.get('threshold_max', 0.70),
        'drift_detection_enabled': TRADING_CONFIG.get('drift_detection_enabled', True),
        'gb_max_iter': TRADING_CONFIG.get('gb_max_iter', 200),
        'gb_max_depth': TRADING_CONFIG.get('gb_max_depth', 5),
        'gb_learning_rate': TRADING_CONFIG.get('gb_learning_rate', 0.1),
        'gb_l2_regularization': TRADING_CONFIG.get('gb_l2_regularization', 0.5),
        'max_spread_pct': TRADING_CONFIG.get('max_spread_pct'),
        'max_spread_pct_fixe': TRADING_CONFIG.get('max_spread_pct_fixe', 0.03),
        'max_spread_pct_atr': TRADING_CONFIG.get('max_spread_pct_atr', 0.06),
        'invert_signals': TRADING_CONFIG.get('invert_signals', False)
    })


@router.get("/complete")
async def api_get_complete_config():
    """Récupérer TOUTES les variables de configuration"""
    from config import (
        TRADING_CONFIG, RISK_CONFIG, CONDITION_WEIGHTS, TREND_BONUS_CONFIG,
        RETRY_CONFIG, CIRCUIT_BREAKER_CONFIG, WEBSOCKET_CONFIG
    )
    
    try:
        from utils.effective_config import get_effective_config, get_config_summary
        effective = get_effective_config()
        summary = get_config_summary()
    except Exception as e:
        logger.warning(f"⚠️ Erreur chargement effective_config: {e}")
        effective = TRADING_CONFIG
        summary = {}
    
    return JSONResponse({
        'trading_config': TRADING_CONFIG,
        'effective_config': effective,
        'adjustments_summary': summary,
        'risk_config': RISK_CONFIG,
        'condition_weights': CONDITION_WEIGHTS,
        'trend_bonus_config': TREND_BONUS_CONFIG,
        'retry_config': RETRY_CONFIG,
        'circuit_breaker_config': CIRCUIT_BREAKER_CONFIG,
        'websocket_config': WEBSOCKET_CONFIG,
        'timestamp': time.time()
    })


@router.get("/effective")
async def api_get_effective_config():
    """Récupérer uniquement les valeurs EFFECTIVES utilisées par le bot"""
    try:
        from utils.effective_config import get_effective_config, get_config_summary
        effective = get_effective_config()
        summary = get_config_summary()
        
        return JSONResponse({
            'success': True,
            'effective_config': effective,
            'adjustments': summary.get('adjustments', {}),
            'differences': summary.get('differences', {}),
            'regime_enabled': summary.get('regime_enabled', False),
            'cb_enabled': summary.get('cb_enabled', False),
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"❌ Erreur récupération effective_config: {e}")
        from config import TRADING_CONFIG
        return JSONResponse({
            'success': False,
            'error': str(e),
            'effective_config': TRADING_CONFIG,
            'timestamp': time.time()
        })


async def perform_config_update(params: dict) -> dict:
    """
    Logique centrale pour mettre à jour la configuration.
    Utilisée par l'API REST et le WebSocket.
    """
    from config import TRADING_CONFIG
    from core.state_manager import get_state_manager
    state = get_state_manager()
    
    updated = {}
    pos_cfg = state.get_position_config()

    def _coerce_bool(v):
        if isinstance(v, bool): return v
        if v is None: return False
        if isinstance(v, (int, float)): return v != 0
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ('true', '1', 'yes', 'y', 'on'): return True
            if s in ('false', '0', 'no', 'n', 'off', ''): return False
        return bool(v)
    
    # --- Paramètres de base ---
    if 'volume_multiplier' in params:
        val = float(params['volume_multiplier'])
        val = max(0.1, min(2.0, val))
        TRADING_CONFIG['volume_multiplier'] = val
        updated['volume_multiplier'] = val
    
    if 'use_confluence' in params:
        TRADING_CONFIG['use_confluence'] = _coerce_bool(params['use_confluence'])
        updated['use_confluence'] = TRADING_CONFIG['use_confluence']
    
    if 'min_score_required' in params:
        val = float(params['min_score_required'])
        val = max(1.0, min(20.0, val))
        TRADING_CONFIG['min_score_required'] = val
        updated['min_score_required'] = val

    if 'max_slippage_pct' in params:
        val = float(params['max_slippage_pct'])
        val = max(0.0, min(0.20, val))
        TRADING_CONFIG['max_slippage_pct'] = val
        updated['max_slippage_pct'] = val

    if 'scan_interval' in params:
        val = int(params['scan_interval'])
        val = max(15, min(120, val))
        TRADING_CONFIG['scan_interval'] = val
        updated['scan_interval'] = val

    # --- TP/SL Mode & Niveaux ---
    if 'tp_sl_mode' in params:
        mode = str(params['tp_sl_mode']).upper()
        if mode in ['FIXE', 'ATR', 'TP_MULTI', 'ESCALIER']:
            TRADING_CONFIG['tp_sl_mode'] = mode
            if pos_cfg:
                pos_cfg.use_atr = (mode == 'ATR')
            pos_mgr = state.get_position_manager()
            if pos_mgr:
                pos_mgr.config.use_atr = (mode == 'ATR')
                # Recalcul TP/SL si position active
                if pos_mgr.active_position and not getattr(pos_mgr.active_position, 'tp_escalier_enabled', False):
                    try:
                        from core.position.tp_sl_calculator import calculate_atr_levels, calculate_fixed_levels
                        pos = pos_mgr.active_position
                        if (mode == 'ATR') and pos.atr:
                            sl, tp = calculate_atr_levels(pos.entry, pos.atr, pos.atr5m, pos.direction, pos_mgr.tpsl_config)
                        else:
                            sl, tp = calculate_fixed_levels(pos.entry, pos.direction, pos_mgr.tpsl_config)
                        pos.tp, pos.sl = tp, sl
                        logger.info(f"✅ TP/SL recalculés pour {pos.symbol}")
                    except Exception as e:
                        logger.error(f"❌ Erreur recalcul TP/SL: {e}")
            updated['tp_sl_mode'] = mode

    if 'tp_percent' in params:
        val = float(params['tp_percent'])
        TRADING_CONFIG['tp_percent'] = val
        if pos_cfg: pos_cfg.fixed_tp_pct = val
        updated['tp_percent'] = val
    
    if 'sl_percent' in params:
        val = float(params['sl_percent'])
        TRADING_CONFIG['sl_percent'] = val
        if pos_cfg: pos_cfg.fixed_sl_pct = val
        updated['sl_percent'] = val

    # --- Break Even & Trailing ---
    if 'break_even_trigger' in params:
        val = float(params['break_even_trigger'])
        val = max(0.05, min(2.0, val))
        TRADING_CONFIG['break_even_trigger'] = val
        if pos_cfg: pos_cfg.break_even_trigger = val
        updated['break_even_trigger'] = val

    if 'trailing_distance' in params:
        val = float(params['trailing_distance'])
        val = max(0.05, min(1.0, val))
        TRADING_CONFIG['trailing_distance'] = val
        if pos_cfg: pos_cfg.trailing_distance = val
        updated['trailing_distance'] = val

    # --- Seuils Techniques ---
    for key in ['snr_threshold', 'breakout_threshold', 'wick_ratio_max', 'di_gap_min', 'di_gap_adx_threshold']:
        if key in params:
            val = float(params[key])
            TRADING_CONFIG[key] = val
            updated[key] = val

    # --- Seuils ATR ---
    for key in ['optimal_atr_min_1m', 'optimal_atr_max_1m', 'optimal_atr_min_5m', 'optimal_atr_max_5m']:
        if key in params:
            val = float(params[key])
            TRADING_CONFIG[key] = val
            updated[key] = val

    if 'trend_timeframe' in params:
        val = str(params['trend_timeframe']).lower()
        if val in ['5m', '15m', '30m', '1h']:
            TRADING_CONFIG['trend_timeframe'] = val
            updated['trend_timeframe'] = val

    if 'account_size' in params:
        val = float(params['account_size'])
        TRADING_CONFIG['account_size'] = val
        updated['account_size'] = val

    if 'risk_per_trade' in params:
        val = float(params['risk_per_trade'])
        TRADING_CONFIG['risk_per_trade'] = val
        updated['risk_per_trade'] = val

    # --- Patterns ---
    patterns = ['use_breakout', 'use_snr', 'use_wick', 'use_divergence', 
                'use_engulfing', 'use_hammer', 'use_shooting_star', 
                'use_doji', 'use_marubozu', 'use_morning_star', 'use_evening_star']
    for p in patterns:
        if p in params:
            TRADING_CONFIG[p] = _coerce_bool(params[p])
            updated[p] = TRADING_CONFIG[p]

    # --- Escalier TP ---
    for i in range(1, 5):
        for suffix in ['pnl', 'size']:
            key = f'escalier_level{i}_{suffix}'
            if key in params:
                val = float(params[key])
                TRADING_CONFIG[key] = val
                updated[key] = val

    # --- Trailing Stop Avancé ---
    trailing_params = ['trailing_enabled', 'trailing_trigger_pnl', 'trailing_atr_multiplier', 
                       'trailing_distance_atr_mult', 'trailing_min_distance', 'trailing_max_distance', 'trailing_pnl_cap']
    for tp in trailing_params:
        if tp in params:
            val = float(params[tp]) if isinstance(params[tp], (int, float)) else _coerce_bool(params[tp])
            TRADING_CONFIG[tp] = val
            updated[tp] = val
            # Sync alias
            if tp == 'trailing_atr_multiplier': TRADING_CONFIG['trailing_distance_atr_mult'] = val
            if tp == 'trailing_distance_atr_mult': TRADING_CONFIG['trailing_atr_multiplier'] = val

    # Reload TrailingStopConfig if changed
    if any(k in updated for k in trailing_params):
        pos_mgr = state.get_position_manager()
        if pos_mgr and hasattr(pos_mgr, 'trailing_stop'):
            from core.position.trailing_stop import TrailingStopConfig
            pos_mgr.trailing_stop.config = TrailingStopConfig(
                enabled=TRADING_CONFIG.get('trailing_enabled', True),
                trigger_pnl=TRADING_CONFIG.get('trailing_trigger_pnl', 0.25),
                atr_multiplier=TRADING_CONFIG.get('trailing_atr_multiplier', 0.4),
                min_distance=TRADING_CONFIG.get('trailing_min_distance', 0.08),
                max_distance=TRADING_CONFIG.get('trailing_max_distance', 0.25)
            )

    # --- Machine Learning (XGBoost) ---
    if 'ml_filter_enabled' in params:
        from config import ML_CONFIG
        val = _coerce_bool(params['ml_filter_enabled'])
        ML_CONFIG['enabled'] = val
        TRADING_CONFIG['ml_filter_enabled'] = val
        updated['ml_filter_enabled'] = val

    if 'ml_min_confidence' in params:
        from config import ML_CONFIG
        val = max(0.50, min(0.90, float(params['ml_min_confidence'])))
        ML_CONFIG['min_confidence'] = val
        TRADING_CONFIG['ml_min_confidence'] = val
        updated['ml_min_confidence'] = val

    if 'ml_filter_mode' in params:
        from config import ML_CONFIG
        mode = str(params['ml_filter_mode']).upper()
        if mode in ['STRICT', 'SOFT', 'NEGATIVE']:
            ML_CONFIG['mode'] = mode
            TRADING_CONFIG['ml_filter_mode'] = mode
            updated['ml_filter_mode'] = mode

    ml_xgb_params = ['ml_max_depth', 'ml_min_child_weight', 'ml_reg_alpha', 'ml_reg_lambda', 
                     'ml_subsample', 'ml_colsample_bytree', 'ml_colsample_bylevel', 
                     'ml_gamma', 'ml_scale_pos_weight', 'ml_n_estimators', 'ml_learning_rate']
    for p in ml_xgb_params:
        if p in params:
            val = float(params[p]) if 'rate' in p or 'alpha' in p or 'lambda' in p or 'subsample' in p or 'col' in p or 'weight' in p or 'gamma' in p else int(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- GradientBoosting (GB) ---
    gb_params = ['gb_filter_enabled', 'gb_min_confidence', 'gb_n_estimators', 'gb_max_depth', 
                 'gb_learning_rate', 'gb_min_samples_split', 'gb_min_samples_leaf', 
                 'gb_subsample', 'gb_max_features', 'gb_model_type', 'gb_max_iter', 'gb_l2_regularization']
    for p in gb_params:
        if p in params:
            if p == 'gb_filter_enabled': val = _coerce_bool(params[p])
            elif p == 'gb_model_type' or p == 'gb_max_features': val = params[p]
            elif 'rate' in p or 'subsample' in p or 'conf' in p or 'reg' in p or 'feat' in p: val = float(params[p])
            else: val = int(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- ML Calibration ---
    calib_params = ['ml_calibration_enabled', 'ml_calib_min_winrate', 'ml_calib_live_weight', 
                    'ml_calib_dryrun_weight', 'ml_calib_decay_days', 'ml_calib_min_trades', 'ml_calib_bucket_size']
    for p in calib_params:
        if p in params:
            val = _coerce_bool(params[p]) if 'enabled' in p else (float(params[p]) if 'weight' in p else int(params[p]))
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- Threshold Optimizer & Drift ---
    if 'threshold_optimizer_enabled' in params:
        val = _coerce_bool(params['threshold_optimizer_enabled'])
        TRADING_CONFIG['threshold_optimizer_enabled'] = val
        updated['threshold_optimizer_enabled'] = val
        try:
            from core.ml import get_threshold_optimizer
            get_threshold_optimizer().enabled = val
        except Exception: pass

    for p in ['threshold_min', 'threshold_max']:
        if p in params:
            val = float(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val
            try:
                from core.ml import get_threshold_optimizer
                opt = get_threshold_optimizer()
                if p == 'threshold_min': opt.min_threshold = val
                else: opt.max_threshold = val
            except Exception: pass

    if 'drift_detection_enabled' in params:
        val = _coerce_bool(params['drift_detection_enabled'])
        TRADING_CONFIG['drift_detection_enabled'] = val
        updated['drift_detection_enabled'] = val
        try:
            from core.ml import get_drift_detector
            get_drift_detector().enabled = val
        except Exception: pass

    # --- Advanced Filters ---
    adv_filters = ['use_anti_whipsaw', 'whipsaw_lookback', 'whipsaw_threshold_pct', 'whipsaw_max_alternations',
                   'use_retest_confirmation', 'retest_tolerance_pct', 'retest_timeout_seconds',
                   'use_cooldown', 'cooldown_seconds', 'cooldown_same_symbol',
                   'use_candle_close', 'candle_close_threshold_seconds',
                   'use_momentum_continuity', 'momentum_lookback',
                   'use_micro_confirmation', 'micro_confirmation_delay_ms',
                   'rsi_final_filter_enabled', 'rsi_final_long_max', 'rsi_final_short_min']
    for p in adv_filters:
        if p in params:
            if p.startswith('use') or p.endswith('enabled'): val = _coerce_bool(params[p])
            elif 'pct' in p or 'ratio' in p or 'delta' in p or 'threshold' in p: val = float(params[p])
            else: val = int(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- Adaptive Sizing ---
    if 'adaptive_sizing_enabled' in params:
        val = _coerce_bool(params['adaptive_sizing_enabled'])
        TRADING_CONFIG['adaptive_sizing_enabled'] = val
        updated['adaptive_sizing_enabled'] = val
    
    adaptive_params = [k for k in params.keys() if k.startswith('adaptive_sizing_') and k != 'adaptive_sizing_enabled']
    for p in adaptive_params:
        val = float(params[p]) if 'wr' in p or 'mult' in p or 'threshold' in p else int(params[p])
        TRADING_CONFIG[p] = val
        updated[p] = val
    
    if 'adaptive_sizing_enabled' in params or adaptive_params:
        try:
            from core.position.adaptive_sizing import get_adaptive_sizing_manager
            get_adaptive_sizing_manager().reload_config()
        except Exception: pass

    # --- Market Regime V2 ---
    regime_v2_params = ['market_regime_v2_enabled', 'market_regime_use_median', 'market_regime_outlier_filter',
                        'market_regime_use_hysteresis', 'market_regime_hysteresis_buffer', 'market_regime_use_smoothing',
                        'market_regime_smoothing_alpha', 'market_regime_use_atr_5m', 'market_regime_use_seasonality',
                        'market_regime_min_duration_minutes', 'market_regime_auto_calibration_enabled',
                        'market_regime_calibration_lookback_days', 'market_regime_calibration_percentile_calme',
                        'market_regime_calibration_percentile_volatile', 'market_regime_calibration_min_samples',
                        'market_regime_btc_indicator_enabled', 'market_regime_btc_volatile_threshold_1h',
                        'market_regime_btc_trend_threshold_24h', 'market_regime_btc_force_volatile_enabled',
                        'market_regime_atr_calme_max', 'market_regime_atr_normal_max', 'market_regime_adx_choppy']
    for p in regime_v2_params:
        if p in params:
            if p.endswith('enabled') or p.startswith('market_regime_use'): val = _coerce_bool(params[p])
            elif 'pct' in p or 'alpha' in p or 'threshold' in p or 'buffer' in p or 'max' in p: val = float(params[p])
            else: val = int(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- Circuit Breaker ---
    cb_params = ['trading_circuit_breaker_enabled', 'trading_cb_max_consecutive_losses',
                 'trading_cb_daily_drawdown_pause_pct', 'trading_cb_daily_drawdown_stop_pct',
                 'trading_cb_pause_duration_minutes', 'trading_cb_score_boost_enabled',
                 'trading_cb_score_boost_per_loss']
    for p in cb_params:
        if p in params:
            if 'enabled' in p: val = _coerce_bool(params[p])
            elif 'pct' in p or 'loss' in p: val = float(params[p])
            else: val = int(params[p])
            TRADING_CONFIG[p] = val
            updated[p] = val
            
    if 'trading_circuit_breaker_enabled' in params:
        if not TRADING_CONFIG['trading_circuit_breaker_enabled']:
            try:
                from core.trading_circuit_breaker import get_trading_circuit_breaker
                get_trading_circuit_breaker().reset()
                from utils.effective_config import set_circuit_breaker_adjustments
                set_circuit_breaker_adjustments({})
            except Exception: pass

    # --- Pair Scorer ---
    ps_params = ['pair_scorer_enabled', 'pair_scorer_min_trades', 'pair_scorer_max_adjustment',
                 'pair_scorer_lookback_days', 'pair_scorer_refresh_minutes']
    for p in ps_params:
        if p in params:
            val = _coerce_bool(params[p]) if 'enabled' in p else (float(params[p]) if 'adj' in p else int(params[p]))
            TRADING_CONFIG[p] = val
            updated[p] = val
            try:
                from core.pair_scorer import get_pair_scorer
                ps = get_pair_scorer()
                if p == 'pair_scorer_enabled': ps.enabled = val
                elif p == 'pair_scorer_min_trades': ps.min_trades = val
                elif p == 'pair_scorer_max_adjustment': ps.max_adjustment = val
                elif p == 'pair_scorer_lookback_days': 
                    ps.lookback_days = val
                    ps.refresh_stats()
                elif p == 'pair_scorer_refresh_minutes': ps.refresh_interval = val * 60
            except Exception: pass

    # --- Signal Inversion ---
    if 'invert_signals' in params:
        val = _coerce_bool(params['invert_signals'])
        TRADING_CONFIG['invert_signals'] = val
        updated['invert_signals'] = val

    # --- Spread Thresholds ---
    for p in ['max_spread_pct', 'max_spread_pct_fixe', 'max_spread_pct_atr']:
        if p in params:
            val = params[p]
            if val in [None, '', 'null']: val = None
            else: val = float(val)
            TRADING_CONFIG[p] = val
            updated[p] = val

    # --- Finalize ---
    if updated:
        from main import add_log
        await add_log('INFO', 'Config mise à jour', str(updated))
        try:
            from utils.config_persistence import save_config_overrides
            save_config_overrides(updated)
        except Exception as e: logger.error(f"❌ Error persisting config: {e}")
        
        # Sync WebSocket clients
        ws_mgr = state.get_ws_manager()
        if ws_mgr:
            await ws_mgr.emit('config_updated', {'updated': updated, 'timestamp': time.time()})

    return updated


@router.post("/update")
@router.post("")
async def api_update_config(request: Request):
    """Modifier la configuration à la volée (tous les paramètres)"""
    try:
        data = await request.json() if hasattr(request, 'json') else {}
        data = data if isinstance(data, dict) else {}
        updated = await perform_config_update(data)
        return JSONResponse({'success': True, 'updated': updated})
    except Exception as e:
        logger.error(f"Erreur mise à jour config: {e}")
        return JSONResponse({'error': str(e)}, status_code=500)


class MexcTokenRequest(BaseModel):
    """Requête pour mettre à jour le token MEXC"""
    token: str


class MexcTokenResponse(BaseModel):
    """Réponse après mise à jour du token"""
    success: bool
    message: str
    updated_at: Optional[str] = None


@router.post("/mexc-token", response_model=MexcTokenResponse)
async def update_mexc_token(request: MexcTokenRequest):
    """
    Met à jour le token d'authentification MEXC (web cookie)
    
    Appelé par l'extension Firefox MEXC Token Helper
    """
    try:
        token = request.token.strip()
        
        if not token:
            raise HTTPException(status_code=400, detail="Token vide")
        
        if len(token) < 20:
            raise HTTPException(status_code=400, detail="Token trop court (minimum 20 caractères)")
        
        # Charger les credentials existants
        credentials = {}
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
                    credentials = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Fichier {CREDENTIALS_FILE} corrompu, création nouveau")
        
        # Mettre à jour le token
        credentials['mexc_web_token'] = token
        credentials['mexc_web_token_updated_at'] = datetime.now().isoformat()
        
        # Sauvegarder
        with open(CREDENTIALS_FILE, 'w', encoding='utf-8') as f:
            json.dump(credentials, f, indent=2)
        
        logger.info(f"✅ Token MEXC mis à jour (longueur: {len(token)})")
        
        # Notifier le bypass client si disponible
        try:
            from trading.mexc_futures_bypass import MexcFuturesBypass
            # Le bypass rechargera le token au prochain appel
        except ImportError:
            pass
        
        return MexcTokenResponse(
            success=True,
            message=f"Token mis à jour avec succès ({len(token)} caractères)",
            updated_at=credentials['mexc_web_token_updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour token MEXC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mexc-token/status")
async def get_mexc_token_status():
    """
    Vérifie le statut du token MEXC
    """
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return {
                "has_token": False,
                "message": "Aucun fichier credentials"
            }
        
        with open(CREDENTIALS_FILE, 'r', encoding='utf-8') as f:
            credentials = json.load(f)
        
        token = credentials.get('mexc_web_token')
        updated_at = credentials.get('mexc_web_token_updated_at')
        
        if not token:
            return {
                "has_token": False,
                "message": "Token non configuré"
            }
        
        return {
            "has_token": True,
            "token_length": len(token),
            "token_preview": token[:10] + "..." + token[-5:] if len(token) > 20 else "***",
            "updated_at": updated_at,
            "message": "Token configuré"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification token: {e}")
        return {
            "has_token": False,
            "error": str(e)
        }
