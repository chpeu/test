import re

f = open('core/analytics_database.py', 'r', encoding='utf-8').read()

# Extract columns from INSERT statement
start = f.find('INSERT INTO trades (')
end = f.find(') VALUES', start)
cols_text = f[start:end]

# Extract column names
cols = re.findall(r'\b\w+\b', cols_text)
cols = [c for c in cols if c not in ['INSERT', 'INTO', 'trades', 'LIVE', 'TRADING', 'COLUMNS']]

print(f"Total columns in INSERT: {len(cols)}")
print("\nAll columns:")
for i, col in enumerate(cols, 1):
    print(f"{i}. {col}")

# Now check values provided
values_provided = [
    'timestamp', 'date', 'time', 'symbol', 'direction', 'entry', 'exit',
    'gross_pnl_pct', 'gross_pnl_usdt', 'net_pnl_pct', 'net_pnl_usdt',
    'fees', 'slippage', 'total_costs', 'reason', 'duration', 'condition_types',
    'trading_mode', 'setup_id', 'tp_sl_mode',
    'break_even_triggered', 'trailing_stop_triggered', 'partial_tp_triggered',
    'tp_escalier_enabled', 'tp_escalier_levels_hit', 'tp_escalier_profits',
    'max_pnl_reached', 'min_pnl_reached', 'max_drawdown_intra',
    'early_invalidation_threshold', 'early_invalidation_elapsed',
    'trailing_stop_updates',
    'is_backtest', 'backtest_id', 'config_hash', 'session_id',
    'is_live_trade', 'is_dry_run', 'live_execution_mode',
    'entry_order_id', 'entry_order_type', 'entry_requested_price', 'entry_fill_price',
    'entry_slippage_pct', 'entry_latency_ms', 'entry_timestamp', 'entry_api_response',
    'exit_order_id', 'exit_order_type', 'exit_requested_price', 'exit_fill_price',
    'exit_slippage_pct', 'exit_latency_ms', 'exit_timestamp', 'exit_api_response',
    'leverage_used', 'margin_mode', 'position_size_usdt', 'position_size_contracts',
    'liquidation_price', 'margin_used',
    'maker_fee_rate', 'taker_fee_rate', 'entry_fee_usdt', 'exit_fee_usdt', 'total_fees_usdt',
    'funding_rate_at_entry', 'funding_rate_at_exit', 'funding_paid_usdt',
    'time_to_fill_entry_ms', 'time_to_fill_exit_ms', 'price_at_signal', 'price_at_order_sent',
    'signal_to_fill_slippage_pct', 'api_errors', 'retry_count', 'exchange_latency_ms', 'ws_latency_ms',
    'market_volatility_entry', 'spread_at_entry_pct', 'volume_24h_at_entry', 'orderbook_imbalance_entry', 'atr_at_entry',
    'market_volatility_exit', 'spread_at_exit_pct', 'volume_24h_at_exit', 'orderbook_imbalance_exit', 'atr_at_exit',
    'rsi_at_entry', 'macd_at_entry', 'bb_position_entry', 'adx_at_entry', 'di_plus_entry', 'di_minus_entry',
    'rsi_at_exit', 'macd_at_exit', 'bb_position_exit', 'adx_at_exit', 'di_plus_exit', 'di_minus_exit',
    'setup_score', 'ml_confidence', 'ml_prediction', 'ml_features',
    'optimal_exit_price', 'optimal_exit_time', 'missed_profit_pct', 'risk_reward_actual', 'risk_reward_planned',
    'trade_notes', 'trade_tags', 'user_rating',
    'instance_port', 'metadata'
]

print(f"\n\nTotal values provided: {len(values_provided)}")

# Find missing
missing = [c for c in cols if c not in values_provided]
print(f"\nMissing values (columns in INSERT but not in VALUES):")
for m in missing:
    idx = cols.index(m) + 1
    print(f"  {idx}. {m}")

# Find extra
extra = [v for v in values_provided if v not in cols]
print(f"\nExtra values (in VALUES but not in INSERT columns):")
for e in extra:
    print(f"  - {e}")
