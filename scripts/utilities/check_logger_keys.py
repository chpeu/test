import re

f = open('core/position/analytics_logger.py', 'r', encoding='utf-8').read()

start = f.find('trade_data = {')
end = f.find('# instance_port', start)
block = f[start:end]

lines = [l.strip() for l in block.split('\n') if ':' in l and not l.strip().startswith('#') and 'trade_data' not in l and l.strip() != '}']
keys = [l.split(':')[0].strip().strip("'").strip('"') for l in lines]

print(f'Total keys in analytics_logger trade_data: {len(keys)}')
print('\nAll keys:')
for i, k in enumerate(keys, 1):
    print(f'{i}. {k}')

# Compare with database columns
db_cols = [
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
    'metadata'  # instance_port is added by analytics_database.py
]

print(f'\n\nDatabase expects {len(db_cols)} values (+ instance_port auto-added = 114 total)')

missing = [c for c in db_cols if c not in keys]
print(f'\nMissing keys in analytics_logger (expected by database):')
for m in missing:
    print(f'  - {m}')

extra = [k for k in keys if k not in db_cols]
print(f'\nExtra keys in analytics_logger (not in database columns):')
for e in extra:
    print(f'  - {e}')
