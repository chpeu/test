"""
Configuration globale pour Trade Cursor
"""
import os

# API MEXC
MEXC_FUTURES_URL = "https://contract.mexc.com"

# Trading parameters
TRADING_CONFIG = {
    "fee_per_trade": 0.0004,  # 0.04% par trade
    "position_timeout": 300,  # 5 minutes
    "check_interval": 2,  # 2 secondes
    "scan_interval": 45,  # 45 secondes pour position scan
    "scalability_interval": 90,  # 90 secondes pour scalability scan
    
    # Volume multiplier
    "volume_multiplier": 1.0,
    "volume_multiplier_range": (0.10, 2.00),
    
    # TP/SL settings
    "tp_sl_mode": "FIXE",  # FIXE ou ATR
    
    # FIXE mode
    "tp_percent": 0.25,  # +0.25%
    "sl_percent": 0.25,  # -0.25%
    "break_even_trigger": 0.3,  # +0.3%
    "trailing_distance": 0.1,  # 0.1%
    
    # ATR mode
    "atr_mult_tp": 1.5,
    "atr_mult_sl": 1.0,
    "atr_min": 0.15,  # %
    "atr_max": 1.5,  # %
    
    # Optimal ATR filter
    "optimal_atr_min_1m": 0.15,
    "optimal_atr_max_1m": 0.8,
    "optimal_atr_min_5m": 0.3,
    "optimal_atr_max_5m": 1.5,
    
    # Position entry conditions
    "min_conditions": 6,
    "dynamic_tolerance_adx_high": 30,  # ADX > 30 → 5 conditions
    "dynamic_tolerance_adx_low": 25,  # ADX < 25 → 6 conditions
    
    # Phase 1+2: New filters (configurable)
    "snr_threshold": 0.3,  # Signal-to-Noise Ratio minimum
    "breakout_threshold": 0.3,  # Breakout multiplier (ATR * threshold)
    "wick_ratio_max": 2.5,  # Max wick ratio before rejection
    "di_gap_min": 5,  # Minimum DI+ - DI- gap
    "di_gap_adx_threshold": 25,  # ADX threshold for DI gap
    
    # Scalability scanner
    "top_pairs_limit": 20,
    "balance_score_min": 0.7,
    
    # Confluence
    "use_confluence": False,  # False = 1m OU 5m, True = 1m ET 5m
}

# Risk management
RISK_CONFIG = {
    "base_risk": 0.02,  # 2% par défaut
    "quality_multiplier_perfect": 1.5,  # 7 conditions
    "quality_multiplier_good": 1.2,  # 6 conditions
    "quality_multiplier_ok": 0.8,  # 5 conditions
    "quality_multiplier_weak": 0.5,  # <5 conditions
    "vol_multiplier_high": 0.7,  # ATR > 2.0%
    "vol_multiplier_low": 1.3,  # ATR < 0.5%
    "max_risk": 0.05,  # 5%
    "min_risk": 0.005,  # 0.5%
}

# 🔥 v6.6: Retry & Circuit Breaker settings
RETRY_CONFIG = {
    "max_attempts": 5,
    "wait_multiplier": 1,
    "wait_min": 1,
    "wait_max": 10,
}

CIRCUIT_BREAKER_CONFIG = {
    "fail_max": 5,
    "timeout_duration": 60,  # 60 seconds
    "expected_exception": Exception,
}

# 🔥 v6.6: WebSocket settings
WEBSOCKET_CONFIG = {
    "url": "wss://contract.mexc.com/ws",  # WebSocket URL MEXC
    "ping_interval": 30,  # Heartbeat toutes les 30s
    "reconnect_delay": 5,  # Délai reconnexion en s
    "timeout": 10,  # Timeout connexion
}

# Debug
DEBUG_ENABLED = os.getenv("DEBUG", "False").lower() == "true"

